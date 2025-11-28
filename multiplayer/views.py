# multiplayer/views.py

from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404
from django.db.models import Q

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import get_user_model
from quizzes.models import Quiz
from .models import Room

User = get_user_model()


def _generate_room_code(length: int = 6) -> str:
    """Generate a simple alphanumeric room code."""
    return get_random_string(length=length).upper()


# -------------------------------------------------------------------
#  ROOM LIST / CREATE
#   GET  /api/multiplayer/rooms/      -> rooms you host / participate in
#   POST /api/multiplayer/rooms/      -> create a new room
# -------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rooms_collection(request):
    user = request.user

    if request.method == "GET":
        # rooms where user is host or participant
        rooms = (
            Room.objects.filter(
                Q(host=user) | Q(participants__user=user)
            )
            .distinct()
            .order_by("-created_at")
        )

        data = [
            {
                "code": r.code,
                "quiz_id": r.quiz_id,
                "quiz_title": r.quiz.title if r.quiz else None,
                "host_id": r.host_id,
                "host_username": r.host.username if r.host else None,
                "is_public": r.is_public,
                "status": r.status,
                "difficulty": r.difficulty,
                "question_count": r.question_count,
                "max_players": r.max_players,
                "created_at": r.created_at,
            }
            for r in rooms
        ]
        return Response(data, status=status.HTTP_200_OK)

    # POST – create room
    quiz_id = request.data.get("quiz_id")
    is_public = request.data.get("is_public", True)
    difficulty = request.data.get("difficulty", "easy")
    question_count = request.data.get("question_count", 5)
    max_players = request.data.get("max_players", 8)

    if quiz_id is None:
        return Response(
            {"detail": "quiz_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    quiz = get_object_or_404(Quiz, pk=quiz_id, status="approved")

    # ensure ints
    try:
        question_count = int(question_count)
    except (TypeError, ValueError):
        question_count = 5

    try:
        max_players = int(max_players)
    except (TypeError, ValueError):
        max_players = 8

    # generate unique code
    code = _generate_room_code()
    while Room.objects.filter(code=code).exists():
        code = _generate_room_code()

    room = Room.objects.create(
        code=code,
        host=user,
        quiz=quiz,
        is_public=bool(is_public),
        difficulty=str(difficulty),
        question_count=question_count,
        max_players=max_players,
        status=Room.Status.WAITING,
    )

    # Ensure host is in participants if relation exists
    if hasattr(room, "participants"):
        room.participants.get_or_create(user=user, defaults={"is_spectator": False})

    return Response(
        {
            "code": room.code,
            "quiz_id": room.quiz_id,
            "quiz_title": room.quiz.title if room.quiz else None,
            "host_id": room.host_id,
            "host_username": room.host.username if room.host else None,
            "is_public": room.is_public,
            "status": room.status,
            "difficulty": room.difficulty,
            "question_count": room.question_count,
            "max_players": room.max_players,
        },
        status=status.HTTP_201_CREATED,
    )


# -------------------------------------------------------------------
#  ROOM DETAIL / JOIN / START / REMATCH
# -------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def room_detail(request, code: str):
    room = get_object_or_404(Room, code=code)

    participants = []
    if hasattr(room, "participants"):
        for p in room.participants.select_related("user").all():
            participants.append(
                {
                    "user_id": p.user_id,
                    "username": p.user.username,
                    "is_spectator": getattr(p, "is_spectator", False),
                    "score": getattr(p, "score", 0),
                }
            )

    data = {
        "code": room.code,
        "quiz_id": room.quiz_id,
        "quiz_title": room.quiz.title if room.quiz else None,
        "host_id": room.host_id,
        "host_username": room.host.username if room.host else None,
        "is_public": room.is_public,
        "status": room.status,
        "difficulty": room.difficulty,
        "question_count": room.question_count,
        "max_players": room.max_players,
        "created_at": room.created_at,
        "participants": participants,
    }
    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_room(request, code: str):
    user = request.user
    room = get_object_or_404(Room, code=code)

    # simple rule: only join if room is waiting or active
    if room.status not in (Room.Status.WAITING, Room.Status.ACTIVE):
        return Response(
            {"detail": "Room is not joinable."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    is_spectator = bool(request.data.get("is_spectator", False))

    if hasattr(room, "participants"):
        part, created = room.participants.get_or_create(
            user=user,
            defaults={"is_spectator": is_spectator},
        )
        if not created and part.is_spectator != is_spectator:
            part.is_spectator = is_spectator
            part.save()

    return Response(
        {
            "code": room.code,
            "quiz_id": room.quiz_id,
            "quiz_title": room.quiz.title if room.quiz else None,
            "is_spectator": is_spectator,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_match(request, code: str):
    room = get_object_or_404(Room, code=code)

    if room.host_id != request.user.id:
        return Response(
            {"detail": "Only host can start the match."},
            status=status.HTTP_403_FORBIDDEN,
        )

    room.status = Room.Status.ACTIVE
    room.save(update_fields=["status"])

    return Response(
        {"detail": "Match started.", "status": room.status},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rematch(request, code: str):
    room = get_object_or_404(Room, code=code)
    if room.host_id != request.user.id:
        return Response(
            {"detail": "Only host can request rematch."},
            status=status.HTTP_403_FORBIDDEN,
        )

    room.status = Room.Status.WAITING
    room.save(update_fields=["status"])

    return Response(
        {"detail": "Rematch requested.", "status": room.status},
        status=status.HTTP_200_OK,
    )


# -------------------------------------------------------------------
#  PUBLIC LOBBY
#   GET /api/multiplayer/lobby/
# -------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # or AllowAny if you want
def public_lobby(request):
    """
    List public rooms that are joinable (waiting or active).
    """
    rooms = Room.objects.filter(is_public=True).exclude(
        status=Room.Status.FINISHED
    )

    data = [
        {
            "code": r.code,
            "quiz_id": r.quiz_id,
            "quiz_title": r.quiz.title if r.quiz else None,
            "host_username": r.host.username if r.host else None,
            "status": r.status,
            "difficulty": r.difficulty,
            "question_count": r.question_count,
            "max_players": r.max_players,
            "created_at": r.created_at,
        }
        for r in rooms
    ]
    return Response(data, status=status.HTTP_200_OK)
