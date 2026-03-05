"""
Django settings for trapick project.
Supports both LOCAL (with ML) and CLOUD (dashboard-only) deployments.
"""
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env.local if it exists
env_file = BASE_DIR / '.env.local'
if env_file.exists():
    load_dotenv(env_file)

# ==================== DEPLOYMENT ENVIRONMENT DETECTION ====================
DEPLOYMENT_ENV = os.environ.get('DEPLOYMENT_ENV', 'local')
IS_CLOUD_DEPLOYMENT = DEPLOYMENT_ENV == 'cloud'

# ==================== SECURITY ====================
if not os.environ.get('SECRET_KEY'):
    if IS_CLOUD_DEPLOYMENT:
        raise ValueError("SECRET_KEY must be set in cloud deployments!")
    else:
        SECRET_KEY = 'django-insecure-_u9zxz!@e8mafz9^@b$)*hi-egorgmvgg+16%7re0@9g3k*d9='
else:
    SECRET_KEY = os.environ['SECRET_KEY']

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

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

if not IS_CLOUD_DEPLOYMENT:
    INSTALLED_APPS.append('channels')

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
FRONTEND_BUILD_DIR = BASE_DIR / 'frontend' / 'build'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_BUILD_DIR] if FRONTEND_BUILD_DIR.exists() else [],
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
database_url = os.environ.get('DATABASE_URL', '').strip()

if database_url:
    os.environ['DATABASE_URL'] = database_url
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    db_name = os.environ.get('DB_NAME', 'trapickdb')
    db_user = os.environ.get('DB_USER', 'trapickuser')
    db_password = os.environ.get('DB_PASSWORD', 'strongpassword')
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '5432')
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_name,
            'USER': db_user,
            'PASSWORD': db_password,
            'HOST': db_host,
            'PORT': db_port,
        }
    }

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

STATICFILES_DIRS = []
react_static_dir = BASE_DIR / "frontend" / "build" / "static"
if react_static_dir.exists():
    STATICFILES_DIRS.append(react_static_dir)

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==================== MEDIA FILES ====================
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

if IS_CLOUD_DEPLOYMENT:
    DATA_UPLOAD_MAX_MEMORY_SIZE = 2097152   # 2MB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 2097152   # 2MB
else:
    DATA_UPLOAD_MAX_MEMORY_SIZE = 2097152    # 2 GB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 2097152 

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# ==================== CORS SETTINGS ====================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

if IS_CLOUD_DEPLOYMENT:
    if RENDER_EXTERNAL_HOSTNAME:
        CORS_ALLOWED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
    if HEROKU_APP_NAME:
        CORS_ALLOWED_ORIGINS.append(f"https://{HEROKU_APP_NAME}.herokuapp.com")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
    'x-sync-api-key',
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

# ==================== CACHE - LOCAL ONLY ====================
if not IS_CLOUD_DEPLOYMENT:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'TIMEOUT': 3600,
        }
    }

# ==================== CELERY - LOCAL ONLY ====================
if not IS_CLOUD_DEPLOYMENT:
    try:
        from kombu import Queue
    except ImportError:
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

# ==================== CLOUD SYNC CONFIGURATION ====================
if not IS_CLOUD_DEPLOYMENT:
    CLOUD_SYNC_URL = os.environ.get(
        'CLOUD_SYNC_URL',
        'https://your-app.herokuapp.com/api/sync/'
    ).rstrip('/') + '/'
    CLOUD_SYNC_API_KEY = os.environ.get('CLOUD_SYNC_API_KEY', None)

if IS_CLOUD_DEPLOYMENT:
    SYNC_API_KEY = os.environ.get('SYNC_API_KEY', None)

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