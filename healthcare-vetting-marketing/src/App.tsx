import './App.css'
import { brand, APP_URL } from './config/brand'
import {
  Shield, UserCheck, FileCheck, Award, BarChart3, Brain,
  Lock, Building2, ClipboardCheck, Heart, FileSearch, Download,
  Menu, X, ChevronRight, ArrowRight, Check, Star, Phone, Mail,
  Zap, Clock
} from 'lucide-react'
import { useState } from 'react'

/* ------------------------------------------------------------------ */
/*  Icon resolver — maps string names from brand config to components */
/* ------------------------------------------------------------------ */
const iconMap: Record<string, React.ElementType> = {
  Shield, UserCheck, FileCheck, Award, BarChart3, Brain,
  Lock, Building2, ClipboardCheck, Heart, FileSearch, Download,
  Zap, Clock
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
          {brand.logoUrl ? (
            <img src={brand.logoUrl} alt={brand.logoAlt} className="h-8" />
          ) : (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
                <Shield size={18} className="text-white" />
              </div>
              <span className="text-xl font-bold text-slate-900">{brand.name}</span>
            </div>
          )}
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
            <Zap size={14} /> Trusted by 50+ UK healthcare agencies
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
          <div className="mt-12 grid grid-cols-3 gap-6">
            {[
              { value: '80%', label: 'Faster Onboarding' },
              { value: '15h+', label: 'Saved Per Week' },
              { value: '99.9%', label: 'Uptime SLA' },
            ].map(s => (
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
            onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/800x600/e2e8f0/475569?text=Healthcare+Compliance' }}
          />
          {/* Floating card */}
          <div className="absolute -bottom-6 -left-6 bg-white rounded-xl shadow-xl p-4 flex items-center gap-3 border border-slate-100">
            <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center">
              <Check size={20} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">DBS Check Complete</p>
              <p className="text-xs text-slate-500">Candidate shift-ready</p>
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
  const logos = ['NHS Trusts', 'CQC Regulated', 'Care Homes', 'Nursing Agencies', 'Staffing Groups']
  return (
    <section className="py-12 bg-white border-b border-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <p className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-8">
          Trusted across the UK healthcare sector
        </p>
        <div className="flex flex-wrap justify-center gap-8 md:gap-16">
          {logos.map(name => (
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
            Everything You Need for Compliant Staffing
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            One platform replaces spreadsheets, phone calls, and manual chasing. Automate every step of the vetting process.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {brand.features.map((f, i) => (
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
            From Invite to Shift-Ready in 4 Steps
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            Our platform handles the entire compliance journey — so you can focus on placing candidates, not chasing paperwork.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {brand.howItWorks.map((step, i) => (
            <div key={i} className="relative">
              {/* Connector line */}
              {i < brand.howItWorks.length - 1 && (
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
/*  Compliance / Trust Signals                                        */
/* ------------------------------------------------------------------ */
function Compliance() {
  return (
    <section id="compliance" className="py-20 lg:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <span className="inline-block text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Compliance</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900">
              {brand.compliance.headline}
            </h2>
            <p className="mt-4 text-lg text-slate-600 leading-relaxed">
              {brand.compliance.subheadline}
            </p>

            <div className="mt-10 grid grid-cols-2 gap-4">
              {brand.compliance.badges.map((b, i) => (
                <div key={i} className="flex items-center gap-3 bg-slate-50 rounded-xl p-4 border border-slate-100">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                    <Icon name={b.icon} size={20} className="text-blue-600" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">{b.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <img
              src={brand.images.compliance}
              alt="Healthcare compliance professional reviewing documents"
              className="rounded-2xl shadow-xl w-full object-cover aspect-video"
              onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/800x500/e2e8f0/475569?text=Compliance+Ready' }}
            />
            <div className="absolute -top-4 -right-4 bg-white rounded-xl shadow-lg p-4 border border-slate-100">
              <div className="flex items-center gap-2">
                <Lock size={16} className="text-emerald-600" />
                <span className="text-sm font-semibold text-slate-900">GDPR Compliant</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">End-to-end data protection</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Pricing                                                           */
/* ------------------------------------------------------------------ */
function Pricing() {
  return (
    <section id="pricing" className="py-20 lg:py-28 bg-gradient-to-br from-slate-900 to-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="inline-block text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3">Pricing</span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {brand.pricing.headline}
          </h2>
          <p className="mt-4 text-lg text-slate-400">
            {brand.pricing.subheadline}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {brand.pricing.plans.map((plan, i) => (
            <div
              key={i}
              className={`relative rounded-2xl p-8 transition-all ${
                plan.highlighted
                  ? 'bg-white ring-2 ring-blue-500 shadow-2xl shadow-blue-500/10 scale-105'
                  : 'bg-slate-800/50 border border-slate-700 hover:border-slate-600'
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-xs font-bold px-4 py-1.5 rounded-full uppercase tracking-wider">
                  Most Popular
                </div>
              )}
              <h3 className={`text-lg font-semibold ${plan.highlighted ? 'text-slate-900' : 'text-white'}`}>
                {plan.name}
              </h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className={`text-4xl font-bold ${plan.highlighted ? 'text-slate-900' : 'text-white'}`}>
                  {plan.price}
                </span>
                {plan.period && (
                  <span className={`text-sm ${plan.highlighted ? 'text-slate-500' : 'text-slate-400'}`}>
                    /{plan.period}
                  </span>
                )}
              </div>
              <p className={`mt-2 text-sm ${plan.highlighted ? 'text-slate-600' : 'text-slate-400'}`}>
                {plan.description}
              </p>

              <ul className="mt-8 space-y-3">
                {plan.features.map((f, j) => (
                  <li key={j} className="flex items-start gap-2">
                    <Check size={16} className={`mt-0.5 shrink-0 ${plan.highlighted ? 'text-blue-600' : 'text-blue-400'}`} />
                    <span className={`text-sm ${plan.highlighted ? 'text-slate-600' : 'text-slate-300'}`}>{f}</span>
                  </li>
                ))}
              </ul>

              <a
                href="#contact"
                className={`mt-8 block text-center rounded-xl px-6 py-3 text-sm font-semibold transition-colors ${
                  plan.highlighted
                    ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-600/25'
                    : 'bg-slate-700 text-white hover:bg-slate-600 border border-slate-600'
                }`}
              >
                {plan.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

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
                  <Phone size={20} className="text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Call us</p>
                  <a href={`tel:${brand.contact.phone}`} className="text-blue-600 font-medium hover:underline">
                    {brand.contact.phone}
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
              <form onSubmit={e => { e.preventDefault(); setSubmitted(true) }} className="space-y-5">
                <h3 className="text-lg font-semibold text-slate-900 mb-2">Request a Demo</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
                    <input type="text" required placeholder="John Smith" className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">Work Email</label>
                    <input type="email" required placeholder="john@agency.co.uk" className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Company Name</label>
                  <input type="text" required placeholder="Acme Healthcare Staffing" className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">How many candidates do you process per month?</label>
                  <select className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white">
                    <option>1-25</option>
                    <option>26-50</option>
                    <option>51-200</option>
                    <option>200+</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Message (optional)</label>
                  <textarea rows={3} placeholder="Tell us about your compliance challenges..." className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none" />
                </div>
                <button type="submit" className="w-full rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 transition-colors">
                  Request a Demo <ArrowRight size={16} className="inline ml-1" />
                </button>
                <p className="text-xs text-slate-500 text-center">
                  By submitting, you agree to our Privacy Policy. We&apos;ll never share your data.
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
          Join agencies across the UK who trust {brand.name} to keep their workforce compliant.
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
              {brand.logoUrl ? (
                <img src={brand.logoUrl} alt={brand.logoAlt} className="h-8 brightness-200" />
              ) : (
                <>
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                    <Shield size={18} className="text-white" />
                  </div>
                  <span className="text-xl font-bold text-white">{brand.name}</span>
                </>
              )}
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
            <a href="#" className="text-sm text-slate-500 hover:text-white transition-colors">Privacy</a>
            <a href="#" className="text-sm text-slate-500 hover:text-white transition-colors">Terms</a>
            <a href="#" className="text-sm text-slate-500 hover:text-white transition-colors">Cookies</a>
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
      <Compliance />
      <Pricing />
      <Testimonials />
      <Contact />
      <CtaBanner />
      <Footer />
    </div>
  )
}

export default App
