import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import App from "../App";
import apiClient from "../api/client";
import { AxiosError } from "axios";
import type { Mock } from "vitest";

const mockGet = apiClient.get as Mock;
const mockPost = apiClient.post as Mock;

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  mockGet.mockRejectedValue(new Error("not authenticated"));
});

function renderLoginPage() {
  return renderWithProviders(<App />, {
    routerProps: { initialEntries: ["/login"] },
  });
}

describe("LoginPage", () => {
  it("renders the login form with email and password fields", async () => {
    renderLoginPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /login/i })
      ).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /login/i })
    ).toBeInTheDocument();
  });

  it("shows a link to register page", async () => {
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByText(/need an account/i)).toBeInTheDocument();
    });

    // The form has a "Register" link inside the auth-switch paragraph
    const switchParagraph = screen.getByText(/need an account/i);
    const registerLink = switchParagraph.querySelector("a");
    expect(registerLink).toHaveAttribute("href", "/register");
  });

  it("shows validation errors when submitting empty form", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /login/i })
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText("Email is required.")).toBeInTheDocument();
    });
    expect(screen.getByText("Password is required.")).toBeInTheDocument();

    // Should NOT have called the API
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("shows validation error for empty email only", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/password/i), "somepassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText("Email is required.")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Password is required.")
    ).not.toBeInTheDocument();
  });

  it("shows validation error for empty password only", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText("Password is required.")).toBeInTheDocument();
    });
    expect(screen.queryByText("Email is required.")).not.toBeInTheDocument();
  });

  it("calls login API and navigates to / on success", async () => {
    const user = userEvent.setup();

    const fakeUser = {
      id: "u1",
      email: "test@example.com",
      display_name: "TestUser",
      role: "user",
    };

    mockPost.mockResolvedValue({
      data: { access_token: "jwt-token-123", user: fakeUser },
    });

    // After login succeeds, AuthProvider re-renders and pages may call /api/auth/me
    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ data: fakeUser });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "mypassword123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/auth/login", {
        email: "test@example.com",
        password: "mypassword123",
      });
    });
  });

  it("shows API error for 401 unauthorized", async () => {
    const user = userEvent.setup();

    const axiosError = new AxiosError("Unauthorized", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 401,
      data: {},
      statusText: "Unauthorized",
      headers: {},
      config: {} as any,
    });

    mockPost.mockRejectedValue(axiosError);

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Invalid credentials. Please check your email and password.")
      ).toBeInTheDocument();
    });
  });

  it("shows network error message when request fails", async () => {
    const user = userEvent.setup();

    mockPost.mockRejectedValue(new Error("Network Error"));

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "somepassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please check your connection.")
      ).toBeInTheDocument();
    });
  });

  it("disables form fields and button while submitting", async () => {
    const user = userEvent.setup();

    // Create a promise that won't resolve immediately
    let resolveLogin: (value: any) => void;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    mockPost.mockReturnValue(loginPromise);

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "mypassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText("Logging in...")).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/email/i)).toBeDisabled();
    expect(screen.getByLabelText(/password/i)).toBeDisabled();

    // Resolve to clean up
    resolveLogin!({
      data: {
        access_token: "tok",
        user: { id: "u1", email: "a@b.com", display_name: "X", role: "user" },
      },
    });
  });
});
