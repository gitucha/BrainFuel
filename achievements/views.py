from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Achievement, UserAchievement
from .serializers import AchievementSerializer, UserAchievementSerializer

# View all available achievements
class AchievementListView(generics.ListAPIView):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = [permissions.AllowAny]


# View achievements earned by current user
class UserAchievementsView(generics.ListAPIView):
    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserAchievement.objects.filter(user=self.request.user)


# Claim an achievement manually (optional)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def claim_achievement(request):
    achievement_id = request.data.get("achievement_id")
    achievement = Achievement.objects.filter(id=achievement_id).first()

    if not achievement:
        return Response({"detail": "Achievement not found."}, status=status.HTTP_404_NOT_FOUND)

    # Prevent duplicate claims
    if UserAchievement.objects.filter(user=request.user, achievement=achievement).exists():
        return Response({"detail": "Achievement already claimed."}, status=status.HTTP_400_BAD_REQUEST)

    # Add to user achievements
    UserAchievement.objects.create(user=request.user, achievement=achievement)

    # Add XP reward
    request.user.xp += achievement.xp_reward
    request.user.save()

    return Response({
        "detail": f"Achievement '{achievement.title}' claimed!",
        "xp_reward": achievement.xp_reward
    }, status=status.HTTP_201_CREATED)
