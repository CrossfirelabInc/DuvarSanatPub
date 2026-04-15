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

describe("UserProfilePage", () => {
  it("shows loading state initially", () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      // Never resolve user profile
      return new Promise(() => {});
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-1"] },
    });

    expect(screen.getByText("Loading profile...")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      return Promise.reject(new Error("Server error"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("User Not Found")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/failed to load user profile/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Back to Map")).toBeInTheDocument();
  });

  it("renders user profile with display name and stats", async () => {
    const profileData = {
      display_name: "StreetArtFan",
      bio: "I love discovering street art",
      created_at: "2024-06-15T10:00:00Z",
      total_photos: 25,
      total_artworks: 12,
      photos: [],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/users/user-1/profile") {
        return Promise.resolve({ data: profileData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-1"] },
    });

    await waitFor(() => {
      expect(screen.getByText("StreetArtFan")).toBeInTheDocument();
    });

    expect(
      screen.getByText("I love discovering street art")
    ).toBeInTheDocument();
    expect(screen.getByText(/25 photos uploaded/)).toBeInTheDocument();
    expect(screen.getByText(/12 artworks cataloged/)).toBeInTheDocument();
    expect(screen.getByText(/member since/i)).toBeInTheDocument();
  });

  it("shows empty state when user has no photos", async () => {
    const profileData = {
      display_name: "NewUser",
      bio: null,
      created_at: "2025-01-01T00:00:00Z",
      total_photos: 0,
      total_artworks: 0,
      photos: [],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/users/user-2/profile") {
        return Promise.resolve({ data: profileData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-2"] },
    });

    await waitFor(() => {
      expect(screen.getByText("NewUser")).toBeInTheDocument();
    });

    expect(screen.getByText("No photos uploaded yet.")).toBeInTheDocument();
  });

  it("renders photo grid with links to artworks", async () => {
    const profileData = {
      display_name: "Photographer",
      bio: null,
      created_at: "2024-03-01T00:00:00Z",
      total_photos: 2,
      total_artworks: 1,
      photos: [
        {
          id: "p1",
          image_url: "http://example.com/photo1.jpg",
          artwork_id: "aw-5",
          date_uploaded: "2024-06-10T00:00:00Z",
        },
        {
          id: "p2",
          image_url: "http://example.com/photo2.jpg",
          artwork_id: null,
          date_uploaded: "2024-07-20T00:00:00Z",
        },
      ],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/users/user-3/profile") {
        return Promise.resolve({ data: profileData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-3"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Photographer")).toBeInTheDocument();
    });

    // Photo linked to artwork should be a link
    const images = screen.getAllByAltText("Uploaded photo");
    expect(images).toHaveLength(2);

    // First photo has artwork_id so it should be wrapped in a link
    const linkedCard = images[0].closest("a");
    expect(linkedCard).toHaveAttribute("href", "/artworks/aw-5");

    // Second photo has no artwork_id so it should NOT be a link
    const unlinkedCard = images[1].closest("a");
    expect(unlinkedCard).toBeNull();
  });

  it("shows correct pluralization for 1 photo and 1 artwork", async () => {
    const profileData = {
      display_name: "OneOfEach",
      bio: null,
      created_at: "2025-01-01T00:00:00Z",
      total_photos: 1,
      total_artworks: 1,
      photos: [],
    };

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.reject(new Error("not authenticated"));
      }
      if (url === "/api/users/user-4/profile") {
        return Promise.resolve({ data: profileData });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/users/user-4"] },
    });

    await waitFor(() => {
      expect(screen.getByText("OneOfEach")).toBeInTheDocument();
    });

    expect(screen.getByText(/1 photo uploaded/)).toBeInTheDocument();
    expect(screen.getByText(/1 artwork cataloged/)).toBeInTheDocument();
  });
});
