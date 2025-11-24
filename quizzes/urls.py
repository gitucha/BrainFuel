from django.urls import path
from .views import (
    QuizListCreateView,
    QuizDetailView,
    QuizSubmitView,
    LeaderboardView,
    UserResultsView,
    QuizStatsView,
    CategoryListView,
    CreateQuizView,
    QuizUpdateView,
    QuizDeleteView,
    PendingQuizzesView,
    ApproveQuizView,
    RejectQuizView,
    QuizReportCreateView,
    ReportedQuizzesView,
    StartQuizView,
    add_question,
    add_option,
    update_question,
    update_option,
    update_question_order,
    update_option_order,
    publish_quiz,
)

urlpatterns = [
    # user quiz endpoints
    path("", QuizListCreateView.as_view(), name="quiz_list_create"),
    path("create/", CreateQuizView.as_view(), name="quiz_create"),
    path("<int:pk>/", QuizDetailView.as_view(), name="quiz_detail"),
    path("<int:pk>/update/", QuizUpdateView.as_view(), name="quiz_update"),
    path("<int:pk>/delete/", QuizDeleteView.as_view(), name="quiz_delete"),
    path("<int:pk>/submit/", QuizSubmitView.as_view(), name="quiz_submit"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("results/", UserResultsView.as_view(), name="user_results"),
    path("<int:pk>/stats/", QuizStatsView.as_view(), name="quiz_stats"),
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("start/", StartQuizView.as_view(), name="quiz_start"),


    # admin
    path("pending/", PendingQuizzesView.as_view(), name="pending_quizzes"),
    path("<int:pk>/approve/", ApproveQuizView.as_view(), name="approve_quiz"),
    path("<int:pk>/reject/", RejectQuizView.as_view(), name="reject_quiz"),

    # reporting
    path("<int:pk>/report/", QuizReportCreateView.as_view(), name="report_quiz"),
    path("reports/", ReportedQuizzesView.as_view(), name="reported_quizzes"),

    # question and option management in creation flow
    path("<int:quiz_id>/add-question/", add_question, name="add_question"),
    path("<int:quiz_id>/questions/<int:question_id>/add-option/", add_option, name="add_option"),
    path("<int:quiz_id>/questions/<int:question_id>/", update_question, name="update_question"),
    path("<int:quiz_id>/questions/<int:question_id>/options/<int:option_id>/", update_option, name="update_option"),
    path("<int:quiz_id>/reorder-questions/", update_question_order, name="reorder_questions"),
    path("<int:quiz_id>/questions/<int:question_id>/reorder-options/", update_option_order, name="reorder_options"),
    path("<int:quiz_id>/publish/", publish_quiz, name="publish_quiz"),
]
