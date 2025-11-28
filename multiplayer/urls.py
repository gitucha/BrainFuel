# multiplayer/urls.py
from django.urls import path
from .views import list_rooms, create_room, join_room

urlpatterns = [
    path("rooms/", list_rooms, name="multiplayer-rooms"),        # GET
    path("rooms/join/", join_room, name="multiplayer-join"),
    path("rooms/create/", create_room, name="multiplayer-create"),
]
