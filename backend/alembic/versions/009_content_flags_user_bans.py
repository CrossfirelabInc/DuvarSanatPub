"""Add content flags table and banned_at column on users.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Content flags / reports
    op.create_table(
        "content_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reporter_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),  # photo, comment, artwork, user
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),  # inappropriate, spam, harassment, other
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending, reviewed, dismissed
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_content_flags_target", "content_flags", ["target_type", "target_id"])
    op.create_index("ix_content_flags_status", "content_flags", ["status"])
    op.create_index("ix_content_flags_reporter", "content_flags", ["reporter_id"])

    # User ban column
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "banned_at")
    op.drop_index("ix_content_flags_reporter")
    op.drop_index("ix_content_flags_status")
    op.drop_index("ix_content_flags_target")
    op.drop_table("content_flags")
