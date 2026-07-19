from django.contrib import admin

from .models import AnonymousUserLog, ChatHistory, UploadedFile


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'question', 'created_at', 'is_deleted')
    search_fields = ('question', 'answer')
    list_filter = ('is_deleted', 'language')


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'uploaded_at')
    list_filter = ('status',)


@admin.register(AnonymousUserLog)
class AnonymousUserLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_key', 'timestamp')
