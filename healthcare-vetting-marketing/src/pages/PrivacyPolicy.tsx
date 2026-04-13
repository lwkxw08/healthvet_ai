import { brand } from '../config/brand'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="bg-slate-900 pt-24 pb-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link to="/" className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm mb-6 transition-colors">
            <ArrowLeft size={16} /> Back to {brand.name}
          </Link>
          <h1 className="text-3xl sm:text-4xl font-bold text-white">Privacy Policy</h1>
          <p className="mt-3 text-slate-400">Last updated: {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4 prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-p:text-slate-600 prose-p:leading-relaxed prose-li:text-slate-600 prose-a:text-blue-600">

          <h2>1. Introduction</h2>
          <p>
            This Privacy Policy explains how {brand.name} ("we", "us", "our"), operated by the entity identified in
            our company registration details, collects, uses, stores, and protects your personal data when you use
            our compliance vetting platform and related services (the "Service").
          </p>
          <p>
            We are committed to protecting your privacy and complying with the UK General Data Protection Regulation
            (UK GDPR), the Data Protection Act 2018, and all other applicable data protection legislation.
          </p>
          <p>
            By using our Service, you acknowledge that you have read and understood this Privacy Policy.
          </p>

          <h2>2. Data Controller</h2>
          <p>
            The data controller responsible for your personal data is the entity operating the {brand.name} platform,
            registered as detailed on our website. For data protection enquiries, please contact us at{' '}
            <a href={`mailto:${brand.contact.email}`}>{brand.contact.email}</a>.
          </p>
          <p>
            We are registered with the Information Commissioner's Office (ICO) as required under UK data
            protection law.
          </p>

          <h2>3. What Personal Data We Collect</h2>
          <p>We collect and process different categories of personal data depending on your relationship with us:</p>

          <h3>3.1 Candidate Data (Data Subjects)</h3>
          <ul>
            <li><strong>Identity information:</strong> Full name, date of birth, nationality, gender</li>
            <li><strong>Contact information:</strong> Email address, phone number, residential address</li>
            <li><strong>Identity documents:</strong> Passport, driving licence, national ID card (processed via our trusted identity verification partner)</li>
            <li><strong>Biometric data:</strong> Selfie photographs for facial matching (processed via our identity verification partner)</li>
            <li><strong>Employment history:</strong> Previous employers, job titles, dates of employment, reasons for leaving</li>
            <li><strong>Professional registration:</strong> Registration numbers for NMC, GMC, HCPC, GPhC, CSCS, and other professional bodies</li>
            <li><strong>Training and qualifications:</strong> Training certificates, qualification records, and expiry dates</li>
            <li><strong>Right to work data:</strong> Share codes, visa details, immigration status</li>
            <li><strong>DBS check data:</strong> DBS certificate numbers, check results, and update service subscription status</li>
            <li><strong>CV and work history:</strong> Uploaded CV documents and parsed employment data</li>
            <li><strong>Reference and verification data:</strong> Referee contact details, verification responses, sentiment analysis results</li>
            <li><strong>Consent records:</strong> Timestamps, IP addresses, and versions of policies consented to</li>
          </ul>

          <h3>3.2 Agency User Data</h3>
          <ul>
            <li><strong>Account information:</strong> Name, email address, organisation name, job title</li>
            <li><strong>Billing information:</strong> Invoice details, subscription tier, payment history</li>
            <li><strong>Usage data:</strong> Login activity, feature usage, candidate invitations sent</li>
          </ul>

          <h3>3.3 Referee and Verifier Data</h3>
          <ul>
            <li><strong>Contact information:</strong> Name, email address, job title, organisation</li>
            <li><strong>Verification responses:</strong> Employment confirmations, reference questionnaire responses</li>
            <li><strong>Technical data:</strong> IP address, submission timestamps, browser information</li>
          </ul>

          <h3>3.4 Technical Data (All Users)</h3>
          <ul>
            <li><strong>Device and browser information:</strong> IP address, browser type, operating system</li>
            <li><strong>Usage data:</strong> Pages visited, features used, session duration</li>
            <li><strong>Authentication data:</strong> Login timestamps, session tokens</li>
          </ul>

          <h2>4. Legal Basis for Processing</h2>
          <p>We process personal data under the following legal bases as defined by UK GDPR:</p>
          <ul>
            <li><strong>Consent (Article 6(1)(a)):</strong> Candidates provide explicit consent before submitting personal data for vetting checks. Consent is recorded with timestamp, IP address, and policy version for audit purposes.</li>
            <li><strong>Contract (Article 6(1)(b)):</strong> Processing is necessary for the performance of our service agreement with agencies and the vetting process requested by candidates.</li>
            <li><strong>Legal obligation (Article 6(1)(c)):</strong> Certain checks (e.g., DBS, Right to Work) are required by law for specific roles in regulated industries.</li>
            <li><strong>Legitimate interests (Article 6(1)(f)):</strong> Fraud detection, platform security, and service improvement where these interests do not override the data subject's rights.</li>
          </ul>

          <h3>4.1 Special Category Data</h3>
          <p>
            Where we process special category data (such as health declarations or criminal records information
            via DBS checks), we do so on the basis of:
          </p>
          <ul>
            <li>Explicit consent from the data subject</li>
            <li>Processing necessary for reasons of substantial public interest (Schedule 1, Part 2 of the Data Protection Act 2018)</li>
            <li>Processing necessary for employment, social security, and social protection law</li>
          </ul>

          <h2>5. How We Use Your Data</h2>
          <p>We use your personal data for the following purposes:</p>
          <ul>
            <li><strong>Identity verification:</strong> Confirming your identity through document checks and biometric matching via our trusted identity verification partner</li>
            <li><strong>Background checks:</strong> Submitting and processing DBS checks through our authorised DBS umbrella body partner</li>
            <li><strong>Right to work verification:</strong> Validating immigration status and work eligibility through certified IDSP channels</li>
            <li><strong>Professional registration checks:</strong> Verifying active registration with relevant professional bodies</li>
            <li><strong>Employment verification:</strong> Contacting previous employers to confirm employment history</li>
            <li><strong>Reference collection:</strong> Gathering structured references from nominated referees</li>
            <li><strong>CV analysis:</strong> AI-powered analysis of CV content for gap detection and fraud indicators</li>
            <li><strong>Compliance scoring:</strong> Calculating real-time compliance scores based on check results</li>
            <li><strong>Ongoing monitoring:</strong> Tracking expiry dates for DBS, registrations, visas, and training certificates</li>
            <li><strong>Audit and reporting:</strong> Generating CQC-ready audit packs and compliance reports</li>
            <li><strong>Service improvement:</strong> Analysing anonymised usage patterns to improve our platform</li>
            <li><strong>Communication:</strong> Sending verification requests, status updates, expiry reminders, and billing notifications</li>
          </ul>

          <h2>6. Third-Party Data Sharing</h2>
          <p>We share personal data with the following categories of third parties, strictly as necessary to deliver our Service:</p>
          <ul>
            <li><strong>Identity verification provider (TrustID or equivalent):</strong> Identity documents, biometric data, and personal details for ID verification, Right to Work checks, and DBS submission</li>
            <li><strong>DBS umbrella body:</strong> Personal details required for DBS check applications</li>
            <li><strong>Professional registration bodies:</strong> Registration numbers for verification against NMC, GMC, HCPC, GPhC, and other registers</li>
            <li><strong>Referees and past employers:</strong> Candidate name and role details to enable verification responses</li>
            <li><strong>Recruiting agencies:</strong> Compliance status, check results, and audit documentation as the contracting party</li>
            <li><strong>Email service provider (SendGrid/Mailgun/Resend):</strong> Email addresses for transactional communications</li>
            <li><strong>Payment processor (Stripe/GoCardless):</strong> Agency billing information for payment processing</li>
            <li><strong>Cloud infrastructure providers:</strong> Data is hosted on secure, UK/EU-based cloud infrastructure</li>
            <li><strong>AI analysis provider (OpenAI):</strong> CV text and reference responses for AI-powered analysis (anonymised where possible)</li>
          </ul>
          <p>
            We do not sell, rent, or trade your personal data to any third party for marketing purposes.
          </p>

          <h2>7. International Data Transfers</h2>
          <p>
            Where personal data is transferred outside the UK (for example, to cloud service providers or AI
            analysis services), we ensure appropriate safeguards are in place, including:
          </p>
          <ul>
            <li>Standard Contractual Clauses (SCCs) approved by the ICO</li>
            <li>Adequacy decisions where applicable</li>
            <li>Data processing agreements with all sub-processors</li>
          </ul>

          <h2>8. Data Retention</h2>
          <p>We retain personal data only for as long as necessary to fulfil the purposes for which it was collected:</p>
          <ul>
            <li><strong>Candidate vetting data:</strong> Retained for 6 years from the date of the last check, in line with CQC record-keeping requirements and the Limitation Act 1980</li>
            <li><strong>DBS certificate data:</strong> Certificate numbers and results retained; original certificates are not stored</li>
            <li><strong>Consent records:</strong> Retained for the duration of the data retention period plus 1 year</li>
            <li><strong>Audit logs:</strong> Retained for 7 years for regulatory compliance</li>
            <li><strong>Agency account data:</strong> Retained for the duration of the service agreement plus 6 years</li>
            <li><strong>Technical logs:</strong> Retained for 12 months</li>
          </ul>
          <p>
            After the retention period, data is securely deleted or anonymised. Automated retention policies
            enforce deletion schedules.
          </p>

          <h2>9. Your Rights Under UK GDPR</h2>
          <p>You have the following rights in relation to your personal data:</p>
          <ul>
            <li><strong>Right of access (Article 15):</strong> Request a copy of the personal data we hold about you</li>
            <li><strong>Right to rectification (Article 16):</strong> Request correction of inaccurate or incomplete data</li>
            <li><strong>Right to erasure (Article 17):</strong> Request deletion of your personal data ("right to be forgotten"), subject to legal retention requirements</li>
            <li><strong>Right to restrict processing (Article 18):</strong> Request that we limit how we use your data</li>
            <li><strong>Right to data portability (Article 20):</strong> Request your data in a structured, commonly used format</li>
            <li><strong>Right to object (Article 21):</strong> Object to processing based on legitimate interests</li>
            <li><strong>Right to withdraw consent:</strong> Withdraw consent at any time where processing is based on consent</li>
          </ul>
          <p>
            To exercise any of these rights, please contact us at{' '}
            <a href={`mailto:${brand.contact.email}`}>{brand.contact.email}</a>. We will respond within one
            month of receiving your request.
          </p>

          <h2>10. Data Security</h2>
          <p>We implement appropriate technical and organisational measures to protect your personal data, including:</p>
          <ul>
            <li>Encryption of data in transit (TLS 1.2+) and at rest</li>
            <li>Secure authentication with password hashing (bcrypt) and optional multi-factor authentication</li>
            <li>Role-based access controls ensuring agencies can only access their own candidates' data</li>
            <li>Tamper-evident audit logging with cryptographic hash chains</li>
            <li>Regular security reviews and vulnerability assessments</li>
            <li>Encrypted storage of third-party API credentials</li>
            <li>Rate limiting and IP-based access controls</li>
            <li>Automated database backups with point-in-time recovery</li>
          </ul>

          <h2>11. Automated Decision-Making</h2>
          <p>
            Our platform uses automated processing to calculate compliance scores and flag potential fraud
            indicators. However:
          </p>
          <ul>
            <li>No solely automated decisions are made that produce legal or similarly significant effects</li>
            <li>All flagged candidates are reviewed by a human administrator before any adverse action</li>
            <li>Compliance scores are advisory — final hiring decisions remain with the recruiting agency</li>
            <li>You have the right to request human review of any automated assessment</li>
          </ul>

          <h2>12. Children's Data</h2>
          <p>
            Our Service is not intended for individuals under 18 years of age. We do not knowingly collect
            personal data from children. If we become aware that we have collected data from a child, we will
            take steps to delete it promptly.
          </p>

          <h2>13. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. Material changes will be communicated via
            email or through the platform. The "Last updated" date at the top of this page indicates when the
            policy was last revised. Continued use of the Service after changes constitutes acceptance of the
            updated policy.
          </p>

          <h2>14. Complaints</h2>
          <p>
            If you are not satisfied with how we handle your personal data, you have the right to lodge a
            complaint with the Information Commissioner's Office (ICO):
          </p>
          <ul>
            <li>Website: <a href="https://ico.org.uk" target="_blank" rel="noopener noreferrer">ico.org.uk</a></li>
            <li>Telephone: 0303 123 1113</li>
            <li>Post: Information Commissioner's Office, Wycliffe House, Water Lane, Wilmslow, Cheshire, SK9 5AF</li>
          </ul>

          <h2>15. Contact Us</h2>
          <p>
            For any questions about this Privacy Policy or our data practices, please contact us:
          </p>
          <ul>
            <li>Email: <a href={`mailto:${brand.contact.email}`}>{brand.contact.email}</a></li>
            <li>Phone: {brand.contact.phone}</li>
          </ul>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-sm text-slate-500">&copy; {brand.footer.copyright}</p>
        </div>
      </footer>
    </div>
  )
}
