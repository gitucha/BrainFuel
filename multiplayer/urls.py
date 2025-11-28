# multiplayer/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # collection
    path("rooms/", views.rooms_collection, name="mp-rooms-collection"),  # GET, POST

    # room detail / actions
    path("rooms/<str:code>/", views.room_detail, name="mp-room-detail"),
    path("rooms/<str:code>/join/", views.join_room, name="mp-room-join"),
    path("rooms/<str:code>/start/", views.start_match, name="mp-room-start"),
    path("rooms/<str:code>/rematch/", views.rematch, name="mp-room-rematch"),

    # public lobby
    path("lobby/", views.public_lobby, name="mp-lobby"),
]
