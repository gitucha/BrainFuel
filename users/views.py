from rest_framework import generics, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
from django.conf import settings

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    MyTokenObtainPairSerializer,
    AdminUserSerializer,
    TermsSerializer,
)

from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()
token_generator = PasswordResetTokenGenerator()


# ======================================================
# AUTH TOKEN
# ======================================================

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


# ======================================================
# PASSWORD RESET
# ======================================================

class RequestPasswordResetView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Always return same response for security
            return Response({"message": "If this email exists, a reset link has been sent."})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)

        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{uid}/{token}"

        send_mail(
            subject="BrainFuel Password Reset",
            message=f"Click to reset your password: {reset_url}",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@brainfuel.local"),
            recipient_list=[email],
        )

        return Response({"message": "If this email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = []

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            return Response({"error": "Invalid link"}, status=400)

        if not token_generator.check_token(user, token):
            return Response({"error": "Reset link invalid or expired"}, status=400)

        password = request.data.get("password")
        if not password:
            return Response({"error": "Password required"}, status=400)

        user.set_password(password)
        user.save()
        return Response({"message": "Password reset successful"})


# ======================================================
# REGISTER
# ======================================================

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


# ======================================================
# USER PROFILE (SELF)
# ======================================================

class UserDetailView(generics.RetrieveAPIView):
    """
    GET /api/users/me/
    Returns full user profile including:
      - xp
      - level
      - thalers
      - subscription_plan
      - is_premium
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/users/me/
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ======================================================
# ADMIN USER MANAGEMENT
# ======================================================

class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email"]


class AdminUserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminUserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = "pk"


class AdminUserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = "pk"


# ======================================================
# TERMS & CONDITIONS
# ======================================================

class TermsView(generics.ListAPIView):
    from .models import TermsAndConditions
    queryset = TermsAndConditions.objects.all().order_by("-created_at")
    serializer_class = TermsSerializer
    permission_classes = [permissions.AllowAny]


class AcceptTermsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .models import TermsAndConditions, UserTermsAcceptance
        latest_terms = TermsAndConditions.objects.latest("created_at")
        UserTermsAcceptance.objects.update_or_create(
            user=request.user,
            defaults={"terms": latest_terms},
        )
        return Response({"message": "Terms accepted successfully"})


# ======================================================
# MANUAL PREMIUM UPGRADE
# ======================================================

class UpgradeToPremiumView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        user.is_premium = True
        user.save()
        return Response({"message": "Upgraded to Premium successfully!"})
