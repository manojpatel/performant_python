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
