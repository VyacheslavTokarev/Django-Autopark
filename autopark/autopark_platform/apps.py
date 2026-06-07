from django.apps import AppConfig


class AutoparkPlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'autopark_platform'

    def ready(self):
        from . import signals
