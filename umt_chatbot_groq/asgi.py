"""
ASGI config for umt_chatbot_groq project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umt_chatbot_groq.settings')

application = get_asgi_application()
