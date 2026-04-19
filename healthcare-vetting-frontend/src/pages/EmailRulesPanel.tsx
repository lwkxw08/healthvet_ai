import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { emailRulesApi, emailTemplatesApi } from "../api/client";
import {
  GitBranch, Plus, Edit, Trash2, CheckCircle, XCircle,
  Zap, ArrowRight, Save, X, ChevronDown, ChevronUp, Info,
} from "lucide-react";

interface EmailRule {
  id: string;
  action_trigger: string;
  name: string;
  description: string;
  template_key: string;
  recipient_type: string;
  conditions: string;
  priority: number;
  is_active: number;
  created_at: string;
  updated_at: string;
}

interface TriggerInfo {
  label: string;
  description: string;
  category: string;
}

interface TemplateOption {
  template_key: string;
  name: string;
  category: string;
  is_active: number;
}

// Visual Conditions Builder types and helpers
interface ConditionValues {
  minDaysSinceRequest: string;
  maxDaysLeft: string;
  checkTypes: string[];
  urgency: string;
}

const AVAILABLE_CHECK_TYPES = [
  { value: "dbs", label: "DBS Check" },
  { value: "identity", label: "Identity Verification" },
  { value: "right_to_work", label: "Right to Work" },
  { value: "references", label: "References" },
  { value: "employment", label: "Employment Verification" },
  { value: "registration", label: "Registration Check" },
  { value: "training", label: "Training Verification" },
  { value: "monitoring", label: "Continuous Monitoring" },
];

const URGENCY_OPTIONS = [
  { value: "", label: "Any urgency" },
  { value: "First Reminder", label: "First Reminder" },
  { value: "Second Reminder", label: "Second Reminder" },
  { value: "Final Notice", label: "Final Notice" },
  { value: "Overdue", label: "Overdue" },
];

const EMPTY_CONDITIONS: ConditionValues = { minDaysSinceRequest: "", maxDaysLeft: "", checkTypes: [], urgency: "" };

function jsonToConditionValues(jsonStr: string): ConditionValues {
  try {
    const obj = JSON.parse(jsonStr || "{}");
    return {
      minDaysSinceRequest: obj.min_days_since_request?.toString() || "",
      maxDaysLeft: obj.max_days_left?.toString() || "",
      checkTypes: Array.isArray(obj.check_types) ? obj.check_types : [],
      urgency: obj.urgency || "",
    };
  } catch {
    return { ...EMPTY_CONDITIONS };
  }
}

function conditionValuesToJson(vals: ConditionValues): string {
  const obj: Record<string, unknown> = {};
  if (vals.minDaysSinceRequest && parseInt(vals.minDaysSinceRequest) > 0)
    obj.min_days_since_request = parseInt(vals.minDaysSinceRequest);
  if (vals.maxDaysLeft && parseInt(vals.maxDaysLeft) > 0)
    obj.max_days_left = parseInt(vals.maxDaysLeft);
  if (vals.checkTypes.length > 0)
    obj.check_types = vals.checkTypes;
  if (vals.urgency)
    obj.urgency = vals.urgency;
  return JSON.stringify(obj);
}

function ConditionsBuilder({
  values,
  onChange,
}: {
  values: ConditionValues;
  onChange: (v: ConditionValues) => void;
  compact?: boolean;
}) {
  const inputCls = "w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs";
  const hasAny = values.minDaysSinceRequest || values.maxDaysLeft || values.checkTypes.length > 0 || values.urgency;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[11px] text-slate-400">
        <span className="font-medium text-slate-300">Conditions</span>
        {!hasAny && <span className="text-slate-600 italic">(none set &mdash; rule always fires)</span>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[11px] text-slate-500 mb-1">
            Minimum days since request
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="0"
              value={values.minDaysSinceRequest}
              onChange={(e) => onChange({ ...values, minDaysSinceRequest: e.target.value })}
              placeholder="e.g. 7"
              className={inputCls}
            />
            <span className="text-[10px] text-slate-600 whitespace-nowrap">days</span>
          </div>
          <p className="text-[10px] text-slate-600 mt-1">Only fire if request was sent at least this many days ago</p>
        </div>

        <div>
          <label className="block text-[11px] text-slate-500 mb-1">
            Maximum days until expiry
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="0"
              value={values.maxDaysLeft}
              onChange={(e) => onChange({ ...values, maxDaysLeft: e.target.value })}
              placeholder="e.g. 14"
              className={inputCls}
            />
            <span className="text-[10px] text-slate-600 whitespace-nowrap">days</span>
          </div>
          <p className="text-[10px] text-slate-600 mt-1">Only fire if credential expires within this many days</p>
        </div>

        <div>
          <label className="block text-[11px] text-slate-500 mb-1">
            Urgency level
          </label>
          <select
            value={values.urgency}
            onChange={(e) => onChange({ ...values, urgency: e.target.value })}
            className={inputCls}
          >
            {URGENCY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <p className="text-[10px] text-slate-600 mt-1">Only fire for this urgency level (e.g. payment reminders)</p>
        </div>

        <div>
          <label className="block text-[11px] text-slate-500 mb-1">
            Specific check types only
          </label>
          <div className="bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 max-h-28 overflow-y-auto space-y-1">
            {AVAILABLE_CHECK_TYPES.map((ct) => (
              <label key={ct.value} className="flex items-center gap-2 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={values.checkTypes.includes(ct.value)}
                  onChange={(e) => {
                    const newTypes = e.target.checked
                      ? [...values.checkTypes, ct.value]
                      : values.checkTypes.filter((t) => t !== ct.value);
                    onChange({ ...values, checkTypes: newTypes });
                  }}
                  className="rounded border-slate-600 bg-slate-800 text-blue-500"
                />
                <span className="text-slate-400">{ct.label}</span>
              </label>
            ))}
          </div>
          <p className="text-[10px] text-slate-600 mt-1">Leave all unchecked to apply to all check types</p>
        </div>
      </div>
    </div>
  );
}

export default function EmailRulesPanel() {
  const { token } = useAuth();
  const [rules, setRules] = useState<EmailRule[]>([]);
  const [triggers, setTriggers] = useState<Record<string, TriggerInfo>>({});
  const [templates, setTemplates] = useState<TemplateOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [expandedTrigger, setExpandedTrigger] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Edit state
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editTemplateKey, setEditTemplateKey] = useState("");
  const [editRecipientType, setEditRecipientType] = useState("primary");
  const [editConditions, setEditConditions] = useState<ConditionValues>({ ...EMPTY_CONDITIONS });
  const [editPriority, setEditPriority] = useState(0);
  const [saving, setSaving] = useState(false);

  // Create state
  const [newTrigger, setNewTrigger] = useState("");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newTemplateKey, setNewTemplateKey] = useState("");
  const [newRecipientType, setNewRecipientType] = useState("primary");
  const [newConditions, setNewConditions] = useState<ConditionValues>({ ...EMPTY_CONDITIONS });
  const [newPriority, setNewPriority] = useState(0);
  const [creating, setCreating] = useState(false);

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 3000);
  };

  const loadRules = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailRulesApi.list(token);
      setRules(((result as unknown) as { rules: EmailRule[] }).rules || []);
    } catch (e) {
      console.error("Failed to load rules", e);
    }
  }, [token]);

  const loadTriggers = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailRulesApi.triggers(token);
      setTriggers(((result as unknown) as { triggers: Record<string, TriggerInfo> }).triggers || {});
    } catch { /* ignore */ }
  }, [token]);

  const loadTemplates = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailTemplatesApi.list(token);
      const tpls = ((result as unknown) as { templates: TemplateOption[] }).templates || [];
      setTemplates(tpls);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadRules(), loadTriggers(), loadTemplates()]).finally(() => setLoading(false));
  }, [loadRules, loadTriggers, loadTemplates]);

  // Group rules by action_trigger
  const rulesByTrigger: Record<string, EmailRule[]> = {};
  for (const rule of rules) {
    if (!rulesByTrigger[rule.action_trigger]) {
      rulesByTrigger[rule.action_trigger] = [];
    }
    rulesByTrigger[rule.action_trigger].push(rule);
  }

  // Get all known triggers (including ones with no rules)
  const allTriggers = new Set([...Object.keys(triggers), ...Object.keys(rulesByTrigger)]);
  const sortedTriggers = Array.from(allTriggers).sort();

  const startEdit = (rule: EmailRule) => {
    setEditingRule(rule.id);
    setEditName(rule.name);
    setEditDescription(rule.description || "");
    setEditTemplateKey(rule.template_key);
    setEditRecipientType(rule.recipient_type);
    setEditConditions(jsonToConditionValues(typeof rule.conditions === "string" ? rule.conditions : JSON.stringify(rule.conditions)));
    setEditPriority(rule.priority);
  };

  const handleSave = async (ruleId: string) => {
    if (!token) return;
    setSaving(true);
    try {
      const condJson = conditionValuesToJson(editConditions);
      let parsedConditions = {};
      try { parsedConditions = JSON.parse(condJson); } catch { /* keep empty */ }
      await emailRulesApi.update(token, ruleId, {
        name: editName,
        description: editDescription,
        template_key: editTemplateKey,
        recipient_type: editRecipientType,
        conditions: parsedConditions,
        priority: editPriority,
      });
      showMsg("Rule updated");
      setEditingRule(null);
      await loadRules();
    } catch {
      showMsg("Failed to update rule");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (rule: EmailRule) => {
    if (!token) return;
    try {
      await emailRulesApi.update(token, rule.id, { is_active: !rule.is_active });
      showMsg(rule.is_active ? "Rule disabled" : "Rule enabled");
      await loadRules();
    } catch {
      showMsg("Failed to update rule");
    }
  };

  const handleDelete = async (rule: EmailRule) => {
    if (!token) return;
    if (!confirm(`Delete rule "${rule.name}"? This cannot be undone.`)) return;
    try {
      await emailRulesApi.remove(token, rule.id);
      showMsg("Rule deleted");
      await loadRules();
    } catch {
      showMsg("Failed to delete rule");
    }
  };

  const handleCreate = async () => {
    if (!token || !newTrigger || !newName || !newTemplateKey) return;
    setCreating(true);
    try {
      const condJson = conditionValuesToJson(newConditions);
      let parsedConditions = {};
      try { parsedConditions = JSON.parse(condJson); } catch { /* keep empty */ }
      await emailRulesApi.create(token, {
        action_trigger: newTrigger,
        name: newName,
        description: newDescription,
        template_key: newTemplateKey,
        recipient_type: newRecipientType,
        conditions: parsedConditions,
        priority: newPriority,
      });
      showMsg("Rule created");
      setShowCreateForm(false);
      setNewTrigger("");
      setNewName("");
      setNewDescription("");
      setNewTemplateKey("");
      setNewRecipientType("primary");
      setNewConditions({ ...EMPTY_CONDITIONS });
      setNewPriority(0);
      await loadRules();
    } catch {
      showMsg("Failed to create rule");
    } finally {
      setCreating(false);
    }
  };

  const triggerCategoryColors: Record<string, string> = {
    verification: "text-blue-400 bg-blue-400/10 border-blue-400/30",
    compliance: "text-amber-400 bg-amber-400/10 border-amber-400/30",
    billing: "text-green-400 bg-green-400/10 border-green-400/30",
    onboarding: "text-purple-400 bg-purple-400/10 border-purple-400/30",
  };

  const recipientLabels: Record<string, string> = {
    primary: "Primary",
    agency: "Agency",
    candidate: "Candidate",
    referee: "Referee",
    admin: "Admin",
  };

  const parseConditions = (condStr: string): Record<string, unknown> => {
    try { return JSON.parse(condStr || "{}"); } catch { return {}; }
  };

  const conditionSummary = (condStr: string): string => {
    const conds = parseConditions(condStr);
    const parts: string[] = [];
    if (conds.min_days_since_request) parts.push(`after ${conds.min_days_since_request} days`);
    if (conds.max_days_left) parts.push(`within ${conds.max_days_left} days of expiry`);
    if (conds.check_types && Array.isArray(conds.check_types)) parts.push(`types: ${(conds.check_types as string[]).join(", ")}`);
    if (conds.urgency) parts.push(`urgency: ${conds.urgency}`);
    return parts.length > 0 ? parts.join(" | ") : "No conditions (always fires)";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-400 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <GitBranch className="text-purple-400" size={22} /> Email Rules
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Configure which email template fires for each business action. Rules map triggers to templates with optional conditions.
          </p>
        </div>
        <button onClick={() => setShowCreateForm(!showCreateForm)}
          className="text-xs px-4 py-2 rounded-lg bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 flex items-center gap-1">
          <Plus size={14} /> Add Rule
        </button>
      </div>

      {message && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-3 text-blue-300 text-sm">
          {message}
        </div>
      )}

      {/* How It Works */}
      <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 px-5 py-4">
        <div className="flex items-start gap-3">
          <Info className="text-blue-400 flex-shrink-0 mt-0.5" size={16} />
          <div className="text-xs text-slate-400 space-y-1">
            <p><strong className="text-slate-300">How it works:</strong> When the app performs an action (e.g. credential expiring, invoice created), it looks up rules for that trigger. The first matching active rule determines which email template is sent.</p>
            <p>You can have <strong className="text-slate-300">multiple rules per trigger</strong> for different recipients (e.g. send expiry warning to both agency AND candidate). Use <strong className="text-slate-300">conditions</strong> to add filters (e.g. only fire if days left &lt; 14). Rules are evaluated in <strong className="text-slate-300">priority order</strong> (lower number = higher priority).</p>
          </div>
        </div>
      </div>

      {/* Create Rule Form */}
      {showCreateForm && (
        <div className="bg-slate-800/60 rounded-xl border border-blue-500/30 p-5 space-y-4">
          <p className="text-sm font-semibold text-blue-300 flex items-center gap-2"><Plus size={14} /> Create New Rule</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Action Trigger</label>
              <select value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs">
                <option value="">Select a trigger...</option>
                {sortedTriggers.map((t) => (
                  <option key={t} value={t}>{triggers[t]?.label || t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Template</label>
              <select value={newTemplateKey} onChange={(e) => setNewTemplateKey(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs">
                <option value="">Select a template...</option>
                {templates.map((t) => (
                  <option key={t.template_key} value={t.template_key}>{t.name} ({t.template_key})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Rule Name</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Urgent Expiry Warning"
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs" />
            </div>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Recipient Type</label>
              <select value={newRecipientType} onChange={(e) => setNewRecipientType(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs">
                {Object.entries(recipientLabels).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-[11px] text-slate-500 mb-1">Description</label>
              <input value={newDescription} onChange={(e) => setNewDescription(e.target.value)}
                placeholder="When this rule should fire..."
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs" />
            </div>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">Priority (lower = first)</label>
              <input type="number" value={newPriority} onChange={(e) => setNewPriority(parseInt(e.target.value) || 0)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs" />
            </div>
          </div>

          <div className="border-t border-slate-700/50 pt-4">
            <ConditionsBuilder values={newConditions} onChange={setNewConditions} />
          </div>

          <div className="flex gap-2 pt-2">
            <button onClick={handleCreate} disabled={creating || !newTrigger || !newName || !newTemplateKey}
              className="bg-blue-500 hover:bg-blue-600 text-white text-xs px-4 py-2 rounded-lg disabled:opacity-50">
              {creating ? "Creating..." : "Create Rule"}
            </button>
            <button onClick={() => setShowCreateForm(false)}
              className="text-slate-400 hover:text-white text-xs px-4 py-2 rounded-lg border border-slate-700">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Rules by Trigger */}
      <div className="space-y-3">
        {sortedTriggers.map((triggerKey) => {
          const triggerInfo = triggers[triggerKey];
          const triggerRules = rulesByTrigger[triggerKey] || [];
          const isExpanded = expandedTrigger === triggerKey;
          const category = triggerInfo?.category || "general";
          const activeRules = triggerRules.filter(r => r.is_active);

          return (
            <div key={triggerKey} className="bg-slate-800/40 rounded-xl border border-slate-700/50 overflow-hidden">
              {/* Trigger Header */}
              <button
                onClick={() => setExpandedTrigger(isExpanded ? null : triggerKey)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/60 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Zap size={16} className={category === "verification" ? "text-blue-400" : category === "compliance" ? "text-amber-400" : category === "billing" ? "text-green-400" : "text-purple-400"} />
                  <div className="text-left">
                    <p className="text-white text-sm font-medium">{triggerInfo?.label || triggerKey}</p>
                    <p className="text-slate-500 text-xs mt-0.5">{triggerInfo?.description || ""}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${triggerCategoryColors[category] || "text-slate-400 bg-slate-400/10 border-slate-400/30"}`}>
                    {category}
                  </span>
                  <span className="text-xs text-slate-500">
                    {activeRules.length} active rule{activeRules.length !== 1 ? "s" : ""}
                  </span>
                  {isExpanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
                </div>
              </button>

              {/* Rules List */}
              {isExpanded && (
                <div className="border-t border-slate-700/50">
                  {triggerRules.length === 0 ? (
                    <div className="px-5 py-6 text-center">
                      <p className="text-slate-500 text-sm">No rules configured for this trigger</p>
                      <button onClick={() => { setShowCreateForm(true); setNewTrigger(triggerKey); }}
                        className="text-blue-400 text-xs mt-2 hover:underline">
                        + Add a rule
                      </button>
                    </div>
                  ) : (
                    <div className="divide-y divide-slate-700/30">
                      {triggerRules.map((rule) => (
                        <div key={rule.id} className={`px-5 py-3 ${!rule.is_active ? "opacity-50" : ""}`}>
                          {editingRule === rule.id ? (
                            /* Edit Mode */
                            <div className="space-y-3">
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <label className="block text-[10px] text-slate-500 mb-1">Name</label>
                                  <input value={editName} onChange={(e) => setEditName(e.target.value)}
                                    className="w-full bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-white text-xs" />
                                </div>
                                <div>
                                  <label className="block text-[10px] text-slate-500 mb-1">Template</label>
                                  <select value={editTemplateKey} onChange={(e) => setEditTemplateKey(e.target.value)}
                                    className="w-full bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-white text-xs">
                                    {templates.map((t) => (
                                      <option key={t.template_key} value={t.template_key}>{t.name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-[10px] text-slate-500 mb-1">Recipient</label>
                                  <select value={editRecipientType} onChange={(e) => setEditRecipientType(e.target.value)}
                                    className="w-full bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-white text-xs">
                                    {Object.entries(recipientLabels).map(([k, v]) => (
                                      <option key={k} value={k}>{v}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-[10px] text-slate-500 mb-1">Priority</label>
                                  <input type="number" value={editPriority} onChange={(e) => setEditPriority(parseInt(e.target.value) || 0)}
                                    className="w-full bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-white text-xs" />
                                </div>
                                <div className="col-span-2">
                                  <label className="block text-[10px] text-slate-500 mb-1">Description</label>
                                  <input value={editDescription} onChange={(e) => setEditDescription(e.target.value)}
                                    className="w-full bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-white text-xs" />
                                </div>
                              </div>
                              <div className="border-t border-slate-700/30 pt-3">
                                <ConditionsBuilder values={editConditions} onChange={setEditConditions} compact />
                              </div>
                              <div className="flex gap-2">
                                <button onClick={() => handleSave(rule.id)} disabled={saving}
                                  className="bg-blue-500 hover:bg-blue-600 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-50">
                                  <Save size={11} /> {saving ? "Saving..." : "Save"}
                                </button>
                                <button onClick={() => setEditingRule(null)}
                                  className="text-slate-400 hover:text-white text-xs px-3 py-1.5 rounded border border-slate-700 flex items-center gap-1">
                                  <X size={11} /> Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            /* View Mode */
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                <div className="flex items-center gap-2 text-xs">
                                  <span className="text-slate-400 font-medium">{rule.name}</span>
                                  <ArrowRight size={12} className="text-slate-600" />
                                  <code className="text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded text-[11px]">{rule.template_key}</code>
                                </div>
                                <span className="text-[10px] text-slate-600 px-1.5 py-0.5 rounded bg-slate-700/30">
                                  {recipientLabels[rule.recipient_type] || rule.recipient_type}
                                </span>
                                <span className="text-[10px] text-slate-600 italic hidden lg:inline">
                                  {conditionSummary(rule.conditions)}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className="text-[10px] text-slate-600">P{rule.priority}</span>
                                <button onClick={() => handleToggleActive(rule)}
                                  className={`p-1 rounded ${rule.is_active ? "text-green-400 hover:bg-green-400/10" : "text-red-400 hover:bg-red-400/10"}`}
                                  title={rule.is_active ? "Active (click to disable)" : "Disabled (click to enable)"}>
                                  {rule.is_active ? <CheckCircle size={14} /> : <XCircle size={14} />}
                                </button>
                                <button onClick={() => startEdit(rule)}
                                  className="p-1 rounded text-amber-400 hover:bg-amber-400/10" title="Edit rule">
                                  <Edit size={14} />
                                </button>
                                <button onClick={() => handleDelete(rule)}
                                  className="p-1 rounded text-red-400 hover:bg-red-400/10" title="Delete rule">
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Conditions Reference */}
      <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 px-5 py-4">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-3">Conditions Reference</p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-700/50">
            <span className="text-amber-400 font-medium">Minimum days since request</span>
            <p className="text-slate-500 mt-1">Only fire if the verification request was sent at least N days ago. Useful for automated reminders.</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-700/50">
            <span className="text-amber-400 font-medium">Maximum days until expiry</span>
            <p className="text-slate-500 mt-1">Only fire if a credential expires within N days. Useful for urgency-based escalation.</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-700/50">
            <span className="text-amber-400 font-medium">Specific check types</span>
            <p className="text-slate-500 mt-1">Restrict the rule to fire only for certain check types (e.g. DBS only, or Right to Work only).</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-700/50">
            <span className="text-amber-400 font-medium">Urgency level</span>
            <p className="text-slate-500 mt-1">Only fire for a specific urgency level. Useful for payment reminders that escalate over time.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
