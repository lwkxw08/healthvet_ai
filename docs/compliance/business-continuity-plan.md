# Business Continuity Plan (BCP)

## 1. Purpose

This plan ensures Viper AI can continue operating during and recover from disruptive events, maintaining service to healthcare staffing agencies and protecting candidate personal data.

## 2. Scope

This plan covers:
- Application infrastructure (Railway, Cloudflare, database)
- Data protection and recovery
- Communication with customers
- Team operations during disruption

## 3. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cloud provider outage (Railway) | Medium | High | Multi-region deployment, failover procedures |
| Database failure | Low | Critical | Automated backups, point-in-time recovery |
| DDoS attack | Medium | Medium | Cloudflare WAF + DDoS protection |
| Data breach | Low | Critical | Incident response plan, encryption, access controls |
| Key personnel unavailability | Medium | Medium | Cross-training, documented runbooks |
| Third-party service failure (Stripe, TrustID) | Medium | Medium | Graceful degradation, manual fallback procedures |
| DNS/domain issues | Low | High | Multiple DNS providers, low TTL records |

## 4. Recovery Objectives

| Metric | Target | Description |
|--------|--------|-------------|
| **RTO** (Recovery Time Objective) | 4 hours | Maximum time to restore service |
| **RPO** (Recovery Point Objective) | 24 hours | Maximum acceptable data loss |
| **MTPD** (Maximum Tolerable Period of Disruption) | 24 hours | Beyond this, business impact is severe |

## 5. Backup Strategy

### Database Backups
- **Frequency**: Daily automated backups at 02:00 UTC
- **Retention**: 30 days
- **Type**: Full database snapshots + point-in-time recovery logs
- **Storage**: Encrypted, stored in a different region from primary
- **Testing**: Monthly restore test to verify backup integrity

### Application Code
- **Repository**: GitHub (lwkxw08/healthvet_ai)
- **Branches**: main (production), staging, feature branches
- **Deployment**: Railway auto-deploys from main branch
- **Rollback**: Previous deployment available via Railway dashboard

### Configuration & Secrets
- **Secrets**: Stored in Railway environment variables (encrypted)
- **Backup**: Documented in secure vault (not in repository)
- **Rotation**: See [Key Rotation](../key-rotation.md) documentation

## 6. Disaster Recovery Procedures

### Scenario 1: Railway Outage

1. Check Railway status page (https://status.railway.app)
2. If outage > 30 minutes:
   - Activate backup deployment on alternative provider
   - Update DNS to point to backup
   - Notify customers via status page and email
3. Once Railway recovers:
   - Verify data consistency
   - Migrate back to primary
   - Post-incident review

### Scenario 2: Database Corruption / Loss

1. Stop application to prevent further writes
2. Identify last known good backup
3. Restore from backup (target: < 2 hours)
4. Verify data integrity:
   - Run consistency checks
   - Compare record counts with audit logs
   - Verify candidate compliance scores
5. Resume service
6. Notify affected agencies if data loss occurred

### Scenario 3: Security Breach

Follow the [Incident Response Runbook](./incident-response-runbook.md).

### Scenario 4: Third-Party Service Failure

| Service | Fallback |
|---------|----------|
| **Stripe** | Queue payment processing; manual invoicing |
| **TrustID** | Manual identity verification; flag as "pending external check" |
| **SendGrid** | Queue emails; switch to backup SMTP provider |
| **Cloudflare** | Direct DNS to Railway; accept temporary loss of CDN/WAF |
| **Sentry** | Continue without error monitoring; rely on structured logs |

## 7. Communication Plan

### Internal Communication
- Primary: Slack `#incidents` channel
- Backup: Phone tree (see Incident Response Runbook contact list)
- Tertiary: Personal email

### Customer Communication
- **Status page**: _[URL to be configured — e.g., status.viperai.io]_
- **Email**: Automated notification to agency admin contacts
- **In-app banner**: Degraded service notification on dashboard

### Communication Templates

**Initial Notification:**
> We are currently experiencing [description]. Our team is actively investigating. We will provide updates every [30 minutes / 1 hour]. Current impact: [description].

**Resolution Notification:**
> The incident affecting [description] has been resolved at [time]. Service has been fully restored. Root cause: [brief description]. A full post-mortem will follow within 5 business days.

## 8. Testing

| Test | Frequency | Description |
|------|-----------|-------------|
| Backup restore | Monthly | Restore database backup to verify integrity |
| Failover drill | Quarterly | Simulate primary infrastructure failure |
| Incident response drill | Semi-annually | Tabletop exercise with full team |
| Communication test | Quarterly | Verify contact list and notification systems |

## 9. Roles and Responsibilities

| Role | Responsibility |
|------|---------------|
| **Incident Commander** | Overall coordination, decision-making |
| **Infrastructure Lead** | Technical recovery, system restoration |
| **Data Protection Officer** | Data breach assessment, regulatory notification |
| **Customer Success** | Customer communication, status updates |
| **CEO/CTO** | Executive decisions, media communication |

## 10. Review

This plan is reviewed:
- Quarterly (scheduled)
- After every P1/P2 incident
- After any significant infrastructure change
- Annually (comprehensive review)

Last review: _[Date]_
