import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { subscriptionPlansApi, industryTemplatesApi, billingApi } from "../api/client";
import {
  DollarSign, PlusCircle, Trash2, Edit, Save, X, RefreshCw,
  CreditCard, Layers, Tag, CheckCircle,
} from "lucide-react";

export default function SubscriptionPlansPanel() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"plans" | "pricing" | "matrix">("plans");
  const [message, setMessage] = useState("");

  // Industry templates
  const [templates, setTemplates] = useState<Record<string, unknown>[]>([]);

  // Plan links state (Option A)
  const [planLinks, setPlanLinks] = useState<Record<string, unknown>[]>([]);
  const [tiers, setTiers] = useState<Record<string, { name: string; monthly_price: number; per_worker_price: number; monthly_checks: number }>>({});
  const [planLinksLoading, setPlanLinksLoading] = useState(false);
  const [creatingPlanLink, setCreatingPlanLink] = useState(false);
  const [newPlanLink, setNewPlanLink] = useState({ tier_key: "", industry_template_id: "", custom_monthly_price: "", custom_per_worker_price: "", custom_monthly_checks: "" });

  // Per-element pricing state (Option C)
  const [checkPricing, setCheckPricing] = useState<Record<string, unknown>[]>([]);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [addingPricing, setAddingPricing] = useState(false);
  const [newPricing, setNewPricing] = useState({ check_type: "", label: "", credit_value: "1", third_party_cost: "0", sell_price: "0" });
  const [editingPricingId, setEditingPricingId] = useState<string | null>(null);
  const [editPricingData, setEditPricingData] = useState({ label: "", credit_value: "", third_party_cost: "", sell_price: "" });

  // Pricing matrix state
  const [pricingMatrix, setPricingMatrix] = useState<Record<string, unknown> | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [matrixSelectedIndustry, setMatrixSelectedIndustry] = useState<string>("");
  const [matrixIndustryPricing, setMatrixIndustryPricing] = useState<Record<string, unknown>[]>([]);
  const [matrixEditingId, setMatrixEditingId] = useState<string | null>(null);
  const [matrixEditData, setMatrixEditData] = useState({ label: "", credit_value: "", third_party_cost: "", sell_price: "" });
  const [matrixAddingCheck, setMatrixAddingCheck] = useState(false);
  const [matrixNewCheck, setMatrixNewCheck] = useState({ check_type: "", label: "", credit_value: "1", third_party_cost: "0", sell_price: "0" });

  const showMessage = (msg: string) => { setMessage(msg); setTimeout(() => setMessage(""), 4000); };

  const loadTemplates = useCallback(async () => {
    if (!token) return;
    try { const data = await industryTemplatesApi.list(token); setTemplates(data); } catch { /* ignore */ }
  }, [token]);

  const loadTiers = useCallback(async () => {
    if (!token) return;
    try {
      const t = await billingApi.getTiers(token);
      setTiers(t as Record<string, { name: string; monthly_price: number; per_worker_price: number; monthly_checks: number }>);
    } catch { /* ignore */ }
  }, [token]);

  const loadPlanLinks = useCallback(async () => {
    if (!token) return;
    setPlanLinksLoading(true);
    try { const pl = await subscriptionPlansApi.getIndustryPlans(token); setPlanLinks(pl); } catch { /* ignore */ }
    finally { setPlanLinksLoading(false); }
  }, [token]);

  const loadCheckPricing = useCallback(async () => {
    if (!token) return;
    setPricingLoading(true);
    try {
      const cp = await subscriptionPlansApi.getIndustryPricing(token, selectedIndustry || undefined);
      setCheckPricing(cp);
    } catch { /* ignore */ }
    finally { setPricingLoading(false); }
  }, [token, selectedIndustry]);

  const loadPricingMatrix = useCallback(async () => {
    if (!token) return;
    setMatrixLoading(true);
    try { const m = await subscriptionPlansApi.getPricingMatrix(token); setPricingMatrix(m); } catch { /* ignore */ }
    finally { setMatrixLoading(false); }
  }, [token]);

  useEffect(() => { loadTemplates(); loadTiers(); }, [loadTemplates, loadTiers]);
  useEffect(() => { if (activeTab === "plans") loadPlanLinks(); }, [activeTab, loadPlanLinks]);
  useEffect(() => { if (activeTab === "pricing") loadCheckPricing(); }, [activeTab, loadCheckPricing]);
  useEffect(() => { if (activeTab === "matrix") loadPricingMatrix(); }, [activeTab, loadPricingMatrix]);

  const createPlanLink = async () => {
    if (!token || !newPlanLink.tier_key || !newPlanLink.industry_template_id) return;
    try {
      const data: Record<string, unknown> = {
        tier_key: newPlanLink.tier_key,
        industry_template_id: newPlanLink.industry_template_id,
      };
      if (newPlanLink.custom_monthly_price) data.custom_monthly_price = parseFloat(newPlanLink.custom_monthly_price);
      if (newPlanLink.custom_per_worker_price) data.custom_per_worker_price = parseFloat(newPlanLink.custom_per_worker_price);
      if (newPlanLink.custom_monthly_checks) data.custom_monthly_checks = parseInt(newPlanLink.custom_monthly_checks);
      await subscriptionPlansApi.createIndustryPlan(token, data);
      showMessage("Industry plan link created");
      setCreatingPlanLink(false);
      setNewPlanLink({ tier_key: "", industry_template_id: "", custom_monthly_price: "", custom_per_worker_price: "", custom_monthly_checks: "" });
      loadPlanLinks();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const deletePlanLink = async (linkId: string) => {
    if (!token) return;
    try {
      await subscriptionPlansApi.deleteIndustryPlan(token, linkId);
      showMessage("Plan link deleted");
      loadPlanLinks();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const createCheckPricing = async () => {
    if (!token || !selectedIndustry || !newPricing.check_type) return;
    try {
      await subscriptionPlansApi.createIndustryPricing(token, {
        industry_template_id: selectedIndustry,
        check_type: newPricing.check_type,
        label: newPricing.label || newPricing.check_type.replace(/_/g, " "),
        credit_value: parseFloat(newPricing.credit_value) || 1,
        third_party_cost: parseFloat(newPricing.third_party_cost) || 0,
        sell_price: parseFloat(newPricing.sell_price) || 0,
      });
      showMessage("Check pricing created");
      setAddingPricing(false);
      setNewPricing({ check_type: "", label: "", credit_value: "1", third_party_cost: "0", sell_price: "0" });
      loadCheckPricing();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const updateCheckPricing = async (pricingId: string) => {
    if (!token) return;
    try {
      await subscriptionPlansApi.updateIndustryPricing(token, pricingId, {
        label: editPricingData.label,
        credit_value: parseFloat(editPricingData.credit_value),
        third_party_cost: parseFloat(editPricingData.third_party_cost),
        sell_price: parseFloat(editPricingData.sell_price),
      });
      showMessage("Pricing updated");
      setEditingPricingId(null);
      loadCheckPricing();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const deleteCheckPricing = async (pricingId: string) => {
    if (!token) return;
    try {
      await subscriptionPlansApi.deleteIndustryPricing(token, pricingId);
      showMessage("Pricing deleted");
      loadCheckPricing();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const startEditPricing = (pricing: Record<string, unknown>) => {
    setEditingPricingId(String(pricing.id));
    setEditPricingData({
      label: String(pricing.label || ""),
      credit_value: String(pricing.credit_value || 1),
      third_party_cost: String(pricing.third_party_cost || 0),
      sell_price: String(pricing.sell_price || 0),
    });
  };

  // Matrix tab helpers
  const loadMatrixIndustryPricing = useCallback(async (industryId: string) => {
    if (!token || !industryId) { setMatrixIndustryPricing([]); return; }
    try {
      const cp = await subscriptionPlansApi.getIndustryPricing(token, industryId);
      setMatrixIndustryPricing(cp);
    } catch { setMatrixIndustryPricing([]); }
  }, [token]);

  useEffect(() => {
    if (activeTab === "matrix" && matrixSelectedIndustry) loadMatrixIndustryPricing(matrixSelectedIndustry);
  }, [activeTab, matrixSelectedIndustry, loadMatrixIndustryPricing]);

  const matrixStartEdit = (p: Record<string, unknown>) => {
    setMatrixEditingId(String(p.id));
    setMatrixEditData({
      label: String(p.label || ""), credit_value: String(p.credit_value || 1),
      third_party_cost: String(p.third_party_cost || 0), sell_price: String(p.sell_price || 0),
    });
  };

  const matrixSaveEdit = async (pricingId: string) => {
    if (!token) return;
    try {
      await subscriptionPlansApi.updateIndustryPricing(token, pricingId, {
        label: matrixEditData.label, credit_value: parseFloat(matrixEditData.credit_value),
        third_party_cost: parseFloat(matrixEditData.third_party_cost), sell_price: parseFloat(matrixEditData.sell_price),
      });
      showMessage("Pricing updated");
      setMatrixEditingId(null);
      loadMatrixIndustryPricing(matrixSelectedIndustry);
      loadPricingMatrix();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const matrixDeleteCheck = async (pricingId: string) => {
    if (!token) return;
    try {
      await subscriptionPlansApi.deleteIndustryPricing(token, pricingId);
      showMessage("Check pricing deleted");
      loadMatrixIndustryPricing(matrixSelectedIndustry);
      loadPricingMatrix();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const matrixAddCheck = async () => {
    if (!token || !matrixSelectedIndustry || !matrixNewCheck.check_type) return;
    try {
      await subscriptionPlansApi.createIndustryPricing(token, {
        industry_template_id: matrixSelectedIndustry, check_type: matrixNewCheck.check_type,
        label: matrixNewCheck.label || matrixNewCheck.check_type.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase()),
        credit_value: parseFloat(matrixNewCheck.credit_value) || 1, third_party_cost: parseFloat(matrixNewCheck.third_party_cost) || 0,
        sell_price: parseFloat(matrixNewCheck.sell_price) || 0,
      });
      showMessage("Check pricing added");
      setMatrixAddingCheck(false);
      setMatrixNewCheck({ check_type: "", label: "", credit_value: "1", third_party_cost: "0", sell_price: "0" });
      loadMatrixIndustryPricing(matrixSelectedIndustry);
      loadPricingMatrix();
    } catch (err) { showMessage(`Error: ${err instanceof Error ? err.message : "Failed"}`); }
  };

  const checkTypeOptions = [
    "identity_verification", "right_to_work", "dbs_check", "enhanced_dbs",
    "professional_registration", "employment_history", "reference_check",
    "qualification_check", "training_compliance", "occupational_health",
    "criminal_record", "credit_check", "address_verification", "driving_license",
    "cscs_card", "construction_skills", "food_hygiene", "safeguarding",
  ];

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.startsWith("Error") ? "bg-red-500/20 text-red-300 border border-red-500/30" : "bg-green-500/20 text-green-300 border border-green-500/30"}`}>{message}</div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-2">
        {[
          { key: "plans" as const, label: "Industry Plans (A)", icon: <Layers size={14} /> },
          { key: "pricing" as const, label: "Per-Check Pricing (C)", icon: <Tag size={14} /> },
          { key: "matrix" as const, label: "Pricing Matrix", icon: <CreditCard size={14} /> },
        ].map((t) => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === t.key ? "bg-blue-600 text-white" : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Option A: Industry Plans */}
      {activeTab === "plans" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Industry-Specific Plans</h3>
              <p className="text-slate-400 text-xs mt-0.5">Link subscription tiers to industries with optional custom pricing overrides</p>
            </div>
            <div className="flex gap-2">
              <button onClick={loadPlanLinks} className="text-slate-400 hover:text-white flex items-center gap-1 text-sm">
                <RefreshCw size={14} className={planLinksLoading ? "animate-spin" : ""} /> Refresh
              </button>
              <button onClick={() => setCreatingPlanLink(true)} className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1">
                <PlusCircle size={12} /> Add Plan Link
              </button>
            </div>
          </div>

          {/* Create form */}
          {creatingPlanLink && (
            <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-4">
              <h4 className="text-white font-medium mb-3">New Industry Plan Link</h4>
              <div className="grid grid-cols-5 gap-3">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Tier</label>
                  <select value={newPlanLink.tier_key} onChange={(e) => setNewPlanLink((p) => ({ ...p, tier_key: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs">
                    <option value="">Select tier...</option>
                    {Object.entries(tiers).map(([key, tier]) => (
                      <option key={key} value={key}>{tier.name} ({"\u00A3"}{tier.monthly_price}/mo)</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Industry</label>
                  <select value={newPlanLink.industry_template_id} onChange={(e) => setNewPlanLink((p) => ({ ...p, industry_template_id: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs">
                    <option value="">Select industry...</option>
                    {templates.map((t) => (
                      <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Custom Price ({"\u00A3"}/mo)</label>
                  <input type="number" step="0.01" value={newPlanLink.custom_monthly_price}
                    onChange={(e) => setNewPlanLink((p) => ({ ...p, custom_monthly_price: e.target.value }))}
                    placeholder="Override"
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Custom Per-Worker ({"\u00A3"})</label>
                  <input type="number" step="0.01" value={newPlanLink.custom_per_worker_price}
                    onChange={(e) => setNewPlanLink((p) => ({ ...p, custom_per_worker_price: e.target.value }))}
                    placeholder="Override"
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Custom Checks/mo</label>
                  <input type="number" value={newPlanLink.custom_monthly_checks}
                    onChange={(e) => setNewPlanLink((p) => ({ ...p, custom_monthly_checks: e.target.value }))}
                    placeholder="Override"
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={createPlanLink} className="bg-green-600 hover:bg-green-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><Save size={12} /> Save</button>
                <button onClick={() => setCreatingPlanLink(false)} className="bg-slate-600 hover:bg-slate-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><X size={12} /> Cancel</button>
              </div>
            </div>
          )}

          {/* Plan links table */}
          {planLinks.length === 0 && !planLinksLoading ? (
            <div className="text-center py-12 text-slate-500">
              <Layers size={40} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No industry plan links configured. Click "Add Plan Link" to create one.</p>
            </div>
          ) : (
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Industry</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Tier</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Base Price</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Custom Price</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Per-Worker</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Checks/mo</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Active</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {planLinks.map((pl) => (
                    <tr key={String(pl.id)} className="hover:bg-slate-700/20">
                      <td className="py-3 px-3 text-white font-medium">{String(pl.industry_name || pl.industry_template_id)}</td>
                      <td className="py-3 px-3 text-slate-300">{String(pl.tier_name || pl.tier_key)}</td>
                      <td className="py-3 px-3 text-center text-slate-400">{"\u00A3"}{Number(pl.base_monthly_price || 0).toFixed(2)}</td>
                      <td className="py-3 px-3 text-center text-emerald-400 font-medium">
                        {pl.custom_monthly_price ? `\u00A3${Number(pl.custom_monthly_price).toFixed(2)}` : <span className="text-slate-500">-</span>}
                      </td>
                      <td className="py-3 px-3 text-center text-slate-300">
                        {pl.custom_per_worker_price ? `\u00A3${Number(pl.custom_per_worker_price).toFixed(2)}` : `\u00A3${Number(pl.base_per_worker_price || 0).toFixed(2)}`}
                      </td>
                      <td className="py-3 px-3 text-center text-slate-300">
                        {pl.custom_monthly_checks ? String(pl.custom_monthly_checks) : String(pl.base_monthly_checks || "-")}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {pl.is_active ? <CheckCircle size={14} className="text-green-400 mx-auto" /> : <X size={14} className="text-red-400 mx-auto" />}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <button onClick={() => deletePlanLink(String(pl.id))} className="text-slate-400 hover:text-red-400"><Trash2 size={14} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Option C: Per-Element Pricing */}
      {activeTab === "pricing" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Per-Check Industry Pricing</h3>
              <p className="text-slate-400 text-xs mt-0.5">Set different credit values and costs for each check type per industry</p>
            </div>
            <div className="flex gap-2 items-center">
              <select value={selectedIndustry} onChange={(e) => setSelectedIndustry(e.target.value)}
                className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-xs">
                <option value="">All Industries</option>
                {templates.map((t) => (
                  <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>
                ))}
              </select>
              {selectedIndustry && (
                <button onClick={() => setAddingPricing(true)} className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1">
                  <PlusCircle size={12} /> Add Check Pricing
                </button>
              )}
            </div>
          </div>

          {/* Add pricing form */}
          {addingPricing && selectedIndustry && (
            <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-4">
              <h4 className="text-white font-medium mb-3">New Check Pricing</h4>
              <div className="grid grid-cols-5 gap-3">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Check Type</label>
                  <select value={newPricing.check_type} onChange={(e) => setNewPricing((p) => ({ ...p, check_type: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs">
                    <option value="">Select check...</option>
                    {checkTypeOptions.map((ct) => (
                      <option key={ct} value={ct}>{ct.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Label</label>
                  <input type="text" value={newPricing.label} onChange={(e) => setNewPricing((p) => ({ ...p, label: e.target.value }))}
                    placeholder="Display name"
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Credit Value</label>
                  <input type="number" step="0.1" value={newPricing.credit_value} onChange={(e) => setNewPricing((p) => ({ ...p, credit_value: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">3rd Party Cost ({"\u00A3"})</label>
                  <input type="number" step="0.01" value={newPricing.third_party_cost} onChange={(e) => setNewPricing((p) => ({ ...p, third_party_cost: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Sell Price ({"\u00A3"})</label>
                  <input type="number" step="0.01" value={newPricing.sell_price} onChange={(e) => setNewPricing((p) => ({ ...p, sell_price: e.target.value }))}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={createCheckPricing} className="bg-green-600 hover:bg-green-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><Save size={12} /> Save</button>
                <button onClick={() => setAddingPricing(false)} className="bg-slate-600 hover:bg-slate-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><X size={12} /> Cancel</button>
              </div>
            </div>
          )}

          {/* Pricing table */}
          {pricingLoading ? (
            <div className="text-center py-8"><RefreshCw size={24} className="animate-spin mx-auto text-slate-400" /></div>
          ) : checkPricing.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Tag size={40} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No per-check pricing configured{selectedIndustry ? " for this industry" : ""}. Select an industry and add pricing.</p>
            </div>
          ) : (
            <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Industry</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Check Type</th>
                    <th className="py-3 px-3 text-left text-slate-400 text-xs">Label</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Credits</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">3rd Party ({"\u00A3"})</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Sell Price ({"\u00A3"})</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Margin ({"\u00A3"})</th>
                    <th className="py-3 px-3 text-center text-slate-400 text-xs">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {checkPricing.map((cp) => {
                    const isEditing = editingPricingId === String(cp.id);
                    const margin = Number(cp.sell_price || 0) - Number(cp.third_party_cost || 0);
                    return (
                      <tr key={String(cp.id)} className="hover:bg-slate-700/20">
                        <td className="py-3 px-3 text-slate-300 text-xs">{String(cp.industry_name || "-")}</td>
                        <td className="py-3 px-3 text-white font-medium text-xs">{String(cp.check_type || "").replace(/_/g, " ")}</td>
                        <td className="py-3 px-3">
                          {isEditing ? (
                            <input type="text" value={editPricingData.label} onChange={(e) => setEditPricingData((p) => ({ ...p, label: e.target.value }))}
                              className="w-full bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs" />
                          ) : <span className="text-slate-300 text-xs">{String(cp.label || "-")}</span>}
                        </td>
                        <td className="py-3 px-3 text-center">
                          {isEditing ? (
                            <input type="number" step="0.1" value={editPricingData.credit_value} onChange={(e) => setEditPricingData((p) => ({ ...p, credit_value: e.target.value }))}
                              className="w-16 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                          ) : <span className="text-blue-400 font-medium text-xs">{Number(cp.credit_value || 0).toFixed(1)}</span>}
                        </td>
                        <td className="py-3 px-3 text-center">
                          {isEditing ? (
                            <input type="number" step="0.01" value={editPricingData.third_party_cost} onChange={(e) => setEditPricingData((p) => ({ ...p, third_party_cost: e.target.value }))}
                              className="w-20 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                          ) : <span className="text-slate-300 text-xs">{"\u00A3"}{Number(cp.third_party_cost || 0).toFixed(2)}</span>}
                        </td>
                        <td className="py-3 px-3 text-center">
                          {isEditing ? (
                            <input type="number" step="0.01" value={editPricingData.sell_price} onChange={(e) => setEditPricingData((p) => ({ ...p, sell_price: e.target.value }))}
                              className="w-20 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                          ) : <span className="text-emerald-400 font-medium text-xs">{"\u00A3"}{Number(cp.sell_price || 0).toFixed(2)}</span>}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className={`text-xs font-medium ${margin >= 0 ? "text-green-400" : "text-red-400"}`}>{"\u00A3"}{margin.toFixed(2)}</span>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {isEditing ? (<>
                              <button onClick={() => updateCheckPricing(String(cp.id))} className="text-green-400 hover:text-green-300"><Save size={14} /></button>
                              <button onClick={() => setEditingPricingId(null)} className="text-slate-400 hover:text-white"><X size={14} /></button>
                            </>) : (<>
                              <button onClick={() => startEditPricing(cp)} className="text-slate-400 hover:text-blue-400"><Edit size={14} /></button>
                              <button onClick={() => deleteCheckPricing(String(cp.id))} className="text-slate-400 hover:text-red-400"><Trash2 size={14} /></button>
                            </>)}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Pricing Matrix */}
      {activeTab === "matrix" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Pricing Matrix</h3>
              <p className="text-slate-400 text-xs mt-0.5">View and edit per-check pricing for each industry</p>
            </div>
            <button onClick={() => { loadPricingMatrix(); if (matrixSelectedIndustry) loadMatrixIndustryPricing(matrixSelectedIndustry); }}
              className="text-slate-400 hover:text-white flex items-center gap-1 text-sm">
              <RefreshCw size={14} className={matrixLoading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          {/* Clickable industry tabs */}
          <div className="flex gap-1 overflow-x-auto pb-1">
            {templates.map((ind) => (
              <button key={String(ind.id)}
                onClick={() => setMatrixSelectedIndustry(matrixSelectedIndustry === String(ind.id) ? "" : String(ind.id))}
                className={`px-4 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  matrixSelectedIndustry === String(ind.id)
                    ? "bg-blue-600 text-white"
                    : "bg-slate-700/50 text-slate-300 hover:bg-slate-600/50"
                }`}>
                {String(ind.name)}
              </button>
            ))}
          </div>

          {/* Selected industry pricing editor */}
          {matrixSelectedIndustry ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-white font-medium">
                  {String(templates.find((t) => String(t.id) === matrixSelectedIndustry)?.name || "")} — Per-Check Pricing
                </h4>
                <button onClick={() => setMatrixAddingCheck(true)}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1">
                  <PlusCircle size={12} /> Add Check
                </button>
              </div>

              {/* Add check form */}
              {matrixAddingCheck && (
                <div className="bg-slate-800/80 rounded-xl border border-blue-500/30 p-4">
                  <h4 className="text-white font-medium mb-3 text-sm">Add Check Pricing</h4>
                  <div className="grid grid-cols-5 gap-3">
                    <div>
                      <label className="block text-slate-400 text-xs mb-1">Check Type</label>
                      <select value={matrixNewCheck.check_type} onChange={(e) => setMatrixNewCheck((p) => ({ ...p, check_type: e.target.value }))}
                        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs">
                        <option value="">Select check...</option>
                        {checkTypeOptions.map((ct) => (
                          <option key={ct} value={ct}>{ct.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 text-xs mb-1">Label</label>
                      <input type="text" value={matrixNewCheck.label} onChange={(e) => setMatrixNewCheck((p) => ({ ...p, label: e.target.value }))}
                        placeholder="Display name" className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-xs mb-1">Credit Value</label>
                      <input type="number" step="0.1" value={matrixNewCheck.credit_value} onChange={(e) => setMatrixNewCheck((p) => ({ ...p, credit_value: e.target.value }))}
                        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-xs mb-1">3rd Party Cost ({"\u00A3"})</label>
                      <input type="number" step="0.01" value={matrixNewCheck.third_party_cost} onChange={(e) => setMatrixNewCheck((p) => ({ ...p, third_party_cost: e.target.value }))}
                        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-xs mb-1">Sell Price ({"\u00A3"})</label>
                      <input type="number" step="0.01" value={matrixNewCheck.sell_price} onChange={(e) => setMatrixNewCheck((p) => ({ ...p, sell_price: e.target.value }))}
                        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-xs" />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button onClick={matrixAddCheck} className="bg-green-600 hover:bg-green-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><Save size={12} /> Save</button>
                    <button onClick={() => setMatrixAddingCheck(false)} className="bg-slate-600 hover:bg-slate-700 text-white px-4 py-1.5 rounded-lg text-xs flex items-center gap-1"><X size={12} /> Cancel</button>
                  </div>
                </div>
              )}

              {/* Industry pricing table */}
              {matrixIndustryPricing.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Tag size={32} className="mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No per-check pricing configured for this industry yet.</p>
                  <p className="text-xs mt-1">Click "Add Check" above to start adding pricing.</p>
                </div>
              ) : (
                <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="py-3 px-3 text-left text-slate-400 text-xs">Check Type</th>
                        <th className="py-3 px-3 text-left text-slate-400 text-xs">Label</th>
                        <th className="py-3 px-3 text-center text-slate-400 text-xs">Credits</th>
                        <th className="py-3 px-3 text-center text-slate-400 text-xs">3rd Party ({"\u00A3"})</th>
                        <th className="py-3 px-3 text-center text-slate-400 text-xs">Sell Price ({"\u00A3"})</th>
                        <th className="py-3 px-3 text-center text-slate-400 text-xs">Margin ({"\u00A3"})</th>
                        <th className="py-3 px-3 text-center text-slate-400 text-xs">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/50">
                      {matrixIndustryPricing.map((cp) => {
                        const isEd = matrixEditingId === String(cp.id);
                        const margin = Number(cp.sell_price || 0) - Number(cp.third_party_cost || 0);
                        return (
                          <tr key={String(cp.id)} className="hover:bg-slate-700/20">
                            <td className="py-3 px-3 text-white font-medium text-xs">{String(cp.check_type || "").replace(/_/g, " ")}</td>
                            <td className="py-3 px-3">
                              {isEd ? (
                                <input type="text" value={matrixEditData.label} onChange={(e) => setMatrixEditData((p) => ({ ...p, label: e.target.value }))}
                                  className="w-full bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs" />
                              ) : <span className="text-slate-300 text-xs">{String(cp.label || "-")}</span>}
                            </td>
                            <td className="py-3 px-3 text-center">
                              {isEd ? (
                                <input type="number" step="0.1" value={matrixEditData.credit_value} onChange={(e) => setMatrixEditData((p) => ({ ...p, credit_value: e.target.value }))}
                                  className="w-16 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                              ) : <span className="text-blue-400 font-medium text-xs">{Number(cp.credit_value || 0).toFixed(1)}</span>}
                            </td>
                            <td className="py-3 px-3 text-center">
                              {isEd ? (
                                <input type="number" step="0.01" value={matrixEditData.third_party_cost} onChange={(e) => setMatrixEditData((p) => ({ ...p, third_party_cost: e.target.value }))}
                                  className="w-20 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                              ) : <span className="text-slate-300 text-xs">{"\u00A3"}{Number(cp.third_party_cost || 0).toFixed(2)}</span>}
                            </td>
                            <td className="py-3 px-3 text-center">
                              {isEd ? (
                                <input type="number" step="0.01" value={matrixEditData.sell_price} onChange={(e) => setMatrixEditData((p) => ({ ...p, sell_price: e.target.value }))}
                                  className="w-20 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center" />
                              ) : <span className="text-emerald-400 font-medium text-xs">{"\u00A3"}{Number(cp.sell_price || 0).toFixed(2)}</span>}
                            </td>
                            <td className="py-3 px-3 text-center">
                              <span className={`text-xs font-medium ${margin >= 0 ? "text-green-400" : "text-red-400"}`}>{"\u00A3"}{margin.toFixed(2)}</span>
                            </td>
                            <td className="py-3 px-3 text-center">
                              <div className="flex items-center justify-center gap-1">
                                {isEd ? (<>
                                  <button onClick={() => matrixSaveEdit(String(cp.id))} className="text-green-400 hover:text-green-300"><Save size={14} /></button>
                                  <button onClick={() => setMatrixEditingId(null)} className="text-slate-400 hover:text-white"><X size={14} /></button>
                                </>) : (<>
                                  <button onClick={() => matrixStartEdit(cp)} className="text-slate-400 hover:text-blue-400"><Edit size={14} /></button>
                                  <button onClick={() => matrixDeleteCheck(String(cp.id))} className="text-slate-400 hover:text-red-400"><Trash2 size={14} /></button>
                                </>)}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            /* No industry selected — show overview */
            matrixLoading ? (
              <div className="text-center py-8"><RefreshCw size={24} className="animate-spin mx-auto text-slate-400" /></div>
            ) : (
              <div className="space-y-4">
                <div className="text-center py-8 text-slate-500">
                  <CreditCard size={40} className="mx-auto mb-3 opacity-50" />
                  <p className="text-sm">Select an industry above to view and edit its per-check pricing.</p>
                </div>

                {/* Overview matrix table (read-only) */}
                {pricingMatrix && ((pricingMatrix as Record<string, unknown>).check_types as string[] || []).length > 0 && (
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-700/50">
                        <tr>
                          <th className="py-3 px-3 text-left text-slate-400 sticky left-0 bg-slate-700/50">Check Type</th>
                          {((pricingMatrix as Record<string, unknown>).industries as Record<string, unknown>[] || []).map((ind) => (
                            <th key={String(ind.id)} className="py-3 px-3 text-center text-slate-400 cursor-pointer hover:text-blue-400"
                              onClick={() => setMatrixSelectedIndustry(String(ind.id))}>
                              {String(ind.name || "").slice(0, 18)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/50">
                        {((pricingMatrix as Record<string, unknown>).check_types as string[] || []).map((ct) => (
                          <tr key={ct} className="hover:bg-slate-700/20">
                            <td className="py-2 px-3 text-white font-medium sticky left-0 bg-slate-800/80">{ct.replace(/_/g, " ")}</td>
                            {((pricingMatrix as Record<string, unknown>).industries as Record<string, unknown>[] || []).map((ind) => {
                              const matrix = (pricingMatrix as Record<string, unknown>).matrix as Record<string, Record<string, Record<string, number>>>;
                              const data = matrix?.[String(ind.name)]?.[ct];
                              return (
                                <td key={String(ind.id)} className="py-2 px-3 text-center cursor-pointer hover:bg-slate-600/30"
                                  onClick={() => setMatrixSelectedIndustry(String(ind.id))}>
                                  {data ? (
                                    <div className="space-y-0.5">
                                      <div className="text-emerald-400 font-medium">{"\u00A3"}{data.sell_price?.toFixed(2)}</div>
                                      <div className="text-slate-500">{data.credit_value?.toFixed(1)} cr</div>
                                    </div>
                                  ) : (
                                    <span className="text-slate-600">-</span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Default rates reference */}
                {pricingMatrix && ((pricingMatrix as Record<string, unknown>).default_rates as Record<string, unknown>[] || []).length > 0 && (
                  <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-4">
                    <h4 className="text-white font-medium mb-3 flex items-center gap-2"><DollarSign size={16} className="text-amber-400" /> Default Credit Rates (fallback)</h4>
                    <div className="grid grid-cols-4 gap-2">
                      {((pricingMatrix as Record<string, unknown>).default_rates as Record<string, unknown>[]).map((rate) => (
                        <div key={String(rate.check_type)} className="bg-slate-700/30 rounded-lg p-2 border border-slate-600/50">
                          <p className="text-slate-400 text-xs">{String(rate.label || rate.check_type)}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-blue-400 text-xs font-medium">{Number(rate.credit_value || 0).toFixed(1)} cr</span>
                            <span className="text-slate-500 text-xs">{"\u00A3"}{Number(rate.third_party_cost || 0).toFixed(2)} cost</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
