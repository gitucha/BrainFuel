from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
from django.contrib.auth import get_user_model
from quizzes.models import QuizAttempt  # adjust if your app name differs
from .models import Achievement

User = get_user_model()

def unlock_achievement(user, achievement_title):
    """Utility to attach an achievement if not already owned."""
    achievement = Achievement.objects.filter(title=achievement_title).first()
    if achievement and not user.achievements.filter(id=achievement.id).exists():
        user.achievements.add(achievement)
        user.xp += achievement.xp_reward
        user.save()
        print(f"{user.email} unlocked: {achievement_title}")

@receiver(post_save, sender=QuizAttempt)
def handle_quiz_completion(sender, instance, created, **kwargs):
    """Fired whenever a quiz attempt is saved (completed)."""
    if not created:
        return
    user = instance.user

    # 1️ Achievement: First quiz
    total_attempts = QuizAttempt.objects.filter(user=user).count()
    if total_attempts == 1:
        unlock_achievement(user, "First Quiz!")

    # 2️ Achievement: 10 quizzes
    if total_attempts >= 10:
        unlock_achievement(user, "Quiz Explorer")

    # 3️ Achievement: Perfect Score
    if instance.score == 100:
        unlock_achievement(user, "Perfect Score")

    # 4️ Achievement: XP milestones
    total_xp = user.xp
    if total_xp >= 1000:
        unlock_achievement(user, "Knowledge Seeker")
