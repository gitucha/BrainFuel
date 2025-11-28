# multiplayer/consumers.py
import json
import random

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from django.contrib.auth import get_user_model

from quizzes.models import Quiz, Question, Option
from .models import Room

User = get_user_model()

# In-memory game state (OK for dev/single-worker; for production you’d
# push this into cache/redis).
ROOM_STATE = {}
# structure:
# ROOM_STATE[room_id] = {
#     "players": {
#         user_id: {
#             "id": user_id,
#             "username": "...",
#             "is_spectator": bool,
#             "score": 0,
#             "correct": 0,
#             "total": 0,
#         }
#     },
#     "host": user_id,
#     "questions": [ { "id": qid, "text": "...", "options": [...] }, ... ],
#     "current_index": 0,
#     "started": False,
# }


class QuizRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """
        Called on websocket connect.
        URL: /ws/quiz/<room_id>/?difficulty=&count=&role=
        """
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"quiz_{self.room_id}"

        # who is this user?
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close()
            return

        # parse query params
        query_string = self.scope["query_string"].decode()
        params = {}
        if query_string:
            for pair in query_string.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        difficulty = params.get("difficulty", "easy").lower()
        count = int(params.get("count", "5") or 5)
        role = params.get("role", "player").lower()
        is_spectator = role == "spectator"

        # join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # init / update room state
        state = ROOM_STATE.get(self.room_id)
        if state is None:
            # new room state
            state = {
                "players": {},
                "host": None,
                "questions": [],
                "current_index": 0,
                "started": False,
                "difficulty": difficulty,
                "count": count,
            }

        # register this player
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

        # choose host: first non-spectator player, or keep existing
        if not state["host"]:
            # first non-spectator if available, else whoever
            non_specs = [p for p in state["players"].values() if not p["is_spectator"]]
            if non_specs:
                state["host"] = non_specs[0]["id"]
            else:
                state["host"] = uid

        ROOM_STATE[self.room_id] = state

        # ensure DB room exists if coming from lobby
        await self._mark_room_active(difficulty, count)

        # send updated state to everyone
        await self._broadcast_state()

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        uid = user.id
        if uid in state["players"]:
            del state["players"][uid]

        # reassign host if needed
        if state["host"] == uid:
            remaining = list(state["players"].values())
            if remaining:
                # pick first non-spectator if possible
                non_specs = [p for p in remaining if not p["is_spectator"]]
                state["host"] = non_specs[0]["id"] if non_specs else remaining[0]["id"]
            else:
                # no one left → clear room state
                ROOM_STATE.pop(self.room_id, None)
                return

        ROOM_STATE[self.room_id] = state
        await self._broadcast_state()

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
        Handle messages from client.
        """
        action = content.get("action")

        if action == "start_game":
            await self._handle_start_game(content)
        elif action == "answer":
            await self._handle_answer(content)

    # -----------------------------
    # Helpers
    # -----------------------------

    async def _handle_start_game(self, content):
        user = self.scope["user"]
        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        # only host may start / rematch
        if state["host"] != user.id:
            return

        difficulty = (content.get("difficulty") or state.get("difficulty") or "easy").lower()
        count = int(content.get("count") or state.get("count") or 5)
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

        ROOM_STATE[self.room_id] = state

        # send first question
        await self._broadcast_state()
        await self._send_current_question()

    async def _handle_answer(self, content):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        state = ROOM_STATE.get(self.room_id)
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

        # we don't store all answers; just evaluate on the fly
        is_correct = await self._check_answer(qid, option_id)

        player["total"] += 1
        if is_correct:
          player["correct"] += 1
          player["score"] += 10

        # for simplicity: advance when *all non-spectator players answered*  
        # or allow repeated answers – this is basic. You can track per-question answers in state if you like.
        # Here we just move on when everyone has answered at least once for this question.
        # Minimal implementation: just advance immediately on user answer:
        await self._advance_or_finish()

    async def _advance_or_finish(self):
        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        state["current_index"] += 1
        if state["current_index"] >= len(state["questions"]):
            # game over
            state["started"] = False
            ROOM_STATE[self.room_id] = state
            await self._send_results()
        else:
            ROOM_STATE[self.room_id] = state
            await self._send_current_question()

    async def _send_current_question(self):
        state = ROOM_STATE.get(self.room_id)
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
        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        players = [
            p for p in state["players"].values() if not p["is_spectator"]
        ]

        ranking = sorted(
            players,
            key=lambda p: (-p["score"], -p["correct"]),
        )

        # xp/thalers; simple rule: 10 xp, 2 thalers per correct
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
        state = ROOM_STATE.get(self.room_id)
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
        Receive group message and send to websocket.
        """
        event_type = event.get("event")
        payload = event.get("payload", {})

        if event_type == "state_update":
            await self.send_json(
                {"type": "state_update", "data": payload}
            )
        elif event_type == "question":
            await self.send_json(
                {"type": "question", **payload}
            )
        elif event_type == "results":
            await self.send_json(
                {"type": "results", "payload": payload}
            )

    # -----------------------------
    # DB helpers
    # -----------------------------

    @database_sync_to_async
    def _fetch_questions(self, difficulty, count):
        """
        Pull random questions from approved quizzes of given difficulty.
        Adapts your existing quiz schema.
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
                    "options": [
                        {"id": o.id, "text": o.text}
                        for o in q.options.all()
                    ],
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
        # simple level-up rule (same as elsewhere)
        leveled_up = False
        while u.xp >= u.level * 100:
            u.level += 1
            leveled_up = True
        u.save()
        # achievement signals (if you have them) will fire off your model logic

    @database_sync_to_async
    def _mark_room_active(self, difficulty, count):
        """
        If room was created via REST, keep DB metadata in sync.
        If not, create a temp Room entry (for debugging).
        """
        try:
            room = Room.objects.filter(id=self.room_id).first()
        except Exception:
            room = None

        if room:
            if not room.is_active:
                room.is_active = True
            room.difficulty = difficulty
            room.question_count = count
            room.save()
        else:
            # optional fallback: create a dummy room
            Room.objects.create(
                id=self.room_id,
                code=_generate_temp_code(),
                host=None,
                is_public=False,
                difficulty=difficulty,
                question_count=count,
            )


def _generate_temp_code():
    import string, random

    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(6))
