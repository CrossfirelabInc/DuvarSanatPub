import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";

interface ArtistItem {
  id: string;
  name: string;
  artwork_count: number;
  bio?: string | null;
  total_photos?: number;
  active_since?: string | null;
}

function getInitial(name: string): { letter: string; color: string } {
  const letter = name.charAt(0).toUpperCase();
  const colors = ["#9b59b6", "#e94560", "#27ae60", "#3498db", "#f39c12", "#1abc9c", "#e67e22", "#2c3e50"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return { letter, color: colors[Math.abs(hash) % colors.length] };
}

function ArtistsDirectoryPage() {
  const [artists, setArtists] = useState<ArtistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    apiClient
      .get<ArtistItem[]>("/api/artists")
      .then((res) => {
        setArtists(res.data || []);
      })
      .catch(() => {
        setArtists([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = searchQuery.trim()
    ? artists.filter((a) =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : artists;

  if (loading) {
    return <div className="loading">Loading artists...</div>;
  }

  return (
    <div className="page">
      <div className="directory-header">
        <span className="page-type-badge artist">Artist Directory</span>
        <h1>Street Artists of Istanbul</h1>
        <p className="directory-subtitle">
          {artists.length} artist{artists.length !== 1 ? "s" : ""} cataloged by the community
        </p>
      </div>

      <div className="directory-search">
        <input
          type="text"
          placeholder="Search artists..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="directory-search-input"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="directory-empty">
          {searchQuery ? `No artists matching "${searchQuery}"` : "No artists cataloged yet. Be the first to suggest an artist on an artwork page!"}
        </p>
      ) : (
        <div className="directory-grid">
          {filtered.map((artist) => {
            const { letter, color } = getInitial(artist.name);
            return (
              <Link
                key={artist.id}
                to={`/artists/${artist.id}`}
                className="directory-card"
              >
                <div className="directory-avatar" style={{ background: color }}>
                  {letter}
                </div>
                <div className="directory-info">
                  <strong className="directory-name">{artist.name}</strong>
                  {artist.bio && (
                    <p className="directory-bio">
                      {artist.bio.length > 80 ? artist.bio.slice(0, 80) + "..." : artist.bio}
                    </p>
                  )}
                  <span className="directory-meta">
                    {artist.artwork_count} artwork{artist.artwork_count !== 1 ? "s" : ""}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ArtistsDirectoryPage;
