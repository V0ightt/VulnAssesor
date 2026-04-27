from .views import dangerous_call, healthcheck


urlpatterns = [
    ("health", healthcheck),
    ("run", dangerous_call),
]
