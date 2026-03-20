import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import CandidatePortal from "./pages/CandidatePortal";
import AgencyDashboard from "./pages/AgencyDashboard";
import AdminPanel from "./pages/AdminPanel";

function getInviteCodeFromURL(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("invite");
}

function AppContent() {
  const { isAuthenticated, userType } = useAuth();
  const inviteCode = getInviteCodeFromURL();

  if (!isAuthenticated) {
    return <LoginPage inviteCode={inviteCode} />;
  }

  switch (userType) {
    case "candidate":
      return <CandidatePortal />;
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
