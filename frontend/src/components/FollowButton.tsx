import { useState, useCallback } from "react";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";

interface FollowButtonProps {
  targetType: "artist" | "user";
  targetId: string;
  initialFollowing?: boolean;
  initialCount?: number;
  compact?: boolean;
}

function FollowButton({
  targetType,
  targetId,
  initialFollowing = false,
  initialCount = 0,
  compact = false,
}: FollowButtonProps) {
  const { isAuthenticated } = useAuth();
  const [following, setFollowing] = useState(initialFollowing);
  const [count, setCount] = useState(initialCount);
  const [toggling, setToggling] = useState(false);

  const handleToggle = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (!isAuthenticated || toggling) return;

      // Optimistic update
      const prevFollowing = following;
      const prevCount = count;
      setFollowing(!prevFollowing);
      setCount(prevFollowing ? Math.max(0, count - 1) : count + 1);
      setToggling(true);

      try {
        const endpoint =
          targetType === "artist"
            ? `/api/artists/${targetId}/follow`
            : `/api/users/${targetId}/follow`;
        const res = await apiClient.post<{
          following: boolean;
          follower_count: number;
        }>(endpoint);
        setFollowing(res.data.following);
        setCount(res.data.follower_count);
      } catch {
        // Revert on error
        setFollowing(prevFollowing);
        setCount(prevCount);
      } finally {
        setToggling(false);
      }
    },
    [targetType, targetId, isAuthenticated, following, count, toggling]
  );

  const label = following ? "Following" : "Follow";
  const displayCount = count > 0 ? ` \u00b7 ${count}` : "";

  return (
    <button
      className={`follow-btn${following ? " follow-btn--following" : ""}${compact ? " follow-btn--compact" : ""}`}
      onClick={handleToggle}
      disabled={!isAuthenticated}
      title={!isAuthenticated ? "Login to follow" : following ? "Unfollow" : "Follow"}
      aria-label={following ? "Unfollow" : "Follow"}
    >
      {label}
      {!compact && <span className="follow-count">{displayCount}</span>}
    </button>
  );
}

export default FollowButton;
