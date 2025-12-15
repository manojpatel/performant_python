from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


class DataPoint(BaseModel):
    """
    Represents a single data point for processing.
    Pydantic v2 is significantly faster at validation.
    """

    id: int = Field(..., description="Unique identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    category: str = Field(..., pattern=r"^[A-Z]+$")
    value: float = Field(..., ge=0.0, le=1000.0)
    tags: list[str] = Field(default_factory=list)


class BatchData(BaseModel):
    """
    Represents a batch of data points to be processed by Polars.
    """

    batch_id: str
    data: list[DataPoint]


class ProcessingStats(BaseModel):
    """
    The result of the heavy computation.
    """

    batch_id: str
    processed_at: datetime = Field(default_factory=datetime.now)
    total_records: int
    mean_value: float
    max_value: float
    by_category: dict[str, float]  # Average value by category

    @computed_field
    def processing_speed_score(self) -> float:
        """
        A dummy computed field to demonstrate Pydantic v2 computed fields.
        """
        return self.total_records * 1.5


# ========================================================================
# PostgreSQL Models (User Events Analytics)
# ========================================================================


class UserEvent(BaseModel):
    """
    Represents a user event for analytics tracking.
    Used for INSERT operations.
    """

    user_id: int = Field(..., gt=0, description="User ID")
    event_type: str = Field(..., pattern=r"^(page_view|click|conversion)$")
    page_url: str = Field(..., min_length=1, description="Page URL")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event data")


class UserEventResponse(UserEvent):
    """
    User event with database ID and timestamp.
    Used for SELECT/response operations.
    """

    id: int
    created_at: datetime


class AnalyticsSummary(BaseModel):
    """
    Aggregated analytics metrics.
    """

    total_events: int
    unique_users: int
    events_by_type: dict[str, int]
    avg_duration_seconds: float
    query_time_ms: float
    source: str  # 'postgres' or 'duckdb'


class ConversionFunnel(BaseModel):
    """
    Conversion funnel by page.
    """

    page_url: str
    page_views: int
    clicks: int
    conversions: int
    conversion_rate: float


class IcebergBenchmarkResult(BaseModel):
    """
    Result of an Iceberg performance benchmark test.
    """

    test_name: str
    duration_ms: float
    result_summary: dict[str, Any]
    scanned_record_count: int | None = None
