# trapick/__init__.py
"""
Trapick Django App Initialization

Conditionally imports Celery based on deployment environment.
"""
import os

DEPLOYMENT_ENV = os.environ.get('DEPLOYMENT_ENV', 'local')

if DEPLOYMENT_ENV == 'local':
    try:
        from .celery import app as celery_app
        __all__ = ('celery_app',)
    except ImportError:
        __all__ = ()
else:
    # Cloud mode: Skip Celery
    __all__ = ()