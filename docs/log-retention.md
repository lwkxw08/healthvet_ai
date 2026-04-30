# Log Retention & Forwarding

## Overview

Viper AI uses structured JSON logging to support healthcare audit compliance.
All application logs are emitted as JSON to stdout and should be forwarded to a
log aggregation service with **minimum 1-year retention** for CQC / NHS audit
requirements.

## Log Format

Every log line is a JSON object:

```json
{
  "timestamp": "2025-01-15T10:30:45.123456+00:00",
  "level": "INFO",
  "logger": "viperai.http",
  "message": "POST /api/auth/candidates/register 201 142ms",
  "service": "viperai-api",
  "environment": "production",
  "request_id": "a1b2c3d4-...",
  "method": "POST",
  "path": "/api/auth/candidates/register",
  "status_code": 201,
  "duration_ms": 142.3,
  "ip": "203.0.113.42",
  "http": {
    "method": "POST",
    "url": "https://api.viperai.io/api/auth/candidates/register",
    "status_code": 201,
    "user_agent": "Mozilla/5.0 ..."
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Minimum log level: DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | `json` | `json` for production, `text` for local development |
| `SERVICE_NAME` | `viperai-api` | Service identifier in aggregated logs |
| `ENVIRONMENT` | `production` | Environment tag (production/staging/development) |

## Forwarding to Datadog

### Option A: Datadog Agent (recommended for Railway)

1. Add the Datadog buildpack or sidecar to your Railway service
2. Set environment variables:
   ```
   DD_API_KEY=<your-datadog-api-key>
   DD_SITE=datadoghq.eu          # or datadoghq.com for US
   DD_SERVICE=viperai-api
   DD_ENV=production
   DD_LOGS_ENABLED=true
   DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true
   ```
3. Datadog auto-parses JSON logs from stdout

### Option B: Datadog HTTP Intake (no agent required)

Use a log drain or a lightweight forwarder (e.g. Vector) to POST logs to:
```
https://http-intake.logs.datadoghq.eu/api/v2/logs
```

Header: `DD-API-KEY: <your-key>`

### Retention

Configure a Datadog log index with:
- **Retention**: 395 days (13 months) — meets NHS/CQC 1-year audit requirement
- **Filter**: `service:viperai-api`
- **Daily quota**: Set based on expected volume (~5 GB/day for typical usage)

## Forwarding to BetterStack (Logtail)

1. Create a source at https://logs.betterstack.com
2. Set the Railway log drain URL:
   ```
   https://<your-source-token>@in.logs.betterstack.com
   ```
   Or set the environment variable:
   ```
   BETTERSTACK_SOURCE_TOKEN=<your-token>
   ```
3. BetterStack auto-parses JSON logs

### Retention

BetterStack supports configurable retention per source:
- Set to **365 days** minimum for healthcare compliance
- Enable archival to S3 for long-term storage beyond 1 year

## Forwarding to Grafana Cloud / Loki

1. Install the Grafana Agent or use Promtail
2. Configure the Loki push endpoint:
   ```yaml
   clients:
     - url: https://logs-prod-eu-west-0.grafana.net/loki/api/v1/push
       tenant_id: <your-tenant-id>
       basic_auth:
         username: <user-id>
         password: <api-key>
   ```

## Healthcare Audit Requirements

| Requirement | Implementation |
|-------------|---------------|
| All API requests logged | AuditMiddleware logs every non-health-check request |
| Request tracing | X-Request-ID header propagated through all logs |
| User attribution | user_id, user_type, agency_id fields in log context |
| Tamper-evident | Logs forwarded to immutable external store (Datadog/BetterStack) |
| 1-year retention | Configured at the log aggregation service level |
| Access audit | Admin impersonation logged with separate action type |
| Data access | GDPR data exports/deletions logged to audit_logs table + structured logs |

## Railway Log Drain Setup

Railway supports log drains that forward stdout to external services:

1. Go to your Railway project → Settings → Log Drains
2. Add a new drain with the HTTP endpoint for your chosen service
3. All JSON logs from stdout are automatically forwarded

**Important**: Railway's built-in logs have ~72h retention. The log drain ensures
logs are preserved for the required 1-year period in your chosen aggregation service.
