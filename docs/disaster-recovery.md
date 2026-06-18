# Disaster Recovery & Backup Policy

**Owner:** Platform Engineering  
**Last reviewed:** 2026-04-28  
**Review cadence:** Quarterly

---

## 1. Recovery Objectives

| Metric | Target | Justification |
|--------|--------|---------------|
| **RPO** (Recovery Point Objective) | **15 minutes** | Railway Postgres WAL-based Point-in-Time Recovery (PITR) streams continuously; worst-case data loss is the last unflushed WAL segment. |
| **RTO** (Recovery Time Objective) | **4 hours** | Includes incident detection (~15 min), triage (~30 min), database restore (~1–2 h), service verification (~1 h), DNS propagation (~30 min). |

---

## 2. Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────────┐
│  Cloudflare Pages    │     │  Railway (Backend)       │
│  ┌─────────────────┐ │     │  ┌───────────────────┐  │
│  │ viperai-app      │ │────▶│  │ healthvet-api      │  │
│  │ (app.viperai.io) │ │     │  │ (FastAPI + Gunicorn)│  │
│  └─────────────────┘ │     │  └───────────────────┘  │
│  ┌─────────────────┐ │     │  ┌───────────────────┐  │
│  │ viperai-marketing│ │     │  │ PostgreSQL 16      │  │
│  │ (viperai.io)     │ │     │  │ (PITR enabled)     │  │
│  └─────────────────┘ │     │  ┌───────────────────┐  │
└─────────────────────┘     │  │ Redis              │  │
                            │  └───────────────────┘  │
                            └─────────────────────────┘
```

| Component | Provider | Backup mechanism |
|-----------|----------|-----------------|
| **PostgreSQL** | Railway | Continuous WAL archiving + PITR. Railway retains 7 days of point-in-time snapshots (Pro plan: 14 days). |
| **Redis** | Railway | Ephemeral cache — no backup needed. Data is rebuilt from Postgres on restart. |
| **Frontend / Marketing** | Cloudflare Pages | Immutable deployments. Every deploy is versioned. Roll back via Cloudflare dashboard or `wrangler pages deploy` with a previous build. |
| **Backend code** | GitHub | Full git history. Redeploy any commit via Railway or manual trigger. |
| **File storage** | Cloudflare R2 | Cross-region replication enabled by default. Versioning recommended (see §5). |

---

## 3. Backup Procedures

### 3.1 PostgreSQL (Primary Data Store)

Railway Postgres provides automatic PITR:

- **Continuous backups:** WAL segments are streamed to Railway's backup storage in real time.
- **Retention:** 7 days (Hobby) / 14 days (Pro).
- **Granularity:** Restore to any second within the retention window.

**Manual backup (supplemental):**

```bash
# Export a logical dump for offline retention
# Run from a machine with network access to the Railway Postgres
pg_dump "$DATABASE_URL" --format=custom --compress=9 \
  --file="healthvet_backup_$(date +%Y%m%d_%H%M%S).dump"

# Upload to R2 or S3 for offsite storage
aws s3 cp healthvet_backup_*.dump s3://healthvet-backups/ \
  --endpoint-url "$CLOUDFLARE_R2_ENDPOINT_URL"
```

**Recommended schedule:** Weekly `pg_dump` to R2, retained for 90 days.

### 3.2 Cloudflare R2 (Document Storage)

- Enable **object versioning** on the R2 bucket via the Cloudflare dashboard.
- Deleted or overwritten files remain recoverable for the configured retention period.

### 3.3 Application Configuration

All environment variables are stored in Railway's service settings. Export them periodically:

```bash
# Via Railway CLI
railway variables --json > railway_env_backup_$(date +%Y%m%d).json
# Store encrypted in a password manager or secrets vault
```

---

## 4. Restore Procedures

### 4.1 PostgreSQL Point-in-Time Restore

1. **Go to Railway dashboard** → Project → Postgres service → **Backups** tab.
2. Select a restore point (date/time picker — any time within the retention window).
3. Railway creates a **new Postgres instance** with the restored data.
4. Update the `DATABASE_URL` environment variable on the `healthvet-api` service to point to the new instance.
5. Redeploy the backend service.
6. Verify data integrity (see §6 Restore Drill).

**Via Railway CLI:**

```bash
# List available backup points
railway service backups

# Restore to a specific point in time
railway service restore --timestamp "2026-04-28T12:00:00Z"
```

### 4.2 Frontend Rollback

```bash
# List recent deployments
CLOUDFLARE_API_TOKEN="<token>" npx wrangler pages deployments list \
  --project-name=viperai-app

# Roll back to a specific deployment
CLOUDFLARE_API_TOKEN="<token>" npx wrangler pages deployments rollback \
  --project-name=viperai-app --deployment-id=<id>
```

Or via Cloudflare dashboard → Pages → viperai-app → Deployments → click "Rollback" on any previous deployment.

### 4.3 Backend Rollback

```bash
# Via Railway dashboard: Deployments tab → click "Redeploy" on any previous deployment
# Or trigger a deploy from a specific git commit:
git push origin <known-good-commit>:devin/1774026028-initial-codebase --force-with-lease
```

### 4.4 Full Disaster Recovery (Total Loss)

If all Railway services are lost:

1. Provision new Railway project with Postgres, Redis, and API service.
2. Restore Postgres from the most recent `pg_dump` in R2/S3.
3. Set environment variables from the backed-up config.
4. Deploy backend from the latest git commit.
5. Deploy frontend/marketing via `wrangler pages deploy`.
6. Update DNS records if Railway domain changes.

**Estimated time:** 2–4 hours.

---

## 5. Monitoring & Alerting

| Signal | Tool | Alert threshold |
|--------|------|----------------|
| API health | Railway healthcheck (`/healthz`) | 3 consecutive failures (90s) |
| Database connectivity | Backend startup check | App fails to start |
| Deploy failures | GitHub Actions + Railway | Any deploy status != SUCCESS |
| Error rate | Application logs (Railway) | Manual review (TODO: add structured logging + alerting) |

**Recommended additions:**
- [ ] Set up UptimeRobot or Cloudflare Health Check for `https://healthvet-api-production.up.railway.app/healthz`
- [ ] Set up Cloudflare Health Check for `https://app.viperai.io`
- [ ] Configure Railway webhook notifications to Slack/email on deploy failures

---

## 6. Quarterly Restore Drill

### Purpose

Validate that backups are restorable and the RTO target is achievable. Enterprise security reviews require documented evidence of successful restore tests.

### Procedure

| Step | Action | Evidence to capture |
|------|--------|-------------------|
| 1 | Record drill start time | Timestamp |
| 2 | Create a test record in production DB (e.g., a dummy candidate with name `DR_TEST_<date>`) | Screenshot of record |
| 3 | Initiate PITR restore to a new Railway Postgres instance (target: 5 minutes before the test record) | Railway restore confirmation screenshot |
| 4 | Connect to restored instance and verify the test record does **not** exist (confirms PITR precision) | Query result screenshot |
| 5 | Verify row counts match production (within ~5 min of drift) | `SELECT COUNT(*) FROM candidates` on both instances |
| 6 | Point staging backend at restored DB and verify the application loads | Screenshot of staging app with restored data |
| 7 | Record drill end time and calculate actual RTO | Timestamp + elapsed time |
| 8 | Delete the restored Postgres instance (avoid cost) | Cleanup confirmation |
| 9 | Delete the test record from production | Cleanup confirmation |

### Evidence Template

```markdown
# DR Restore Drill — Q[N] [YYYY]

**Date:** YYYY-MM-DD
**Conducted by:** [Name]
**Drill type:** PostgreSQL PITR restore

## Timing
- Drill started: HH:MM UTC
- Restore initiated: HH:MM UTC
- Restore completed: HH:MM UTC
- Application verified: HH:MM UTC
- Drill ended: HH:MM UTC
- **Actual RTO: X hours Y minutes** (target: 4 hours)

## Results
- [ ] PITR restore completed successfully
- [ ] Data integrity verified (row counts match within tolerance)
- [ ] Application functional on restored data
- [ ] Test record absent in restored DB (PITR precision confirmed)
- [ ] RTO target met

## Issues encountered
[None / describe any issues]

## Attachments
- [ ] Railway restore confirmation screenshot
- [ ] Row count comparison
- [ ] Application screenshot on restored data

## Sign-off
- Conducted by: _________________ Date: _________
- Reviewed by:  _________________ Date: _________
```

### Schedule

| Quarter | Target date | Status |
|---------|-------------|--------|
| Q2 2026 | 2026-06-15 | Pending |
| Q3 2026 | 2026-09-15 | Pending |
| Q4 2026 | 2026-12-15 | Pending |
| Q1 2027 | 2027-03-15 | Pending |

---

## 7. Runbook: Incident Response

### Severity Levels

| Level | Definition | Response time | Example |
|-------|-----------|---------------|---------|
| **P1** | Service down, all users affected | 15 min | Database unreachable, API 500s |
| **P2** | Degraded service, some users affected | 1 hour | Slow queries, partial feature failure |
| **P3** | Minor issue, workaround available | 4 hours | UI glitch, non-critical API error |

### P1 Response Checklist

1. **Acknowledge** — Note the time, check Railway dashboard for service status.
2. **Diagnose** — Check Railway logs (`railway logs`), Cloudflare analytics, GitHub Actions.
3. **Mitigate** — If backend is down: redeploy last known good version. If DB is corrupted: initiate PITR restore.
4. **Communicate** — Notify affected users/agencies via email.
5. **Resolve** — Fix root cause, deploy fix, verify.
6. **Post-mortem** — Document within 48 hours: timeline, root cause, remediation, prevention.

---

## 8. Document History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-28 | Devin (automated) | Initial DR policy created |
