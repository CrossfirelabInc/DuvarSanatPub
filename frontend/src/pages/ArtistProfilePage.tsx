import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";
import CommentSection from "../components/CommentSection";
import FavoriteButton from "../components/FavoriteButton";
import FollowButton from "../components/FollowButton";
import VerifiedBadge from "../components/VerifiedBadge";


interface ArtistArtwork {
  id: string;
  title: string | null;
  status: "active" | "modified" | "gone";
  thumbnail_url: string | null;
  photo_count?: number;
}

interface ArtistDetail {
  id: string;
  name: string;
  bio: string | null;
  aliases?: string[] | null;
  website?: string | null;
  social_links?: { instagram?: string; twitter?: string } | null;
  artwork_count: number;
  total_photos?: number;
  active_since?: string | null;
  follower_count?: number;
  is_following?: boolean;
  claimed_by_user_id?: string | null;
  verified_at?: string | null;
  artworks: ArtistArtwork[];
}

interface StyleSimilarArtist {
  artist_id: string;
  name: string;
  artwork_count: number;
  similarity: number;
}



function formatActiveSince(iso: string | null | undefined): string {
  if (!iso) return "Unknown";
  try {
    const date = new Date(iso);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
    });
  } catch {
    return "Unknown";
  }
}

function extractHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function hasAnyLink(artist: ArtistDetail): boolean {
  if (artist.website) return true;
  if (artist.social_links?.instagram) return true;
  if (artist.social_links?.twitter) return true;
  return false;
}


function ArtistProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { isAuthenticated } = useAuth();

  const [artist, setArtist] = useState<ArtistDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [styleSimilarArtists, setStyleSimilarArtists] = useState<StyleSimilarArtist[]>([]);

  // Claim modal state
  const [showClaimModal, setShowClaimModal] = useState(false);
  const [claimText, setClaimText] = useState("");
  const [claimUrl, setClaimUrl] = useState("");
  const [claimSubmitting, setClaimSubmitting] = useState(false);
  const [claimSuccess, setClaimSuccess] = useState(false);
  const [claimError, setClaimError] = useState("");

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setError("");

    apiClient
      .get<ArtistDetail>(`/api/artists/${id}`)
      .then((res) => {
        setArtist(res.data);
      })
      .catch(() => {
        setError(
          "Failed to load artist. They may not exist or the server is unavailable."
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id]);

  // Fetch style-similar artists
  useEffect(() => {
    if (!id) return;

    apiClient
      .get<StyleSimilarArtist[]>(`/api/artists/${id}/style-similar`)
      .then((res) => {
        if (Array.isArray(res.data)) {
          setStyleSimilarArtists(res.data.slice(0, 5));
        }
      })
      .catch(() => {
        // Gracefully ignore
      });
  }, [id]);

  const handleClaimSubmit = async () => {
    if (!id || claimText.length < 10) return;
    setClaimSubmitting(true);
    setClaimError("");
    try {
      await apiClient.post(`/api/artists/${id}/claim`, {
        verification_text: claimText,
        verification_url: claimUrl || undefined,
      });
      setClaimSuccess(true);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setClaimError(
        axiosErr.response?.data?.detail || "Failed to submit claim."
      );
    } finally {
      setClaimSubmitting(false);
    }
  };


  if (loading) {
    return <div className="loading">Loading artist...</div>;
  }

  if (error || !artist) {
    return (
      <div className="page">
        <div className="profile-error">
          <h1>Artist Not Found</h1>
          <p>{error || "This artist could not be loaded."}</p>
          <Link to="/" className="btn btn-primary">
            Back to Map
          </Link>
        </div>
      </div>
    );
  }

  const aliases = artist.aliases?.filter(Boolean);

  return (
    <div className="page profile-page artist-page">
      <Helmet>
        <title>{`${artist.name} — DuvarSanat`}</title>
        <meta name="description" content={`${artist.name} — street artist with ${artist.artwork_count} documented artworks on DuvarSanat.`} />
        <meta property="og:title" content={`${artist.name} — DuvarSanat`} />
      </Helmet>
      {/* Hero section */}
      <div className="artist-hero">
        <span className="page-type-badge artist">Artist</span>
        <div className="artist-hero-name-row">
          <h1>
            {artist.name}
            {artist.verified_at && <VerifiedBadge />}
          </h1>
          <FollowButton
            targetType="artist"
            targetId={artist.id}
            initialFollowing={artist.is_following}
            initialCount={artist.follower_count ?? 0}
          />
        </div>

        {artist.verified_at && artist.claimed_by_user_id && (
          <p className="artist-verified-info">
            Verified artist &middot; Profile managed by{" "}
            <Link to={`/users/${artist.claimed_by_user_id}`} className="artwork-link">
              view profile
            </Link>
          </p>
        )}

        {aliases && aliases.length > 0 && (
          <p className="artist-aliases">
            Also known as: {aliases.join(", ")}
          </p>
        )}
      </div>

      {/* Stats bar */}
      <div className="artist-stats">
        <div className="artist-stat-box">
          <span className="artist-stat-value">{artist.artwork_count}</span>
          <span className="artist-stat-label">{artist.artwork_count === 1 ? "Artwork" : "Artworks"}</span>
        </div>
        <div className="artist-stat-box">
          <span className="artist-stat-value">{artist.total_photos ?? 0}</span>
          <span className="artist-stat-label">Photos</span>
        </div>
        <div className="artist-stat-box">
          <span className="artist-stat-value">{formatActiveSince(artist.active_since)}</span>
          <span className="artist-stat-label">Active since</span>
        </div>
      </div>

      {/* Biography section — always shown */}
      <div className="artist-bio-section">
        <h2 className="artist-section-title">Biography</h2>
        {artist.bio ? (
          <div className="artist-bio-text">
            {artist.bio.split("\n").map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
          </div>
        ) : (
          <p className="artist-bio-empty">
            No biography available yet. Know this artist? Help the community by contributing information.
          </p>
        )}
      </div>

      {/* Contact & Links — always shown */}
      <div className="artist-contact-section">
        <h2 className="artist-section-title">Contact & Links</h2>
        {hasAnyLink(artist) ? (
          <div className="artist-links">
            {artist.website && (
              <a href={artist.website} target="_blank" rel="noopener noreferrer" className="artist-link">
                {"🌐"} {extractHostname(artist.website)}
              </a>
            )}
            {artist.social_links?.instagram && (
              <a href={`https://instagram.com/${artist.social_links.instagram}`} target="_blank" rel="noopener noreferrer" className="artist-link">
                {"📷"} {artist.social_links.instagram}
              </a>
            )}
            {artist.social_links?.twitter && (
              <a href={`https://twitter.com/${artist.social_links.twitter}`} target="_blank" rel="noopener noreferrer" className="artist-link">
                {"𝕏"} {artist.social_links.twitter}
              </a>
            )}
          </div>
        ) : (
          <p className="artist-bio-empty">
            No contact information available. If you are this artist, you can claim this profile.
          </p>
        )}

        {/* Claim / Verified indicator */}
        {artist.claimed_by_user_id ? (
          <p className="artist-claimed-note">
            <VerifiedBadge /> Verified Artist
          </p>
        ) : isAuthenticated ? (
          <button
            className="btn btn-primary"
            onClick={() => setShowClaimModal(true)}
            style={{ marginTop: "0.75rem" }}
          >
            Claim This Profile
          </button>
        ) : null}
      </div>

      {/* Portfolio / Artworks */}
      <div className="artist-portfolio-section">
        <h2 className="artist-section-title">
          Artworks ({artist.artwork_count})
        </h2>
        {artist.artworks.length === 0 ? (
          <p className="artist-bio-empty">
            No artworks linked to this artist yet. Suggest this artist on an artwork page to connect their work.
          </p>
        ) : (
        <div className="artist-grid">
          {artist.artworks.map((aw) => (
              <Link
                key={aw.id}
                to={`/artworks/${aw.id}`}
                className="profile-card"
              >
                {aw.thumbnail_url ? (
                  <img
                    src={aw.thumbnail_url}
                    alt={aw.title || "Artwork"}
                    className="profile-card-img"
                    loading="lazy"
                  />
                ) : (
                  <div className="profile-card-img profile-card-img-empty" />
                )}
                <div className="profile-card-body">
                  <span className="profile-card-title">
                    {aw.title || "Untitled"}
                  </span>
                </div>
                {aw.photo_count != null && (
                  <div className="profile-card-footer">
                    {aw.photo_count} photo{aw.photo_count !== 1 ? "s" : ""}
                    <FavoriteButton artworkId={aw.id} className="favorite-btn-card" />
                  </div>
                )}
              </Link>
          ))}
        </div>
        )}
      </div>

      {/* Comments */}
      {/* Similar Artists by Style */}
      {styleSimilarArtists.length > 0 && (
        <div className="style-similar-section">
          <h2 className="artist-section-title">Similar Artists</h2>
          <div className="style-similar-grid">
            {styleSimilarArtists.map((sa) => (
              <Link
                key={sa.artist_id}
                to={`/artists/${sa.artist_id}`}
                className="style-similar-card"
              >
                <div className="style-similar-avatar">
                  {sa.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")
                    .toUpperCase()
                    .slice(0, 2)}
                </div>
                <div className="style-similar-info">
                  <span>{sa.name}</span>
                </div>
                <div className="style-similar-meta">
                  {sa.artwork_count} artwork{sa.artwork_count !== 1 ? "s" : ""}
                </div>
                <div className="style-similar-score">
                  {Math.round(sa.similarity * 100)}% match
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Comments */}
      <CommentSection targetType="artist" targetId={artist.id} />

      {/* Claim Modal */}
      {showClaimModal && (
        <div className="claim-modal-overlay" onClick={() => !claimSubmitting && setShowClaimModal(false)}>
          <div className="claim-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Claim This Profile</h2>

            {claimSuccess ? (
              <div className="claim-success">
                <p>Claim submitted! A moderator will review within 48h.</p>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setShowClaimModal(false);
                    setClaimSuccess(false);
                    setClaimText("");
                    setClaimUrl("");
                  }}
                >
                  Close
                </button>
              </div>
            ) : (
              <>
                <label className="claim-label">
                  How can we verify you are this artist?
                  <textarea
                    className="claim-textarea"
                    value={claimText}
                    onChange={(e) => setClaimText(e.target.value)}
                    placeholder="Describe how we can verify your identity (min 10 chars)"
                    rows={4}
                  />
                </label>

                <label className="claim-label">
                  Link to your social media or portfolio
                  <input
                    type="url"
                    className="claim-url-input"
                    value={claimUrl}
                    onChange={(e) => setClaimUrl(e.target.value)}
                    placeholder="https://..."
                  />
                </label>

                {claimError && <p className="form-error">{claimError}</p>}

                <div className="claim-actions">
                  <button
                    className="btn btn-primary"
                    disabled={claimSubmitting || claimText.length < 10}
                    onClick={handleClaimSubmit}
                  >
                    {claimSubmitting ? "Submitting..." : "Submit Claim"}
                  </button>
                  <button
                    className="btn"
                    onClick={() => setShowClaimModal(false)}
                    disabled={claimSubmitting}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ArtistProfilePage;
