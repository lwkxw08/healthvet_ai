import { brand } from '../config/brand'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function CookiePolicy() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="bg-slate-900 pt-24 pb-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link to="/" className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm mb-6 transition-colors">
            <ArrowLeft size={16} /> Back to {brand.name}
          </Link>
          <h1 className="text-3xl sm:text-4xl font-bold text-white">Cookie Policy</h1>
          <p className="mt-3 text-slate-400">Last updated: {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4 prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-p:text-slate-600 prose-p:leading-relaxed prose-li:text-slate-600 prose-a:text-blue-600">

          <h2>1. What Are Cookies?</h2>
          <p>
            Cookies are small text files that are placed on your device (computer, tablet, or mobile phone)
            when you visit a website. They are widely used to make websites work more efficiently, provide
            a better user experience, and give website operators useful information.
          </p>
          <p>
            This Cookie Policy explains how {brand.name} ("we", "us", "our") uses cookies and similar
            technologies on our website and platform.
          </p>

          <h2>2. How We Use Cookies</h2>
          <p>We use cookies for the following purposes:</p>

          <h3>2.1 Strictly Necessary Cookies</h3>
          <p>
            These cookies are essential for the operation of our Service. They enable core functionality
            such as security, authentication, and session management. Without these cookies, the Service
            cannot function properly.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Cookie</th>
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Purpose</th>
                <th className="text-left py-3 font-semibold text-slate-900">Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">viperai_auth</td>
                <td className="py-3 pr-4">Authentication token for logged-in users</td>
                <td className="py-3">Session / 24 hours</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">csrf_token</td>
                <td className="py-3 pr-4">Cross-site request forgery protection</td>
                <td className="py-3">Session</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">cookie_consent</td>
                <td className="py-3 pr-4">Records your cookie preferences</td>
                <td className="py-3">12 months</td>
              </tr>
            </tbody>
          </table>

          <h3>2.2 Functional Cookies</h3>
          <p>
            These cookies enable enhanced functionality and personalisation, such as remembering your
            preferences and settings.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Cookie</th>
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Purpose</th>
                <th className="text-left py-3 font-semibold text-slate-900">Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">user_preferences</td>
                <td className="py-3 pr-4">Remembers display preferences (e.g., dashboard layout)</td>
                <td className="py-3">12 months</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">last_login_type</td>
                <td className="py-3 pr-4">Remembers your account type for faster login</td>
                <td className="py-3">30 days</td>
              </tr>
            </tbody>
          </table>

          <h3>2.3 Analytics Cookies</h3>
          <p>
            If enabled, these cookies help us understand how visitors interact with our website by
            collecting anonymised usage data. We currently do not use third-party analytics cookies.
            If we introduce analytics tracking in the future, this policy will be updated and your
            consent will be requested.
          </p>

          <h3>2.4 Marketing Cookies</h3>
          <p>
            We do not currently use marketing or advertising cookies. If this changes, we will update
            this policy and obtain your consent before placing such cookies.
          </p>

          <h2>3. Local Storage</h2>
          <p>
            In addition to cookies, we use browser local storage (localStorage) to store certain data
            on your device:
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Key</th>
                <th className="text-left py-3 pr-4 font-semibold text-slate-900">Purpose</th>
                <th className="text-left py-3 font-semibold text-slate-900">Cleared On</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">viperai_auth</td>
                <td className="py-3 pr-4">JWT authentication token</td>
                <td className="py-3">Logout / token expiry</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-3 pr-4 font-mono text-xs">viperai_user</td>
                <td className="py-3 pr-4">Cached user profile data</td>
                <td className="py-3">Logout</td>
              </tr>
            </tbody>
          </table>
          <p>
            Local storage data is only accessible by our application and is not sent to our servers
            with every request (unlike cookies).
          </p>

          <h2>4. Your Cookie Choices</h2>
          <p>You have several options for managing cookies:</p>

          <h3>4.1 Browser Settings</h3>
          <p>
            Most web browsers allow you to control cookies through their settings. You can typically:
          </p>
          <ul>
            <li>View what cookies are stored on your device</li>
            <li>Delete individual or all cookies</li>
            <li>Block cookies from specific or all websites</li>
            <li>Set preferences for first-party vs third-party cookies</li>
          </ul>
          <p>
            Please note that blocking strictly necessary cookies will prevent the Service from
            functioning correctly.
          </p>

          <h3>4.2 How to Manage Cookies in Common Browsers</h3>
          <ul>
            <li><strong>Chrome:</strong> Settings &gt; Privacy and security &gt; Cookies and other site data</li>
            <li><strong>Firefox:</strong> Settings &gt; Privacy &amp; Security &gt; Cookies and Site Data</li>
            <li><strong>Safari:</strong> Preferences &gt; Privacy &gt; Manage Website Data</li>
            <li><strong>Edge:</strong> Settings &gt; Cookies and site permissions &gt; Manage and delete cookies</li>
          </ul>

          <h2>5. Third-Party Cookies</h2>
          <p>
            Our Service may include integrations with third-party services that set their own cookies.
            These may include:
          </p>
          <ul>
            <li><strong>Payment providers (Stripe/GoCardless):</strong> May set cookies during the payment process for fraud prevention and session management</li>
            <li><strong>Identity verification providers:</strong> May set cookies during document capture and verification flows</li>
          </ul>
          <p>
            We do not control these third-party cookies. Please refer to the relevant third party's
            cookie policy for more information.
          </p>

          <h2>6. Do Not Track</h2>
          <p>
            Some browsers offer a "Do Not Track" (DNT) feature. Since there is no universally accepted
            standard for how to respond to DNT signals, we do not currently respond to them. However,
            as we do not use tracking or marketing cookies, this has no practical impact on your
            experience.
          </p>

          <h2>7. Updates to This Policy</h2>
          <p>
            We may update this Cookie Policy from time to time to reflect changes in our practices or
            for other operational, legal, or regulatory reasons. The "Last updated" date at the top of
            this page indicates when it was last revised.
          </p>

          <h2>8. Contact Us</h2>
          <p>
            If you have any questions about our use of cookies or this Cookie Policy, please contact us:
          </p>
          <ul>
            <li>Email: <a href={`mailto:${brand.contact.email}`}>{brand.contact.email}</a></li>
            <li>Phone: {brand.contact.phone}</li>
          </ul>

          <h2>9. More Information</h2>
          <p>
            For more information about cookies, including how to see what cookies have been set and how
            to manage and delete them, visit{' '}
            <a href="https://www.aboutcookies.org" target="_blank" rel="noopener noreferrer">
              www.aboutcookies.org
            </a>{' '}
            or{' '}
            <a href="https://www.allaboutcookies.org" target="_blank" rel="noopener noreferrer">
              www.allaboutcookies.org
            </a>.
          </p>
          <p>
            For information about the ICO's guidance on cookies, visit{' '}
            <a href="https://ico.org.uk/for-organisations/guide-to-pecr/cookies-and-similar-technologies/" target="_blank" rel="noopener noreferrer">
              ico.org.uk/cookies
            </a>.
          </p>
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
