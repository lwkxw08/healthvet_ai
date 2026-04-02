import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { emailConfigApi } from "../api/client";
import { Shield, Save, RefreshCw, CheckCircle, AlertTriangle, Mail, Key, Globe } from "lucide-react";

type Provider = "" | "sendgrid" | "mailgun" | "resend";

interface EmailConfig {
  email_provider: Provider;
  sendgrid_api_key: string;
  sendgrid_api_key_set: boolean;
  mailgun_api_key: string;
  mailgun_api_key_set: boolean;
  mailgun_domain: string;
  resend_api_key: string;
  resend_api_key_set: boolean;
  email_from_address: string;
  email_from_name: string;
  active_provider: {
    provider: string | null;
    configured: boolean;
    from_email: string;
    from_name: string;
  };
}

const PROVIDERS = [
  { value: "", label: "Auto-detect (based on which API key is set)", icon: "🔍" },
  { value: "sendgrid", label: "SendGrid", icon: "📧" },
  { value: "mailgun", label: "Mailgun", icon: "📮" },
  { value: "resend", label: "Resend", icon: "📨" },
];

export default function EmailConfigPanel() {
  const { token } = useAuth();
  const [config, setConfig] = useState<EmailConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  // Form state
  const [provider, setProvider] = useState<Provider>("");
  const [sendgridKey, setSendgridKey] = useState("");
  const [mailgunKey, setMailgunKey] = useState("");
  const [mailgunDomain, setMailgunDomain] = useState("");
  const [resendKey, setResendKey] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [fromName, setFromName] = useState("");

  const loadConfig = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await emailConfigApi.get(token) as unknown as EmailConfig;
      setConfig(data);
      setProvider((data.email_provider || "") as Provider);
      setSendgridKey(data.sendgrid_api_key || "");
      setMailgunKey(data.mailgun_api_key || "");
      setMailgunDomain(data.mailgun_domain || "");
      setResendKey(data.resend_api_key || "");
      setFromAddress(data.email_from_address || "");
      setFromName(data.email_from_name || "");
    } catch {
      setMessage({ type: "error", text: "Failed to load email configuration" });
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setMessage(null);
    try {
      await emailConfigApi.update(token, {
        email_provider: provider,
        sendgrid_api_key: sendgridKey.startsWith("*") ? "" : sendgridKey,
        mailgun_api_key: mailgunKey.startsWith("*") ? "" : mailgunKey,
        mailgun_domain: mailgunDomain,
        resend_api_key: resendKey.startsWith("*") ? "" : resendKey,
        email_from_address: fromAddress,
        email_from_name: fromName,
      });
      setMessage({ type: "success", text: "Email configuration saved successfully" });
      await loadConfig();
    } catch {
      setMessage({ type: "error", text: "Failed to save email configuration" });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!token) return;
    setTesting(true);
    setMessage(null);
    try {
      const result = await emailConfigApi.test(token) as { status: string; message: string };
      setMessage({
        type: result.status === "ok" ? "success" : "info",
        text: result.message,
      });
    } catch {
      setMessage({ type: "error", text: "Failed to test email configuration" });
    } finally {
      setTesting(false);
    }
  };

  const inputCls = "w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2.5 text-white text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors";
  const labelCls = "block text-xs font-medium text-slate-400 mb-1.5";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="animate-spin text-blue-400" size={24} />
        <span className="ml-3 text-slate-400">Loading email configuration...</span>
      </div>
    );
  }

  const activeProvider = config?.active_provider;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Mail size={20} className="text-blue-400" />
            Email Provider Configuration
          </h2>
          <p className="text-xs text-slate-500 mt-1">Configure your email delivery provider and API keys. Changes take effect immediately.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleTest} disabled={testing}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg transition-colors disabled:opacity-50">
            {testing ? <RefreshCw size={14} className="animate-spin" /> : <Shield size={14} />}
            Test Connection
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg font-medium transition-colors disabled:opacity-50">
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
            Save Configuration
          </button>
        </div>
      </div>

      {/* Status message */}
      {message && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
          message.type === "success" ? "bg-green-500/10 border border-green-500/30 text-green-400" :
          message.type === "error" ? "bg-red-500/10 border border-red-500/30 text-red-400" :
          "bg-blue-500/10 border border-blue-500/30 text-blue-400"
        }`}>
          {message.type === "success" ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {message.text}
        </div>
      )}

      {/* Active Provider Status */}
      <div className={`rounded-xl border p-4 ${
        activeProvider?.configured
          ? "bg-green-500/5 border-green-500/20"
          : "bg-amber-500/5 border-amber-500/20"
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${activeProvider?.configured ? "bg-green-400" : "bg-amber-400"}`} />
          <div>
            <p className="text-sm font-medium text-white">
              {activeProvider?.configured
                ? `Active provider: ${activeProvider.provider?.charAt(0).toUpperCase()}${activeProvider.provider?.slice(1)}`
                : "No email provider configured"
              }
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {activeProvider?.configured
                ? `Sending from: ${activeProvider.from_name} <${activeProvider.from_email}>`
                : "Emails are being logged to the database only. Configure a provider below to start sending."
              }
            </p>
          </div>
        </div>
      </div>

      {/* Provider Selection */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Globe size={16} className="text-blue-400" />
          Email Provider
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {PROVIDERS.map((p) => (
            <button
              key={p.value}
              onClick={() => setProvider(p.value as Provider)}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-all ${
                provider === p.value
                  ? "border-blue-500 bg-blue-500/10 text-white"
                  : "border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600 hover:text-slate-300"
              }`}
            >
              <span className="text-lg">{p.icon}</span>
              <span className="text-sm">{p.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Sender Details */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Mail size={16} className="text-blue-400" />
          Sender Details
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>From Email Address</label>
            <input
              type="email"
              value={fromAddress}
              onChange={(e) => setFromAddress(e.target.value)}
              placeholder="noreply@yourdomain.com"
              className={inputCls}
            />
            <p className="text-[10px] text-slate-600 mt-1">Must be verified with your email provider</p>
          </div>
          <div>
            <label className={labelCls}>From Name</label>
            <input
              type="text"
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              placeholder="HealthVet AI"
              className={inputCls}
            />
            <p className="text-[10px] text-slate-600 mt-1">Display name shown to email recipients</p>
          </div>
        </div>
      </div>

      {/* SendGrid Configuration */}
      <div className={`bg-slate-800/50 rounded-xl border p-5 space-y-4 transition-all ${
        provider === "sendgrid" || provider === "" ? "border-slate-700/50" : "border-slate-700/30 opacity-50"
      }`}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Key size={16} className="text-blue-400" />
            SendGrid
          </h3>
          {config?.sendgrid_api_key_set && (
            <span className="text-[10px] text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">API key configured</span>
          )}
        </div>
        <div>
          <label className={labelCls}>SendGrid API Key</label>
          <input
            type="password"
            value={sendgridKey}
            onChange={(e) => setSendgridKey(e.target.value)}
            placeholder={config?.sendgrid_api_key_set ? "••••••••(key is set — enter new value to change)" : "SG.xxxxxxxx..."}
            className={inputCls}
          />
          <p className="text-[10px] text-slate-600 mt-1">
            Get your API key from{" "}
            <a href="https://app.sendgrid.com/settings/api_keys" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
              SendGrid Settings → API Keys
            </a>
          </p>
        </div>
      </div>

      {/* Mailgun Configuration */}
      <div className={`bg-slate-800/50 rounded-xl border p-5 space-y-4 transition-all ${
        provider === "mailgun" || provider === "" ? "border-slate-700/50" : "border-slate-700/30 opacity-50"
      }`}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Key size={16} className="text-purple-400" />
            Mailgun
          </h3>
          {config?.mailgun_api_key_set && (
            <span className="text-[10px] text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">API key configured</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Mailgun API Key</label>
            <input
              type="password"
              value={mailgunKey}
              onChange={(e) => setMailgunKey(e.target.value)}
              placeholder={config?.mailgun_api_key_set ? "••••••••(key is set)" : "key-xxxxxxxx..."}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Mailgun Domain</label>
            <input
              type="text"
              value={mailgunDomain}
              onChange={(e) => setMailgunDomain(e.target.value)}
              placeholder="mg.yourdomain.com"
              className={inputCls}
            />
          </div>
        </div>
        <p className="text-[10px] text-slate-600">
          Get your credentials from{" "}
          <a href="https://app.mailgun.com/app/sending/domains" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
            Mailgun Dashboard → Sending → Domains
          </a>
        </p>
      </div>

      {/* Resend Configuration */}
      <div className={`bg-slate-800/50 rounded-xl border p-5 space-y-4 transition-all ${
        provider === "resend" || provider === "" ? "border-slate-700/50" : "border-slate-700/30 opacity-50"
      }`}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Key size={16} className="text-emerald-400" />
            Resend
          </h3>
          {config?.resend_api_key_set && (
            <span className="text-[10px] text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">API key configured</span>
          )}
        </div>
        <div>
          <label className={labelCls}>Resend API Key</label>
          <input
            type="password"
            value={resendKey}
            onChange={(e) => setResendKey(e.target.value)}
            placeholder={config?.resend_api_key_set ? "••••••••(key is set)" : "re_xxxxxxxx..."}
            className={inputCls}
          />
          <p className="text-[10px] text-slate-600 mt-1">
            Get your API key from{" "}
            <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
              Resend Dashboard → API Keys
            </a>
          </p>
        </div>
      </div>

      {/* Help Section */}
      <div className="bg-slate-900/50 rounded-xl border border-slate-700/30 p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">How it works</h3>
        <ul className="space-y-2 text-xs text-slate-500">
          <li className="flex items-start gap-2">
            <span className="text-blue-400 mt-0.5">1.</span>
            <span>Choose a provider above and enter your API key. If set to "Auto-detect", the system uses whichever provider has a valid API key.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-400 mt-0.5">2.</span>
            <span>Set the "From" email address and name. The email address must be verified/authorised with your chosen provider.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-400 mt-0.5">3.</span>
            <span>Click "Save Configuration" then "Test Connection" to verify everything works.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-400 mt-0.5">4.</span>
            <span>Without a provider configured, all emails are logged to the database and can be viewed in the Email Templates send log — nothing is lost.</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
