"""User follows table and follower_count columns.

Revision ID: 005
Revises: 004
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followed_artist_id", sa.Uuid(), nullable=True),
        sa.Column("followed_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followed_artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followed_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "(followed_artist_id IS NOT NULL AND followed_user_id IS NULL) OR "
            "(followed_artist_id IS NULL AND followed_user_id IS NOT NULL)",
            name="ck_user_follows_exactly_one",
        ),
        sa.UniqueConstraint("follower_id", "followed_artist_id", name="uq_user_follows_artist"),
        sa.UniqueConstraint("follower_id", "followed_user_id", name="uq_user_follows_user"),
    )
    op.create_index("ix_user_follows_follower", "user_follows", ["follower_id"])
    op.create_index(
        "ix_user_follows_artist",
        "user_follows",
        ["followed_artist_id"],
        postgresql_where=sa.text("followed_artist_id IS NOT NULL"),
    )
    op.create_index(
        "ix_user_follows_user",
        "user_follows",
        ["followed_user_id"],
        postgresql_where=sa.text("followed_user_id IS NOT NULL"),
    )

    # Add follower_count columns for fast reads
    op.add_column("artists", sa.Column("follower_count", sa.Integer(), server_default="0"))
    op.add_column("users", sa.Column("follower_count", sa.Integer(), server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "follower_count")
    op.drop_column("artists", "follower_count")
    op.drop_index("ix_user_follows_user", "user_follows")
    op.drop_index("ix_user_follows_artist", "user_follows")
    op.drop_index("ix_user_follows_follower", "user_follows")
    op.drop_table("user_follows")
