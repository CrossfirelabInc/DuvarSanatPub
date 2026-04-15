import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import apiClient from "../api/client";
import FollowButton from "../components/FollowButton";
import BadgeIcon from "../components/BadgeIcon";
import { useAuth } from "../context/AuthContext";


interface LeaderboardEntry {
  rank: number;
  id: string;
  name: string;
  score: number;
  follower_count: number;
  metric: string;
  avatar_url: string | null;
}

interface LeaderboardResponse {
  type: string;
  period: string;
  entries: LeaderboardEntry[];
}

interface Challenge {
  id: string;
  title: string;
  description: string;
  challenge_type: string;
  badge_type: string;
  progress: number;
  target: number;
  completed: boolean;
}

type LeaderboardType = "photographers" | "artists";
type LeaderboardPeriod = "all_time" | "monthly";
type CommunityTab = "leaderboard" | "challenges";


function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getAvatarColor(name: string): string {
  const colors = [
    "#e74c3c",
    "#3498db",
    "#2ecc71",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#34495e",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function getRankClass(rank: number): string {
  if (rank === 1) return "leaderboard-rank gold";
  if (rank === 2) return "leaderboard-rank silver";
  if (rank === 3) return "leaderboard-rank bronze";
  return "leaderboard-rank";
}


function CommunityPage() {
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<CommunityTab>("leaderboard");

  // Leaderboard state
  const [type, setType] = useState<LeaderboardType>("photographers");
  const [period, setPeriod] = useState<LeaderboardPeriod>("all_time");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Challenges state
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [challengesLoading, setChallengesLoading] = useState(false);
  const [challengesError, setChallengesError] = useState("");
  const [challengesFetched, setChallengesFetched] = useState(false);
  const [checkingId, setCheckingId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError("");

    apiClient
      .get<LeaderboardResponse>("/api/leaderboard", {
        params: { type, period },
      })
      .then((res) => {
        setEntries(res.data.entries);
      })
      .catch(() => {
        setError("Failed to load leaderboard. Please try again later.");
        setEntries([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [type, period]);

  // Fetch challenges when tab is switched, auto-check progress if authenticated
  useEffect(() => {
    if (tab !== "challenges" || challengesFetched) return;

    setChallengesLoading(true);
    setChallengesError("");

    const fetchAndCheck = async () => {
      try {
        // Auto-check all challenges if authenticated
        if (isAuthenticated) {
          await apiClient.post("/api/challenges/check-all").catch(() => {});
        }
        const res = await apiClient.get<Challenge[]>("/api/challenges");
        setChallenges(Array.isArray(res.data) ? res.data : []);
        setChallengesFetched(true);
      } catch {
        setChallengesError("Failed to load challenges. Please try again later.");
      } finally {
        setChallengesLoading(false);
      }
    };
    fetchAndCheck();
  }, [tab, challengesFetched, isAuthenticated]);

  function handleCheckProgress(challengeId: string) {
    setCheckingId(challengeId);
    apiClient
      .post<Challenge>(`/api/challenges/${challengeId}/check`)
      .then((res) => {
        setChallenges((prev) =>
          prev.map((c) => (c.id === challengeId ? { ...c, ...res.data } : c))
        );
      })
      .catch(() => {
        // silently ignore
      })
      .finally(() => setCheckingId(null));
  }

  return (
    <div className="page community-page">
      <Helmet>
        <title>Community — DuvarSanat</title>
      </Helmet>
      <div className="community-header">
        <h1>Community</h1>
        <span
          className="page-type-badge"
          style={{ background: "#f0e6f6", color: "#9b59b6" }}
        >
          Community
        </span>
      </div>

      {/* Section tabs */}
      <div className="community-tabs">
        <button
          className={`community-tab${tab === "leaderboard" ? " active" : ""}`}
          onClick={() => setTab("leaderboard")}
        >
          Leaderboard
        </button>
        <button
          className={`community-tab${tab === "challenges" ? " active" : ""}`}
          onClick={() => setTab("challenges")}
        >
          Challenges
        </button>
      </div>

      {/* Leaderboard tab */}
      {tab === "leaderboard" && (
        <>
          {/* Toggle controls */}
          <div className="leaderboard-toggles">
            <div className="leaderboard-toggle-group">
              <button
                className={`leaderboard-toggle${type === "photographers" ? " active" : ""}`}
                onClick={() => setType("photographers")}
              >
                Photographers
              </button>
              <button
                className={`leaderboard-toggle${type === "artists" ? " active" : ""}`}
                onClick={() => setType("artists")}
              >
                Artists
              </button>
            </div>

            <div className="leaderboard-toggle-group">
              <button
                className={`leaderboard-toggle${period === "all_time" ? " active" : ""}`}
                onClick={() => setPeriod("all_time")}
              >
                All Time
              </button>
              <button
                className={`leaderboard-toggle${period === "monthly" ? " active" : ""}`}
                onClick={() => setPeriod("monthly")}
              >
                This Month
              </button>
            </div>
          </div>

          {/* Content area */}
          {loading && (
            <div className="loading">
              <div className="spinner" />
            </div>
          )}

          {error && <p className="community-error">{error}</p>}

          {!loading && !error && entries.length === 0 && (
            <div className="community-empty">
              <p>No data yet. Start uploading to climb the ranks!</p>
            </div>
          )}

          {!loading && !error && entries.length > 0 && (
            <div className="leaderboard-table">
              {entries.map((entry) => {
                const isTop3 = entry.rank <= 3;
                const profileLink =
                  type === "photographers"
                    ? `/users/${entry.id}`
                    : `/artists/${entry.id}`;
                const targetType = type === "photographers" ? "user" : "artist";

                return (
                  <div
                    key={entry.id}
                    className={`leaderboard-row${isTop3 ? " leaderboard-row--top" : ""}`}
                  >
                    <span className={getRankClass(entry.rank)}>
                      #{entry.rank}
                    </span>

                    {entry.avatar_url ? (
                      <img
                        className="leaderboard-avatar-img"
                        src={entry.avatar_url}
                        alt={entry.name}
                      />
                    ) : (
                      <div
                        className="leaderboard-avatar"
                        style={{ background: getAvatarColor(entry.name) }}
                      >
                        {getInitials(entry.name)}
                      </div>
                    )}

                    <Link to={profileLink} className="leaderboard-name">
                      {entry.name}
                    </Link>

                    <span className="leaderboard-score">
                      {entry.score}{" "}
                      <span className="leaderboard-metric">{entry.metric}</span>
                    </span>

                    <FollowButton
                      targetType={targetType}
                      targetId={entry.id}
                      initialCount={entry.follower_count}
                      compact
                    />
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Challenges tab */}
      {tab === "challenges" && (
        <>
          {challengesLoading && (
            <div className="loading">
              <div className="spinner" />
            </div>
          )}

          {challengesError && <p className="community-error">{challengesError}</p>}

          {!challengesLoading && !challengesError && challenges.length === 0 && challengesFetched && (
            <div className="community-empty">
              <p>No challenges available yet. Check back soon!</p>
            </div>
          )}

          {!challengesLoading && challenges.length > 0 && (
            <div className="challenges-grid">
              {challenges.map((ch) => {
                const pct = ch.target > 0 ? Math.min(100, Math.round((ch.progress / ch.target) * 100)) : 0;

                return (
                  <div key={ch.id} className={`challenge-card${ch.completed ? " challenge-completed" : ""}`}>
                    <div className="challenge-card-header">
                      <BadgeIcon badgeType={ch.badge_type} size="md" />
                      <div className="challenge-card-title-group">
                        <h3 className="challenge-card-title">{ch.title}</h3>
                        <p className="challenge-card-desc">{ch.description}</p>
                      </div>
                    </div>

                    <div className="challenge-progress-wrapper">
                      <div className="challenge-progress-bar">
                        <div
                          className="challenge-progress-fill"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="challenge-progress-text">
                        {ch.progress} / {ch.target} ({pct}%)
                      </span>
                    </div>

                    {ch.completed ? (
                      <div className="challenge-done">
                        {"\u2713"} Completed!
                      </div>
                    ) : (
                      isAuthenticated && (
                        <button
                          className="btn btn-challenge-check"
                          onClick={() => handleCheckProgress(ch.id)}
                          disabled={checkingId === ch.id}
                        >
                          {checkingId === ch.id ? "Checking..." : "Check Progress"}
                        </button>
                      )
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default CommunityPage;
