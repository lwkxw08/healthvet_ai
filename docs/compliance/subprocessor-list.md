# Subprocessor List

**Last Updated:** _[Date]_

Viper AI engages the following third-party sub-processors to deliver the platform. All sub-processors are bound by equivalent data protection obligations under our DPA.

## Infrastructure & Hosting

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **Railway** (Railway Corp) | Application hosting, backend API | All application data in transit and at rest | US (Oregon) / EU available |
| **Cloudflare** (Cloudflare Inc) | CDN, DDoS protection, frontend hosting (Pages) | HTTP request metadata, static assets | Global edge network |
| **PlanetScale / MySQL** | Primary database | All structured application data | US / EU configurable |

## Authentication & Security

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **Sentry** (Functional Software Inc) | Error monitoring and performance tracing | Error context, stack traces (PII scrubbed) | US / EU available |

## Payment Processing

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **Stripe** (Stripe Inc) | Payment processing, invoicing | Agency billing details, payment card tokens | US / EU |

## Identity Verification

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **TrustID** | Identity document verification, right to work checks | Candidate name, DOB, ID document images | UK |

## Communication

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **SendGrid** (Twilio Inc) | Transactional email delivery | Recipient email addresses, email content | US |
| **Twilio** | SMS notifications | Recipient phone numbers, message content | US |

## Log Aggregation (if configured)

| Sub-processor | Purpose | Data Processed | Location |
|---------------|---------|---------------|----------|
| **Datadog** (Datadog Inc) | Log aggregation, monitoring | Application logs (may contain user IDs) | EU / US configurable |
| **BetterStack** (Better Stack Inc) | Log aggregation | Application logs | EU |

---

## Change Notification Process

Viper AI will notify all Controllers at least **30 days** before:
- Adding a new sub-processor
- Changing the purpose or data categories for an existing sub-processor
- Changing the data processing location for an existing sub-processor

Notifications are sent via email to the agency's registered contact address.

Controllers may object to a new sub-processor within the 30-day notice period. If a reasonable objection cannot be resolved, the Controller may terminate the agreement without penalty.

---

## How to Subscribe to Updates

Agency administrators can subscribe to sub-processor change notifications at:
`https://app.viperai.io` → Settings → Notifications → Sub-processor Updates
