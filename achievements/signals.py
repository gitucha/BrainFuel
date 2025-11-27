# achievements/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from quizzes.models import QuizAttempt
from .models import Achievement, UserAchievement  # adjust names if different
from notifications.utils import create_notification


def unlock_achievement(user, title: str):
    """
    Unlock an achievement by its title, if the user doesn't have it yet.
    Also gives optional XP reward and creates a notification.
    """
    try:
        achievement = Achievement.objects.get(title=title)
    except Achievement.DoesNotExist:
        return

    ua, created = UserAchievement.objects.get_or_create(
        user=user,
        achievement=achievement,
    )

    if not created:
        # Already had this achievement
        return

    # Optional: reward extra XP from achievement.xp_reward
    reward = getattr(achievement, "xp_reward", 0) or 0
    if reward > 0:
        current_xp = getattr(user, "xp", 0) or 0
        user.xp = current_xp + reward
        user.save(update_fields=["xp"])

    # Notify the user
    create_notification(
        user,
        "Achievement unlocked",
        f"You unlocked '{achievement.title}'!",
    )


@receiver(post_save, sender=QuizAttempt)
def handle_quiz_completion(sender, instance: QuizAttempt, created, **kwargs):
    """
    Runs every time a QuizAttempt is created.
    Add whatever achievement logic you want here.
    """
    if not created:
        return

    user = instance.user

    # Example 1: First quiz ever
    total_attempts = QuizAttempt.objects.filter(user=user).count()
    if total_attempts == 1:
        unlock_achievement(user, "First Quiz")

    # Example 2: Generic explorer achievement (any completed quiz)
    unlock_achievement(user, "Quiz Explorer")

    # Add more rules here (scores, streaks, categories, etc.)
