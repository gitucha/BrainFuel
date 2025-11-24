from django.urls import path
from . import views

urlpatterns = [
    path("", views.list_notifications, name="notifications_list"),
    path("<int:pk>/read/", views.mark_notification_read, name="notification_read"),
    path("<int:pk>/delete/", views.delete_notification, name="notification_delete"),
]
