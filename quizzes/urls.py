from django.urls import path
from .views import QuizListCreateView, QuizDetailView, QuizSubmitView, LeaderboardView, UserResultsView, QuizStatsView, CategoryListView
from .views import PendingQuizzesView, ApproveQuizView, RejectQuizView, ReportQuizView, ReportedQuizzesView

urlpatterns = [
    path("", QuizListCreateView.as_view(), name="quiz_list_create"),
    path("<int:pk>/", QuizDetailView.as_view(), name="quiz_detail"),
    path("<int:pk>/submit/", QuizSubmitView.as_view(), name="quiz_submit"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("results/", UserResultsView.as_view(), name="user_results"),
    path("<int:pk>/stats/", QuizStatsView.as_view(), name="quiz_stats"), 
    path("categories/", CategoryListView.as_view(), name="categories"),

    path('pending/', PendingQuizzesView.as_view(), name='pending_quizzes'),
    path('<int:pk>/approve/', ApproveQuizView.as_view(), name='approve_quiz'),
    path('<int:pk>/reject/', RejectQuizView.as_view(), name='reject_quiz'),
    path('<int:pk>/report/', ReportQuizView.as_view(), name='report_quiz'),
    path('reports/', ReportedQuizzesView.as_view(), name='reported_quizzes'),
]
