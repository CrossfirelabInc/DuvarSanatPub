"""Tests for challenges, walking tours, and notifications."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.auth import get_current_user
from app.database import get_db
from tests.conftest import make_mock_db, make_user


# Helpers


def _override_db(mock_db):
    async def _get():
        yield mock_db
    app.dependency_overrides[get_db] = _get


def _override_auth(user):
    async def _get():
        return user
    app.dependency_overrides[get_current_user] = _get


def _cleanup():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


# Mock objects


def _make_challenge(**overrides):
    c = MagicMock()
    c.id = overrides.get("id", uuid.uuid4())
    c.title = overrides.get("title", "Test Challenge")
    c.description = overrides.get("description", "Do something")
    c.challenge_type = overrides.get("challenge_type", "upload")
    c.badge_type = overrides.get("badge_type", "test_badge")
    c.criteria = overrides.get("criteria", {"action": "first_photo", "count": 1})
    c.is_active = overrides.get("is_active", True)
    c.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return c


def _make_notification(**overrides):
    n = MagicMock()
    n.id = overrides.get("id", uuid.uuid4())
    n.user_id = overrides.get("user_id", uuid.uuid4())
    n.type = overrides.get("type", "badge_earned")
    n.title = overrides.get("title", "Test notification")
    n.message = overrides.get("message", "Test message")
    n.link = overrides.get("link", None)
    n.is_read = overrides.get("is_read", False)
    n.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return n


def _make_tour(**overrides):
    t = MagicMock()
    t.id = overrides.get("id", uuid.uuid4())
    t.title = overrides.get("title", "Test Tour")
    t.description = overrides.get("description", "A nice walk")
    t.neighborhood_id = overrides.get("neighborhood_id", uuid.uuid4())
    t.total_distance_m = overrides.get("total_distance_m", 1500)
    t.estimated_minutes = overrides.get("estimated_minutes", 18)
    t.artwork_count = overrides.get("artwork_count", 5)
    t.is_auto_generated = overrides.get("is_auto_generated", True)
    t.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return t


# Challenge Tests


@pytest.mark.anyio
async def test_list_challenges_returns_list():
    """GET /api/challenges returns a list of active challenges."""
    mock_db = make_mock_db()
    challenge = _make_challenge()

    # Mock the scalars().all() chain for challenges query
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [challenge]

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    mock_db.execute = AsyncMock(return_value=result_mock)

    _override_db(mock_db)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/challenges")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test Challenge"
        assert data[0]["badge_type"] == "test_badge"
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_check_challenge_requires_auth():
    """POST /api/challenges/:id/check requires authentication."""
    transport = ASGITransport(app=app)
    _cleanup()
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(f"/api/challenges/{uuid.uuid4()}/check")
    assert resp.status_code in (401, 403)


# Tour Tests


@pytest.mark.anyio
async def test_list_tours_returns_list():
    """GET /api/tours returns a list of tours."""
    mock_db = make_mock_db()
    tour = _make_tour()
    neighborhood_name = "Kadikoy"

    result_mock = MagicMock()
    result_mock.all.return_value = [(tour, neighborhood_name)]
    mock_db.execute = AsyncMock(return_value=result_mock)

    _override_db(mock_db)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/tours")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test Tour"
        assert data[0]["neighborhood_name"] == "Kadikoy"
        assert data[0]["artwork_count"] == 5
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_generate_tours_requires_admin():
    """POST /api/tours/generate requires admin role."""
    mock_db = make_mock_db()
    user = make_user(role="user")

    _override_db(mock_db)
    _override_auth(user)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/tours/generate")
        assert resp.status_code == 403
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_tour_detail_not_found():
    """GET /api/tours/:id returns 404 for non-existent tour."""
    mock_db = make_mock_db()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    _override_db(mock_db)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(f"/api/tours/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        _cleanup()


# Notification Tests


@pytest.mark.anyio
async def test_notifications_requires_auth():
    """GET /api/notifications requires authentication."""
    _cleanup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/notifications")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_unread_count_returns_count():
    """GET /api/notifications/unread-count returns count for authenticated user."""
    mock_db = make_mock_db()
    user = make_user()

    mock_db.scalar = AsyncMock(return_value=3)

    _override_db(mock_db)
    _override_auth(user)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/notifications/unread-count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_list_notifications_returns_list():
    """GET /api/notifications returns notifications for the current user."""
    mock_db = make_mock_db()
    user = make_user()
    notification = _make_notification(user_id=user.id)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [notification]

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute = AsyncMock(return_value=result_mock)

    _override_db(mock_db)
    _override_auth(user)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test notification"
        assert data[0]["type"] == "badge_earned"
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_mark_all_read():
    """POST /api/notifications/read-all marks all notifications as read."""
    mock_db = make_mock_db()
    user = make_user()

    mock_db.execute = AsyncMock(return_value=MagicMock())

    _override_db(mock_db)
    _override_auth(user)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    finally:
        _cleanup()


@pytest.mark.anyio
async def test_unread_count_requires_auth():
    """GET /api/notifications/unread-count requires authentication."""
    _cleanup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/notifications/unread-count")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_mark_notification_read_not_found():
    """POST /api/notifications/:id/read returns 404 for non-existent notification."""
    mock_db = make_mock_db()
    user = make_user()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    _override_db(mock_db)
    _override_auth(user)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(f"/api/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 404
    finally:
        _cleanup()
