from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView
)
from .views import UserUpdateView
from .views import RegisterView, UserDetailView, MyTokenObtainPairView, AdminUserListView, AdminUserDetailView, AdminUserUpdateView, AdminUserDeleteView
from .views import TermsView, AcceptTermsView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('me/update/', UserUpdateView.as_view(), name='user_update'),

    path('admin/users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('admin/users/<int:pk>/update_role/', AdminUserUpdateView.as_view(), name='admin_user_update'),
    path('admin/users/<int:pk>/delete/', AdminUserDeleteView.as_view(), name='admin_user_delete'),

    path('terms/', TermsView.as_view(), name='terms'),
    path('accept-terms/', AcceptTermsView.as_view(), name='accept_terms'),
]