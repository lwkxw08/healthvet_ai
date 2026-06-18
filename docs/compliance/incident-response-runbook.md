# Incident Response Runbook

## 1. Purpose

This runbook defines the process for detecting, responding to, and recovering from security incidents affecting Viper AI and the personal data it processes.

## 2. Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **P1 — Critical** | Active data breach or total service outage | 15 minutes | Unauthorised data access, database compromise, complete API failure |
| **P2 — High** | Partial breach or degraded service | 1 hour | Suspicious login patterns, single endpoint down, elevated error rates |
| **P3 — Medium** | Potential vulnerability or minor degradation | 4 hours | Dependency vulnerability, slow queries, failed background jobs |
| **P4 — Low** | Informational or cosmetic issue | Next business day | Minor UI bug, non-critical log anomaly |

## 3. Incident Response Phases

### Phase 1: Detection & Triage (0–15 min)

1. **Automated detection**: Sentry alerts, uptime monitors, log anomaly alerts
2. **Manual report**: Customer support, team member, or external reporter
3. **Triage**:
   - Assign severity level (P1–P4)
   - Designate Incident Commander (IC)
   - Open incident channel (Slack: `#incident-YYYY-MM-DD`)
   - Start incident log with timestamps

### Phase 2: Containment (15 min – 1 hour for P1)

1. **Isolate affected systems**:
   - Revoke compromised API keys/tokens
   - Block suspicious IP addresses (Cloudflare WAF rules)
   - Disable affected user accounts if necessary
   - Scale down or isolate affected services on Railway
2. **Preserve evidence**:
   - Export relevant logs from Datadog/BetterStack
   - Capture database state (point-in-time snapshot)
   - Document attacker indicators (IPs, user agents, payloads)

### Phase 3: Eradication (1–4 hours for P1)

1. Identify root cause
2. Patch vulnerability or close attack vector
3. Rotate all potentially compromised credentials:
   - Database passwords
   - API keys (Stripe, TrustID, SendGrid)
   - JWT signing secret
   - Admin passwords
4. Deploy fix to production via Railway

### Phase 4: Recovery (4–24 hours for P1)

1. Restore affected services to normal operation
2. Verify data integrity:
   - Compare database checksums
   - Review audit logs for unauthorised modifications
   - Check compliance records for tampering
3. Monitor for re-occurrence (elevated alerting for 72 hours)

### Phase 5: Post-Incident (within 5 business days)

1. Conduct blameless post-mortem
2. Document:
   - Timeline of events
   - Root cause analysis
   - Impact assessment (users affected, data exposed)
   - Remediation actions taken
   - Preventive measures for the future
3. Update this runbook if process gaps were identified
4. File post-mortem in `docs/incidents/YYYY-MM-DD-title.md`

## 4. Data Breach Notification

### ICO Notification (within 72 hours)

If the incident involves a personal data breach:

1. Assess whether notification to the ICO is required (risk to individuals)
2. Prepare notification including:
   - Nature of the breach
   - Categories and approximate number of data subjects affected
   - Name and contact details of the DPO
   - Likely consequences
   - Measures taken or proposed
3. Submit via https://ico.org.uk/make-a-complaint/data-protection-complaints/data-protection-complaints/

### Controller Notification (within 72 hours)

Notify all affected agency Controllers:
- Email to registered contact
- Description of breach and data categories affected
- Measures taken
- Recommendations for Controllers' own notification obligations

### Data Subject Notification

If the breach results in high risk to individuals:
- Notify affected candidates via email
- Provide clear description of what happened and what data was involved
- Recommend protective actions (password change, monitor accounts)

## 5. Contact List

| Role | Name | Contact |
|------|------|---------|
| Incident Commander (primary) | _[TBD]_ | _[phone/email]_ |
| Incident Commander (backup) | _[TBD]_ | _[phone/email]_ |
| Data Protection Officer | _[TBD]_ | _[email]_ |
| Infrastructure Lead | _[TBD]_ | _[phone/email]_ |
| Legal Counsel | _[TBD]_ | _[email]_ |
| ICO Helpline | — | 0303 123 1113 |

## 6. Quarterly Review

This runbook is reviewed quarterly and after every P1/P2 incident. Last review: _[Date]_
