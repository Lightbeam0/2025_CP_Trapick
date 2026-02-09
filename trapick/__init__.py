# trapick/__init__.py
"""
Trapick Django App Initialization

Conditionally imports Celery based on deployment environment.
- LOCAL: Imports Celery for video processing
- CLOUD: Skips Celery (not needed for dashboard)
"""
import os

# Detect deployment environment
DEPLOYMENT_ENV = os.environ.get('DEPLOYMENT_ENV', 'local')

if DEPLOYMENT_ENV == 'local':
    # Local mode: Import Celery for background tasks
    try:
        from .celery import app as celery_app
        __all__ = ('celery_app',)
    except ImportError:
        # Celery not installed (shouldn't happen in local, but be safe)
        __all__ = ()
else:
    # Cloud mode: Skip Celery entirely
    __all__ = ()