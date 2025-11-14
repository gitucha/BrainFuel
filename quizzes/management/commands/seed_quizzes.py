from django.core.management.base import BaseCommand
from quizzes.models import Quiz, Question, Option
from django.contrib.auth import get_user_model
import random

User = get_user_model()

CATEGORIES = [
    "Science",
    "History",
    "Technology",
    "Math",
    "Geography",
    "Literature",
    "Sports",
    "Pop Culture",
    "Logic",
    "General Knowledge",
]

DIFFICULTIES = ["easy", "medium", "hard"]

# --- Question Pools (Option C Mix) ---

SCIENCE_QS = [
    ("What planet is known as the Red Planet?", ["Mars", "Jupiter", "Saturn", "Venus"], "Mars"),
    ("What gas do plants absorb during photosynthesis?", ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"], "Carbon Dioxide"),
    ("What is H2O?", ["Salt", "Water", "Hydrogen", "Ozone"], "Water"),
]

HISTORY_QS = [
    ("Who was the first President of the United States?", ["George Washington", "Abraham Lincoln", "John Adams", "Thomas Jefferson"], "George Washington"),
    ("What year did World War II end?", ["1941", "1943", "1945", "1950"], "1945"),
    ("Which empire built the Colosseum?", ["Roman", "Greek", "Ottoman", "Persian"], "Roman"),
]

TECH_QS = [
    ("HTML stands for?", ["Hyper Trainer Marking Language", "HyperText Markup Language", "HighText Machine Language", "None"], "HyperText Markup Language"),
    ("What does CPU stand for?", ["Central Processing Unit", "Computer Power Unit", "Control Panel Unit", "Compute Performance Usage"], "Central Processing Unit"),
    ("Python was created by?", ["Guido van Rossum", "Elon Musk", "James Gosling", "Alan Turing"], "Guido van Rossum"),
]

MATH_QS = [
    ("What is 12 × 12?", ["124", "144", "112", "154"], "144"),
    ("Solve: 8 + 6 / 3", ["6", "10", "12", "8"], "10"),
    ("What is the square root of 81?", ["8", "9", "7", "6"], "9"),
]

GEOGRAPHY_QS = [
    ("What is the largest ocean?", ["Atlantic", "Pacific", "Indian", "Arctic"], "Pacific"),
    ("Where is Mount Everest located?", ["China", "India", "Nepal", "Japan"], "Nepal"),
    ("What is the capital of Australia?", ["Sydney", "Melbourne", "Canberra", "Perth"], "Canberra"),
]

LITERATURE_QS = [
    ("Who wrote '1984'?", ["George Orwell", "J.K Rowling", "Mark Twain", "Jane Austen"], "George Orwell"),
    ("Shakespeare wrote…?", ["The Odyssey", "Hamlet", "Inferno", "Ulysses"], "Hamlet"),
    ("Who wrote 'Pride and Prejudice'?", ["Bronte", "Shelley", "Austen", "Eliot"], "Austen"),
]

SPORTS_QS = [
    ("How many players in a football team?", ["9", "10", "11", "12"], "11"),
    ("Where were the 2016 Olympics held?", ["Tokyo", "Rio", "Paris", "London"], "Rio"),
    ("What sport uses a shuttlecock?", ["Tennis", "Badminton", "Squash", "Croquet"], "Badminton"),
]

POP_QS = [
    ("Who sang 'Blinding Lights'?", ["The Weeknd", "Drake", "Justin Bieber", "Bruno Mars"], "The Weeknd"),
    ("Which movie features Iron Man?", ["DC Universe", "Harry Potter", "Star Wars", "Marvel Universe"], "Marvel Universe"),
    ("What show features Eleven?", ["The Boys", "Stranger Things", "Loki", "Lost"], "Stranger Things"),
]

LOGIC_QS = [
    ("If A=1, B=2… what is Z?", ["24", "25", "26", "27"], "26"),
    ("Which number completes the sequence: 2, 4, 8, 16, ?", ["18", "24", "32", "20"], "32"),
    ("What has keys but can't open locks?", ["Map", "Piano", "Clock", "River"], "Piano"),
]

GK_QS = [
    ("What is the capital of Kenya?", ["Nairobi", "Kampala", "Accra", "Lagos"], "Nairobi"),
    ("How many continents exist?", ["5", "6", "7", "8"], "7"),
    ("Which is the fastest land animal?", ["Cheetah", "Lion", "Horse", "Falcon"], "Cheetah"),
]

QUESTION_MAP = {
    "Science": SCIENCE_QS,
    "History": HISTORY_QS,
    "Technology": TECH_QS,
    "Math": MATH_QS,
    "Geography": GEOGRAPHY_QS,
    "Literature": LITERATURE_QS,
    "Sports": SPORTS_QS,
    "Pop Culture": POP_QS,
    "Logic": LOGIC_QS,
    "General Knowledge": GK_QS,
}


class Command(BaseCommand):
    help = "Seeds the database with 50 mixed quizzes (C type)"

    def handle(self, *args, **kwargs):
        Quiz.objects.all().delete()
        Question.objects.all().delete()
        Option.objects.all().delete()

        user = User.objects.first()

        for category in CATEGORIES:
            qs = QUESTION_MAP[category]
            for i in range(5):  # 5 quizzes per category
                quiz = Quiz.objects.create(
                    title=f"{category} Quiz {i+1}",
                    description=f"A fun and educational {category.lower()} quiz.",
                    category=category,
                    difficulty=random.choice(DIFFICULTIES),
                    created_by=user,
                    status="approved",
                )

                # add questions
                for (text, opts, correct) in qs:
                    q = Question.objects.create(quiz=quiz, text=text)
                    for o in opts:
                        Option.objects.create(
                            question=q,
                            text=o,
                            is_correct=(o == correct)
                        )

        self.stdout.write(self.style.SUCCESS("✔ Successfully seeded 50 mixed quizzes (Option C)!"))
