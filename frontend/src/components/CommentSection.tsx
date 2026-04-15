import { useState, useEffect } from "react";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";

interface Comment {
  id: string;
  user_id: string;
  user_display_name: string;
  content: string;
  created_at: string;
}

interface CommentSectionProps {
  targetType: "artwork" | "artist";
  targetId: string;
}

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function CommentSection({ targetType, targetId }: CommentSectionProps) {
  const { user, isAuthenticated } = useAuth();

  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [content, setContent] = useState("");
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");

    apiClient
      .get<Comment[]>("/api/comments", {
        params: { target_type: targetType, target_id: targetId },
      })
      .then((res) => {
        setComments(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        setError("Could not load comments.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [targetType, targetId]);

  async function handlePost() {
    const trimmed = content.trim();
    if (!trimmed || !user) return;

    setPosting(true);
    setPostError("");

    // Optimistic add
    const optimisticComment: Comment = {
      id: `temp-${Date.now()}`,
      user_id: user.id,
      user_display_name: user.display_name,
      content: trimmed,
      created_at: new Date().toISOString(),
    };
    setComments((prev) => [...prev, optimisticComment]);
    setContent("");

    try {
      const res = await apiClient.post<Comment>("/api/comments", {
        target_type: targetType,
        target_id: targetId,
        content: trimmed,
      });
      // Replace optimistic comment with server response
      setComments((prev) =>
        prev.map((c) => (c.id === optimisticComment.id ? res.data : c))
      );
    } catch {
      // Revert optimistic add
      setComments((prev) =>
        prev.filter((c) => c.id !== optimisticComment.id)
      );
      setContent(trimmed);
      setPostError("Failed to post comment. Please try again.");
    } finally {
      setPosting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handlePost();
    }
  }

  return (
    <div className="comment-section">
      <h3 className="comment-section-title">Comments</h3>

      {loading ? (
        <p className="comment-loading">Loading comments...</p>
      ) : error ? (
        <p className="comment-error">{error}</p>
      ) : comments.length === 0 ? (
        <p className="comment-empty">
          No comments yet. Be the first to share your thoughts.
        </p>
      ) : (
        <div className="comment-list">
          {comments.map((c) => (
            <div key={c.id} className="comment-item">
              <div className="comment-avatar">
                {getInitials(c.user_display_name)}
              </div>
              <div className="comment-body">
                <div className="comment-meta">
                  <span className="comment-author">
                    {c.user_display_name}
                  </span>
                  <span className="comment-date">
                    {formatDate(c.created_at)}
                  </span>
                </div>
                <p className="comment-content">{c.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {isAuthenticated && (
        <div className="comment-form">
          <textarea
            className="comment-input"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write a comment..."
            rows={2}
            disabled={posting}
          />
          <button
            className="btn btn-accent comment-post-btn"
            onClick={handlePost}
            disabled={posting || !content.trim()}
          >
            {posting ? "Posting..." : "Post"}
          </button>
          {postError && <p className="comment-post-error">{postError}</p>}
        </div>
      )}
    </div>
  );
}

export default CommentSection;
