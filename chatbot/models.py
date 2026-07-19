from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    session_id = models.CharField(max_length=255, blank=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Chat History'
        verbose_name_plural = 'Chat Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.question[:50]}'


class UploadedFile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    file_hash = models.CharField(max_length=64, blank=True, null=True, unique=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class AnonymousUserLog(models.Model):
    session_key = models.CharField(max_length=100, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
