from .models import Notification

def create_notification(user, message):
    Notification.objects.create(user=user, message=message)
    print(f" Notification sent to {user.email}: {message}")