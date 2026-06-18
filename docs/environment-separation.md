# Environment Separation Guide

**Last updated:** 2026-04-28

---

## Overview

HealthVet AI uses a two-environment architecture to protect production data:

| Environment | Purpose | Backend (Railway) | Frontend (Cloudflare Pages) | Database |
|-------------|---------|-------------------|----------------------------|----------|
| **Production** | Live users | `healthvet-api` → `healthvet-api-production.up.railway.app` | `app.viperai.io` / `viperai.io` | Railway Postgres (production env) |
| **Staging** | PR review & QA | `healthvet-api` → staging Railway env | `pr-{N}.viperai-app.pages.dev` | Railway Postgres (staging env) |

---

## Current Setup

### Railway

- **Project:** `healthvet-backend` (ID: `3be5927f-a073-4eab-bf05-ed8f12ef8946`)
- **Production environment:** auto-deploys from `devin/1774026028-initial-codebase` branch
- **Staging environment:** created, deploy trigger needs manual configuration (see §3)
- **Services:** healthvet-api (FastAPI), PostgreSQL 16, Redis

### Cloudflare Pages

- **Frontend** (`viperai-app`): Deployed via GitHub Actions on push to default branch. PR preview deployments at `pr-{N}.viperai-app.pages.dev`.
- **Marketing** (`viperai-marketing`): Deployed via GitHub Actions on push to default branch. PR preview deployments at `pr-{N}.viperai-marketing.pages.dev`.

### GitHub Actions

Two workflows:
- **`ci.yml`** — Lint, test, build (runs on push + PRs)
- **`deploy.yml`** — Cloudflare Pages deploy (production on push, preview on PRs)

---

## Deployment Flow

```
Developer creates PR
        │
        ├──▶ GitHub Actions CI: lint + test + build
        │
        ├──▶ GitHub Actions Deploy: Cloudflare Pages preview
        │    (frontend: pr-N.viperai-app.pages.dev)
        │    (marketing: pr-N.viperai-marketing.pages.dev)
        │
        └──▶ Railway staging: auto-deploy backend (once configured)

Review PR + test on preview URLs
        │
        ▼
Merge to default branch
        │
        ├──▶ GitHub Actions Deploy: Cloudflare Pages production
        │    (app.viperai.io, viperai.io)
        │
        └──▶ Railway production: auto-deploy backend
             (healthvet-api-production.up.railway.app)
```

---

## 3. Setup Instructions

### 3.1 GitHub Secrets (Required for CI/CD)

Add these secrets in GitHub → Settings → Secrets and variables → Actions:

| Secret name | Value | Where to find it |
|-------------|-------|-------------------|
| `CLOUDFLARE_PAGES_API_TOKEN` | Cloudflare API token with Pages permissions | [Cloudflare dashboard → API Tokens](https://dash.cloudflare.com/profile/api-tokens) |
| `CLOUDFLARE_ACCOUNT_ID` | `afad1cf2d6fb88085f06d97e4b03e944` | Cloudflare dashboard → any domain → Overview → right sidebar |

### 3.2 Railway Staging Deploy Trigger

The staging environment has been created but needs a deploy trigger configured:

1. Go to [Railway dashboard](https://railway.com/project/3be5927f-a073-4eab-bf05-ed8f12ef8946)
2. Switch to the **staging** environment (environment switcher at top)
3. Click on the **healthvet-api** service
4. Go to **Settings** → **Build & Deploy** → **Source**
5. Set the branch to `staging`
6. Save

Now when you push to the `staging` branch, Railway will auto-deploy the staging backend.

### 3.3 Staging Workflow

To test a PR in the staging environment before merging:

```bash
# From your feature branch
git push origin HEAD:staging
# This triggers Railway staging deploy
# Frontend preview is automatic via GitHub Actions on the PR
```

---

## 4. Environment Variables

Each Railway environment has its own set of environment variables. The staging environment should mirror production except:

| Variable | Production | Staging |
|----------|-----------|---------|
| `DATABASE_URL` | (auto-set by Railway Postgres) | (auto-set by Railway Postgres — separate instance) |
| `REDIS_URL` | (auto-set by Railway Redis) | (auto-set by Railway Redis — separate instance) |
| `ALLOWED_ORIGINS` | `https://app.viperai.io` | `https://pr-*.viperai-app.pages.dev` |
| `JWT_SECRET` | (production secret) | (different staging secret) |

All other variables (OPENAI_API_KEY, SENDGRID_API_KEY, etc.) can be shared or use test/sandbox equivalents.

---

## 5. Branch Strategy

```
devin/1774026028-initial-codebase  ← default branch (production)
        │
        ├── staging                 ← staging branch (Railway staging)
        │
        └── feature/*              ← feature branches (PRs)
```

**Future migration:** When ready, rename the default branch to `main`:

```bash
# On GitHub: Settings → Default branch → change to main
# Update Railway trigger: production → main
# Update deploy.yml: push branches → main
# Update ci.yml: push/PR branches → main
```

This is tracked as item #6 and can be done when convenient.
