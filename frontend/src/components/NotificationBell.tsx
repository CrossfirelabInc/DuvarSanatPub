import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

const TYPE_ICONS: Record<string, string> = {
  badge_earned: "\uD83C\uDFC6",
  challenge_complete: "\u2705",
  claim_approved: "\u2713",
  claim_rejected: "\u2717",
  new_photo: "\uD83D\uDCF7",
  new_message: "\u2709",
  new_flag: "\u26A0",
  new_claim: "\uD83D\uDCCB",
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);

  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function NotificationBell() {
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch unread count
  const fetchUnreadCount = useCallback(() => {
    apiClient
      .get<{ count: number }>("/api/notifications/unread-count")
      .then((res) => setUnreadCount(res.data.count))
      .catch(() => {
        // API may not exist yet -- silently ignore
      });
  }, []);

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  function handleToggle() {
    if (!open) {
      // Fetch notifications when opening
      setLoading(true);
      apiClient
        .get<Notification[]>("/api/notifications", { params: { limit: 10 } })
        .then((res) => {
          setNotifications(Array.isArray(res.data) ? res.data : []);
        })
        .catch(() => {
          setNotifications([]);
        })
        .finally(() => setLoading(false));
    }
    setOpen(!open);
  }

  function handleNotificationClick(notif: Notification) {
    // Mark as read
    apiClient.post(`/api/notifications/${notif.id}/read`).catch(() => {});
    setNotifications((prev) =>
      prev.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n))
    );
    setUnreadCount((prev) => Math.max(0, prev - (notif.is_read ? 0 : 1)));
    setOpen(false);

    if (notif.link) {
      navigate(notif.link);
    }
  }

  function handleMarkAllRead() {
    apiClient.post("/api/notifications/read-all").catch(() => {});
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  }

  return (
    <div className="notif-bell-wrapper" ref={dropdownRef}>
      <button
        className="notif-bell"
        onClick={handleToggle}
        aria-label="Notifications"
      >
        {"\uD83D\uDD14"}
        {unreadCount > 0 && (
          <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-header">
            <span className="notif-dropdown-title">Notifications</span>
          </div>

          {loading && (
            <div className="notif-loading">Loading...</div>
          )}

          {!loading && notifications.length === 0 && (
            <div className="notif-empty">No notifications yet.</div>
          )}

          {!loading && notifications.length > 0 && (
            <div className="notif-list">
              {notifications.map((notif) => (
                <button
                  key={notif.id}
                  className={`notif-item${notif.is_read ? "" : " notif-unread"}`}
                  onClick={() => handleNotificationClick(notif)}
                >
                  <span className="notif-item-icon">
                    {TYPE_ICONS[notif.type] || "\uD83D\uDD14"}
                  </span>
                  <div className="notif-item-content">
                    <span className="notif-item-title">{notif.title}</span>
                    {notif.message && (
                      <span className="notif-item-message">{notif.message}</span>
                    )}
                    <span className="notif-item-time">{timeAgo(notif.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {!loading && notifications.length > 0 && (
            <button className="notif-mark-all" onClick={handleMarkAllRead}>
              Mark all as read
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
