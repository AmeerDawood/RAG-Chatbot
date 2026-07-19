"""
WSGI config for umt_chatbot_groq project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'umt_chatbot_groq.settings')

application = get_wsgi_application()
