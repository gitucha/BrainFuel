from django.urls import path
from . import views

urlpatterns = [
    path("create/", views.create_payment),
    path("verify/", views.verify_payment),
    path("history/", views.PaymentHistoryView.as_view()),
    path("discounts/", views.apply_discount),
    path("creator-earnings/", views.CreatorEarningsView.as_view()),
    path("add-thaler/", views.add_thalers),
    path("upgrade/", views.upgrade_user),
]