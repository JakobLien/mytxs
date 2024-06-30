from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in


@receiver(user_logged_in)
def increment_innlogginger(user, **kwargs):
    user.medlem.innlogginger += 1
    user.medlem.save()
