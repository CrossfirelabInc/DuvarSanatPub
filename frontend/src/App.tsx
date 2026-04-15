import { lazy, Suspense } from "react";
import { Routes, Route, Link } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";

// Eager imports -- entry points and pages with tests that render via App
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import MapPage from "./pages/MapPage";
import UploadPage from "./pages/UploadPage";
import ArtworkDetailPage from "./pages/ArtworkDetailPage";
import ArtistProfilePage from "./pages/ArtistProfilePage";
import UserProfilePage from "./pages/UserProfilePage";
import MyProfilePage from "./pages/MyProfilePage";
import ArtOfTheDayPage from "./pages/ArtOfTheDayPage";

// Lazy-loaded pages (heavy, no direct test routing through App)
const ArtistsDirectoryPage = lazy(() => import("./pages/ArtistsDirectoryPage"));
const CommunityPage = lazy(() => import("./pages/CommunityPage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const ModDashboardPage = lazy(() => import("./pages/ModDashboardPage"));
const ToursPage = lazy(() => import("./pages/ToursPage"));
const TourDetailPage = lazy(() => import("./pages/TourDetailPage"));
const MessagesPage = lazy(() => import("./pages/MessagesPage"));
const AdminSettingsPage = lazy(() => import("./pages/AdminSettingsPage"));

function App() {
  return (
    <Suspense fallback={<div className="loading">Loading...</div>}>
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/explore" element={<MapPage />} />
        <Route path="/artists" element={<ArtistsDirectoryPage />} />
        <Route path="/community" element={<CommunityPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/tours" element={<ToursPage />} />
        <Route path="/tours/:id" element={<TourDetailPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <UploadPage />
            </ProtectedRoute>
          }
        />
        <Route path="/artworks/:id" element={<ArtworkDetailPage />} />
        <Route path="/artists/:id" element={<ArtistProfilePage />} />
        <Route path="/users/:id" element={<UserProfilePage />} />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <MyProfilePage />
            </ProtectedRoute>
          }
        />
        <Route path="/art-of-the-day" element={<ArtOfTheDayPage />} />
        <Route
          path="/messages"
          element={
            <ProtectedRoute>
              <MessagesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/mod"
          element={
            <ProtectedRoute>
              <ModDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/settings"
          element={
            <ProtectedRoute>
              <AdminSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="*"
          element={
            <div className="page" style={{ textAlign: "center", paddingTop: "4rem" }}>
              <h1>Page Not Found</h1>
              <p style={{ color: "#555", margin: "1rem 0 1.5rem" }}>
                The page you are looking for does not exist.
              </p>
              <Link to="/" className="btn btn-primary">
                Back to Home
              </Link>
            </div>
          }
        />
      </Route>
    </Routes>
    </Suspense>
  );
}

export default App;
