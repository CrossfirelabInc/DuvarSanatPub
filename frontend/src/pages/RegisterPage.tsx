import { useState, useEffect, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AxiosError } from "axios";

function RegisterPage() {
  const { register, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Redirect away if already logged in
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: Record<string, string> = {};

    if (!email.trim()) {
      next.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "Enter a valid email address.";
    }

    if (!password) {
      next.password = "Password is required.";
    } else if (password.length < 8) {
      next.password = "Password must be at least 8 characters.";
    }

    if (!displayName.trim()) {
      next.displayName = "Display name is required.";
    } else if (displayName.trim().length < 2) {
      next.displayName = "Display name must be at least 2 characters.";
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setApiError("");

    if (!validate()) return;

    setSubmitting(true);
    try {
      await register(email.trim(), password, displayName.trim());
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        const data = err.response.data;
        // Backend returns 409 for duplicates with a detail message
        if (typeof data?.detail === "string") {
          setApiError(data.detail);
        } else {
          setApiError("Registration failed. Please try again.");
        }
      } else {
        setApiError("Network error. Please check your connection.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit} noValidate>
        <h1 className="auth-title">Create Account</h1>

        {apiError && <div className="auth-error">{apiError}</div>}

        <div className="form-field">
          <label htmlFor="reg-email">Email</label>
          <input
            id="reg-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            disabled={submitting}
          />
          {errors.email && (
            <span className="field-error">{errors.email}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="reg-display-name">Display Name</label>
          <input
            id="reg-display-name"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="username"
            disabled={submitting}
          />
          {errors.displayName && (
            <span className="field-error">{errors.displayName}</span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="reg-password">Password</label>
          <input
            id="reg-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            disabled={submitting}
          />
          {errors.password && (
            <span className="field-error">{errors.password}</span>
          )}
        </div>

        <button
          type="submit"
          className="btn btn-primary auth-submit"
          disabled={submitting}
        >
          {submitting ? "Creating account..." : "Register"}
        </button>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </form>
    </div>
  );
}

export default RegisterPage;
