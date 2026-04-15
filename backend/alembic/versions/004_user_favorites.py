"""User favorites table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("artwork_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "artwork_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artwork_id"], ["artworks.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("user_favorites")
