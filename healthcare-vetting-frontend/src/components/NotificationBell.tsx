import { useState, useEffect, useRef, useCallback } from "react";
import { Bell, Check, CheckCheck, Trash2, X } from "lucide-react";
import { notificationsApi } from "../api/client";

interface Notification {
  id: string;
  title: string;
  message: string;
  category: string;
  severity: string;
  is_read: number;
  created_at: string;
  link?: string;
}

interface NotificationBellProps {
  token: string;
  onNavigate?: (link: string) => void;
}

export default function NotificationBell({ token, onNavigate }: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await notificationsApi.getUnreadCount(token);
      setUnreadCount((data as { unread_count: number }).unread_count || 0);
    } catch {
      // silently fail
    }
  }, [token]);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.getNotifications(token, { limit: 20 });
      const resp = data as { notifications: Notification[]; unread_count: number };
      setNotifications(resp.notifications || []);
      setUnreadCount(resp.unread_count || 0);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch full notifications when dropdown opens
  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const markRead = async (id: string) => {
    try {
      await notificationsApi.markRead(token, id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: 1 } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { /* ignore */ }
  };

  const markAllRead = async () => {
    try {
      await notificationsApi.markAllRead(token);
      setNotifications(prev => prev.map(n => ({ ...n, is_read: 1 })));
      setUnreadCount(0);
    } catch { /* ignore */ }
  };

  const deleteNotif = async (id: string) => {
    try {
      await notificationsApi.deleteNotification(token, id);
      const removed = notifications.find(n => n.id === id);
      setNotifications(prev => prev.filter(n => n.id !== id));
      if (removed && !removed.is_read) setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { /* ignore */ }
  };

  const severityColor: Record<string, string> = {
    success: "#22c55e",
    warning: "#f59e0b",
    error: "#ef4444",
    info: "#3b82f6",
  };

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div ref={dropdownRef} style={{ position: "relative", display: "inline-block" }}>
      {/* Bell button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          position: "relative",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "8px",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background 0.2s",
        }}
        onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.1)")}
        onMouseLeave={e => (e.currentTarget.style.background = "none")}
        title="Notifications"
      >
        <Bell size={20} color="currentColor" />
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: 2,
              right: 2,
              background: "#ef4444",
              color: "#fff",
              fontSize: "10px",
              fontWeight: 700,
              borderRadius: "50%",
              minWidth: "18px",
              height: "18px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 4px",
              lineHeight: 1,
            }}
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "360px",
            maxHeight: "480px",
            background: "#fff",
            borderRadius: "12px",
            boxShadow: "0 8px 30px rgba(0,0,0,0.15)",
            zIndex: 9999,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "14px 16px",
              borderBottom: "1px solid #e5e7eb",
              background: "#f9fafb",
            }}
          >
            <span style={{ fontWeight: 600, fontSize: "14px", color: "#1e3a5f" }}>
              Notifications {unreadCount > 0 && `(${unreadCount})`}
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "12px",
                    color: "#3b82f6",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                  title="Mark all as read"
                >
                  <CheckCheck size={14} /> All read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: "2px" }}
              >
                <X size={16} color="#6b7280" />
              </button>
            </div>
          </div>

          {/* Notification list */}
          <div style={{ overflowY: "auto", flex: 1, maxHeight: "400px" }}>
            {loading && notifications.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", color: "#9ca3af", fontSize: "13px" }}>
                Loading...
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", color: "#9ca3af", fontSize: "13px" }}>
                No notifications yet
              </div>
            ) : (
              notifications.map(n => (
                <div
                  key={n.id}
                  style={{
                    padding: "12px 16px",
                    borderBottom: "1px solid #f3f4f6",
                    background: n.is_read ? "#fff" : "#eff6ff",
                    cursor: "pointer",
                    transition: "background 0.15s",
                    display: "flex",
                    gap: "10px",
                    alignItems: "flex-start",
                  }}
                  onClick={() => {
                    if (!n.is_read) markRead(n.id);
                    if (n.link && onNavigate) onNavigate(n.link);
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = n.is_read ? "#f9fafb" : "#dbeafe")}
                  onMouseLeave={e => (e.currentTarget.style.background = n.is_read ? "#fff" : "#eff6ff")}
                >
                  {/* Severity dot */}
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: severityColor[n.severity] || "#9ca3af",
                      marginTop: 6,
                      flexShrink: 0,
                    }}
                  />
                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <span
                        style={{
                          fontWeight: n.is_read ? 400 : 600,
                          fontSize: "13px",
                          color: "#1f2937",
                          lineHeight: 1.3,
                        }}
                      >
                        {n.title}
                      </span>
                      <span style={{ fontSize: "11px", color: "#9ca3af", whiteSpace: "nowrap", marginLeft: 8 }}>
                        {timeAgo(n.created_at)}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: "12px",
                        color: "#6b7280",
                        marginTop: 2,
                        lineHeight: 1.4,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}
                    >
                      {n.message}
                    </div>
                  </div>
                  {/* Actions */}
                  <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
                    {!n.is_read && (
                      <button
                        onClick={e => { e.stopPropagation(); markRead(n.id); }}
                        style={{ background: "none", border: "none", cursor: "pointer", padding: "2px" }}
                        title="Mark as read"
                      >
                        <Check size={14} color="#3b82f6" />
                      </button>
                    )}
                    <button
                      onClick={e => { e.stopPropagation(); deleteNotif(n.id); }}
                      style={{ background: "none", border: "none", cursor: "pointer", padding: "2px" }}
                      title="Delete"
                    >
                      <Trash2 size={14} color="#9ca3af" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
