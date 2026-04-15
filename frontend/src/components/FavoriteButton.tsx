import { useState, useEffect, useCallback } from "react";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";

interface FavoriteButtonProps {
  artworkId: string;
  className?: string;
}

function FavoriteButton({ artworkId, className = "" }: FavoriteButtonProps) {
  const { isAuthenticated } = useAuth();
  const [favorited, setFavorited] = useState(false);
  const [toggling, setToggling] = useState(false);

  // Check initial favorite status
  useEffect(() => {
    if (!isAuthenticated) return;

    apiClient
      .get<{ favorited: boolean }>(`/api/favorites/${artworkId}/status`)
      .then((res) => {
        setFavorited(res.data.favorited);
      })
      .catch(() => {
        // Silently ignore - not critical
      });
  }, [artworkId, isAuthenticated]);

  const handleToggle = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (!isAuthenticated || toggling) return;

      const prev = favorited;
      setFavorited(!prev);
      setToggling(true);

      try {
        const res = await apiClient.post<{ favorited: boolean }>(
          `/api/favorites/${artworkId}`
        );
        setFavorited(res.data.favorited);
      } catch {
        setFavorited(prev);
      } finally {
        setToggling(false);
      }
    },
    [artworkId, isAuthenticated, favorited, toggling]
  );

  return (
    <button
      className={`favorite-btn ${favorited ? "favorite-btn--active" : ""} ${className}`}
      onClick={handleToggle}
      disabled={!isAuthenticated}
      title={
        !isAuthenticated
          ? "Login to favorite"
          : favorited
            ? "Remove from favorites"
            : "Add to favorites"
      }
      aria-label={favorited ? "Unfavorite" : "Favorite"}
    >
      {favorited ? (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="#e94560" stroke="none">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#999" strokeWidth="2">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
      )}
    </button>
  );
}

export default FavoriteButton;
