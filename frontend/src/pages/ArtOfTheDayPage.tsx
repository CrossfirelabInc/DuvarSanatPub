import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";

interface HistoryItem {
  artwork_id: string;
  title: string | null;
  artist_name: string | null;
  thumbnail_url: string | null;
  featured_date: string;
}

interface TodayData {
  artwork_id: string;
  title: string | null;
  artist_name: string | null;
  description: string | null;
  photo_url: string | null;
  featured_date: string;
  photo_count: number;
}

function ArtOfTheDayPage() {
  const [today, setToday] = useState<TodayData | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiClient.get<TodayData>("/api/art-of-the-day").catch(() => ({ data: null })),
      apiClient.get<HistoryItem[]>("/api/art-of-the-day/history", { params: { limit: 30 } }).catch(() => ({ data: [] })),
    ]).then(([todayRes, historyRes]) => {
      setToday(todayRes.data);
      setHistory(historyRes.data || []);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="page">
      <h1>Art of the Day</h1>

      {today && (
        <div className="aotd-hero">
          {today.photo_url && (
            <img src={today.photo_url} alt={today.title || "Featured artwork"} className="aotd-hero-img" />
          )}
          <div className="aotd-hero-body">
            <span className="aotd-hero-date">{today.featured_date}</span>
            <h2>{today.title || "Untitled"}</h2>
            <p className="aotd-hero-artist">
              {today.artist_name ? `by ${today.artist_name}` : "Anonymous"}
            </p>
            {today.description && <p className="aotd-hero-desc">{today.description}</p>}
            <Link to={`/artworks/${today.artwork_id}`} className="btn btn-primary">
              View Artwork
            </Link>
          </div>
        </div>
      )}

      {history.length > 0 && (
        <>
          <h2 className="aotd-history-title">Previous Picks</h2>
          <div className="profile-grid">
            {history.map((item) => (
              <Link
                key={`${item.artwork_id}-${item.featured_date}`}
                to={`/artworks/${item.artwork_id}`}
                className="profile-card"
              >
                {item.thumbnail_url ? (
                  <img src={item.thumbnail_url} alt={item.title || "Artwork"} className="profile-card-img" />
                ) : (
                  <div className="profile-card-img profile-card-img-empty" />
                )}
                <div className="profile-card-body">
                  <span className="profile-card-title">{item.title || "Untitled"}</span>
                  <span className="profile-card-date">
                    {item.featured_date} &middot; {item.artist_name || "Anonymous"}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}

      {!today && history.length === 0 && (
        <p>No featured artworks yet. Check back when artworks have been uploaded!</p>
      )}
    </div>
  );
}

export default ArtOfTheDayPage;
