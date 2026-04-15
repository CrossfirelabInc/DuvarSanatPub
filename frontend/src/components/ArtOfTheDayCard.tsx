import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";

interface ArtOfTheDay {
  artwork_id: string;
  title: string | null;
  artist_name: string | null;
  photo_url: string | null;
  featured_date: string;
}

const DISMISSED_KEY = "duvarsanat_aotd_dismissed";

function ArtOfTheDayCard() {
  const [data, setData] = useState<ArtOfTheDay | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem(DISMISSED_KEY);
    if (stored === new Date().toISOString().slice(0, 10)) {
      setCollapsed(true);
    }

    apiClient
      .get<ArtOfTheDay>("/api/art-of-the-day")
      .then((res) => {
        if (res.data) setData(res.data);
      })
      .catch(() => {});
  }, []);

  if (!data) return null;

  if (collapsed) {
    return (
      <button className="aotd-chip" onClick={() => setCollapsed(false)}>
        Today's Pick
      </button>
    );
  }

  function handleDismiss() {
    sessionStorage.setItem(DISMISSED_KEY, new Date().toISOString().slice(0, 10));
    setCollapsed(true);
  }

  return (
    <div className="aotd-card">
      <div className="aotd-header">
        <span className="aotd-label">Art of the Day</span>
        <button className="aotd-close" onClick={handleDismiss} aria-label="Dismiss">
          &times;
        </button>
      </div>
      {data.photo_url && (
        <img src={data.photo_url} alt={data.title || "Featured artwork"} className="aotd-img" />
      )}
      <div className="aotd-body">
        <strong className="aotd-title">{data.title || "Untitled"}</strong>
        <span className="aotd-artist">
          {data.artist_name ? `by ${data.artist_name}` : "Anonymous"}
        </span>
        <Link to={`/artworks/${data.artwork_id}`} className="btn btn-primary aotd-link">
          View Artwork
        </Link>
      </div>
    </div>
  );
}

export default ArtOfTheDayCard;
