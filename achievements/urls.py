from django.urls import path
from .views import (
    my_achievements,
    all_achievements,
    achievement_overview,
)

urlpatterns = [
    path("my/", my_achievements, name="my-achievements"),
    path("all/", all_achievements, name="all-achievements"),
    path("overview/", achievement_overview, name="achievement-overview"),
]
