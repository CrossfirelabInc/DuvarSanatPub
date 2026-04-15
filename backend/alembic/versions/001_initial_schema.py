"""Initial schema: users, artists, artworks, photos with PostGIS and pgvector.

Revision ID: 001
Revises:
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions (require superuser or pre-created extensions)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
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

    # artists
    op.create_table(
        "artists",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("artwork_count", sa.Integer(), nullable=False, server_default="0"),
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

    # artworks
    op.create_table(
        "artworks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        # location added via raw SQL below (Geography type)
        sa.Column(
            "artist_id",
            sa.Uuid(),
            sa.ForeignKey("artists.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
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

    # Add the PostGIS geography column (not natively supported by op.create_table)
    op.execute(
        "ALTER TABLE artworks "
        "ADD COLUMN location geography(POINT, 4326) NOT NULL"
    )

    # GiST index on artworks.location
    op.execute(
        "CREATE INDEX ix_artworks_location ON artworks USING gist (location)"
    )

    # B-tree index on artworks.artist_id
    op.create_index("ix_artworks_artist_id", "artworks", ["artist_id"])

    # photos
    op.create_table(
        "photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "artwork_id",
            sa.Uuid(),
            sa.ForeignKey("artworks.id"),
            nullable=True,
        ),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        # location added via raw SQL below (Geography type)
        sa.Column("date_taken", sa.DateTime(timezone=True), nullable=True),
        # image_embedding added via raw SQL below (vector type)
        sa.Column(
            "date_uploaded",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Add the PostGIS geography column
    op.execute(
        "ALTER TABLE photos "
        "ADD COLUMN location geography(POINT, 4326) NOT NULL"
    )

    # Add the pgvector embedding column
    op.execute(
        "ALTER TABLE photos "
        "ADD COLUMN image_embedding vector(512)"
    )

    # GiST index on photos.location
    op.execute(
        "CREATE INDEX ix_photos_location ON photos USING gist (location)"
    )

    # Composite B-tree index on (artwork_id, date_taken)
    op.create_index("ix_photos_artwork_date", "photos", ["artwork_id", "date_taken"])

    # B-tree index on photos.user_id
    op.create_index("ix_photos_user_id", "photos", ["user_id"])

    # IVFFlat index for fast cosine similarity search on embeddings.
    # NOTE: IVFFlat requires data to exist before creation for best results.
    # For an empty table this creates the index structure; consider REINDEX
    # after bulk-loading data.  We use lists=100 as a reasonable starting point.
    op.execute(
        "CREATE INDEX ix_photos_embedding ON photos "
        "USING ivfflat (image_embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("photos")
    op.drop_table("artworks")
    op.drop_table("artists")
    op.drop_table("users")

    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
