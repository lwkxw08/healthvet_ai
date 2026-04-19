import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import CandidateOnboarding from "./pages/CandidateOnboarding";
import AgencyDashboard from "./pages/AgencyDashboard";
import AdminPanel from "./pages/AdminPanel";
import VerificationPortal from "./pages/VerificationPortal";

function getInviteCodeFromURL(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("invite");
}

function isVerifyRoute(): boolean {
  return window.location.pathname === "/verify" || window.location.pathname.startsWith("/verify/");
}

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
      <AppContent />
    </AuthProvider>
  );
}

export default App;
