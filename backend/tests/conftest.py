"""Shared test fixtures for the DuvarSanat backend test suite.

Sets JWT_SECRET env var BEFORE any app module is imported to prevent
config.py from calling sys.exit(1).  All fixtures that touch the FastAPI
app override the get_db and get_current_user dependencies so that no real
PostgreSQL / PostGIS connection is needed.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET"] = "test-secret-key-not-change-me"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"  # unused, but avoids connection attempts
os.environ["UPLOAD_DIR"] = "./test_uploads"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.auth import create_access_token, get_current_user  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


# Fake DB session

def make_mock_db() -> AsyncMock:
    """Return an AsyncMock that behaves enough like an AsyncSession."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# Fake user objects

def make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    display_name: str = "TestUser",
    role: str = "user",
    bio: str | None = None,
) -> MagicMock:
    """Create a mock that behaves like a User model instance.

    Uses MagicMock because SQLAlchemy mapped classes cannot have attributes
    set via __setattr__ without a proper session/instrumentation context.
    """
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.display_name = display_name
    user.password_hash = "$2b$12$fake_hash"  # not a real hash
    user.bio = bio
    user.role = role
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    # columns with defaults
    user.tagline = None
    user.website = None
    user.social_links = None
    user.avatar_url = None
    user.total_votes_received = 0
    user.follower_count = 0
    user.profile_type = "explorer"
    return user


# Fixtures

@pytest.fixture()
def mock_db():
    """Provide a mock AsyncSession and override the get_db dependency."""
    db = make_mock_db()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def test_user() -> User:
    """A default test user."""
    return make_user()


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization header dict containing a valid JWT for test_user."""
    token = create_access_token(test_user.id, test_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def override_auth(test_user: User):
    """Override get_current_user so endpoints skip real DB lookup."""

    async def _override():
        return test_user

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTPX client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture()
async def authed_client(
    client: AsyncClient,
    auth_headers: dict[str, str],
    override_auth,
    mock_db,
) -> AsyncClient:
    """Client pre-configured with auth headers + mocked DB + mocked auth."""
    client.headers.update(auth_headers)
    return client
