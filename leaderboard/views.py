from rest_framework import generics, permissions
from django.db.models import Sum
from django.contrib.auth import get_user_model
from .serializers import LeaderboardSerializer
from quizzes.models import QuizAttempt

User = get_user_model()

class LeaderboardView(generics.ListAPIView):
    queryset = User.objects.filter(xp__gt=0).order_by('-xp')
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.AllowAny]

class GlobalLeaderboardView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return User.objects.all().order_by("-xp")[:50]

class CategoryLeaderboardView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        category = self.kwargs["category"]
        return User.objects.filter(quizattempt__quiz__category=category).annotate(
            total_xp=Sum("quizattempt__score")
        ).order_by("-total_xp")[:50]
