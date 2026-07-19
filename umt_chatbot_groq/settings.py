"""
Django settings for umt_chatbot_groq project.

All secrets and environment-specific values are read from `.env` (see
`.env.example` for the full list). Nothing sensitive is hardcoded here.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=''):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        'SECRET_KEY is not set. Copy .env.example to .env and set a value.'
    )

DEBUG = _env_bool('DEBUG', default=False)

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'chatbot',
    'authenticate',

    # Third-party
    'rest_framework',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'umt_chatbot_groq.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'umt_chatbot_groq.wsgi.application'
ASGI_APPLICATION = 'umt_chatbot_groq.asgi.application'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# I18N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en'
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Karachi')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'authenticate.User'

# ---------------------------------------------------------------------------
# CORS / CSRF
#
# The previous implementation used CORS_ALLOW_ALL_ORIGINS = True together
# with CORS_ALLOW_CREDENTIALS = True, which allows any website to make
# credentialed requests against this API. Origins are now an explicit,
# environment-driven allow-list instead.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:3000')
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000')
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax' if DEBUG else 'None'
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', default=False)

# ---------------------------------------------------------------------------
# DRF / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=6),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ---------------------------------------------------------------------------
# Cache (used for cached chatbot answers, see chatbot/utils/rag.py)
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# ---------------------------------------------------------------------------
# LLM / RAG configuration
#
# Embeddings run locally via a free HuggingFace sentence-transformers model
# (no API key, no per-call cost). Answer generation uses Groq. See
# chatbot/utils/rag.py and chatbot/utils/embedding_setup.py.
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
MAX_UPLOAD_SIZE_BYTES = int(os.getenv('MAX_UPLOAD_SIZE_MB', '20')) * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = ['.csv', '.txt', '.pdf', '.docx', '.xlsx']

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
}
