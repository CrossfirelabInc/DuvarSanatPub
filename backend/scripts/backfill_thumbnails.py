"""Generate thumbnails for all existing photos that don't have one.

Usage: docker compose exec backend python -m scripts.backfill_thumbnails
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from sqlalchemy import select, update
from app.database import async_session
from app.models import Photo

THUMBNAIL_MAX_SIZE = 400


async def main():
    print("Starting thumbnail backfill...")

    async with async_session() as db:
        result = await db.execute(
            select(Photo.id, Photo.image_url).where(Photo.thumbnail_url.is_(None))
        )
        photos = result.all()
        print(f"Found {len(photos)} photos without thumbnails")

        success = 0
        failed = 0
        for photo in photos:
            try:
                file_path = Path("/app") / photo.image_url.lstrip("/")
                if not file_path.exists():
                    print(f"  SKIP {photo.id}: file not found")
                    failed += 1
                    continue

                img = Image.open(file_path)
                img.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE), Image.LANCZOS)

                thumb_dir = Path("/app/uploads/thumbs")
                thumb_dir.mkdir(parents=True, exist_ok=True)

                original_filename = Path(photo.image_url).name
                thumb_filename = f"thumb_{original_filename}"
                thumb_path = thumb_dir / thumb_filename
                img.save(str(thumb_path), quality=85, optimize=True)

                thumb_url = f"/uploads/thumbs/{thumb_filename}"
                await db.execute(
                    update(Photo)
                    .where(Photo.id == photo.id)
                    .values(thumbnail_url=thumb_url)
                )
                success += 1
            except Exception as e:
                print(f"  FAIL {photo.id}: {e}")
                failed += 1

        await db.commit()
        print(f"Done! {success} thumbnails generated, {failed} failed out of {len(photos)}")


if __name__ == "__main__":
    asyncio.run(main())
