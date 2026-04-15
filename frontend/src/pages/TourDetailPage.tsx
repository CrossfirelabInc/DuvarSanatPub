import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import apiClient from "../api/client";

// Fix default marker icons for bundled builds
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

interface TourStop {
  stop_order: number;
  artwork_id: string;
  artwork_title: string | null;
  thumbnail_url: string | null;
  latitude: number;
  longitude: number;
  distance_from_previous_m: number;
}

interface TourDetail {
  id: string;
  title: string;
  description: string | null;
  stops: TourStop[];
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters}m`;
  return `${(meters / 1000).toFixed(1)}km`;
}

function getTotalDistance(stops: TourStop[]): number {
  return stops.reduce((sum, s) => sum + s.distance_from_previous_m, 0);
}

function estimateMinutes(stops: TourStop[]): number {
  // Rough walking speed ~5km/h = 83m/min, plus 2min per stop for viewing
  const totalM = getTotalDistance(stops);
  return Math.round(totalM / 83 + stops.length * 2);
}

function TourDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tour, setTour] = useState<TourDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    apiClient
      .get<TourDetail>(`/api/tours/${id}`)
      .then((res) => setTour(res.data))
      .catch(() => setError("Failed to load tour details."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  if (error || !tour) {
    return (
      <div className="page">
        <div className="profile-error">
          <h1>Tour Not Found</h1>
          <p>{error || "This tour could not be loaded."}</p>
          <Link to="/tours" className="btn btn-primary">
            Back to Tours
          </Link>
        </div>
      </div>
    );
  }

  const sortedStops = [...tour.stops].sort((a, b) => a.stop_order - b.stop_order);
  const positions: [number, number][] = sortedStops.map((s) => [s.latitude, s.longitude]);
  const totalDist = getTotalDistance(sortedStops);
  const estMin = estimateMinutes(sortedStops);

  // Map center: average of all stop positions
  const centerLat = positions.reduce((s, p) => s + p[0], 0) / (positions.length || 1);
  const centerLng = positions.reduce((s, p) => s + p[1], 0) / (positions.length || 1);

  return (
    <div className="page tour-detail">
      <Link to="/tours" className="tour-back-link">
        {"\u2190"} All Tours
      </Link>

      <h1 className="tour-detail-title">{tour.title}</h1>
      {tour.description && (
        <p className="tour-detail-desc">{tour.description}</p>
      )}

      <div className="tour-detail-stats">
        <span className="tour-stat">{sortedStops.length} stops</span>
        <span className="tour-stat">{formatDistance(totalDist)}</span>
        <span className="tour-stat">~{estMin} min</span>
      </div>

      {/* Map */}
      {positions.length > 0 && (
        <div className="tour-map">
          <MapContainer
            center={[centerLat, centerLng]}
            zoom={14}
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom={false}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />
            {sortedStops.map((stop) => (
              <Marker
                key={stop.artwork_id}
                position={[stop.latitude, stop.longitude]}
              />
            ))}
            <Polyline positions={positions} color="#2e7d32" weight={3} opacity={0.7} />
          </MapContainer>
        </div>
      )}

      {/* Stop list */}
      <div className="tour-stops-list">
        {sortedStops.map((stop, idx) => (
          <div key={stop.artwork_id} className="tour-stop">
            <div className="tour-stop-number">{stop.stop_order}</div>
            <div className="tour-stop-content">
              {stop.thumbnail_url && (
                <img
                  className="tour-stop-thumb"
                  src={stop.thumbnail_url}
                  alt={stop.artwork_title || "Artwork"}
                />
              )}
              <div className="tour-stop-info">
                <Link
                  to={`/artworks/${stop.artwork_id}`}
                  className="tour-stop-title"
                >
                  {stop.artwork_title || "Untitled Artwork"}
                </Link>
                {idx < sortedStops.length - 1 && stop.distance_from_previous_m > 0 && (
                  <span className="tour-stop-distance">
                    {formatDistance(sortedStops[idx + 1]?.distance_from_previous_m ?? 0)} to next stop
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Placeholder Start Tour button */}
      <button className="btn btn-tour-start" disabled>
        Start Tour (Coming Soon)
      </button>
    </div>
  );
}

export default TourDetailPage;
