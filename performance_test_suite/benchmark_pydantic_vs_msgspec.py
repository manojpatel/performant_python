import time
import msgspec
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from pydantic import BaseModel
from typing import Optional
from src.samples.msgspec_models import IcebergBenchmarkResult as MsgspecResult

# Define Pydantic equivalent locally for comparison
class PydanticResult(BaseModel):
    test_name: str
    duration_ms: float
    result_summary: dict
    scanned_record_count: Optional[int] = 0

def benchmark():
    N = 100_000
    print(f"Benchmarking Instantiation of {N} objects...")
    
    # 1. Pydantic Instantiation
    t0 = time.perf_counter()
    for i in range(N):
        _ = PydanticResult(
            test_name="test",
            duration_ms=100.0,
            result_summary={"foo": "bar"},
            scanned_record_count=i
        )
    pydantic_time = time.perf_counter() - t0
    print(f"Pydantic: {pydantic_time:.4f}s")

    # 2. Msgspec Instantiation
    t0 = time.perf_counter()
    for i in range(N):
        _ = MsgspecResult(
            test_name="test",
            duration_ms=100.0,
            result_summary={"foo": "bar"},
            scanned_record_count=i
        )
    msgspec_time = time.perf_counter() - t0
    print(f"Msgspec:  {msgspec_time:.4f}s")
    
    speedup = pydantic_time / msgspec_time
    print(f"Instantiation Speedup: {speedup:.2f}x")
    
    print("-" * 30)
    print(f"Benchmarking Serialization of {N} objects...")
    
    # Random objects
    p_obj = PydanticResult(test_name="T", duration_ms=1.0, result_summary={}, scanned_record_count=1)
    m_obj = MsgspecResult(test_name="T", duration_ms=1.0, result_summary={}, scanned_record_count=1)
    
    # 3. Pydantic JSON Dump
    t0 = time.perf_counter()
    for _ in range(N):
        _ = p_obj.model_dump_json()
    pydantic_ser_time = time.perf_counter() - t0
    print(f"Pydantic Dump: {pydantic_ser_time:.4f}s")
    
    # 4. Msgspec JSON Encode
    encoder = msgspec.json.Encoder()
    t0 = time.perf_counter()
    for _ in range(N):
        _ = encoder.encode(m_obj)
    msgspec_ser_time = time.perf_counter() - t0
    print(f"Msgspec Encode: {msgspec_ser_time:.4f}s")
    
    ser_speedup = pydantic_ser_time / msgspec_ser_time
    print(f"Serialization Speedup: {ser_speedup:.2f}x")

if __name__ == "__main__":
    benchmark()
