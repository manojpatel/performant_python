
import duckdb
import time
import concurrent.futures
import threading
import os
import psutil

def get_memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

DB_PATH = "concurrency_test.db"
NUM_QUERIES = 30
# A query that takes a bit of time but not forever. 
# We'll generate enough data so it's measurable.
QUERY = "SELECT count(*), avg(val), max(val) FROM large_table WHERE category = (random() * 10)::INTEGER"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    print("Setting up database and generating data...")
    con = duckdb.connect(DB_PATH)
    # Generate ~10M rows. DuckDB is fast, so 10M might be quick, but good enough for parallelism check.
    con.execute("""
        CREATE TABLE large_table AS 
        SELECT 
            (random() * 100)::INTEGER as category,
            random() as val 
        FROM generate_series(1, 10000000)
    """)
    # Check single query time
    start = time.time()
    con.execute(QUERY).fetchall()
    print(f"Single query baseline duration: {time.time() - start:.4f}s")
    con.close()


def monitor_memory(stop_event, peak_container):
    while not stop_event.is_set():
        current = get_memory_mb()
        if current > peak_container[0]:
            peak_container[0] = current
        time.sleep(0.05)

def run_single_connection_shared(num_queries):
    print(f"\n--- Scenario A: Single Connection Shared by {num_queries} Threads ---")
    
    stop_event = threading.Event()
    peak_mem = [get_memory_mb()]
    mem_thread = threading.Thread(target=monitor_memory, args=(stop_event, peak_mem))
    mem_thread.start()

    con = duckdb.connect(DB_PATH, read_only=True)
    
    def worker():
        # Use a cursor for each thread to ensure isolation if connection is shared
        cursor = con.cursor()
        start_t = time.time()
        cursor.execute(QUERY).fetchall()
        dur = time.time() - start_t
        cursor.close()
        return dur

    start_total = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_queries) as executor:
        futures = [executor.submit(worker) for _ in range(num_queries)]
        results = [f.result() for f in futures]
    
    total_time = time.time() - start_total
    
    stop_event.set()
    mem_thread.join()
    
    print(f"Total time (wall clock): {total_time:.4f}s")
    print(f"Average time per query: {sum(results)/len(results):.4f}s")
    print(f"Peak Memory: {peak_mem[0]:.2f} MB")
    con.close()

def run_connection_per_thread(num_queries):
    print(f"\n--- Scenario B: Connection Per Thread (Pool) ({num_queries} Threads) ---")
    
    stop_event = threading.Event()
    peak_mem = [get_memory_mb()]
    mem_thread = threading.Thread(target=monitor_memory, args=(stop_event, peak_mem))
    mem_thread.start()
    
    def worker():
        # Each thread gets its own connection
        local_con = duckdb.connect(DB_PATH, read_only=True)
        start_t = time.time()
        local_con.execute(QUERY).fetchall()
        dur = time.time() - start_t
        local_con.close()
        return dur

    start_total = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_queries) as executor:
        futures = [executor.submit(worker) for _ in range(num_queries)]
        results = [f.result() for f in futures]
    
    total_time = time.time() - start_total
    
    stop_event.set()
    mem_thread.join()
    
    print(f"Total time (wall clock): {total_time:.4f}s")
    print(f"Average time per query: {sum(results)/len(results):.4f}s")
    print(f"Peak Memory: {peak_mem[0]:.2f} MB")

def main():
    setup_db()
    
    print(f"Initial Memory: {get_memory_mb():.2f} MB")
    
    # Run Scenario A
    run_single_connection_shared(NUM_QUERIES)
    print(f"Memory after Scenario A: {get_memory_mb():.2f} MB")
    
    # Run Scenario B
    # Force GC/Cleanup? DuckDB handles it, but let's see buildup.
    run_connection_per_thread(NUM_QUERIES)
    print(f"Memory after Scenario B: {get_memory_mb():.2f} MB")
    
    print("\nBenchmark complete.")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

if __name__ == "__main__":
    main()
