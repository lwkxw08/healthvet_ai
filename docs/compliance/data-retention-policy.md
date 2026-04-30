# Data Retention Policy

## 1. Purpose

This policy defines how long Viper AI retains personal data and the procedures for deletion, in compliance with UK GDPR Article 5(1)(e) (storage limitation).

## 2. Retention Schedule

### Candidate Data

| Data Category | Retention Period | Basis | Deletion Method |
|--------------|-----------------|-------|-----------------|
| **Active candidate profile** | Duration of agency subscription + 6 months | Contract performance | Automated on account closure |
| **Completed vetting records** | 6 years from completion | Legal obligation (healthcare regulatory) | Scheduled batch deletion |
| **DBS certificate numbers** | 3 years from check date | Regulatory guidance (DBS Code of Practice) | Automated expiry |
| **Identity documents** | Deleted after verification (max 30 days) | Data minimisation | Auto-delete post-verification |
| **Right to work evidence** | 2 years after employment ends | Immigration Act 2016 | Scheduled deletion |
| **Training certificates** | Duration of validity + 1 year | Contract performance | Automated on expiry |
| **Reference records** | 6 years from collection | Healthcare regulatory | Scheduled batch deletion |
| **CV / employment history** | Duration of active vetting | Contract performance | Deleted with candidate profile |
| **Compliance scores** | 6 years from calculation | Regulatory audit trail | Scheduled batch deletion |

### Agency Data

| Data Category | Retention Period | Basis | Deletion Method |
|--------------|-----------------|-------|-----------------|
| **Agency account** | Duration of subscription + 12 months | Contract performance | Manual on request |
| **Billing / invoices** | 7 years from invoice date | HMRC requirement (VAT) | Scheduled deletion |
| **Staff accounts** | Duration of employment + 3 months | Contract performance | Agency-managed |
| **Invite records** | 2 years from creation | Audit trail | Scheduled deletion |

### System Data

| Data Category | Retention Period | Basis | Deletion Method |
|--------------|-----------------|-------|-----------------|
| **Audit logs** | 7 years | Regulatory compliance | Scheduled deletion |
| **Application logs** | 1 year minimum | Healthcare audit | Log aggregation service policy |
| **Error reports (Sentry)** | 90 days | Legitimate interest | Sentry auto-deletion |
| **Session tokens** | 15 minutes (access) / 7 days (refresh) | Security | Automatic expiry |

## 3. Deletion Procedures

### Candidate Self-Service Deletion

Candidates can request deletion via the candidate portal:
1. Navigate to Settings → Privacy → "Delete My Data"
2. Confirm deletion request
3. System processes within 30 days
4. Confirmation email sent on completion

**Exceptions**: Data required by law (e.g., DBS records within retention period) is retained with an anonymised profile.

### Agency-Initiated Deletion

Agencies can request deletion of candidate data via:
1. Admin Panel → Candidates → Delete
2. Bulk deletion of candidates who have left the business
3. Account closure request to support

### Automated Retention Enforcement

A scheduled job runs weekly to:
1. Identify records past their retention period
2. Delete or anonymise the data
3. Log the deletion in the audit trail
4. Generate a retention compliance report

## 4. Data Anonymisation

Where full deletion is not possible (e.g., audit trail integrity), data is anonymised:
- Name → "Deleted User [hash]"
- Email → "deleted-[hash]@anonymised.local"
- Phone → cleared
- Address → cleared
- All PII fields → cleared or hashed

The anonymised record retains:
- Compliance score (for aggregate analytics)
- Audit trail entries (for regulatory queries)
- Invoice references (for HMRC)

## 5. Right to Erasure Requests

On receiving a GDPR erasure request:

1. Verify the identity of the requester
2. Check for legal retention obligations
3. If no obligation: delete within 30 days
4. If obligation exists: inform requester of the specific data retained and the legal basis
5. Log the request and outcome in the audit trail

## 6. Review

This policy is reviewed annually and whenever regulatory guidance changes. Last review: _[Date]_
