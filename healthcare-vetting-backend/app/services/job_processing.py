"""
3.5 Background Job Processing (Production)

Enhanced Celery configuration, job monitoring dashboard,
dead letter queue for permanently failed jobs,
proper task timeout handling, and job status tracking.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# Job status constants
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_DEAD = "dead_letter"
STATUS_RETRYING = "retrying"
STATUS_TIMED_OUT = "timed_out"

# Default timeout per task type (seconds)
TASK_TIMEOUTS = {
    "run_compliance_evaluation": 120,
    "run_all_monitoring_checks": 300,
    "run_fraud_detection_scan": 600,
    "deliver_webhook": 30,
    "apply_retention_policies": 300,
    "send_payment_reminders_task": 120,
    "run_expiry_warning_checks": 300,
    "process_pending_retries": 300,
    "default": 180,
}

MAX_JOB_RETRIES = 3


class JobProcessingService:
    """Production-grade background job processing with monitoring."""

    @staticmethod
    def submit_job(task_name: str, args: tuple = None, kwargs: dict = None,
                   priority: int = 5, scheduled_at: str = None) -> dict:
        """Submit a job for background processing with tracking."""
        job_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        timeout = TASK_TIMEOUTS.get(task_name.split(".")[-1], TASK_TIMEOUTS["default"])

        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs
                   (id, task_name, args, kwargs, status, priority, timeout_seconds,
                    max_retries, attempt, scheduled_at, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)""",
                (job_id, task_name, json.dumps(args or []),
                 json.dumps(kwargs or {}), STATUS_QUEUED, priority,
                 timeout, MAX_JOB_RETRIES, scheduled_at, now),
            )

        # Try Celery first, fall back to synchronous
        from app.services.celery_app import is_celery_available, dispatch_task

        if is_celery_available():
            try:
                result = dispatch_task(task_name, *(args or ()), **(kwargs or {}))
                celery_task_id = result.get("task_id")
                with get_db() as db:
                    db.execute(
                        "UPDATE background_jobs SET celery_task_id=%s, status=%s WHERE id=%s",
                        (celery_task_id, STATUS_RUNNING, job_id),
                    )
                return {"job_id": job_id, "celery_task_id": celery_task_id, "status": STATUS_RUNNING}
            except Exception as e:
                logger.warning("Celery dispatch failed, running sync: %s", e)

        # Synchronous fallback with timeout tracking
        _run_job_sync(job_id, task_name, args or (), kwargs or {}, timeout)
        return {"job_id": job_id, "status": "dispatched_sync"}

    @staticmethod
    def get_job_status(job_id: str) -> dict:
        """Get the status of a specific job."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM background_jobs WHERE id=%s", (job_id,)
            )
            row = db.fetchone()
            if not row:
                return None
            r = dict(row)
            for field in ["args", "kwargs", "result", "error"]:
                if r.get(field):
                    try:
                        r[field] = json.loads(r[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return r

    @staticmethod
    def get_job_dashboard(status: str = None, task_name: str = None,
                          limit: int = 100, offset: int = 0) -> dict:
        """Get job monitoring dashboard with filters."""
        conditions = []
        params = []

        if status:
            conditions.append("status=%s")
            params.append(status)
        if task_name:
            conditions.append("task_name LIKE %s")
            params.append(f"%{task_name}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db() as db:
            total = db.execute(
                f"SELECT COUNT(*) AS cnt FROM background_jobs {where}",
                tuple(params),
            ).fetchone()["cnt"]

            rows = db.execute(
                f"""SELECT id, task_name, status, priority, attempt, max_retries,
                           timeout_seconds, celery_task_id, started_at, completed_at,
                           error, created_at
                    FROM background_jobs {where}
                    ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                tuple(params) + (limit, offset),
            )
            rows = db.fetchall()

            # Stats
            stats = {}
            for s in [STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED,
                      STATUS_FAILED, STATUS_DEAD, STATUS_TIMED_OUT]:
                count = db.execute(
                    "SELECT COUNT(*) AS cnt FROM background_jobs WHERE status=%s", (s,)
                ).fetchone()["cnt"]
                stats[s] = count

            return {
                "total": total,
                "jobs": [dict(r) for r in rows],
                "stats": stats,
                "limit": limit,
                "offset": offset,
            }

    @staticmethod
    def get_dead_letter_queue(limit: int = 50) -> dict:
        """Get jobs in the dead letter queue (permanently failed)."""
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM background_jobs
                   WHERE status=%s
                   ORDER BY completed_at DESC LIMIT %s""",
                (STATUS_DEAD, limit),
            )
            rows = db.fetchall()

            items = []
            for row in rows:
                r = dict(row)
                for field in ["args", "kwargs", "result", "error"]:
                    if r.get(field):
                        try:
                            r[field] = json.loads(r[field])
                        except (json.JSONDecodeError, TypeError):
                            pass
                items.append(r)

            return {"total": len(items), "jobs": items}

    @staticmethod
    def retry_dead_letter(job_id: str) -> dict:
        """Retry a job from the dead letter queue."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM background_jobs WHERE id=%s AND status=%s",
                (job_id, STATUS_DEAD),
            )
            row = db.fetchone()
            if not row:
                return {"status": "not_found"}

            r = dict(row)
            args = json.loads(r["args"]) if r["args"] else []
            kwargs = json.loads(r["kwargs"]) if r["kwargs"] else {}

            # Reset the job
            db.execute(
                """UPDATE background_jobs SET
                   status=%s, attempt=0, error=NULL, started_at=NULL,
                   completed_at=NULL, result=NULL
                   WHERE id=%s""",
                (STATUS_QUEUED, job_id),
            )

        # Re-dispatch
        return JobProcessingService.submit_job(
            r["task_name"],
            tuple(args) if isinstance(args, list) else args,
            kwargs,
        )

    @staticmethod
    def cancel_job(job_id: str) -> dict:
        """Cancel a queued or running job."""
        with get_db() as db:
            row = db.execute(
                "SELECT status, celery_task_id FROM background_jobs WHERE id=%s",
                (job_id,),
            )
            row = db.fetchone()
            if not row:
                return {"status": "not_found"}

            r = dict(row)
            if r["status"] in (STATUS_COMPLETED, STATUS_DEAD):
                return {"status": "cannot_cancel", "current_status": r["status"]}

            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "UPDATE background_jobs SET status='cancelled', completed_at=%s WHERE id=%s",
                (now, job_id),
            )

            # Try to revoke Celery task
            if r.get("celery_task_id"):
                try:
                    from app.services.celery_app import get_celery_app
                    app = get_celery_app()
                    if app:
                        app.control.revoke(r["celery_task_id"], terminate=True)
                except Exception:
                    pass

            return {"status": "cancelled", "job_id": job_id}

    @staticmethod
    def cleanup_old_jobs(days: int = 30) -> dict:
        """Clean up completed jobs older than N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with get_db() as db:
            result = db.execute(
                "DELETE FROM background_jobs WHERE status IN (%s, 'cancelled') AND completed_at < %s",
                (STATUS_COMPLETED, cutoff),
            )
            return {"deleted": result.rowcount}

    @staticmethod
    def get_worker_status() -> dict:
        """Get Celery worker status (if available)."""
        from app.services.celery_app import is_celery_available, get_celery_app

        if not is_celery_available():
            return {
                "celery_available": False,
                "mode": "synchronous_fallback",
                "workers": [],
            }

        try:
            app = get_celery_app()
            inspector = app.control.inspect()
            active = inspector.active() or {}
            stats = inspector.stats() or {}
            registered = inspector.registered() or {}

            workers = []
            for worker_name, worker_stats in stats.items():
                workers.append({
                    "name": worker_name,
                    "active_tasks": len(active.get(worker_name, [])),
                    "registered_tasks": len(registered.get(worker_name, [])),
                    "pool": worker_stats.get("pool", {}).get("implementation", "unknown"),
                    "concurrency": worker_stats.get("pool", {}).get("max-concurrency", 0),
                    "uptime": worker_stats.get("uptime", 0),
                })

            return {
                "celery_available": True,
                "mode": "celery",
                "workers": workers,
                "total_active": sum(w["active_tasks"] for w in workers),
            }
        except Exception as e:
            return {
                "celery_available": True,
                "mode": "celery_error",
                "error": str(e),
                "workers": [],
            }


def _run_job_sync(job_id: str, task_name: str, args: tuple,
                  kwargs: dict, timeout: int):
    """Run a job synchronously in a background thread with timeout handling."""

    def _execute():
        from app.services import tasks as task_module

        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE background_jobs SET status=%s, started_at=%s WHERE id=%s",
                (STATUS_RUNNING, now, job_id),
            )

        func_name = task_name.rsplit(".", 1)[-1]
        func = getattr(task_module, func_name, None)
        if not func:
            _mark_job_failed(job_id, f"Task function {func_name} not found")
            return

        try:
            result = func(*args, **kwargs)
            completed = datetime.now(timezone.utc).isoformat()
            with get_db() as db:
                db.execute(
                    """UPDATE background_jobs SET
                       status=%s, result=%s, completed_at=%s, attempt=attempt+1
                       WHERE id=%s""",
                    (STATUS_COMPLETED, json.dumps(result, default=str),
                     completed, job_id),
                )
        except Exception as e:
            error_msg = str(e)[:1000]
            _handle_job_failure(job_id, task_name, args, kwargs, error_msg)

    thread = threading.Thread(target=_execute, daemon=True)
    thread.start()

    # Timeout monitoring in another thread
    def _monitor_timeout():
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning("Job %s timed out after %ds", job_id, timeout)
            _mark_job_failed(job_id, f"Timed out after {timeout}s", STATUS_TIMED_OUT)

    monitor = threading.Thread(target=_monitor_timeout, daemon=True)
    monitor.start()


def _mark_job_failed(job_id: str, error: str, status: str = STATUS_FAILED):
    """Mark a job as failed."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "UPDATE background_jobs SET status=%s, error=%s, completed_at=%s WHERE id=%s",
            (status, error, now, job_id),
        )


def _handle_job_failure(job_id: str, task_name: str, args: tuple,
                        kwargs: dict, error: str):
    """Handle a job failure with retry logic."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        row = db.execute(
            "SELECT attempt, max_retries FROM background_jobs WHERE id=%s",
            (job_id,),
        )
        row = db.fetchone()
        if not row:
            return

        r = dict(row)
        attempt = (r["attempt"] or 0) + 1
        max_retries = r["max_retries"] or MAX_JOB_RETRIES

        if attempt >= max_retries:
            # Move to dead letter queue
            db.execute(
                """UPDATE background_jobs SET
                   status=%s, error=%s, completed_at=%s, attempt=%s
                   WHERE id=%s""",
                (STATUS_DEAD, error, now, attempt, job_id),
            )
            logger.warning("Job %s moved to dead letter queue after %d attempts", job_id, attempt)
        else:
            # Schedule retry with exponential backoff
            delay = min(60 * (2 ** attempt), 3600)  # Max 1 hour
            retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            db.execute(
                """UPDATE background_jobs SET
                   status=%s, error=%s, attempt=%s, scheduled_at=%s
                   WHERE id=%s""",
                (STATUS_RETRYING, error, attempt, retry_at, job_id),
            )

            # Schedule retry in background
            def _retry():
                time.sleep(delay)
                try:
                    from app.services.celery_app import dispatch_task
                    dispatch_task(task_name, *args, **kwargs)
                    with get_db() as inner_db:
                        inner_db.execute(
                            "UPDATE background_jobs SET status=%s WHERE id=%s",
                            (STATUS_RUNNING, job_id),
                        )
                except Exception as e:
                    _mark_job_failed(job_id, str(e)[:1000])

            threading.Thread(target=_retry, daemon=True).start()
