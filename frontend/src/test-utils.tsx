import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import type { ReactElement, ReactNode } from "react";

// Mock apiClient before anything imports it
vi.mock("./api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

// Mock leaflet and react-leaflet globally so map-heavy pages don't crash in jsdom
vi.mock("leaflet", () => {
  const L = {
    map: vi.fn(),
    tileLayer: vi.fn(),
    marker: vi.fn(() => ({
      bindPopup: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
    })),
    icon: vi.fn(),
    divIcon: vi.fn(() => ({})),
    latLngBounds: vi.fn(() => ({
      getSouth: () => 0,
      getWest: () => 0,
      getNorth: () => 1,
      getEast: () => 1,
    })),
    Icon: { Default: { mergeOptions: vi.fn() } },
    markerClusterGroup: vi.fn(() => ({
      addLayer: vi.fn(),
      clearLayers: vi.fn(),
      removeFrom: vi.fn(),
      addTo: vi.fn(),
    })),
  };
  return { default: L, ...L };
});

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children }: { children: ReactNode }) => (
    <div data-testid="marker">{children}</div>
  ),
  Popup: ({ children }: { children: ReactNode }) => (
    <div data-testid="popup">{children}</div>
  ),
  Polyline: () => <div data-testid="polyline" />,
  useMap: () => ({
    getBounds: () => ({
      getSouth: () => 0,
      getWest: () => 0,
      getNorth: () => 1,
      getEast: () => 1,
    }),
    on: vi.fn(),
    off: vi.fn(),
    setView: vi.fn(),
    flyTo: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
  }),
  useMapEvents: vi.fn(() => ({
    getBounds: () => ({
      getSouth: () => 0,
      getWest: () => 0,
      getNorth: () => 1,
      getEast: () => 1,
    }),
    on: vi.fn(),
    off: vi.fn(),
    setView: vi.fn(),
    flyTo: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
  })),
}));

vi.mock("leaflet.markercluster", () => ({}));

// Mock react-helmet-async so Helmet renders nothing in tests
vi.mock("react-helmet-async", () => ({
  Helmet: () => null,
  HelmetProvider: ({ children }: { children?: ReactNode }) => <>{children}</>,
}));

// CSS imports should be noops in tests
vi.mock("leaflet/dist/leaflet.css", () => ({}));
vi.mock("leaflet.markercluster/dist/MarkerCluster.css", () => ({}));
vi.mock("leaflet.markercluster/dist/MarkerCluster.Default.css", () => ({}));

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  routerProps?: MemoryRouterProps;
  /** If true, skip AuthProvider wrapping (for testing AuthProvider itself) */
  skipAuth?: boolean;
}

/**
 * Custom render that wraps components in MemoryRouter + AuthProvider.
 * Use routerProps.initialEntries to control the starting URL.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {}
) {
  const { routerProps, skipAuth, ...renderOptions } = options;

  function Wrapper({ children }: { children: ReactNode }) {
    const inner = <MemoryRouter {...routerProps}>{children}</MemoryRouter>;
    return skipAuth ? inner : <AuthProvider>{inner}</AuthProvider>;
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export { render };
