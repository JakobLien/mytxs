from django.apps import AppConfig

class MytxsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mytxs'

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver.
        import mytxs.signals.fileSignals
        import mytxs.signals.logSignals
        import mytxs.signals.loginSignals