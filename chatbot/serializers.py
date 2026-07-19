from rest_framework import serializers

from .models import ChatHistory, UploadedFile


class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = '__all__'


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = ('id', 'title', 'file', 'status', 'error_message', 'uploaded_at')
