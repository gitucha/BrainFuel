from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Quiz, Question, Option, QuizAttempt
from .serializers import QuizSerializer, QuizAttemptSerializer
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from django.db.models import Avg,Count

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