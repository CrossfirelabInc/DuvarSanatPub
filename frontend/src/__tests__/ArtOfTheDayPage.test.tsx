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

describe("ArtOfTheDayPage", () => {
  it("shows loading state", () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      return new Promise(() => {});
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/art-of-the-day"] },
    });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders empty state when no data", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      if (url === "/api/art-of-the-day") return Promise.resolve({ data: null });
      if (url.startsWith("/api/art-of-the-day/history")) return Promise.resolve({ data: [] });
      return Promise.reject(new Error("unexpected: " + url));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/art-of-the-day"] },
    });

    await waitFor(() => {
      expect(screen.getByText(/no featured artworks yet/i)).toBeInTheDocument();
    });
  });

  it("renders today's pick and history", async () => {
    const todayData = {
      artwork_id: "aw-1",
      title: "Today's Mural",
      artist_name: "Street Artist",
      description: "A beautiful piece",
      photo_url: "/uploads/today.jpg",
      featured_date: "2026-04-01",
      photo_count: 3,
    };
    const historyData = [
      {
        artwork_id: "aw-2",
        title: "Yesterday's Art",
        artist_name: null,
        thumbnail_url: "/uploads/thumb.jpg",
        featured_date: "2026-03-31",
      },
    ];

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      if (url === "/api/art-of-the-day") return Promise.resolve({ data: todayData });
      if (url.startsWith("/api/art-of-the-day/history")) return Promise.resolve({ data: historyData });
      return Promise.reject(new Error("unexpected: " + url));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/art-of-the-day"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Today's Mural")).toBeInTheDocument();
    });
    expect(screen.getByText("by Street Artist")).toBeInTheDocument();
    expect(screen.getByText("Yesterday's Art")).toBeInTheDocument();
  });
});
