# Service Level Agreement (SLA)

**Between:** Viper AI Ltd ("Provider") and the subscribing agency ("Customer")

---

## 1. Service Description

The Provider operates the Viper AI platform (`app.viperai.io` / `api.viperai.io`), a cloud-based vetting intelligence service for healthcare staffing compliance.

## 2. Availability

### 2.1 Uptime Commitment

| Metric | Target |
|--------|--------|
| **Monthly uptime** | 99.9% |
| **Maximum scheduled downtime** | 4 hours per month (announced 48h in advance) |
| **Planned maintenance window** | Sundays 02:00–06:00 UTC |

**Uptime** is measured as the percentage of time the API endpoint (`api.viperai.io/health`) responds with HTTP 200 within 5 seconds, excluding scheduled maintenance.

### 2.2 Uptime Calculation

```
Monthly Uptime % = ((Total Minutes − Downtime Minutes) / Total Minutes) × 100
```

### 2.3 Service Credits

If the Provider fails to meet the uptime commitment:

| Monthly Uptime | Service Credit |
|----------------|---------------|
| 99.0% – 99.9% | 10% of monthly fee |
| 95.0% – 99.0% | 25% of monthly fee |
| Below 95.0% | 50% of monthly fee |

Service credits are applied to the next billing cycle upon Customer request within 30 days of the incident.

## 3. Performance

| Metric | Target |
|--------|--------|
| API response time (p95) | < 500ms |
| API response time (p99) | < 2000ms |
| Page load time (frontend) | < 3 seconds |
| Background job processing | < 5 minutes |

## 4. Support

### 4.1 Support Channels

| Channel | Availability |
|---------|-------------|
| Email (support@viperai.io) | 24/7 (response within SLA) |
| In-app support chat | Business hours (09:00–18:00 UTC, Mon–Fri) |
| Phone (for P1 incidents) | 24/7 for Enterprise tier |

### 4.2 Response Times

| Severity | First Response | Resolution Target |
|----------|---------------|-------------------|
| **P1 — Critical** (service down, data breach) | 15 minutes | 4 hours |
| **P2 — High** (major feature unavailable) | 1 hour | 8 hours |
| **P3 — Medium** (minor feature issue) | 4 hours | 2 business days |
| **P4 — Low** (cosmetic, enhancement request) | 1 business day | Best effort |

## 5. Data Protection

| Commitment | Detail |
|------------|--------|
| Encryption in transit | TLS 1.2+ for all connections |
| Encryption at rest | AES-256 for database and backups |
| Backup frequency | Daily automated backups |
| Backup retention | 30 days |
| Recovery Point Objective (RPO) | 24 hours |
| Recovery Time Objective (RTO) | 4 hours |

## 6. Change Management

- **Feature releases**: Deployed continuously; breaking changes announced 30 days in advance
- **Security patches**: Applied within 24 hours of disclosure for critical vulnerabilities
- **API versioning**: Minimum 12 months support for deprecated API versions
- **Maintenance notifications**: 48 hours advance notice via email and status page

## 7. Reporting

The Provider shall make available:
- **Uptime reports**: Monthly, via status page or on request
- **Security reports**: Quarterly summary of security posture
- **Compliance reports**: Annual attestation of GDPR/DPA compliance

## 8. Exclusions

The uptime commitment does not apply during:
- Scheduled maintenance windows
- Force majeure events
- Issues caused by Customer's infrastructure, browsers, or network
- Third-party service outages beyond Provider's control (e.g., Stripe, TrustID)

## 9. Term and Review

This SLA is reviewed annually and may be updated with 30 days' notice. The SLA applies for the duration of the service agreement.

---

**Agreed:**

| | Customer | Provider |
|--|----------|----------|
| Name | ___________________ | ___________________ |
| Date | ___________________ | ___________________ |
