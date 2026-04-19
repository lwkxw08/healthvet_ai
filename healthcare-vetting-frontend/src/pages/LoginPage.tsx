import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi, agencyInvitesApi } from "../api/client";
import { UserPlus, Building2, Lock, Mail, KeyRound, ArrowLeft, CheckCircle } from "lucide-react";

type LoginTab = "candidate" | "agency" | "admin";
type Mode = "login" | "register" | "forgot_password" | "reset_password";

interface LoginPageProps {
  inviteCode?: string | null;
}

export default function LoginPage({ inviteCode }: LoginPageProps) {
  const { login } = useAuth();
  const [tab, setTab] = useState<LoginTab>("candidate");
  const [mode, setMode] = useState<Mode>(inviteCode ? "register" : "login");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [inviteInfo, setInviteInfo] = useState<{ agency_name: string; candidate_email: string } | null>(null);

  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [profession, setProfession] = useState("");
  const [regNumber, setRegNumber] = useState("");
  const [regBody, setRegBody] = useState("");
  const [agencyName, setAgencyName] = useState("");
  const [contactName, setContactName] = useState("");

  // Load invite info if invite code is present
  useEffect(() => {
    if (inviteCode) {
      agencyInvitesApi.getInviteInfo(inviteCode).then((info) => {
        setInviteInfo(info);
        setEmail(info.candidate_email);
        setTab("candidate");
        setMode("register");
      }).catch(() => {
        setError("Invalid or expired invite code");
      });
    }
  }, [inviteCode]);

  // Password reset states
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetSuccess, setResetSuccess] = useState("");

  // Check URL for reset token
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token");
    if (token) {
      setResetToken(token);
      setMode("reset_password");
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let result;
      if (tab === "candidate") {
        if (mode === "login") {
          result = await authApi.loginCandidate(email, password);
        } else if (mode === "register") {
          result = await authApi.registerCandidate({
            email, password, first_name: firstName, last_name: lastName,
            phone, profession, registration_number: regNumber, registration_body: regBody,
            invite_code: inviteCode || undefined,
          });
        }
      } else if (tab === "agency") {
        if (mode === "login") {
          result = await authApi.loginAgency(email, password);
        } else if (mode === "register") {
          result = await authApi.registerAgency({
            email, password, name: agencyName, contact_name: contactName, phone,
          });
        }
      } else {
        result = await authApi.loginAdmin(email, password);
      }

      if (result) login(result.access_token, result.user_type, result.user_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const userType = tab === "agency" ? "agency" : tab === "admin" ? "admin" : "candidate";
      const resp = await authApi.requestPasswordReset(email, userType);
      if (resp._demo_token) {
        setResetToken(resp._demo_token);
        setResetSuccess("Reset token generated. Enter your new password below.");
        setMode("reset_password");
      } else {
        setResetSuccess(resp.message || "If that email exists, a reset link has been sent.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to request reset");
    } finally { setLoading(false); }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) { setError("Passwords do not match"); return; }
    if (newPassword.length < 8) { setError("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      await authApi.confirmPasswordReset(resetToken, newPassword);
      setResetSuccess("Password reset successfully! You can now sign in.");
      setMode("login");
      setResetToken("");
      setNewPassword("");
      setConfirmPassword("");
      // Clear URL params
      window.history.replaceState({}, "", window.location.pathname);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally { setLoading(false); }
  };

  const tabs: { key: LoginTab; label: string; icon: React.ReactNode }[] = [
    { key: "candidate", label: "Candidate", icon: <UserPlus size={18} /> },
    { key: "agency", label: "Agency", icon: <Building2 size={18} /> },
    { key: "admin", label: "Admin", icon: <Lock size={18} /> },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-3">
            <img src="/viper-logo.png" alt="Viper AI" className="h-12" />
          </div>
          <p className="text-blue-300 text-sm">Vetting Intelligence Platform for Enterprise Risk</p>
        </div>

        {inviteInfo && (
          <div className="mb-4 p-4 bg-blue-500/20 border border-blue-500/30 rounded-xl flex items-center gap-3">
            <Mail className="text-blue-400 flex-shrink-0" size={24} />
            <div>
              <p className="text-blue-200 text-sm font-medium">
                You've been invited by <span className="text-white font-bold">{inviteInfo.agency_name}</span>
              </p>
              <p className="text-blue-300 text-xs mt-0.5">
                Register below to start your vetting process. Your email has been pre-filled.
              </p>
            </div>
          </div>
        )}

        <div className="bg-white/10 backdrop-blur-lg rounded-2xl border border-white/20 p-6 shadow-2xl">
          {/* Tabs */}
          <div className="flex gap-1 mb-6 bg-white/5 rounded-lg p-1">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => { setTab(t.key); setError(""); setMode("login"); }}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-md text-sm font-medium transition-all ${
                  tab === t.key ? "bg-blue-600 text-white shadow-lg" : "text-blue-200 hover:text-white hover:bg-white/10"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-200 text-sm">
              {error}
            </div>
          )}

          {resetSuccess && (
            <div className="mb-4 p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-200 text-sm flex items-center gap-2">
              <CheckCircle size={16} />
              {resetSuccess}
            </div>
          )}

          {/* Password Reset - Request */}
          {mode === "forgot_password" && (
            <form onSubmit={handleForgotPassword} className="space-y-4">
              <div className="text-center mb-2">
                <KeyRound className="text-blue-400 mx-auto mb-2" size={32} />
                <h3 className="text-white font-semibold">Reset Password</h3>
                <p className="text-blue-300 text-xs mt-1">Enter your email to receive a reset link</p>
              </div>
              <div>
                <label className="block text-blue-200 text-xs mb-1">Email</label>
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
              </div>
              <button type="submit" disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-medium py-3 rounded-lg transition-colors shadow-lg">
                {loading ? "Sending..." : "Send Reset Link"}
              </button>
              <button type="button" onClick={() => { setMode("login"); setError(""); setResetSuccess(""); }}
                className="w-full text-blue-400 hover:text-blue-300 text-sm flex items-center justify-center gap-1">
                <ArrowLeft size={14} /> Back to Sign In
              </button>
            </form>
          )}

          {/* Password Reset - Confirm */}
          {mode === "reset_password" && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div className="text-center mb-2">
                <KeyRound className="text-blue-400 mx-auto mb-2" size={32} />
                <h3 className="text-white font-semibold">Set New Password</h3>
                <p className="text-blue-300 text-xs mt-1">Must be at least 8 characters with uppercase, lowercase, and a number</p>
              </div>
              <div>
                <label className="block text-blue-200 text-xs mb-1">New Password</label>
                <input type="password" required value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
              </div>
              <div>
                <label className="block text-blue-200 text-xs mb-1">Confirm Password</label>
                <input type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
              </div>
              <button type="submit" disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-medium py-3 rounded-lg transition-colors shadow-lg">
                {loading ? "Resetting..." : "Reset Password"}
              </button>
              <button type="button" onClick={() => { setMode("login"); setError(""); setResetSuccess(""); }}
                className="w-full text-blue-400 hover:text-blue-300 text-sm flex items-center justify-center gap-1">
                <ArrowLeft size={14} /> Back to Sign In
              </button>
            </form>
          )}

          {(mode === "login" || mode === "register") && <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && tab === "candidate" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-blue-200 text-xs mb-1">First Name</label>
                    <input type="text" required value={firstName} onChange={(e) => setFirstName(e.target.value)}
                      className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                  </div>
                  <div>
                    <label className="block text-blue-200 text-xs mb-1">Last Name</label>
                    <input type="text" required value={lastName} onChange={(e) => setLastName(e.target.value)}
                      className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="block text-blue-200 text-xs mb-1">Phone</label>
                  <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                </div>
                <div>
                  <label className="block text-blue-200 text-xs mb-1">Profession</label>
                  <select value={profession} onChange={(e) => setProfession(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm">
                    <option value="" className="bg-slate-800">Select profession</option>
                    <option value="Nurse" className="bg-slate-800">Nurse</option>
                    <option value="Doctor" className="bg-slate-800">Doctor</option>
                    <option value="Midwife" className="bg-slate-800">Midwife</option>
                    <option value="Physiotherapist" className="bg-slate-800">Physiotherapist</option>
                    <option value="Paramedic" className="bg-slate-800">Paramedic</option>
                    <option value="Pharmacist" className="bg-slate-800">Pharmacist</option>
                    <option value="Other" className="bg-slate-800">Other Healthcare Professional</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-blue-200 text-xs mb-1">Registration Body</label>
                    <select value={regBody} onChange={(e) => setRegBody(e.target.value)}
                      className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm">
                      <option value="" className="bg-slate-800">Select</option>
                      <option value="NMC" className="bg-slate-800">NMC</option>
                      <option value="GMC" className="bg-slate-800">GMC</option>
                      <option value="HCPC" className="bg-slate-800">HCPC</option>
                      <option value="GPhC" className="bg-slate-800">GPhC</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-blue-200 text-xs mb-1">Registration Number</label>
                    <input type="text" value={regNumber} onChange={(e) => setRegNumber(e.target.value)}
                      className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                  </div>
                </div>
              </>
            )}

            {mode === "register" && tab === "agency" && (
              <>
                <div>
                  <label className="block text-blue-200 text-xs mb-1">Agency Name</label>
                  <input type="text" required value={agencyName} onChange={(e) => setAgencyName(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                </div>
                <div>
                  <label className="block text-blue-200 text-xs mb-1">Contact Name</label>
                  <input type="text" value={contactName} onChange={(e) => setContactName(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                </div>
                <div>
                  <label className="block text-blue-200 text-xs mb-1">Phone</label>
                  <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
                </div>
              </>
            )}

            <div>
              <label className="block text-blue-200 text-xs mb-1">Email</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder={tab === "admin" ? "admin@viperai.io" : "you@example.com"}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
            </div>

            <div>
              <label className="block text-blue-200 text-xs mb-1">Password</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={tab === "admin" ? "admin123" : ""}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
            </div>

            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-medium py-3 rounded-lg transition-colors shadow-lg">
              {loading ? "Processing..." : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>}

          {(mode === "login" || mode === "register") && (
            <p className="mt-3 text-center">
              <button onClick={() => { setMode("forgot_password"); setError(""); setResetSuccess(""); }}
                className="text-blue-400/70 hover:text-blue-300 text-xs">
                Forgot your password?
              </button>
            </p>
          )}

          {tab !== "admin" && (mode === "login" || mode === "register") && (
            <p className="mt-2 text-center text-blue-300 text-sm">
              {mode === "login" ? "Don't have an account? " : "Already have an account? "}
              <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
                className="text-blue-400 hover:text-blue-300 font-medium">
                {mode === "login" ? "Register" : "Sign In"}
              </button>
            </p>
          )}

          {tab === "admin" && (mode === "login" || mode === "register") && (
            <p className="mt-4 text-center text-blue-400/60 text-xs">
              Demo: admin@viperai.io / admin123
            </p>
          )}
        </div>

        <div className="mt-6 text-center text-blue-400/50 text-xs">
          <p>Automated DBS &middot; Identity Verification &middot; Right to Work &middot; AI CV Analysis</p>
          <p className="mt-1">GDPR Compliant &middot; ICO Registered &middot; CQC Ready</p>
        </div>
      </div>
    </div>
  );
}
