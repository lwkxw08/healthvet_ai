# Viper AI (healthvet_ai) — Project Skill File

## Overview
Healthcare compliance vetting platform. Agencies submit candidates, the platform runs automated checks (identity, DBS, right-to-work, references, training) and produces compliance scores.

## Repository Structure
```
healthvet_ai/
├── healthcare-vetting-backend/     # FastAPI Python 3.11 backend
│   ├── app/main.py                 # Entry point
│   ├── app/database.py             # PostgreSQL connection
│   ├── app/middleware/             # CSRF, audit, API versioning
│   ├── app/routes/                 # ~30 route modules
│   ├── app/services/              # Business logic
│   └── tests/                     # pytest (~126 tests)
├── healthcare-vetting-frontend/    # React + TypeScript + Vite
│   └── src/pages/                 # Page components
├── healthcare-vetting-marketing/   # Static HTML marketing site
└── .github/workflows/             # CI (ci.yml) and deploy (deploy.yml)
```

## Setup & Run

### Backend
```bash
cd healthcare-vetting-backend
pip install -r requirements.txt

# Local dev server
DATABASE_URL=postgresql://test:test@localhost:5432/healthvet_test \
JWT_SECRET=test-secret \
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd healthcare-vetting-frontend
npm install
npm run dev
```

### Marketing Site
```bash
cd healthcare-vetting-marketing
# Static files — open index.html or serve with any HTTP server
npx serve .
```

## Lint & Type Check

### Backend (ruff)
```bash
cd healthcare-vetting-backend
ruff check .
```

### Frontend (TypeScript + ESLint)
```bash
cd healthcare-vetting-frontend
npx tsc --noEmit
npx eslint src/
```

## Testing
```bash
cd healthcare-vetting-backend

# Start PostgreSQL (if not running)
# Tests expect: postgresql://test:test@localhost:5432/healthvet_test

DATABASE_URL=postgresql://test:test@localhost:5432/healthvet_test \
JWT_SECRET=ci-test-secret \
pytest tests/ -v
```

Test files cover: auth, billing integration, monitoring lifecycle, scheduler jobs, API contracts, compliance, training, CSRF.

## CI Pipeline (8 jobs)
1. `backend-lint` — ruff check
2. `backend-test` — pytest with PostgreSQL 16 service container
3. `frontend-lint` — ESLint
4. `frontend-typecheck` — tsc --noEmit
5. `frontend-build` — Vite production build
6. `marketing-build` — Marketing site build
7. `deploy-backend` — Railway deployment
8. `deploy-frontend` — Cloudflare Pages deployment

## Deployment
- **Backend:** Railway (auto-deploys from CI on push to main/devin branches)
- **Frontend:** Cloudflare Pages
- **Marketing:** Cloudflare Pages (separate project)

## Key Architecture Patterns

### CSRF Middleware
Public endpoints must be added to `_EXEMPT_PATHS` in `app/middleware/csrf.py`:
```python
_EXEMPT_PATHS = ("/api/auth/", "/api/verify/", "/api/webhooks/", "/healthz")
```

### Notifications
All notifications must write to `in_app_notifications` table. Do NOT use a `notifications` table (doesn't exist in schema).

### Email Templates
Defined in `app/services/email_templates.py` as HTML strings. Email sending via `app/services/email_service.py` (SendGrid).

### Compliance Engine
`app/services/compliance_engine.py` recalculates compliance scores. Detects status transitions (e.g., to "compliant") and triggers email notifications.

### Trigger Engine
`app/services/trigger_engine.py` orchestrates the automated vetting flow. OpenAI CV analysis runs automatically here.

### AI Integration
- CV Gap Analysis: `app/services/ai_cv_analysis.py` (GPT-4o-mini)
- Reference Sentiment: `app/services/ai_reference_sentiment.py` (GPT-4o-mini)
- API key loaded via `get_openai_api_key()` — checks `admin_settings` DB table, then `OPENAI_API_KEY` env var
- Both silently fall back to rule-based analysis if no key configured

### Suppressed Fields
Some verification form fields are hidden pre-launch but retained in code. Marked with comment: `SUPPRESSED: hidden pre-launch, reinstate post go-live if needed`

### Date Formatting
All dates display as dd-mm-yyyy hh:mm (UK format). Use shared `fmtDate()` utility in frontend.

### External Check Providers
Identity, DBS, right-to-work checks are currently **simulated** with `random.random()`. Real provider integrations not yet connected.

## Conventions
- Branch naming: `devin/<timestamp>-<description>`
- PR #10 is the long-running enterprise readiness PR
- Working branch: `devin/1774026028-initial-codebase`
- Domain: `viperai.io`
- Contact email: `enquiries@viperai.io`
- All user-facing dates: dd-mm-yyyy hh:mm
- UK legal jurisdiction (GDPR, ICO)
