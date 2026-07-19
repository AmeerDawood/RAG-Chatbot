from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views


@ensure_csrf_cookie
def set_csrf_token(request):
    return JsonResponse({'detail': 'CSRF cookie set'})


urlpatterns = [
    path('api/set-csrf/', set_csrf_token, name='set_csrf_token'),

    # Chat
    path('query/', views.ask_query, name='ask_query'),
    path('chat-response/<int:chat_id>/', views.get_chat_response_by_id, name='get_chat_response_by_id'),
    path('chat-history/', views.chat_history_list, name='chat_history_list'),
    path('chat-history/<int:pk>/', views.chat_history_delete_one, name='chat_history_delete_one'),
    path('chat-history/delete-all/', views.chat_history_delete_all, name='chat_history_delete_all'),

    # Document management (admin only)
    path('upload/', views.upload_document, name='upload_document'),
    path('upload/status/<int:uploaded_id>/', views.check_status, name='check_status'),
    path('upload/list/', views.upload_list, name='upload_list'),
    path('delete-file/<int:file_id>/', views.delete_uploaded_file, name='delete_uploaded_file'),
    path('chroma-list-docs/', views.chroma_list_docs, name='chroma_list_docs'),
]
