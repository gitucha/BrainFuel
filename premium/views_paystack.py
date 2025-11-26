# premium/views_paystack.py
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
    Initialize a Paystack transaction.

    - Uses a numeric amount from the frontend (major units, e.g. 500 KES).
    - Stores plan_key + purpose + shop_thalers in metadata so verify() can update the user.
    - Plan tracking in Paystack is currently disabled to avoid 'Plan not found' issues.
    """
    body = request.data or {}

    # 1) Amount in *major* units from frontend (e.g. 500 for 500 KES)
    amount_major = body.get("amount")
    if amount_major is None:
        return Response({"detail": "amount required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount_major = float(amount_major)
        amount_minor = int(amount_major * 100)  # convert to minor units, integer
        if amount_minor <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return Response({"detail": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

    # 2) Currency
    currency = getattr(settings, "PAYSTACK_CURRENCY", "NGN")

    if not PAYSTACK_SECRET:
        return Response(
            {"detail": "Payment gateway not configured"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    email = request.user.email

    # Plan key passed from frontend (e.g. "basic", "scholar", "warrior", "elite") – for subscriptions
    plan_key = body.get("plan_key")

    # Optional: explicit thaler amount for shop purchases
    shop_thalers = body.get("shop_thalers")  # e.g. 100, 300, 700

    # Carry metadata so verify() can upgrade the user correctly
    metadata = {
        "user_id": request.user.id,
        "plan_key": plan_key,
        "shop_thalers": shop_thalers,
        "purpose": body.get("purpose") or f"subscription_{plan_key or ''}",
    }

    payload = {
        "email": email,
        "amount": amount_minor,  # integer, no decimals
        "currency": currency,
        "metadata": metadata,
        "callback_url": settings.FRONTEND_URL.rstrip("/") + "/payments/success"
        if getattr(settings, "FRONTEND_URL", None)
        else None,
    }

    if plan_key:
        plan_codes = getattr(settings, "PAYSTACK_PLAN_CODES", {})
        plan_code = plan_codes.get(plan_key)
        if plan_code:
            payload["plan"] = plan_code

    try:
        resp = requests.post(
            PAYSTACK_INIT_URL,
            json=payload,
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.exception("Paystack init error")
        return Response(
            {"detail": "Payment provider unreachable", "error": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if not resp.ok:
        try:
            raw = resp.json()
        except Exception:
            raw = resp.text
        logger.error("Paystack init failed: %s", raw)
        return Response(
            {"detail": "Paystack init failed", "raw": raw},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_data = resp.json()
    data = raw_data.get("data", {}) if isinstance(raw_data, dict) else {}

    authorization_url = data.get("authorization_url")
    reference = data.get("reference")

    try:
        Payment.objects.create(
            user=request.user,
            amount=amount_minor,
            reference=reference,
            status="initialized",
            purpose=metadata.get("purpose", ""),
        )
    except Exception:
        logger.exception("Failed to create Payment record")

    return Response(
        {"authorization_url": authorization_url, "reference": reference},
        status=status.HTTP_201_CREATED,
    )



@api_view(["POST"])
@permission_classes([AllowAny])
def verify_paystack_transaction(request):
    """
    Verify transaction by reference (frontend will POST { "reference": "<ref>" }).

    - Reads metadata.user_id, metadata.plan_key, metadata.shop_thalers, metadata.purpose.
    - Marks Payment as success/failed.
    - Updates user.thalers, user.is_premium, user.subscription_plan.
    """
    reference = request.data.get("reference")
    if not reference:
        return Response(
            {"detail": "reference required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PAYSTACK_SECRET:
        return Response(
            {"detail": "Payment gateway not configured"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    url = PAYSTACK_VERIFY_URL.format(reference)
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        logger.exception("Paystack verify request failed")
        return Response(
            {"detail": "Payment provider unreachable", "error": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if not resp.ok:
        logger.error("Paystack verify returned non-ok: %s", resp.text)
        try:
            raw = resp.json()
        except Exception:
            raw = {"detail": resp.text}
        return Response(
            {"detail": "verify failed", "raw": raw},
            status=status.HTTP_400_BAD_REQUEST,
        )

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

    # If transaction is not successful, record status and return (no coins, no premium)
    if status_str != "success":
        if payment:
            payment.status = status_str or "failed"
            payment.save(update_fields=["status"])
        return Response(
            {"status": status_str, "raw": payload},
            status=status.HTTP_200_OK,
        )

    # ---- SUCCESS PATH ----
    amount_kobo = int(payload.get("amount", 0))
    major_amount = amount_kobo // 100

    # Base rule: 1 thaler per 10 currency units
    thalers_awarded = major_amount // 10

    purpose = metadata.get("purpose", "") or (payment.purpose if payment else "")

    # Try to get plan_key from metadata first (for subscriptions)
    plan_key = metadata.get("plan_key")

    # If not present, try to parse from purpose like "subscription_warrior"
    if not plan_key and purpose:
        lower = purpose.lower()
        if "subscription_" in lower:
            plan_key = lower.split("subscription_", 1)[1] or None

    # Shop-specific override: if this is a shop purchase and shop_thalers is provided,
    # use that exact number of thalers instead of the generic rule.
    shop_thalers = metadata.get("shop_thalers")
    if shop_thalers is not None and purpose and "shop" in purpose.lower():
        try:
            thalers_awarded = int(shop_thalers)
        except (ValueError, TypeError):
            # if parsing fails, fall back to generic rule
            pass

    with transaction.atomic():
        # Update local Payment record
        if payment:
            payment.status = "success"
            try:
                payment.user = user or payment.user
                payment.save(update_fields=["status", "user"])
            except Exception:
                payment.save(update_fields=["status"])

        # Update user account (thalers, premium flag, subscription_plan)
        if user:
            # Add thalers (from subscription rule or shop override)
            user.thalers = getattr(user, "thalers", 0) + thalers_awarded

            # Subscriptions upgrade premium
            if purpose and "subscription" in purpose.lower():
                user.is_premium = True
                if plan_key:
                    # e.g. "basic", "scholar", "warrior", "elite"
                    user.subscription_plan = plan_key

            user.save(update_fields=["thalers", "is_premium", "subscription_plan"])

    return Response(
        {
            "status": "success",
            "thalers_awarded": thalers_awarded,
            "new_balance": getattr(user, "thalers", 0) if user else None,
            "purpose": purpose,
        },
        status=status.HTTP_200_OK,
    )
