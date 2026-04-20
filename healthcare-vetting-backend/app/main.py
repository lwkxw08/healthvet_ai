import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

# ── Sentry SDK — error monitoring ────────────────────────────────────────────
_SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
        )
        logging.getLogger(__name__).info("Sentry SDK initialised")
    except ImportError:
        logging.getLogger(__name__).warning("sentry-sdk not installed — error monitoring disabled")

from app.database import init_db, migrate_db
from app.routes import auth, candidates, checks, compliance, webhooks, agencies, admin, reports
from app.routes import admin_extended
from app.routes import submissions
from app.routes import gdpr
from app.routes import integrations
from app.routes import bulk_import
from app.routes import shift_readiness
from app.routes import sub_accounts
from app.routes import notifications
from app.routes import benchmarking
from app.routes import industry_templates
from app.routes import lead_generation
from app.routes import subscription_plans
from app.routes import email_templates
from app.routes import email_rules
from app.routes import email_config
from app.routes import verification_portal
from app.routes import candidate_portal
from app.routes import analytics
from app.routes import webhook_management
from app.routes import audit_trail
from app.routes import job_monitor
from app.routes import payment_providers
from app.routes import ai_insights
from app.routes import documents
from app.routes import trustid
from app.routes import sms
from app.routes import training_catalogue
from app.routes import websocket as ws_routes
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.agency_scope import AgencyScopeMiddleware
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler

app = FastAPI(
    title="Viper AI - Vetting Intelligence Platform for Enterprise Risk",
    description="AI-powered compliance intelligence for healthcare staffing",
    version="1.0.0",
)

# ── Security Headers Middleware ──────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Agency Scope / Multi-Tenancy Middleware ──────────────────────────────────
app.add_middleware(AgencyScopeMiddleware)

# ── Audit / Request-ID Middleware ────────────────────────────────────────────
app.add_middleware(AuditMiddleware)

# ── Rate Limiting ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── CORS — environment-configurable, locked down for production ──────────────
# In production set ALLOWED_ORIGINS to your domain(s), e.g. "https://app.viperai.io"
_default_origins = "http://localhost:5173,http://localhost:3000"
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins.split(",")

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
app.include_router(gdpr.router)
app.include_router(integrations.router)
app.include_router(bulk_import.router)
app.include_router(shift_readiness.router)
app.include_router(sub_accounts.router)
app.include_router(notifications.router)
app.include_router(benchmarking.router)
app.include_router(industry_templates.router)
app.include_router(industry_templates.agency_router)
app.include_router(lead_generation.router)
app.include_router(subscription_plans.router)
app.include_router(email_templates.router)
app.include_router(email_rules.router)
app.include_router(email_config.router)
app.include_router(verification_portal.router)
app.include_router(candidate_portal.router)
app.include_router(analytics.router)
app.include_router(webhook_management.router)
app.include_router(audit_trail.router)
app.include_router(job_monitor.router)
app.include_router(payment_providers.router)
app.include_router(ai_insights.router)
app.include_router(documents.router)
app.include_router(trustid.router)
app.include_router(sms.router)
app.include_router(training_catalogue.router)
app.include_router(ws_routes.router)


@app.on_event("startup")
async def startup():
    import traceback
    _log = logging.getLogger("startup")
    try:
        _log.info("Starting init_db...")
        init_db()
        _log.info("init_db complete. Starting migrate_db...")
        migrate_db()
        _log.info("migrate_db complete.")
    except Exception as e:
        _log.error(f"Database init/migration failed: {e}\n{traceback.format_exc()}")
    try:
        from app.services.email_templates import EmailTemplateService
        EmailTemplateService.seed_defaults()
        from app.services.email_rules import EmailRulesService
        EmailRulesService.seed_defaults()
    except Exception as e:
        _log.error(f"Email template seeding failed: {e}")
    try:
        from app.routes.lead_generation import recover_stale_scrape_jobs
        recover_stale_scrape_jobs()
    except Exception as e:
        _log.error(f"Scrape job recovery failed: {e}")
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        _log.error(f"Scheduler start failed: {e}")
    try:
        from app.routes.api_versioning import register_v1_routes
        register_v1_routes(app)
    except Exception as e:
        _log.error(f"API versioning failed: {e}")


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
        "name": "Viper AI",
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
_ASSETS_DIR = STATIC_DIR / "assets"

if _ASSETS_DIR.exists():
    # Serve static assets (JS, CSS, images) — only if the build was bundled
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="static-assets")

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
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
        return FileResponse(str(STATIC_DIR / "index.html"))
