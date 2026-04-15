"""Unit tests for auth utility functions (hash, verify, JWT creation/decode).

These tests exercise the pure functions in app.auth without touching the
database or making HTTP requests.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.auth import create_access_token, hash_password, verify_password
from app.config import settings


# Password hashing


class TestHashPassword:

    def test_returns_bcrypt_hash(self):
        """Hash should start with the bcrypt prefix."""
        hashed = hash_password("my_password")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_different_hashes_for_same_input(self):
        """Bcrypt includes a random salt, so two hashes of the same password differ."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_hash_is_string(self):
        assert isinstance(hash_password("test"), str)


class TestVerifyPassword:

    def test_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


# JWT creation


class TestCreateAccessToken:

    def test_returns_string(self):
        token = create_access_token(uuid.uuid4(), "user")
        assert isinstance(token, str)

    def test_token_contains_sub_and_role(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "admin")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == str(uid)
        assert payload["role"] == "admin"

    def test_token_has_expiry(self):
        token = create_access_token(uuid.uuid4(), "user")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        # Expiry should be roughly JWT_EXPIRE_DAYS from now
        expected = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
        # Allow 10 seconds of drift
        assert abs((exp - expected).total_seconds()) < 10

    def test_token_decodable_with_correct_secret(self):
        token = create_access_token(uuid.uuid4(), "user")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert "sub" in payload

    def test_token_not_decodable_with_wrong_secret(self):
        token = create_access_token(uuid.uuid4(), "user")
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret", algorithms=[settings.JWT_ALGORITHM])

    def test_different_users_get_different_tokens(self):
        t1 = create_access_token(uuid.uuid4(), "user")
        t2 = create_access_token(uuid.uuid4(), "user")
        assert t1 != t2
