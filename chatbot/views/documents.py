import logging
import os
import threading

from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from chatbot.models import UploadedFile
from ..serializers import UploadedFileSerializer
from ..utils.embedding_setup import chroma_collection
from ..utils.ingestion import ALLOWED_EXTENSIONS, generate_file_hash, process_uploaded_file

logger = logging.getLogger(__name__)


def _run_indexing_in_background(uploaded_id):
    def task():
        try:
            uploaded = UploadedFile.objects.get(pk=uploaded_id)
            process_uploaded_file(uploaded)
        except Exception:
            logger.exception('Background indexing failed for UploadedFile id=%s', uploaded_id)

    threading.Thread(target=task, daemon=True).start()


class UploadDocumentView(APIView):
    """Admin-only: upload a document for RAG indexing.

    ISSUES.md #4: in the original project this endpoint had no authentication
    at all, letting anyone inject or overwrite content in the knowledge base.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        title = request.POST.get('title')
        file = request.FILES.get('file')

        if not title or not file:
            return JsonResponse({'error': 'Title and file are required.'}, status=400)

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return JsonResponse(
                {'error': f'Unsupported file type "{ext}". Allowed: {", ".join(ALLOWED_EXTENSIONS)}'},
                status=400,
            )

        if file.size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            return JsonResponse({'error': f'File exceeds the {max_mb}MB size limit.'}, status=400)

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.name)
        try:
            with open(temp_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            file_hash = generate_file_hash(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        existing = UploadedFile.objects.filter(file_hash=file_hash, status='success').first()
        if existing:
            return JsonResponse({
                'message': 'This file has already been indexed.',
                'uploaded_id': existing.pk,
                'title': existing.title,
                'file': existing.file.url,
                'status': existing.status,
            })

        file.seek(0)
        uploaded_file = UploadedFile.objects.create(title=title, file=file, status='pending')

        _run_indexing_in_background(uploaded_file.pk)

        return JsonResponse({
            'message': 'File uploaded. Indexing in progress.',
            'uploaded_id': uploaded_file.pk,
            'title': uploaded_file.title,
            'file': uploaded_file.file.url,
            'status': uploaded_file.status,
        })


upload_document = UploadDocumentView.as_view()


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAdminUser])
def check_status(request, uploaded_id):
    try:
        uploaded = UploadedFile.objects.get(pk=uploaded_id)
    except UploadedFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)

    return JsonResponse({
        'status': uploaded.status,
        'error_message': uploaded.error_message,
        'file': uploaded.file.name,
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAdminUser])
def upload_list(request):
    files = UploadedFile.objects.all().order_by('-uploaded_at')
    return JsonResponse({'files': UploadedFileSerializer(files, many=True).data})


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAdminUser])
def delete_uploaded_file(request, file_id):
    try:
        uploaded = UploadedFile.objects.get(pk=file_id)
    except UploadedFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)

    uploaded.file.delete(save=False)

    if uploaded.file_hash:
        # document_id metadata is set at ingestion time (see utils/ingestion.py) —
        # this is the fix for ISSUES.md #3, where the original project deleted
        # by a metadata key ("document_id") that was never actually written,
        # so vectors were never removed.
        chroma_collection.delete(where={'document_id': uploaded.file_hash})
    else:
        logger.warning('UploadedFile id=%s has no file_hash; skipping vector deletion.', file_id)

    uploaded.delete()
    return JsonResponse({'message': 'File deleted successfully'})


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAdminUser])
def chroma_list_docs(request):
    try:
        results = chroma_collection.get(include=['documents', 'metadatas'])
        documents = [
            {'document': doc, 'metadata': meta}
            for doc, meta in zip(results['documents'], results.get('metadatas', [{}]))
        ]
        return JsonResponse({'documents': documents})
    except Exception:
        logger.exception('chroma_list_docs failed')
        return JsonResponse({'error': 'Unable to list indexed documents.'}, status=500)
