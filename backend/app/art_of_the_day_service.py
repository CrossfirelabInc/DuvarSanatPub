"""Art of the Day selection logic."""

import hashlib
from datetime import date


def pick_artwork_id(
    eligible_ids: list[str],
    recently_featured_ids: set[str],
    today: date,
    secret: str,
) -> str | None:
    """Deterministically pick an artwork ID for the given date.

    1. Filter out recently featured IDs.
    2. If all are excluded, fall back to the full list.
    3. Use hash(date + secret) as a deterministic seed to index into the list.

    Returns None if eligible_ids is empty.
    """
    if not eligible_ids:
        return None

    candidates = [i for i in eligible_ids if i not in recently_featured_ids]
    if not candidates:
        candidates = eligible_ids

    seed = hashlib.sha256(f"{today.isoformat()}:{secret}".encode()).hexdigest()
    index = int(seed, 16) % len(candidates)
    return candidates[index]
