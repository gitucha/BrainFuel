# multiplayer/routing.py
from django.urls import re_path
from .consumers import QuizRoomConsumer

websocket_urlpatterns = [
    re_path(r"^ws/quiz/(?P<room_code>[A-Za-z0-9]+)/$", QuizRoomConsumer.as_asgi()),
]
