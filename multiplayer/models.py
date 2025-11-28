# multiplayer/models.py
from django.db import models
from django.conf import settings
import uuid


class Room(models.Model):
    """
    Simple room model for public lobby / join by code.
    Game state is handled in-memory in the WebSocket consumer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="hosted_rooms",
    )
    is_public = models.BooleanField(default=True)
    difficulty = models.CharField(max_length=20, default="easy")
    question_count = models.PositiveIntegerField(default=5)
    max_players = models.PositiveIntegerField(default=8)
    is_active = models.BooleanField(default=True)  # can mark finished rooms later

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({'public' if self.is_public else 'private'})"
