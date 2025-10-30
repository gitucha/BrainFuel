from rest_framework import generics, permissions, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserSerializer, MyTokenObtainPairSerializer, AdminUserSerializer, TermsSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
User = get_user_model()

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class UserUpdateView(generics.UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email']

class AdminUserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

class AdminUserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'pk'

class AdminUserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'pk'

class TermsView(generics.ListAPIView):
    from .models import TermsAndConditions
    queryset = TermsAndConditions.objects.all().order_by('-created_at')
    serializer_class = TermsSerializer
    permission_classes = [permissions.AllowAny]

class AcceptTermsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, format=None):
        from .models import TermsAndConditions, UserTermsAcceptance
        latest_terms = TermsAndConditions.objects.latest('created_at')
        UserTermsAcceptance.objects.update_or_create(
            user=request.user,
            defaults={'terms': latest_terms}
        )
        return Response({'status': 'terms accepted'})