"""Promote a user to admin by email.

Usage:
    python -m scripts.make_admin seed@duvarsanat.com
"""

import asyncio
import sys

from sqlalchemy import select, update

from app.database import async_session
from app.models import User


async def promote(email: str) -> None:
    """Set user.role = 'admin' for the given email."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"ERROR: No user found with email '{email}'", file=sys.stderr)
            sys.exit(1)

        if user.role == "admin":
            print(f"User '{user.display_name}' ({email}) is already an admin.")
            return

        old_role = user.role
        await session.execute(
            update(User).where(User.id == user.id).values(role="admin")
        )
        await session.commit()
        print(f"Promoted '{user.display_name}' ({email}) from '{old_role}' to 'admin'.")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.make_admin <email>", file=sys.stderr)
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(promote(email))


if __name__ == "__main__":
    main()
