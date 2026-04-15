"""Compute style embeddings for all photos that don't have one yet.

Usage: docker compose exec backend python -m scripts.backfill_style_embeddings
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path so 'app' is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from app.database import async_session
from app.models import Photo
from app.clip_service import clip_service


async def main():
    print("Loading CLIP model...")
    clip_service.load()
    print("Model loaded. Starting style embedding backfill...")

    async with async_session() as db:
        result = await db.execute(
            select(Photo.id, Photo.image_url).where(Photo.style_embedding.is_(None))
        )
        photos = result.all()
        print(f"Found {len(photos)} photos without style embeddings")

        success = 0
        failed = 0
        for photo in photos:
            try:
                # Read the image file
                # image_url is like /uploads/filename.jpg
                file_path = Path("/app") / photo.image_url.lstrip("/")
                if not file_path.exists():
                    print(f"  SKIP {photo.id}: file not found at {file_path}")
                    failed += 1
                    continue

                image_bytes = file_path.read_bytes()
                style_embedding = clip_service.compute_style_embedding(image_bytes)

                await db.execute(
                    update(Photo)
                    .where(Photo.id == photo.id)
                    .values(style_embedding=style_embedding)
                )
                success += 1
                if success % 10 == 0:
                    print(f"  Processed {success}/{len(photos)}...")
            except Exception as e:
                print(f"  FAIL {photo.id}: {e}")
                failed += 1

        await db.commit()
        print(f"Done! {success} updated, {failed} failed out of {len(photos)}")


if __name__ == "__main__":
    asyncio.run(main())
