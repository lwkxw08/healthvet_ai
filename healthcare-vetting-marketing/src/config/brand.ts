/**
 * BRAND CONFIGURATION
 * ==================
 * Change ONLY this file to rebrand the entire marketing site.
 * Every component reads from here — no hardcoded brand names anywhere else.
 */

export const brand = {
  // ── Core Identity ──────────────────────────────────────────────
  name: "HealthVet AI",
  tagline: "Automated Compliance Vetting for Healthcare Agencies",
  description:
    "Streamline DBS checks, right-to-work verification, identity validation, and professional registration — all from one intelligent platform.",

  // ── Logo ───────────────────────────────────────────────────────
  // Replace with your own logo file in /public/images/logo.svg (or .png)
  // Set to "" to use the text-only logo fallback
  logoUrl: "",
  logoAlt: "HealthVet AI logo",

  // ── Colours (Tailwind classes) ─────────────────────────────────
  colors: {
    primary: "blue-600",       // buttons, links, accents
    primaryHover: "blue-700",
    primaryLight: "blue-50",   // light backgrounds
    primaryDark: "blue-900",   // dark text on light bg
    accent: "emerald-500",     // success / secondary accent
    accentHover: "emerald-600",
    gradient: "from-blue-600 to-indigo-700", // hero gradient
  },

  // ── Navigation ─────────────────────────────────────────────────
  nav: {
    links: [
      { label: "Features", href: "#features" },
      { label: "How It Works", href: "#how-it-works" },
      { label: "Pricing", href: "#pricing" },
      { label: "Compliance", href: "#compliance" },
      { label: "Contact", href: "#contact" },
    ],
    ctaLabel: "Get Started",
    ctaHref: "#contact",
  },

  // ── Hero Section ───────────────────────────────────────────────
  hero: {
    headline: "Compliance Vetting, Simplified.",
    subheadline:
      "Automate DBS checks, identity verification, right-to-work, and professional registration for your healthcare workforce — in one platform.",
    ctaPrimary: "Request a Demo",
    ctaPrimaryHref: "#contact",
    ctaSecondary: "See How It Works",
    ctaSecondaryHref: "#how-it-works",
    image: "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800&q=80",
    imageAlt: "Healthcare professional using laptop with stethoscope nearby",
  },

  // ── Features ───────────────────────────────────────────────────
  features: [
    {
      icon: "Shield",
      title: "DBS & Background Checks",
      description:
        "Automated DBS check submission and tracking with TrustID integration. Standard, Enhanced, and Enhanced with Barred List — all managed centrally.",
    },
    {
      icon: "UserCheck",
      title: "Identity Verification",
      description:
        "Secure digital identity verification with document scanning, selfie matching, and fraud detection powered by AI.",
    },
    {
      icon: "FileCheck",
      title: "Right to Work",
      description:
        "Automated RTW checks with share-code validation, visa expiry tracking, and imposter check declaration for full compliance.",
    },
    {
      icon: "Award",
      title: "Professional Registration",
      description:
        "NMC, GMC, HCPC, and GPhC registration verification with automatic expiry monitoring and renewal alerts.",
    },
    {
      icon: "BarChart3",
      title: "Compliance Dashboard",
      description:
        "Real-time compliance scoring per candidate, per agency, per industry. Weighted checks, configurable thresholds, and audit-ready reports.",
    },
    {
      icon: "Brain",
      title: "AI-Powered Insights",
      description:
        "CV gap analysis, reference sentiment scoring, anomaly detection, and smart scheduling — powered by GPT-4o-mini with rule-based fallbacks.",
    },
  ],

  // ── How It Works ───────────────────────────────────────────────
  howItWorks: [
    {
      step: "1",
      title: "Invite Candidates",
      description:
        "Agency sends a single invitation link. Candidate fills in personal details, uploads documents, and provides referee contacts.",
    },
    {
      step: "2",
      title: "Automated Processing",
      description:
        "Background checks, reference requests, and employment verifications are triggered automatically. No manual chasing required.",
    },
    {
      step: "3",
      title: "Real-Time Tracking",
      description:
        "Admin dashboard shows live compliance scores, pending tasks, and alerts. Notification bell keeps you on top of every action item.",
    },
    {
      step: "4",
      title: "Shift-Ready Candidates",
      description:
        "Once all checks pass, candidates are marked shift-ready. Agencies see a clear green light before deploying staff.",
    },
  ],

  // ── Pricing ────────────────────────────────────────────────────
  pricing: {
    headline: "Simple, Transparent Pricing",
    subheadline: "Pay per check or subscribe for volume discounts. No hidden fees.",
    plans: [
      {
        name: "Pay As You Go",
        price: "From $4",
        period: "per check",
        description: "Perfect for agencies with variable volume",
        features: [
          "All check types included",
          "Per-candidate billing",
          "Email notifications",
          "Compliance dashboard",
          "Standard support",
        ],
        cta: "Get Started",
        highlighted: false,
      },
      {
        name: "Professional",
        price: "$299",
        period: "per month",
        description: "For growing agencies processing 50+ candidates/month",
        features: [
          "Everything in PAYG",
          "Volume credit discounts",
          "Credit rollover",
          "AI-powered insights",
          "Priority support",
          "Sub-account management",
          "Custom email branding",
        ],
        cta: "Request a Demo",
        highlighted: true,
      },
      {
        name: "Enterprise",
        price: "Custom",
        period: "",
        description: "For large organisations with complex requirements",
        features: [
          "Everything in Professional",
          "Dedicated account manager",
          "Custom integrations",
          "SLA guarantee",
          "On-premise option",
          "Multi-industry templates",
          "Webhook & API access",
        ],
        cta: "Contact Sales",
        highlighted: false,
      },
    ],
  },

  // ── Compliance / Trust Signals ─────────────────────────────────
  compliance: {
    headline: "Built for Regulated Industries",
    subheadline:
      "Designed from the ground up to meet UK healthcare compliance requirements — and configurable for education, social care, construction, and more.",
    badges: [
      { label: "GDPR Compliant", icon: "Lock" },
      { label: "ICO Registered", icon: "Building2" },
      { label: "CQC Ready", icon: "ClipboardCheck" },
      { label: "NHS Compatible", icon: "Heart" },
      { label: "Tamper-Evident Audit Trail", icon: "FileSearch" },
      { label: "Data Portability (Art. 20)", icon: "Download" },
    ],
  },

  // ── Testimonials ───────────────────────────────────────────────
  testimonials: [
    {
      quote:
        "We cut our onboarding time from 3 weeks to 4 days. The automated reference chasing alone saved us 15 hours a week.",
      name: "Sarah Mitchell",
      role: "Compliance Manager",
      company: "MedStaff Solutions",
    },
    {
      quote:
        "The compliance dashboard gives us instant visibility across 200+ active candidates. No more spreadsheets.",
      name: "James Okafor",
      role: "Operations Director",
      company: "CareLink Recruitment",
    },
    {
      quote:
        "Being able to configure industry-specific templates means we use one platform for healthcare AND education placements.",
      name: "Emma Richardson",
      role: "Managing Director",
      company: "Apex Staffing Group",
    },
  ],

  // ── Contact / CTA ─────────────────────────────────────────────
  contact: {
    headline: "Ready to Streamline Your Compliance?",
    subheadline:
      "Book a 15-minute demo and see how we can cut your vetting time by 80%.",
    email: "hello@healthvet.ai",
    phone: "+44 (0) 20 1234 5678",
    formFields: ["name", "email", "company", "message"],
  },

  // ── Footer ─────────────────────────────────────────────────────
  footer: {
    copyright: `${new Date().getFullYear()} HealthVet AI. All rights reserved.`,
    companyReg: "Company Reg: 12345678",
    icoRef: "ICO Registration: ZA123456",
    columns: [
      {
        title: "Product",
        links: [
          { label: "Features", href: "#features" },
          { label: "Pricing", href: "#pricing" },
          { label: "How It Works", href: "#how-it-works" },
          { label: "API Docs", href: "#" },
        ],
      },
      {
        title: "Company",
        links: [
          { label: "About", href: "#" },
          { label: "Careers", href: "#" },
          { label: "Blog", href: "#" },
          { label: "Contact", href: "#contact" },
        ],
      },
      {
        title: "Legal",
        links: [
          { label: "Privacy Policy", href: "#" },
          { label: "Terms of Service", href: "#" },
          { label: "Cookie Policy", href: "#" },
          { label: "GDPR", href: "#" },
        ],
      },
    ],
  },

  // ── Images (Unsplash) ─────────────────────────────────────────
  images: {
    hero: "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800&q=80",
    howItWorks: "https://images.unsplash.com/photo-1516841273335-e39b37888115?w=800&q=80",
    compliance: "https://images.unsplash.com/photo-1584432810601-6c7f27d2362b?w=800&q=80",
    about: "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=800&q=80",
  },
} as const;

// Helper: get the app URL for "Log In" / "Sign Up" buttons
export const APP_URL = import.meta.env.VITE_APP_URL || "https://app-wwjesgoe.fly.dev";
