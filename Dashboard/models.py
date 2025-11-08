from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Website(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='websites')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
