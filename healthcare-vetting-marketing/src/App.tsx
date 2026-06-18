import './App.css'
import { brand, APP_URL } from './config/brand'
import {
  Shield, UserCheck, FileCheck, Award, BarChart3, Brain,
  Lock, Building2, ClipboardCheck, Heart, FileSearch, Download,
  Menu, X, ChevronRight, ArrowRight, Check, Star, Mail,
  Zap, Clock, ChevronLeft, GraduationCap, Users, HardHat, Landmark, ShieldCheck
} from 'lucide-react'
import { useState } from 'react'

/* ------------------------------------------------------------------ */
/*  Icon resolver — maps string names from brand config to components */
/* ------------------------------------------------------------------ */
const iconMap: Record<string, React.ElementType> = {
  Shield, UserCheck, FileCheck, Award, BarChart3, Brain,
  Lock, Building2, ClipboardCheck, Heart, FileSearch, Download,
  Zap, Clock, GraduationCap, Users, HardHat, Landmark, ShieldCheck
}

function Icon({ name, size = 24, className = '' }: { name: string; size?: number; className?: string }) {
  const Comp = iconMap[name]
  if (!Comp) return null
  return <Comp size={size} className={className} />
}

/* ------------------------------------------------------------------ */
/*  Navbar                                                            */
/* ------------------------------------------------------------------ */
function Navbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2">
          <img src={brand.logoUrl || ''} alt={brand.logoAlt} className="h-10" />
          <span className="text-xl font-bold text-slate-900">{brand.name}</span>
        </a>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {brand.nav.links.map(l => (
            <a key={l.href} href={l.href} className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors">
              {l.label}
            </a>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-4">
          <a href={APP_URL} className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors">
            Log In
          </a>
          <a href={brand.nav.ctaHref} className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700 transition-colors">
            {brand.nav.ctaLabel} <ArrowRight size={14} />
          </a>
        </div>

        {/* Mobile toggle */}
        <button onClick={() => setOpen(!open)} className="md:hidden p-2 text-slate-600">
          {open ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-white border-t border-slate-200 px-4 pb-4">
          {brand.nav.links.map(l => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="block py-3 text-slate-700 font-medium border-b border-slate-100">
              {l.label}
            </a>
          ))}
          <div className="flex flex-col gap-3 mt-4">
            <a href={APP_URL} className="text-center text-sm font-medium text-slate-600 py-2">Log In</a>
            <a href={brand.nav.ctaHref} onClick={() => setOpen(false)} className="text-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white">
              {brand.nav.ctaLabel}
            </a>
          </div>
        </div>
      )}
    </header>
  )
}

/* ------------------------------------------------------------------ */
/*  Hero                                                              */
/* ------------------------------------------------------------------ */
function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-slate-50 to-blue-50 pt-32 pb-20 lg:pt-40 lg:pb-28">
      {/* Decorative blobs */}
      <div className="absolute -top-40 -right-40 w-96 h-96 bg-blue-200 rounded-full opacity-20 blur-3xl" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-200 rounded-full opacity-20 blur-3xl" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-100 text-blue-700 px-4 py-1.5 text-sm font-medium mb-6">
            <Zap size={14} /> {brand.hero.badge}
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 leading-tight tracking-tight">
            {brand.hero.headline}
          </h1>
          <p className="mt-6 text-lg text-slate-600 leading-relaxed max-w-xl">
            {brand.hero.subheadline}
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <a href={brand.hero.ctaPrimaryHref} className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 transition-all hover:shadow-xl hover:shadow-blue-600/30">
              {brand.hero.ctaPrimary} <ArrowRight size={18} />
            </a>
            <a href={brand.hero.ctaSecondaryHref} className="inline-flex items-center gap-2 rounded-xl border-2 border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:border-blue-400 hover:text-blue-600 transition-colors">
              {brand.hero.ctaSecondary} <ChevronRight size={18} />
            </a>
          </div>

          {/* Quick stats */}
          <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-6">
            {brand.hero.stats.map(s => (
              <div key={s.label}>
                <p className="text-2xl font-bold text-blue-600">{s.value}</p>
                <p className="text-sm text-slate-500">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Hero image */}
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-600/10 to-indigo-600/10 rounded-2xl" />
          <img
            src={brand.hero.image}
            alt={brand.hero.imageAlt}
            className="relative rounded-2xl shadow-2xl w-full object-cover aspect-square lg:aspect-auto lg:h-auto"
            onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/800x600/e2e8f0/475569?text=Compliance+Platform' }}
          />
          {/* Floating card */}
          <div className="hidden sm:flex absolute -bottom-6 -left-6 bg-white rounded-xl shadow-xl p-4 items-center gap-3 border border-slate-100">
            <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center">
              <Check size={20} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">All Checks Complete</p>
              <p className="text-xs text-slate-500">Candidate work-ready</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Logos / Social Proof Bar                                          */
/* ------------------------------------------------------------------ */
function LogoBar() {
  return (
    <section className="py-12 bg-white border-b border-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <p className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-8">
          {brand.socialProof.headline}
        </p>
        <div className="flex flex-wrap justify-center gap-8 md:gap-16">
          {brand.socialProof.logos.map(name => (
            <div key={name} className="flex items-center gap-2 text-slate-400">
              <Building2 size={20} />
              <span className="text-sm font-medium">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Features                                                          */
/* ------------------------------------------------------------------ */
function Features() {
  return (
    <section id="features" className="py-20 lg:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Features</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
            {brand.features.headline}
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            {brand.features.subheadline}
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {brand.features.items.map((f, i) => (
            <div key={i} className="group relative bg-white rounded-2xl border border-slate-200 p-8 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-50 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-5 group-hover:bg-blue-100 transition-colors">
                <Icon name={f.icon} size={24} className="text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">{f.title}</h3>
              <p className="text-slate-600 leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  How It Works                                                      */
/* ------------------------------------------------------------------ */
function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 lg:py-28 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">How It Works</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
            {brand.howItWorks.headline}
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            {brand.howItWorks.subheadline}
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {brand.howItWorks.steps.map((step, i) => (
            <div key={i} className="relative">
              {/* Connector line */}
              {i < brand.howItWorks.steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-full w-full h-0.5 bg-blue-200 -translate-x-4 z-0" />
              )}
              <div className="relative bg-white rounded-2xl p-8 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center mb-5 text-white font-bold text-xl shadow-lg shadow-blue-600/20">
                  {step.step}
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">{step.title}</h3>
                <p className="text-slate-600 leading-relaxed text-sm">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Industry Compliance Carousel                                      */
/* ------------------------------------------------------------------ */
function IndustryCarousel() {
  const sectors = brand.industries.sectors
  const [activeIdx, setActiveIdx] = useState(0)
  const active = sectors[activeIdx]

  const prev = () => setActiveIdx(i => (i - 1 + sectors.length) % sectors.length)
  const next = () => setActiveIdx(i => (i + 1) % sectors.length)

  return (
    <section id="industries" className="py-20 lg:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Industries</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
            {brand.industries.headline}
          </h2>
          <p className="mt-4 text-lg text-slate-600 leading-relaxed">
            {brand.industries.subheadline}
          </p>
        </div>

        {/* Industry Tabs — scrollable on mobile */}
        <div className="relative mb-10">
          <div className="flex items-center gap-2">
            <button onClick={prev} className="shrink-0 w-9 h-9 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors">
              <ChevronLeft size={18} />
            </button>

            <div className="flex-1 overflow-x-auto scrollbar-hide">
              <div className="flex gap-2 min-w-max px-1 py-1">
                {sectors.map((s, i) => (
                  <button
                    key={s.name}
                    onClick={() => setActiveIdx(i)}
                    className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium whitespace-nowrap transition-all ${
                      i === activeIdx
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    <Icon name={s.icon} size={16} className={i === activeIdx ? 'text-white' : 'text-slate-500'} />
                    {s.name}
                  </button>
                ))}
              </div>
            </div>

            <button onClick={next} className="shrink-0 w-9 h-9 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors">
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        {/* Active industry checks */}
        <div className="bg-gradient-to-br from-slate-50 to-blue-50 rounded-2xl border border-slate-200 p-8 lg:p-12">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
              <Icon name={active.icon} size={24} className="text-blue-600" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-slate-900">{active.name} Compliance</h3>
              <p className="text-sm text-slate-500">{active.checks.length} automated checks</p>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {active.checks.map((c, i) => (
              <div key={i} className="flex items-start gap-3 bg-white rounded-xl p-4 border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center shrink-0 mt-0.5">
                  <Icon name={c.icon} size={18} className="text-blue-600" />
                </div>
                <span className="text-sm font-medium text-slate-700 leading-snug">{c.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Global trust badges */}
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          {brand.industries.globalBadges.map((b, i) => (
            <div key={i} className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600">
              <Icon name={b.icon} size={16} className="text-blue-600" />
              {b.label}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* Pricing section hidden — uncomment when ready to display
function Pricing() { ... }
*/

/* ------------------------------------------------------------------ */
/*  Testimonials                                                      */
/* ------------------------------------------------------------------ */
function Testimonials() {
  return (
    <section className="py-20 lg:py-28 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Testimonials</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
            Loved by Compliance Teams
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {brand.testimonials.map((t, i) => (
            <div key={i} className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex gap-1 mb-4">
                {[...Array(5)].map((_, j) => (
                  <Star key={j} size={16} className="text-amber-400 fill-amber-400" />
                ))}
              </div>
              <blockquote className="text-slate-700 leading-relaxed mb-6">
                &ldquo;{t.quote}&rdquo;
              </blockquote>
              <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
                  {t.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{t.name}</p>
                  <p className="text-xs text-slate-500">{t.role}, {t.company}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Contact / CTA                                                     */
/* ------------------------------------------------------------------ */
function Contact() {
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [formData, setFormData] = useState({ name: '', email: '', company: '', candidates_per_month: '1-25', message: '' })

  const API_URL = import.meta.env.VITE_API_URL || 'https://api.viperai.io'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/api/auth/demo-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(typeof err.detail === 'string' ? err.detail : 'Request failed')
      }
      setSubmitted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section id="contact" className="py-20 lg:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16">
          <div>
            <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Get Started</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
              {brand.contact.headline}
            </h2>
            <p className="mt-4 text-lg text-slate-600 leading-relaxed">
              {brand.contact.subheadline}
            </p>

            <div className="mt-10 space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                  <Mail size={20} className="text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Email us</p>
                  <a href={`mailto:${brand.contact.email}`} className="text-blue-600 font-medium hover:underline">
                    {brand.contact.email}
                  </a>
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
            </div>
          </div>

          {/* Contact form */}
          <div className="bg-slate-50 rounded-2xl p-8 border border-slate-200">
            {submitted ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                  <Check size={32} className="text-emerald-600" />
                </div>
                <h3 className="text-xl font-semibold text-slate-900 mb-2">Message Sent!</h3>
                <p className="text-slate-600">We&apos;ll be in touch within 2 business hours.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <h3 className="text-lg font-semibold text-slate-900 mb-2">Request a Demo</h3>
                {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200">{error}</p>}
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
                    <input type="text" required placeholder="John Smith" value={formData.name} onChange={e => setFormData(f => ({ ...f, name: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">Work Email</label>
                    <input type="email" required placeholder="john@agency.co.uk" value={formData.email} onChange={e => setFormData(f => ({ ...f, email: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Company Name</label>
                  <input type="text" required placeholder="Acme Staffing Ltd" value={formData.company} onChange={e => setFormData(f => ({ ...f, company: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">How many candidates do you process per month?</label>
                  <select value={formData.candidates_per_month} onChange={e => setFormData(f => ({ ...f, candidates_per_month: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white">
                    <option>1-25</option>
                    <option>26-50</option>
                    <option>51-200</option>
                    <option>200+</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Message (optional)</label>
                  <textarea rows={3} placeholder="Tell us about your compliance challenges..." value={formData.message} onChange={e => setFormData(f => ({ ...f, message: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none" />
                </div>
                <button type="submit" disabled={submitting} className="w-full rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                  {submitting ? 'Submitting...' : 'Request a Demo'} {!submitting && <ArrowRight size={16} className="inline ml-1" />}
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
  )
}

/* ------------------------------------------------------------------ */
/*  Final CTA Banner                                                  */
/* ------------------------------------------------------------------ */
function CtaBanner() {
  return (
    <section className="py-16 bg-gradient-to-r from-blue-600 to-indigo-700">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-bold text-white">
          Start Vetting Smarter Today
        </h2>
        <p className="mt-4 text-lg text-blue-100">
          Join organisations across the UK who trust {brand.name} to keep their workforce compliant.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <a href="#contact" className="inline-flex items-center gap-2 rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-blue-700 shadow-lg hover:bg-blue-50 transition-colors">
            Request a Demo <ArrowRight size={18} />
          </a>
          <a href={APP_URL} className="inline-flex items-center gap-2 rounded-xl border-2 border-white/40 px-8 py-3.5 text-base font-semibold text-white hover:bg-white/10 transition-colors">
            Log In to Dashboard
          </a>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Footer                                                            */
/* ------------------------------------------------------------------ */
function Footer() {
  return (
    <footer className="bg-slate-900 pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-12 pb-12 border-b border-slate-800">
          {/* Brand column */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <img src={brand.logoUrl || ''} alt={brand.logoAlt} className="h-10 brightness-200" />
              <span className="text-xl font-bold text-white">{brand.name}</span>
            </div>
            <p className="text-slate-400 text-sm leading-relaxed max-w-xs">
              {brand.description}
            </p>
            <div className="mt-6 text-xs text-slate-500 space-y-1">
              <p>{brand.footer.companyReg}</p>
              <p>{brand.footer.icoRef}</p>
            </div>
          </div>

          {/* Link columns */}
          {brand.footer.columns.map((col, i) => (
            <div key={i}>
              <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">{col.title}</h4>
              <ul className="space-y-2.5">
                {col.links.map((link, j) => (
                  <li key={j}>
                    <a href={link.href} className="text-sm text-slate-400 hover:text-white transition-colors">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-sm text-slate-500">&copy; {brand.footer.copyright}</p>
          <div className="flex items-center gap-6">
            <a href="/privacy-policy.html" className="text-sm text-slate-500 hover:text-white transition-colors">Privacy</a>
            <a href="/terms-of-service.html" className="text-sm text-slate-500 hover:text-white transition-colors">Terms</a>
            <a href="/cookie-policy.html" className="text-sm text-slate-500 hover:text-white transition-colors">Cookies</a>
          </div>
        </div>
      </div>
    </footer>
  )
}

/* ------------------------------------------------------------------ */
/*  App                                                               */
/* ------------------------------------------------------------------ */
function App() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <Hero />
      <LogoBar />
      <Features />
      <HowItWorks />
      <IndustryCarousel />
      {/* <Pricing /> */}
      <Testimonials />
      <Contact />
      <CtaBanner />
      <Footer />
    </div>
  )
}

export default App
