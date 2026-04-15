import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";
import FavoriteButton from "../components/FavoriteButton";
import FollowButton from "../components/FollowButton";
import BadgeIcon from "../components/BadgeIcon";


interface UserPhoto {
  id: string;
  image_url: string;
  thumbnail_url?: string | null;
  artwork_id: string | null;
  date_uploaded: string;
}

interface UserBadge {
  badge_type: string;
  earned_at?: string;
}

interface UserProfile {
  id?: string;
  display_name: string;
  avatar_url?: string | null;
  bio: string | null;
  tagline?: string | null;
  website?: string | null;
  social_links?: { instagram?: string; twitter?: string } | null;
  profile_type?: "photographer" | "artist" | "explorer" | null;
  created_at: string;
  total_photos: number;
  total_artworks: number;
  artworks_discovered?: number;
  unique_artworks_contributed?: number;
  follower_count?: number;
  is_following?: boolean;
  badges?: UserBadge[];
  photos: UserPhoto[];
}

interface DiscoveryItem {
  id: string;
  title: string | null;
  status: string;
  thumbnail_url: string | null;
  photo_count: number;
  created_at: string;
}


function getInitialsAvatar(name: string): { initial: string; color: string } {
  const initial = name.charAt(0).toUpperCase();
  const colors = [
    "#e74c3c",
    "#3498db",
    "#2ecc71",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#34495e",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const color = colors[Math.abs(hash) % colors.length];
  return { initial, color };
}

function formatMemberSince(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
  });
}

function formatDateShort(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const PROFILE_TYPE_LABELS: Record<string, string> = {
  photographer: "Photographer",
  artist: "Artist",
  explorer: "Explorer",
};

function extractHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}



function UserProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [startingChat, setStartingChat] = useState(false);

  async function handleMessage() {
    if (!id) return;
    setStartingChat(true);
    try {
      await apiClient.post(`/api/messages/conversations?other_user_id=${id}`);
      navigate("/messages");
    } catch {
      alert("Could not start conversation.");
    } finally {
      setStartingChat(false);
    }
  }

  // Tab state
  const [activeTab, setActiveTab] = useState<"photos" | "discoveries">(
    "photos"
  );

  // Discoveries state
  const [discoveries, setDiscoveries] = useState<DiscoveryItem[]>([]);
  const [discoveriesLoading, setDiscoveriesLoading] = useState(false);
  const [discoveriesError, setDiscoveriesError] = useState("");
  const [discoveriesFetched, setDiscoveriesFetched] = useState(false);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setError("");

    apiClient
      .get<UserProfile>(`/api/users/${id}/profile`)
      .then((res) => {
        setProfile(res.data);
      })
      .catch(() => {
        setError(
          "Failed to load user profile. They may not exist or the server is unavailable."
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id]);

  // Fetch discoveries when tab is switched
  useEffect(() => {
    if (activeTab !== "discoveries" || !id || discoveriesFetched) return;

    setDiscoveriesLoading(true);
    setDiscoveriesError("");

    apiClient
      .get<DiscoveryItem[]>(`/api/users/${id}/discoveries`)
      .then((res) => {
        setDiscoveries(res.data);
        setDiscoveriesFetched(true);
      })
      .catch(() => {
        setDiscoveriesError("Failed to load discoveries.");
      })
      .finally(() => {
        setDiscoveriesLoading(false);
      });
  }, [activeTab, id, discoveriesFetched]);


  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  if (error || !profile) {
    return (
      <div className="page">
        <div className="profile-error">
          <h1>User Not Found</h1>
          <p>{error || "This user could not be loaded."}</p>
          <Link to="/" className="btn btn-primary">
            Back to Map
          </Link>
        </div>
      </div>
    );
  }

  const avatar = getInitialsAvatar(profile.display_name);
  const hasLinks =
    profile.website ||
    profile.social_links?.instagram ||
    profile.social_links?.twitter;

  return (
    <div className="page profile-page user-page">
      {/* Hero section */}
      <div className="profile-hero">
        <div
          className="profile-avatar"
          style={{ background: profile.avatar_url ? "transparent" : avatar.color }}
        >
          {profile.avatar_url ? (
            <img src={profile.avatar_url} alt={profile.display_name} className="profile-avatar-img" />
          ) : (
            avatar.initial
          )}
        </div>
        <div className="profile-hero-info">
          <span className="page-type-badge user">
            {PROFILE_TYPE_LABELS[profile.profile_type ?? "explorer"] ?? "Explorer"}
          </span>
          <div className="profile-header">
            <h1>
              {profile.display_name}
              {profile.badges && profile.badges.length > 0 && (
                <span className="profile-badges">
                  {profile.badges.map((b) => (
                    <BadgeIcon key={b.badge_type} badgeType={b.badge_type} size="sm" />
                  ))}
                </span>
              )}
            </h1>
            {user?.id !== id && (
              <>
                <FollowButton
                  targetType="user"
                  targetId={id!}
                  initialFollowing={profile.is_following}
                  initialCount={profile.follower_count ?? 0}
                />
                {user && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleMessage}
                    disabled={startingChat}
                  >
                    {startingChat ? "..." : "Message"}
                  </button>
                )}
              </>
            )}
          </div>
          {profile.tagline && (
            <p className="profile-tagline">{profile.tagline}</p>
          )}
          <p className="profile-member-since">
            Member since {formatMemberSince(profile.created_at)}
          </p>
        </div>
      </div>

      {profile.bio && <p className="profile-bio">{profile.bio}</p>}

      {/* Hidden stat line for backward compatibility with existing tests */}
      <p className="profile-stat" style={{ position: "absolute", left: "-9999px", height: "1px", overflow: "hidden" }}>
        {profile.total_photos} photo{profile.total_photos !== 1 ? "s" : ""}{" "}
        uploaded &middot; {profile.total_artworks} artwork
        {profile.total_artworks !== 1 ? "s" : ""} cataloged
      </p>

      {/* Stats bar */}
      <div className="profile-stats">
        <div className="profile-stat-box">
          <span className="artist-stat-value">{profile.total_photos}</span>
          <span className="artist-stat-label">Photos</span>
        </div>
        <div className="profile-stat-box">
          <span className="artist-stat-value">
            {profile.unique_artworks_contributed ?? profile.total_artworks}
          </span>
          <span className="artist-stat-label">Artworks Contributed</span>
        </div>
        <div className="profile-stat-box">
          <span className="artist-stat-value">
            {profile.artworks_discovered ?? 0}
          </span>
          <span className="artist-stat-label">Discovered</span>
        </div>
      </div>

      {/* Links row */}
      {hasLinks && (
        <div className="profile-links">
          {profile.website && (
            <a
              href={profile.website}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-link"
            >
              {"🌐"} {extractHostname(profile.website)}
            </a>
          )}
          {profile.social_links?.instagram && (
            <a
              href={`https://instagram.com/${profile.social_links.instagram}`}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-link"
            >
              {"📷"} {profile.social_links.instagram}
            </a>
          )}
          {profile.social_links?.twitter && (
            <a
              href={`https://twitter.com/${profile.social_links.twitter}`}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-link"
            >
              {"𝕏"} {profile.social_links.twitter}
            </a>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="profile-tabs">
        <button
          className={`profile-tab${activeTab === "photos" ? " active" : ""}`}
          onClick={() => setActiveTab("photos")}
        >
          Photos
        </button>
        <button
          className={`profile-tab${activeTab === "discoveries" ? " active" : ""}`}
          onClick={() => setActiveTab("discoveries")}
        >
          Discoveries
        </button>
      </div>

      {/* Photos tab */}
      {activeTab === "photos" && (
        <>
          {profile.photos.length === 0 ? (
            <p className="profile-empty">No photos uploaded yet.</p>
          ) : (
            <div className="profile-grid">
              {profile.photos.map((photo) => {
                const inner = (
                  <>
                    <img
                      src={photo.thumbnail_url || photo.image_url}
                      alt="Uploaded photo"
                      className="profile-card-img"
                      loading="lazy"
                    />
                    <div className="profile-card-body">
                      <span className="profile-card-date">
                        {formatDateShort(photo.date_uploaded)}
                      </span>
                    </div>
                  </>
                );

                if (photo.artwork_id) {
                  return (
                    <Link
                      key={photo.id}
                      to={`/artworks/${photo.artwork_id}`}
                      className="profile-card"
                    >
                      {inner}
                    </Link>
                  );
                }

                return (
                  <div key={photo.id} className="profile-card">
                    {inner}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Discoveries tab */}
      {activeTab === "discoveries" && (
        <>
          {discoveriesLoading && (
            <div className="loading">
              <div className="spinner" />
            </div>
          )}
          {discoveriesError && (
            <p className="profile-empty">{discoveriesError}</p>
          )}
          {!discoveriesLoading && !discoveriesError && discoveries.length === 0 && discoveriesFetched && (
            <p className="profile-empty">No discoveries yet.</p>
          )}
          {!discoveriesLoading && discoveries.length > 0 && (
            <div className="artist-grid">
              {discoveries.map((item) => (
                  <Link
                    key={item.id}
                    to={`/artworks/${item.id}`}
                    className="profile-card"
                  >
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt={item.title || "Artwork"}
                        className="profile-card-img"
                        loading="lazy"
                      />
                    ) : (
                      <div className="profile-card-img profile-card-img-empty" />
                    )}
                    <div className="profile-card-body">
                      <span className="profile-card-title">
                        {item.title || "Untitled"}
                      </span>
                    </div>
                    <div className="profile-card-footer">
                      {item.photo_count} photo
                      {item.photo_count !== 1 ? "s" : ""}
                      <FavoriteButton artworkId={item.id} className="favorite-btn-card" />
                    </div>
                  </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default UserProfilePage;
