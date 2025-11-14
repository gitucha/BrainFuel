import os
import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

PAYSTACK_SECRET = settings.PAYSTACK_SECRET_KEY
PAYSTACK_PUBLIC = settings.PAYSTACK_PUBLIC_KEY
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{}"
PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_paystack_session(request):
    """
    Create a Paystack transaction initialization and return the authorization_url to the frontend.
    Payload: { "amount_ksh": 1000, "currency": "NGN" or "KES", "purpose": "buy_thalers" }
    Note: paystack expects amount in kobo/ngn minor units; for KES Paystack may not support KES — for demo use NGN or treat as a generic currency.
    """
    body = request.data
    amount = int(body.get("amount_kobo") or (int(body.get("amount") or 0) * 100))
    email = request.user.email
    metadata = {
        "user_id": request.user.id,
        "purpose": body.get("purpose", "purchase"),
    }
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "amount": amount,
        "metadata": metadata,
        "callback_url": settings.FRONTEND_URL + "/payments/success",  # optional
    }
    resp = requests.post(PAYSTACK_INIT_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        return Response({"detail": "Paystack init failed", "raw": resp.json()}, status=status.HTTP_400_BAD_REQUEST)
    data = resp.json()["data"]
    return Response({"authorization_url": data["authorization_url"], "reference": data["reference"]})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_paystack_transaction(request):
    """
    Called from frontend after payment or by webhook. For demo, frontend hits this after redirect.
    Payload: { "reference": "<paystack_reference>" }
    """
    reference = request.data.get("reference")
    if not reference:
        return Response({"detail": "reference required"}, status=status.HTTP_400_BAD_REQUEST)

    url = PAYSTACK_VERIFY_URL.format(reference)
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return Response({"detail": "verify failed", "raw": resp.json()}, status=status.HTTP_400_BAD_REQUEST)

    data = resp.json()["data"]
    status_str = data.get("status")
    # locate user from metadata if present
    metadata = data.get("metadata", {})
    uid = metadata.get("user_id")
    try:
        user = User.objects.get(pk=uid) if uid else None
    except User.DoesNotExist:
        user = None

    if status_str == "success":
        # For demo: credit thalers proportional to amount (e.g., 1 Kobo => 0.01 thaler); decide your rule
        amount = int(data.get("amount", 0))  # in kobo
        thalers_awarded = (amount // 100) // 10  # e.g., 1 thaler per 10 currency units (adjust)
        if user:
            user.thalers += thalers_awarded
            user.save()
        return Response({"status": "success", "thalers_awarded": thalers_awarded})
    return Response({"status": status_str, "raw": data})
