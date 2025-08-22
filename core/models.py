from django.db import models

class Conversation(models.Model):
    sender_id = models.CharField(max_length=255)
    history = models.TextField(default="[]", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_history(self):
        return self.history if self.history else "[]"
    
    class Meta:
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return self.sender_id