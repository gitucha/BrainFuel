# users/views_thalers.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ThalerTransaction
from django.contrib.auth import get_user_model

User = get_user_model()

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_thalers(request):
    # Admin or internal endpoint to credit thalers (or purchases)
    amount = int(request.data.get("amount", 0))
    reason = request.data.get("reason", "credit")
    if amount <= 0:
        return Response({"detail": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.thalers = (user.thalers or 0) + amount
    user.save()
    tx = ThalerTransaction.objects.create(user=user, amount=amount, reason=reason)
    return Response({"thalers": user.thalers, "transaction_id": tx.id}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet(request):
    user = request.user
    transactions = [
        {"id": t.id, "amount": t.amount, "reason": t.reason, "created_at": t.created_at}
        for t in ThalerTransaction.objects.filter(user=user).order_by("-created_at")[:50]
    ]
    return Response({"thalers": user.thalers or 0, "transactions": transactions})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def spend_thalers(request):
    user = request.user
    amount = int(request.data.get("amount", 0))
    reason = request.data.get("reason", "spend")
    if amount <= 0:
        return Response({"detail": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
    if (user.thalers or 0) < amount:
        return Response({"detail": "Insufficient thalers"}, status=status.HTTP_400_BAD_REQUEST)

    user.thalers = user.thalers - amount
    user.save()
    tx = ThalerTransaction.objects.create(user=user, amount=-amount, reason=reason)
    return Response({"thalers": user.thalers, "transaction_id": tx.id})
