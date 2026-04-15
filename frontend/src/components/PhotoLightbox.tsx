import { useEffect, useCallback } from "react";

interface PhotoLightboxProps {
  photo: {
    id?: string;
    image_url: string;
    date_taken: string | null;
    user_id?: string;
    user_display_name: string;
    categories?: string[];
  };
  artworkVotes?: Record<string, { voted: boolean; vote_count: number }>;
  artworkDownvotes?: Record<string, { voted: boolean }>;
  currentUserId?: string;
  isAuthenticated?: boolean;
  onVote?: (photoId: string) => void;
  onDownvote?: (photoId: string) => void;
  onPrev?: () => void;
  onNext?: () => void;
  hasPrev?: boolean;
  hasNext?: boolean;
  onClose: () => void;
}

function PhotoLightbox({
  photo,
  artworkVotes,
  artworkDownvotes,
  currentUserId,
  isAuthenticated,
  onVote,
  onDownvote,
  onPrev,
  onNext,
  hasPrev = false,
  hasNext = false,
  onClose,
}: PhotoLightboxProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && hasPrev && onPrev) onPrev();
      if (e.key === "ArrowRight" && hasNext && onNext) onNext();
    },
    [onClose, onPrev, onNext, hasPrev, hasNext]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  const dateStr = photo.date_taken
    ? new Date(photo.date_taken).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Date unknown";

  const categories = photo.categories?.length ? photo.categories : null;

  const photoId = photo.id;
  const photoVote = photoId && artworkVotes ? artworkVotes[photoId] : null;
  const isOwnPhoto = currentUserId && photo.user_id === currentUserId;
  const showVote = photoId && onVote && !isOwnPhoto;

  return (
    <div className="lightbox-overlay" onClick={handleOverlayClick}>
      <div className="lightbox-content">
        <button className="lightbox-close" onClick={onClose}>
          &times;
        </button>

        {hasPrev && onPrev && (
          <button className="lightbox-nav lightbox-nav-prev" onClick={onPrev}>
            &#x2039;
          </button>
        )}
        {hasNext && onNext && (
          <button className="lightbox-nav lightbox-nav-next" onClick={onNext}>
            &#x203A;
          </button>
        )}

        <img src={photo.image_url} alt="Artwork photo" />
        <div className="lightbox-info">
          <div>{dateStr}</div>
          <div>Photo by {photo.user_display_name}</div>
          {categories && (
            <div className="lightbox-categories">
              {categories.map((cat) => (
                <span key={cat} className="lightbox-category-tag">
                  {cat}
                </span>
              ))}
            </div>
          )}
          {showVote && (
            <div className="lightbox-vote">
              <button
                className={`vote-btn vote-btn-light ${photoVote?.voted ? "vote-btn--active" : ""}`}
                onClick={() => onVote(photoId)}
                disabled={!isAuthenticated}
                title={
                  !isAuthenticated
                    ? "Login to vote"
                    : photoVote?.voted
                      ? "Remove vote"
                      : "Upvote this photo"
                }
              >
                &#x25B2;
              </button>
              <span className="vote-count-light">
                {photoVote?.vote_count ?? 0}
              </span>
              {onDownvote && (
                <button
                  className={`vote-btn vote-btn-light vote-btn-down ${artworkDownvotes?.[photoId]?.voted ? "vote-btn--active" : ""}`}
                  onClick={() => onDownvote(photoId)}
                  disabled={!isAuthenticated}
                  title={
                    !isAuthenticated
                      ? "Login to vote"
                      : artworkDownvotes?.[photoId]?.voted
                        ? "Remove downvote"
                        : "Downvote this photo"
                  }
                >
                  &#x25BC;
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default PhotoLightbox;
