# premium/views.py
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Payment, DiscountCode, CreatorEarning
from .serializers import PaymentSerializer, CreatorEarningSerializer
import uuid
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction
from django.conf import settings

# Create a payment record (mock or pre-init before calling Paystack)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment(request):
    amount = request.data.get("amount")
    if amount is None:
        return Response({"detail": "amount is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return Response({"detail": "amount must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    reference = str(uuid.uuid4())
    payment = Payment.objects.create(user=request.user, amount=amount, reference=reference, status="created")
    serializer = PaymentSerializer(payment)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """
    Verify a payment that was previously created (mock flow).
    Expects: { "reference": "<reference>" }
    This endpoint is intentionally simple for demo/testing. For production use the Paystack verify view.
    """
    reference = request.data.get("reference")
    if not reference:
        return Response({"detail": "reference required"}, status=status.HTTP_400_BAD_REQUEST)

    payment = Payment.objects.filter(reference=reference, user=request.user).first()
    if not payment:
        return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

    # simple mock verification:
    with transaction.atomic():
        payment.status = "success"
        payment.save(update_fields=["status"])
        request.user.is_premium = True
        # Example: award thalers based on amount; adjust formula as needed
        try:
            thalers_awarded = int(payment.amount) // 10
        except Exception:
            thalers_awarded = 0
        request.user.thalers = getattr(request.user, "thalers", 0) + thalers_awarded
        request.user.save()

    return Response({"detail": "Payment verified. User upgraded to premium.", "thalers_awarded": thalers_awarded})


class PaymentHistoryView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).order_by("-created_at")


@api_view(["POST"])
@permission_classes([IsAdminUser])
def upgrade_user(request):
    """
    Admin endpoint to upgrade a specific user to premium.
    Expects: {"user_id": <id>} or if omitted, upgrades the current admin user (useful for testing).
    """
    user_id = request.data.get("user_id")
    if user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    else:
        user = request.user

    if getattr(user, "is_premium", False):
        return Response({"detail": "User is already premium."}, status=status.HTTP_400_BAD_REQUEST)

    user.is_premium = True
    user.save(update_fields=["is_premium"])
    return Response({
        "message": "Account successfully upgraded to premium.",
        "user": {"id": user.id, "email": user.email, "is_premium": user.is_premium}
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_thalers(request):
    """
    Add thalers to the logged-in user (trusted internal endpoint used after payments).
    Expects {"amount": <int>}
    """
    amount = request.data.get("amount", 0)
    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return Response({"detail": "amount must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.thalers = getattr(user, "thalers", 0) + amount
    user.save(update_fields=["thalers"])
    return Response({"detail": f"Added {amount} thalers.", "thalers": user.thalers}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_discount(request):
    code = request.data.get("code")
    if not code:
        return Response({"detail": "code required"}, status=status.HTTP_400_BAD_REQUEST)

    discount = DiscountCode.objects.filter(code=code, active=True).first()
    if not discount:
        return Response({"detail": "Invalid or expired discount code."}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"discount_percent": discount.percentage}, status=status.HTTP_200_OK)


from rest_framework.generics import RetrieveAPIView

class CreatorEarningsView(RetrieveAPIView):
    serializer_class = CreatorEarningSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, _ = CreatorEarning.objects.get_or_create(user=self.request.user)
        return obj


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_thalers(request):
    """
    For demo: frontend calls create_paystack_session, user completes payment on paystack,
    then frontend calls verify_paystack_transaction that credits thalers. This buy_thalers is kept as a fallback
    to credit thalers when you have an internal reference.
    """
    reference = request.data.get("reference")
    thalers = int(request.data.get("thalers", 0))

    if not reference or thalers <= 0:
        return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.thalers = getattr(user, "thalers", 0) + thalers
    user.save(update_fields=["thalers"])

    # Optionally create a Payment record for bookkeeping
    Payment.objects.create(user=user, amount=thalers, reference=reference, status="success", purpose="buy_thalers")
    return Response({"message": "Thalers added successfully", "thalers": user.thalers}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def switch_plan(request):
    plan = request.data.get("plan")
    reference = request.data.get("reference", None)
    plans = ["free", "pro", "elite"]

    if plan not in plans:
        return Response({"error": "Invalid plan"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.subscription = plan
    user.save(update_fields=["subscription"])
    # Optionally persist a Payment or Subscription model entry here
    return Response({"message": "Subscription updated", "subscription": plan}, status=status.HTTP_200_OK)
