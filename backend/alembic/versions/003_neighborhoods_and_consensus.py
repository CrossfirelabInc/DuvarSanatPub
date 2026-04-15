"""Neighborhoods, artist suggestion consensus, and comments.

Revision ID: 003
Revises: 002
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

ISTANBUL_NEIGHBORHOODS = [
    ("Kadikoy", "Kadıköy", "kadikoy", "Vibrant art scene on the Asian side"),
    ("Beyoglu", "Beyoğlu", "beyoglu", "The heart of Istanbul's contemporary art"),
    ("Besiktas", "Beşiktaş", "besiktas", "Historic district with emerging street art"),
    ("Karakoy", "Karaköy", "karakoy", "Waterfront galleries and murals"),
    ("Balat", "Balat", "balat", "Colorful houses and hidden art"),
    ("Moda", "Moda", "moda", "Seaside neighborhood with creative energy"),
    ("Uskudar", "Üsküdar", "uskudar", "Traditional meets modern on the Asian side"),
    ("Sisli", "Şişli", "sisli", "Urban canvas in the business district"),
    ("Taksim", "Taksim", "taksim", "Iconic square surrounded by art"),
    ("Cihangir", "Cihangir", "cihangir", "Bohemian quarter with artistic soul"),
    ("Galata", "Galata", "galata", "Historic tower neighborhood with murals"),
    ("Ortakoy", "Ortaköy", "ortakoy", "Bosphorus views and street art"),
    ("Nisantasi", "Nişantaşı", "nisantasi", "Upscale streets with curated art"),
    ("Sultanahmet", "Sultanahmet", "sultanahmet", "Ancient walls, modern art"),
    ("Bahariye", "Bahariye", "bahariye", "Kadikoy's main artery of expression"),
]


def upgrade() -> None:
    # PART 1: New tables

    op.create_table(
        "neighborhoods",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("name_tr", sa.String(100), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("artwork_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "artist_suggestions",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "artwork_id",
            sa.Uuid(),
            sa.ForeignKey("artworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artist_id",
            sa.Uuid(),
            sa.ForeignKey("artists.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("suggested_name", sa.String(255), nullable=False),
        sa.Column(
            "suggested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "resolved_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "artwork_id", "suggested_by", name="uq_artist_suggestions_artwork_user"
        ),
    )
    op.create_index(
        "ix_artist_suggestions_artwork",
        "artist_suggestions",
        ["artwork_id", "status"],
    )

    op.create_table(
        "comments",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
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
        "ix_comments_target",
        "comments",
        ["target_type", "target_id", "created_at"],
    )
    op.create_index("ix_comments_user", "comments", ["user_id"])

    # PART 2: Column additions to existing tables

    op.execute("ALTER TABLE photos ADD COLUMN categories VARCHAR[] DEFAULT '{}'")
    op.execute(
        "CREATE INDEX ix_photos_categories ON photos USING GIN (categories)"
    )

    op.add_column(
        "users",
        sa.Column(
            "profile_type",
            sa.String(20),
            nullable=False,
            server_default="explorer",
        ),
    )

    op.add_column(
        "artworks",
        sa.Column(
            "neighborhood_id",
            sa.Uuid(),
            sa.ForeignKey("neighborhoods.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_artworks_neighborhood", "artworks", ["neighborhood_id"])

    # PART 3: Seed Istanbul neighborhoods
    for name, name_tr, slug, description in ISTANBUL_NEIGHBORHOODS:
        op.execute(
            sa.text(
                "INSERT INTO neighborhoods (name, name_tr, slug, description) "
                "VALUES (:name, :name_tr, :slug, :description)"
            ).bindparams(name=name, name_tr=name_tr, slug=slug, description=description)
        )


def downgrade() -> None:
    # Drop column additions
    op.drop_index("ix_artworks_neighborhood", table_name="artworks")
    op.drop_column("artworks", "neighborhood_id")
    op.drop_column("users", "profile_type")
    op.drop_index("ix_photos_categories", table_name="photos")
    op.execute("ALTER TABLE photos DROP COLUMN categories")

    # Drop new tables
    op.drop_table("comments")
    op.drop_table("artist_suggestions")
    op.drop_table("neighborhoods")
