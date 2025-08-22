from django.db import models

class SeytemPrompt(models.Model):
    custom_instructions = models.TextField()
    custom_data = models.TextField()
    base_prompt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Prompt'
        verbose_name_plural = 'System Prompts'
        ordering = ['-updated_at']
        
class APIKey(models.Model):
    name = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-updated_at']
              
    def get_api_key(self):
        return self.api_key
        
    def __str__(self):
        return f'{self.name} -> {self.api_key[:4]}...{self.api_key[-4:]}'
    

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