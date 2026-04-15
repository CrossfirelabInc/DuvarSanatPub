"""Tests for Art of the Day API endpoints."""

import os

# Ensure JWT_SECRET is set before any app module is imported.
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-change-me")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from tests.conftest import make_mock_db


# Helpers


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _setup_overrides(db):
    """Override get_db on the FastAPI app."""

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)


# GET /api/art-of-the-day/history


class TestArtOfTheDayHistory:

    @pytest.mark.asyncio
    async def test_history_returns_empty_list(self):
        """History endpoint returns empty list when no data."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                resp = await client.get("/api/art-of-the-day/history")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_history_limit_zero_returns_422(self):
        """limit=0 is below minimum (1) and should return 422."""
        db = make_mock_db()
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                resp = await client.get("/api/art-of-the-day/history?limit=0")
        finally:
            _clear_overrides()

        assert resp.status_code == 422
