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

function renderRegisterPage() {
  return renderWithProviders(<App />, {
    routerProps: { initialEntries: ["/register"] },
  });
}

describe("RegisterPage", () => {
  it("renders the registration form with all fields", async () => {
    renderRegisterPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /create account/i })
      ).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/display name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /register/i })
    ).toBeInTheDocument();
  });

  it("shows a link to login page", async () => {
    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByText(/already have an account/i)).toBeInTheDocument();
    });

    // The form has a "Login" link inside the auth-switch paragraph
    const switchParagraph = screen.getByText(/already have an account/i);
    const loginLink = switchParagraph.querySelector("a");
    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("shows all validation errors when submitting empty form", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /register/i })
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(screen.getByText("Email is required.")).toBeInTheDocument();
    });
    expect(screen.getByText("Password is required.")).toBeInTheDocument();
    expect(
      screen.getByText("Display name is required.")
    ).toBeInTheDocument();

    expect(mockPost).not.toHaveBeenCalled();
  });

  it("shows invalid email error", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/display name/i), "TestUser");
    await user.type(screen.getByLabelText(/password/i), "longpassword123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Enter a valid email address.")
      ).toBeInTheDocument();
    });

    // Other fields should be valid
    expect(
      screen.queryByText("Password is required.")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Display name is required.")
    ).not.toBeInTheDocument();
  });

  it("shows short password error", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/display name/i), "TestUser");
    await user.type(screen.getByLabelText(/password/i), "short");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Password must be at least 8 characters.")
      ).toBeInTheDocument();
    });
  });

  it("shows short display name error", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/display name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/display name/i), "A");
    await user.type(screen.getByLabelText(/password/i), "longpassword123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Display name must be at least 2 characters.")
      ).toBeInTheDocument();
    });
  });

  it("calls register API with correct payload on valid submission", async () => {
    const user = userEvent.setup();

    const fakeUser = {
      id: "u1",
      email: "test@example.com",
      display_name: "NewUser",
      role: "user",
    };

    mockPost.mockResolvedValue({
      data: { access_token: "jwt-token-456", user: fakeUser },
    });

    mockGet.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ data: fakeUser });
      }
      return Promise.reject(new Error("unexpected"));
    });

    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/display name/i), "NewUser");
    await user.type(screen.getByLabelText(/password/i), "securepassword123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/auth/register", {
        email: "test@example.com",
        password: "securepassword123",
        display_name: "NewUser",
      });
    });
  });

  it("shows API error for duplicate email (409)", async () => {
    const user = userEvent.setup();

    const axiosError = new AxiosError("Conflict", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 409,
      data: { detail: "A user with this email already exists." },
      statusText: "Conflict",
      headers: {},
      config: {} as any,
    });

    mockPost.mockRejectedValue(axiosError);

    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "taken@example.com");
    await user.type(screen.getByLabelText(/display name/i), "NewUser");
    await user.type(screen.getByLabelText(/password/i), "securepassword123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(
        screen.getByText("A user with this email already exists.")
      ).toBeInTheDocument();
    });
  });

  it("shows network error when request fails entirely", async () => {
    const user = userEvent.setup();

    mockPost.mockRejectedValue(new Error("Network Error"));

    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/display name/i), "NewUser");
    await user.type(screen.getByLabelText(/password/i), "securepassword123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please check your connection.")
      ).toBeInTheDocument();
    });
  });

  it("disables form fields and shows loading text while submitting", async () => {
    const user = userEvent.setup();

    let resolveRegister: (value: any) => void;
    const registerPromise = new Promise((resolve) => {
      resolveRegister = resolve;
    });
    mockPost.mockReturnValue(registerPromise);

    renderRegisterPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/display name/i), "NewUser");
    await user.type(screen.getByLabelText(/password/i), "longpassword");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(screen.getByText("Creating account...")).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/email/i)).toBeDisabled();
    expect(screen.getByLabelText(/display name/i)).toBeDisabled();
    expect(screen.getByLabelText(/password/i)).toBeDisabled();

    // Resolve to clean up
    resolveRegister!({
      data: {
        access_token: "tok",
        user: { id: "u1", email: "a@b.com", display_name: "X", role: "user" },
      },
    });
  });
});
