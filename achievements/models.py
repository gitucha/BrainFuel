from django.db import models
from django.conf import settings

class Achievement(models.Model):
    title = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.URLField(blank=True, null=True)
    xp_reward = models.PositiveIntegerField(default=0)
    requirement = models.CharField(max_length=255, help_text="Describe how to unlock this achievement.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class UserAchievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="earned_achievements")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.title}"