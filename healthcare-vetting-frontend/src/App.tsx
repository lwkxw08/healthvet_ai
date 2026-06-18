import { Suspense, lazy } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ImpersonationBanner from "./components/ImpersonationBanner";

// Code-split large page bundles — each loads only when needed
const LoginPage = lazy(() => import("./pages/LoginPage"));
const CandidateOnboarding = lazy(() => import("./pages/CandidateOnboarding"));
const AgencyDashboard = lazy(() => import("./pages/AgencyDashboard"));
const AdminPanel = lazy(() => import("./pages/AdminPanel"));
const VerificationPortal = lazy(() => import("./pages/VerificationPortal"));

function getInviteCodeFromURL(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("invite");
}

function isVerifyRoute(): boolean {
  return window.location.pathname === "/verify" || window.location.pathname.startsWith("/verify/");
}

const LoadingFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
  </div>
);

function AppContent() {
  const { isAuthenticated, userType } = useAuth();
  const inviteCode = getInviteCodeFromURL();

  // /verify is a public route — no auth required
  if (isVerifyRoute()) {
    return <VerificationPortal />;
  }

  if (!isAuthenticated) {
    return <LoginPage inviteCode={inviteCode} />;
  }

  switch (userType) {
    case "candidate":
      return <CandidateOnboarding />;
    case "agency":
      return <AgencyDashboard />;
    case "admin":
      return <AdminPanel />;
    default:
      return <LoginPage inviteCode={inviteCode} />;
  }
}

function App() {
  return (
    <AuthProvider>
      <ImpersonationBanner />
      <Suspense fallback={<LoadingFallback />}>
        <AppContent />
      </Suspense>
    </AuthProvider>
  );
}

export default App;
