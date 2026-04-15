"""Add moderation audit log table and soft-delete columns.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Moderation audit log — tracks all mod actions for accountability and revert
    op.create_table(
        "moderation_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("moderator_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),  # delete_photo, delete_comment, delete_artwork, restore_photo, etc.
        sa.Column("target_type", sa.String(20), nullable=False),  # photo, comment, artwork
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("flag_id", UUID(as_uuid=True), sa.ForeignKey("content_flags.id"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_moderation_log_target", "moderation_log", ["target_type", "target_id"])
    op.create_index("ix_moderation_log_moderator", "moderation_log", ["moderator_id"])

    # Soft-delete on photos (comments already have is_deleted)
    op.add_column("photos", sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False))

    # Soft-delete on artworks
    op.add_column("artworks", sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False))

    # Downvote count on photos (hidden, for community filtering)
    op.add_column("photos", sa.Column("downvote_count", sa.Integer, server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("photos", "downvote_count")
    op.drop_column("artworks", "is_deleted")
    op.drop_column("photos", "is_deleted")
    op.drop_index("ix_moderation_log_moderator")
    op.drop_index("ix_moderation_log_target")
    op.drop_table("moderation_log")
