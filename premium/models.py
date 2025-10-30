from django.db import models
from django.conf import settings

class Payment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, default="mock")

class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    percentage = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

class CreatorEarning(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)
