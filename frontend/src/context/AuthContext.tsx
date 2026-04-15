import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import apiClient from "../api/client";

const TOKEN_KEY = "duvarsanat_token";

interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  avatar_url: string | null;
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName: string
  ) => Promise<void>;
  logout: () => void;
  updateUser: (data: Partial<Pick<User, "display_name" | "email" | "avatar_url">>) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Validate existing token on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }

    // Try to decode JWT payload as fallback user data
    let fallbackUser: User | null = null;
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      if (payload.sub && payload.exp && payload.exp * 1000 > Date.now()) {
        fallbackUser = {
          id: payload.sub,
          email: "",
          display_name: "",
          role: payload.role || "user",
          avatar_url: null,
        };
      } else {
        // Token expired — clear it
        localStorage.removeItem(TOKEN_KEY);
        setLoading(false);
        return;
      }
    } catch {
      // Can't decode token — invalid
      localStorage.removeItem(TOKEN_KEY);
      setLoading(false);
      return;
    }

    apiClient
      .get<User>("/api/auth/me")
      .then((res) => setUser(res.data))
      .catch((err) => {
        if (err?.response?.status === 401) {
          // Token rejected by server — clear it
          localStorage.removeItem(TOKEN_KEY);
        } else {
          // Network error / server down — use fallback from JWT
          // User stays "logged in" with basic info until server recovers
          setUser(fallbackUser);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiClient.post<{ access_token: string; user: User }>(
      "/api/auth/login",
      { email, password }
    );
    localStorage.setItem(TOKEN_KEY, res.data.access_token);
    setUser(res.data.user);
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const res = await apiClient.post<{ access_token: string; user: User }>(
        "/api/auth/register",
        { email, password, display_name: displayName }
      );
      localStorage.setItem(TOKEN_KEY, res.data.access_token);
      setUser(res.data.user);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  const updateUser = useCallback(
    (data: Partial<Pick<User, "display_name" | "email" | "avatar_url">>) => {
      setUser((prev) => (prev ? { ...prev, ...data } : prev));
    },
    []
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
