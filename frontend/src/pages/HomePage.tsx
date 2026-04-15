import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import apiClient from "../api/client";
import FavoriteButton from "../components/FavoriteButton";

interface ArtOfTheDay {
  artwork_id: string;
  title: string | null;
  artist_name: string | null;
  photo_url: string | null;
  featured_date: string;
  description: string | null;
}

interface HomepageStats {
  total_artworks: number;
  total_photos: number;
  total_artists: number;
  walls_changed_this_week: number;
}

interface WallChanged {
  artwork_id: string;
  title: string | null;
  artist_name: string | null;
  neighborhood: string | null;
  oldest_photo_url: string | null;
  newest_photo_url: string | null;
  photo_count: number;
}

interface RecentDiscovery {
  id: string;
  title: string | null;
  artist_name: string | null;
  thumbnail_url: string | null;
  neighborhood: string | null;
  created_at: string;
}

interface Neighborhood {
  id: string;
  name: string;
  slug: string;
  artwork_count: number;
}

interface Contributor {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  photo_count: number;
  artwork_count: number;
}

interface ArtistItem {
  id: string;
  name: string;
  artwork_count: number;
}

interface TopArtwork {
  id: string;
  title: string | null;
  thumbnail_url: string | null;
  total_votes: number;
}

interface HomepageData {
  art_of_the_day: ArtOfTheDay | null;
  stats: HomepageStats;
  walls_changed: WallChanged[];
  recent_discoveries: RecentDiscovery[];
  neighborhoods: Neighborhood[];
  mysteries_count: number;
  top_contributors?: Contributor[];
  top_artworks?: TopArtwork[];
}

const defaultStats: HomepageStats = {
  total_artworks: 0,
  total_photos: 0,
  total_artists: 0,
  walls_changed_this_week: 0,
};

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

interface ActivityItem {
  id: string;
  type: string;
  image_url: string | null;
  user_name: string;
  user_id: string;
  target_id: string | null;
  content: string | null;
  created_at: string;
}

function activityLabel(item: ActivityItem): string {
  if (item.type === "photo_upload") return `${item.user_name} uploaded a photo`;
  if (item.type === "comment") return `${item.user_name} commented`;
  if (item.type === "artwork_created") return `${item.user_name} discovered ${item.content || "an artwork"}`;
  return `${item.user_name} did something`;
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function HomePage() {
  const [data, setData] = useState<HomepageData | null>(null);
  const [topArtists, setTopArtists] = useState<ArtistItem[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiClient.get<HomepageData>("/api/homepage").catch(() => null),
      apiClient.get<ArtistItem[]>("/api/artists").catch(() => ({ data: [] })),
      apiClient.get<ActivityItem[]>("/api/activity?limit=8").catch(() => ({ data: [] })),
    ]).then(([homepageRes, artistsRes, activityRes]) => {
      if (cancelled) return;
      if (homepageRes) setData(homepageRes.data);
      else setError(true);
      setTopArtists((artistsRes as any)?.data?.slice(0, 5) || []);
      setActivity((activityRes as any)?.data || []);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  const artOfTheDay = data?.art_of_the_day ?? null;
  const stats = data?.stats ?? defaultStats;
  const wallsChanged = data?.walls_changed ?? [];
  const recentDiscoveries = data?.recent_discoveries ?? [];
  const neighborhoods = data?.neighborhoods ?? [];
  const mysteriesCount = data?.mysteries_count ?? 0;
  const topContributors = data?.top_contributors ?? [];
  const topArtworks = data?.top_artworks ?? [];

  return (
    <div className="homepage">
      <Helmet>
        <title>DuvarSanat — Istanbul Street Art Archive</title>
        <meta name="description" content="Discover, document, and preserve Istanbul's street art. A living archive of murals, graffiti, and urban art." />
        <meta property="og:title" content="DuvarSanat — Istanbul Street Art Archive" />
      </Helmet>
      {/* Section 1: Hero Banner */}
      <section
        className="hp-hero"
        style={
          artOfTheDay?.photo_url
            ? { backgroundImage: `url(${artOfTheDay.photo_url})` }
            : undefined
        }
      >
        <div className="hp-hero-overlay" />
        <div className="hp-hero-content">
          {artOfTheDay ? (
            <>
              <span className="hp-hero-badge">WALL ART OF THE DAY</span>
              <h1 className="hp-hero-title">
                {artOfTheDay.title || "Untitled"}
              </h1>
              <p className="hp-hero-artist">
                {artOfTheDay.artist_name || "Artist Unknown"}
              </p>
              <Link
                to={`/artworks/${artOfTheDay.artwork_id}`}
                className="btn btn-accent"
              >
                Explore This Wall
              </Link>
            </>
          ) : (
            <>
              <h1 className="hp-hero-title">
                Discover Istanbul's Street Art
              </h1>
              <p className="hp-hero-artist">
                A living archive of murals, graffiti, and urban art
              </p>
              <Link to="/explore" className="btn btn-accent">
                Start Exploring
              </Link>
            </>
          )}
        </div>
      </section>

      {/* Section 2: Stats Ticker */}
      <section className="hp-stats">
        <div className="hp-stats-inner">
          <div className="hp-stat-box">
            <span className="hp-stat-value">{stats.total_artworks}</span>
            <span className="hp-stat-label">Artworks Cataloged</span>
          </div>
          <div className="hp-stat-box">
            <span className="hp-stat-value">{stats.total_photos}</span>
            <span className="hp-stat-label">Photos</span>
          </div>
          <div className="hp-stat-box">
            <span className="hp-stat-value">{stats.total_artists}</span>
            <span className="hp-stat-label">Artists</span>
          </div>
          <div className="hp-stat-box">
            <span className="hp-stat-value">
              {stats.walls_changed_this_week}
            </span>
            <span className="hp-stat-label">Walls Changed This Week</span>
          </div>
        </div>
      </section>

      {/* Main body: content + sidebar */}
      <div className="hp-body">
        <div className="hp-main">
          {/* Walls That Changed */}
          <section className="hp-section">
            <h2 className="hp-section-title">Walls That Changed This Week</h2>
            {wallsChanged.length > 0 ? (
              <div className="hp-walls-scroll">
                {wallsChanged.map((wall) => (
                  <Link key={wall.artwork_id} to={`/artworks/${wall.artwork_id}`} className="hp-wall-card">
                    <div className="hp-wall-images">
                      {wall.oldest_photo_url && wall.newest_photo_url && wall.oldest_photo_url !== wall.newest_photo_url ? (
                        <>
                          <img src={wall.oldest_photo_url} alt="Before" className="hp-wall-img" loading="lazy" />
                          <img src={wall.newest_photo_url} alt="After" className="hp-wall-img" loading="lazy" />
                        </>
                      ) : (
                        <img src={wall.newest_photo_url || wall.oldest_photo_url || ""} alt={wall.title || "Artwork"} className="hp-wall-img hp-wall-img-full" loading="lazy" />
                      )}
                    </div>
                    <div className="hp-wall-info">
                      <span className="hp-wall-title">{wall.title || "Untitled"}</span>
                      <span className="hp-wall-artist">{wall.artist_name || "Unknown artist"}</span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="hp-empty">No walls changed this week.</p>
            )}
          </section>

          {/* CTAs side by side */}
          <div className="hp-ctas-row">
            {mysteriesCount > 0 && (
              <div className="hp-cta-card hp-cta-mysteries">
                <h3>{mysteriesCount} artworks have unknown artists</h3>
                <Link to="/explore?unattributed=true" className="btn btn-accent">Help Identify</Link>
              </div>
            )}
            <div className="hp-cta-card hp-cta-upload">
              <h3>Got your camera ready?</h3>
              <p>Document Istanbul's street art before it disappears.</p>
              <Link to="/upload" className="btn btn-accent">Upload Your Discovery</Link>
            </div>
          </div>

          {/* Neighborhoods */}
          {neighborhoods.length > 0 && (
            <section className="hp-section">
              <h2 className="hp-section-title">Discover by Neighborhood</h2>
              <div className="hp-neighborhoods-grid">
                {neighborhoods.map((n) => (
                  <Link key={n.id} to={`/explore?neighborhood=${n.slug}`} className="hp-neighborhood-card">
                    <span className="hp-neighborhood-name">{n.name}</span>
                    <span className="hp-neighborhood-count">
                      {n.artwork_count > 0 ? `${n.artwork_count} artworks` : "Explore"}
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* Recently Discovered */}
          {recentDiscoveries.length > 0 && (
            <section className="hp-section">
              <h2 className="hp-section-title">Recently Discovered</h2>
              <div className="hp-recent-grid">
                {recentDiscoveries.map((d) => (
                  <Link key={d.id} to={`/artworks/${d.id}`} className="hp-recent-card">
                    {d.thumbnail_url ? (
                      <img src={d.thumbnail_url} alt={d.title || "Artwork"} className="hp-recent-img" loading="lazy" />
                    ) : (
                      <div className="hp-recent-img hp-recent-img-empty" />
                    )}
                    <div className="hp-recent-info">
                      <span className="hp-recent-title">{d.title || "Untitled"}</span>
                      <span className="hp-recent-artist">{d.artist_name || "Unknown artist"}</span>
                      <FavoriteButton artworkId={d.id} className="favorite-btn-card" />
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

        </div>

        {/* Left Sidebar: Activity Feed */}
        <aside className="hp-sidebar-left">
          {activity.length > 0 && (
            <div className="hp-sidebar-section">
              <h3 className="hp-sidebar-title">Recent Activity</h3>
              <div className="hp-activity-list">
                {activity.map((item) => (
                  <div key={item.id} className="hp-activity-item">
                    {item.image_url && (
                      <img src={item.image_url} alt="" className="hp-activity-thumb" loading="lazy" />
                    )}
                    <div className="hp-activity-info">
                      <span className="hp-activity-text">{activityLabel(item)}</span>
                      {item.type === "comment" && item.content && (
                        <span className="hp-activity-comment">"{item.content.slice(0, 100)}"</span>
                      )}
                      <span className="hp-activity-time">{timeAgo(item.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Right Sidebar */}
        <aside className="hp-sidebar">
          {topContributors.length > 0 && (
            <div className="hp-sidebar-section">
              <h3 className="hp-sidebar-title">Top Contributors</h3>
              <div className="hp-contributors-list">
                {topContributors.slice(0, 5).map((c, idx) => {
                  const avatar = getInitialsAvatar(c.display_name);
                  return (
                    <Link key={c.user_id} to={`/users/${c.user_id}`} className="hp-contributor-row">
                      <span className="hp-contributor-rank">#{idx + 1}</span>
                      <div className="hp-contributor-avatar" style={{ background: c.avatar_url ? "transparent" : avatar.color, overflow: "hidden" }}>
                        {c.avatar_url ? (
                          <img src={c.avatar_url} alt="" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                        ) : (
                          avatar.initial
                        )}
                      </div>
                      <div className="hp-contributor-info">
                        <span className="hp-contributor-name">{c.display_name}</span>
                        <span className="hp-contributor-stats">{c.photo_count} photos</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {topArtists.length > 0 && (
            <div className="hp-sidebar-section">
              <h3 className="hp-sidebar-title">Top Artists</h3>
              <div className="hp-contributors-list">
                {topArtists.map((a, idx) => {
                  const avatar = getInitialsAvatar(a.name);
                  return (
                    <Link key={a.id} to={`/artists/${a.id}`} className="hp-contributor-row">
                      <span className="hp-contributor-rank">#{idx + 1}</span>
                      <div className="hp-contributor-avatar" style={{ background: avatar.color }}>{avatar.initial}</div>
                      <div className="hp-contributor-info">
                        <span className="hp-contributor-name">{a.name}</span>
                        <span className="hp-contributor-stats">{a.artwork_count} artworks</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {topArtworks.length > 0 && (
            <div className="hp-sidebar-section">
              <h3 className="hp-sidebar-title">Top Artworks</h3>
              <div className="hp-contributors-list">
                {topArtworks.map((a, idx) => (
                  <Link key={a.id} to={`/artworks/${a.id}`} className="hp-contributor-row">
                    <span className="hp-contributor-rank">#{idx + 1}</span>
                    {a.thumbnail_url ? (
                      <img src={a.thumbnail_url} alt="" className="hp-artwork-thumb" />
                    ) : (
                      <div className="hp-artwork-thumb hp-artwork-thumb-empty" />
                    )}
                    <div className="hp-contributor-info">
                      <span className="hp-contributor-name">{a.title || "Untitled"}</span>
                      <span className="hp-contributor-stats">{a.total_votes} votes</span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Show a subtle message if API failed */}
      {error && !data && (
        <div className="hp-section" style={{ textAlign: "center" }}>
          <p className="hp-empty">
            Could not load homepage data. The server may be starting up.
          </p>
          <Link to="/explore" className="btn btn-accent" style={{ marginTop: "1rem" }}>
            Explore the Map
          </Link>
        </div>
      )}
    </div>
  );
}

export default HomePage;
