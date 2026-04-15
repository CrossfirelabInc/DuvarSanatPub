import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import apiClient from "../api/client";

interface TourListItem {
  id: string;
  title: string;
  neighborhood_name: string | null;
  artwork_count: number;
  total_distance_m: number;
  estimated_minutes: number;
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters}m`;
  return `${(meters / 1000).toFixed(1)}km`;
}

function formatTime(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

function ToursPage() {
  const [tours, setTours] = useState<TourListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get<TourListItem[]>("/api/tours")
      .then((res) => {
        setTours(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        setError("Failed to load tours. Please try again later.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page tours-page">
      <Helmet>
        <title>Walking Tours — DuvarSanat</title>
        <meta name="description" content="Explore Istanbul's street art on foot with curated walking tours." />
      </Helmet>
      <div className="tours-header">
        <h1>Walking Tours</h1>
        <span
          className="page-type-badge"
          style={{ background: "#e8f5e9", color: "#2e7d32" }}
        >
          Tours
        </span>
      </div>
      <p className="tours-subtitle">
        Discover street art on foot with curated walking routes.
      </p>

      {loading && (
        <div className="loading">
          <div className="spinner" />
        </div>
      )}

      {error && <p className="community-error">{error}</p>}

      {!loading && !error && tours.length === 0 && (
        <div className="tours-empty">
          <p>No tours available yet. Check back soon!</p>
        </div>
      )}

      {!loading && !error && tours.length > 0 && (
        <div className="tours-grid">
          {tours.map((tour) => (
            <Link key={tour.id} to={`/tours/${tour.id}`} className="tour-card">
              <div className="tour-card-icon">{"\uD83D\uDEB6"}</div>
              <div className="tour-card-body">
                <h3 className="tour-card-title">{tour.title}</h3>
                {tour.neighborhood_name && (
                  <span className="tour-card-neighborhood">
                    {tour.neighborhood_name}
                  </span>
                )}
                <div className="tour-card-stats">
                  <span>{tour.artwork_count} stops</span>
                  <span>{formatDistance(tour.total_distance_m)}</span>
                  <span>{formatTime(tour.estimated_minutes)}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default ToursPage;
