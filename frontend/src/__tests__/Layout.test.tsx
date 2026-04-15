import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import App from "../App";
import apiClient from "../api/client";
import type { Mock } from "vitest";

const mockGet = apiClient.get as Mock;

const emptyHomepage = {
  art_of_the_day: null,
  stats: { total_artworks: 0, total_photos: 0, total_artists: 0, walls_changed_this_week: 0 },
  walls_changed: [],
  recent_discoveries: [],
  neighborhoods: [],
  mysteries_count: 0,
};

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("Layout - unauthenticated", () => {
  beforeEach(() => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/api/artworks")) {
        return Promise.resolve({ data: [] });
      }
      if (url === "/api/homepage") {
        return Promise.resolve({ data: emptyHomepage });
      }
      return Promise.reject(new Error("not authenticated"));
    });
  });

  it("shows Login and Register links when not authenticated", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });
    expect(screen.getByText("Register")).toBeInTheDocument();

    // Should NOT show authenticated-only elements
    expect(screen.queryByText("Upload")).not.toBeInTheDocument();
    expect(screen.queryByText("Logout")).not.toBeInTheDocument();
  });

  it("shows the DuvarSanat brand link", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    await waitFor(() => {
      expect(screen.getByText("DuvarSanat")).toBeInTheDocument();
    });

    const brand = screen.getByText("DuvarSanat");
    expect(brand.closest("a")).toHaveAttribute("href", "/");
  });
});

describe("Layout - authenticated", () => {
  const fakeUser = {
    id: "u1",
    email: "test@example.com",
    display_name: "TestUser",
    role: "user",
  };

  beforeEach(() => {
    localStorage.setItem("duvarsanat_token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1MSIsInJvbGUiOiJ1c2VyIiwiZXhwIjo5OTk5OTk5OTk5fQ==.fakesig");
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ data: fakeUser });
      }
      if (url.startsWith("/api/artworks")) {
        return Promise.resolve({ data: [] });
      }
      if (url === "/api/homepage") {
        return Promise.resolve({ data: emptyHomepage });
      }
      return Promise.reject(new Error("unexpected: " + url));
    });
  });

  it("shows user display name, Upload, and Logout when authenticated", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    await waitFor(() => {
      expect(screen.getByText("TestUser")).toBeInTheDocument();
    });

    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText("Logout")).toBeInTheDocument();

    // Should NOT show login/register links
    expect(screen.queryByText("Login")).not.toBeInTheDocument();
    expect(screen.queryByText("Register")).not.toBeInTheDocument();
  });

  it("logs out when Logout button is clicked", async () => {
    const user = userEvent.setup();

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Logout")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Logout"));

    // After logout, should show Login/Register again
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });
    expect(screen.getByText("Register")).toBeInTheDocument();
    expect(localStorage.getItem("duvarsanat_token")).toBeNull();
  });

  it("links user display name to /profile", async () => {
    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/"] },
    });

    await waitFor(() => {
      expect(screen.getByText("TestUser")).toBeInTheDocument();
    });

    const profileLink = screen.getByText("TestUser").closest("a");
    expect(profileLink).toHaveAttribute("href", "/profile");
  });
});
