from django.urls import path
from .views import QuizListCreateView, QuizDetailView, QuizSubmitView, LeaderboardView, UserResultsView, QuizStatsView, CategoryListView, CreateQuizView, QuizUpdateView, QuizDeleteView
from .views import PendingQuizzesView, ApproveQuizView, RejectQuizView, ReportQuizView, ReportedQuizzesView, QuizReportCreateView, ApprovedQuizListView, ApprovedQuizDetailView

urlpatterns = [

    #user quiz endpoints
    path("", QuizListCreateView.as_view(), name="quiz_list_create"),
    path("<int:pk>/", QuizDetailView.as_view(), name="quiz_detail"),
    path('create/', CreateQuizView.as_view(), name='quiz_create'),
    path('<int:pk>/update/', QuizUpdateView.as_view(), name='quiz_update'),
    path('<int:pk>/delete/', QuizDeleteView.as_view(), name='quiz_delete'),
    path("<int:pk>/submit/", QuizSubmitView.as_view(), name="quiz_submit"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("results/", UserResultsView.as_view(), name="user_results"),
    path("<int:pk>/stats/", QuizStatsView.as_view(), name="quiz_stats"), 
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("approved/", ApprovedQuizListView.as_view(), name="approved_quizzes"),
    path("approved/<int:pk>/", ApprovedQuizDetailView.as_view(), name="approved_quiz_detail"),
    path("<int:pk>/report/", QuizReportCreateView.as_view(), name="report_quiz"),

    #Admin
    path('pending/', PendingQuizzesView.as_view(), name='pending_quizzes'),
    path('<int:pk>/approve/', ApproveQuizView.as_view(), name='approve_quiz'),
    path('<int:pk>/reject/', RejectQuizView.as_view(), name='reject_quiz'),

    #reporting
    path('<int:pk>/report/', ReportQuizView.as_view(), name='report_quiz'),
    path('reports/', ReportedQuizzesView.as_view(), name='reported_quizzes'),
]
