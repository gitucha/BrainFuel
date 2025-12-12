# achievements/utils.py
from django.contrib.auth import get_user_model
from .models import Achievement, UserAchievement

User = get_user_model()


def unlock(user, achievement_code):
    """
    Very simple unlock helper:
    - user = user instance
    - achievement_code = string code from Achievement model
    - unlock only if not already unlocked
    - apply XP reward
    """

    if not user:
        return None

    # find achievement
    achievement = Achievement.objects.filter(code=achievement_code).first()
    if not achievement:
        return None

    # already earned?
    existing = UserAchievement.objects.filter(
        user=user, achievement=achievement
    ).first()
    if existing:
        return existing

    # create unlock
    ua = UserAchievement.objects.create(user=user, achievement=achievement)

    # apply XP reward
    reward = achievement.xp_reward or 0
    user.xp = (user.xp or 0) + reward

    # optional simple level logic
    while user.xp >= user.level * 100:
        user.level += 1

    user.save()

    return ua
