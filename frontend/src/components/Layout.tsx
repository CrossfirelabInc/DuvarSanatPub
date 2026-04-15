import { useState, useCallback } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import OnboardingModal from "./OnboardingModal";
import NotificationBell from "./NotificationBell";

function Layout() {
  const { user, isAuthenticated, loading, logout } = useAuth();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchExpanded, setSearchExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const needsOnboarding =
    isAuthenticated &&
    localStorage.getItem("duvarsanat_onboarded") !== "true";
  const [showOnboarding, setShowOnboarding] = useState(needsOnboarding);

  const handleOnboardingComplete = useCallback(() => {
    setShowOnboarding(false);
  }, []);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
    setSearchQuery("");
    setSearchExpanded(false);
    setMenuOpen(false);
  }

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <>
      <div className="for-sale-banner">
        This domain is for sale — contact:{" "}
        <a href="mailto:info@crossfirelab.com">info@crossfirelab.com</a>
      </div>
      <nav className="nav-redesign">
        <div className="nav-redesign-left">
          <Link to="/" className="nav-redesign-brand">
            DuvarSanat
          </Link>
          <button
            className="nav-hamburger"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            {menuOpen ? "\u2715" : "\u2630"}
          </button>
          <div className={`nav-redesign-links${menuOpen ? " open" : ""}`}>
            <Link to="/" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
              Home
            </Link>
            <Link to="/explore" className="nav-redesign-link nav-explore-btn" onClick={() => setMenuOpen(false)}>
              Explore
            </Link>
            <Link to="/artists" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
              Artists
            </Link>
            <Link to="/community" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
              Community
            </Link>
            <Link to="/tours" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
              Tours
            </Link>
            <Link to="/art-of-the-day" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
              Daily
            </Link>
            {/* Mobile-only: auth links inside hamburger menu */}
            {menuOpen && isAuthenticated && (
              <>
                <div className="nav-mobile-divider" />
                <Link to="/profile" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                  My Profile
                </Link>
                <Link to="/messages" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                  Messages
                </Link>
                <Link to="/upload" className="nav-redesign-link nav-explore-btn" onClick={() => setMenuOpen(false)}>
                  Upload
                </Link>
                {(user?.role === "moderator" || user?.role === "admin") && (
                  <Link to="/mod" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                    Mod Dashboard
                  </Link>
                )}
                {user?.role === "admin" && (
                  <Link to="/admin/settings" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                    Admin Settings
                  </Link>
                )}
                <button className="nav-redesign-link nav-mobile-logout" onClick={() => { logout(); setMenuOpen(false); }}>
                  Logout
                </button>
              </>
            )}
            {menuOpen && !isAuthenticated && (
              <>
                <div className="nav-mobile-divider" />
                <Link to="/login" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                  Login
                </Link>
                <Link to="/register" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                  Register
                </Link>
              </>
            )}
          </div>
        </div>

        <div className={`nav-redesign-right${menuOpen ? " open" : ""}`}>
          {/* Desktop search */}
          <form
            className="nav-search-form nav-search-desktop"
            onSubmit={handleSearchSubmit}
          >
            <input
              type="text"
              className="nav-search-input"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>

          {/* Mobile search toggle */}
          <button
            className="nav-search-toggle"
            onClick={() => setSearchExpanded(!searchExpanded)}
            aria-label="Toggle search"
          >
            &#x1F50D;
          </button>

          {isAuthenticated ? (
            <>
              <Link to="/messages" className="btn btn-ghost-dark btn-sm" title="Messages" onClick={() => setMenuOpen(false)}>
                Messages
              </Link>
              {(user?.role === "moderator" || user?.role === "admin") && (
                <Link to="/mod" className="btn btn-ghost-dark btn-sm nav-mod-btn" title="Moderator Dashboard" onClick={() => setMenuOpen(false)}>
                  Mod
                </Link>
              )}
              {user?.role === "admin" && (
                <Link to="/admin/settings" className="btn btn-ghost-dark btn-sm" title="Admin Settings" onClick={() => setMenuOpen(false)}>
                  Settings
                </Link>
              )}
              <Link to="/upload" className="btn btn-accent btn-sm" onClick={() => setMenuOpen(false)}>
                Upload
              </Link>
              <Link to="/profile" className="nav-redesign-user" onClick={() => setMenuOpen(false)}>
                {user?.display_name}
              </Link>
              <button className="btn btn-ghost-dark" onClick={() => { logout(); setMenuOpen(false); }}>
                Logout
              </button>
              <NotificationBell />
            </>
          ) : (
            <>
              <Link to="/login" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                Login
              </Link>
              <Link to="/register" className="nav-redesign-link" onClick={() => setMenuOpen(false)}>
                Register
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Mobile expanded search */}
      {searchExpanded && (
        <form
          className="nav-search-mobile-bar"
          onSubmit={handleSearchSubmit}
        >
          <input
            type="text"
            className="nav-search-input nav-search-input-full"
            placeholder="Search artworks, artists..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />
          <button type="submit" className="btn btn-accent btn-sm">
            Go
          </button>
        </form>
      )}

      <Outlet />

      {showOnboarding && (
        <OnboardingModal onComplete={handleOnboardingComplete} />
      )}
    </>
  );
}

export default Layout;
