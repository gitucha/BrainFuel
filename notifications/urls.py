# notifications/urls.py
from django.urls import path
from . import views
from .views import delete_notification

urlpatterns = [
    path("", views.list_notifications, name="notifications-list"),
    path("mark-all-read/", views.mark_all_notifications_read, name="notifications-mark-all"),
    path("<int:pk>/read/", views.mark_notification_read, name="notifications-read"),
    path("<int:pk>/", views.delete_notification, name="notifications-delete"),
    path("<int:pk>/delete/", delete_notification, name="notifications-delete")
]
