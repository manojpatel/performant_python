-- PostgreSQL initialization script for User Events Analytics
-- This script creates the schema and loads sample data

-- User events table for analytics
CREATE TABLE IF NOT EXISTS user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'page_view', 'click', 'conversion'
    page_url TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_user_events_created_at ON user_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_events_metadata ON user_events USING GIN (metadata);

-- Insert sample data (1000 user events)
INSERT INTO user_events (user_id, event_type, page_url, metadata)
SELECT 
    (random() * 100)::int + 1 AS user_id,
    (ARRAY['page_view', 'click', 'conversion'])[floor(random() * 3 + 1)] AS event_type,
    '/page-' || (random() * 20)::int AS page_url,
    jsonb_build_object(
        'duration', (random() * 60)::int,
        'browser', (ARRAY['chrome', 'firefox', 'safari', 'edge'])[floor(random() * 4 + 1)],
        'device', (ARRAY['desktop', 'mobile', 'tablet'])[floor(random() * 3 + 1)],
        'timestamp', NOW() - (random() * interval '30 days')
    ) AS metadata
FROM generate_series(1, 1000);

-- Create a view for quick analytics
CREATE OR REPLACE VIEW analytics_summary AS
SELECT 
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) FILTER (WHERE event_type = 'page_view') as page_views,
    COUNT(*) FILTER (WHERE event_type = 'click') as clicks,
    COUNT(*) FILTER (WHERE event_type = 'conversion') as conversions,
    AVG((metadata->>'duration')::int) as avg_duration_seconds
FROM user_events;

-- Print stats
DO $$
DECLARE
    event_count INTEGER;
    user_count INTEGER;
BEGIN
    SELECT COUNT(*), COUNT(DISTINCT user_id) INTO event_count, user_count FROM user_events;
    RAISE NOTICE '✅ Database initialized successfully!';
    RAISE NOTICE '   Total events: %', event_count;
    RAISE NOTICE '   Unique users: %', user_count;
END $$;
