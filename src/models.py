from pydantic import BaseModel, Field, computed_field
from typing import List, Optional
from datetime import datetime
import random

class DataPoint(BaseModel):
    """
    Represents a single data point for processing.
    Pydantic v2 is significantly faster at validation.
    """
    id: int = Field(..., description="Unique identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    category: str = Field(..., pattern=r"^[A-Z]+$")
    value: float = Field(..., ge=0.0, le=1000.0)
    tags: List[str] = Field(default_factory=list)

class BatchData(BaseModel):
    """
    Represents a batch of data points to be processed by Polars.
    """
    batch_id: str
    data: List[DataPoint]

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
