# multiplayer/views.py
import random
import string

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Room


def _generate_code(length=6):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(chars) for _ in range(length))
        if not Room.objects.filter(code=code).exists():
            return code


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def list_rooms(request):
    if request.method == "POST":
        return create_room(request)
    """
    GET /api/multiplayer/rooms/
    List active public rooms for the lobby.
    """
    rooms = (
        Room.objects.filter(is_public=True, is_active=True)
        .order_by("-created_at")[:50]
    )

    data = [
        {
            "id": str(r.id),
            "room_id": str(r.id),
            "code": r.code,
            "host_username": r.host.username if r.host else None,
            "difficulty": r.difficulty,
            "count": r.question_count,
            "max_players": r.max_players,
            #/socket layer knows actual players; here just expose "unknown/1"
            "current_players": 1,
        }
        for r in rooms
    ]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_room(request):
    """
    POST /api/multiplayer/rooms/
    Body: { "is_public": true/false, "difficulty"?: "easy", "count"?: 5 }
    """
    user = request.user
    is_public = bool(request.data.get("is_public", True))
    difficulty = (request.data.get("difficulty") or "easy").lower()
    count = int(request.data.get("count", 5))

    # clamp count 1–10 just like elsewhere
    count = max(1, min(10, count))

    room = Room.objects.create(
        code=_generate_code(),
        host=user,
        is_public=is_public,
        difficulty=difficulty,
        question_count=count,
    )

    payload = {
        "id": str(room.id),
        "room_id": str(room.id),
        "code": room.code,
        "difficulty": room.difficulty,
        "count": room.question_count,
        "host_username": user.username,
        "is_public": room.is_public,
    }
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_room(request):
    """
    POST /api/multiplayer/rooms/join/
    Body: { "room_code": "ABC123" }
    """
    code = request.data.get("room_code") or request.data.get("code")
    if not code:
        return Response(
            {"detail": "room_code is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        room = Room.objects.get(code=code.upper(), is_active=True)
    except Room.DoesNotExist:
        return Response(
            {"detail": "Room not found or not active"},
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = {
        "id": str(room.id),
        "room_id": str(room.id),
        "code": room.code,
        "difficulty": room.difficulty,
        "count": room.question_count,
        "host_username": room.host.username if room.host else None,
        "is_public": room.is_public,
    }
    return Response(payload, status=status.HTTP_200_OK)
