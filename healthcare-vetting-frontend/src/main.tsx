import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.tsx'

// ── Sentry: frontend error & performance monitoring ─────────────────────
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN || "";
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "production",
    release: import.meta.env.VITE_SENTRY_RELEASE || "viperai-frontend@1.0.0",
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: false,
        blockAllMedia: false,
      }),
    ],
    tracesSampleRate: 0.2,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  });
}

console.log("Viper AI build 20260408v2");

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<div className="p-8 text-center text-red-600">Something went wrong. Please refresh the page.</div>}>
      <App />
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
