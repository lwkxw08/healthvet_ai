import { brand } from '../config/brand'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="bg-slate-900 pt-24 pb-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link to="/" className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm mb-6 transition-colors">
            <ArrowLeft size={16} /> Back to {brand.name}
          </Link>
          <h1 className="text-3xl sm:text-4xl font-bold text-white">Terms of Service</h1>
          <p className="mt-3 text-slate-400">Last updated: {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4 prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-p:text-slate-600 prose-p:leading-relaxed prose-li:text-slate-600 prose-a:text-blue-600">

          <h2>1. Agreement to Terms</h2>
          <p>
            These Terms of Service ("Terms") govern your access to and use of the {brand.name} compliance
            vetting platform and related services (the "Service") operated by the entity identified in our
            company registration details ("we", "us", "our").
          </p>
          <p>
            By accessing or using the Service, you agree to be bound by these Terms. If you are using the
            Service on behalf of an organisation, you represent that you have authority to bind that
            organisation to these Terms.
          </p>

          <h2>2. Description of Service</h2>
          <p>
            {brand.name} provides an automated compliance vetting platform that enables recruitment agencies
            and employers to manage background checks, identity verification, right-to-work validation,
            professional registration checks, reference collection, employment verification, and ongoing
            compliance monitoring for candidates across regulated industries.
          </p>
          <p>The Service includes:</p>
          <ul>
            <li>Candidate onboarding portal for data collection and document submission</li>
            <li>Automated and manual check processing via third-party verification providers</li>
            <li>Real-time compliance scoring and dashboard</li>
            <li>Agency management tools including billing, invoicing, and candidate tracking</li>
            <li>AI-powered CV analysis and fraud detection</li>
            <li>Verification portal for referees and employment verifiers</li>
            <li>CQC audit pack generation and compliance reporting</li>
            <li>Continuous monitoring of credential expiry and regulatory changes</li>
          </ul>

          <h2>3. User Accounts</h2>
          <h3>3.1 Account Types</h3>
          <p>The Service supports three account types:</p>
          <ul>
            <li><strong>Agency accounts:</strong> For recruitment agencies and employers who manage candidate vetting</li>
            <li><strong>Candidate accounts:</strong> For individuals undergoing the vetting process</li>
            <li><strong>Admin accounts:</strong> For platform administrators who manage system configuration</li>
          </ul>

          <h3>3.2 Account Responsibilities</h3>
          <p>You are responsible for:</p>
          <ul>
            <li>Maintaining the confidentiality of your login credentials</li>
            <li>All activities that occur under your account</li>
            <li>Ensuring that all information you provide is accurate, current, and complete</li>
            <li>Notifying us immediately of any unauthorised access to your account</li>
          </ul>

          <h3>3.3 Account Suspension</h3>
          <p>
            We reserve the right to suspend or terminate accounts that violate these Terms, engage in
            fraudulent activity, or fail to maintain payment obligations.
          </p>

          <h2>4. Agency Obligations</h2>
          <p>Agencies using the Service agree to:</p>
          <ul>
            <li>Only submit candidate data with the candidate's knowledge and consent</li>
            <li>Use vetting results solely for lawful employment screening purposes</li>
            <li>Comply with all applicable employment law, equality legislation, and data protection requirements</li>
            <li>Not share access credentials with unauthorised individuals</li>
            <li>Conduct imposter checks where required by law (e.g., Right to Work verification requires an in-person or compliant video check)</li>
            <li>Maintain appropriate data processing agreements where acting as a data controller</li>
            <li>Respond to candidate data subject requests in a timely manner</li>
          </ul>

          <h2>5. Candidate Obligations</h2>
          <p>Candidates using the Service agree to:</p>
          <ul>
            <li>Provide accurate and truthful information in all sections of the vetting process</li>
            <li>Not submit fraudulent, forged, or misleading documents</li>
            <li>Notify referees and employment verifiers before providing their contact details</li>
            <li>Respond promptly to requests for additional information or clarification</li>
            <li>Consent to the processing of their personal data as described in our Privacy Policy</li>
          </ul>

          <h2>6. Fees and Payment</h2>
          <h3>6.1 Pricing</h3>
          <p>
            Fees for the Service are set out in the pricing section of our website and/or in your service
            agreement. We reserve the right to change pricing with 30 days' written notice.
          </p>

          <h3>6.2 Payment Methods</h3>
          <p>We accept payment via:</p>
          <ul>
            <li><strong>Credit pack:</strong> Pre-purchased check credits valid for 12 months</li>
            <li><strong>Pay-as-you-go:</strong> Per-check billing via Stripe or GoCardless</li>
            <li><strong>Manual invoicing:</strong> Periodic invoicing for agreed payment terms</li>
          </ul>

          <h3>6.3 Payment Terms</h3>
          <ul>
            <li>Credit packs are non-refundable and expire 12 months from purchase unless topped up</li>
            <li>Pay-as-you-go charges are due at the time of check initiation</li>
            <li>Invoiced amounts are due within 30 days unless otherwise agreed</li>
            <li>Late payments may incur interest at 8% above the Bank of England base rate, in accordance with the Late Payment of Commercial Debts (Interest) Act 1998</li>
          </ul>

          <h3>6.4 Refunds</h3>
          <p>
            Where a check cannot be completed due to a system error or provider failure, we will either
            re-process the check at no additional cost or refund the applicable charge. Refunds are not
            available where a check has been successfully processed, regardless of the outcome.
          </p>

          <h2>7. Third-Party Services</h2>
          <p>
            The Service integrates with third-party providers for identity verification, DBS checks, and
            other compliance checks. By using the Service, you acknowledge that:
          </p>
          <ul>
            <li>Third-party services are subject to their own terms and conditions</li>
            <li>We are not responsible for the accuracy, timeliness, or availability of third-party services</li>
            <li>Processing times for external checks (particularly DBS) are outside our control</li>
            <li>We will use reasonable efforts to select reputable and certified third-party providers</li>
          </ul>

          <h2>8. Intellectual Property</h2>
          <p>
            All intellectual property rights in the Service, including but not limited to the software,
            algorithms, compliance scoring models, user interface design, and documentation, remain our
            exclusive property.
          </p>
          <p>You may not:</p>
          <ul>
            <li>Copy, modify, or create derivative works of the Service</li>
            <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
            <li>Use the Service to develop a competing product</li>
            <li>Scrape, harvest, or extract data from the Service except through approved APIs</li>
          </ul>

          <h2>9. Data Protection</h2>
          <p>
            Both parties agree to comply with the UK GDPR and Data Protection Act 2018. Our Privacy Policy,
            available at <Link to="/privacy" className="text-blue-600 hover:text-blue-700">viperai.io/privacy</Link>,
            sets out how we collect, use, and protect personal data.
          </p>
          <p>
            Where an agency acts as a data controller and we act as a data processor, the terms of our Data
            Processing Agreement (available on request) shall apply.
          </p>

          <h2>10. Limitation of Liability</h2>
          <p>To the fullest extent permitted by law:</p>
          <ul>
            <li>Our total liability arising from or related to the Service shall not exceed the fees paid by you in the 12 months preceding the claim</li>
            <li>We shall not be liable for any indirect, incidental, special, consequential, or punitive damages</li>
            <li>We are not liable for decisions made by agencies or employers based on vetting results</li>
            <li>We are not liable for delays or failures in third-party checks beyond our reasonable control</li>
          </ul>
          <p>
            Nothing in these Terms excludes or limits liability for death or personal injury caused by
            negligence, fraud or fraudulent misrepresentation, or any other liability that cannot be
            excluded by law.
          </p>

          <h2>11. Service Availability</h2>
          <p>
            We aim to provide 99.9% uptime for the Service but do not guarantee uninterrupted access. We
            may suspend the Service temporarily for maintenance, updates, or circumstances beyond our
            reasonable control. We will provide reasonable notice of planned maintenance where possible.
          </p>

          <h2>12. Confidentiality</h2>
          <p>
            Both parties agree to keep confidential any information disclosed in connection with the Service
            that is not publicly available. This obligation survives termination of these Terms for a period
            of 3 years.
          </p>

          <h2>13. Termination</h2>
          <ul>
            <li>Either party may terminate the service agreement with 30 days' written notice</li>
            <li>We may terminate immediately if you breach these Terms</li>
            <li>Upon termination, your access to the Service will be revoked</li>
            <li>Data retention following termination is governed by our Privacy Policy and applicable law</li>
            <li>Outstanding fees remain payable following termination</li>
          </ul>

          <h2>14. Indemnification</h2>
          <p>
            You agree to indemnify and hold us harmless from any claims, losses, or damages arising from:
          </p>
          <ul>
            <li>Your breach of these Terms</li>
            <li>Your misuse of the Service</li>
            <li>Inaccurate information provided by you or your candidates</li>
            <li>Your failure to comply with applicable laws and regulations</li>
          </ul>

          <h2>15. Dispute Resolution</h2>
          <p>
            These Terms are governed by the laws of England and Wales. Any disputes shall first be addressed
            through good-faith negotiation. If unresolved within 30 days, disputes may be referred to
            mediation before proceeding to the courts of England and Wales.
          </p>

          <h2>16. Changes to These Terms</h2>
          <p>
            We may update these Terms from time to time. Material changes will be communicated via email or
            through the platform with at least 30 days' notice. Continued use of the Service after changes
            take effect constitutes acceptance of the updated Terms.
          </p>

          <h2>17. Severability</h2>
          <p>
            If any provision of these Terms is found to be unenforceable, the remaining provisions shall
            continue in full force and effect.
          </p>

          <h2>18. Entire Agreement</h2>
          <p>
            These Terms, together with our Privacy Policy, Cookie Policy, and any applicable Data Processing
            Agreement, constitute the entire agreement between you and us regarding the Service.
          </p>

          <h2>19. Contact Us</h2>
          <p>For questions about these Terms, please contact us:</p>
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
