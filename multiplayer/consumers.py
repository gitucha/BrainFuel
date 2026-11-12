# multiplayer/consumers.py
import json
import random
import string

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from django.contrib.auth import get_user_model

from quizzes.models import Quiz, Question, Option
from .models import Room

User = get_user_model()

# In-memory game state (dev only)
ROOM_STATE = {}
# ROOM_STATE[room_code] = {
#   "players": { user_id: { id, username, is_spectator, score, correct, total } },
#   "host": user_id,
#   "questions": [ { id, text, options: [{id, text}, ...] }, ... ],
#   "current_index": 0,
#   "started": False,
#   "difficulty": "easy",
#   "count": 5,
# }

def _generate_temp_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


class QuizRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """
        WebSocket URL: /ws/quiz/<room_code>/?difficulty=&count=&role=
        Uses room_code (not numeric DB id).
        """
        # room identifier (we expect the room code in the URL)
        self.room_id = self.scope["url_route"]["kwargs"].get("room_id")
        self.group_name = f"quiz_{self.room_id}"

        user = self.scope["user"]
        print(f"[WS] connect attempt - room_id={self.room_id} user={getattr(user, 'id', None)}")

        if not user or not user.is_authenticated:
            print("[WS] unauthenticated - closing")
            await self.close()
            return

        # parse query params (simple parse of scope['query_string'])
        query_string = self.scope.get("query_string", b"").decode()
        params = {}
        if query_string:
            for pair in query_string.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        difficulty = params.get("difficulty", "easy").lower()
        try:
            count = int(params.get("count", "5") or 5)
        except (TypeError, ValueError):
            count = 5
        count = max(1, min(10, count))

        role = params.get("role", "player").lower()
        is_spectator = role == "spectator"

        # join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"[WS] accepted - joined group {self.group_name}")

        # init / update room state
        state = ROOM_STATE.get(self.room_id)
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
            print(f"[WS] added player {user.username} ({uid}) to state for room {self.room_id}")

        # choose host: first non-spectator player, or keep existing
        if not state["host"]:
            non_specs = [p for p in state["players"].values() if not p["is_spectator"]]
            if non_specs:
                state["host"] = non_specs[0]["id"]
            else:
                state["host"] = uid

        ROOM_STATE[self.room_id] = state

        # keep DB room metadata in sync (optional)
        await self._mark_room_active(difficulty, count)

        # broadcast current state to group
        await self._broadcast_state()

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        print(f"[WS] disconnect user={user.id} from room {self.room_id}")

        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        uid = user.id
        if uid in state["players"]:
            del state["players"][uid]
            print(f"[WS] removed player {uid} from in-memory state")

        # reassign host if needed, or clear room if empty
        if state.get("host") == uid:
            remaining = list(state["players"].values())
            if remaining:
                non_specs = [p for p in remaining if not p["is_spectator"]]
                state["host"] = non_specs[0]["id"] if non_specs else remaining[0]["id"]
                print(f"[WS] reassigned host to {state['host']}")
            else:
                ROOM_STATE.pop(self.room_id, None)
                print(f"[WS] no players left; cleared ROOM_STATE for {self.room_id}")
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                return

        ROOM_STATE[self.room_id] = state
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self._broadcast_state()

        if state.get("started") and self._everyone_answered(state):
            await self._advance_or_finish()

    async def receive_json(self, content, **kwargs):
        """
        Client -> server messages:
          { action: "start_game", difficulty, count }
          { action: "answer", option_id: 123 }
        """
        action = content.get("action")
        print(f"[WS] receive_json action={action} from user={getattr(self.scope.get('user'), 'id', None)}")

        if action == "start_game":
            await self._handle_start_game(content)
        elif action == "answer":
            await self._handle_answer(content)
        else:
            print(f"[WS] unknown action: {action}")

    # -----------------------------
    # Game flow handlers
    # -----------------------------

    async def _handle_start_game(self, content):
        """
        Host requested start. This sets up questions in memory and
        broadcasts a start_with_questions event (group_send). The
        quiz_message handler will then call _handle_start_with_questions.
        """
        user = self.scope["user"]
        state = ROOM_STATE.get(self.room_id)
        print(f"[WS] _handle_start_game called by {user.id} in room {self.room_id}")

        if not state:
            print("[WS] no state; abort start")
            return

        if state.get("host") != user.id:
            print("[WS] start_game - user is not host; ignoring")
            return

        difficulty = (content.get("difficulty") or state.get("difficulty") or "easy").lower()
        try:
            count = int(content.get("count") or state.get("count") or 5)
        except (TypeError, ValueError):
            count = state.get("count", 5)
        count = max(1, min(10, count))

        # reset scores
        for p in state["players"].values():
            p["score"] = 0
            p["correct"] = 0
            p["total"] = 0

        # fetch questions from DB
        questions = await self._fetch_questions(difficulty, count)
        print(f"[WS] fetched {len(questions)} questions for room {self.room_id}")

        if not questions:
            # notify group that no questions were available
            state["started"] = False
            ROOM_STATE[self.room_id] = state
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "quiz.message",
                    "event": "no_questions",
                    "payload": {"detail": "No questions available for this match."},
                },
            )
            return

        # update in-memory state
        state["difficulty"] = difficulty
        state["count"] = count
        state["questions"] = questions
        state["current_index"] = 0
        state["answered"] = set()
        state["started"] = True
        ROOM_STATE[self.room_id] = state

        # broadcast state update first
        await self._broadcast_state()

        # send a start marker (consumers will handle it via quiz_message)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "quiz.message",
                "event": "start_with_questions",
                "payload": {
                    "questions_count": len(questions),
                    "difficulty": difficulty,
                    "count": count,
                    # optionally include first question payload, but we'll call _send_current_question below
                },
            },
        )
        print(f"[WS] group_send start_with_questions for {self.group_name}")

    async def _handle_start_with_questions(self, payload):
        """
        Called in EVERY consumer of the room when 'start_with_questions' is
        group-sent, either by the host's start_game action or by the REST
        start endpoint (which includes the questions in the payload).

        Each consumer sends the first question to its own client only.
        (Group-sending here would deliver N copies of each question.)
        """
        state = ROOM_STATE.get(self.room_id)
        if state is None:
            return

        questions = payload.get("questions")
        if questions and state.get("questions") != questions:
            # Started via REST: load the questions into the in-memory game.
            for p in state["players"].values():
                p["score"] = 0
                p["correct"] = 0
                p["total"] = 0
            state["questions"] = questions
            state["difficulty"] = payload.get("difficulty", state.get("difficulty"))
            state["count"] = len(questions)
            state["current_index"] = 0
            state["answered"] = set()
            state["started"] = True

        if not state.get("questions"):
            return

        idx = state.get("current_index", 0)
        await self.send_json(
            {
                "type": "question",
                "question": state["questions"][idx],
                "index": idx,
                "total": len(state["questions"]),
            }
        )

    async def _handle_answer(self, content):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            return

        state = ROOM_STATE.get(self.room_id)
        if not state or not state.get("started"):
            print("[WS] answer received but game not started")
            return

        uid = user.id
        player = state["players"].get(uid)
        if not player or player.get("is_spectator"):
            print("[WS] answer from spectator or unknown player; ignoring")
            return

        option_id = content.get("option_id")
        if option_id is None:
            return

        idx = state.get("current_index", 0)
        if idx >= len(state.get("questions", [])):
            return

        answered = state.setdefault("answered", set())
        if uid in answered:
            return  # already answered this question
        answered.add(uid)

        question = state["questions"][idx]
        qid = question["id"]

        is_correct = await self._check_answer(qid, option_id)

        player["total"] = player.get("total", 0) + 1
        if is_correct:
            player["correct"] = player.get("correct", 0) + 1
            player["score"] = player.get("score", 0) + 10

        await self._broadcast_state()

        # Move on only once every (non-spectator) player has answered.
        if self._everyone_answered(state):
            await self._advance_or_finish()

    @staticmethod
    def _everyone_answered(state):
        active = {p["id"] for p in state["players"].values() if not p.get("is_spectator")}
        return active.issubset(state.get("answered", set()))

    async def _advance_or_finish(self):
        state = ROOM_STATE.get(self.room_id)
        if not state:
            return

        state["current_index"] = state.get("current_index", 0) + 1
        state["answered"] = set()
        if state["current_index"] >= len(state.get("questions", [])):
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

        idx = state.get("current_index", 0)
        if idx >= len(state.get("questions", [])):
            # Nothing to send
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "quiz.message",
                    "event": "status",
                    "payload": {"status": "waiting", "message": "No more questions."},
                },
            )
            return

        q = state["questions"][idx]
        print(f"[WS] sending question index={idx} id={q.get('id')} to group {self.group_name}")
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

        players = [p for p in state["players"].values() if not p.get("is_spectator")]
        ranking = sorted(players, key=lambda p: (-p.get("score", 0), -p.get("correct", 0)))

        ranking_payload = []
        for p in ranking:
            xp = p.get("correct", 0) * 10
            thalers = p.get("correct", 0) * 2
            # apply rewards in DB
            await self._apply_rewards(p["id"], xp, thalers)
            ranking_payload.append(
                {
                    "user_id": p["id"],
                    "username": p["username"],
                    "correct": p.get("correct", 0),
                    "total": p.get("total", 0),
                    "score": p.get("score", 0),
                    "xp_earned": xp,
                    "thalers_earned": thalers,
                }
            )

        summary = {"total_questions": len(state.get("questions", []))}
        print(f"[WS] broadcasting results for room {self.room_id}")

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "quiz.message",
                "event": "results",
                "payload": {"summary": summary, "ranking": ranking_payload},
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
                    "host": state.get("host"),
                    "started": state.get("started"),
                    "questionIndex": state.get("current_index"),
                    "totalQuestions": len(state.get("questions", [])),
                },
            },
        )

    # -----------------------------
    # Group -> consumer routing
    # -----------------------------

    async def quiz_message(self, event):
        """
        This receives group messages (from channel_layer.group_send).
        We inspect the 'event' field and dispatch accordingly.
        """
        ev = event.get("event")
        payload = event.get("payload", {})
        print(f"[WS] quiz_message received event={ev} payload_keys={list(payload.keys())} for room {self.room_id}")

        # handle start marker by delegating to the start-with-questions handler
        if ev == "start_with_questions":
            print("[WS] quiz_message -> calling _handle_start_with_questions")
            await self._handle_start_with_questions(payload)
            return

        if ev == "state_update":
            await self.send_json({"type": "state_update", "data": payload})
            return

        if ev == "question":
            # forward question payload directly
            await self.send_json({"type": "question", **payload})
            return

        if ev == "results":
            await self.send_json({"type": "results", "payload": payload})
            return

        if ev == "status":
            await self.send_json({"type": "status", "payload": payload})
            return

        if ev == "no_questions":
            await self.send_json({"type": "no_questions", "payload": payload})
            return

        # unknown event
        print(f"[WS] unknown group event: {ev}")

    # -----------------------------
    # DB helpers (sync -> async)
    # -----------------------------

    @database_sync_to_async
    def _fetch_questions(self, difficulty, count):
        """
        Fetch random questions (with options) from approved quizzes.
        Try to respect difficulty; if none exist, fall back to any approved quiz.
        Returns list of dicts: {id, text, options: [{id, text}, ...]}
        """
        base_quizzes = Quiz.objects.filter(status="approved")
        if difficulty in ["easy", "medium", "hard"]:
            quizzes = base_quizzes.filter(difficulty__iexact=difficulty)
        else:
            quizzes = base_quizzes

        qs = Question.objects.filter(quiz__in=quizzes).prefetch_related("options")
        if qs.count() == 0:
            # fallback to any approved quiz
            qs = Question.objects.filter(quiz__in=base_quizzes).prefetch_related("options")

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
            return bool(opt.is_correct)
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
        # simple leveling
        leveled = False
        while u.xp >= (u.level or 1) * 100:
            u.level = (u.level or 1) + 1
            leveled = True
        u.save()

    @database_sync_to_async
    def _mark_room_active(self, difficulty, count):
        """
        Keep DB room metadata in sync when possible.
        Uses room code (self.room_id).
        """
        # try find room by code
        room = Room.objects.filter(code=self.room_id).first()
        if room:
            changed = False
            if not room.is_active:
                room.is_active = True
                changed = True
            if room.difficulty != difficulty:
                room.difficulty = difficulty
                changed = True
            if room.question_count != count:
                room.question_count = count
                changed = True
            if changed:
                room.save()
        else:
            # create a lightweight placeholder (optional)
            try:
                Room.objects.create(
                    code=self.room_id,
                    host=None,
                    is_public=False,
                    difficulty=difficulty,
                    question_count=count,
                    is_active=True,
                )
            except Exception as e:
                print(f"[WS] _mark_room_active: could not create dummy Room: {e}")
