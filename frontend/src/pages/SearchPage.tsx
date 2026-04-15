import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import apiClient from "../api/client";

interface SearchArtwork {
  id: string;
  title: string | null;
  thumbnail_url: string | null;
  status: string;
  artist_name: string | null;
}

interface SearchArtist {
  id: string;
  name: string;
  artwork_count: number;
}

interface SearchResponse {
  artworks: SearchArtwork[];
  artists: SearchArtist[];
}

const STATUS_COLORS: Record<string, string> = {
  active: "#27ae60",
  modified: "#f39c12",
  gone: "#e74c3c",
};

function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";

  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      return;
    }

    setLoading(true);
    setError("");

    apiClient
      .get<SearchResponse>("/api/search", { params: { q: query } })
      .then((res) => {
        setResults(res.data);
      })
      .catch(() => {
        setError("Search failed. Please try again.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [query]);

  const hasArtworks = results && results.artworks.length > 0;
  const hasArtists = results && results.artists.length > 0;
  const hasResults = hasArtworks || hasArtists;

  return (
    <div className="page search-page">
      <Helmet>
        <title>{query ? `"${query}" — Search — DuvarSanat` : "Search — DuvarSanat"}</title>
      </Helmet>
      <h1>Search</h1>

      {!query.trim() && (
        <p className="search-prompt">
          Enter a search term to find artworks and artists.
        </p>
      )}

      {loading && <div className="loading">Searching...</div>}

      {error && <p className="search-error">{error}</p>}

      {query.trim() && !loading && !error && results && !hasResults && (
        <p className="search-empty">
          No results found for &ldquo;{query}&rdquo;
        </p>
      )}

      {hasArtworks && (
        <section className="search-section">
          <h2 className="search-section-title">Artworks</h2>
          <div className="search-results-list">
            {results!.artworks.map((aw) => {
              const statusColor =
                STATUS_COLORS[aw.status] || STATUS_COLORS.active;
              return (
                <Link
                  key={aw.id}
                  to={`/artworks/${aw.id}`}
                  className="search-result-card"
                >
                  {aw.thumbnail_url ? (
                    <img
                      src={aw.thumbnail_url}
                      alt={aw.title || "Artwork"}
                      className="search-result-thumb"
                    />
                  ) : (
                    <div className="search-result-thumb search-result-thumb-empty" />
                  )}
                  <div className="search-result-info">
                    <span className="search-result-title">
                      {aw.title || "Untitled"}
                    </span>
                    {aw.artist_name && (
                      <span className="search-result-artist">
                        by {aw.artist_name}
                      </span>
                    )}
                  </div>
                  <span
                    className="artwork-status-badge"
                    style={{ background: statusColor }}
                  >
                    {aw.status}
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {hasArtists && (
        <section className="search-section">
          <h2 className="search-section-title">Artists</h2>
          <div className="search-results-list">
            {results!.artists.map((artist) => (
              <Link
                key={artist.id}
                to={`/artists/${artist.id}`}
                className="search-result-card"
              >
                <div className="search-result-artist-avatar">
                  {artist.name[0]?.toUpperCase() || "?"}
                </div>
                <div className="search-result-info">
                  <span className="search-result-title">{artist.name}</span>
                  <span className="search-result-artist">
                    {artist.artwork_count} artwork
                    {artist.artwork_count !== 1 ? "s" : ""}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default SearchPage;
