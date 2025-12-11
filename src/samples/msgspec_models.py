import msgspec
from typing import List

class FastDataPoint(msgspec.Struct):
    """
    Equivalent to DataPoint but using msgspec.Struct.
    msgspec structs are defined as C structures and are faster to instantiate and validate.
    """
    id: int
    timestamp: float
    category: str
    value: float
    tags: List[str]

class FastBatchData(msgspec.Struct):
    """
    Batch data model for msgspec.
    """
    batch_id: str
    data: List[FastDataPoint]

class FastProcessingStats(msgspec.Struct):
    """
    Return type for msgspec endpoints.
    """
    batch_id: str
    processed_at: float
    total_records: int
    mean_value: float
    max_value: float
    by_category: dict[str, float]
    processing_speed_score: float

# =============================================================================
# PostgreSQL Models (msgspec - faster than Pydantic)
# =============================================================================

class UserEventMsg(msgspec.Struct):
    """User event for analytics (msgspec - 3-5x faster than Pydantic)."""
    user_id: int
    event_type: str
    page_url: str
    metadata: dict

class UserEventResponseMsg(msgspec.Struct):
    """User event response with ID and timestamp."""
    id: int
    user_id: int
    event_type: str
    page_url: str
    metadata: dict
    created_at: str  # ISO format datetime string

class AnalyticsSummaryMsg(msgspec.Struct):
    """Analytics summary (msgspec)."""
    total_events: int
    unique_users: int
    events_by_type: dict[str, int]
    avg_duration_seconds: float
    query_time_ms: float
    source: str
