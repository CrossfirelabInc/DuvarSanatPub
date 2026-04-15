import { useState, useEffect, useRef, useCallback } from "react";
import { AxiosError } from "axios";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";

interface ConversationItem {
  id: string;
  other_user: {
    id: string;
    display_name: string;
    avatar_url: string | null;
  } | null;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
}

interface MessageItem {
  id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  read_at: string | null;
  created_at: string;
  is_mine: boolean;
}

function getInitial(name: string): { initial: string; color: string } {
  const initial = name.charAt(0).toUpperCase();
  const colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return { initial, color: colors[Math.abs(hash) % colors.length] };
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function MessagesPage() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeConv = conversations.find((c) => c.id === activeConvId);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await apiClient.get<ConversationItem[]>("/api/messages/conversations");
      setConversations(res.data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  useEffect(() => {
    if (!activeConvId) return;
    setMessagesLoading(true);
    apiClient
      .get<MessageItem[]>(`/api/messages/conversations/${activeConvId}/messages`)
      .then((res) => {
        setMessages(res.data);
        // Clear unread count for this conversation (backend marks as read on fetch)
        setConversations((prev) =>
          prev.map((c) => c.id === activeConvId ? { ...c, unread_count: 0 } : c)
        );
      })
      .catch(() => setMessages([]))
      .finally(() => setMessagesLoading(false));
  }, [activeConvId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!newMessage.trim() || !activeConvId) return;
    setSending(true);
    setError("");
    try {
      const res = await apiClient.post(`/api/messages/conversations/${activeConvId}/messages`, {
        content: newMessage.trim(),
      });
      setMessages((prev) => [...prev, res.data]);
      setNewMessage("");
      // Update last message in conversation list
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConvId
            ? { ...c, last_message: res.data.content, last_message_at: res.data.created_at }
            : c
        )
      );
    } catch (err) {
      if (err instanceof AxiosError && err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to send message.");
      }
    } finally {
      setSending(false);
    }
  }

  if (!user) return null;

  return (
    <div className="page messages-page">
      <h1>Messages</h1>

      <div className={`messages-layout${activeConvId ? " thread-active" : ""}`}>
        {/* Conversation list */}
        <div className="messages-sidebar">
          {loading && <div className="loading">Loading...</div>}
          {!loading && conversations.length === 0 && (
            <p style={{ color: "#777", padding: "1rem", textAlign: "center" }}>
              No conversations yet. Visit a user's profile to start a conversation.
            </p>
          )}
          {conversations.map((conv) => {
            const other = conv.other_user;
            const avatar = other ? getInitial(other.display_name) : { initial: "?", color: "#999" };
            return (
              <button
                key={conv.id}
                className={`messages-conv-item ${conv.id === activeConvId ? "active" : ""}`}
                onClick={() => setActiveConvId(conv.id)}
              >
                <div className="messages-conv-avatar" style={{ background: other?.avatar_url ? "transparent" : avatar.color }}>
                  {other?.avatar_url ? (
                    <img src={other.avatar_url} alt="" className="profile-avatar-img" />
                  ) : (
                    avatar.initial
                  )}
                </div>
                <div className="messages-conv-info">
                  <span className="messages-conv-name">{other?.display_name || "Unknown"}</span>
                  <span className="messages-conv-preview">
                    {conv.last_message ? conv.last_message.slice(0, 40) : "No messages yet"}
                  </span>
                </div>
                {conv.last_message_at && (
                  <span className="messages-conv-time">{timeAgo(conv.last_message_at)}</span>
                )}
                {conv.unread_count > 0 && (
                  <span className="messages-unread-badge">{conv.unread_count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Message thread */}
        <div className="messages-thread">
          {!activeConvId && (
            <div className="messages-empty">
              <p>Select a conversation to view messages</p>
            </div>
          )}

          {activeConvId && (
            <>
              <div className="messages-thread-header">
                <button className="messages-back-btn" onClick={() => setActiveConvId(null)} aria-label="Back to conversations">
                  &larr;
                </button>
                <strong>{activeConv?.other_user?.display_name || "Conversation"}</strong>
              </div>

              <div className="messages-list">
                {messagesLoading && <div className="loading">Loading messages...</div>}
                {!messagesLoading && messages.length === 0 && (
                  <p style={{ color: "#777", textAlign: "center", padding: "2rem" }}>
                    No messages yet. Say hello!
                  </p>
                )}
                {messages.map((msg) => (
                  <div key={msg.id} className={`message-bubble ${msg.is_mine ? "mine" : "theirs"}`}>
                    <p className="message-content">{msg.content}</p>
                    <span className="message-time">{timeAgo(msg.created_at)}</span>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              <div className="messages-input-bar">
                {error && <div className="auth-error" style={{ marginBottom: 4 }}>{error}</div>}
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !sending && handleSend()}
                  placeholder="Type a message..."
                  disabled={sending}
                  maxLength={5000}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleSend}
                  disabled={sending || !newMessage.trim()}
                >
                  Send
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default MessagesPage;
