from rest_framework import serializers
from .models import Payment, DiscountCode, CreatorEarning

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["user", "status", "created_at"]

class DiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = "__all__"

class CreatorEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreatorEarning
        fields = ["user", "total_earnings", "updated_at"]
