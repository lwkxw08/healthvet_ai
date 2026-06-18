# Data Processing Agreement (DPA)

**Between:** Viper AI Ltd ("Processor") and the subscribing agency ("Controller")

**Effective Date:** _[To be completed on signing]_

---

## 1. Definitions

- **Personal Data**: any information relating to an identified or identifiable natural person, as defined in UK GDPR Article 4(1).
- **Processing**: any operation performed on Personal Data, including collection, recording, storage, retrieval, consultation, use, disclosure, erasure, or destruction.
- **Data Subject**: the individual to whom the Personal Data relates (candidates, agency staff).
- **Sub-processor**: any third party engaged by the Processor to process Personal Data on behalf of the Controller.

## 2. Scope of Processing

The Processor processes Personal Data solely to provide the Viper AI vetting intelligence platform, including:

| Category | Data Types | Purpose |
|----------|-----------|---------|
| Candidate identity | Name, email, phone, date of birth, address | Onboarding and identity verification |
| Employment history | Employer names, dates, roles | CV analysis and reference checking |
| Professional registration | NMC/HCPC/GMC numbers, registration status | Registration verification |
| DBS/criminal record | Certificate numbers, check dates, status | Enhanced DBS checking |
| Right to work | Visa type, expiry, share codes | Immigration status verification |
| Training records | Course names, dates, certificates | Training compliance monitoring |
| Agency staff | Name, email, role | Platform access and billing |
| Billing data | Credit usage, invoices | Service billing |

## 3. Controller Obligations

The Controller shall:
- Ensure a lawful basis for processing (typically legitimate interest or contract performance)
- Inform Data Subjects that their data will be processed by Viper AI
- Respond to Data Subject access requests (with Processor assistance)
- Notify the Processor of any data accuracy issues

## 4. Processor Obligations

The Processor shall:
- Process Personal Data only on documented instructions from the Controller
- Ensure persons authorised to process data are bound by confidentiality
- Implement appropriate technical and organisational security measures (see Section 6)
- Not engage sub-processors without prior written consent (see Section 5)
- Assist the Controller with Data Subject rights requests within 5 business days
- Delete or return all Personal Data on termination, at Controller's choice
- Make available all information necessary to demonstrate compliance

## 5. Sub-processors

Current sub-processors are listed in the [Subprocessor List](./subprocessor-list.md).

The Processor shall:
- Notify the Controller at least 30 days before engaging a new sub-processor
- Impose equivalent data protection obligations on all sub-processors
- Remain fully liable for sub-processor compliance

## 6. Security Measures

The Processor implements:

- **Encryption**: TLS 1.2+ in transit; AES-256 at rest for database storage
- **Access control**: Role-based access with MFA for admin accounts
- **Audit logging**: All data access logged with immutable audit trail (1-year retention)
- **Network security**: WAF, DDoS protection, IP allowlisting for admin endpoints
- **Data isolation**: Multi-tenant architecture with row-level security per agency
- **Backup**: Automated daily backups with 30-day retention, encrypted at rest
- **Vulnerability management**: Regular dependency scanning, penetration testing

## 7. Data Breach Notification

The Processor shall:
- Notify the Controller without undue delay (and within 72 hours) of becoming aware of a Personal Data breach
- Provide details of the breach: nature, categories of data, approximate number of records, likely consequences, and measures taken
- Cooperate with the Controller's notification to the ICO and affected Data Subjects

## 8. International Transfers

Personal Data is processed within the UK and EEA. If transfer outside these regions is necessary:
- Standard Contractual Clauses (UK Addendum) shall apply
- A Transfer Impact Assessment shall be conducted
- Controller shall be notified and approve in advance

## 9. Data Subject Rights

The Processor shall assist the Controller in responding to:
- Right of access (Article 15)
- Right to rectification (Article 16)
- Right to erasure (Article 17) — see [Data Retention Policy](./data-retention-policy.md)
- Right to restriction (Article 18)
- Right to data portability (Article 20)

Self-service data export and deletion are available via the candidate portal.

## 10. Duration and Termination

- This DPA remains in effect for the duration of the service agreement
- On termination, the Processor shall delete all Personal Data within 30 days unless legally required to retain it
- The Controller may request a certified confirmation of deletion

## 11. Governing Law

This DPA is governed by the laws of England and Wales. Disputes shall be subject to the exclusive jurisdiction of the courts of England and Wales.

---

**Signatures:**

| | Controller | Processor |
|--|-----------|-----------|
| Name | ___________________ | ___________________ |
| Title | ___________________ | ___________________ |
| Date | ___________________ | ___________________ |
| Signature | ___________________ | ___________________ |
