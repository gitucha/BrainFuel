from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import Achievement, UserAchievement
from .serializers import AchievementSerializer, UserAchievementSerializer

@api_view(["GET"])
@permission_classes([AllowAny])
def all_achievements(request):
    qs = Achievement.objects.all().order_by("xp_reward", "id")
    ser = AchievementSerializer(qs, many=True)
    return Response(ser.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_achievements(request):
    """
    Returns JSON:
    {
      "earned": [ { id, achievement: {...}, earned_at }, ... ],
      "locked": [ { id, code, title, description, requirement, icon, xp_reward, created_at }, ... ]
    }
    """
    user = request.user

    # earned user achievements (ordered newest first)
    earned_qs = (
        UserAchievement.objects.filter(user=user)
        .select_related("achievement")
        .order_by("-earned_at")
    )
    earned_ser = UserAchievementSerializer(earned_qs, many=True)

    # locked achievements = all achievements not in earned list
    earned_ids = earned_qs.values_list("achievement_id", flat=True)
    locked_qs = Achievement.objects.exclude(id__in=earned_ids).order_by("xp_reward", "id")
    locked_ser = AchievementSerializer(locked_qs, many=True)

    return Response({"earned": earned_ser.data, "locked": locked_ser.data}, status=status.HTTP_200_OK)

