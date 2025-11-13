# quizzes/consumers.py
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import QuizAttempt, Quiz

User = get_user_model()

class QuizRoomConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for quiz multiplayer rooms.
    Protocol (JSON messages):
    - join: {"type":"join","room":"room-123"}
    - answer: {"type":"answer","room":"room-123","question_id":12,"option_id":34}
    - ping: {"type":"ping"}
    """

    async def connect(self):
        # optional: only allow authenticated (cookie or token auth via querystring)
        await self.accept()
        self.room_name = None
        self.user = None

    async def receive_json(self, content):
        t = content.get("type")
        if t == "join":
            room = content.get("room")
            username = content.get("username") or "anonymous"
            self.room_name = f"quiz_{room}"
            await self.channel_layer.group_add(self.room_name, self.channel_name)
            self.user = username
            # announce
            await self.channel_layer.group_send(
                self.room_name,
                {"type": "user.joined", "user": username}
            )
            # send ack
            await self.send_json({"type": "joined", "room": room})
        elif t == "leave":
            if self.room_name:
                await self.channel_layer.group_send(self.room_name, {"type":"user.left", "user": content.get("username")})
                await self.channel_layer.group_discard(self.room_name, self.channel_name)
        elif t == "answer":
            # broadcast answer to room (server can check correctness)
            payload = {
                "type": "broadcast.answer",
                "user": content.get("username"),
                "question_id": content.get("question_id"),
                "option_id": content.get("option_id"),
            }
            await self.channel_layer.group_send(self.room_name, payload)
        elif t == "ping":
            await self.send_json({"type":"pong"})

    async def user_joined(self, event):
        await self.send_json({"type":"user_joined", "user": event["user"]})

    async def user_left(self, event):
        await self.send_json({"type":"user_left", "user": event["user"]})

    async def broadcast_answer(self, event):
        # echo to clients (frontends decide to show live ranks)
        await self.send_json({
            "type": "answer_broadcast",
            "user": event.get("user"),
            "question_id": event.get("question_id"),
            "option_id": event.get("option_id"),
        })

    async def disconnect(self, code):
        if self.room_name:
            await self.channel_layer.group_discard(self.room_name, self.channel_name)
