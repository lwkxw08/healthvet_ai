# HealthVet AI - Features by Profile

## Candidate Profile

### Registration & Onboarding
- **Self-Registration**: Create account with email, password, name, phone, and profession
- **Agency Invite Acceptance**: Accept invitations from agencies to link accounts
- **Guided Submission Flow**: Step-by-step data collection across all vetting sections
- **GDPR Consent Management**: Explicit consent capture with privacy policy and terms versioning
- **Re-Vet Submissions**: Complete targeted re-vetting when requested by agency

### Identity Verification
- **Document Upload**: Upload passport, driving licence, or national ID
- **Selfie Verification**: Take or upload selfie for liveness/match check
- **Onfido-Ready Integration**: Backend structured to consume Onfido API when API key is provided
- **Verification Status Tracking**: View real-time status of identity check (pending/verified/failed)

### Right to Work (RTW)
- **Citizenship Declaration**: Declare UK Citizen, Irish Citizen, or Visa/Share Code holder
- **UK/Irish Citizen Flow**: National Insurance number collection with automated verification stub
- **Share Code Flow**: Enter Home Office share code for online RTW check
- **Imposter Check Declaration**: Agency-facing declaration confirming identity match with documents
- **TrustID-Ready Integration**: Backend structured for TrustID API integration

### DBS (Disclosure & Barring Service)
- **DBS Certificate Upload**: Upload DBS certificate number and issue date
- **Enhanced DBS Support**: Track enhanced DBS with barred list checks
- **Update Service Registration**: Record DBS Update Service subscription status
- **Expiry Monitoring**: Automated tracking of DBS validity periods

### CV / Professional Profile
- **CV Upload**: Upload CV document for AI-powered analysis
- **AI CV Analysis**: Automated extraction of qualifications, experience, and skills
- **Gap Detection**: Identify employment gaps for compliance review
- **Qualification Validation**: Cross-reference qualifications against role requirements

### Professional Registration
- **Registration Body Selection**: NMC, GMC, GPhC, HCPC, Social Work England, and others
- **Registration Number Entry**: Enter professional registration number
- **Automated Verification Stub**: Backend ready for live register API lookups
- **Expiry Tracking**: Monitor registration renewal dates

### Employment History & Verification
- **Work History Entry**: Add employment records with dates, employer, role, and reason for leaving
- **Verifier Details**: Specify reference contact for each employment record
- **Verification Request Dispatch**: Send verification requests to previous employers
- **Employment Gap Analysis**: Automated detection and flagging of gaps > 30 days

### References
- **Reference Submission**: Provide referee name, email, phone, relationship, and years known
- **Automated Reference Requests**: System dispatches verification emails to referees
- **Reference Status Tracking**: Monitor pending, verified, and failed reference checks
- **Re-trigger Capability**: Admin can re-send reference verification requests

### Training Certificates
- **Certificate Upload**: Add training certificates with name, provider, category
- **Issue & Expiry Dates**: Track certificate validity periods
- **Mandatory Training Tracking**: System checks against required healthcare training standards
- **Compliance Scoring**: Training contributes to overall compliance score

### Submission & Status
- **Section Progress Tracking**: Visual progress indicator across all vetting sections
- **Submission Validation**: Pre-submit check ensuring all required sections are complete
- **Consent & Submit**: Final consent confirmation before submission for processing
- **Status Dashboard**: View overall vetting status and compliance score
- **Agency Visibility**: See which agencies have access to your profile

---

## Agency Profile

### Dashboard & Overview
- **Compliance Summary Cards**: Total candidates, compliant, pending, flagged counts
- **Risk Overview Panel**: Green/Amber/Red breakdown of candidate compliance status
- **Compliance Distribution Chart**: Pie chart showing compliance breakdown
- **Monthly Vetting Trend**: Bar chart showing vetting activity over time
- **Credit Usage Tracking**: Monitor subscription credits used/remaining with progress bar
- **Rollover Credits Display**: View unused credits carried forward from previous month

### Candidate Management
- **Candidate List**: Searchable, filterable list of all linked candidates
- **RAG Status Badges**: Red/Amber/Green compliance badges on each candidate
- **Status Filter**: Filter candidates by employment status (vetting, hired, on-hold, terminated)
- **RAG Filter**: Filter by compliance status (Red, Amber, Green)
- **Candidate Detail View**: Deep-dive into individual candidate compliance data
- **Compliance Breakdown**: 8-check compliance grid (Identity, RTW, DBS, CV, Registration, Employment, References, Training)
- **Employment Status Management**: Update candidate status (vetting/hired/on-hold/terminated)
- **Shift Readiness Badge**: Single "Ready to Work" indicator (Ready/Conditional/Not Ready)

### Bulk Candidate Import (NEW)
- **CSV File Upload**: Upload .csv file with candidate data
- **CSV Text Paste**: Paste CSV data directly into text area
- **Template Format**: Required columns (email, first_name, last_name) + optional (phone, profession)
- **Import Preview**: View import results (created, skipped, errors)
- **Auto-Invite Option**: Optionally send invite emails to imported candidates
- **Error Reporting**: Per-row error details for failed imports

### Shift Readiness Overview (NEW)
- **Agency-Wide Overview**: Summary cards showing Ready/Conditional/Not Ready counts
- **Per-Candidate Badge**: Shift readiness status badge on each candidate in the list
- **Compliance Aggregation**: Combines all 8 compliance checks into single readiness status

### Agency Sub-Accounts (NEW)
- **Create Sub-Accounts**: Add team members with email, password, name, and role
- **Role-Based Access Control**: 4 roles with specific permissions:
  - **Owner**: Full access (view/edit candidates, billing, sub-accounts, settings, reports)
  - **Manager**: Manage candidates, view reports, invite candidates, request re-vets
  - **Compliance Officer**: View compliance data, download reports, view analytics
  - **Recruiter**: View candidates, invite candidates, view basic compliance
- **Role Management**: Change sub-account roles via dropdown
- **Active/Inactive Toggle**: Enable or disable sub-account access
- **Delete Sub-Accounts**: Remove team member access

### In-App Notification Centre (NEW)
- **Activity Feed**: Chronological list of notifications with timestamps
- **Category Filters**: Filter by expiry_warning, completion, action_required, payment
- **Severity Indicators**: Visual severity levels (info/blue, warning/amber, success/green, error/red)
- **Unread Badge**: Notification count badge in navigation tab
- **Mark as Read**: Mark individual notifications as read
- **Mark All Read**: Bulk mark all notifications as read
- **Delete Notifications**: Remove individual notifications
- **Generate Notifications**: Seed sample notifications for testing/demo

### Invites & Onboarding
- **Send Invites**: Invite candidates by email with cost preview
- **Vetting Cost Preview**: See itemised vetting costs before sending invite
- **Monitoring Add-On**: Option to include ongoing monitoring with invite
- **Invite Management**: View pending, accepted, and expired invites
- **Copy Invite Link**: Share invite link directly
- **Revoke Invites**: Cancel pending invitations

### Re-Vetting
- **Request Re-Vet**: Select specific sections for re-verification
- **Section-Level Pricing**: View cost per re-vet section
- **Cost Estimate**: Total cost preview before submitting request
- **Re-Vet History**: View past re-vet requests and their status

### Imposter Check
- **Declaration Form**: Confirm candidate identity matches submitted documents
- **Document Verification Checklist**: Tick off verified document types
- **Declaration Recording**: Timestamped record of who made the declaration

### CQC Audit
- **Agency Audit Pack**: Download comprehensive agency-level audit PDF
- **Individual Candidate Audit**: Download per-candidate audit PDF
- **Bulk Candidate Audit**: Select multiple candidates for batch audit download
- **Compliance Report**: Download compliance summary report

### Billing & Subscriptions
- **Subscription Plans**: View and subscribe to tiered plans (Basic, Professional, Enterprise, etc.)
- **Credit Tracking**: Monitor monthly credit allocation and usage
- **Invoice History**: View all invoices with status and amounts
- **Pay Invoices**: Mark invoices as paid
- **Billing Mode**: Manual invoicing or Stripe integration
- **PAYG Support**: Pay-as-you-go option for non-subscription agencies

### Alerts
- **Expiry Warnings**: Automated alerts for expiring documents (DBS, visa, training, registration)
- **Compliance Alerts**: Notifications when candidate compliance status changes
- **Alert Resolution**: Mark alerts as resolved with notes

---

## Admin Profile

### Dashboard Overview
- **Platform Statistics**: Total candidates, agencies, compliance rates
- **Compliance Distribution**: Pie chart of platform-wide compliance
- **Monthly Vetting Trends**: Bar chart of vetting activity
- **Active Alerts Count**: Real-time alert monitoring

### Candidate Management
- **Full Candidate List**: View all candidates across all agencies
- **Create Candidates**: Manually create candidate accounts
- **Edit Candidate Data**: Modify candidate profiles, profession, registration details
- **Delete Candidates**: Remove candidate accounts
- **Candidate Detail View**: Deep-dive into any candidate's full vetting data
- **Compliance Evaluation**: Trigger compliance re-evaluation for candidates
- **Status Override**: Override compliance check statuses

### Agency Management
- **Agency List**: View all registered agencies with status
- **Create Agencies**: Manually create agency accounts
- **Suspend/Activate Agencies**: Toggle agency active status
- **Delete Agencies**: Remove agency accounts
- **Billing Mode Management**: Set agency billing mode (manual/stripe)
- **Discount Configuration**: Set per-agency discount percentages
- **Agency Detail View**: View agency candidates, subscription, and billing data

### Compliance Overrides
- **Check Status Override**: Manually override any of the 8 compliance checks
- **Override Notes**: Document reason for override
- **Audit Trail**: All overrides logged with timestamp and admin user

### Analytics
- **Revenue Analytics**: Platform-wide revenue tracking with period filters
- **Operations Analytics**: Vetting volumes, completion rates, turnaround times
- **Agency Analytics**: Per-agency performance metrics
- **Invoice Analytics**: Invoice generation and payment tracking
- **Custom Date Ranges**: Filter analytics by any date period
- **Financial Reports**: Download PDF financial reports
- **Compliance Reports**: Download PDF compliance reports

### Fraud Detection
- **Automated Fraud Scan**: Run AI-powered fraud detection across all candidates
- **Fraud Flags**: View detected anomalies and suspicious patterns
- **Flag Resolution**: Review and resolve fraud flags
- **Fraud Summary**: Overview of fraud detection statistics

### Monitoring
- **Continuous Monitoring**: Track ongoing compliance status changes
- **Monitoring Candidates**: View candidates enrolled in continuous monitoring
- **Run Monitoring Checks**: Manually trigger monitoring check cycle
- **Alert Generation**: Automated alert creation for compliance changes
- **Monitoring Revenue**: Track revenue from monitoring subscriptions

### Benchmarking (NEW)
- **Agency Comparison Table**: Compare all agencies side-by-side on key metrics
- **Compliance Rate Ranking**: See which agencies have highest/lowest compliance
- **Candidate Volume**: Compare candidate counts across agencies
- **Average Vetting Time**: Compare vetting turnaround by agency
- **Revenue per Agency**: Track revenue contribution per agency
- **Compliance Bar Chart**: Visual comparison of agency compliance rates
- **Summary Cards**: Quick counts of high/medium/low compliance agencies
- **Trend Analysis**: Monthly compliance and vetting trends

### Invoicing
- **View All Invoices**: Platform-wide invoice list with filters
- **Generate Invoices**: Create invoices for specific agencies and date ranges
- **Grouped Invoices**: Generate consolidated invoices across date ranges
- **Mark as Paid**: Update invoice payment status
- **Adjust Invoices**: Modify invoice amounts with notes
- **Filter by Status**: Filter invoices by paid/unpaid/overdue
- **Filter by Agency**: View invoices for specific agencies
- **Search Invoices**: Text search across invoice data

### Subscriptions
- **Tier Management**: Create, edit, and delete subscription tiers
- **Tier Configuration**: Set credits, pricing, rollover, overage rates per tier
- **Partial Credit Rates**: Configure fractional credit costs per check type
- **Agency Subscriptions**: View and manage agency subscription assignments

### Scheduler
- **Job Status**: View scheduled background job status
- **Manual Trigger**: Manually trigger any scheduled job
- **Job Types**: Expiry checks, monitoring scans, invoice generation, alert cleanup

### User Management
- **User List**: View all users across the platform
- **Create Users**: Manually create user accounts
- **User Roles**: Manage user type assignments

### Audit Logs
- **Activity Logs**: View all platform activity with timestamps
- **Filter by Action**: Filter logs by action type
- **Filter by User**: Filter logs by specific user
- **Date Range Filter**: View logs for specific time periods

### Settings
- **Pricing Configuration**: Set per-check pricing for all vetting services
- **Alert Settings**: Configure alert thresholds and notification rules
- **Platform Configuration**: General platform settings
- **Payment Reminders**: Send bulk payment reminders to agencies

### Reports & Exports
- **Financial Reports**: Download PDF financial reports with date range filters
- **Compliance Reports**: Download PDF compliance reports (platform-wide or per-agency)
- **Candidate Audit Packs**: Generate CQC-ready audit documentation
- **Bulk Audit Export**: Select multiple candidates for batch audit download
