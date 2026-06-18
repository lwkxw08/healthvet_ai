/**
 * QR Code Expo Landing Page
 *
 * Custom landing page for prospects who scan a QR code at an expo.
 * Features: platform overview, industry benefits, video placeholder,
 * free first candidate vetting check offer, and contact form.
 */
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Shield, UserCheck, FileCheck, Award, Brain, BarChart3,
  Check, ArrowRight, Play, ChevronRight, Star,
  Heart, GraduationCap, Users, HardHat, Landmark, ShieldCheck,
  Clock, Mail, Phone, Sparkles, Gift,
} from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'https://api.viperai.io'
const APP_URL = import.meta.env.VITE_APP_URL || 'https://app.viperai.io'

const iconMap: Record<string, React.ElementType> = {
  Shield, UserCheck, FileCheck, Award, Brain, BarChart3,
  Heart, GraduationCap, Users, HardHat, Landmark, ShieldCheck,
}

function Icon({ name, size = 24, className = '' }: { name: string; size?: number; className?: string }) {
  const Comp = iconMap[name]
  if (!Comp) return null
  return <Comp size={size} className={className} />
}

const industries = [
  { name: 'Healthcare', icon: 'Heart', checks: ['Enhanced DBS', 'NMC/GMC Registration', 'Right to Work', 'Employment History', 'ID Verification', 'Mandatory Training', 'References', 'CV Validation'] },
  { name: 'Education', icon: 'GraduationCap', checks: ['Enhanced DBS + Barred List', 'TRA Check', 'QTS Verification', 'Section 128 Check', 'Right to Work', 'References'] },
  { name: 'Social Care', icon: 'Users', checks: ['Enhanced DBS + Adults Barred', 'Social Work England Reg', 'CQC Compliance', 'Right to Work', 'Safeguarding Training', 'References'] },
  { name: 'Construction', icon: 'HardHat', checks: ['CSCS Card Verification', 'Standard DBS', 'Right to Work', 'CITB Training', 'H&S Certifications', 'CPCS/NPORS Licences'] },
  { name: 'Finance', icon: 'Landmark', checks: ['Basic/Standard DBS', 'FCA/SRA Registration', 'Credit Check', 'Right to Work', 'AML Training', 'References'] },
  { name: 'Security', icon: 'ShieldCheck', checks: ['Enhanced DBS', 'SIA Licence', 'Right to Work', 'Counter-Terrorism Training', 'First Aid Cert', 'References'] },
]

export default function ExpoLanding() {
  const [searchParams] = useSearchParams()
  const qrCode = searchParams.get('qr') || ''
  const [selectedIndustry, setSelectedIndustry] = useState(0)
  const [formSubmitted, setFormSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [formData, setFormData] = useState({
    name: '', email: '', company: '', phone: '', industry: '', team_size: '', message: '',
  })

  // Track QR scan on page load
  useEffect(() => {
    if (qrCode) {
      fetch(`${API_URL}/api/qr/scan/${qrCode}`, { method: 'POST' }).catch(() => {})
    }
  }, [qrCode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setFormError('')
    try {
      const res = await fetch(`${API_URL}/api/qr/expo-lead`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...formData, qr_code: qrCode }),
      })
      if (!res.ok) throw new Error('Submission failed')
      setFormSubmitted(true)
    } catch {
      setFormError('Something went wrong. Please try again or email us directly.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <a href="/" className="flex items-center gap-2">
            <img src="/viper-logo.png" alt="Viper AI" className="h-10" />
            <span className="text-xl font-bold text-slate-900">Viper AI</span>
          </a>
          <div className="flex items-center gap-4">
            <a href={APP_URL} className="text-sm font-medium text-slate-600 hover:text-blue-600">Log In</a>
            <a href="#contact" className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700">
              Get Started <ArrowRight size={14} />
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900 pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-500/20 text-blue-200 px-5 py-2 text-sm font-medium mb-8 border border-blue-400/20">
            <Gift size={16} /> Exclusive Expo Offer — First Candidate Vetting Check Free
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-tight tracking-tight max-w-4xl mx-auto">
            Automate Your Workforce <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              Compliance Vetting
            </span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-blue-100/80 leading-relaxed max-w-2xl mx-auto">
            Viper AI empowers your compliance team by automating background checks, reference chasing,
            and compliance tracking — so your people can focus on what matters most. Built for any regulated industry.
          </p>

          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <a href="#contact" className="inline-flex items-center gap-2 rounded-xl bg-blue-500 px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-400 transition-all">
              Claim Your Free Trial <ArrowRight size={20} />
            </a>
            <a href="#video" className="inline-flex items-center gap-2 rounded-xl border-2 border-white/20 bg-white/5 px-8 py-4 text-lg font-semibold text-white hover:bg-white/10 transition-all">
              <Play size={20} /> Watch Demo
            </a>
          </div>

          {/* Trust stats */}
          <div className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-8 max-w-3xl mx-auto">
            {[
              { value: '80%', label: 'Faster Onboarding' },
              { value: '15h+', label: 'Saved Per Week' },
              { value: '6', label: 'Industries Covered' },
              { value: '99.9%', label: 'Uptime SLA' },
            ].map(s => (
              <div key={s.label}>
                <p className="text-3xl font-bold text-white">{s.value}</p>
                <p className="text-sm text-blue-200/60">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What is Viper AI */}
      <section className="py-20 lg:py-28 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">The Platform</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
              What is Viper AI?
            </h2>
            <p className="mt-4 text-lg text-slate-600 leading-relaxed">
              VIPER — <strong>Vetting Intelligence Platform for Enterprise Risk</strong>. We automate the entire
              pre-employment screening process: from identity verification and DBS checks to professional
              registration, references, and ongoing compliance monitoring.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              { icon: Shield, title: 'Background Checks', desc: 'Automated DBS submission, tracking, and renewal management. Standard, Enhanced, and Enhanced with Barred List.' },
              { icon: UserCheck, title: 'Identity & Right to Work', desc: 'Digital ID verification with facial matching, liveness detection, and share-code RTW validation.' },
              { icon: Award, title: 'Professional Registration', desc: 'NMC, GMC, HCPC, CSCS, SIA — automatic verification with expiry monitoring and renewal alerts.' },
              { icon: Brain, title: 'AI-Powered Insights', desc: 'CV gap analysis, reference sentiment scoring, fraud detection, and anomaly flagging — all automated.' },
              { icon: BarChart3, title: 'Compliance Dashboard', desc: 'Real-time scores per candidate, configurable thresholds, and audit-ready reporting for CQC/Ofsted.' },
              { icon: Sparkles, title: 'Staged Workflow', desc: 'Two-phase vetting with agency review gates. See full feedback before proceeding — save costs on unsuitable candidates.' },
            ].map((f, i) => (
              <div key={i} className="group bg-white rounded-2xl border border-slate-200 p-8 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-50 transition-all duration-300">
                <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-5 group-hover:bg-blue-100 transition-colors">
                  <f.icon size={24} className="text-blue-600" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-slate-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Video Placeholder */}
      <section id="video" className="py-20 lg:py-28 bg-slate-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">See It In Action</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-8">
            Platform Demo
          </h2>

          {/* Video embed placeholder */}
          <div className="relative aspect-video bg-slate-900 rounded-2xl overflow-hidden border border-slate-200 shadow-2xl group cursor-pointer">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-indigo-600/20" />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-600/30 group-hover:scale-110 transition-transform">
                <Play size={36} className="text-white ml-1" />
              </div>
              <p className="mt-6 text-white/80 text-lg font-medium">Promo video coming soon</p>
              <p className="mt-2 text-white/50 text-sm">Full platform walkthrough and demo</p>
            </div>
            <img
              src="https://images.unsplash.com/photo-1553877522-43269d4ea984?w=1200&q=80"
              alt="Platform demo preview"
              className="w-full h-full object-cover opacity-30"
            />
          </div>
        </div>
      </section>

      {/* Industry Benefits */}
      <section className="py-20 lg:py-28 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Your Industry</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
              Built for Every Regulated Sector
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              One platform, tailored to your industry. We configure the exact compliance checks your sector requires.
            </p>
          </div>

          {/* Industry selector */}
          <div className="flex flex-wrap justify-center gap-2 mb-10">
            {industries.map((ind, i) => (
              <button key={ind.name} onClick={() => setSelectedIndustry(i)}
                className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all ${
                  i === selectedIndustry
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}>
                <Icon name={ind.icon} size={16} className={i === selectedIndustry ? 'text-white' : 'text-slate-500'} />
                {ind.name}
              </button>
            ))}
          </div>

          {/* Selected industry checks */}
          <div className="bg-gradient-to-br from-slate-50 to-blue-50 rounded-2xl border border-slate-200 p-8 lg:p-12">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                <Icon name={industries[selectedIndustry].icon} size={24} className="text-blue-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900">{industries[selectedIndustry].name} Compliance</h3>
                <p className="text-sm text-slate-500">{industries[selectedIndustry].checks.length} automated checks</p>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {industries[selectedIndustry].checks.map((check, i) => (
                <div key={i} className="flex items-center gap-3 bg-white rounded-xl p-4 border border-slate-100">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0">
                    <Check size={16} className="text-emerald-600" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">{check}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Team Potential Section */}
      <section className="py-20 lg:py-28 bg-gradient-to-br from-blue-600 to-indigo-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <span className="inline-block text-sm font-semibold text-blue-200 uppercase tracking-wider mb-3">Your Team</span>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
                Realise the Full Potential of Your Team
              </h2>
              <p className="text-lg text-blue-100/80 leading-relaxed mb-8">
                Your compliance team spends hours on manual checks, phone chasing, and spreadsheet management.
                Viper AI automates up to 80% of these tasks, freeing your team to focus on what matters:
                placing quality candidates and growing your business.
              </p>
              <div className="space-y-4">
                {[
                  { text: 'Eliminate manual reference chasing — automated email sequences with intelligent follow-ups' },
                  { text: 'No more spreadsheet tracking — real-time dashboards with configurable alerts' },
                  { text: 'Reduce compliance risk — automated expiry monitoring and renewal notifications' },
                  { text: 'Faster candidate onboarding — from weeks to days with parallel check processing' },
                  { text: 'Audit-ready at all times — one-click CQC/Ofsted audit packs in branded DOCX format' },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-400/20 flex items-center justify-center shrink-0 mt-0.5">
                      <Check size={14} className="text-blue-200" />
                    </div>
                    <p className="text-blue-100/90">{item.text}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white/10 rounded-2xl p-8 border border-white/10 backdrop-blur-sm">
              <h3 className="text-xl font-bold text-white mb-6">Before vs After Viper AI</h3>
              <div className="space-y-4">
                {[
                  { label: 'Onboarding Time', before: '2-4 weeks', after: '3-5 days' },
                  { label: 'Manual Hours/Week', before: '15+ hours', after: '3 hours' },
                  { label: 'Reference Completion', before: '60-70%', after: '95%+' },
                  { label: 'Audit Preparation', before: '2-3 days', after: '1 click' },
                  { label: 'Compliance Visibility', before: 'Spreadsheets', after: 'Real-time' },
                ].map((row, i) => (
                  <div key={i} className="grid grid-cols-3 gap-4 items-center">
                    <span className="text-sm text-blue-100/70">{row.label}</span>
                    <span className="text-sm text-red-300/80 line-through text-center">{row.before}</span>
                    <span className="text-sm text-emerald-300 font-semibold text-center">{row.after}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Free Offer Banner */}
      <section className="py-16 bg-gradient-to-r from-emerald-500 to-teal-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/20 text-white px-5 py-2 text-sm font-medium mb-6">
            <Gift size={16} /> Exclusive Expo Offer
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            Your First Candidate Vetting Check — Completely Free
          </h2>
          <p className="mt-4 text-lg text-emerald-50/80 max-w-2xl mx-auto">
            Experience the full power of Viper AI with no commitment. We&apos;ll set up a bespoke check template
            matched to your exact industry requirements, and you can run your first candidate vetting check
            at no cost.
          </p>
          <a href="#contact" className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-8 py-4 text-lg font-semibold text-emerald-700 shadow-lg hover:bg-emerald-50 transition-colors">
            Claim Your Free Trial <ChevronRight size={20} />
          </a>
        </div>
      </section>

      {/* Social Proof */}
      <section className="py-16 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { quote: 'We cut our onboarding time from 3 weeks to 4 days. The automated reference chasing alone saved us 15 hours a week.', name: 'Sarah', role: 'Compliance Manager' },
              { quote: 'The compliance dashboard gives us instant visibility across 200+ active candidates. No more spreadsheets.', name: 'James', role: 'Operations Director' },
              { quote: 'Being able to configure industry-specific templates means we use one platform for healthcare AND education placements.', name: 'Emma', role: 'Managing Director' },
            ].map((t, i) => (
              <div key={i} className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm">
                <div className="flex gap-1 mb-4">
                  {[...Array(5)].map((_, j) => (
                    <Star key={j} size={16} className="text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <blockquote className="text-slate-700 leading-relaxed mb-6">&ldquo;{t.quote}&rdquo;</blockquote>
                <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
                    {t.name[0]}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{t.name}</p>
                    <p className="text-xs text-slate-500">{t.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact Form */}
      <section id="contact" className="py-20 lg:py-28 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16">
            <div>
              <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Get Started</span>
              <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
                Set Up Your Bespoke Check Template
              </h2>
              <p className="mt-4 text-lg text-slate-600 leading-relaxed">
                Tell us about your industry and requirements. We&apos;ll configure a custom check template
                tailored to your exact needs — and your first candidate vetting check is on us.
              </p>

              <div className="mt-10 space-y-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                    <Mail size={20} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Email us</p>
                    <a href="mailto:enquiries@viperai.io" className="text-blue-600 font-medium hover:underline">
                      enquiries@viperai.io
                    </a>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                    <Phone size={20} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Call us</p>
                    <p className="text-slate-900 font-medium">Contact via form</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                    <Clock size={20} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Response time</p>
                    <p className="text-slate-900 font-medium">Within 2 business hours</p>
                  </div>
                </div>

                <div className="mt-8 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                  <div className="flex items-center gap-2 text-emerald-700 font-medium mb-1">
                    <Gift size={16} /> Free First Use Case
                  </div>
                  <p className="text-sm text-emerald-600">
                    Mention this expo offer and we&apos;ll set up your template and run your
                    first candidate vetting check completely free of charge.
                  </p>
                </div>
              </div>
            </div>

            {/* Form */}
            <div className="bg-slate-50 rounded-2xl p-8 border border-slate-200">
              {formSubmitted ? (
                <div className="flex flex-col items-center justify-center h-full text-center py-12">
                  <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                    <Check size={32} className="text-emerald-600" />
                  </div>
                  <h3 className="text-xl font-semibold text-slate-900 mb-2">Thank You!</h3>
                  <p className="text-slate-600">We&apos;ll be in touch within 2 business hours to set up your free trial and bespoke check template.</p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">Set Up My Free Trial</h3>
                  {formError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200">{formError}</p>}

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name *</label>
                      <input type="text" required placeholder="John Smith" value={formData.name}
                        onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Work Email *</label>
                      <input type="email" required placeholder="john@agency.co.uk" value={formData.email}
                        onChange={e => setFormData(f => ({ ...f, email: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Company *</label>
                      <input type="text" required placeholder="Acme Staffing Ltd" value={formData.company}
                        onChange={e => setFormData(f => ({ ...f, company: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Phone</label>
                      <input type="tel" placeholder="07700 900000" value={formData.phone}
                        onChange={e => setFormData(f => ({ ...f, phone: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Industry</label>
                      <select value={formData.industry} onChange={e => setFormData(f => ({ ...f, industry: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                        <option value="">Select your industry</option>
                        <option>Healthcare</option>
                        <option>Education</option>
                        <option>Social Care</option>
                        <option>Construction</option>
                        <option>Finance & Legal</option>
                        <option>Security</option>
                        <option>Other</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Team Size</label>
                      <select value={formData.team_size} onChange={e => setFormData(f => ({ ...f, team_size: e.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                        <option value="">How many candidates per month?</option>
                        <option>1-25</option>
                        <option>26-50</option>
                        <option>51-200</option>
                        <option>200+</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">Tell us about your check requirements</label>
                    <textarea rows={3} placeholder="Which checks do you need? Any specific regulatory requirements?" value={formData.message}
                      onChange={e => setFormData(f => ({ ...f, message: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
                  </div>

                  <button type="submit" disabled={submitting}
                    className="w-full rounded-xl bg-blue-600 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 transition-colors disabled:opacity-60">
                    {submitting ? 'Submitting...' : 'Get My Free Trial'} {!submitting && <ArrowRight size={16} className="inline ml-1" />}
                  </button>
                  <p className="text-xs text-slate-500 text-center">
                    By submitting, you agree to our <a href="/privacy-policy.html" className="underline hover:text-blue-600">Privacy Policy</a>. We&apos;ll never share your data.
                  </p>
                </form>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <img src="/viper-logo.png" alt="Viper AI" className="h-8 brightness-200" />
              <span className="text-lg font-bold text-white">Viper AI</span>
            </div>
            <p className="text-sm text-slate-500">
              &copy; {new Date().getFullYear()} Viper AI. All rights reserved. Company Reg: 15822421
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
