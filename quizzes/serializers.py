from rest_framework import serializers
from .models import Quiz, Question, Option, QuizAttempt, QuizReport


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "text", "is_correct"]
        extra_kwargs = {"is_correct": {"write_only": True}}  # hide from client


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True)

    class Meta:
        model = Question
        fields = ["id", "text", "options"]

    def create(self, validated_data):
        options_data = validated_data.pop("options")
        question = Question.objects.create(**validated_data)
        for option_data in options_data:
            Option.objects.create(question=question, **option_data)
        return question


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)
    created_by = serializers.ReadOnlyField(source="created_by.email")

    class Meta:
        model = Quiz
        fields = ["id", "title", "description", "category", "created_at", "created_by", "questions"]

    def create(self, validated_data):
        questions_data = validated_data.pop("questions", [])
        quiz = Quiz.objects.create(**validated_data)
        for q_data in questions_data:
            options_data = q_data.pop("options", [])
            question = Question.objects.create(quiz=quiz, **q_data)
            for opt_data in options_data:
                Option.objects.create(question=question, **opt_data)
        return quiz

class QuizAttemptSerializer(serializers.ModelSerializer):
    quiz_title = serializers.ReadOnlyField(source="quiz.title")

    class Meta:
        model = QuizAttempt
        fields = '__all__'

class QuizReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizReport
        fields = ["id", "quiz", "user", "reason", "created_at"]
        read_only_fields = ["user"]