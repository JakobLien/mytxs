from django.apps import AppConfig

from django.core.signals import request_finished

class MytxsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mytxs'

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver.
        import mytxs.signals.handlers