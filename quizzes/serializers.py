from rest_framework import serializers
from .models import Quiz, Question, Option, QuizAttempt, QuizReport
from django.contrib.auth import get_user_model

User = get_user_model()


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "text", "is_correct", "order"]

class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "order", "options"]

class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ["id", "title", "description", "category", "difficulty", "status", "is_premium", "questions", "created_by", "created_at"]

class QuizCreateSerializer(serializers.ModelSerializer):
    # For creators who include nested payloads (optional extension)
    class Meta:
        model = Quiz
        fields = ["title", "description", "category", "difficulty", "is_premium"]


class QuizAttemptSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "quiz_title",
            "score",
            "correct",
            "total",
            "xp_earned",
            "thalers_earned",
            "created_at",
        ]
        read_only_fields = ["score", "correct", "total", "xp_earned", "thalers_earned", "created_at"]



class SubmitAnswerSerializer(serializers.Serializer):
    answers = serializers.DictField(
        child=serializers.IntegerField(),
        required=False,
        help_text='Map of question_id -> option_id'
    )

class QuizReportSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    quiz = serializers.PrimaryKeyRelatedField(queryset=Quiz.objects.all())

    class Meta:
        model = QuizReport
        fields = ["id", "quiz", "user", "reason", "created_at"]
        read_only_fields = ["user", "created_at"]

from rest_framework import serializers
from .models import Quiz, Question, Option, QuizAttempt, QuizReport

# Question create/update serializer
class QuestionCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Question
        fields = ["id", "quiz", "text", "order"]
        read_only_fields = ["quiz", "id", "order"]


class OptionCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Option
        fields = ["id", "question", "text", "is_correct", "order"]
        read_only_fields = ["question", "id", "order"]


class OrderUpdateSerializer(serializers.Serializer):
    order = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of IDs in desired order"
    )
