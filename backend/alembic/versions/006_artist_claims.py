"""Artist claims table and claimed_by_user_id column.

Revision ID: 006
Revises: 005
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artist_claims",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("artist_id", sa.Uuid(), nullable=False),
        sa.Column("verification_text", sa.Text(), nullable=False),
        sa.Column("verification_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.UniqueConstraint("user_id", "artist_id", name="uq_artist_claims_user_artist"),
    )

    op.add_column(
        "artists",
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint("uq_artists_claimed_by_user_id", "artists", ["claimed_by_user_id"])
    op.create_foreign_key(
        "fk_artists_claimed_by_user_id",
        "artists",
        "users",
        ["claimed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_artists_claimed_by_user_id", "artists", type_="foreignkey")
    op.drop_constraint("uq_artists_claimed_by_user_id", "artists", type_="unique")
    op.drop_column("artists", "claimed_by_user_id")
    op.drop_table("artist_claims")
