import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import App from "../App";
import apiClient from "../api/client";
import type { Mock } from "vitest";

const mockGet = apiClient.get as Mock;

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("ArtistProfilePage", () => {
  it("shows loading state initially", () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      // Never resolve the artist request
      return new Promise(() => {});
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-1"] },
    });

    expect(screen.getByText("Loading artist...")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      return Promise.reject(new Error("Server error"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Artist Not Found")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/failed to load artist/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Back to Map")).toBeInTheDocument();
  });

  it("renders artist name and bio", async () => {
    const artistData = {
      id: "artist-1",
      name: "Banksy",
      bio: "Anonymous England-based street artist",
      artwork_count: 2,
      artworks: [
        {
          id: "aw-1",
          title: "Girl with Balloon",
          status: "active",
          thumbnail_url: "http://example.com/thumb1.jpg",
        },
        {
          id: "aw-2",
          title: "Flower Thrower",
          status: "gone",
          thumbnail_url: null,
        },
      ],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/artists/artist-1") {
        return Promise.resolve({ data: artistData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Banksy")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Anonymous England-based street artist")
    ).toBeInTheDocument();
    expect(screen.getByText("Artworks")).toBeInTheDocument();
  });

  it("renders artwork grid with correct links", async () => {
    const artistData = {
      id: "artist-1",
      name: "Banksy",
      bio: null,
      artwork_count: 1,
      artworks: [
        {
          id: "aw-1",
          title: "Girl with Balloon",
          status: "active",
          thumbnail_url: "http://example.com/thumb1.jpg",
        },
      ],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/artists/artist-1") {
        return Promise.resolve({ data: artistData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Girl with Balloon")).toBeInTheDocument();
    });

    const artworkLink = screen.getByText("Girl with Balloon").closest("a");
    expect(artworkLink).toHaveAttribute("href", "/artworks/aw-1");
  });

  it("shows empty state when artist has no artworks", async () => {
    const artistData = {
      id: "artist-2",
      name: "Unknown Artist",
      bio: null,
      artwork_count: 0,
      artworks: [],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/artists/artist-2") {
        return Promise.resolve({ data: artistData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-2"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Unknown Artist")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/no artworks linked to this artist/i)
    ).toBeInTheDocument();
  });

  it("shows artwork count with correct pluralization", async () => {
    const artistData = {
      id: "artist-1",
      name: "Solo Artist",
      bio: null,
      artwork_count: 1,
      artworks: [
        { id: "aw-1", title: "One Piece", status: "active", thumbnail_url: null },
      ],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/artists/artist-1") {
        return Promise.resolve({ data: artistData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/artists/artist-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Artwork")).toBeInTheDocument();
    });
  });
});
