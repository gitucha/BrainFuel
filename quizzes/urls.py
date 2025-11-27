# quizzes/urls.py
from django.urls import path

from .views import (
    QuizListCreateView,
    QuizDetailView,
    QuizUpdateView,
    QuizDeleteView,
    StartQuizView,
    QuizSubmitView,
    LeaderboardView,
    UserResultsView,
    QuizStatsView,
    CategoryListView,
    PendingQuizzesView,
    ApproveQuizView,
    RejectQuizView,
    ReportedQuizzesView,
    list_quiz_reports,
    add_question,
    add_option,
    update_question,
    update_option,
    update_question_order,
    update_option_order,
    publish_quiz,
    quiz_questions_limited,
)
from . import views

urlpatterns = [
    # list / create
    path("quizzes/", QuizListCreateView.as_view(), name="quiz-list"),
    path("quizzes/<int:pk>/", QuizDetailView.as_view(), name="quiz-detail"),
    path("quizzes/<int:pk>/update/", QuizUpdateView.as_view(), name="quiz-update"),
    path("quizzes/<int:pk>/delete/", QuizDeleteView.as_view(), name="quiz-delete"),

    # limited questions for a specific quiz (used by QuizTakingGamified)
    path(
        "quizzes/<int:pk>/questions/",
        quiz_questions_limited,
        name="quiz-questions-limited",
    ),

    # submit quiz results
    path(
        "quizzes/<int:pk>/submit/",
        QuizSubmitView.as_view(),
        name="quiz-submit",
    ),

    # optional: generated quiz from pool
    path("quizzes/start/", StartQuizView.as_view(), name="quiz-start"),

    # builder / editing helpers
    path("quizzes/<int:quiz_id>/publish/", publish_quiz, name="quiz-publish"),
    path("quizzes/<int:quiz_id>/questions/add/", add_question, name="question-add"),
    path(
        "quizzes/<int:quiz_id>/questions/<int:question_id>/",
        update_question,
        name="question-update",
    ),
    path(
        "quizzes/<int:quiz_id>/questions/<int:question_id>/options/add/",
        add_option,
        name="option-add",
    ),
    path(
        "quizzes/<int:quiz_id>/questions/<int:question_id>/options/<int:option_id>/",
        update_option,
        name="option-update",
    ),
    path(
        "quizzes/<int:quiz_id>/questions/order/",
        update_question_order,
        name="question-order",
    ),
    path(
        "quizzes/<int:quiz_id>/questions/<int:question_id>/options/order/",
        update_option_order,
        name="option-order",
    ),

    # categories
    path("quizzes/categories/", CategoryListView.as_view(), name="quiz-categories"),

    # moderation
    path("quizzes/pending/", PendingQuizzesView.as_view(), name="quiz-pending"),
    path("quizzes/<int:pk>/approve/", ApproveQuizView.as_view(), name="quiz-approve"),
    path("quizzes/<int:pk>/reject/", RejectQuizView.as_view(), name="quiz-reject"),

    # reports
    path("quizzes/reports/", views.list_quiz_reports, name="quiz-reports"),
    path("quizzes/reported/", ReportedQuizzesView.as_view(), name="quiz-reported"),

    # stats / results / leaderboard
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("results/", UserResultsView.as_view(), name="user-results"),
    path("quizzes/<int:pk>/stats/", QuizStatsView.as_view(), name="quiz-stats"),
]
