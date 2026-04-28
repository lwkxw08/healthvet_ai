import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { emailTemplatesApi } from "../api/client";
import {
  Mail, Eye, Edit, RotateCcw, Send, CheckCircle, XCircle,
  Clock, AlertTriangle, FileText, Settings, ChevronDown, ChevronUp,
  Plus, Trash2,
} from "lucide-react";

interface EmailTemplate {
  id: string;
  template_key: string;
  name: string;
  description: string;
  subject: string;
  body_html: string;
  body_text: string;
  category: string;
  variables: string;
  is_active: number;
  created_at: string;
  updated_at: string;
}

interface SendLogEntry {
  id: string;
  template_key: string;
  recipient_email: string;
  recipient_name: string;
  subject: string;
  status: string;
  created_at: string;
  sent_at: string;
  error_message: string;
}

export default function EmailTemplatesPanel() {
  const { token } = useAuth();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [sendLog, setSendLog] = useState<SendLogEntry[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState<"templates" | "send-log">("templates");
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBodyHtml, setEditBodyHtml] = useState("");
  const [editBodyText, setEditBodyText] = useState("");
  const [editName, setEditName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [testEmail, setTestEmail] = useState("");
  const [showTestSend, setShowTestSend] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTemplateKey, setNewTemplateKey] = useState("");
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateCategory, setNewTemplateCategory] = useState("general");
  const [newTemplateDesc, setNewTemplateDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const showMessage = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 3000);
  };

  const loadTemplates = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailTemplatesApi.list(token);
      setTemplates(((result as unknown) as { templates: EmailTemplate[] }).templates || []);
    } catch (e) {
      console.error("Failed to load templates", e);
    }
  }, [token]);

  const loadStats = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailTemplatesApi.stats(token);
      setStats(result as Record<string, unknown>);
    } catch { /* ignore */ }
  }, [token]);

  const loadSendLog = useCallback(async () => {
    if (!token) return;
    try {
      const result = await emailTemplatesApi.sendLog(token, 100);
      setSendLog(((result as unknown) as { log: SendLogEntry[] }).log || []);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadTemplates(), loadStats(), loadSendLog()]).finally(() => setLoading(false));
  }, [loadTemplates, loadStats, loadSendLog]);

  const handleSelectTemplate = (tpl: EmailTemplate) => {
    setSelectedTemplate(tpl);
    setEditMode(false);
    setPreviewMode(false);
    setShowTestSend(false);
  };

  const handleStartEdit = () => {
    if (!selectedTemplate) return;
    setEditName(selectedTemplate.name);
    setEditSubject(selectedTemplate.subject);
    setEditBodyHtml(selectedTemplate.body_html);
    setEditBodyText(selectedTemplate.body_text || "");
    setEditMode(true);
    setPreviewMode(false);
  };

  const handleSave = async () => {
    if (!selectedTemplate || !token) return;
    setSaving(true);
    try {
      const updated = await emailTemplatesApi.update(token, selectedTemplate.id, {
        name: editName,
        subject: editSubject,
        body_html: editBodyHtml,
        body_text: editBodyText,
      });
      setSelectedTemplate((updated as unknown) as EmailTemplate);
      setEditMode(false);
      showMessage("Template saved successfully");
      await loadTemplates();
    } catch (e) {
      showMessage("Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selectedTemplate || !token) return;
    if (!confirm("Reset this template to its default content? Your customisations will be lost.")) return;
    try {
      const updated = await emailTemplatesApi.reset(token, selectedTemplate.id);
      setSelectedTemplate((updated as unknown) as EmailTemplate);
      setEditMode(false);
      showMessage("Template reset to default");
      await loadTemplates();
    } catch {
      showMessage("Failed to reset template");
    }
  };

  const handlePreview = async () => {
    if (!selectedTemplate || !token) return;
    try {
      const result = await emailTemplatesApi.preview(token, selectedTemplate.id) as { rendered: { body_html: string } };
      setPreviewHtml(result.rendered?.body_html || "");
      setPreviewMode(true);
      setEditMode(false);
    } catch {
      showMessage("Failed to load preview");
    }
  };

  const handleTestSend = async () => {
    if (!selectedTemplate || !token || !testEmail) return;
    setSendingTest(true);
    try {
      const result = await emailTemplatesApi.testSend(token, {
        template_key: selectedTemplate.template_key,
        recipient_email: testEmail,
        recipient_name: "Test Recipient",
      });
      const status = (result as Record<string, unknown>).status;
      if (status === "sent") {
        showMessage("Test email sent via SendGrid");
      } else if (status === "logged") {
        showMessage("Test email logged (SendGrid not configured — email stored in send log)");
      } else {
        showMessage(`Test send result: ${status}`);
      }
      setShowTestSend(false);
      setTestEmail("");
      await loadSendLog();
      await loadStats();
    } catch {
      showMessage("Failed to send test email");
    } finally {
      setSendingTest(false);
    }
  };

  const handleCreate = async () => {
    if (!token || !newTemplateKey || !newTemplateName) return;
    setCreating(true);
    try {
      const result = await emailTemplatesApi.create(token, {
        template_key: newTemplateKey.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
        name: newTemplateName,
        description: newTemplateDesc,
        subject: `{{subject_placeholder}}`,
        body_html: `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="color:#1e40af;">{{heading}}</h2>
  <p>Dear {{recipient_name}},</p>
  <p>{{body_content}}</p>
  <p>Best regards,<br/>Viper AI Team</p>
</div>`,
        body_text: "Dear {{recipient_name}},\n\n{{body_content}}\n\nBest regards,\nViper AI Team",
        category: newTemplateCategory,
        variables: [
          { key: "recipient_name", description: "Recipient's name" },
          { key: "heading", description: "Email heading" },
          { key: "body_content", description: "Main email body content" },
        ],
      });
      if (result) {
        showMessage("Template created successfully");
        setShowCreateForm(false);
        setNewTemplateKey("");
        setNewTemplateName("");
        setNewTemplateDesc("");
        setNewTemplateCategory("general");
        await loadTemplates();
        setSelectedTemplate((result as unknown) as EmailTemplate);
      }
    } catch {
      showMessage("Failed to create template — key may already exist");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedTemplate || !token) return;
    if (!confirm(`Delete template "${selectedTemplate.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await emailTemplatesApi.remove(token, selectedTemplate.id);
      showMessage("Template deleted");
      setSelectedTemplate(null);
      await loadTemplates();
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      if (errMsg.includes("403") || errMsg.includes("Default")) {
        showMessage("Default templates cannot be deleted");
      } else {
        showMessage("Failed to delete template");
      }
    } finally {
      setDeleting(false);
    }
  };

  const isDefaultTemplate = (tpl: EmailTemplate): boolean => {
    const defaultKeys = [
      "employment_verification_request", "reference_request", "verification_reminder",
      "expiry_warning_agency", "expiry_warning_candidate", "monitoring_alert_summary",
      "invoice_notification", "payment_reminder", "candidate_invite", "subscription_confirmation",
    ];
    return defaultKeys.includes(tpl.template_key);
  };

  const handleToggleActive = async (tpl: EmailTemplate) => {
    if (!token) return;
    try {
      await emailTemplatesApi.update(token, tpl.id, { is_active: !tpl.is_active });
      showMessage(tpl.is_active ? "Template disabled" : "Template enabled");
      await loadTemplates();
      if (selectedTemplate?.id === tpl.id) {
        setSelectedTemplate({ ...tpl, is_active: tpl.is_active ? 0 : 1 });
      }
    } catch {
      showMessage("Failed to update template status");
    }
  };

  const categoryColors: Record<string, string> = {
    verification: "text-blue-400 bg-blue-400/10 border-blue-400/30",
    compliance: "text-amber-400 bg-amber-400/10 border-amber-400/30",
    billing: "text-green-400 bg-green-400/10 border-green-400/30",
    onboarding: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    general: "text-slate-400 bg-slate-400/10 border-slate-400/30",
  };

  const statusColors: Record<string, string> = {
    sent: "text-green-400",
    logged: "text-blue-400",
    failed: "text-red-400",
    queued: "text-amber-400",
  };

  const statusIcons: Record<string, JSX.Element> = {
    sent: <CheckCircle size={14} className="text-green-400" />,
    logged: <FileText size={14} className="text-blue-400" />,
    failed: <XCircle size={14} className="text-red-400" />,
    queued: <Clock size={14} className="text-amber-400" />,
  };

  const parseVariables = (varsJson: string): { key: string; description: string }[] => {
    try { return JSON.parse(varsJson || "[]"); } catch { return []; }
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Mail className="text-blue-400" size={22} /> Email Templates
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Manage email templates for verification requests, compliance alerts, billing, and onboarding.
            {stats && !(stats as Record<string, unknown>).sendgrid_configured && (
              <span className="text-amber-400 ml-2">
                <AlertTriangle size={12} className="inline mb-0.5" /> Email provider not configured — emails are logged only
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setActiveView("templates")}
            className={`px-4 py-2 text-xs font-medium rounded-lg transition-all ${activeView === "templates" ? "bg-blue-500/20 text-blue-300 border border-blue-500/30" : "text-slate-400 hover:text-white border border-slate-700"}`}>
            Templates
          </button>
          <button onClick={() => { setActiveView("send-log"); loadSendLog(); }}
            className={`px-4 py-2 text-xs font-medium rounded-lg transition-all ${activeView === "send-log" ? "bg-blue-500/20 text-blue-300 border border-blue-500/30" : "text-slate-400 hover:text-white border border-slate-700"}`}>
            Send Log
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Total Emails", value: stats.total, icon: <Mail size={16} className="text-blue-400" /> },
            { label: "Sent (SendGrid)", value: stats.sent, icon: <CheckCircle size={16} className="text-green-400" /> },
            { label: "Logged (No Key)", value: stats.logged, icon: <FileText size={16} className="text-slate-400" /> },
            { label: "Failed", value: stats.failed, icon: <XCircle size={16} className="text-red-400" /> },
          ].map((s) => (
            <div key={s.label} className="bg-slate-800/60 rounded-lg border border-slate-700/50 p-4 flex items-center gap-3">
              {s.icon}
              <div>
                <p className="text-white font-semibold text-lg">{String(s.value || 0)}</p>
                <p className="text-slate-400 text-xs">{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {message && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-3 text-blue-300 text-sm">
          {message}
        </div>
      )}

      {/* Templates View */}
      {activeView === "templates" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Template List */}
          <div className="md:col-span-1 space-y-2">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                {templates.length} Templates
              </p>
              <button onClick={() => setShowCreateForm(!showCreateForm)}
                className="text-xs px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 flex items-center gap-1">
                <Plus size={12} /> New
              </button>
            </div>

            {/* Create New Template Form */}
            {showCreateForm && (
              <div className="bg-slate-800/80 rounded-lg border border-blue-500/30 p-4 space-y-3 mb-3">
                <p className="text-sm font-medium text-blue-300">Create New Template</p>
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1">Template Key</label>
                  <input value={newTemplateKey} onChange={(e) => setNewTemplateKey(e.target.value)}
                    placeholder="e.g. custom_welcome_email"
                    className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1">Name</label>
                  <input value={newTemplateName} onChange={(e) => setNewTemplateName(e.target.value)}
                    placeholder="e.g. Custom Welcome Email"
                    className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-xs" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1">Category</label>
                  <select value={newTemplateCategory} onChange={(e) => setNewTemplateCategory(e.target.value)}
                    className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-xs">
                    <option value="general">General</option>
                    <option value="verification">Verification</option>
                    <option value="compliance">Compliance</option>
                    <option value="billing">Billing</option>
                    <option value="onboarding">Onboarding</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1">Description</label>
                  <input value={newTemplateDesc} onChange={(e) => setNewTemplateDesc(e.target.value)}
                    placeholder="Brief description..."
                    className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-xs" />
                </div>
                <div className="flex gap-2">
                  <button onClick={handleCreate} disabled={creating || !newTemplateKey || !newTemplateName}
                    className="flex-1 bg-blue-500 hover:bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg disabled:opacity-50">
                    {creating ? "Creating..." : "Create Template"}
                  </button>
                  <button onClick={() => setShowCreateForm(false)}
                    className="text-slate-400 hover:text-white text-xs px-3 py-1.5 rounded-lg border border-slate-700">
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {templates.map((tpl) => (
              <button key={tpl.id} onClick={() => handleSelectTemplate(tpl)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedTemplate?.id === tpl.id
                    ? "bg-blue-500/10 border-blue-500/30"
                    : "bg-slate-800/40 border-slate-700/50 hover:border-slate-600"
                }`}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${selectedTemplate?.id === tpl.id ? "text-blue-300" : "text-white"}`}>
                      {tpl.name}
                    </p>
                    <p className="text-xs text-slate-500 mt-1 truncate">{tpl.description}</p>
                  </div>
                  <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${categoryColors[tpl.category] || categoryColors.general}`}>
                      {tpl.category}
                    </span>
                    {!tpl.is_active && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-400/10 text-red-400 border border-red-400/30">off</span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Template Detail */}
          <div className="md:col-span-2">
            {!selectedTemplate ? (
              <div className="bg-slate-800/40 rounded-xl border border-slate-700/50 p-12 text-center">
                <Mail className="text-slate-600 mx-auto mb-3" size={40} />
                <p className="text-slate-500">Select a template to view or edit</p>
              </div>
            ) : previewMode ? (
              /* Preview Mode */
              <div className="bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
                  <div className="flex items-center gap-2">
                    <Eye size={16} className="text-purple-400" />
                    <span className="text-white text-sm font-medium">Preview: {selectedTemplate.name}</span>
                  </div>
                  <button onClick={() => setPreviewMode(false)} className="text-slate-400 hover:text-white text-xs">Close Preview</button>
                </div>
                <div className="p-4">
                  <div className="bg-white rounded-lg overflow-hidden" style={{ maxHeight: "600px", overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
                  </div>
                  <p className="text-slate-500 text-xs mt-3">
                    This preview uses sample placeholder data. Variables shown in brackets will be replaced with real values when emails are sent.
                  </p>
                </div>
              </div>
            ) : editMode ? (
              /* Edit Mode */
              <div className="bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
                  <div className="flex items-center gap-2">
                    <Edit size={16} className="text-amber-400" />
                    <span className="text-white text-sm font-medium">Editing: {selectedTemplate.name}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => setEditMode(false)} className="text-slate-400 hover:text-white text-xs">Cancel</button>
                    <button onClick={handleSave} disabled={saving}
                      className="bg-blue-500 hover:bg-blue-600 text-white text-xs px-4 py-1.5 rounded-lg disabled:opacity-50">
                      {saving ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                </div>
                <div className="p-5 space-y-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Template Name</label>
                    <input value={editName} onChange={(e) => setEditName(e.target.value)}
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Subject Line</label>
                    <input value={editSubject} onChange={(e) => setEditSubject(e.target.value)}
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm" />
                    <p className="text-slate-600 text-[11px] mt-1">Use {"{{variable_name}}"} for dynamic values</p>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">HTML Body</label>
                    <textarea value={editBodyHtml} onChange={(e) => setEditBodyHtml(e.target.value)}
                      rows={16}
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm font-mono text-xs leading-relaxed" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Plain Text Body (fallback)</label>
                    <textarea value={editBodyText} onChange={(e) => setEditBodyText(e.target.value)}
                      rows={8}
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm font-mono text-xs leading-relaxed" />
                  </div>
                </div>
              </div>
            ) : (
              /* View Mode */
              <div className="bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/50">
                  <div>
                    <h3 className="text-white font-semibold">{selectedTemplate.name}</h3>
                    <p className="text-slate-500 text-xs mt-0.5">{selectedTemplate.description}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => handleToggleActive(selectedTemplate)}
                      className={`text-xs px-3 py-1.5 rounded-lg border ${selectedTemplate.is_active ? "text-green-400 border-green-400/30 hover:bg-green-400/10" : "text-red-400 border-red-400/30 hover:bg-red-400/10"}`}>
                      {selectedTemplate.is_active ? "Active" : "Disabled"}
                    </button>
                    <button onClick={handlePreview}
                      className="text-xs px-3 py-1.5 rounded-lg border border-purple-400/30 text-purple-400 hover:bg-purple-400/10 flex items-center gap-1">
                      <Eye size={12} /> Preview
                    </button>
                    <button onClick={handleStartEdit}
                      className="text-xs px-3 py-1.5 rounded-lg border border-amber-400/30 text-amber-400 hover:bg-amber-400/10 flex items-center gap-1">
                      <Edit size={12} /> Edit
                    </button>
                    {isDefaultTemplate(selectedTemplate) && (
                      <button onClick={handleReset}
                        className="text-xs px-3 py-1.5 rounded-lg border border-slate-600 text-slate-400 hover:bg-slate-700/50 flex items-center gap-1">
                        <RotateCcw size={12} /> Reset
                      </button>
                    )}
                    {!isDefaultTemplate(selectedTemplate) && (
                      <button onClick={handleDelete} disabled={deleting}
                        className="text-xs px-3 py-1.5 rounded-lg border border-red-400/30 text-red-400 hover:bg-red-400/10 flex items-center gap-1 disabled:opacity-50">
                        <Trash2 size={12} /> {deleting ? "Deleting..." : "Delete"}
                      </button>
                    )}
                    <button onClick={() => setShowTestSend(!showTestSend)}
                      className="text-xs px-3 py-1.5 rounded-lg border border-blue-400/30 text-blue-400 hover:bg-blue-400/10 flex items-center gap-1">
                      <Send size={12} /> Test Send
                    </button>
                  </div>
                </div>

                {/* Test Send Panel */}
                {showTestSend && (
                  <div className="px-5 py-3 border-b border-slate-700/50 bg-slate-800/60">
                    <div className="flex items-center gap-3">
                      <input
                        type="email"
                        placeholder="Enter recipient email address..."
                        value={testEmail}
                        onChange={(e) => setTestEmail(e.target.value)}
                        className="flex-1 bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm"
                      />
                      <button onClick={handleTestSend} disabled={sendingTest || !testEmail}
                        className="bg-blue-500 hover:bg-blue-600 text-white text-xs px-4 py-2 rounded-lg disabled:opacity-50 flex items-center gap-1">
                        <Send size={12} /> {sendingTest ? "Sending..." : "Send Test"}
                      </button>
                    </div>
                    <p className="text-slate-600 text-[11px] mt-2">
                      {stats && (stats as Record<string, unknown>).sendgrid_configured
                        ? "Email will be sent via SendGrid to the specified address."
                        : "No SendGrid API key configured. Email will be logged in the send log but not actually delivered."}
                    </p>
                  </div>
                )}

                <div className="p-5 space-y-4">
                  {/* Subject */}
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Subject Line</p>
                    <div className="bg-slate-900/50 rounded-lg px-4 py-2.5 text-white text-sm border border-slate-700/50">
                      {selectedTemplate.subject}
                    </div>
                  </div>

                  {/* Variables */}
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Template Variables</p>
                    <div className="flex flex-wrap gap-2">
                      {parseVariables(selectedTemplate.variables).map((v) => (
                        <span key={v.key} className="inline-flex items-center gap-1 text-xs bg-slate-700/50 text-slate-300 px-2.5 py-1 rounded-full border border-slate-600/50"
                          title={v.description}>
                          <code className="text-blue-400">{`{{${v.key}}}`}</code>
                          <span className="text-slate-500">— {v.description}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* HTML Preview Snippet */}
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">HTML Body (raw)</p>
                    <pre className="bg-slate-900/50 rounded-lg px-4 py-3 text-slate-400 text-xs font-mono overflow-auto max-h-48 border border-slate-700/50">
                      {selectedTemplate.body_html.substring(0, 500)}
                      {selectedTemplate.body_html.length > 500 && "..."}
                    </pre>
                  </div>

                  {/* Metadata */}
                  <div className="flex gap-6 text-xs text-slate-500">
                    <span>Key: <code className="text-slate-400">{selectedTemplate.template_key}</code></span>
                    <span>Category: <span className={`${categoryColors[selectedTemplate.category]?.split(" ")[0] || "text-slate-400"}`}>{selectedTemplate.category}</span></span>
                    <span>Updated: {new Date(selectedTemplate.updated_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Send Log View */}
      {activeView === "send-log" && (
        <div className="bg-slate-800/40 rounded-xl border border-slate-700/50">
          <div className="px-5 py-3 border-b border-slate-700/50">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <FileText size={16} className="text-slate-400" /> Email Send Log
            </h3>
            <p className="text-slate-500 text-xs mt-0.5">
              All emails sent or logged by the system. {sendLog.length} entries.
            </p>
          </div>
          {sendLog.length === 0 ? (
            <div className="p-12 text-center">
              <Mail className="text-slate-600 mx-auto mb-3" size={32} />
              <p className="text-slate-500 text-sm">No emails have been sent yet</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700/30">
              {sendLog.map((entry) => (
                <div key={entry.id} className="px-5 py-3 hover:bg-slate-800/30 transition-colors">
                  <div className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedLog(expandedLog === entry.id ? null : entry.id)}>
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      {statusIcons[entry.status] || <Clock size={14} className="text-slate-400" />}
                      <div className="min-w-0 flex-1">
                        <p className="text-white text-sm truncate">{entry.subject}</p>
                        <p className="text-slate-500 text-xs">
                          To: {entry.recipient_name ? `${entry.recipient_name} <${entry.recipient_email}>` : entry.recipient_email}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 flex-shrink-0">
                      <span className={`text-xs ${statusColors[entry.status] || "text-slate-400"}`}>
                        {entry.status}
                      </span>
                      <span className="text-slate-600 text-xs">
                        {entry.template_key?.replace(/_/g, " ")}
                      </span>
                      <span className="text-slate-600 text-xs">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                      {expandedLog === entry.id ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
                    </div>
                  </div>
                  {expandedLog === entry.id && (
                    <div className="mt-3 pl-7 space-y-2">
                      {entry.error_message && (
                        <div className="bg-red-400/10 border border-red-400/30 rounded-lg px-3 py-2 text-red-400 text-xs">
                          Error: {entry.error_message}
                        </div>
                      )}
                      {entry.sent_at && (
                        <p className="text-slate-500 text-xs">Sent at: {new Date(entry.sent_at).toLocaleString()}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Email Provider Configuration Notice */}
      {stats && !(stats as Record<string, unknown>).sendgrid_configured && (
        <div className="bg-amber-400/5 border border-amber-400/20 rounded-xl p-5">
          <div className="flex items-start gap-3">
            <Settings className="text-amber-400 flex-shrink-0 mt-0.5" size={18} />
            <div>
              <h4 className="text-amber-300 font-semibold text-sm">Email Provider Not Configured</h4>
              <p className="text-slate-400 text-xs mt-1">
                Emails are currently being logged but not delivered. To enable real email delivery, go to <strong className="text-amber-300">Settings &rarr; Email Provider</strong> and configure your email provider API key (SendGrid, Mailgun, or Resend).
              </p>
              <p className="text-slate-500 text-xs mt-2">
                Once configured, all template emails will be delivered automatically via your chosen provider.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
