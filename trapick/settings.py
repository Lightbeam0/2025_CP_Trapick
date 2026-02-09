"""
Django settings for trapick project.
Supports both LOCAL (with ML) and CLOUD (dashboard-only) deployments.
"""
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# ✅ Load .env.local if it exists
env_file = BASE_DIR / '.env.local'
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print("ℹ️  No .env.local file found, using system environment variables")

# ==================== DEPLOYMENT ENVIRONMENT DETECTION ====================
# Set DEPLOYMENT_ENV=cloud on your cloud platform
# Set DEPLOYMENT_ENV=local (or leave unset) on your local machine
DEPLOYMENT_ENV = os.environ.get('DEPLOYMENT_ENV', 'local')
IS_CLOUD_DEPLOYMENT = DEPLOYMENT_ENV == 'cloud'

# Quick check logging
if IS_CLOUD_DEPLOYMENT:
    print("🌐 Running in CLOUD mode (dashboard-only, no ML)")
else:
    print("💻 Running in LOCAL mode (full system with ML)")

# ==================== SECURITY ====================
# Handle SECRET_KEY securely
if not os.environ.get('SECRET_KEY'):
    if IS_CLOUD_DEPLOYMENT:
        raise ValueError("SECRET_KEY must be set in cloud deployments!")
    else:
        SECRET_KEY = 'django-insecure-_u9zxz!@e8mafz9^@b$)*hi-egorgmvgg+16%7re0@9g3k*d9='
        print("⚠️  Using default SECRET_KEY (local development only)")
else:
    SECRET_KEY = os.environ['SECRET_KEY']

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# For Heroku
HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
if HEROKU_APP_NAME:
    ALLOWED_HOSTS.append(f'{HEROKU_APP_NAME}.herokuapp.com')

# ==================== INSTALLED APPS ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'trapickapp',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
]

# ✅ CLOUD-SPECIFIC: Remove Channels (no WebSocket needed for dashboard)
if not IS_CLOUD_DEPLOYMENT:
    INSTALLED_APPS.append('channels')
    print("  ✓ Channels enabled (WebSocket support)")
else:
    print("  ✓ Channels disabled (not needed for cloud)")

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.RemoteUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trapick.urls'

# ==================== TEMPLATES ====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'frontend', 'build')],
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

WSGI_APPLICATION = 'trapick.wsgi.application'

# ==================== DATABASE ====================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'trapickdb'),
        'USER': os.environ.get('DB_USER', 'trapickuser'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'strongpassword'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Support for DATABASE_URL (common in cloud platforms)
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )

# ==================== PASSWORD VALIDATION ====================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==================== STATIC FILES ====================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / "frontend" / "build" / "static",
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==================== MEDIA FILES ====================
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ✅ CLOUD-SPECIFIC: Smaller upload limits (only for sync API, no videos)
if IS_CLOUD_DEPLOYMENT:
    DATA_UPLOAD_MAX_MEMORY_SIZE = 2097152   # 2MB (for JSON sync data)
    FILE_UPLOAD_MAX_MEMORY_SIZE = 2097152   # 2MB
    print("  ✓ Upload limits: 2MB (sync API only)")
else:
    DATA_UPLOAD_MAX_MEMORY_SIZE = 2147483648  # 2GB (for video uploads)
    FILE_UPLOAD_MAX_MEMORY_SIZE = 2147483648  # 2GB
    print("  ✓ Upload limits: 2GB (video uploads enabled)")

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# ==================== CORS SETTINGS ====================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

# ✅ CLOUD-SPECIFIC: Add production frontend URL
if IS_CLOUD_DEPLOYMENT and HEROKU_APP_NAME:
    CORS_ALLOWED_ORIGINS.append(f"https://{HEROKU_APP_NAME}.herokuapp.com")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
    'x-sync-api-key',  # ✅ For sync endpoint
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Disposition']

# ==================== SESSION & SECURITY ====================
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# ==================== AUTHENTICATION ====================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/api/auth/login/'
LOGIN_REDIRECT_URL = '/home'
LOGOUT_REDIRECT_URL = '/'

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# ✅ Disable browsable API in cloud deployments
if IS_CLOUD_DEPLOYMENT:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
        'rest_framework.renderers.JSONRenderer',
    ]

# ==================== CHANNELS (WebSocket) - LOCAL ONLY ====================
if not IS_CLOUD_DEPLOYMENT:
    ASGI_APPLICATION = 'trapick.asgi.application'
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(
                    os.environ.get('REDIS_HOST', '127.0.0.1'),
                    int(os.environ.get('REDIS_PORT', 6379))
                )],
            },
        },
    }
    print("  ✓ WebSocket channels configured")

# ==================== CACHE - LOCAL ONLY ====================
if not IS_CLOUD_DEPLOYMENT:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'TIMEOUT': 3600,
        }
    }
    print("  ✓ Cache configured")

# ==================== CELERY - LOCAL ONLY ====================
if not IS_CLOUD_DEPLOYMENT:
    # Import kombu only in local mode
    try:
        from kombu import Queue
    except ImportError:
        print("  ⚠️ Warning: kombu not available (Celery disabled)")
        Queue = None
    
    if Queue:
        CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
        CELERY_RESULT_BACKEND = CELERY_BROKER_URL
        CELERY_TASK_ACKS_LATE = True
        CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True
        CELERY_TASK_TRACK_STARTED = True

        CELERY_TASK_ROUTES = {
            'trapickapp.tasks.process_video_task': {'queue': 'trapick_queue'},
            'trapickapp.tasks.process_session_task': {'queue': 'trapick_queue'},
        }
        CELERY_TASK_QUEUES = (Queue('trapick_queue', routing_key='trapick_queue'),)
        CELERY_TASK_DEFAULT_QUEUE = 'trapick_queue'
        print("  ✓ Celery configured for video processing")
else:
    print("  ✓ Celery disabled (not needed for cloud)")

# ==================== CLOUD SYNC CONFIGURATION ====================
# ✅ LOCAL: URL where to send data
if not IS_CLOUD_DEPLOYMENT:
    CLOUD_SYNC_URL = os.environ.get(
        'CLOUD_SYNC_URL',
        'https://your-app.herokuapp.com/api/sync/'  # Fixed trailing spaces
    ).rstrip('/') + '/'  # Ensure clean URL
    CLOUD_SYNC_API_KEY = os.environ.get('CLOUD_SYNC_API_KEY', None)
    if CLOUD_SYNC_API_KEY:
        print(f"  ✓ Cloud sync configured: {CLOUD_SYNC_URL}")

# ✅ CLOUD: API key to accept data
if IS_CLOUD_DEPLOYMENT:
    SYNC_API_KEY = os.environ.get('SYNC_API_KEY', None)
    if SYNC_API_KEY:
        print("  ✓ Sync API endpoint enabled")
    else:
        print("  ⚠️ WARNING: SYNC_API_KEY not set - sync endpoint will reject requests")

# ==================== LOGGING ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'trapickapp': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ==================== DEFAULT PRIMARY KEY ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== DEPLOYMENT INFO ====================
print("\n" + "="*60)
print(f"🚀 TRAPICK CONFIGURATION")
print("="*60)
print(f"Environment: {DEPLOYMENT_ENV.upper()}")
print(f"Debug: {DEBUG}")
print(f"Database: {DATABASES['default']['NAME']}@{DATABASES['default']['HOST']}")
if IS_CLOUD_DEPLOYMENT:
    print("Mode: DASHBOARD ONLY (no ML, no video processing)")
else:
    print("Mode: FULL SYSTEM (ML enabled, video processing)")
print("="*60 + "\n")