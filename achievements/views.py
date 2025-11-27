# achievements/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import UserAchievement
from rest_framework import status
from .models import Achievement
from .serializers import AchievementSerializer
from rest_framework.permissions import AllowAny
from quizzes.models import QuizAttempt

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_achievements(request):
  uas = (
      UserAchievement.objects
      .filter(user=request.user)
      .select_related("achievement")
      .order_by("-created_at")  # or unlocked_at if you have it
  )

  data = [
      {
          "id": ua.id,
          "title": ua.achievement.title,
          "description": ua.achievement.description,
          "icon": ua.achievement.icon,  # if it's a URL/path
          "xp_reward": ua.achievement.xp_reward,
          "unlocked_at": getattr(ua, "created_at", None),
      }
      for ua in uas
  ]

  return Response(data, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([AllowAny])
def all_achievements(request):
    qs = Achievement.objects.all().order_by("id")
    return Response(AchievementSerializer(qs, many=True).data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def achievement_overview(request):
    user = request.user

    # Stats to drive progress
    quizzes_completed = QuizAttempt.objects.filter(user=user).count()
    xp_total = getattr(user, "xp", 0)
    level = getattr(user, "level", 1)

    achievements = Achievement.objects.all().order_by("id")
    earned_map = {
        ua.achievement_id: ua.earned_at
        for ua in UserAchievement.objects.filter(user=user)
    }

    def progress_for(ach: Achievement):
        code = ach.code or ""
        # Map codes to numeric goals
        if code == "first_quiz":
            return min(quizzes_completed, 1), 1
        if code == "quiz_5":
            return min(quizzes_completed, 5), 5
        if code == "quiz_10":
            return min(quizzes_completed, 10), 10
        if code == "xp_1000":
            return min(xp_total, 1000), 1000
        if code == "xp_5000":
            return min(xp_total, 5000), 5000
        # default: no specific goal
        return 0, 1

    items = []
    for a in achievements:
        current, target = progress_for(a)
        is_unlocked = a.id in earned_map

        items.append({
            "id": a.id,
            "code": a.code,
            "title": a.title,
            "description": a.description,
            "requirement": a.requirement,
            "icon": a.icon or "🏆",
            "xp_reward": a.xp_reward,
            "is_unlocked": is_unlocked,
            "earned_at": earned_map.get(a.id),
            "progress": current,
            "target": target,
        })

    return Response(
        {
            "user": {
                "xp": xp_total,
                "level": level,
            },
            "achievements": items,
        }
    )