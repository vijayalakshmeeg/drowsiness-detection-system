from django.db import models
from django.contrib.auth.models import User

class EventLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=100)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.timestamp} - {self.event_type}"

    class Meta:
        ordering = ['-timestamp']
