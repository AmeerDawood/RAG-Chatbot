import logging
import threading

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from ..models import ChatHistory
from ..serializers import ChatHistorySerializer
from ..utils.rag import generate_rag_response

logger = logging.getLogger(__name__)

CACHE_TIMEOUT_SECONDS = 600

GREETINGS = {'hi', 'hello', 'hey', 'salam', 'assalamualaikum'}
GREETING_RESPONSE = (
    'Hello! Welcome to the University of Jhang Assistance Portal. How may I help you today?'
)

_FALLBACK_MARKERS = (
    'information related to this question is currently unavailable',
    'information not found exactly',
    'unable to find relevant information',
    'ai service is unavailable',
    'our ai system is currently experiencing issues',
    'this question is outside my scope',
)


def _is_greeting(query: str) -> bool:
    return query.strip().lower() in GREETINGS


def _is_fallback_response(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _FALLBACK_MARKERS)


def _answer_query(query: str) -> str:
    cache_key = f'cached_answer:{query.strip().lower()}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    answer = generate_rag_response(query)
    if not _is_fallback_response(answer):
        cache.set(cache_key, answer, timeout=CACHE_TIMEOUT_SECONDS)
    return answer


def _background_answer(query: str, chat_id: int):
    try:
        answer = _answer_query(query)
        ChatHistory.objects.filter(pk=chat_id).update(answer=answer)
    except Exception:
        logger.exception('Background RAG generation failed for chat_id=%s', chat_id)
        ChatHistory.objects.filter(pk=chat_id).update(
            answer='An error occurred while processing your request.'
        )


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([AllowAny])
@csrf_exempt
def ask_query(request):
    user = request.user if request.user and request.user.is_authenticated else None
    query = request.data.get('query', '').strip()

    if not query:
        return Response({'error': 'No query provided.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if _is_greeting(query):
            if user:
                chat = ChatHistory.objects.create(user=user, question=query, answer=GREETING_RESPONSE)
                return Response({'response': GREETING_RESPONSE, 'chat_id': chat.pk})
            return Response({'response': GREETING_RESPONSE})

        if not user:
            answer = _answer_query(query)
            return Response({'response': answer})

        # Authenticated: create a placeholder row, answer in the background,
        # and let the client poll get_chat_response_by_id for the result.
        chat = ChatHistory.objects.create(user=user, question=query, answer='')
        threading.Thread(target=_background_answer, args=(query, chat.pk), daemon=True).start()
        return Response(
            {'response': 'Processing...', 'chat_id': chat.pk},
            status=status.HTTP_202_ACCEPTED,
        )

    except Exception:
        logger.exception('ask_query failed for query: %s', query)
        return Response(
            {'error': 'Query failed. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_chat_response_by_id(request, chat_id):
    chat = get_object_or_404(ChatHistory, pk=chat_id)

    if chat.user_id and chat.user_id != request.user.id and not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_ready = bool(chat.answer)
    return JsonResponse({
        'question': chat.question,
        'answer': chat.answer or 'Processing...',
        'ready': is_ready,
    })


class ChatHistoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            history = ChatHistory.objects.all()
        else:
            history = ChatHistory.objects.filter(user=request.user, is_deleted=False)
        return Response(ChatHistorySerializer(history, many=True).data)


chat_history_list = ChatHistoryListView.as_view()


class ChatHistoryDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        chat = get_object_or_404(ChatHistory, pk=pk)
        if not request.user.is_staff and chat.user_id != request.user.id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        if request.user.is_staff:
            chat.delete()
        else:
            chat.is_deleted = True
            chat.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)


chat_history_delete_one = ChatHistoryDeleteView.as_view()


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def chat_history_delete_all(request):
    user = request.user
    if user.is_staff:
        ChatHistory.objects.all().delete()
    else:
        ChatHistory.objects.filter(user=user).update(is_deleted=True)
    return Response(status=status.HTTP_204_NO_CONTENT)
