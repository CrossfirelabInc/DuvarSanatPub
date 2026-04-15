"""Tests for the Art of the Day selection service."""

import os

# Ensure JWT_SECRET is set before any app module is imported.
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-change-me")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")

from datetime import date

from app.art_of_the_day_service import pick_artwork_id


class TestPickArtworkId:
    """Tests for pick_artwork_id deterministic selection."""

    def test_returns_none_when_no_eligible(self):
        """Empty eligible list returns None."""
        result = pick_artwork_id([], set(), date(2025, 6, 1), "secret")
        assert result is None

    def test_returns_only_artwork_when_one_eligible(self):
        """Single eligible artwork is always returned."""
        result = pick_artwork_id(["abc"], set(), date(2025, 6, 1), "secret")
        assert result == "abc"

    def test_excludes_recently_featured(self):
        """Recently featured IDs are filtered out."""
        ids = ["a", "b", "c"]
        recently = {"a", "b"}
        result = pick_artwork_id(ids, recently, date(2025, 6, 1), "secret")
        assert result == "c"

    def test_deterministic_for_same_date(self):
        """Same inputs always produce the same result."""
        ids = [str(i) for i in range(200)]
        r1 = pick_artwork_id(ids, set(), date(2025, 6, 1), "secret")
        r2 = pick_artwork_id(ids, set(), date(2025, 6, 1), "secret")
        assert r1 == r2

    def test_different_date_picks_differently(self):
        """Different dates should (very likely) pick different artworks.

        With 200 candidates the chance of collision on two dates is ~0.5%.
        """
        ids = [str(i) for i in range(200)]
        r1 = pick_artwork_id(ids, set(), date(2025, 6, 1), "secret")
        r2 = pick_artwork_id(ids, set(), date(2025, 6, 2), "secret")
        assert r1 != r2

    def test_falls_back_to_all_when_all_excluded(self):
        """When every ID is recently featured, fall back to full list."""
        ids = ["a", "b", "c"]
        recently = {"a", "b", "c"}
        result = pick_artwork_id(ids, recently, date(2025, 6, 1), "secret")
        assert result in ids
