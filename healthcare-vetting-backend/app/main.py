import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.database import init_db, migrate_db
from app.routes import auth, candidates, checks, compliance, webhooks, agencies, admin, reports
from app.routes import admin_extended
from app.routes import submissions
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler

app = FastAPI(
    title="HealthVet AI - Healthcare Vetting Engine",
    description="AI-powered compliance intelligence for healthcare staffing",
    version="1.0.0",
)

# ── Security Headers Middleware ──────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Audit / Request-ID Middleware ────────────────────────────────────────────
app.add_middleware(AuditMiddleware)

# ── Rate Limiting ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── CORS — environment-configurable, locked down for production ──────────────
_default_origins = "http://localhost:5173,http://localhost:3000"
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Auth-Token"],
    max_age=600,
)

# Include all routers
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(checks.router)
app.include_router(compliance.router)
app.include_router(webhooks.router)
app.include_router(agencies.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(admin_extended.router)
app.include_router(submissions.router)


@app.on_event("startup")
async def startup():
    init_db()
    migrate_db()
    # Start the background scheduler for monitoring tasks
    from app.services.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()


@app.get("/healthz")
async def healthz():
    """Health check endpoint for load balancers and container orchestration."""
    from app.database import get_db
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "degraded"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }


@app.get("/api/info")
async def api_info():
    return {
        "name": "HealthVet AI",
        "version": "1.0.0",
        "description": "AI-powered compliance intelligence for healthcare staffing",
        "features": [
            "Automated Identity Verification (Onfido/Yoti/Trulioo)",
            "Right to Work Automation (UK Home Office)",
            "DBS Check Submission (uCheck/CareCheck)",
            "AI CV & Document Validation",
            "Automated Reference Collection",
            "Rule-Based Compliance Engine",
            "Continuous Monitoring & Alerts",
            "Webhook Architecture",
            "CQC-Ready Audit Logs",
        ],
    }


# Serve frontend static files
STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Serve the React SPA for any non-API route."""
        # Never intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        # Try to serve a specific static file first
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for SPA routing
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
