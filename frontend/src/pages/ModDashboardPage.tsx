import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import apiClient from "../api/client";


interface Claim {
  id: string;
  user_id: string;
  artist_id: string;
  verification_text: string;
  verification_url: string | null;
  status: string;
  reviewed_by: string | null;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  artist_name: string | null;
  claimant_display_name: string | null;
}

interface Flag {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  reason: string;
  description: string | null;
  status: string;
  reviewed_by: string | null;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  reporter_display_name: string | null;
}

type ClaimTab = "pending" | "approved" | "rejected";
type FlagTab = "pending" | "actioned" | "dismissed";
type Section = "claims" | "flags";


function ModDashboardPage() {
  const { user } = useAuth();
  const [section, setSection] = useState<Section>("claims");

  // Claims state
  const [claimTab, setClaimTab] = useState<ClaimTab>("pending");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [claimsError, setClaimsError] = useState("");
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectNote, setRejectNote] = useState("");

  // Flags state
  const [flagTab, setFlagTab] = useState<FlagTab>("pending");
  const [flags, setFlags] = useState<Flag[]>([]);
  const [flagsLoading, setFlagsLoading] = useState(false);
  const [flagsError, setFlagsError] = useState("");

  // Toast / confirmation state
  const [toast, setToast] = useState("");
  const [confirmAction, setConfirmAction] = useState<{ label: string; onConfirm: () => void } | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  // Merge state
  const [merging, setMerging] = useState(false);
  const [mergeResult, setMergeResult] = useState("");

  const isMod = user?.role === "moderator" || user?.role === "admin";

  const fetchClaims = useCallback(async (status: ClaimTab) => {
    setClaimsLoading(true);
    setClaimsError("");
    try {
      const res = await apiClient.get<Claim[]>("/api/mod/claims", {
        params: { status_filter: status },
      });
      setClaims(res.data);
    } catch {
      setClaimsError("Failed to load claims.");
    } finally {
      setClaimsLoading(false);
    }
  }, []);

  const fetchFlags = useCallback(async (status: FlagTab) => {
    setFlagsLoading(true);
    setFlagsError("");
    try {
      const res = await apiClient.get<Flag[]>("/api/mod/flags", {
        params: { flag_status: status },
      });
      setFlags(res.data);
    } catch {
      setFlagsError("Failed to load flags.");
    } finally {
      setFlagsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isMod && section === "claims") fetchClaims(claimTab);
  }, [claimTab, isMod, section, fetchClaims]);

  useEffect(() => {
    if (isMod && section === "flags") fetchFlags(flagTab);
  }, [flagTab, isMod, section, fetchFlags]);

  if (!isMod) {
    return (
      <div className="page" style={{ textAlign: "center", paddingTop: "4rem" }}>
        <h1>Access Denied</h1>
        <p style={{ color: "#555", margin: "1rem 0" }}>
          You do not have permission to view this page.
        </p>
      </div>
    );
  }

  const handleApprove = async (claimId: string) => {
    try {
      await apiClient.post(`/api/mod/claims/${claimId}/approve`);
      setClaims((prev) => prev.filter((c) => c.id !== claimId));
    } catch {
      alert("Failed to approve claim.");
    }
  };

  const handleReject = async (claimId: string) => {
    try {
      await apiClient.post(`/api/mod/claims/${claimId}/reject`, {
        note: rejectNote || undefined,
      });
      setClaims((prev) => prev.filter((c) => c.id !== claimId));
      setRejectingId(null);
      setRejectNote("");
    } catch {
      alert("Failed to reject claim.");
    }
  };

  const doReviewFlag = async (flagId: string, action: "delete" | "dismissed") => {
    try {
      await apiClient.post(`/api/mod/flags/${flagId}/review`, { action });
      setFlags((prev) => prev.filter((f) => f.id !== flagId));
      showToast(action === "delete" ? "Content deleted successfully." : "Flag dismissed.");
    } catch {
      showToast("Failed to process flag.");
    }
  };

  const handleReviewFlag = (flagId: string, action: "delete" | "dismissed") => {
    const label = action === "delete" ? "Delete this content? It will be hidden from the site." : "Dismiss this flag? No action will be taken.";
    setConfirmAction({
      label,
      onConfirm: () => {
        setConfirmAction(null);
        doReviewFlag(flagId, action);
      },
    });
  };

  const handleBanUser = (userId: string) => {
    setConfirmAction({
      label: "Ban this user? They will no longer be able to use the platform.",
      onConfirm: async () => {
        setConfirmAction(null);
        try {
          await apiClient.post("/api/mod/ban", { user_id: userId });
          showToast("User banned successfully.");
        } catch {
          showToast("Failed to ban user.");
        }
      },
    });
  };

  async function handleMergeDuplicates() {
    setMerging(true);
    setMergeResult("");
    try {
      const res = await apiClient.post<{ merges: number; message: string }>(
        "/api/mod/merge-duplicates"
      );
      setMergeResult(res.data.message);
    } catch {
      setMergeResult("Failed to run merge. Check server logs.");
    } finally {
      setMerging(false);
    }
  }

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="page mod-dashboard">
      <h1>Moderator Dashboard</h1>

      {/* Toast notification */}
      {toast && <div className="mod-toast">{toast}</div>}

      {/* Confirmation modal */}
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

      {/* Tools section */}
      <div className="mod-tools">
        <button
          className="btn btn-accent btn-sm"
          onClick={handleMergeDuplicates}
          disabled={merging}
        >
          {merging ? "Scanning..." : "Merge Duplicate Artworks"}
        </button>
        {mergeResult && <span className="mod-merge-result">{mergeResult}</span>}
      </div>

      {/* Section selector */}
      <div className="mod-section-tabs" style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          className={`btn ${section === "claims" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setSection("claims")}
        >
          Artist Claims
        </button>
        <button
          className={`btn ${section === "flags" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setSection("flags")}
        >
          Content Flags
        </button>
        {user?.role === "admin" && (
          <a href="/admin/settings" className="btn btn-ghost">
            Admin Settings
          </a>
        )}
      </div>

      {/* ===== CLAIMS SECTION ===== */}
      {section === "claims" && (
        <>
          <div className="mod-tabs">
            {(["pending", "approved", "rejected"] as ClaimTab[]).map((s) => (
              <button
                key={s}
                className={`mod-tab ${claimTab === s ? "mod-tab-active" : ""}`}
                onClick={() => setClaimTab(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {claimsLoading && <div className="loading">Loading claims...</div>}
          {claimsError && <p className="form-error">{claimsError}</p>}

          {!claimsLoading && !claimsError && claims.length === 0 && (
            <p style={{ color: "#777", textAlign: "center", margin: "2rem 0" }}>
              No {claimTab} claims found.
            </p>
          )}

          {!claimsLoading && !claimsError && claims.length > 0 && (
            <div className="mod-table-wrapper">
              <table className="mod-table">
                <thead>
                  <tr>
                    <th>Artist</th>
                    <th>Claimant</th>
                    <th>Verification</th>
                    <th>URL</th>
                    <th>Date</th>
                    {claimTab === "pending" && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {claims.map((claim) => (
                    <tr key={claim.id}>
                      <td>{claim.artist_name || "Unknown"}</td>
                      <td>{claim.claimant_display_name || "Unknown"}</td>
                      <td className="mod-text-cell">{claim.verification_text}</td>
                      <td>
                        {claim.verification_url ? (
                          <a href={claim.verification_url} target="_blank" rel="noopener noreferrer">Link</a>
                        ) : "-"}
                      </td>
                      <td>{formatDate(claim.created_at)}</td>
                      {claimTab === "pending" && (
                        <td className="mod-actions">
                          <button className="btn btn-sm btn-approve" onClick={() => handleApprove(claim.id)}>
                            Approve
                          </button>
                          {rejectingId === claim.id ? (
                            <div className="mod-reject-form">
                              <input
                                type="text"
                                placeholder="Reason (optional)"
                                value={rejectNote}
                                onChange={(e) => setRejectNote(e.target.value)}
                                className="mod-reject-input"
                              />
                              <button className="btn btn-sm btn-reject" onClick={() => handleReject(claim.id)}>
                                Confirm
                              </button>
                              <button className="btn btn-sm" onClick={() => { setRejectingId(null); setRejectNote(""); }}>
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button className="btn btn-sm btn-reject" onClick={() => setRejectingId(claim.id)}>
                              Reject
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ===== FLAGS SECTION ===== */}
      {section === "flags" && (
        <>
          <div className="mod-tabs">
            {(["pending", "actioned", "dismissed"] as FlagTab[]).map((s) => (
              <button
                key={s}
                className={`mod-tab ${flagTab === s ? "mod-tab-active" : ""}`}
                onClick={() => setFlagTab(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {flagsLoading && <div className="loading">Loading flags...</div>}
          {flagsError && <p className="form-error">{flagsError}</p>}

          {!flagsLoading && !flagsError && flags.length === 0 && (
            <p style={{ color: "#777", textAlign: "center", margin: "2rem 0" }}>
              No {flagTab} flags found.
            </p>
          )}

          {!flagsLoading && !flagsError && flags.length > 0 && (
            <div className="mod-table-wrapper">
              <table className="mod-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Reason</th>
                    <th>Reporter</th>
                    <th>Description</th>
                    <th>Date</th>
                    {flagTab === "pending" && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {flags.map((flag) => (
                    <tr key={flag.id}>
                      <td>
                        {flag.target_type === "artwork" ? (
                          <Link to={`/artworks/${flag.target_id}`}>{flag.target_type}</Link>
                        ) : flag.target_type === "user" ? (
                          <Link to={`/users/${flag.target_id}`}>{flag.target_type}</Link>
                        ) : (
                          flag.target_type
                        )}
                      </td>
                      <td>{flag.reason}</td>
                      <td>{flag.reporter_display_name || "Unknown"}</td>
                      <td className="mod-text-cell">{flag.description || "-"}</td>
                      <td>{formatDate(flag.created_at)}</td>
                      {flagTab === "pending" && (
                        <td className="mod-actions">
                          <button
                            className="btn btn-sm btn-reject"
                            onClick={() => handleReviewFlag(flag.id, "delete")}
                          >
                            Delete Content
                          </button>
                          <button
                            className="btn btn-sm btn-ghost"
                            onClick={() => handleReviewFlag(flag.id, "dismissed")}
                          >
                            Dismiss
                          </button>
                          {flag.target_type === "user" && (
                            <button
                              className="btn btn-sm btn-reject"
                              onClick={() => handleBanUser(flag.target_id)}
                            >
                              Ban User
                            </button>
                          )}
                        </td>
                      )}
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

export default ModDashboardPage;
