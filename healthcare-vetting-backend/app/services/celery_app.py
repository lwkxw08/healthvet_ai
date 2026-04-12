"""
Celery application configuration.

Supports Redis broker (production) or in-process fallback (dev without Redis).
Configure via environment variables:
  CELERY_BROKER_URL=redis://localhost:6379/0
  CELERY_RESULT_BACKEND=redis://localhost:6379/1
"""
import os
import logging

logger = logging.getLogger(__name__)

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

_celery_app = None
_celery_available = False


def get_celery_app():
    """Get or create the Celery application instance."""
    global _celery_app, _celery_available
    if _celery_app is not None:
        return _celery_app

    try:
        from celery import Celery

        _celery_app = Celery(
            "viperai",
            broker=BROKER_URL,
            backend=RESULT_BACKEND,
        )

        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
            # Retry policy for broker connection
            broker_connection_retry_on_startup=True,
            broker_connection_max_retries=5,
            # Task result expiry (24 hours)
            result_expires=86400,
            # Rate limits
            task_default_rate_limit="100/m",
            # Retry configuration
            task_default_retry_delay=60,
            task_max_retries=3,
        )

        # Auto-discover tasks from the tasks module
        _celery_app.autodiscover_tasks(["app.services.tasks"])

        _celery_available = True
        logger.info("Celery configured with broker: %s", BROKER_URL)

    except ImportError:
        logger.warning("Celery not installed — background tasks will run synchronously")
        _celery_app = None
        _celery_available = False
    except Exception as e:
        logger.warning("Celery setup failed (%s) — falling back to synchronous execution", e)
        _celery_app = None
        _celery_available = False

    return _celery_app


def is_celery_available() -> bool:
    """Check if Celery is available and configured."""
    get_celery_app()
    return _celery_available


def dispatch_task(task_name: str, *args, **kwargs):
    """Dispatch a task to Celery if available, otherwise run synchronously.

    This is the main entry point for scheduling background work. It
    transparently falls back to direct function execution when Celery
    or Redis is not available (e.g. local development).
    """
    from app.services import tasks as task_module

    if is_celery_available():
        try:
            app = get_celery_app()
            result = app.send_task(task_name, args=args, kwargs=kwargs)
            logger.info("Task %s dispatched to Celery (id=%s)", task_name, result.id)
            return {"task_id": result.id, "status": "queued"}
        except Exception as e:
            logger.warning("Celery dispatch failed (%s) — running synchronously", e)

    # Fallback: run synchronously
    func_name = task_name.rsplit(".", 1)[-1]
    func = getattr(task_module, func_name, None)
    if func:
        try:
            result = func(*args, **kwargs)
            return {"task_id": None, "status": "completed_sync", "result": result}
        except Exception as e:
            logger.error("Synchronous task %s failed: %s", task_name, e)
            return {"task_id": None, "status": "failed", "error": str(e)}
    else:
        logger.error("Task function %s not found in tasks module", func_name)
        return {"task_id": None, "status": "not_found"}
