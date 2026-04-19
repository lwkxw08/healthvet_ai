import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { paymentProvidersApi } from "../api/client";
import { CreditCard, CheckCircle, XCircle, RefreshCw, Trash2, Zap, AlertTriangle, Eye, EyeOff } from "lucide-react";

interface ProviderConfig {
  id: string;
  provider: string;
  display_name: string;
  is_enabled: number;
  api_key_set: number;
  api_key_masked: string | null;
  api_secret_masked: string | null;
  environment: string;
  account_id: string | null;
  account_name: string | null;
  currency: string;
  last_tested_at: string | null;
  test_status: string | null;
  connected_at: string | null;
  capabilities: string[];
  payment_methods: string[];
  capability_description: string;
}

interface RoutingRule {
  id: string;
  payment_type: string;
  label: string;
  provider: string | null;
  fallback_provider: string | null;
  is_enabled: number;
  description: string | null;
}

export default function PaymentProvidersPanel() {
  const { token } = useAuth();
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [routing, setRouting] = useState<RoutingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Connect form state
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [environment, setEnvironment] = useState("live");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const loadData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [provs, routes] = await Promise.all([
        paymentProvidersApi.getProviders(token),
        paymentProvidersApi.getRouting(token),
      ]);
      setProviders(provs as unknown as ProviderConfig[]);
      setRouting(routes as unknown as RoutingRule[]);
    } catch (err) {
      showMessage("error", "Failed to load payment provider configuration");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleConnect = async (provider: string) => {
    if (!token || !apiKey.trim()) return;
    setSaving(true);
    try {
      const result = await paymentProvidersApi.connectProvider(token, {
        provider,
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim() || undefined,
        webhook_secret: webhookSecret.trim() || undefined,
        environment,
      }) as Record<string, unknown>;

      if (result.connected) {
        showMessage("success", `${provider === "stripe" ? "Stripe" : "GoCardless"} connected successfully! Account: ${result.account_name || result.account_id}`);
      } else {
        showMessage("error", `Connection test failed: ${result.message || "Check your API key"}`);
      }
      setConnectingProvider(null);
      setApiKey("");
      setApiSecret("");
      setWebhookSecret("");
      await loadData();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Connection failed";
      showMessage("error", errorMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async (provider: string) => {
    if (!token) return;
    if (!confirm(`Disconnect ${provider}? This will remove all credentials and routing assignments.`)) return;
    try {
      await paymentProvidersApi.disconnectProvider(token, provider);
      showMessage("success", `${provider} disconnected`);
      await loadData();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Disconnect failed";
      showMessage("error", errorMsg);
    }
  };

  const handleTest = async (provider: string) => {
    if (!token) return;
    setTesting(provider);
    try {
      const result = await paymentProvidersApi.testProvider(token, provider) as Record<string, unknown>;
      if (result.success) {
        showMessage("success", `${provider} connectivity test passed!`);
      } else {
        showMessage("error", `Test failed: ${result.error || result.message || "Unknown error"}`);
      }
      await loadData();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Test failed";
      showMessage("error", errorMsg);
    } finally {
      setTesting(null);
    }
  };

  const handleRoutingChange = async (paymentType: string, field: "provider" | "fallback_provider", value: string) => {
    if (!token) return;
    const currentRule = routing.find(r => r.payment_type === paymentType);
    if (!currentRule) return;

    const data: { payment_type: string; provider: string | null; fallback_provider?: string | null } = {
      payment_type: paymentType,
      provider: field === "provider" ? (value || null) : currentRule.provider,
    };
    if (field === "fallback_provider") {
      data.fallback_provider = value || null;
    } else {
      data.fallback_provider = currentRule.fallback_provider;
    }

    try {
      await paymentProvidersApi.updateRouting(token, data);
      showMessage("success", `Routing updated for ${currentRule.label}`);
      await loadData();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Routing update failed";
      showMessage("error", errorMsg);
    }
  };

  const enabledProviders = providers.filter(p => p.is_enabled);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="animate-spin text-blue-400" size={24} />
        <span className="ml-2 text-slate-400">Loading payment providers...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <CreditCard className="text-blue-400" size={22} /> Payment Providers
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Connect Stripe and/or GoCardless, then choose which provider handles each payment type.
          </p>
        </div>
        <button onClick={loadData} className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Status message */}
      {message && (
        <div className={`p-3 rounded-lg border text-sm ${message.type === "success" ? "bg-green-900/30 border-green-700 text-green-300" : "bg-red-900/30 border-red-700 text-red-300"}`}>
          {message.type === "success" ? <CheckCircle size={14} className="inline mr-1" /> : <XCircle size={14} className="inline mr-1" />}
          {message.text}
        </div>
      )}

      {/* Provider Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {providers.map((prov) => (
          <div key={prov.provider} className={`bg-slate-800/80 rounded-xl border p-5 ${prov.is_enabled ? "border-green-700/50" : "border-slate-700"}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${prov.provider === "stripe" ? "bg-purple-900/50" : "bg-teal-900/50"}`}>
                  {prov.provider === "stripe" ? (
                    <CreditCard className="text-purple-400" size={20} />
                  ) : (
                    <Zap className="text-teal-400" size={20} />
                  )}
                </div>
                <div>
                  <h3 className="text-white font-semibold">{prov.display_name}</h3>
                  <p className="text-slate-500 text-xs">{prov.capability_description}</p>
                </div>
              </div>
              <div className={`px-2 py-0.5 rounded text-[10px] font-medium ${prov.is_enabled ? "bg-green-900/50 text-green-300" : "bg-slate-700 text-slate-400"}`}>
                {prov.is_enabled ? "Connected" : "Not Connected"}
              </div>
            </div>

            {/* Connected state */}
            {prov.is_enabled ? (
              <div className="space-y-2">
                <div className="bg-slate-900/50 rounded p-3 text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Account</span>
                    <span className="text-white">{prov.account_name || prov.account_id || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">API Key</span>
                    <span className="text-slate-300 font-mono">{prov.api_key_masked || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Environment</span>
                    <span className={`font-medium ${prov.environment === "live" ? "text-green-400" : "text-amber-400"}`}>
                      {prov.environment === "live" ? "Live" : "Sandbox"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Last Tested</span>
                    <span className="text-slate-300">{prov.last_tested_at ? new Date(prov.last_tested_at).toLocaleString() : "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Status</span>
                    <span className={prov.test_status === "ok" ? "text-green-400" : "text-red-400"}>
                      {prov.test_status === "ok" ? "Healthy" : prov.test_status || "Unknown"}
                    </span>
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 text-[10px]">Supports: {prov.payment_methods?.join(", ")}</span>
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleTest(prov.provider)}
                    disabled={testing === prov.provider}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-blue-900/40 hover:bg-blue-900/60 text-blue-300 rounded text-xs border border-blue-800/50"
                  >
                    {testing === prov.provider ? <RefreshCw size={12} className="animate-spin" /> : <CheckCircle size={12} />}
                    Test Connection
                  </button>
                  <button
                    onClick={() => { setConnectingProvider(prov.provider); setEnvironment(prov.environment || "live"); }}
                    className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs"
                  >
                    Update Keys
                  </button>
                  <button
                    onClick={() => handleDisconnect(prov.provider)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded text-xs border border-red-800/50"
                  >
                    <Trash2 size={12} /> Disconnect
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="bg-slate-900/30 rounded p-3 text-xs text-slate-400">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
                    <span>
                      Not connected. Enter your {prov.provider === "stripe" ? "Stripe secret key (sk_live_...)" : "GoCardless access token"} to enable.
                    </span>
                  </div>
                </div>
                <div className="text-xs text-slate-500">
                  <span className="font-medium text-slate-400">Capabilities:</span>{" "}
                  {prov.capabilities?.map((c: string) => c.replace(/_/g, " ")).join(", ")}
                </div>
                <button
                  onClick={() => { setConnectingProvider(prov.provider); setApiKey(""); setApiSecret(""); setWebhookSecret(""); setEnvironment("live"); }}
                  className="w-full flex items-center justify-center gap-1 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium"
                >
                  <CreditCard size={14} /> Connect {prov.display_name}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Connect Provider Modal */}
      {connectingProvider && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setConnectingProvider(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-white mb-1">
              Connect {connectingProvider === "stripe" ? "Stripe" : "GoCardless"}
            </h3>
            <p className="text-slate-400 text-xs mb-4">
              {connectingProvider === "stripe"
                ? "Enter your Stripe Secret Key (starts with sk_live_ or sk_test_). Find it at dashboard.stripe.com/apikeys"
                : "Enter your GoCardless Access Token. Find it at manage.gocardless.com/developers"}
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  {connectingProvider === "stripe" ? "Secret Key *" : "Access Token *"}
                </label>
                <div className="relative">
                  <input
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder={connectingProvider === "stripe" ? "sk_live_..." : "live_..."}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white text-sm font-mono pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                  >
                    {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {connectingProvider === "stripe" && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Webhook Signing Secret (optional)</label>
                  <input
                    type="password"
                    value={webhookSecret}
                    onChange={e => setWebhookSecret(e.target.value)}
                    placeholder="whsec_..."
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white text-sm font-mono"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs text-slate-400 mb-1">Environment</label>
                <select
                  value={environment}
                  onChange={e => setEnvironment(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white text-sm"
                >
                  <option value="live">Live (Production)</option>
                  <option value="sandbox">Sandbox (Test)</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setConnectingProvider(null)}
                className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConnect(connectingProvider)}
                disabled={saving || !apiKey.trim()}
                className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 text-white rounded text-sm font-medium"
              >
                {saving ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                {saving ? "Connecting..." : "Connect & Test"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payment Routing */}
      <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-5">
        <h3 className="text-white font-semibold mb-1">Payment Routing</h3>
        <p className="text-slate-400 text-xs mb-4">
          Choose which provider handles each payment type. You can use Stripe for everything, GoCardless for everything, or mix them.
        </p>

        {enabledProviders.length === 0 && (
          <div className="bg-amber-900/20 border border-amber-800/50 rounded p-3 text-xs text-amber-300 mb-4 flex items-start gap-2">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <span>No payment providers connected. Connect at least one provider above to configure routing.</span>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 text-xs border-b border-slate-700">
                <th className="text-left py-2 px-3">Payment Type</th>
                <th className="text-left py-2 px-3">Description</th>
                <th className="text-left py-2 px-3">Primary Provider</th>
                <th className="text-left py-2 px-3">Fallback Provider</th>
                <th className="text-left py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {routing.map((rule) => (
                <tr key={rule.payment_type} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                  <td className="py-2.5 px-3">
                    <span className="text-white font-medium">{rule.label}</span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 text-xs">{rule.description || "—"}</td>
                  <td className="py-2.5 px-3">
                    <select
                      value={rule.provider || ""}
                      onChange={e => handleRoutingChange(rule.payment_type, "provider", e.target.value)}
                      disabled={enabledProviders.length === 0}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-600 rounded text-white text-xs"
                    >
                      <option value="">Not assigned</option>
                      {enabledProviders.map(p => (
                        <option key={p.provider} value={p.provider}>{p.display_name}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2.5 px-3">
                    <select
                      value={rule.fallback_provider || ""}
                      onChange={e => handleRoutingChange(rule.payment_type, "fallback_provider", e.target.value)}
                      disabled={enabledProviders.length < 2}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-600 rounded text-white text-xs"
                    >
                      <option value="">None</option>
                      {enabledProviders
                        .filter(p => p.provider !== rule.provider)
                        .map(p => (
                          <option key={p.provider} value={p.provider}>{p.display_name}</option>
                        ))}
                    </select>
                  </td>
                  <td className="py-2.5 px-3">
                    {rule.provider ? (
                      <span className="inline-flex items-center gap-1 text-green-400 text-xs">
                        <CheckCircle size={12} /> Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-slate-500 text-xs">
                        <XCircle size={12} /> Unassigned
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Reference */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
        <h3 className="text-white font-semibold mb-2 text-sm">How it works</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-400">
          <div className="space-y-1">
            <p className="text-white font-medium">1. Connect Providers</p>
            <p>Enter your API keys for Stripe and/or GoCardless. We test connectivity automatically before saving.</p>
          </div>
          <div className="space-y-1">
            <p className="text-white font-medium">2. Assign Routing</p>
            <p>Choose which provider handles each payment type. Use one for everything, or split between providers.</p>
          </div>
          <div className="space-y-1">
            <p className="text-white font-medium">3. Payments Route Automatically</p>
            <p>When agencies pay, the system routes to the correct provider. If the primary fails, it tries the fallback.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
