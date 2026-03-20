import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, migrate_db
from app.routes import auth, candidates, checks, compliance, webhooks, agencies, admin

app = FastAPI(
    title="HealthVet AI - Healthcare Vetting Engine",
    description="AI-powered compliance intelligence for healthcare staffing",
    version="1.0.0",
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include all routers
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(checks.router)
app.include_router(compliance.router)
app.include_router(webhooks.router)
app.include_router(agencies.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup():
    init_db()
    migrate_db()


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


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
        # Try to serve a specific static file first
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for SPA routing
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
