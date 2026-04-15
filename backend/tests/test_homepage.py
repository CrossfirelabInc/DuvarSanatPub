"""Tests for the GET /api/homepage endpoint."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from tests.conftest import make_mock_db


def _scalar(value):
    """Mock result for db.scalar() calls."""
    return value


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _scalars_all(values):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    result.scalars.return_value = scalars
    return result


def _first(value):
    result = MagicMock()
    result.first.return_value = value
    return result


def _setup_overrides(db):
    async def _db_override():
        yield db
    app.dependency_overrides[get_db] = _db_override


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)


class TestHomepage:

    @pytest.mark.asyncio
    async def test_homepage_returns_all_sections(self):
        """GET /api/homepage returns structured response with all sections."""
        db = make_mock_db()

        # The homepage endpoint calls:
        # 1. _get_art_of_the_day: execute (ArtOfTheDay lookup) -> None (no aotd today)
        #    then execute (eligible artworks) -> empty list -> returns None
        # 2. _get_stats: scalar (total_artworks), scalar (total_photos),
        #    scalar (total_artists), scalar (walls_changed_this_week)
        # 3. _get_walls_changed: execute -> empty list
        # 4. _get_recent_discoveries: execute -> empty list
        # 5. _get_active_neighborhoods: execute -> scalars -> empty list
        # 6. mysteries_count: scalar -> 0

        # Track scalar and execute calls separately
        scalar_returns = [10, 50, 5, 3, 0]  # stats + mysteries
        scalar_index = [0]

        async def mock_scalar(stmt):
            idx = scalar_index[0]
            scalar_index[0] += 1
            if idx < len(scalar_returns):
                return scalar_returns[idx]
            return 0

        db.scalar = mock_scalar

        execute_returns = [
            _scalar_one_or_none(None),  # AoTD lookup -> None
            _all([]),                    # eligible artworks -> empty
            _all([]),                    # walls_changed query
            _all([]),                    # recent_discoveries query
            _scalars_all([]),            # active_neighborhoods query
        ]
        execute_index = [0]

        async def mock_execute(stmt, *args, **kwargs):
            idx = execute_index[0]
            execute_index[0] += 1
            if idx < len(execute_returns):
                return execute_returns[idx]
            return _all([])

        db.execute = mock_execute

        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/homepage")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()

        # Verify all sections present
        assert "art_of_the_day" in body
        assert "stats" in body
        assert "walls_changed" in body
        assert "recent_discoveries" in body
        assert "neighborhoods" in body
        assert "mysteries_count" in body

        # Art of the day is None when no eligible artworks
        assert body["art_of_the_day"] is None

        # Stats should reflect mock values
        assert body["stats"]["total_artworks"] == 10
        assert body["stats"]["total_photos"] == 50
        assert body["stats"]["total_artists"] == 5
        assert body["stats"]["walls_changed_this_week"] == 3

        # Empty lists
        assert body["walls_changed"] == []
        assert body["recent_discoveries"] == []
        assert body["neighborhoods"] == []
        assert body["mysteries_count"] == 0

    @pytest.mark.asyncio
    async def test_homepage_is_public(self):
        """GET /api/homepage does not require authentication."""
        db = make_mock_db()

        scalar_returns = [0, 0, 0, 0, 0]
        scalar_index = [0]

        async def mock_scalar(stmt):
            idx = scalar_index[0]
            scalar_index[0] += 1
            if idx < len(scalar_returns):
                return scalar_returns[idx]
            return 0

        db.scalar = mock_scalar

        execute_returns = [
            _scalar_one_or_none(None),
            _all([]),
            _all([]),
            _all([]),
            _scalars_all([]),
        ]
        execute_index = [0]

        async def mock_execute(stmt, *args, **kwargs):
            idx = execute_index[0]
            execute_index[0] += 1
            if idx < len(execute_returns):
                return execute_returns[idx]
            return _all([])

        db.execute = mock_execute

        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                # No auth headers
                resp = await client.get("/api/homepage")
        finally:
            _clear_overrides()

        # Should succeed without auth
        assert resp.status_code == 200
