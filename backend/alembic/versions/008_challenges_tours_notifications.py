"""Challenges, walking tours, and notifications.

Revision ID: 008
Revises: 007
Create Date: 2026-04-01
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE challenges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            challenge_type VARCHAR(50) NOT NULL,
            badge_type VARCHAR(50) NOT NULL,
            criteria JSONB NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE challenge_progress (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            progress INTEGER NOT NULL DEFAULT 0,
            target INTEGER NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(challenge_id, user_id)
        );
    """)
    op.execute("CREATE INDEX ix_challenge_progress_user ON challenge_progress(user_id);")

    op.execute("""
        CREATE TABLE walking_tours (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(200) NOT NULL,
            description TEXT,
            neighborhood_id UUID REFERENCES neighborhoods(id),
            total_distance_m INTEGER DEFAULT 0,
            estimated_minutes INTEGER DEFAULT 0,
            artwork_count INTEGER DEFAULT 0,
            is_auto_generated BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE walking_tour_stops (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tour_id UUID NOT NULL REFERENCES walking_tours(id) ON DELETE CASCADE,
            artwork_id UUID NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
            stop_order INTEGER NOT NULL,
            distance_from_previous_m INTEGER DEFAULT 0
        );
    """)
    op.execute(
        "CREATE INDEX ix_walking_tour_stops_tour ON walking_tour_stops(tour_id, stop_order);"
    )

    op.execute("""
        CREATE TABLE notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT,
            link VARCHAR(500),
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    op.execute(
        "CREATE INDEX ix_notifications_user_unread "
        "ON notifications(user_id, is_read, created_at DESC);"
    )

    op.execute("""
        INSERT INTO challenges (title, description, challenge_type, badge_type, criteria) VALUES
        ('Street Detective', 'Suggest artists for 5 unattributed artworks', 'identification', 'street_detective', '{"action": "suggest_artist", "count": 5}'),
        ('Night Owl', 'Upload 3 photos tagged as Night', 'upload', 'night_owl', '{"action": "upload_category", "category": "Night", "count": 3}'),
        ('Explorer', 'Upload photos in 3 different neighborhoods', 'exploration', 'explorer', '{"action": "upload_neighborhoods", "count": 3}'),
        ('Time Keeper', 'Upload 2 photos of the same artwork in different seasons', 'temporal', 'time_keeper', '{"action": "seasonal_pair", "count": 2}'),
        ('Pioneer', 'Be the first to photograph a new artwork', 'upload', 'pioneer', '{"action": "first_photo", "count": 1}');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS walking_tour_stops CASCADE;")
    op.execute("DROP TABLE IF EXISTS walking_tours CASCADE;")
    op.execute("DROP TABLE IF EXISTS challenge_progress CASCADE;")
    op.execute("DROP TABLE IF EXISTS challenges CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
