import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import Option, Question, Quiz
from quizzes.seed_data import QUESTION_BANK

User = get_user_model()

# Difficulty of "<Category> Quiz 1" .. "<Category> Quiz 5"
QUIZ_DIFFICULTIES = ["easy", "easy", "medium", "medium", "hard"]
QUESTIONS_PER_QUIZ = 4


def validate_bank():
    """Fail loudly on bad data instead of seeding broken questions."""
    seen = set()
    for category, levels in QUESTION_BANK.items():
        for difficulty in set(QUIZ_DIFFICULTIES):
            needed = QUIZ_DIFFICULTIES.count(difficulty) * QUESTIONS_PER_QUIZ
            got = len(levels.get(difficulty, []))
            if got != needed:
                raise CommandError(f"{category}/{difficulty}: need {needed} questions, found {got}")
            for text, options, correct in levels[difficulty]:
                if text in seen:
                    raise CommandError(f"Duplicate question: {text}")
                seen.add(text)
                if len(text) > 255:
                    raise CommandError(f"Question too long (max 255): {text}")
                if len(set(options)) != 4 or correct not in options:
                    raise CommandError(f"Need 4 distinct options including the answer: {text}")


class Command(BaseCommand):
    help = (
        "Seed/refresh the built-in quizzes: 5 quizzes per category, each with "
        "its own questions matching the quiz's difficulty. Updates existing "
        "seeded quizzes in place (keeping attempt history); quizzes created "
        "by users are not touched."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        validate_bank()

        author = (
            User.objects.filter(is_superuser=True).order_by("id").first()
            or User.objects.order_by("id").first()
        )
        if author is None:
            raise CommandError("Create a user first (e.g. python manage.py createsuperuser).")

        created = updated = 0
        for category, levels in QUESTION_BANK.items():
            used = {d: 0 for d in levels}  # how many questions of each level are taken

            for i, difficulty in enumerate(QUIZ_DIFFICULTIES, start=1):
                title = f"{category} Quiz {i}"
                start = used[difficulty]
                questions = levels[difficulty][start:start + QUESTIONS_PER_QUIZ]
                used[difficulty] += QUESTIONS_PER_QUIZ

                quiz = Quiz.objects.filter(title=title, category=category).order_by("id").first()
                if quiz is None:
                    quiz = Quiz(title=title, category=category, created_by=author)
                    created += 1
                else:
                    updated += 1
                quiz.description = f"A {difficulty} {category.lower()} quiz."
                quiz.difficulty = difficulty
                quiz.status = "approved"
                quiz.save()

                # Replace the questions. QuizAttempt rows only reference the
                # quiz, so users' scores and history are kept.
                quiz.questions.all().delete()
                rng = random.Random(title)  # same option order on every run
                for order, (text, opts, correct) in enumerate(questions):
                    question = Question.objects.create(
                        quiz=quiz, text=text, order=order, difficulty=difficulty
                    )
                    shuffled = list(opts)
                    rng.shuffle(shuffled)
                    Option.objects.bulk_create(
                        Option(question=question, text=o, is_correct=(o == correct), order=n)
                        for n, o in enumerate(shuffled)
                    )

        total_q = len(QUIZ_DIFFICULTIES) * QUESTIONS_PER_QUIZ * len(QUESTION_BANK)
        self.stdout.write(self.style.SUCCESS(
            f"✔ Seeded {created + updated} quizzes ({created} new, {updated} updated), "
            f"{total_q} unique questions."
        ))
