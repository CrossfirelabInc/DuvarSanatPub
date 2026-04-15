import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { MapContainer, TileLayer, Marker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";
import PhotoLightbox from "../components/PhotoLightbox";
import CommentSection from "../components/CommentSection";
import FavoriteButton from "../components/FavoriteButton";
import FlagButton from "../components/FlagButton";
import ComparisonSlider from "../components/ComparisonSlider";

// Fix default marker icon
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});


interface Photo {
  id: string;
  image_url: string;
  thumbnail_url?: string | null;
  date_taken: string | null;
  date_uploaded: string;
  user_id: string;
  user_display_name: string;
  categories?: string[];
  vote_count?: number;
}

interface SimilarArtwork {
  artwork_id: string;
  title: string | null;
  thumbnail_url: string | null;
  similarity: number;
}

interface StyleSimilarArtwork {
  artwork_id: string;
  title: string | null;
  thumbnail_url: string | null;
  similarity: number;
}

interface ArtistSuggestion {
  artist_name: string;
  count: number;
  status: string;
}

interface ArtworkDetail {
  id: string;
  title: string | null;
  description: string | null;
  status: "active" | "modified" | "gone";
  latitude: number;
  longitude: number;
  artist_id: string | null;
  artist_name: string | null;
  created_by: string;
  creator_display_name: string;
  photos: Photo[];
  photo_count: number;
  created_at: string;
  updated_at: string;
  suggestions?: ArtistSuggestion[];
}

interface ArtistSuggestionResponse {
  artist_name: string;
  count: number;
  status: string;
  artist_id: string | null;
}


const STATUS_COLORS: Record<string, string> = {
  active: "#27ae60",
  modified: "#f39c12",
  gone: "#e74c3c",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Still There",
  modified: "Changed",
  gone: "Painted Over",
};

const CONSENSUS_THRESHOLD = 3;


function ArtworkDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, isAuthenticated } = useAuth();

  const [artwork, setArtwork] = useState<ArtworkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Vote tracking: photoId -> { voted, vote_count }
  const [votes, setVotes] = useState<
    Record<string, { voted: boolean; vote_count: number }>
  >({});

  // Downvote tracking: photoId -> { voted }
  const [downvotes, setDownvotes] = useState<Record<string, { voted: boolean }>>({});

  // Neighbor artworks (prev/next by proximity)
  const [neighbors, setNeighbors] = useState<{
    prev: { id: string; title: string | null; thumbnail_url: string | null } | null;
    next: { id: string; title: string | null; thumbnail_url: string | null } | null;
  }>({ prev: null, next: null });

  // Similar artworks
  const [similarArtworks, setSimilarArtworks] = useState<SimilarArtwork[]>([]);

  // Style-similar artworks
  const [styleSimilarArtworks, setStyleSimilarArtworks] = useState<StyleSimilarArtwork[]>([]);

  const suggestTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    };
  }, []);

  // Suggest artist
  const [showSuggest, setShowSuggest] = useState(false);
  const [artistName, setArtistName] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState("");
  const [suggestSuccess, setSuggestSuccess] = useState(false);

  // Artist autocomplete
  const [allArtists, setAllArtists] = useState<{ id: string; name: string }[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);

  useEffect(() => {
    apiClient.get<{ id: string; name: string }[]>("/api/artists")
      .then((res) => setAllArtists(res.data || []))
      .catch(() => {});
  }, []);

  const filteredArtists = artistName.trim().length >= 1
    ? allArtists.filter((a) => a.name.toLowerCase().includes(artistName.toLowerCase())).slice(0, 5)
    : [];
  const [alreadySuggested, setAlreadySuggested] = useState(false);

  // Lightbox with navigation
  const [lightboxPhoto, setLightboxPhoto] = useState<Photo | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  // Category filter
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [sortOrder, setSortOrder] = useState<"oldest" | "newest">("oldest");

  // Comparison slider
  const [compareBeforeIdx, setCompareBeforeIdx] = useState(0);
  const [compareAfterIdx, setCompareAfterIdx] = useState(0);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setError("");

    apiClient
      .get<ArtworkDetail>(`/api/artworks/${id}`)
      .then((res) => {
        setArtwork(res.data);
        // Initialize vote counts from photo data
        const initialVotes: Record<string, { voted: boolean; vote_count: number }> = {};
        for (const photo of res.data.photos) {
          initialVotes[photo.id] = {
            voted: false,
            vote_count: photo.vote_count ?? 0,
          };
        }
        setVotes(initialVotes);

        // Set default comparison indices: oldest vs newest
        if (res.data.photos.length >= 2) {
          setCompareBeforeIdx(0);
          setCompareAfterIdx(res.data.photos.length - 1);
        }
      })
      .catch(() => {
        setError("Failed to load artwork. It may not exist or the server is unavailable.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id]);

  // Fetch neighbor artworks
  useEffect(() => {
    if (!id) return;
    apiClient
      .get<typeof neighbors>(`/api/artworks/${id}/neighbors`)
      .then((res) => setNeighbors(res.data))
      .catch(() => {});
  }, [id]);

  // Fetch similar artworks
  useEffect(() => {
    if (!id) return;

    apiClient
      .get<SimilarArtwork[]>(`/api/artworks/${id}/similar`)
      .then((res) => {
        if (Array.isArray(res.data)) {
          setSimilarArtworks(res.data.slice(0, 3));
        }
      })
      .catch(() => {
        // Gracefully ignore - endpoint may not exist yet
      });
  }, [id]);

  // Fetch style-similar artworks
  useEffect(() => {
    if (!id) return;

    apiClient
      .get<StyleSimilarArtwork[]>(`/api/artworks/${id}/style-similar`)
      .then((res) => {
        if (Array.isArray(res.data)) {
          setStyleSimilarArtworks(res.data.slice(0, 5));
        }
      })
      .catch(() => {
        // Gracefully ignore
      });
  }, [id]);

  const handleVote = useCallback(
    async (photoId: string) => {
      if (!isAuthenticated) return;

      const prev = votes[photoId];
      if (!prev) return;

      // Optimistic update
      setVotes((v) => ({
        ...v,
        [photoId]: {
          voted: !prev.voted,
          vote_count: prev.voted ? prev.vote_count - 1 : prev.vote_count + 1,
        },
      }));

      try {
        const res = await apiClient.post<{ voted: boolean; vote_count: number }>(
          `/api/photos/${photoId}/vote`
        );
        setVotes((v) => ({
          ...v,
          [photoId]: { voted: res.data.voted, vote_count: res.data.vote_count },
        }));
      } catch {
        // Revert
        setVotes((v) => ({
          ...v,
          [photoId]: prev,
        }));
      }
    },
    [isAuthenticated, votes]
  );

  const handleDownvote = useCallback(
    async (photoId: string) => {
      if (!isAuthenticated) return;

      const prev = downvotes[photoId];
      setDownvotes((v) => ({
        ...v,
        [photoId]: { voted: !(prev?.voted) },
      }));

      try {
        const res = await apiClient.post<{ voted: boolean }>(
          `/api/photos/${photoId}/downvote`
        );
        setDownvotes((v) => ({
          ...v,
          [photoId]: { voted: res.data.voted },
        }));
      } catch {
        setDownvotes((v) => ({
          ...v,
          [photoId]: prev || { voted: false },
        }));
      }
    },
    [isAuthenticated, downvotes]
  );

  // Compute available categories from photos
  const categoryTabs = useMemo(() => {
    if (!artwork) return [];
    const counts: Record<string, number> = {};
    for (const photo of artwork.photos) {
      const cats = photo.categories ?? [];
      for (const cat of cats) {
        counts[cat] = (counts[cat] || 0) + 1;
      }
    }
    const tabs: Array<{ label: string; count: number }> = [
      { label: "All", count: artwork.photos.length },
    ];
    for (const [label, count] of Object.entries(counts)) {
      tabs.push({ label, count });
    }
    return tabs;
  }, [artwork]);

  // Filter photos by active category
  const filteredPhotos = useMemo(() => {
    if (!artwork) return [];
    if (activeCategory === "All") return artwork.photos;
    return artwork.photos.filter((p) =>
      (p.categories ?? []).includes(activeCategory)
    );
  }, [artwork, activeCategory]);

  // Sort photos by date for timeline
  const sortedPhotos = useMemo(() => {
    return [...filteredPhotos].sort((a, b) => {
      if (!a.date_taken && !b.date_taken) return 0;
      if (!a.date_taken) return 1;
      if (!b.date_taken) return -1;
      const diff = new Date(a.date_taken).getTime() - new Date(b.date_taken).getTime();
      return sortOrder === "oldest" ? diff : -diff;
    });
  }, [filteredPhotos, sortOrder]);

  async function handleSuggestArtist() {
    if (!id || !artistName.trim()) return;

    setSuggesting(true);
    setSuggestError("");
    setSuggestSuccess(false);
    setAlreadySuggested(false);

    try {
      const submittedName = artistName.trim();
      const res = await apiClient.post<ArtistSuggestionResponse>(
        `/api/artworks/${id}/suggest-artist`,
        { artist_name: submittedName }
      );
      // Update artwork state based on response
      setArtwork((prev) => {
        if (!prev) return prev;
        // If consensus reached, the artist_id will be set
        if (res.data.artist_id) {
          return {
            ...prev,
            artist_id: res.data.artist_id,
            artist_name: submittedName,
          };
        }
        // Update suggestions list
        const existing = prev.suggestions ?? [];
        const idx = existing.findIndex(
          (s) => s.artist_name.toLowerCase() === submittedName.toLowerCase()
        );
        let updated: ArtistSuggestion[];
        if (idx >= 0) {
          updated = [...existing];
          updated[idx] = {
            artist_name: res.data.artist_name,
            count: res.data.count,
            status: res.data.status,
          };
        } else {
          updated = [
            ...existing,
            {
              artist_name: res.data.artist_name,
              count: res.data.count,
              status: res.data.status,
            },
          ];
        }
        return { ...prev, suggestions: updated };
      });
      setSuggestSuccess(true);
      setArtistName("");
      if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
      suggestTimerRef.current = setTimeout(() => {
        setShowSuggest(false);
        setSuggestSuccess(false);
      }, 2000);
    } catch (err: unknown) {
      // 409 means user already suggested
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { status?: number } }).response?.status === 409
      ) {
        setAlreadySuggested(true);
      } else {
        setSuggestError("Failed to suggest artist. Please try again.");
      }
    } finally {
      setSuggesting(false);
    }
  }


  if (loading) {
    return <div className="loading">Loading artwork...</div>;
  }

  if (error || !artwork) {
    return (
      <div className="page">
        <div className="artwork-error">
          <h1>Artwork Not Found</h1>
          <p>{error || "This artwork could not be loaded."}</p>
          <Link to="/" className="btn btn-primary">
            Back to Map
          </Link>
        </div>
      </div>
    );
  }

  const statusColor = STATUS_COLORS[artwork.status] || STATUS_COLORS.active;
  const hasSuggestions =
    !artwork.artist_id &&
    artwork.suggestions &&
    artwork.suggestions.length > 0;

  return (
    <div className="page artwork-page">
      {/* Prev/Next artwork sidebar navigation */}
      {neighbors.prev && (
        <Link to={`/artworks/${neighbors.prev.id}`} className="artwork-nav artwork-nav-prev" title={neighbors.prev.title || "Previous artwork"}>
          <span className="artwork-nav-arrow">&#x2039;</span>
          <div className="artwork-nav-info">
            {neighbors.prev.thumbnail_url && (
              <img src={neighbors.prev.thumbnail_url} alt="" className="artwork-nav-thumb" />
            )}
            <span className="artwork-nav-label">{neighbors.prev.title || "Nearby"}</span>
          </div>
        </Link>
      )}
      {neighbors.next && (
        <Link to={`/artworks/${neighbors.next.id}`} className="artwork-nav artwork-nav-next" title={neighbors.next.title || "Next artwork"}>
          <div className="artwork-nav-info">
            {neighbors.next.thumbnail_url && (
              <img src={neighbors.next.thumbnail_url} alt="" className="artwork-nav-thumb" />
            )}
            <span className="artwork-nav-label">{neighbors.next.title || "Nearby"}</span>
          </div>
          <span className="artwork-nav-arrow">&#x203A;</span>
        </Link>
      )}
      <Helmet>
        <title>{`${artwork.title || "Untitled"} — DuvarSanat`}</title>
        <meta name="description" content={`Street art in Istanbul${artwork.artist_name ? ` by ${artwork.artist_name}` : ""}. ${artwork.photos.length} photos documenting this wall.`} />
        <meta property="og:title" content={`${artwork.title || "Untitled"} — DuvarSanat`} />
        <meta property="og:description" content={artwork.description || "Street art documented on DuvarSanat"} />
        {artwork.photos[0] && <meta property="og:image" content={artwork.photos[0].image_url} />}
      </Helmet>
      <div className="artwork-header">
        <span className="page-type-badge artwork">Artwork</span>
        <div className="artwork-title-row">
          <h1 className="artwork-title">
            {artwork.title || "Untitled"}
          </h1>
          <FavoriteButton artworkId={artwork.id} />
          <FlagButton targetType="artwork" targetId={artwork.id} />
        </div>
      </div>

      <div className="artwork-meta">
        {artwork.artist_id && artwork.artist_name ? (
          <p>
            By{" "}
            <Link to={`/artists/${artwork.artist_id}`} className="artwork-link">
              {artwork.artist_name}
            </Link>
          </p>
        ) : (
          <p>
            <em className="artwork-anonymous">Anonymous</em>
            {isAuthenticated && (
              <button
                className="btn-inline-link"
                onClick={() => setShowSuggest(true)}
              >
                Know the artist? Suggest one
              </button>
            )}
          </p>
        )}
        <p>
          Cataloged by{" "}
          <Link
            to={`/users/${artwork.created_by}`}
            className="artwork-link"
          >
            {artwork.creator_display_name}
          </Link>
        </p>
        <p className="artwork-status-line">
          Wall: <span className="artwork-status-dot" style={{ background: statusColor }} /> {STATUS_LABELS[artwork.status] || artwork.status}
        </p>
      </div>

      {/* Mini map */}
      <div className="artwork-map-wrapper">
        <MapContainer
          center={[artwork.latitude, artwork.longitude]}
          zoom={16}
          className="artwork-map"
          scrollWheelZoom={false}
          dragging={false}
          zoomControl={false}
          doubleClickZoom={false}
          touchZoom={false}
          attributionControl={false}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Marker position={[artwork.latitude, artwork.longitude]} />
        </MapContainer>
      </div>

      {/* Artist suggestions section */}
      {hasSuggestions && (
        <div className="suggestions-section">
          <h3 style={{ color: "#2c2c2c", marginBottom: "12px", fontSize: "1rem" }}>
            Community Suggestions
          </h3>
          {artwork.suggestions!.map((suggestion) => (
            <div key={suggestion.artist_name} className="suggestion-item">
              <span style={{ color: "#2c2c2c", fontSize: "0.9rem", minWidth: "120px" }}>
                {suggestion.artist_name}
              </span>
              <div className="suggestion-bar">
                <div
                  className="suggestion-bar-fill"
                  style={{
                    width: `${Math.min((suggestion.count / CONSENSUS_THRESHOLD) * 100, 100)}%`,
                  }}
                />
              </div>
              <span style={{ color: "#666", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                {suggestion.count} vote{suggestion.count !== 1 ? "s" : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="artwork-actions">
        {isAuthenticated && (
          <button
            className="btn btn-ghost"
            onClick={() => {
              setShowSuggest(!showSuggest);
              setSuggestSuccess(false);
              setSuggestError("");
              setAlreadySuggested(false);
            }}
          >
            {showSuggest ? "Cancel" : "Suggest Artist"}
          </button>
        )}
        <Link to="/upload" className="btn btn-primary">
          I have a photo of this
        </Link>
      </div>

      {/* Suggest artist form */}
      {showSuggest && (
        <div className="artwork-suggest">
          <div className="artwork-suggest-row">
            <div className="autocomplete-wrapper">
              <input
                type="text"
                value={artistName}
                onChange={(e) => {
                  setArtistName(e.target.value);
                  setShowAutocomplete(true);
                }}
                onFocus={() => setShowAutocomplete(true)}
                onBlur={() => setTimeout(() => setShowAutocomplete(false), 200)}
                placeholder="Start typing an artist name..."
                className="artwork-suggest-input"
                disabled={suggesting}
              />
              {showAutocomplete && filteredArtists.length > 0 && (
                <div className="autocomplete-dropdown">
                  {filteredArtists.map((a) => (
                    <button
                      key={a.id}
                      className="autocomplete-item"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setArtistName(a.name);
                        setShowAutocomplete(false);
                      }}
                    >
                      {a.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSuggestArtist}
              disabled={suggesting || !artistName.trim()}
            >
              {suggesting ? "Saving..." : "Submit"}
            </button>
          </div>
          {suggestError && (
            <p className="artwork-suggest-error">{suggestError}</p>
          )}
          {alreadySuggested && (
            <p className="artwork-suggest-error">
              You've already suggested an artist for this work
            </p>
          )}
          {suggestSuccess && (
            <p className="artwork-suggest-success">
              Artist suggestion submitted successfully.
            </p>
          )}
        </div>
      )}

      {/* Photo timeline */}
      <div className="artwork-photos">
        <h2>
          Photos ({artwork.photos.length})
        </h2>

        {/* Filter & sort controls */}
        <div className="photo-filters">
          {categoryTabs.length > 1 && (
            <div className="category-tabs">
              {categoryTabs.map((tab) => (
                <button
                  key={tab.label}
                  className={`category-tab ${activeCategory === tab.label ? "active" : ""}`}
                  onClick={() => setActiveCategory(tab.label)}
                >
                  {tab.label} ({tab.count})
                </button>
              ))}
            </div>
          )}
          <div className="photo-sort">
            <button
              className={`category-tab ${sortOrder === "oldest" ? "active" : ""}`}
              onClick={() => setSortOrder("oldest")}
            >
              Oldest first
            </button>
            <button
              className={`category-tab ${sortOrder === "newest" ? "active" : ""}`}
              onClick={() => setSortOrder("newest")}
            >
              Newest first
            </button>
          </div>
        </div>

        {artwork.photos.length === 0 ? (
          <p className="artwork-no-photos">No photos yet.</p>
        ) : sortedPhotos.length === 0 ? (
          <p className="artwork-no-photos">No photos in this category.</p>
        ) : (
          <div className="timeline-container">
            <div className="timeline-track">
              {sortedPhotos.map((photo, idx) => {
                const photoVote = votes[photo.id];
                const isOwnPhoto = user?.id === photo.user_id;
                return (
                  <div
                    key={photo.id}
                    className="timeline-card"
                    onClick={() => { setLightboxPhoto(photo); setLightboxIndex(idx); }}
                  >
                    <img
                      src={photo.thumbnail_url || photo.image_url}
                      alt={artwork.title || "Artwork photo"}
                      loading={idx === 0 ? undefined : "lazy"}
                    />
                    <div className="timeline-card-info">
                      <div className="timeline-date">
                        {photo.date_taken
                          ? new Date(photo.date_taken).toLocaleDateString(
                              undefined,
                              {
                                year: "numeric",
                                month: "short",
                              }
                            )
                          : "Date unknown"}
                      </div>
                      <div className="timeline-photographer">
                        by{" "}
                        <Link
                          to={`/users/${photo.user_id}`}
                          className="artwork-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          @{photo.user_display_name}
                        </Link>
                      </div>
                      {!isOwnPhoto && (
                        <div className="vote-row">
                          <button
                            className={`vote-btn ${photoVote?.voted ? "vote-btn--active" : ""}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleVote(photo.id);
                            }}
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
                          <span className="vote-count">
                            {photoVote?.vote_count ?? photo.vote_count ?? 0}
                          </span>
                          <button
                            className={`vote-btn vote-btn-down ${downvotes[photo.id]?.voted ? "vote-btn--active" : ""}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownvote(photo.id);
                            }}
                            disabled={!isAuthenticated}
                            title={
                              !isAuthenticated
                                ? "Login to vote"
                                : downvotes[photo.id]?.voted
                                  ? "Remove downvote"
                                  : "Downvote this photo"
                            }
                          >
                            &#x25BC;
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Compare Photos */}
      {sortedPhotos.length >= 2 && (
        <div className="comparison-section">
          <h2>Compare Photos</h2>
          <div className="comparison-selectors">
            <label>
              Before:
              <select
                value={compareBeforeIdx}
                onChange={(e) => setCompareBeforeIdx(Number(e.target.value))}
              >
                {sortedPhotos.map((p, i) => (
                  <option key={p.id} value={i}>
                    Photo {i + 1} — {p.user_display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              After:
              <select
                value={compareAfterIdx}
                onChange={(e) => setCompareAfterIdx(Number(e.target.value))}
              >
                {sortedPhotos.map((p, i) => (
                  <option key={p.id} value={i}>
                    Photo {i + 1} — {p.user_display_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ComparisonSlider
            beforeUrl={sortedPhotos[compareBeforeIdx].image_url}
            afterUrl={sortedPhotos[compareAfterIdx].image_url}
            beforeLabel={`Photo ${compareBeforeIdx + 1}`}
            afterLabel={`Photo ${compareAfterIdx + 1}`}
          />
        </div>
      )}

      {/* Comments */}
      <CommentSection targetType="artwork" targetId={artwork.id} />

      {/* Visually Similar Artworks */}
      {similarArtworks.length > 0 && (
        <div className="similar-section">
          <h3 className="similar-section-title">Visually Similar Artworks</h3>
          <div className="similar-grid">
            {similarArtworks.map((sa) => (
              <Link
                key={sa.artwork_id}
                to={`/artworks/${sa.artwork_id}`}
                className="similar-card"
              >
                {sa.thumbnail_url ? (
                  <img
                    src={sa.thumbnail_url}
                    alt={sa.title || "Similar artwork"}
                    className="similar-card-img"
                    loading="lazy"
                  />
                ) : (
                  <div className="similar-card-img similar-card-img-empty" />
                )}
                <div className="similar-card-info">
                  <span className="similar-card-title">
                    {sa.title || "Untitled"}
                  </span>
                  <span className="similar-card-pct">
                    {Math.round(sa.similarity * 100)}% similar
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Similar Style Artworks */}
      {styleSimilarArtworks.length > 0 && (
        <div className="style-similar-section">
          <h3 className="similar-section-title">Similar Style</h3>
          <p className="style-similar-subtitle">Artworks with a similar artistic vibe</p>
          <div className="style-similar-grid">
            {styleSimilarArtworks.map((sa) => (
              <Link
                key={sa.artwork_id}
                to={`/artworks/${sa.artwork_id}`}
                className="style-similar-card"
              >
                {sa.thumbnail_url ? (
                  <img
                    src={sa.thumbnail_url}
                    alt={sa.title || "Style-similar artwork"}
                    loading="lazy"
                  />
                ) : (
                  <div className="style-similar-placeholder" />
                )}
                <div className="style-similar-info">
                  <span>{sa.title || "Untitled"}</span>
                </div>
                <div className="style-similar-score">
                  {Math.round(sa.similarity * 100)}% match
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Lightbox */}
      {lightboxPhoto && (
        <PhotoLightbox
          photo={lightboxPhoto}
          artworkVotes={votes}
          artworkDownvotes={downvotes}
          currentUserId={user?.id}
          isAuthenticated={isAuthenticated}
          onVote={handleVote}
          onDownvote={handleDownvote}
          hasPrev={lightboxIndex > 0}
          hasNext={lightboxIndex < sortedPhotos.length - 1}
          onPrev={() => {
            const prev = sortedPhotos[lightboxIndex - 1];
            if (prev) { setLightboxPhoto(prev); setLightboxIndex(lightboxIndex - 1); }
          }}
          onNext={() => {
            const next = sortedPhotos[lightboxIndex + 1];
            if (next) { setLightboxPhoto(next); setLightboxIndex(lightboxIndex + 1); }
          }}
          onClose={() => setLightboxPhoto(null)}
        />
      )}
    </div>
  );
}

export default ArtworkDetailPage;
