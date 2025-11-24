# premium/views_paystack.py
import os
import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Payment  # ensure Payment model exists in premium.models
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

PAYSTACK_SECRET = getattr(settings, "PAYSTACK_SECRET_KEY", None)
PAYSTACK_PUBLIC = getattr(settings, "PAYSTACK_PUBLIC_KEY", None)
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{}"
PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"
REQUEST_TIMEOUT = 10  # seconds

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_paystack_session(request):
    """
    Initialize a Paystack transaction and return authorization_url and reference.
    Expects JSON: { "amount": <number in major units>, "currency": "NGN" (optional), "purpose": "buy_thalers" }
    The code converts major units to kobo (amount * 100).
    """
    if not PAYSTACK_SECRET:
        logger.error("PAYSTACK_SECRET_KEY not configured")
        return Response({"detail": "Payment gateway not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    body = request.data or {}
    # Accept either amount (major units) or amount_kobo
    amount_major = body.get("amount")
    amount_kobo = body.get("amount_kobo")

    try:
        if amount_kobo:
            amount = int(amount_kobo)
        elif amount_major is not None:
            # convert to minor units (kobo) expected by Paystack
            amount = int(float(amount_major) * 100)
        else:
            return Response({"detail": "amount or amount_kobo required"}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({"detail": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

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
        # callback_url optional: Paystack will redirect to this after payment flow
        "callback_url": settings.FRONTEND_URL.rstrip("/") + "/payments/success" if getattr(settings, "FRONTEND_URL", None) else None,
    }

    try:
        resp = requests.post(PAYSTACK_INIT_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        logger.exception("Paystack init request failed")
        return Response({"detail": "Payment provider unreachable", "error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    if not resp.ok:
        logger.error("Paystack init returned non-ok: %s", resp.text)
        try:
            body = resp.json()
        except Exception:
            body = {"detail": "unknown error"}
        return Response({"detail": "Paystack init failed", "raw": body}, status=status.HTTP_400_BAD_REQUEST)

    data = resp.json().get("data", {})
    authorization_url = data.get("authorization_url")
    reference = data.get("reference")

    # persist a Payment record for tracking
    try:
        Payment.objects.create(
            user=request.user,
            amount=amount,  # stored in kobo (minor units)
            reference=reference,
            status="initialized",
            purpose=metadata.get("purpose", "")
        )
    except Exception:
        logger.exception("Failed to create Payment record")

    return Response({"authorization_url": authorization_url, "reference": reference}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_paystack_transaction(request):
    """
    Verify transaction by reference (frontend will POST { "reference": "<ref>" }).
    This is idempotent and safe to call multiple times.
    """
    reference = request.data.get("reference")
    if not reference:
        return Response({"detail": "reference required"}, status=status.HTTP_400_BAD_REQUEST)

    if not PAYSTACK_SECRET:
        return Response({"detail": "Payment gateway not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    url = PAYSTACK_VERIFY_URL.format(reference)
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        logger.exception("Paystack verify request failed")
        return Response({"detail": "Payment provider unreachable", "error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    if not resp.ok:
        logger.error("Paystack verify returned non-ok: %s", resp.text)
        try:
            raw = resp.json()
        except Exception:
            raw = {"detail": resp.text}
        return Response({"detail": "verify failed", "raw": raw}, status=status.HTTP_400_BAD_REQUEST)

    payload = resp.json().get("data", {})
    status_str = payload.get("status")
    metadata = payload.get("metadata", {}) or {}

    uid = metadata.get("user_id")
    user = None
    if uid:
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            user = None

    # Find local Payment record if exists
    payment = Payment.objects.filter(reference=reference).first()

    if status_str == "success":
        # Awarding thalers rule: 1 thaler per 10 major currency units (adjust to suit)
        amount_kobo = int(payload.get("amount", 0))
        major_amount = amount_kobo // 100
        thalers_awarded = major_amount // 10

        with transaction.atomic():
            if payment:
                payment.status = "success"
                try:
                    payment.user = user or payment.user
                    payment.save(update_fields=["status", "user"])
                except Exception:
                    payment.save(update_fields=["status"])

            if user:
                user.thalers = getattr(user, "thalers", 0) + thalers_awarded
                # Optionally upgrade subscription if metadata indicates a subscription purchase
                purpose = metadata.get("purpose", "") or payment.purpose if payment else ""
                if purpose and "subscription" in purpose.lower():
                    user.is_premium = True
                user.save(update_fields=["thalers", "is_premium"])

        return Response({"status": "success", "thalers_awarded": thalers_awarded}, status=status.HTTP_200_OK)

    # For non-success statuses, record and return status
    if payment:
        payment.status = status_str or "failed"
        payment.save(update_fields=["status"])

    return Response({"status": status_str, "raw": payload}, status=status.HTTP_200_OK)
