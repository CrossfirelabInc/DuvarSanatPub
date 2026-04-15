import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import ArtOfTheDayCard from "../components/ArtOfTheDayCard";
import apiClient from "../api/client";
import type { Mock } from "vitest";

const mockGet = apiClient.get as Mock;

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("ArtOfTheDayCard", () => {
  it("renders nothing when API returns null", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      if (url === "/api/art-of-the-day") return Promise.resolve({ data: null });
      return Promise.reject(new Error("unexpected: " + url));
    });

    const { container } = renderWithProviders(<ArtOfTheDayCard />);

    await waitFor(() => {
      expect(container.querySelector(".aotd-card")).toBeNull();
    });
  });

  it("renders card when API returns data", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      if (url === "/api/art-of-the-day") {
        return Promise.resolve({
          data: {
            artwork_id: "aw-1",
            title: "Test Mural",
            artist_name: "Banksy",
            photo_url: "/uploads/test.jpg",
            featured_date: "2026-04-01",
          },
        });
      }
      return Promise.reject(new Error("unexpected: " + url));
    });

    renderWithProviders(<ArtOfTheDayCard />);

    await waitFor(() => {
      expect(screen.getByText("Test Mural")).toBeInTheDocument();
    });
    expect(screen.getByText("by Banksy")).toBeInTheDocument();
    expect(screen.getByText("View Artwork")).toBeInTheDocument();
  });

  it("renders anonymous when no artist", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") return Promise.reject(new Error("no auth"));
      if (url === "/api/art-of-the-day") {
        return Promise.resolve({
          data: {
            artwork_id: "aw-1",
            title: "Unknown Piece",
            artist_name: null,
            photo_url: null,
            featured_date: "2026-04-01",
          },
        });
      }
      return Promise.reject(new Error("unexpected: " + url));
    });

    renderWithProviders(<ArtOfTheDayCard />);

    await waitFor(() => {
      expect(screen.getByText("Anonymous")).toBeInTheDocument();
    });
  });
});
