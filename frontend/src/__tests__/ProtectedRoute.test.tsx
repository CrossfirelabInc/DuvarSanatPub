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

describe("ProtectedRoute", () => {
  it("redirects unauthenticated users from /upload to /login", async () => {
    mockGet.mockRejectedValue(new Error("not authenticated"));

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/upload"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });
  });

  it("redirects unauthenticated users from /profile to /login", async () => {
    mockGet.mockRejectedValue(new Error("not authenticated"));

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/profile"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });
  });

  it("allows authenticated users to access /upload", async () => {
    localStorage.setItem("duvarsanat_token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1MSIsInJvbGUiOiJ1c2VyIiwiZXhwIjo5OTk5OTk5OTk5fQ==.fakesig");

    const fakeUser = {
      id: "u1",
      email: "test@example.com",
      display_name: "TestUser",
      role: "user",
    };

    // First call: /api/auth/me. Subsequent calls: page-specific API calls
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ data: fakeUser });
      }
      // UploadPage doesn't fetch on mount, so this is fine
      return Promise.reject(new Error("unexpected"));
    });

    renderWithProviders(<App />, {
      routerProps: { initialEntries: ["/upload"] },
    });

    // Should see the Upload page content, not the login page
    await waitFor(() => {
      expect(screen.getByText("TestUser")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("heading", { name: /login/i })
    ).not.toBeInTheDocument();
  });
});
