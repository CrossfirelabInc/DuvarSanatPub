import { useState } from "react";
import { AxiosError } from "axios";
import apiClient from "../api/client";

interface FlagButtonProps {
  targetType: "photo" | "comment" | "artwork" | "user";
  targetId: string;
}

const REASONS = [
  { value: "inappropriate", label: "Inappropriate content" },
  { value: "spam", label: "Spam" },
  { value: "harassment", label: "Harassment" },
  { value: "other", label: "Other" },
];

function FlagButton({ targetType, targetId }: FlagButtonProps) {
  const [showModal, setShowModal] = useState(false);
  const [reason, setReason] = useState("inappropriate");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post("/api/flags", {
        target_type: targetType,
        target_id: targetId,
        reason,
        description: description.trim() || null,
      });
      setDone(true);
      setTimeout(() => setShowModal(false), 1500);
    } catch (err) {
      if (err instanceof AxiosError && err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to submit report.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return <span className="flag-done">Reported</span>;
  }

  return (
    <>
      <button
        className="btn btn-ghost flag-btn"
        onClick={() => setShowModal(true)}
        title="Report this content"
      >
        Report
      </button>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Report Content</h3>

            <div className="form-field">
              <label>Reason</label>
              <select value={reason} onChange={(e) => setReason(e.target.value)}>
                {REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label>Details (optional)</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={1000}
                placeholder="Provide additional details..."
              />
            </div>

            {error && <div className="auth-error">{error}</div>}

            <div className="profile-edit-actions">
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? "Submitting..." : "Submit Report"}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => setShowModal(false)}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default FlagButton;
