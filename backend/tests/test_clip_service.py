"""Unit tests for CLIPService.

The actual CLIP model is heavy (~300MB) and not available in CI,
so all model interactions are mocked.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO

from app.clip_service import CLIPService


# Helpers

def _make_fake_embedding(dim: int = 512) -> np.ndarray:
    """Return a random L2-normalized numpy vector."""
    vec = np.random.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec


def _create_minimal_png() -> bytes:
    """Return the smallest valid PNG bytes (1x1 red pixel)."""
    # Easiest via Pillow if available
    from PIL import Image
    buf = BytesIO()
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_minimal_jpeg() -> bytes:
    """Return a minimal valid JPEG."""
    from PIL import Image
    buf = BytesIO()
    img = Image.new("RGB", (1, 1), color=(0, 0, 255))
    img.save(buf, format="JPEG")
    return buf.getvalue()


# Tests


class TestCLIPServiceInit:

    def test_initial_state(self):
        service = CLIPService()
        assert service.is_loaded is False
        assert service.model is None
        assert service.preprocess is None
        assert service.device == "cpu"


class TestCLIPServiceLoad:

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_load_sets_loaded_flag(self, mock_create):
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = None
        mock_preprocess = MagicMock()

        mock_create.return_value = (mock_model, None, mock_preprocess)

        service = CLIPService()
        service.load()

        assert service.is_loaded is True
        assert service.model is mock_model
        assert service.preprocess is mock_preprocess
        mock_model.to.assert_called_once_with("cpu")
        mock_model.eval.assert_called_once()

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_load_calls_correct_model(self, mock_create):
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()

        mock_create.assert_called_once_with("ViT-B-16", pretrained="laion2b_s34b_b88k")


class TestCLIPServiceComputeEmbedding:

    def test_raises_if_not_loaded(self):
        service = CLIPService()
        with pytest.raises(RuntimeError, match="CLIP model is not loaded"):
            service.compute_embedding(b"fake image bytes")

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    @patch("app.clip_service.torch")
    def test_compute_returns_list_of_floats(self, mock_torch, mock_create):
        """After loading, compute_embedding should return a list[float] of length 512."""
        # Setup mock model
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        fake_emb = _make_fake_embedding(512)

        import torch
        # Mock the embedding tensor chain
        embedding_tensor = MagicMock()
        embedding_tensor.norm.return_value = MagicMock()
        embedding_tensor.__truediv__ = MagicMock(return_value=embedding_tensor)
        squeeze_result = MagicMock()
        cpu_result = MagicMock()
        cpu_result.numpy.return_value = fake_emb
        squeeze_result.cpu.return_value = cpu_result
        embedding_tensor.squeeze.return_value = squeeze_result

        # norm returns a tensor
        norm_tensor = MagicMock()
        embedding_tensor.norm.return_value = norm_tensor
        # division returns normalized embedding
        embedding_tensor.__truediv__ = lambda self, other: embedding_tensor

        mock_model.encode_image.return_value = embedding_tensor

        # Setup mock preprocess
        mock_preprocess = MagicMock()
        preprocess_result = MagicMock()
        preprocess_result.unsqueeze.return_value = MagicMock()
        preprocess_result.unsqueeze.return_value.to.return_value = MagicMock()
        mock_preprocess.return_value = preprocess_result

        mock_create.return_value = (mock_model, None, mock_preprocess)

        # Use no_grad context manager mock
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        service = CLIPService()
        service.load()

        png_bytes = _create_minimal_png()
        result = service.compute_embedding(png_bytes)

        assert isinstance(result, list)
        assert len(result) == 512
        assert all(isinstance(x, (float, np.floating)) for x in result)

    def test_is_loaded_property_false_initially(self):
        service = CLIPService()
        assert service.is_loaded is False

    @patch("app.clip_service.open_clip.create_model_and_transforms")
    def test_is_loaded_property_true_after_load(self, mock_create):
        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_create.return_value = (mock_model, None, MagicMock())

        service = CLIPService()
        service.load()
        assert service.is_loaded is True
