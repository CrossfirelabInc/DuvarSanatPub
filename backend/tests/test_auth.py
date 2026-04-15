"""Tests for /api/auth/* endpoints (register, login, me).

All DB interactions are mocked -- no PostgreSQL required.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, hash_password
from app.database import get_db
from app.main import app
from app.models import User
from tests.conftest import make_mock_db, make_user


# Helpers

def _scalar_one_or_none(value):
    """Build an execute-result mock that returns *value* on scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# POST /api/auth/register


class TestRegister:
    """Registration endpoint tests."""

    @pytest.mark.asyncio
    async def test_register_success(self):
        """Registering with valid data returns 201 + JWT + user object."""
        db = make_mock_db()

        # First two selects (email check, display_name check) return None
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(None),  # email not taken
            _scalar_one_or_none(None),  # display_name not taken
        ])

        created_user = make_user(email="new@example.com", display_name="NewUser")

        async def fake_refresh(obj):
            # Simulate DB assigning id and created_at
            obj.id = created_user.id
            obj.email = "new@example.com"
            obj.display_name = "NewUser"
            obj.role = "user"
            obj.bio = None
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        db.refresh = AsyncMock(side_effect=fake_refresh)

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/register", json={
                    "email": "new@example.com",
                    "password": "securepass123",
                    "display_name": "NewUser",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "new@example.com"
        assert body["user"]["display_name"] == "NewUser"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self):
        """Registering with an already-taken email returns 409."""
        db = make_mock_db()
        existing = make_user(email="taken@example.com")
        db.execute = AsyncMock(return_value=_scalar_one_or_none(existing))

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/register", json={
                    "email": "taken@example.com",
                    "password": "securepass123",
                    "display_name": "AnyName",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 409
        assert "Email already registered" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_display_name(self):
        """Registering with a taken display_name returns 409."""
        db = make_mock_db()
        existing = make_user(display_name="TakenName")
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(None),      # email check passes
            _scalar_one_or_none(existing),   # display_name taken
        ])

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/register", json={
                    "email": "unique@example.com",
                    "password": "securepass123",
                    "display_name": "TakenName",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 409
        assert "Display name already taken" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_short_password(self):
        """Password shorter than 8 characters is rejected (422)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "short",
                "display_name": "ValidName",
            })

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_display_name(self):
        """Display name shorter than 2 characters is rejected (422)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "securepass123",
                "display_name": "A",
            })

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self):
        """Invalid email format is rejected (422)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/auth/register", json={
                "email": "not-an-email",
                "password": "securepass123",
                "display_name": "ValidName",
            })

        assert resp.status_code == 422


# POST /api/auth/login


class TestLogin:
    """Login endpoint tests."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Valid credentials return 200 + JWT + user."""
        db = make_mock_db()
        user = make_user(email="user@example.com")
        user.password_hash = hash_password("correct_password")
        db.execute = AsyncMock(return_value=_scalar_one_or_none(user))

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "user@example.com",
                    "password": "correct_password",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """Wrong password returns 401."""
        db = make_mock_db()
        user = make_user(email="user@example.com")
        user.password_hash = hash_password("correct_password")
        db.execute = AsyncMock(return_value=_scalar_one_or_none(user))

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "user@example.com",
                    "password": "wrong_password",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self):
        """Email not found returns 401."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))

        async def _override():
            yield db

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/auth/login", json={
                    "email": "nobody@example.com",
                    "password": "anypassword1",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self):
        """Missing required fields returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/auth/login", json={})

        assert resp.status_code == 422


# GET /api/auth/me


class TestMe:
    """GET /api/auth/me endpoint tests."""

    @pytest.mark.asyncio
    async def test_me_valid_token(self):
        """Valid JWT returns 200 + current user data."""
        from app.auth import get_current_user

        user = make_user(email="me@example.com", display_name="MeUser")

        async def _override_auth():
            return user

        app.dependency_overrides[get_current_user] = _override_auth
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "me@example.com"
        assert body["display_name"] == "MeUser"

    @pytest.mark.asyncio
    async def test_me_invalid_token(self):
        """Invalid JWT returns 401 or 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer invalid.token.here"},
            )

        # FastAPI's HTTPBearer + our decode logic should return 401
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_me_no_token(self):
        """No Authorization header returns 401 or 403 (HTTPBearer)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/auth/me")

        assert resp.status_code in (401, 403)
