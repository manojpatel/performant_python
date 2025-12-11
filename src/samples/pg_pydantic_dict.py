"""
PostgreSQL endpoints for user events analytics.
Demonstrates asyncpg performance and connection pooling.
"""
import time
from typing import List
from fastapi import HTTPException
from src.lib.postgres_client import get_postgres
from src.samples.pydantic_models import UserEvent, UserEventResponse, AnalyticsSummary, ConversionFunnel


async def create_event_endpoint(event: UserEvent) -> UserEventResponse:
    """Insert a user event into PostgreSQL."""
    import json
    pg = get_postgres()
    
    t0 = time.perf_counter()
    
    row = await pg.fetchrow(
        """
        INSERT INTO user_events (user_id, event_type, page_url, metadata)
        VALUES ($1, $2, $3, $4)
        RETURNING id, user_id, event_type, page_url, metadata, created_at
        """,
        event.user_id,
        event.event_type,
        event.page_url,
        json.dumps(event.metadata)  # Convert dict to JSON string
    )
    
    # Parse the returned JSONB field back to dict
    event_data = dict(row)
    event_data['metadata'] = json.loads(event_data['metadata']) if isinstance(event_data['metadata'], str) else event_data['metadata']
    
    return UserEventResponse(**event_data)


async def get_user_events_endpoint(user_id: int, limit: int = 100) -> List[UserEventResponse]:
    """Get all events for a specific user."""
    import json
    pg = get_postgres()
    
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit
    )
    
    # Parse metadata JSON string to dict for each row
    events = []
    for row in rows:
        event_data = dict(row)
        event_data['metadata'] = json.loads(event_data['metadata']) if isinstance(event_data['metadata'], str) else event_data['metadata']
        events.append(UserEventResponse(**event_data))
    
    return events


async def get_analytics_summary_endpoint() -> AnalyticsSummary:
    """
    Get aggregated analytics summary.
    Compares PostgreSQL vs DuckDB for OLAP queries.
    """
    pg = get_postgres()
    
    t0 = time.perf_counter()
    
    # Single query with multiple aggregations
    row = await pg.fetchrow(
        """
        SELECT 
            COUNT(*) as total_events,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(*) FILTER (WHERE event_type = 'page_view') as page_views,
            COUNT(*) FILTER (WHERE event_type = 'click') as clicks,
            COUNT(*) FILTER (WHERE event_type = 'conversion') as conversions,
            AVG((metadata->>'duration')::int) as avg_duration
        FROM user_events
        """
    )
    
    t1 = time.perf_counter()
    
    events_by_type = {
        "page_view": row['page_views'],
        "click": row['clicks'],
        "conversion": row['conversions']
    }
    
    return AnalyticsSummary(
        total_events=row['total_events'],
        unique_users=row['unique_users'],
        events_by_type=events_by_type,
        avg_duration_seconds=float(row['avg_duration'] or 0),
        query_time_ms=(t1 - t0) * 1000,
        source="postgres"
    )


async def get_conversion_funnel_endpoint() -> List[ConversionFunnel]:
    """Get conversion funnel by page."""
    pg = get_postgres()
    
    rows = await pg.fetch(
        """
        SELECT 
            page_url,
            COUNT(*) FILTER (WHERE event_type = 'page_view') as page_views,
            COUNT(*) FILTER (WHERE event_type = 'click') as clicks,
            COUNT(*) FILTER (WHERE event_type = 'conversion') as conversions,
            CASE 
                WHEN COUNT(*) FILTER (WHERE event_type = 'page_view') > 0
                THEN (COUNT(*) FILTER (WHERE event_type = 'conversion')::float / 
                      COUNT(*) FILTER (WHERE event_type = 'page_view')::float) * 100
                ELSE 0
            END as conversion_rate
        FROM user_events
        GROUP BY page_url
        HAVING COUNT(*) FILTER (WHERE event_type = 'page_view') > 0
        ORDER BY page_views DESC
        LIMIT 20
        """
    )
    
    return [ConversionFunnel(**dict(row)) for row in rows]


async def bulk_insert_events_endpoint(count: int = 1000) -> dict:
    """Bulk insert events for performance testing."""
    import random
    import json
    
    if count > 10000:
        raise HTTPException(status_code=400, detail="Max 10,000 events per bulk insert")
    
    pg = get_postgres()
    
    # Prepare batch data
    events = []
    for i in range(count):
        events.append((
            random.randint(1, 100),  # user_id
            random.choice(['page_view', 'click', 'conversion']),  # event_type
            f'/page-{random.randint(1, 20)}',  # page_url
            json.dumps({"duration": random.randint(1, 60), "test": True})  # metadata as JSON string
        ))
    
    t0 = time.perf_counter()
    
    # Use executemany for batch insert
    await pg._pool.executemany(
        "INSERT INTO user_events (user_id, event_type, page_url, metadata) VALUES ($1, $2, $3, $4)",
        events
    )
    
    t1 = time.perf_counter()
    
    return {
        "inserted": count,
        "query_time_ms": (t1 - t0) * 1000,
        "inserts_per_second": int(count / (t1 - t0))
    }
