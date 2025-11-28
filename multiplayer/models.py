# multiplayer/models.py
from django.db import models
from django.conf import settings
import uuid


class Room(models.Model):
    """
    Room model for multiplayer lobby / join by code.
    HTTP API stores room meta; WebSocket consumer keeps in-memory game state.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTIVE = "active", "Active"
        FINISHED = "finished", "Finished"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="hosted_rooms",
    )

    # Optional: which quiz this room is based on (can be null → random pool)
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="multiplayer_rooms",
    )

    is_public = models.BooleanField(default=True)
    difficulty = models.CharField(max_length=20, default="easy")
    question_count = models.PositiveIntegerField(default=5)
    max_players = models.PositiveIntegerField(default=8)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )

    # Simple flag if you want to “archive” rooms later
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        kind = "public" if self.is_public else "private"
        return f"{self.code} ({kind}, {self.status})"


class RoomParticipant(models.Model):
    """
    Optional participant table used by REST endpoints for lobby/room detail.
    WebSocket logic still keeps its own in-memory player list.
    """
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="multiplayer_participations",
    )
    is_spectator = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("room", "user")

    def __str__(self):
        return f"{self.user.username} in {self.room.code}"
