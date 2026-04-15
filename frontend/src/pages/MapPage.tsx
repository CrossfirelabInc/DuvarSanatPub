import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import ArtOfTheDayCard from "../components/ArtOfTheDayCard";
import MapSearchBox from "../components/MapSearchBox";


function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


interface ArtworkMarker {
  id: string;
  title: string | null;
  status: "active" | "modified" | "gone";
  latitude: number;
  longitude: number;
  photo_count: number;
  thumbnail_url: string | null;
}


function createStatusIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "artwork-marker",
    html: `<span class="marker-dot" style="background:${color}"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
}

const STATUS_ICONS: Record<string, L.DivIcon> = {
  active: createStatusIcon("#27ae60"),
  modified: createStatusIcon("#f39c12"),
  gone: createStatusIcon("#e74c3c"),
};


function useDebouncedCallback<T extends (...args: never[]) => void>(
  fn: T,
  delay: number
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return useMemo(() => {
    const debounced = (...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => fnRef.current(...args), delay);
    };
    return debounced as unknown as T;
  }, [delay]);
}


function MarkerClusterGroup({
  artworks,
  onArtworkClick,
}: {
  artworks: ArtworkMarker[];
  onArtworkClick: (id: string) => void;
}) {
  const map = useMap();
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null);

  useEffect(() => {
    if (!clusterRef.current) {
      clusterRef.current = L.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
      });
      map.addLayer(clusterRef.current);
    }

    const cluster = clusterRef.current;
    cluster.clearLayers();

    for (const aw of artworks) {
      const icon = STATUS_ICONS[aw.status] || STATUS_ICONS.active;
      const marker = L.marker([aw.latitude, aw.longitude], { icon });

      const safeThumbUrl = aw.thumbnail_url ? escapeHtml(aw.thumbnail_url) : "";
      const imgHtml = safeThumbUrl
        ? `<img class="popup-img-lg" src="${safeThumbUrl}" alt="" />`
        : `<div class="popup-img-lg-empty"></div>`;

      const safeTitle = escapeHtml(aw.title || "Untitled");
      const safeId = escapeHtml(aw.id);
      const statusLabels: Record<string, string> = { active: "Still There", modified: "Changed", gone: "Painted Over" };
      const safeStatus = escapeHtml(statusLabels[aw.status] || aw.status);

      marker.bindPopup(
        `<div class="popup-content-lg">
          ${imgHtml}
          <div class="popup-info-lg">
            <strong class="popup-title-lg">${safeTitle}</strong>
            <span class="popup-meta-lg">${aw.photo_count} photo${aw.photo_count !== 1 ? "s" : ""} &middot; ${safeStatus}</span>
            <a class="popup-link-lg" data-artwork-id="${safeId}">View Full Page &rarr;</a>
          </div>
        </div>`,
        { className: "artwork-popup", minWidth: 280 }
      );

      marker.on("popupopen", () => {
        // Attach click handler to the "View" link inside the popup
        const link = document.querySelector(
          `a[data-artwork-id="${aw.id}"]`
        );
        if (link) {
          link.addEventListener("click", () => onArtworkClick(aw.id));
        }
      });

      cluster.addLayer(marker);
    }

    return () => {
      cluster.clearLayers();
    };
  }, [artworks, map, onArtworkClick]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (clusterRef.current) {
        map.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }
    };
  }, [map]);

  return null;
}


function MapBoundsListener({
  onBoundsChange,
}: {
  onBoundsChange: (bounds: L.LatLngBounds) => void;
}) {
  const map = useMapEvents({
    moveend() {
      onBoundsChange(map.getBounds());
    },
    zoomend() {
      onBoundsChange(map.getBounds());
    },
  });

  // Fire on initial load
  useEffect(() => {
    onBoundsChange(map.getBounds());
  }, [map, onBoundsChange]);

  return null;
}


function FlyToHandler({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) {
      map.flyTo(target, 16);
    }
  }, [target, map]);
  return null;
}


function MyLocationButton() {
  const map = useMap();
  const [locating, setLocating] = useState(false);

  function handleClick() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        map.flyTo([pos.coords.latitude, pos.coords.longitude], 16);
        setLocating(false);
      },
      () => {
        alert("Unable to retrieve your location.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  return (
    <button
      className="my-location-btn"
      onClick={handleClick}
      disabled={locating}
      title="Go to my location"
      aria-label="Go to my location"
    >
      {locating ? "..." : "\u2316"}
    </button>
  );
}


const ISTANBUL_CENTER: L.LatLngTuple = [41.0082, 28.9784];
const DEFAULT_ZOOM = 13;

function MapPage() {
  const [artworks, setArtworks] = useState<ArtworkMarker[]>([]);
  const [unattributed, setUnattributed] = useState(false);
  const [searchTarget, setSearchTarget] = useState<[number, number] | null>(null);
  const [unattributedCount, setUnattributedCount] = useState<number | null>(null);
  const navigate = useNavigate();
  const abortRef = useRef<AbortController | null>(null);
  const lastBoundsRef = useRef<L.LatLngBounds | null>(null);

  // Fetch platform stats once on mount
  useEffect(() => {
    apiClient
      .get<{ artworks_without_artist: number }>("/api/artworks/stats")
      .then((res) => setUnattributedCount(res.data.artworks_without_artist))
      .catch(() => {}); // non-critical
  }, []);

  const fetchArtworks = useCallback(async (bounds: L.LatLngBounds, showUnattributed: boolean) => {
    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const s = bounds.getSouth();
    const w = bounds.getWest();
    const n = bounds.getNorth();
    const e = bounds.getEast();

    try {
      const params: Record<string, string | boolean> = { bounds: `${s},${w},${n},${e}` };
      if (showUnattributed) params.unattributed = true;

      const res = await apiClient.get<ArtworkMarker[]>("/api/artworks", {
        params,
        signal: controller.signal,
      });
      setArtworks(res.data);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      console.error("Failed to fetch artworks:", err);
    }
  }, []);

  const debouncedFetch = useDebouncedCallback(fetchArtworks, 300);

  const handleBoundsChange = useCallback(
    (bounds: L.LatLngBounds) => {
      lastBoundsRef.current = bounds;
      debouncedFetch(bounds, unattributed);
    },
    [debouncedFetch, unattributed]
  );

  // Re-fetch when unattributed toggle changes
  useEffect(() => {
    if (lastBoundsRef.current) {
      fetchArtworks(lastBoundsRef.current, unattributed);
    }
  }, [unattributed, fetchArtworks]);

  const handleArtworkClick = useCallback(
    (id: string) => {
      navigate(`/artworks/${id}`);
    },
    [navigate]
  );

  return (
    <div className="map-wrapper">
      {unattributedCount !== null && unattributedCount > 0 && (
        <button
          className={`map-stats-bar ${unattributed ? "map-stats-bar--active" : ""}`}
          onClick={() => setUnattributed((v) => !v)}
        >
          {unattributed
            ? `Showing ${artworks.length} unattributed artworks — click to show all`
            : `${unattributedCount} artworks need artist identification — click to filter`}
        </button>
      )}
      <ArtOfTheDayCard />
      <div className="map-search-overlay">
        <MapSearchBox
          onSelect={(lat, lng) => setSearchTarget([lat, lng])}
          placeholder="Search street or address..."
        />
      </div>
      <MapContainer
        center={ISTANBUL_CENTER}
        zoom={DEFAULT_ZOOM}
        className="map-container"
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapBoundsListener onBoundsChange={handleBoundsChange} />
        <MarkerClusterGroup
          artworks={artworks}
          onArtworkClick={handleArtworkClick}
        />
        <MyLocationButton />
        <FlyToHandler target={searchTarget} />
      </MapContainer>
    </div>
  );
}

export default MapPage;
