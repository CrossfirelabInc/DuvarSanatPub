"""Add site_settings table for admin feature toggles.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Seed default feature toggles (all enabled)
    op.execute("""
        INSERT INTO site_settings (key, value) VALUES
            ('dm_enabled', 'true'),
            ('tours_enabled', 'true'),
            ('ai_naming_enabled', 'true'),
            ('challenges_enabled', 'true'),
            ('flags_enabled', 'true'),
            ('activity_feed_enabled', 'true'),
            ('nsfw_detection_enabled', 'true'),
            ('art_of_the_day_enabled', 'true')
    """)


def downgrade() -> None:
    op.drop_table("site_settings")
