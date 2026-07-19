from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('chatbot.urls')),
    path('auth/', include('authenticate.urls')),

    # Minimal demo UI exercising the real /query/ and /upload/ JSON APIs.
    path('demo/query/', TemplateView.as_view(template_name='query.html'), name='demo_query'),
    path('demo/upload/', TemplateView.as_view(template_name='upload.html'), name='demo_upload'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
