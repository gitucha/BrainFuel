from django.urls import path
from .views import QuizListCreateView, QuizDetailView, QuizSubmitView, LeaderboardView, UserResultsView, QuizStatsView, CategoryListView

urlpatterns = [
    path("", QuizListCreateView.as_view(), name="quiz_list_create"),
    path("<int:pk>/", QuizDetailView.as_view(), name="quiz_detail"),
    path("<int:pk>/submit/", QuizSubmitView.as_view(), name="quiz_submit"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("results/", UserResultsView.as_view(), name="user_results"),
    path("<int:pk>/stats/", QuizStatsView.as_view(), name="quiz_stats"), 
   path("categories/", CategoryListView.as_view(), name="categories"),
]
