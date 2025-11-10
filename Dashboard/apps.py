"""
AppConfig for Dashboard app with startup initialization.
"""
from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Dashboard'

    def ready(self):
        """
        Called when Django starts.
        This is a good place to run one-time initialization.
        """
        # Import here to avoid AppRegistryNotReady error
        pass  # We'll use a management command instead for safety

