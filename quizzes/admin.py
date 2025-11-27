from django.contrib import admin
from .models import Quiz, Question, Option, QuizAttempt, QuizReport


class OptionInline(admin.TabularInline):
    model = Option
    extra = 1
    fields = ("text", "is_correct", "order")


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("text", "order", "difficulty")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "difficulty", "status", "is_premium", "created_by", "created_at")
    list_filter = ("status", "difficulty", "is_premium", "category")
    search_fields = ("title", "description", "category")
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "quiz", "order", "difficulty")
    list_filter = ("quiz", "difficulty")
    search_fields = ("text",)


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("text", "question", "is_correct", "order")
    list_filter = ("is_correct", "question__quiz")
    search_fields = ("text",)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "quiz", "score", "correct", "total", "xp_earned", "thalers_earned", "created_at")
    list_filter = ("quiz", "user")
    search_fields = ("user__username", "quiz__title")


@admin.register(QuizReport)
class QuizReportAdmin(admin.ModelAdmin):
    list_display = ("quiz", "user", "created_at")
    search_fields = ("quiz__title", "user__username", "reason")
    list_filter = ("quiz",)
