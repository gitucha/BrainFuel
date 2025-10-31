from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from .models import Quiz, Question, Option, QuizAttempt,QuizReport
from .serializers import QuizSerializer, QuizAttemptSerializer, QuizReportSerializer
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from django.db.models import Avg,Count,Q
from django.shortcuts import get_object_or_404

User = get_user_model()


class QuizListCreateView(generics.ListCreateAPIView):
    queryset = Quiz.objects.all().order_by("-created_at")
    serializer_class = QuizSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class QuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]


class QuizSubmitView(generics.GenericAPIView):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        quiz = Quiz.objects.get(pk=pk)
        answers = request.data.get("answers", {})  # {"question_id": option_id}
        correct = 0
        total = quiz.questions.count()

        for q in quiz.questions.all():
            chosen = answers.get(str(q.id))
            if chosen:
                try:
                    option = Option.objects.get(pk=chosen, question=q)
                    if option.is_correct:
                        correct += 1
                except Option.DoesNotExist:
                    pass

        score = int((correct / total) * 100) if total else 0

        # XP system: 10 XP per correct answer
        xp_earned = correct * 10
        user = request.user
        user.xp += xp_earned
        if user.xp >= 100 * user.level:
            user.level += 1
            user.badges.append(f"Level {user.level}")
        user.save()

        QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            score=score,        
            correct=correct,
            total=total,
            xp_earned=xp_earned,
        )

        return Response(
            {"score": score, "correct": correct, "total": total, "xp_earned": xp_earned},
            status=status.HTTP_200_OK,
        )

class LeaderboardView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        users = User.objects.all().order_by('-xp', 'level')[:10]
        leaderboard = [
            {
                "username": user.username,
                "level": user.level,
                "xp": user.xp,
                "badges": user.badges,
            }
            for user in users
        ]
        return Response(leaderboard)
    
class UserResultsView(generics.ListAPIView):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user).order_by('-created_at')
    
class QuizStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        quiz = Quiz.objects.get(pk=pk)
        attempts = QuizAttempt.objects.filter(quiz=quiz)
        data = {
            "quiz": quiz.title,
            "total_attempts": attempts.count(),
            "average_score": round(attempts.aggregate(Avg("score"))["score__avg"] or 0, 2),
            "unique_users": attempts.values("user").distinct().count(),
        }
        return Response(data)
    
class CategoryListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        categories = Quiz.objects.values_list('category', flat=True).distinct()
        return Response({"categories": list(categories)})
    
class PendingQuizzesView(generics.ListAPIView):
    queryset = Quiz.objects.filter(status='pending')
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAdminUser]

class ApproveQuizView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
         quiz = Quiz.objects.get(pk=pk)
         quiz.status = 'approved'
         quiz.save()
         return Response({'message': 'quiz approved'})
        except Quiz.DoesNotExist:
         return Response({'error': 'quiz not found'}, status=status.HTTP_404_NOT_FOUND)
        
# List all approved quizzes
class ApprovedQuizListView(generics.ListAPIView):
    queryset = Quiz.objects.filter(status="approved")
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]

# Retrieve a single approved quiz
class ApprovedQuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.filter(status="approved")
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]

# Report a quiz (user)
class QuizReportCreateView(generics.CreateAPIView):
    queryset = QuizReport.objects.all()
    serializer_class = QuizReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        quiz_id = self.kwargs["pk"]
        quiz = get_object_or_404(Quiz, id=quiz_id)
        serializer.save(reported_by=self.request.user, quiz=quiz)

class RejectQuizView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
         quiz = Quiz.objects.get(pk=pk)
         quiz.status = 'rejected'
         quiz.save()
         return Response({'message': 'quiz rejected'})
        except Quiz.DoesNotExist:
         return Response({'error': 'quiz not found'}, status=status.HTTP_404_NOT_FOUND)
    
class ReportQuizView(generics.CreateAPIView):
    serializer_class = QuizReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ReportedQuizzesView(generics.ListAPIView):
    queryset = QuizReport.objects.all()
    serializer_class = QuizReportSerializer
    permission_classes = [permissions.IsAdminUser]

class QuizListView(generics.ListAPIView):
    """
    List all approved quizzes.
    Optional filters: ?category=Science&difficulty=easy&premium=true
    """
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'category']

    def get_queryset(self):
        queryset = Quiz.objects.filter(status='approved')
        category = self.request.query_params.get('category')
        difficulty = self.request.query_params.get('difficulty')
        premium = self.request.query_params.get('premium')

        if category:
            queryset = queryset.filter(category__icontains=category)
        if difficulty:
            queryset = queryset.filter(difficulty__iexact=difficulty)
        if premium:
            queryset = queryset.filter(is_premium=(premium.lower() == 'true'))

        return queryset


class UserQuizzesView(generics.ListAPIView):
    """List all quizzes created by a specific user"""
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        return Quiz.objects.filter(created_by_id=user_id)


class QuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.filter(status='approved')
    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'


class CreateQuizView(generics.CreateAPIView):
    """Create new quiz - pending by default"""
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='pending')

class QuizUpdateView(generics.UpdateAPIView):
    """Update an existing quiz"""
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        quiz = super().get_object()
        if quiz.created_by != self.request.user:
            raise permissions.PermissionDenied("You do not have permission to edit this quiz.")
        return quiz
    
class QuizDeleteView(generics.DestroyAPIView):
    """Delete an existing quiz"""
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        quiz = super().get_object()
        if quiz.created_by != self.request.user:
            raise permissions.PermissionDenied("You do not have permission to delete this quiz.")
        return quiz