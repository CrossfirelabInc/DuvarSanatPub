"""Tests for artist claims, moderation, and admin promotion endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Artist, ArtistClaim, User
from tests.conftest import make_mock_db, make_user


# Helpers


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _make_artist(artist_id=None, name="Test Artist", claimed_by_user_id=None, verified_at=None):
    artist = MagicMock(spec=Artist)
    artist.id = artist_id or uuid.uuid4()
    artist.name = name
    artist.bio = None
    artist.artwork_count = 0
    artist.follower_count = 0
    artist.claimed_by_user_id = claimed_by_user_id
    artist.verified_at = verified_at
    artist.website = None
    artist.social_links = None
    artist.aliases = None
    artist.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return artist


def _make_claim(claim_id=None, user_id=None, artist_id=None, status="pending"):
    claim = MagicMock(spec=ArtistClaim)
    claim.id = claim_id or uuid.uuid4()
    claim.user_id = user_id or uuid.uuid4()
    claim.artist_id = artist_id or uuid.uuid4()
    claim.verification_text = "I am this artist, here is proof."
    claim.verification_url = "https://instagram.com/myprofile"
    claim.status = status
    claim.reviewed_by = None
    claim.review_note = None
    claim.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    claim.reviewed_at = None
    return claim


# POST /api/artists/:id/claim


@pytest.mark.anyio
async def test_create_claim_success():
    """Authenticated user can claim an unclaimed artist."""
    user = make_user()
    artist = _make_artist()
    db = make_mock_db()

    # First call: find artist, second call: check existing claim, third: mod list for notifications
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(artist),  # artist lookup
        _scalar_one_or_none(None),    # no existing claim
        _all([]),                     # moderator IDs for notification
    ])

    def _fake_refresh(obj):
        """Simulate DB populating server-generated fields on refresh."""
        if not hasattr(obj, '_refreshed'):
            obj.id = obj.id if obj.id else uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
            obj._refreshed = True

    db.refresh = AsyncMock(side_effect=_fake_refresh)

    async def _override_get_db():
        yield db

    async def _override_auth():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            resp = await client.post(
                f"/api/artists/{artist.id}/claim",
                json={
                    "verification_text": "I am this artist, check my Instagram",
                    "verification_url": "https://instagram.com/me",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["artist_name"] == artist.name
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_create_claim_duplicate_409():
    """Returns 409 if user already has a pending claim for this artist."""
    user = make_user()
    artist = _make_artist()
    existing_claim = _make_claim(user_id=user.id, artist_id=artist.id)
    db = make_mock_db()

    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(artist),
        _scalar_one_or_none(existing_claim),
    ])

    async def _override_get_db():
        yield db

    async def _override_auth():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            resp = await client.post(
                f"/api/artists/{artist.id}/claim",
                json={"verification_text": "I am this artist, check my Instagram"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_create_claim_already_claimed_409():
    """Returns 409 if artist is already claimed by someone."""
    user = make_user()
    artist = _make_artist(claimed_by_user_id=uuid.uuid4())
    db = make_mock_db()

    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(artist),
    ])

    async def _override_get_db():
        yield db

    async def _override_auth():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            resp = await client.post(
                f"/api/artists/{artist.id}/claim",
                json={"verification_text": "I am this artist, check my Instagram"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_create_claim_requires_auth():
    """Returns 401/403 when no auth token is provided."""
    artist_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            f"/api/artists/{artist_id}/claim",
            json={"verification_text": "I am this artist, check my Instagram"},
        )
    assert resp.status_code in (401, 403)


# POST /api/mod/claims/:id/approve


@pytest.mark.anyio
async def test_approve_claim_success():
    """Moderator can approve a pending claim."""
    mod = make_user(role="moderator", display_name="ModUser")
    claim_user = make_user(user_id=uuid.uuid4(), display_name="Claimant", email="claimant@test.com")
    artist = _make_artist()
    claim = _make_claim(user_id=claim_user.id, artist_id=artist.id)

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(claim),     # find claim
        _scalar_one_or_none(artist),    # find artist
        _scalar_one_or_none(claim_user),  # find claimant
    ])
    db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def _override_get_db():
        yield db

    async def _override_auth():
        return mod

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(mod.id, mod.role)
            resp = await client.post(
                f"/api/mod/claims/{claim.id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_approve_claim_requires_mod():
    """Regular user cannot approve claims."""
    user = make_user(role="user")
    db = make_mock_db()

    async def _override_get_db():
        yield db

    async def _override_auth():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            resp = await client.post(
                f"/api/mod/claims/{uuid.uuid4()}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


# POST /api/mod/claims/:id/reject


@pytest.mark.anyio
async def test_reject_claim_success():
    """Moderator can reject a pending claim with a note."""
    mod = make_user(role="moderator", display_name="ModUser")
    claim_user = make_user(user_id=uuid.uuid4(), display_name="Claimant", email="claimant@test.com")
    artist = _make_artist()
    claim = _make_claim(user_id=claim_user.id, artist_id=artist.id)

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(claim),
        _scalar_one_or_none(artist),
        _scalar_one_or_none(claim_user),
    ])
    db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def _override_get_db():
        yield db

    async def _override_auth():
        return mod

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(mod.id, mod.role)
            resp = await client.post(
                f"/api/mod/claims/{claim.id}/reject",
                json={"note": "Insufficient evidence"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


# POST /api/admin/promote


@pytest.mark.anyio
async def test_promote_user_success():
    """Admin can promote a user to moderator."""
    admin = make_user(role="admin", display_name="AdminUser", email="admin@test.com")
    target = make_user(user_id=uuid.uuid4(), display_name="TargetUser", email="target@test.com")

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(target),
    ])
    db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def _override_get_db():
        yield db

    async def _override_auth():
        return admin

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(admin.id, admin.role)
            resp = await client.post(
                "/api/admin/promote",
                json={"user_id": str(target.id), "role": "moderator"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_promote_user_requires_admin():
    """Non-admin cannot promote users."""
    mod = make_user(role="moderator")
    db = make_mock_db()

    async def _override_get_db():
        yield db

    async def _override_auth():
        return mod

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(mod.id, mod.role)
            resp = await client.post(
                "/api/admin/promote",
                json={"user_id": str(uuid.uuid4()), "role": "moderator"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
