import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import App from "../App";
import apiClient from "../api/client";
import type { Mock } from "vitest";

const mockGet = apiClient.get as Mock;

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  // AuthProvider calls /api/auth/me; HomePage calls /api/homepage; MapPage calls /api/artworks?bounds=...
  mockGet.mockImplementation((url: string) => {
    if (url.startsWith("/api/artworks")) {
      return Promise.resolve({ data: [] });
    }
    if (url === "/api/homepage") {
      return Promise.resolve({
        data: {
          art_of_the_day: null,
          stats: { total_artworks: 0, total_photos: 0, total_artists: 0, walls_changed_this_week: 0 },
          walls_changed: [],
          recent_discoveries: [],
          neighborhoods: [],
          mysteries_count: 0,
        },
      });
    }
    return Promise.reject(new Error("not authenticated"));
  });
});

describe("App routing", () => {
  it("renders the homepage at /", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    // Layout renders the brand link
    await waitFor(() => {
      expect(screen.getByText("DuvarSanat")).toBeInTheDocument();
    });
  });

  it("renders the map page at /explore", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/explore"] },
    });

    await waitFor(() => {
      expect(screen.getByText("DuvarSanat")).toBeInTheDocument();
    });
  });

  it("renders the login page at /login", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/login"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });
  });

  it("renders the register page at /register", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/register"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /create account/i })
      ).toBeInTheDocument();
    });
  });

  it("renders 404 for unknown routes", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/no-such-page"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Page Not Found")).toBeInTheDocument();
    });
    expect(screen.getByText("Back to Home")).toBeInTheDocument();
  });

  it("redirects /upload to /login when not authenticated", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/upload"] },
    });

    // Should redirect to login page
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });
  });

  it("redirects /profile to /login when not authenticated", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/profile"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });
  });
});
