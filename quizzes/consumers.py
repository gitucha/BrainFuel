# quizzes/consumers.py
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

class QuizRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # accept connection, we'll verify token on join if provided
        await self.accept()
        self.room_group_name = None
        self.user = AnonymousUser()

        # Attempt quick token read from query_string (non-blocking)
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = qs.get("token", [None])[0]
        if token:
            try:
                validated = UntypedToken(token)
                jwt_auth = JWTAuthentication()
                # get_user expects validated token, but JWTAuthentication exposes get_user() differently;
                # we use database_sync_to_async wrapper to call authentication
                user = await database_sync_to_async(jwt_auth.get_user)(validated)
                self.user = user
            except Exception:
                self.user = AnonymousUser()

    async def receive_json(self, content, **kwargs):
        t = content.get("type")
        if t == "join":
            room = content.get("room")
            username = content.get("username") or (getattr(self.user, "username", "Anonymous"))
            if not room:
                await self.send_json({"type": "error", "message": "room required"})
                return

            self.room_group_name = f"quiz_{room}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)

            # notify group
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "user.joined", "user": username}
            )
            await self.send_json({"type": "joined", "room": room, "username": username})

        elif t == "answer":
            # broadcast user's answer to group
            room = content.get("room")
            if not room:
                await self.send_json({"type": "error", "message": "room required"})
                return
            username = content.get("username") or getattr(self.user, "username", "Anonymous")
            payload = {
                "type": "answer.broadcast",
                "user": username,
                "question_id": content.get("question_id"),
                "option_id": content.get("option_id"),
                "score_delta": content.get("score_delta", 0),
            }
            await self.channel_layer.group_send(f"quiz_{room}", payload)

        elif t == "leave":
            room = content.get("room")
            if room:
                await self.channel_layer.group_discard(f"quiz_{room}", self.channel_name)
                await self.send_json({"type": "left", "room": room})

    async def user_joined(self, event):
        await self.send_json({"type": "user_joined", "user": event["user"]})

    async def answer_broadcast(self, event):
        # event fields: user, question_id, option_id, score_delta
        await self.send_json({
            "type": "answer_broadcast",
            "user": event.get("user"),
            "question_id": event.get("question_id"),
            "option_id": event.get("option_id"),
            "score_delta": event.get("score_delta", 0),
        })

    async def disconnect(self, close_code):
        if self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
