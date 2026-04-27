"""
3.5 Background Job Processing API Routes

Job monitoring dashboard, dead letter queue management,
worker status, job submission, and cleanup.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.utils.auth import get_current_admin

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])


@router.get("/dashboard")
async def get_job_dashboard(status: str = None, task_name: str = None,
                             limit: int = 100, offset: int = 0,
                             user=Depends(get_current_admin)):
    """Get job monitoring dashboard (admin only)."""
    from app.services.job_processing import JobProcessingService
    return JobProcessingService.get_job_dashboard(status, task_name, limit, offset)


@router.get("/status/{job_id}")
async def get_job_status(job_id: str, user=Depends(get_current_admin)):
    """Get status of a specific job (admin only)."""
    from app.services.job_processing import JobProcessingService
    result = JobProcessingService.get_job_status(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.get("/dead-letter")
async def get_dead_letter_queue(limit: int = 50, user=Depends(get_current_admin)):
    """Get jobs in the dead letter queue (admin only)."""
    from app.services.job_processing import JobProcessingService
    return JobProcessingService.get_dead_letter_queue(limit)


@router.post("/dead-letter/{job_id}/retry")
async def retry_dead_letter(job_id: str, user=Depends(get_current_admin)):
    """Retry a job from the dead letter queue (admin only)."""
    from app.services.job_processing import JobProcessingService
    result = JobProcessingService.retry_dead_letter(job_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found in dead letter queue")
    return result


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str, user=Depends(get_current_admin)):
    """Cancel a queued or running job (admin only)."""
    from app.services.job_processing import JobProcessingService
    result = JobProcessingService.cancel_job(job_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.get("/workers")
async def get_worker_status(user=Depends(get_current_admin)):
    """Get Celery worker status (admin only)."""
    from app.services.job_processing import JobProcessingService
    return JobProcessingService.get_worker_status()


@router.post("/cleanup")
async def cleanup_old_jobs(days: int = 30, user=Depends(get_current_admin)):
    """Clean up completed jobs older than N days (admin only)."""
    from app.services.job_processing import JobProcessingService
    return JobProcessingService.cleanup_old_jobs(days)


@router.post("/submit")
async def submit_job(data: dict, user=Depends(get_current_admin)):
    """Manually submit a background job (admin only)."""
    from app.services.job_processing import JobProcessingService
    task_name = data.get("task_name")
    if not task_name:
        raise HTTPException(status_code=400, detail="task_name is required")
    args = tuple(data.get("args", []))
    kwargs = data.get("kwargs", {})
    priority = data.get("priority", 5)
    return JobProcessingService.submit_job(task_name, args, kwargs, priority)
