/**
 * BRAND CONFIGURATION
 * ==================
 * Change ONLY this file to rebrand the entire marketing site.
 * Every component reads from here — no hardcoded brand names anywhere else.
 */

export const brand = {
  // ── Core Identity ──────────────────────────────────────────────
  name: "Viper AI",
  tagline: "Vetting Intelligence Platform for Enterprise Risk",
  description:
    "VIPER — Vetting Intelligence Platform for Enterprise Risk. Streamline background checks, identity verification, right-to-work validation, and professional registration — all from one intelligent platform built for any regulated industry.",

  // ── Logo ───────────────────────────────────────────────────────
  logoUrl: "/viper-logo.png",
  logoAlt: "Viper AI logo",

  // ── Colours (Tailwind classes) ─────────────────────────────────
  colors: {
    primary: "blue-600",
    primaryHover: "blue-700",
    primaryLight: "blue-50",
    primaryDark: "blue-900",
    accent: "emerald-500",
    accentHover: "emerald-600",
    gradient: "from-blue-600 to-indigo-700",
  },

  // ── Navigation ─────────────────────────────────────────────────
  nav: {
    links: [
      { label: "Features", href: "#features" },
      { label: "Industries", href: "#industries" },
      { label: "How It Works", href: "#how-it-works" },
      { label: "Pricing", href: "#pricing" },
      { label: "Contact", href: "#contact" },
    ],
    ctaLabel: "Get Started",
    ctaHref: "#contact",
  },

  // ── Hero Section ───────────────────────────────────────────────
  hero: {
    badge: "Trusted across regulated industries in the UK",
    headline: "Compliance Vetting, Simplified.",
    subheadline:
      "Automate background checks, identity verification, right-to-work, and professional registration for your workforce — in one platform built for healthcare, education, social care, construction, and more.",
    ctaPrimary: "Request a Demo",
    ctaPrimaryHref: "#contact",
    ctaSecondary: "See How It Works",
    ctaSecondaryHref: "#how-it-works",
    image: "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&q=80",
    imageAlt: "Team reviewing compliance dashboard on laptop",
    stats: [
      { value: "80%", label: "Faster Onboarding" },
      { value: "15h+ (40%)", label: "Time saved Per Week" },
      { value: "99.9%", label: "Uptime SLA" },
    ],
  },

  // ── Social Proof Bar ──────────────────────────────────────────
  socialProof: {
    headline: "Trusted across regulated industries",
    logos: ["NHS Trusts", "Care Homes", "Schools & Academies", "Construction Firms", "Staffing Agencies"],
  },

  // ── Features ───────────────────────────────────────────────────
  features: {
    headline: "Everything You Need for Compliant Staffing",
    subheadline: "One platform replaces spreadsheets, phone calls, and manual chasing. Automate every step of the vetting process — for any industry.",
    items: [
      {
        icon: "Shield",
        title: "Background Checks",
        description:
          "Automated DBS check submission and tracking. Standard, Enhanced, and Enhanced with Barred List — all managed centrally with real-time status updates.",
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
          "NMC, GMC, HCPC, GPhC, CSCS, and teaching body registration verification with automatic expiry monitoring and renewal alerts.",
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
          "CV gap analysis, reference sentiment scoring, anomaly detection, and smart scheduling — powered by AI with rule-based fallbacks.",
      },
    ],
  },

  // ── Industry Compliance Carousel ──────────────────────────────
  industries: {
    headline: "Built for Every Regulated Industry",
    subheadline:
      "One platform, configured for your sector. Select an industry below to see the specific compliance checks we automate.",
    sectors: [
      {
        name: "Healthcare",
        icon: "Heart",
        color: "rose",
        checks: [
          { label: "Enhanced DBS with Barred List", icon: "Shield" },
          { label: "NMC / GMC / HCPC Registration", icon: "Award" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "CQC Compliance Ready", icon: "ClipboardCheck" },
          { label: "Occupational Health Clearance", icon: "UserCheck" },
          { label: "Mandatory Training Records", icon: "FileSearch" },
          { label: "Reference Verification (2+ refs)", icon: "UserCheck" },
          { label: "Hepatitis B / Immunisation Status", icon: "Heart" },
        ],
      },
      {
        name: "Education",
        icon: "GraduationCap",
        color: "amber",
        checks: [
          { label: "Enhanced DBS with Children's Barred List", icon: "Shield" },
          { label: "Teaching Regulation Agency (TRA) Check", icon: "Award" },
          { label: "QTS / QTLS Verification", icon: "Award" },
          { label: "Section 128 Direction Check", icon: "ClipboardCheck" },
          { label: "Prohibition Order Check", icon: "FileSearch" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "Overseas Criminal Record Check", icon: "Shield" },
          { label: "Reference Verification (2+ refs)", icon: "UserCheck" },
        ],
      },
      {
        name: "Social Care",
        icon: "Users",
        color: "purple",
        checks: [
          { label: "Enhanced DBS with Adults' Barred List", icon: "Shield" },
          { label: "Social Work England Registration", icon: "Award" },
          { label: "CQC Compliance Checks", icon: "ClipboardCheck" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "Safeguarding Training Records", icon: "FileSearch" },
          { label: "Mental Capacity Act Training", icon: "Brain" },
          { label: "Reference Verification (2+ refs)", icon: "UserCheck" },
          { label: "Health Declaration", icon: "Heart" },
        ],
      },
      {
        name: "Construction",
        icon: "HardHat",
        color: "orange",
        checks: [
          { label: "CSCS Card Verification", icon: "Award" },
          { label: "Standard DBS Check", icon: "Shield" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "CITB Training Records", icon: "FileSearch" },
          { label: "Health & Safety Certifications", icon: "ClipboardCheck" },
          { label: "CPCS / NPORS Licence Checks", icon: "Award" },
          { label: "Asbestos Awareness Certification", icon: "Shield" },
          { label: "Working at Height Certificate", icon: "FileSearch" },
        ],
      },
      {
        name: "Finance & Legal",
        icon: "Landmark",
        color: "sky",
        checks: [
          { label: "Basic / Standard DBS Check", icon: "Shield" },
          { label: "FCA / SRA Registration Check", icon: "Award" },
          { label: "Credit Check (CIFAS / Experian)", icon: "BarChart3" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "Anti-Money Laundering (AML) Training", icon: "Lock" },
          { label: "Professional Indemnity Insurance", icon: "ClipboardCheck" },
          { label: "Reference Verification (2+ refs)", icon: "UserCheck" },
          { label: "Conflict of Interest Declaration", icon: "FileSearch" },
        ],
      },
      {
        name: "Security",
        icon: "ShieldCheck",
        color: "slate",
        checks: [
          { label: "Enhanced DBS Check", icon: "Shield" },
          { label: "SIA Licence Verification", icon: "Award" },
          { label: "Right to Work Verification", icon: "FileCheck" },
          { label: "Counter-Terrorism Training", icon: "Lock" },
          { label: "First Aid Certification", icon: "Heart" },
          { label: "Physical Fitness Declaration", icon: "UserCheck" },
          { label: "Reference Verification (2+ refs)", icon: "UserCheck" },
          { label: "CCTV Operation Certification", icon: "FileSearch" },
        ],
      },
    ],
    globalBadges: [
      { label: "GDPR Compliant", icon: "Lock" },
      { label: "ICO Registered", icon: "Building2" },
      { label: "Tamper-Evident Audit Trail", icon: "FileSearch" },
      { label: "Data Portability (Art. 20)", icon: "Download" },
    ],
  },

  // ── How It Works ───────────────────────────────────────────────
  howItWorks: {
    headline: "From Invite to Work-Ready in 4 Steps",
    subheadline: "Our platform handles the entire compliance journey — so you can focus on placing candidates, not chasing paperwork.",
    steps: [
      {
        step: "1",
        title: "Invite Candidates",
        description:
          "Send a single invitation link. Candidates fill in personal details, upload documents, and provide referee contacts — all in one portal.",
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
        title: "Work-Ready Candidates",
        description:
          "Once all checks pass, candidates are marked work-ready. Agencies see a clear green light before deploying staff.",
      },
    ],
  },

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
    email: "hello@viperai.io",
    phone: "+44 (0) 20 1234 5678",
    formFields: ["name", "email", "company", "industry", "message"],
  },

  // ── Footer ─────────────────────────────────────────────────────
  footer: {
    copyright: `${new Date().getFullYear()} Viper AI. All rights reserved.`,
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
        title: "Industries",
        links: [
          { label: "Healthcare", href: "#industries" },
          { label: "Education", href: "#industries" },
          { label: "Social Care", href: "#industries" },
          { label: "Construction", href: "#industries" },
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
    hero: "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&q=80",
    howItWorks: "https://images.unsplash.com/photo-1516841273335-e39b37888115?w=800&q=80",
    compliance: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&q=80",
    about: "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=800&q=80",
  },
} as const;

// Helper: get the app URL for "Log In" / "Sign Up" buttons
export const APP_URL = import.meta.env.VITE_APP_URL || "https://app.viperai.io";
