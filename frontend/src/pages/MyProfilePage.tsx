import { useState, useEffect, useRef, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AxiosError } from "axios";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";
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

interface FollowingArtist {
  id: string;
  name: string;
  artwork_count: number;
  follower_count: number;
}

interface FollowingUser {
  id: string;
  display_name: string;
  follower_count: number;
}

interface FollowingList {
  artists: FollowingArtist[];
  users: FollowingUser[];
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

function stripAtSign(handle: string): string {
  return handle.startsWith("@") ? handle.slice(1) : handle;
}



function MyProfilePage() {
  const { user, updateUser } = useAuth();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editBio, setEditBio] = useState("");
  const [editTagline, setEditTagline] = useState("");
  const [editWebsite, setEditWebsite] = useState("");
  const [editInstagram, setEditInstagram] = useState("");
  const [editTwitter, setEditTwitter] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Avatar upload state
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState("");

  // Tab state
  const [activeTab, setActiveTab] = useState<"photos" | "discoveries" | "following">(
    "photos"
  );

  // Following state
  const [followingData, setFollowingData] = useState<FollowingList | null>(null);
  const [followingLoading, setFollowingLoading] = useState(false);
  const [followingError, setFollowingError] = useState("");
  const [followingFetched, setFollowingFetched] = useState(false);

  // Discoveries state
  const [discoveries, setDiscoveries] = useState<DiscoveryItem[]>([]);
  const [discoveriesLoading, setDiscoveriesLoading] = useState(false);
  const [discoveriesError, setDiscoveriesError] = useState("");
  const [discoveriesFetched, setDiscoveriesFetched] = useState(false);

  useEffect(() => {
    if (!user) return;

    setLoading(true);
    setError("");

    apiClient
      .get<UserProfile>(`/api/users/${user.id}/profile`)
      .then((res) => {
        setProfile(res.data);
      })
      .catch(() => {
        setError("Failed to load your profile. Please try again later.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [user]);

  // Fetch discoveries when tab is switched
  useEffect(() => {
    if (activeTab !== "discoveries" || !user || discoveriesFetched) return;

    setDiscoveriesLoading(true);
    setDiscoveriesError("");

    apiClient
      .get<DiscoveryItem[]>(`/api/users/${user.id}/discoveries`)
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
  }, [activeTab, user, discoveriesFetched]);

  // Fetch following data when tab is switched
  useEffect(() => {
    if (activeTab !== "following" || !user || followingFetched) return;

    setFollowingLoading(true);
    setFollowingError("");

    apiClient
      .get<FollowingList>("/api/users/me/following")
      .then((res) => {
        setFollowingData(res.data);
        setFollowingFetched(true);
      })
      .catch(() => {
        setFollowingError("Failed to load following list.");
      })
      .finally(() => {
        setFollowingLoading(false);
      });
  }, [activeTab, user, followingFetched]);

  function handleEditStart() {
    if (!profile) return;
    setEditName(profile.display_name);
    setEditBio(profile.bio || "");
    setEditTagline(profile.tagline || "");
    setEditWebsite(profile.website || "");
    setEditInstagram(profile.social_links?.instagram || "");
    setEditTwitter(profile.social_links?.twitter || "");
    setSaveError("");
    setSaveSuccess(false);
    setEditing(true);
  }

  function handleEditCancel() {
    setEditing(false);
    setSaveError("");
    setSaveSuccess(false);
  }

  async function handleEditSave(e: FormEvent) {
    e.preventDefault();

    if (!editName.trim()) {
      setSaveError("Display name is required.");
      return;
    }

    if (editName.trim().length < 2) {
      setSaveError("Display name must be at least 2 characters.");
      return;
    }

    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);

    const instagram = stripAtSign(editInstagram.trim()) || null;
    const twitter = stripAtSign(editTwitter.trim()) || null;
    const socialLinks =
      instagram || twitter ? { instagram: instagram || undefined, twitter: twitter || undefined } : null;

    try {
      await apiClient.patch("/api/users/me", {
        display_name: editName.trim(),
        bio: editBio.trim() || null,
        tagline: editTagline.trim() || null,
        website: editWebsite.trim() || null,
        social_links: socialLinks,
      });

      const trimmedName = editName.trim();

      // Update displayed profile
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              display_name: trimmedName,
              bio: editBio.trim() || null,
              tagline: editTagline.trim() || null,
              website: editWebsite.trim() || null,
              social_links: socialLinks,
            }
          : prev
      );

      // Sync display_name into AuthContext so nav bar updates immediately
      updateUser({ display_name: trimmedName });

      setSaveSuccess(true);
      setEditing(false);

      // Clear success message after a few seconds
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        const status = err.response.status;
        if (status === 409) {
          setSaveError(
            "That display name is already taken. Please choose another."
          );
        } else {
          const data = err.response.data;
          if (typeof data?.detail === "string") {
            setSaveError(data.detail);
          } else {
            setSaveError("Failed to save changes. Please try again.");
          }
        }
      } else {
        setSaveError("Network error. Please check your connection.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleAvatarUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setAvatarError("File size exceeds 5MB limit.");
      return;
    }

    setAvatarError("");
    setAvatarUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await apiClient.post("/api/users/me/avatar", formData);
      setProfile((prev) => prev ? { ...prev, avatar_url: res.data.avatar_url } : prev);
      updateUser({ avatar_url: res.data.avatar_url });
    } catch (err) {
      if (err instanceof AxiosError && err.response?.data?.detail) {
        setAvatarError(err.response.data.detail);
      } else {
        setAvatarError("Failed to upload avatar.");
      }
    } finally {
      setAvatarUploading(false);
      if (avatarInputRef.current) avatarInputRef.current.value = "";
    }
  }


  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  if (error || !profile) {
    return (
      <div className="page">
        <div className="profile-error">
          <h1>Profile Unavailable</h1>
          <p>{error || "Your profile could not be loaded."}</p>
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
          onClick={() => avatarInputRef.current?.click()}
          title="Click to change profile picture"
        >
          {profile.avatar_url ? (
            <img src={profile.avatar_url} alt={profile.display_name} className="profile-avatar-img" />
          ) : (
            avatar.initial
          )}
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: "none" }}
            onChange={handleAvatarUpload}
            disabled={avatarUploading}
          />
        </div>
        {avatarError && <div className="auth-error" style={{ marginTop: 8 }}>{avatarError}</div>}
        {avatarUploading && <div className="loading" style={{ marginTop: 4 }}>Uploading...</div>}
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
            {!editing && (
              <button className="btn btn-primary btn-sm" onClick={handleEditStart}>
                Edit Profile
              </button>
            )}
          </div>
          {profile.tagline && !editing && (
            <p className="profile-tagline">{profile.tagline}</p>
          )}
          <p className="profile-member-since">
            Member since {formatMemberSince(profile.created_at)}
          </p>
        </div>
      </div>

      {saveSuccess && (
        <div className="profile-save-success">
          Profile updated successfully.
        </div>
      )}

      {editing && (
        <form
          className="profile-edit-form"
          onSubmit={handleEditSave}
          noValidate
        >
          {saveError && <div className="auth-error">{saveError}</div>}

          <div className="form-field">
            <label htmlFor="edit-display-name">Display Name</label>
            <input
              id="edit-display-name"
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="form-field">
            <label htmlFor="edit-bio">Bio</label>
            <textarea
              id="edit-bio"
              className="profile-edit-textarea"
              value={editBio}
              onChange={(e) => setEditBio(e.target.value)}
              disabled={saving}
              rows={3}
              placeholder="Tell us about yourself..."
            />
          </div>

          <div className="form-field">
            <label htmlFor="edit-tagline">Tagline</label>
            <input
              id="edit-tagline"
              type="text"
              value={editTagline}
              onChange={(e) => setEditTagline(e.target.value)}
              disabled={saving}
              placeholder="A short tagline..."
            />
          </div>

          <div className="form-field">
            <label htmlFor="edit-website">Website</label>
            <input
              id="edit-website"
              type="url"
              value={editWebsite}
              onChange={(e) => setEditWebsite(e.target.value)}
              disabled={saving}
              placeholder="https://example.com"
            />
          </div>

          <div className="form-field">
            <label htmlFor="edit-instagram">Instagram Handle</label>
            <input
              id="edit-instagram"
              type="text"
              value={editInstagram}
              onChange={(e) => setEditInstagram(e.target.value)}
              disabled={saving}
              placeholder="username (without @)"
            />
          </div>

          <div className="form-field">
            <label htmlFor="edit-twitter">Twitter / X Handle</label>
            <input
              id="edit-twitter"
              type="text"
              value={editTwitter}
              onChange={(e) => setEditTwitter(e.target.value)}
              disabled={saving}
              placeholder="username (without @)"
            />
          </div>

          <div className="profile-edit-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleEditCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {!editing && profile.bio && (
        <p className="profile-bio">{profile.bio}</p>
      )}

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
      {!editing && hasLinks && (
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
        <button
          className={`profile-tab${activeTab === "following" ? " active" : ""}`}
          onClick={() => setActiveTab("following")}
        >
          Following
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
          {!discoveriesLoading &&
            !discoveriesError &&
            discoveries.length === 0 &&
            discoveriesFetched && (
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
                    </div>
                  </Link>
              ))}
            </div>
          )}
        </>
      )}

      {/* Following tab */}
      {activeTab === "following" && (
        <>
          {followingLoading && (
            <div className="loading">
              <div className="spinner" />
            </div>
          )}
          {followingError && (
            <p className="profile-empty">{followingError}</p>
          )}
          {!followingLoading && !followingError && followingFetched && followingData && (
            <>
              {followingData.artists.length === 0 && followingData.users.length === 0 && (
                <p className="profile-empty">You are not following anyone yet.</p>
              )}

              {followingData.artists.length > 0 && (
                <div className="following-section">
                  <h3 className="following-section-title">Artists</h3>
                  <div className="following-list">
                    {followingData.artists.map((artist) => (
                      <div key={artist.id} className="following-item">
                        <div
                          className="following-avatar"
                          style={{ background: getInitialsAvatar(artist.name).color }}
                        >
                          {getInitialsAvatar(artist.name).initial}
                        </div>
                        <div className="following-info">
                          <Link to={`/artists/${artist.id}`} className="following-name">
                            {artist.name}
                          </Link>
                          <span className="following-meta">
                            {artist.artwork_count} artwork{artist.artwork_count !== 1 ? "s" : ""}
                          </span>
                        </div>
                        <FollowButton
                          targetType="artist"
                          targetId={artist.id}
                          initialFollowing={true}
                          initialCount={artist.follower_count}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {followingData.users.length > 0 && (
                <div className="following-section">
                  <h3 className="following-section-title">Photographers</h3>
                  <div className="following-list">
                    {followingData.users.map((u) => (
                      <div key={u.id} className="following-item">
                        <div
                          className="following-avatar"
                          style={{ background: getInitialsAvatar(u.display_name).color }}
                        >
                          {getInitialsAvatar(u.display_name).initial}
                        </div>
                        <div className="following-info">
                          <Link to={`/users/${u.id}`} className="following-name">
                            {u.display_name}
                          </Link>
                        </div>
                        <FollowButton
                          targetType="user"
                          targetId={u.id}
                          initialFollowing={true}
                          initialCount={u.follower_count}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default MyProfilePage;
