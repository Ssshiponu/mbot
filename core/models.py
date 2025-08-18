from django.db import models


class Conversation(models.Model):
    sender_id = models.CharField(max_length=255)
    history = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.sender_id