from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from users.models import User
from quizzes.models import QuizAttempt
from premium.models import Payment
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Sum

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_insights(request):
    today = now().date()
    week_ago = today - timedelta(days=7)

    new_users = User.objects.filter(date_joined__gte=week_ago).count()
    quiz_activity = QuizAttempt.objects.filter(created_at__gte=week_ago).count()
    revenue_last_7d = (
        Payment.objects
        .filter(created_at__gte=week_ago, status="SUCCESS")
        .aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    data = {
        "new_users_last_7_days": new_users,
        "quiz_attempts_last_7_days": quiz_activity,
        "revenue_last_7_days": revenue_last_7d,
        "total_users": User.objects.count(),
        "total_premium_users": User.objects.filter(is_premium=True).count(),
    }
    return Response(data)
