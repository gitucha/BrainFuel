# quizzes/views.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import ThalerTransaction  # if unused you can remove later
from .models import Quiz, Question, Option, QuizAttempt, QuizReport
from .serializers import (
    QuizSerializer,
    QuizCreateSerializer,
    SubmitAnswerSerializer,
    QuizAttemptSerializer,
    QuizReportSerializer,
    QuestionCreateSerializer,
    OptionCreateSerializer,
    OrderUpdateSerializer,
)

import random
import traceback

User = get_user_model()


class QuizListCreateView(generics.ListCreateAPIView):
    """
    GET /api/quizzes/ -> list (filterable)
    POST /api/quizzes/ -> create (auth required, status pending)
    """
    serializer_class = QuizSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "description", "category"]

    def get_queryset(self):
        queryset = Quiz.objects.filter(status="approved")
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")
        premium = self.request.query_params.get("premium")
        search = self.request.query_params.get("search")

        if category:
            queryset = queryset.filter(category__icontains=category)
        if difficulty:
            queryset = queryset.filter(difficulty__iexact=difficulty)
        if premium is not None:
            if premium.lower() in ["true", "1", "yes"]:
                queryset = queryset.filter(is_premium=True)
            else:
                queryset = queryset.filter(is_premium=False)
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset.order_by("-created_at")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        # create as pending by default
        serializer = QuizCreateSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=self.request.user, status="pending")


class QuizDetailView(generics.RetrieveAPIView):
    """
    GET /api/quizzes/<pk>/ : single quiz detail (approved only)
    """
    queryset = Quiz.objects.filter(status="approved")
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]


class CreateQuizView(generics.CreateAPIView):
    serializer_class = QuizCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status="pending")


# ---------- QUESTION & OPTION CRUD / ORDERING ----------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    text = request.data.get("text")
    if not text:
        return Response({"detail": "Text required"}, status=status.HTTP_400_BAD_REQUEST)

    # determine next order
    last = quiz.questions.order_by("-order").first()
    next_order = (last.order + 1) if last else 0

    q = Question.objects.create(quiz=quiz, text=text, order=next_order)
    serializer = QuestionCreateSerializer(q)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_option(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    text = request.data.get("text")
    is_correct = bool(request.data.get("is_correct", False))
    if not text:
        return Response({"detail": "Text required"}, status=status.HTTP_400_BAD_REQUEST)

    last = question.options.order_by("-order").first()
    next_order = (last.order + 1) if last else 0

    opt = Option.objects.create(
        question=question,
        text=text,
        is_correct=is_correct,
        order=next_order,
    )
    serializer = OptionCreateSerializer(opt)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_question(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    serializer = QuestionCreateSerializer(question, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_option(request, quiz_id, question_id, option_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz)
    option = get_object_or_404(Option, pk=option_id, question=question)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    serializer = OptionCreateSerializer(option, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_question_order(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    serializer = OrderUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order_list = serializer.validated_data["order"]

    questions = {q.id for q in quiz.questions.all()}
    if set(order_list) != set(questions):
        return Response(
            {"detail": "Order must include all question IDs for this quiz"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    for idx, qid in enumerate(order_list):
        Question.objects.filter(pk=qid, quiz=quiz).update(order=idx)
    return Response({"detail": "Order updated"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_option_order(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    serializer = OrderUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order_list = serializer.validated_data["order"]

    options = {o.id for o in question.options.all()}
    if set(order_list) != set(options):
        return Response(
            {"detail": "Order must include all option IDs for this question"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    for idx, oid in enumerate(order_list):
        Option.objects.filter(pk=oid, question=question).update(order=idx)
    return Response({"detail": "Option order updated"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if quiz.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    quiz.status = "pending"
    quiz.save()
    return Response({"detail": "Quiz published (pending review)"}, status=status.HTTP_200_OK)


class QuizUpdateView(generics.UpdateAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj = super().get_object()
        if obj.created_by != self.request.user and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You do not have permission to edit this quiz.")
        return obj


class QuizDeleteView(generics.DestroyAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj = super().get_object()
        if obj.created_by != self.request.user and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You do not have permission to delete this quiz.")
        return obj


# ---------- QUIZ START / QUESTIONS (MAX 10) ----------


class StartQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Query params:
          category, difficulty, count (int, max 10)
        Returns: a generated quiz object with selected questions/options (not saved as new Quiz)
        """
        category = request.query_params.get("category")
        difficulty = request.query_params.get("difficulty")
        try:
            count = int(request.query_params.get("count", 5))
        except Exception:
            count = 5

        # clamp 1–10
        count = max(1, min(10, count))

        quizzes = Quiz.objects.filter(status="approved")
        if category:
            quizzes = quizzes.filter(category__icontains=category)
        if difficulty:
            quizzes = quizzes.filter(difficulty__iexact=difficulty)

        questions = Question.objects.filter(quiz__in=quizzes).prefetch_related("options")
        total = questions.count()
        if total == 0:
            return Response({"detail": "No questions found"}, status=status.HTTP_404_NOT_FOUND)

        sample_count = min(count, total)
        sampled = random.sample(list(questions), sample_count)

        payload = {
            "title": f"Generated - {category or 'Mixed'}",
            "description": f"{sample_count} questions",
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "options": [{"id": o.id, "text": o.text} for o in q.options.all()],
                }
                for q in sampled
            ],
            "count": sample_count,
        }
        return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def quiz_questions_limited(request, pk):
    """
    GET /api/quizzes/<pk>/questions/?num_questions=10&difficulty=easy

    - num_questions: user-selected (1–10, clamped).
    - difficulty: "easy" | "medium" | "hard" | omitted -> any difficulty.
    - Only returns questions for an approved quiz.
    - Random order.
    """
    quiz = get_object_or_404(Quiz, pk=pk, status="approved")

    try:
        num = int(request.query_params.get("num_questions", 10))
    except ValueError:
        num = 10
    num = max(1, min(10, num))  # clamp 1–10

    difficulty = request.query_params.get("difficulty")
    qs = quiz.questions.all().prefetch_related("options")

    if difficulty in ["easy", "medium", "hard"]:
        qs = qs.filter(difficulty=difficulty)

    total = qs.count()
    if total == 0:
        return Response({"detail": "No questions found for this quiz"}, status=status.HTTP_404_NOT_FOUND)

    sample_count = min(num, total)
    sampled = random.sample(list(qs), sample_count)

    payload = {
        "quiz": QuizSerializer(quiz).data,
        "num_questions": sample_count,
        "difficulty": difficulty,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": [{"id": o.id, "text": o.text} for o in q.options.all()],
            }
            for q in sampled
        ],
    }
    return Response(payload, status=status.HTTP_200_OK)


# ---------- SUBMIT QUIZ / RESULTS / STATS ----------


class QuizSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        answers = request.data.get("answers", {})

        correct = 0
        total = quiz.questions.count()

        for q in quiz.questions.all():
            chosen_id = answers.get(str(q.id))
            if chosen_id:
                try:
                    option = Option.objects.get(pk=chosen_id, question=q)
                    if option.is_correct:
                        correct += 1
                except Option.DoesNotExist:
                    pass

        score = int((correct / total) * 100) if total else 0

        xp_earned = correct * 10
        thalers_earned = correct * 2

        user = request.user
        user.xp += xp_earned
        user.thalers += thalers_earned

        leveled_up = False
        if user.xp >= user.level * 100:
            user.level += 1
            leveled_up = True

        user.save()

        QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            score=score,
            correct=correct,
            total=total,
            xp_earned=xp_earned,
            thalers_earned=thalers_earned,
        )

        return Response(
            {
                "score": score,
                "correct": correct,
                "total": total,
                "xp_earned": xp_earned,
                "thalers_earned": thalers_earned,
                "leveled_up": leveled_up,
                "new_level": user.level if leveled_up else None,
            }
        )


class LeaderboardView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        users = User.objects.all().order_by("-xp", "-level")[:50]
        leaderboard = [
            {
                "username": user.username,
                "level": user.level,
                "xp": user.xp,
                "badges": user.badges,
                "thalers": getattr(user, "thalers", 0),
            }
            for user in users
        ]
        return Response(leaderboard)


class UserResultsView(generics.ListAPIView):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user).order_by("-created_at")


class QuizStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        attempts = QuizAttempt.objects.filter(quiz=quiz)
        data = {
            "quiz": quiz.title,
            "total_attempts": attempts.count(),
            "average_score": round(attempts.aggregate(Avg("score"))["score__avg"] or 0, 2),
            "unique_users": attempts.values("user").distinct().count(),
        }
        return Response(data)


# ---------- CATEGORIES / MODERATION / REPORTS ----------


class CategoryListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # only approved quizzes, non-empty categories
        categories = (
            Quiz.objects.filter(status="approved")
            .exclude(category__isnull=True)
            .exclude(category__exact="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )
        return Response({"categories": list(categories)})


class PendingQuizzesView(generics.ListAPIView):
    queryset = Quiz.objects.filter(status="pending").order_by("-created_at")
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAdminUser]


class ApproveQuizView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        quiz.status = "approved"
        quiz.save()
        return Response({"message": "quiz approved"})


class RejectQuizView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        quiz.status = "rejected"
        quiz.save()
        return Response({"message": "quiz rejected"})


class QuizReportCreateView(generics.CreateAPIView):
    queryset = QuizReport.objects.all()
    serializer_class = QuizReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # expect {"quiz": <pk>, "reason": "..."}
        serializer.save(user=self.request.user)


class ReportedQuizzesView(generics.ListAPIView):
    queryset = QuizReport.objects.all().order_by("-created_at")
    serializer_class = QuizReportSerializer
    permission_classes = [permissions.IsAdminUser]
