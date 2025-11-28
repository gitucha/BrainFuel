# multiplayer/consumers.py
import json
import random

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from quizzes.models import Quiz, Question, Option
from .models import Room

User = get_user_model()

# In-memory game state (good enough for dev / single worker)
# ROOM_STATE[room_code] = {
#   "players": {
#       user_id: {
#           "id": int,
#           "username": str,
#           "is_spectator": bool,
#           "score": int,
#           "correct": int,
#           "total": int,
#       }
#   },
#   "host": user_id,
#   "questions": [ {id,text,options:[{id,text},...]}, ... ],
#   "current_index": int,
#   "started": bool,
#   "difficulty": str,
#   "count": int,
# }
ROOM_STATE = {}


class QuizRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """
        URL: /ws/quiz/<room_code>/?difficulty=&count=&role=
        """
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        self.group_name = f"quiz_{self.room_code}"

        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close()
            return

        # Parse query string
        query_string = self.scope["query_string"].decode()
        params = {}
        if query_string:
            for pair in query_string.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        difficulty = (params.get("difficulty") or "easy").lower()
        try:
            count = int(params.get("count") or 5)
        except ValueError:
            count = 5
        count = max(1, min(10, count))

        role = (params.get("role") or "player").lower()
        is_spectator = role == "spectator"

        # Join group & accept
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Init / update room state
        state = ROOM_STATE.get(self.room_code)
        if state is None:
            state = {
                "players": {},
                "host": None,
                "questions": [],
                "current_index": 0,
                "started": False,
                "difficulty": difficulty,
                "count": count,
            }

        uid = user.id
        if uid not in state["players"]:
            state["players"][uid] = {
                "id": uid,
                "username": user.username,
                "is_spectator": is_spectator,
                "score": 0,
                "correct": 0,
                "total": 0,
            }

        # Choose host: first non-spectator if possible
        if not state["host"]:
            non_specs = [p for p in state["players"].values() if not p["is_spectator"]]
            if non_specs:
                state["host"] = non_specs[0]["id"]
            else:
                state["host"] = uid

        ROOM_STATE[self.room_code] = state

        # Keep DB Room metadata in sync (difficulty, count, active)
        await self._mark_room_active(difficulty, count)

        # Send initial state to everyone
        await self._broadcast_state()

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        uid = user.id
        if uid in state["players"]:
            del state["players"][uid]

        # reassign host if needed
        if state["host"] == uid:
            remaining = list(state["players"].values())
            if remaining:
                non_specs = [p for p in remaining if not p["is_spectator"]]
                state["host"] = non_specs[0]["id"] if non_specs else remaining[0]["id"]
            else:
                # nobody left -> delete room state
                ROOM_STATE.pop(self.room_code, None)
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                return

        ROOM_STATE[self.room_code] = state
        await self._broadcast_state()

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
        Handle incoming messages from clients.
        Expected shapes:
          { "type": "start_game", "difficulty": "easy", "count": 5 }
          { "type": "answer", "option_id": 123 }
        """
        action = content.get("type") or content.get("action")

        if action == "start_game":
            await self._handle_start_game(content)
        elif action == "answer":
            await self._handle_answer(content)

    # -----------------------------
    # Game logic helpers
    # -----------------------------

    async def _handle_start_game(self, content):
        user = self.scope["user"]
        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        # only host can start/rematch
        if state["host"] != user.id:
            return

        difficulty = (content.get("difficulty") or state.get("difficulty") or "easy").lower()
        try:
            count = int(content.get("count") or state.get("count") or 5)
        except ValueError:
            count = 5
        count = max(1, min(10, count))

        # reset per-player scores
        for p in state["players"].values():
            p["score"] = 0
            p["correct"] = 0
            p["total"] = 0

        # fetch questions
        questions = await self._fetch_questions(difficulty, count)
        state["difficulty"] = difficulty
        state["count"] = count
        state["questions"] = questions
        state["current_index"] = 0
        state["started"] = True

        ROOM_STATE[self.room_code] = state

        await self._broadcast_state()
        await self._send_current_question()

    async def _handle_answer(self, content):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        state = ROOM_STATE.get(self.room_code)
        if not state or not state["started"]:
            return

        uid = user.id
        player = state["players"].get(uid)
        if not player or player["is_spectator"]:
            # spectators cannot answer
            return

        option_id = content.get("option_id")
        if not option_id:
            return

        idx = state["current_index"]
        if idx >= len(state["questions"]):
            return

        question = state["questions"][idx]
        qid = question["id"]

        is_correct = await self._check_answer(qid, option_id)

        player["total"] += 1
        if is_correct:
            player["correct"] += 1
            player["score"] += 10

        # For simplicity: advance immediately on answer
        await self._advance_or_finish()

    async def _advance_or_finish(self):
        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        state["current_index"] += 1
        if state["current_index"] >= len(state["questions"]):
            # Game over
            state["started"] = False
            ROOM_STATE[self.room_code] = state
            await self._send_results()
        else:
            ROOM_STATE[self.room_code] = state
            await self._send_current_question()

    async def _send_current_question(self):
        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        idx = state["current_index"]
        if idx >= len(state["questions"]):
            return

        q = state["questions"][idx]
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "quiz.message",
                "event": "question",
                "payload": {
                    "question": q,
                    "index": idx,
                    "total": len(state["questions"]),
                },
            },
        )

    async def _send_results(self):
        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        players = [p for p in state["players"].values() if not p["is_spectator"]]
        ranking = sorted(players, key=lambda p: (-p["score"], -p["correct"]))

        ranking_payload = []
        for p in ranking:
            xp = p["correct"] * 10
            thalers = p["correct"] * 2
            await self._apply_rewards(p["id"], xp, thalers)
            ranking_payload.append(
                {
                    "user_id": p["id"],
                    "username": p["username"],
                    "correct": p["correct"],
                    "total": p["total"],
                    "score": p["score"],
                    "xp_earned": xp,
                    "thalers_earned": thalers,
                }
            )

        summary = {
            "total_questions": len(state["questions"]),
        }

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "quiz.message",
                "event": "results",
                "payload": {
                    "summary": summary,
                    "ranking": ranking_payload,
                },
            },
        )

    async def _broadcast_state(self):
        state = ROOM_STATE.get(self.room_code)
        if not state:
            return

        players_list = list(state["players"].values())
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "quiz.message",
                "event": "state_update",
                "payload": {
                    "players": players_list,
                    "host": state["host"],
                    "started": state["started"],
                    "questionIndex": state["current_index"],
                    "totalQuestions": len(state["questions"]),
                },
            },
        )

    async def quiz_message(self, event):
        """
        Called when group_send with type='quiz.message' is triggered.
        """
        event_type = event.get("event")
        payload = event.get("payload", {})

        if event_type == "state_update":
            await self.send_json({"type": "state_update", "data": payload})
        elif event_type == "question":
            # payload: {question, index, total}
            await self.send_json({"type": "question", **payload})
        elif event_type == "results":
            await self.send_json({"type": "results", "payload": payload})

    # -----------------------------
    # DB helpers
    # -----------------------------

    @database_sync_to_async
    def _fetch_questions(self, difficulty, count):
        """
        Pick random questions from approved quizzes, optionally filtering by difficulty.
        """
        quizzes = Quiz.objects.filter(status="approved")
        if difficulty in ["easy", "medium", "hard"]:
            quizzes = quizzes.filter(difficulty__iexact=difficulty)

        qs = Question.objects.filter(quiz__in=quizzes).prefetch_related("options")
        total = qs.count()
        if total == 0:
            return []

        sample_count = min(count, total)
        sampled = random.sample(list(qs), sample_count)

        questions_payload = []
        for q in sampled:
            questions_payload.append(
                {
                    "id": q.id,
                    "text": q.text,
                    "options": [{"id": o.id, "text": o.text} for o in q.options.all()],
                }
            )
        return questions_payload

    @database_sync_to_async
    def _check_answer(self, question_id, option_id):
        try:
            opt = Option.objects.get(pk=option_id, question_id=question_id)
            return opt.is_correct
        except Option.DoesNotExist:
            return False

    @database_sync_to_async
    def _apply_rewards(self, user_id, xp, thalers):
        try:
            u = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return

        u.xp = (u.xp or 0) + xp
        u.thalers = (u.thalers or 0) + thalers

        while u.xp >= u.level * 100:
            u.level += 1

        u.save()

    @database_sync_to_async
    def _mark_room_active(self, difficulty, count):
        """
        If a Room was created via REST, keep its metadata aligned.
        If not found, create a lightweight one (for debugging).
        """
        try:
            room = Room.objects.filter(code=self.room_code).first()
        except Exception:
            room = None

        if room:
            room.is_active = True
            room.difficulty = difficulty
            room.question_count = count
            if room.status != Room.Status.ACTIVE:
                room.status = Room.Status.ACTIVE
            room.save()
        else:
            from django.utils.crypto import get_random_string

            Room.objects.create(
                code=self.room_code,
                host=None,
                is_public=False,
                difficulty=difficulty,
                question_count=count,
                status=Room.Status.ACTIVE,
            )
