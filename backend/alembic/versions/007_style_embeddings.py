"""Add style_embedding columns to photos and artworks.

Revision ID: 007
Revises: 006
Create Date: 2026-04-01
"""

from alembic import op

# revision identifiers, used by Alembic
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add vector columns directly via raw SQL (pgvector type)
    op.execute("ALTER TABLE photos ADD COLUMN style_embedding vector(256)")
    op.execute("ALTER TABLE artworks ADD COLUMN style_embedding vector(256)")

    op.execute(
        "CREATE INDEX ix_photos_style_embedding ON photos "
        "USING ivfflat (style_embedding vector_cosine_ops) WITH (lists = 50)"
    )
    op.execute(
        "CREATE INDEX ix_artworks_style_embedding ON artworks "
        "USING ivfflat (style_embedding vector_cosine_ops) WITH (lists = 50)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_artworks_style_embedding")
    op.execute("DROP INDEX IF EXISTS ix_photos_style_embedding")
    op.drop_column("artworks", "style_embedding")
    op.drop_column("photos", "style_embedding")
