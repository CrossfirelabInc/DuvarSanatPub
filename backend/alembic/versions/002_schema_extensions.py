"""Schema extensions: new tables and column additions.

Revision ID: 002
Revises: 001
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PART 1: Column additions to existing tables

    op.add_column("users", sa.Column("tagline", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("social_links", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "total_votes_received",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column("artists", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("artists", sa.Column("social_links", sa.JSON(), nullable=True))
    op.add_column(
        "artists",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TABLE artists ADD COLUMN aliases VARCHAR[]")

    op.add_column(
        "photos",
        sa.Column("vote_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "photos",
        sa.Column("vote_count_night", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "photos",
        sa.Column("vote_count_day", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "photos",
        sa.Column(
            "vote_count_seasonal", sa.Integer(), nullable=False, server_default="0"
        ),
    )

    op.execute(
        "CREATE INDEX ix_photos_artwork_votes "
        "ON photos (artwork_id, vote_count DESC)"
    )

    # PART 2: New tables

    op.create_table(
        "art_of_the_day",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "artwork_id",
            sa.Uuid(),
            sa.ForeignKey("artworks.id"),
            nullable=False,
        ),
        sa.Column("featured_date", sa.Date(), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_art_of_the_day_featured_date",
        "art_of_the_day",
        [sa.text("featured_date DESC")],
    )
    op.create_index(
        "ix_art_of_the_day_artwork_id", "art_of_the_day", ["artwork_id"]
    )

    op.create_table(
        "photo_votes",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            sa.Uuid(),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(20),
            nullable=False,
            server_default="overall",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "photo_id", "category", name="uq_photo_votes_user_photo_cat"
        ),
    )
    op.create_index("ix_photo_votes_photo_id", "photo_votes", ["photo_id"])
    op.create_index(
        "ix_photo_votes_user_created",
        "photo_votes",
        ["user_id", sa.text("created_at DESC")],
    )

    # PART 3: New tables

    op.create_table(
        "conversations",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_conversations_updated_at",
        "conversations",
        [sa.text("updated_at DESC")],
    )

    op.create_table(
        "conversation_participants",
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("conversation_id", "user_id"),
    )
    op.create_index(
        "ix_conv_participants_user_id",
        "conversation_participants",
        ["user_id"],
    )

    op.create_table(
        "messages",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.execute(
        "CREATE INDEX ix_messages_unread ON messages (conversation_id, read_at) "
        "WHERE read_at IS NULL"
    )

    op.create_table(
        "user_blocks",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "blocker_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blocked_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        sa.CheckConstraint(
            "blocker_id != blocked_id", name="ck_user_blocks_no_self_block"
        ),
    )
    op.create_index("ix_user_blocks_blocked_id", "user_blocks", ["blocked_id"])

    op.create_table(
        "leaderboard_entries",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "artist_id",
            sa.Uuid(),
            sa.ForeignKey("artists.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("board_type", sa.String(50), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "board_type", "period", "rank", name="uq_leaderboard_board_period_rank"
        ),
        sa.CheckConstraint(
            "user_id IS NOT NULL OR artist_id IS NOT NULL",
            name="ck_leaderboard_has_entity",
        ),
    )
    op.create_index(
        "ix_leaderboard_board_period",
        "leaderboard_entries",
        ["board_type", "period", "rank"],
    )
    op.execute(
        "CREATE INDEX ix_leaderboard_user_id ON leaderboard_entries (user_id) "
        "WHERE user_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_leaderboard_artist_id ON leaderboard_entries (artist_id) "
        "WHERE artist_id IS NOT NULL"
    )

    op.create_table(
        "user_badges",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("badge_type", sa.String(50), nullable=False),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "badge_type", name="uq_user_badges_user_type"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])


def downgrade() -> None:
    # Drop new tables in reverse dependency order
    op.drop_table("user_badges")
    op.drop_table("leaderboard_entries")
    op.drop_table("user_blocks")
    op.drop_table("messages")
    op.drop_table("conversation_participants")
    op.drop_table("conversations")
    op.drop_table("photo_votes")
    op.drop_table("art_of_the_day")

    # Drop new indexes on existing tables
    op.drop_index("ix_photos_artwork_votes", table_name="photos")

    # Drop new columns from photos
    op.drop_column("photos", "vote_count_seasonal")
    op.drop_column("photos", "vote_count_day")
    op.drop_column("photos", "vote_count_night")
    op.drop_column("photos", "vote_count")

    # Drop new columns from artists
    op.execute("ALTER TABLE artists DROP COLUMN aliases")
    op.drop_column("artists", "verified_at")
    op.drop_column("artists", "social_links")
    op.drop_column("artists", "website")

    # Drop new columns from users
    op.drop_column("users", "total_votes_received")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "social_links")
    op.drop_column("users", "website")
    op.drop_column("users", "tagline")
