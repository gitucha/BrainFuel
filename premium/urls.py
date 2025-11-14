from django.urls import path
from . import views
from .views_paystack import create_paystack_session, verify_paystack_transaction

urlpatterns = [
    path("create/", create_paystack_session, name="paystack_init"),
    path("verify/", verify_paystack_transaction, name="paystack_verify"),
    path("history/", views.PaymentHistoryView.as_view()),
    path("discounts/", views.apply_discount),
    path("creator-earnings/", views.CreatorEarningsView.as_view()),
    path("add-thaler/", views.add_thalers),
    path("upgrade/", views.upgrade_user),
]