from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Payment, DiscountCode, CreatorEarning
from .serializers import PaymentSerializer, CreatorEarningSerializer
import uuid

# Mock payment creation
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_payment(request):
    amount = request.data.get("amount")
    reference = str(uuid.uuid4())
    payment = Payment.objects.create(user=request.user, amount=amount, reference=reference)
    return Response({"payment_reference": reference, "detail": "Payment created."}, status=status.HTTP_201_CREATED)


# Verify payment (mock)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def verify_payment(request):
    reference = request.data.get("reference")
    payment = Payment.objects.filter(reference=reference, user=request.user).first()
    if not payment:
        return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

    payment.status = "success"
    payment.save()
    request.user.is_premium = True
    request.user.save()
    return Response({"detail": "Payment verified. User upgraded to premium."})


# Payment history
class PaymentHistoryView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


# Upgrade manually
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def upgrade_user(request):
    user_id = request.data.get("user_id")
    from users.models import User
    user = User.objects.filter(id=user_id).first()
    if not user:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
    user.is_premium = True
    user.save()
    return Response({"detail": f"{user.email} upgraded to premium."})


# Add thalers (virtual currency)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def add_thalers(request):
    amount = request.data.get("amount", 0)
    request.user.xp += int(amount)
    request.user.save()
    return Response({"detail": f"Added {amount} thalers."})


# Apply discount code
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def apply_discount(request):
    code = request.data.get("code")
    discount = DiscountCode.objects.filter(code=code, active=True).first()
    if not discount:
        return Response({"detail": "Invalid or expired discount code."}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"discount_percent": discount.percentage})


# Creator earnings
class CreatorEarningsView(generics.RetrieveAPIView):
    serializer_class = CreatorEarningSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return CreatorEarning.objects.get_or_create(user=self.request.user)[0]
