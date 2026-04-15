"""CLIP image embedding service.

Loads the CLIP model (ViT-B-16, laion2b_s34b_b88k) at application startup
and provides a function to compute 512-dimensional image embeddings,
style embeddings, and NSFW content detection via zero-shot classification.
"""

from io import BytesIO
from typing import Any

import numpy as np
import open_clip
import torch
import torchvision.transforms as T
from PIL import Image

# NSFW detection text prompts for zero-shot classification
SAFE_PROMPTS = [
    "a photo of street art",
    "a photo of a mural",
    "a photo of graffiti on a wall",
    "a photo of a building",
    "a photo of urban art",
]

UNSAFE_PROMPTS = [
    "a photo of nudity",
    "a photo of pornography",
    "a photo of explicit sexual content",
    "a photo of violence and gore",
    "a photo of child abuse",
]


class CLIPService:
    """Singleton-style service that holds the loaded CLIP model and preprocess transform."""

    def __init__(self) -> None:
        self.model: Any = None
        self.preprocess: Any = None
        self.device: str = "cpu"
        self._loaded: bool = False
        self._tokenizer: Any = None

    def load(self) -> None:
        """Load the CLIP model and preprocessing transform.

        Should be called once at application startup (via FastAPI lifespan).
        Takes ~2-3 seconds and ~300MB RAM on CPU.
        """
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-16", pretrained="laion2b_s34b_b88k"
        )
        model = model.to(self.device)
        model.eval()
        self.model = model
        self.preprocess = preprocess
        # Squash-resize transform: preserves all image content instead of
        # center-cropping, which loses 50%+ of wide/panoramic street art photos.
        # Uses the same normalization as CLIP's default preprocessing.
        self._squash_transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(
                mean=(0.48145466, 0.4578275, 0.40821073),
                std=(0.26862954, 0.26130258, 0.27577711),
            ),
        ])
        self._tokenizer = open_clip.get_tokenizer("ViT-B-16")
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def compute_embedding(self, image_bytes: bytes) -> list[float]:
        """Compute a 512-dim L2-normalized CLIP embedding from raw image bytes.

        Args:
            image_bytes: Raw bytes of a JPEG or PNG image.

        Returns:
            A list of 512 floats representing the normalized image embedding.

        Raises:
            RuntimeError: If the model has not been loaded yet.
        """
        if not self._loaded:
            raise RuntimeError("CLIP model is not loaded")

        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        # Use squash-resize instead of CLIP's default center-crop to preserve
        # all image content — critical for wide/panoramic street art photos.
        tensor = self._squash_transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            embedding = self.model.encode_image(tensor)

        # L2-normalize the embedding (required for cosine similarity)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)

        # Convert to plain Python list of floats
        return embedding.squeeze(0).cpu().numpy().tolist()

    def check_nsfw(self, image_bytes: bytes) -> tuple[bool, float]:
        """Check if image is NSFW using CLIP zero-shot classification.

        Returns (is_safe, safety_score) where safety_score is 0-1.
        Higher score = more likely safe. Uses the already-loaded CLIP model
        to compare the image embedding against safe and unsafe text prompts.

        If the model is not loaded, fails open (returns safe).
        """
        if not self._loaded:
            return True, 1.0  # Fail open if model not loaded

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        safe_tokens = self._tokenizer(SAFE_PROMPTS).to(self.device)
        unsafe_tokens = self._tokenizer(UNSAFE_PROMPTS).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            safe_text_features = self.model.encode_text(safe_tokens)
            unsafe_text_features = self.model.encode_text(unsafe_tokens)

            # Normalize
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            safe_text_features = safe_text_features / safe_text_features.norm(dim=-1, keepdim=True)
            unsafe_text_features = unsafe_text_features / unsafe_text_features.norm(dim=-1, keepdim=True)

            # Compute similarities
            safe_sim = (image_features @ safe_text_features.T).max().item()
            unsafe_sim = (image_features @ unsafe_text_features.T).max().item()

        # Safety score: how much more similar to safe than unsafe
        safety_score = safe_sim / (safe_sim + unsafe_sim) if (safe_sim + unsafe_sim) > 0 else 0.5

        is_safe = safety_score > 0.45  # Threshold: if less than 45% safe, reject

        return is_safe, round(safety_score, 4)

    def suggest_title(self, image_bytes: bytes) -> str | None:
        """Generate an artistic title using CLIP zero-shot classification.

        Uses the already-loaded CLIP model to classify the image against
        descriptive terms (style, subject, color, mood) and composes a
        creative title. No extra model or memory needed.
        """
        if not self._loaded:
            return None

        import random

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image_tensor = self._squash_transform(image).unsqueeze(0).to(self.device)

            # Categories to classify against
            styles = [
                "mural", "stencil art", "graffiti tag", "wheat paste",
                "mosaic", "portrait", "abstract art", "geometric shapes",
                "calligraphy", "illustration",
            ]
            subjects = [
                "a human face", "an animal", "a bird", "flowers and plants",
                "a cityscape", "eyes", "hands", "a cat",
                "political message", "fantasy creature", "a woman", "a man",
            ]
            moods = [
                "colorful and vibrant", "dark and moody", "whimsical and playful",
                "bold and striking", "peaceful and serene", "raw and gritty",
            ]

            # Encode image once, reuse for all classifications
            with torch.no_grad():
                img_feat = self.model.encode_image(image_tensor)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)

            def _rank(prompts: list[str]) -> list[tuple[str, float]]:
                tokens = self._tokenizer(
                    [f"a photo of {p}" for p in prompts]
                ).to(self.device)
                with torch.no_grad():
                    txt_feat = self.model.encode_text(tokens)
                    txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)
                    sims = (img_feat @ txt_feat.T).squeeze(0)
                return sorted(
                    zip(prompts, sims.cpu().numpy().tolist()),
                    key=lambda x: x[1],
                    reverse=True,
                )

            def _best(words: list[str]) -> str:
                """Pick the word most relevant to the image via CLIP."""
                tokens = self._tokenizer(words).to(self.device)
                with torch.no_grad():
                    txt_feat = self.model.encode_text(tokens)
                    txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)
                    sims = (img_feat @ txt_feat.T).squeeze(0)
                return words[sims.argmax().item()]

            top_style = _rank(styles)[0][0]
            top_subject = _rank(subjects)[0][0]
            top_mood = _rank(moods)[0][0]
            mood_word = top_mood.split(" and ")[0].strip()
            clean_subject = top_subject.replace("a ", "").replace("an ", "").title()

            # Evocative words — CLIP picks the one most fitting the image
            style_vibes = {
                "mural": ["Canvas", "Chronicle", "Saga", "Epic", "Tapestry"],
                "stencil art": ["Shadow", "Silhouette", "Echo", "Ghost", "Phantom"],
                "graffiti tag": ["Rebel", "Voice", "Cipher", "Signal", "Pulse"],
                "wheat paste": ["Whisper", "Fragment", "Memory", "Remnant", "Trace"],
                "mosaic": ["Kaleidoscope", "Prism", "Fracture", "Spectrum", "Puzzle"],
                "portrait": ["Gaze", "Soul", "Spirit", "Persona", "Mask"],
                "abstract art": ["Dream", "Vortex", "Flux", "Chaos", "Mirage"],
                "geometric shapes": ["Blueprint", "Grid", "Matrix", "Tessellation", "Orbit"],
                "calligraphy": ["Verse", "Script", "Hymn", "Psalm", "Ink"],
                "illustration": ["Fable", "Sketch", "Tale", "Myth", "Legend"],
            }
            mood_vibes = {
                "colorful": ["Carnival", "Bloom", "Fireworks", "Confetti", "Neon"],
                "dark": ["Noir", "Midnight", "Dusk", "Abyss", "Obsidian"],
                "whimsical": ["Wonderland", "Daydream", "Fantasy", "Reverie", "Fairy"],
                "bold": ["Thunder", "Blaze", "Anthem", "Fortress", "Empire"],
                "peaceful": ["Serenade", "Lullaby", "Haven", "Oasis", "Dawn"],
                "raw": ["Concrete", "Rust", "Asphalt", "Grit", "Wire"],
            }

            sv = _best(style_vibes.get(top_style, ["Vision"]))
            mv = _best(mood_vibes.get(mood_word, ["Street"]))

            # Build candidate titles and let CLIP pick the best one
            candidates = [
                f"{sv} of {clean_subject}",
                f"{clean_subject} {sv}",
                f"{mv} {sv}",
                f"The {clean_subject} {sv}",
                f"{mv} {clean_subject}",
                f"{clean_subject} in {mv}",
                f"{sv} & {mv}",
                f"The {mv} {clean_subject}",
            ]

            subject_extras = {
                "Human Face": [f"Face of {mv}", f"The {sv} Gaze", f"Portrait in {mv}"],
                "Eyes": [f"Eyes of {mv}", f"The Watching {sv}", f"Thousand-Yard {sv}"],
                "Cat": [f"Alley {sv}", f"Nine Lives in {mv}", f"The {mv} Cat"],
                "Bird": [f"Wings of {mv}", f"Flight {sv}", f"The {sv} Song"],
                "Flowers And Plants": [f"Bloom of {mv}", f"Wild {sv}", f"Garden {sv}"],
                "Fantasy Creature": [f"{mv} Beast", f"The {sv} Creature", f"Myth of {mv}"],
                "Woman": [f"Her {sv}", f"The {mv} Muse", f"Femme {sv}"],
                "Man": [f"His {sv}", f"The {mv} Figure", f"Homme {sv}"],
                "Animal": [f"Wild {sv}", f"The {mv} Beast", f"Creature of {mv}"],
                "Hands": [f"Reach of {mv}", f"The {sv} Touch", f"Hands of {mv}"],
            }
            if clean_subject in subject_extras:
                candidates.extend(subject_extras[clean_subject])

            # CLIP ranks all candidate titles against the image — best match wins
            ranked = _rank(candidates)
            # Return top pick, but add slight randomness among top 3 to avoid staleness
            top3 = [t for t, _ in ranked[:3]]
            return random.choice(top3)

        except Exception:
            return None

    def compute_style_embedding(self, image_bytes: bytes) -> list[float]:
        """Compute a 256-dim style embedding using color, texture, and edge features.

        Captures artistic STYLE (color palette, texture, technique) rather than
        semantic CONTENT. Two photos of completely different subjects by the same
        artist should produce similar style embeddings.

        Args:
            image_bytes: Raw bytes of a JPEG or PNG image.

        Returns:
            A list of 256 floats representing the L2-normalized style embedding.

        Raises:
            RuntimeError: If the model has not been loaded yet.
        """
        if not self._loaded:
            raise RuntimeError("CLIP model is not loaded")

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(image.resize((224, 224)))

        # Color histogram (3 channels x 32 bins = 96 dims)
        color_features: list[float] = []
        for channel in range(3):
            hist, _ = np.histogram(img_array[:, :, channel], bins=32, range=(0, 256))
            hist = hist.astype(np.float32) / hist.sum()
            color_features.extend(hist.tolist())

        # Texture features using local variance (8x8 grid = 64 dims)
        texture_features: list[float] = []
        h, w = img_array.shape[:2]
        gray = np.mean(img_array, axis=2)
        grid_h, grid_w = h // 8, w // 8
        for i in range(8):
            for j in range(8):
                patch = gray[i * grid_h : (i + 1) * grid_h, j * grid_w : (j + 1) * grid_w]
                texture_features.append(float(np.std(patch)))

        # Edge density features (8x8 grid = 64 dims)
        edge_features: list[float] = []
        gy = np.diff(gray, axis=0)
        gx = np.diff(gray, axis=1)
        # Make same size
        min_h = min(gx.shape[0], gy.shape[0])
        min_w = min(gx.shape[1], gy.shape[1])
        gy = gy[:min_h, :min_w]
        gx = gx[:min_h, :min_w]
        edges = np.sqrt(gx**2 + gy**2)
        eh, ew = edges.shape
        gh, gw = eh // 8, ew // 8
        for i in range(8):
            for j in range(8):
                patch = edges[i * gh : (i + 1) * gh, j * gw : (j + 1) * gw]
                edge_features.append(float(np.mean(patch)))

        # Dominant color features (32 dims) - quantized color histogram
        pixels = img_array.reshape(-1, 3)
        quantized = (pixels // 32).astype(np.uint8)
        color_ids = quantized[:, 0] * 64 + quantized[:, 1] * 8 + quantized[:, 2]
        hist_full, _ = np.histogram(color_ids, bins=32, range=(0, 512))
        hist_full = hist_full.astype(np.float32) / hist_full.sum()
        dominant_features = hist_full.tolist()

        # Combine: 96 + 64 + 64 + 32 = 256 dims
        style_vector = color_features + texture_features + edge_features + dominant_features

        # L2 normalize
        norm = np.linalg.norm(style_vector)
        if norm > 0:
            style_vector = (np.array(style_vector) / norm).tolist()

        return style_vector


# Module-level singleton
clip_service = CLIPService()
