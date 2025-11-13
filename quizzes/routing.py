from django.urls import re_path
from .consumers import QuizRoomConsumer

websocket_urlpatterns = [
    re_path(r"ws/quiz/(?P<room_name>[^/]+)/$", QuizRoomConsumer.as_asgi()),
]
