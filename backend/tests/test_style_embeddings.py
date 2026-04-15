"""Tests for the style embedding feature.

Covers: compute_style_embedding, style-similar endpoints for artworks and artists.
"""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.clip_service import CLIPService


# Helpers


def _create_test_image(width: int = 224, height: int = 224) -> bytes:
    """Create a test image with varied colors for meaningful style features."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_solid_image(color: tuple = (255, 0, 0)) -> bytes:
    """Create a solid-color test image."""
    img = Image.new("RGB", (224, 224), color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# CLIPService.compute_style_embedding tests


class TestComputeStyleEmbedding:

    def test_raises_if_not_loaded(self):
        """Should raise RuntimeError if model is not loaded."""
        service = CLIPService()
        with pytest.raises(RuntimeError, match="CLIP model is not loaded"):
            service.compute_style_embedding(b"fake bytes")

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_returns_256_dim_list(self, mock_create):
        """After loading, compute_style_embedding should return a list of 256 floats."""
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()

        image_bytes = _create_test_image()
        result = service.compute_style_embedding(image_bytes)

        assert isinstance(result, list)
        assert len(result) == 256
        assert all(isinstance(x, float) for x in result)

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_output_is_l2_normalized(self, mock_create):
        """The output vector should be L2-normalized (unit length)."""
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()

        image_bytes = _create_test_image()
        result = service.compute_style_embedding(image_bytes)

        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_different_images_produce_different_embeddings(self, mock_create):
        """Different images should produce different style embeddings."""
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()

        img1 = _create_solid_image((255, 0, 0))
        img2 = _create_solid_image((0, 0, 255))

        emb1 = service.compute_style_embedding(img1)
        emb2 = service.compute_style_embedding(img2)

        # Embeddings should differ
        assert emb1 != emb2

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_accepts_jpeg(self, mock_create):
        """Should work with JPEG images too."""
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()

        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        result = service.compute_style_embedding(jpeg_bytes)
        assert len(result) == 256


# Style-similar endpoint tests (artworks)


class TestStyleSimilarArtworkEndpoint:

    @pytest.mark.anyio
    async def test_returns_empty_list_when_no_embeddings(self, authed_client):
        """Should return empty list when artwork has no style embeddings."""
        from app.database import get_db
        from app.main import app

        artwork_id = uuid.uuid4()

        mock_db = AsyncMock()
        # First query: get style embeddings -> empty
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override

        response = await authed_client.get(f"/api/artworks/{artwork_id}/style-similar")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.pop(get_db, None)

    @pytest.mark.anyio
    async def test_returns_list_shape(self, authed_client):
        """Should return a list of StyleSimilarArtworkItem-shaped objects."""
        from app.database import get_db
        from app.main import app

        artwork_id = uuid.uuid4()
        other_artwork_id = uuid.uuid4()

        # Create a fake style embedding
        fake_embedding = np.random.randn(256).astype(np.float32)
        fake_embedding = (fake_embedding / np.linalg.norm(fake_embedding)).tolist()

        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute(query, *args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_result = MagicMock()
            if call_count == 1:
                # First call: get style embeddings for this artwork
                mock_result.all.return_value = [(fake_embedding,)]
            else:
                # Subsequent calls: return similar artworks
                mock_result.all.return_value = []
            return mock_result

        mock_db.execute = mock_execute

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override

        response = await authed_client.get(f"/api/artworks/{artwork_id}/style-similar")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

        app.dependency_overrides.pop(get_db, None)


# Style-similar endpoint tests (artists)


class TestStyleSimilarArtistEndpoint:

    @pytest.mark.anyio
    async def test_returns_404_for_nonexistent_artist(self, authed_client):
        """Should return 404 when artist doesn't exist."""
        from app.database import get_db
        from app.main import app

        artist_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override

        response = await authed_client.get(f"/api/artists/{artist_id}/style-similar")

        assert response.status_code == 404

        app.dependency_overrides.pop(get_db, None)

    @pytest.mark.anyio
    async def test_returns_empty_when_no_style_embeddings(self, authed_client):
        """Should return empty list when artist's photos have no style embeddings."""
        from app.database import get_db
        from app.main import app

        artist_id = uuid.uuid4()

        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute(query, *args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_result = MagicMock()
            if call_count == 1:
                # First call: check artist exists
                mock_result.scalar_one_or_none.return_value = MagicMock(id=artist_id)
            elif call_count == 2:
                # Second call: get style embeddings -> empty
                mock_result.all.return_value = []
            return mock_result

        mock_db.execute = mock_execute

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override

        response = await authed_client.get(f"/api/artists/{artist_id}/style-similar")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.pop(get_db, None)
