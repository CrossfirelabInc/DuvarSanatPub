import { useState, useRef } from "react";

interface SearchResult {
  display_name: string;
  lat: string;
  lon: string;
}

interface MapSearchBoxProps {
  onSelect: (lat: number, lng: number) => void;
  placeholder?: string;
}

function MapSearchBox({ onSelect, placeholder = "Search street or address..." }: MapSearchBoxProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(value: string) {
    setQuery(value);

    if (timerRef.current) clearTimeout(timerRef.current);

    if (value.trim().length < 3) {
      setResults([]);
      setOpen(false);
      return;
    }

    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(value)}&countrycodes=tr&limit=5&addressdetails=1`,
          { headers: { "Accept-Language": "en" } }
        );
        const data: SearchResult[] = await res.json();
        setResults(data);
        setOpen(data.length > 0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 400);
  }

  function handleSelect(result: SearchResult) {
    const lat = parseFloat(result.lat);
    const lng = parseFloat(result.lon);
    onSelect(lat, lng);
    setQuery(result.display_name.split(",").slice(0, 2).join(","));
    setOpen(false);
  }

  return (
    <div className="map-search-box">
      <input
        type="text"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder={placeholder}
        className="map-search-input"
      />
      {loading && <span className="map-search-spinner" />}
      {open && results.length > 0 && (
        <div className="map-search-dropdown">
          {results.map((r, i) => (
            <button
              key={i}
              className="map-search-item"
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(r);
              }}
            >
              {r.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default MapSearchBox;
