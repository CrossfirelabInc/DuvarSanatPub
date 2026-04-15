import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import apiClient from "../api/client";

interface SettingItem {
  key: string;
  value: string;
  updated_by: string | null;
  updated_at: string | null;
}

interface AuditEntry {
  id: string;
  moderator_name: string;
  action: string;
  target_type: string;
  target_id: string;
  reason: string | null;
  reverted: boolean;
  created_at: string;
}

type Section = "toggles" | "audit";

const TOGGLE_LABELS: Record<string, { label: string; description: string }> = {
  dm_enabled: { label: "Direct Messaging", description: "Allow users to send private messages" },
  tours_enabled: { label: "Walking Tours", description: "Show auto-generated walking tours" },
  ai_naming_enabled: { label: "Artwork Naming", description: "Suggest titles from image captioning on upload" },
  challenges_enabled: { label: "Challenges & Badges", description: "Community challenges and badge awards" },
  flags_enabled: { label: "Content Flags", description: "Allow users to report/flag content" },
  activity_feed_enabled: { label: "Activity Feed", description: "Public activity feed endpoint" },
  nsfw_detection_enabled: { label: "NSFW Detection", description: "Block inappropriate uploads via CLIP" },
  art_of_the_day_enabled: { label: "Art of the Day", description: "Daily featured artwork on homepage" },
};

function AdminSettingsPage() {
  const { user } = useAuth();
  const [section, setSection] = useState<Section>("toggles");

  // Settings state
  const [settings, setSettings] = useState<SettingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  // Audit log state
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ label: string; onConfirm: () => void } | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  const isAdmin = user?.role === "admin";

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<SettingItem[]>("/api/admin/settings");
      setSettings(res.data);
    } catch {
      showToast("Failed to load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin && section === "toggles") fetchSettings();
  }, [isAdmin, section, fetchSettings]);

  useEffect(() => {
    if (isAdmin && section === "audit") {
      setAuditLoading(true);
      apiClient.get<AuditEntry[]>("/api/mod/audit-log")
        .then((res) => setAuditLog(res.data))
        .catch(() => setAuditLog([]))
        .finally(() => setAuditLoading(false));
    }
  }, [isAdmin, section]);

  if (!isAdmin) {
    return (
      <div className="page" style={{ textAlign: "center", paddingTop: "4rem" }}>
        <h1>Access Denied</h1>
        <p style={{ color: "#555", margin: "1rem 0" }}>
          Admin access required.
        </p>
      </div>
    );
  }

  async function handleToggle(key: string, currentValue: string) {
    const newValue = currentValue.toLowerCase() === "true" ? "false" : "true";
    setSaving(true);
    try {
      await apiClient.put("/api/admin/settings", { [key]: newValue });
      setSettings((prev) =>
        prev.map((s) => s.key === key ? { ...s, value: newValue } : s)
      );
      showToast(`${TOGGLE_LABELS[key]?.label || key} ${newValue === "true" ? "enabled" : "disabled"}.`);
    } catch {
      showToast("Failed to update setting.");
    } finally {
      setSaving(false);
    }
  }

  const handleRevert = (logId: string) => {
    setConfirmAction({
      label: "Restore this content? It will become visible again.",
      onConfirm: async () => {
        setConfirmAction(null);
        try {
          await apiClient.post(`/api/mod/audit-log/${logId}/revert`);
          setAuditLog((prev) => prev.map((e) => e.id === logId ? { ...e, reverted: true } : e));
          showToast("Content restored successfully.");
        } catch {
          showToast("Failed to restore content.");
        }
      },
    });
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="page mod-dashboard">
      <h1>Admin Settings</h1>

      {toast && <div className="mod-toast">{toast}</div>}

      {confirmAction && (
        <div className="modal-overlay" onClick={() => setConfirmAction(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm Action</h3>
            <p>{confirmAction.label}</p>
            <div className="profile-edit-actions">
              <button className="btn btn-primary" onClick={confirmAction.onConfirm}>
                Confirm
              </button>
              <button className="btn btn-ghost" onClick={() => setConfirmAction(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mod-section-tabs" style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={`btn ${section === "toggles" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setSection("toggles")}
        >
          Feature Toggles
        </button>
        <button
          className={`btn ${section === "audit" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setSection("audit")}
        >
          Audit Log
        </button>
      </div>

      {/* ===== FEATURE TOGGLES ===== */}
      {section === "toggles" && (
        <>
          {loading ? (
            <div className="loading">Loading settings...</div>
          ) : (
            <div className="settings-grid">
              {settings.map((setting) => {
                const meta = TOGGLE_LABELS[setting.key];
                if (!meta) return null;
                const enabled = setting.value.toLowerCase() === "true";
                return (
                  <div key={setting.key} className="settings-toggle-card">
                    <div className="settings-toggle-info">
                      <div className="settings-toggle-label">{meta.label}</div>
                      <div className="settings-toggle-desc">{meta.description}</div>
                      {setting.updated_at && (
                        <div className="settings-toggle-meta">
                          Last changed: {formatDate(setting.updated_at)}
                        </div>
                      )}
                    </div>
                    <button
                      className={`settings-toggle-btn ${enabled ? "settings-toggle-on" : "settings-toggle-off"}`}
                      onClick={() => handleToggle(setting.key, setting.value)}
                      disabled={saving}
                    >
                      {enabled ? "ON" : "OFF"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ===== AUDIT LOG ===== */}
      {section === "audit" && (
        <>
          {auditLoading && <div className="loading">Loading audit log...</div>}
          {!auditLoading && auditLog.length === 0 && (
            <p style={{ color: "#777", textAlign: "center", margin: "2rem 0" }}>
              No moderation actions recorded yet.
            </p>
          )}
          {!auditLoading && auditLog.length > 0 && (
            <div className="mod-table-wrapper">
              <table className="mod-table">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Target</th>
                    <th>Moderator</th>
                    <th>Reason</th>
                    <th>Date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLog.map((entry) => (
                    <tr key={entry.id}>
                      <td><strong>{entry.action}</strong></td>
                      <td>{entry.target_type} ({entry.target_id.slice(0, 8)}...)</td>
                      <td>{entry.moderator_name}</td>
                      <td className="mod-text-cell">{entry.reason || "-"}</td>
                      <td>{formatDate(entry.created_at)}</td>
                      <td>
                        {entry.reverted ? (
                          <span style={{ color: "#27ae60", fontWeight: 600 }}>Reverted</span>
                        ) : (
                          <button
                            className="btn btn-sm btn-ghost"
                            onClick={() => handleRevert(entry.id)}
                          >
                            Undo
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default AdminSettingsPage;
