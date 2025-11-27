from django.db import models
from django.conf import settings

class Achievement(models.Model):
    code = models.CharField(
        max_length=100,
        unique=True,
        null=True,      # <-- allow null for now
        blank=True      # <-- allow blank in forms
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirement = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    xp_reward = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="earned_achievements",
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "achievement")

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.title}"


def seed_default_achievements():
    # since we're in the same file, no need to re-import Achievement
    defaults = [
        ("first_quiz", "First Quiz Completed", "Complete 1 quiz", 200),
        ("quiz_5", "Quiz Novice", "Complete 5 quizzes", 300),
        ("quiz_10", "Quiz Master", "Complete 10 quizzes", 500),
        ("xp_1000", "Rising Star", "Earn 1000 XP", 200),
        ("xp_5000", "Knowledge Seeker", "Earn 5000 XP", 1000),
    ]

    for code, title, req, xp in defaults:
        Achievement.objects.get_or_create(
            code=code,
            defaults={
                "title": title,
                "description": req,
                "requirement": req,
                "xp_reward": xp,
            },
        )
