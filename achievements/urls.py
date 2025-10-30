from django.urls import path
from . import views

urlpatterns = [
    path('', views.AchievementListView.as_view(), name='achievements_list'),
    path('me/', views.UserAchievementsView.as_view(), name='user_achievements'),
    path('claim/', views.claim_achievement, name='claim_achievement'),
]