from rest_framework import generics, permissions
from django.db.models import Sum
from django.contrib.auth import get_user_model
from .serializers import LeaderboardSerializer
from quizzes.models import QuizAttempt
from premium.models import Payment
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from quizzes.models import Quiz
from django.db import models
import csv, io

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

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_summary(request):
    total_users = User.objects.count()
    premium_users = User.objects.filter(is_premium=True).count()
    total_quizzes = Quiz.objects.count()
    total_attempts = QuizAttempt.objects.count()
    total_revenue = Payment.objects.filter(status="SUCCESS").aggregate(total=models.Sum("amount"))["total"] or 0

    data = {
        "total_users": total_users,
        "premium_users": premium_users,
        "total_quizzes": total_quizzes,
        "total_attempts": total_attempts,
        "total_revenue": total_revenue,
    }
    return Response(data)