from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Quiz, Question, Option
from .serializers import QuizSerializer
from django.contrib.auth import get_user_model

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

        return Response(
            {"score": score, "correct": correct, "total": total, "xp_earned": xp_earned},
            status=status.HTTP_200_OK,
        )
