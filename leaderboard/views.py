from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from .serializers import LeaderboardSerializer

User = get_user_model()

class LeaderboardView(generics.ListAPIView):
    queryset = User.objects.filter(xp__gt=0).order_by('-xp')
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.AllowAny]