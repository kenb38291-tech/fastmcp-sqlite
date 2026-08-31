"""Stress test suite for WAL concurrency lock contention and VDBE watchdog runaway query protection."""

import concurrent.futures
import gc
import os
import sqlite3
import time
import tracemalloc
import pytest

from fastmcp_sqlite.engine import SQLiteEngine
from fastmcp_sqlite.server import create_server


def test_stress_50_concurrent_threads_mixed_workload(sample_db):
    """Stress test 50 concurrent threads executing mixed operations (schema, query, explain, table_info, DML)."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        timeout=5.0,
        opcode_limit=1_000_000,
    )

    # Ensure WAL mode is active
    init_conn = engine.get_connection(sample_db, readonly=False)
    init_conn.close()

    errors = []
    latencies = []

    def schema_worker(worker_id: int):
        for _ in range(15):
            t0 = time.perf_counter()
            try:
                res = engine.describe_schema(sample_db)
                latencies.append((time.perf_counter() - t0) * 1000)
                if "Error" in res:
                    errors.append(f"Worker {worker_id} schema error: {res}")
            except Exception as e:
                errors.append(f"Worker {worker_id} schema exception: {e}")

    def query_reader_worker(worker_id: int):
        for _ in range(20):
            t0 = time.perf_counter()
            try:
                res = engine.execute_query(
                    "SELECT u.username, u.role, count(p.id) as post_count "
                    "FROM users u LEFT JOIN posts p ON u.id = p.user_id "
                    "GROUP BY u.id;",
                    db=sample_db,
                    readonly=True,
                )
                latencies.append((time.perf_counter() - t0) * 1000)
                if "OperationalError" in res or "Error" in res:
                    errors.append(f"Worker {worker_id} query error: {res}")
            except Exception as e:
                errors.append(f"Worker {worker_id} query exception: {e}")

    def explain_worker(worker_id: int):
        for _ in range(15):
            t0 = time.perf_counter()
            try:
                res = engine.explain_query(
                    "SELECT * FROM posts WHERE user_id = 1;",
                    db=sample_db,
                )
                latencies.append((time.perf_counter() - t0) * 1000)
                if "Error" in res:
                    errors.append(f"Worker {worker_id} explain error: {res}")
            except Exception as e:
                errors.append(f"Worker {worker_id} explain exception: {e}")

    def table_info_worker(worker_id: int):
        for _ in range(15):
            t0 = time.perf_counter()
            try:
                tbl = "users" if worker_id % 2 == 0 else "posts"
                res = engine.describe_table(tbl, db=sample_db)
                latencies.append((time.perf_counter() - t0) * 1000)
                if "Error" in res:
                    errors.append(f"Worker {worker_id} table_info error: {res}")
            except Exception as e:
                errors.append(f"Worker {worker_id} table_info exception: {e}")

    def dml_writer_worker(worker_id: int):
        for i in range(10):
            t0 = time.perf_counter()
            try:
                res = engine.execute_query(
                    "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?) RETURNING id;",
                    params=[1, f"Stress Post {worker_id}-{i}", f"Stress content payload from worker {worker_id}"],
                    db=sample_db,
                    readonly=False,
                )
                latencies.append((time.perf_counter() - t0) * 1000)
                if "OperationalError" in res or "database is locked" in res:
                    errors.append(f"Worker {worker_id} DML error: {res}")
            except Exception as e:
                errors.append(f"Worker {worker_id} DML exception: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        # 10 Schema workers
        for w in range(10):
            futures.append(executor.submit(schema_worker, w))
        # 15 Reader workers
        for w in range(10, 25):
            futures.append(executor.submit(query_reader_worker, w))
        # 10 Explain workers
        for w in range(25, 35):
            futures.append(executor.submit(explain_worker, w))
        # 5 Table info workers
        for w in range(35, 40):
            futures.append(executor.submit(table_info_worker, w))
        # 10 Writer workers
        for w in range(40, 50):
            futures.append(executor.submit(dml_writer_worker, w))

        for f in futures:
            f.result(timeout=15.0)

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
    assert len(latencies) >= 600
    avg_lat = sum(latencies) / len(latencies)
    assert avg_lat < 300.0  # Average latency should remain well under 300ms under heavy 50-thread concurrent load


def test_stress_concurrent_writer_lock_contention(sample_db):
    """Stress test 20 concurrent writer threads competing for write locks in WAL mode."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        timeout=5.0,
    )

    errors = []
    insert_count = 0

    def pure_writer_task(worker_id: int):
        nonlocal insert_count
        for i in range(12):
            # 1. Insert with returning
            res = engine.execute_query(
                "INSERT INTO users (username, email, role) VALUES (?, ?, ?) RETURNING id;",
                params=[f"lock_user_{worker_id}_{i}", f"lock_{worker_id}_{i}@test.com", "stress"],
                db=sample_db,
                readonly=False,
            )
            if "Error" in res and "database is locked" in res:
                errors.append(f"Writer {worker_id} locked during insert: {res}")
            elif "Rows Returned" in res:
                insert_count += 1

            # 2. Update
            res_up = engine.execute_query(
                "UPDATE users SET role = 'active_stress' WHERE username = ?;",
                params=[f"lock_user_{worker_id}_{i}"],
                db=sample_db,
                readonly=False,
            )
            if "Error" in res_up and "database is locked" in res_up:
                errors.append(f"Writer {worker_id} locked during update: {res_up}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(pure_writer_task, w) for w in range(20)]
        for f in futures:
            f.result(timeout=15.0)

    assert len(errors) == 0, f"Write lock contention failures: {errors}"
    # Verify rows were committed
    verify_res = engine.execute_query("SELECT count(*) as total FROM users WHERE role = 'active_stress';", db=sample_db)
    assert "240" in verify_res


def test_watchdog_extreme_recursive_cte(sample_db):
    """Test infinite recursive CTE execution is intercepted by VDBE progress watchdog."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=100_000,
    )

    # 1. Select count(*) from unbounded loop (requires full evaluation)
    t0 = time.perf_counter()
    sql_count = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT count(*) FROM loop;"
    res_count = engine.execute_query(sql_count)
    elapsed_count_ms = (time.perf_counter() - t0) * 1000

    assert "Query aborted by execution watchdog" in res_count
    assert "exceeded CPU opcode budget of 100,000 instructions" in res_count
    assert elapsed_count_ms < 1000.0

    # 2. Select * from unbounded loop with ORDER BY (forces full evaluation)
    t0 = time.perf_counter()
    sql_sort = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT * FROM loop ORDER BY n DESC;"
    res_sort = engine.execute_query(sql_sort)
    elapsed_sort_ms = (time.perf_counter() - t0) * 1000

    assert "Query aborted by execution watchdog" in res_sort
    assert elapsed_sort_ms < 1000.0

    # 3. Select * with high max_rows exceeding opcode budget
    engine_high_rows = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=50_000,
        max_rows=10_000,
    )
    sql_raw = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT * FROM loop;"
    res_raw = engine_high_rows.execute_query(sql_raw)
    assert "Query aborted by execution watchdog" in res_raw

    # 4. Multi-tier tokenomics defense: default max_rows=100 returns immediately
    engine_default = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=100_000,
        max_rows=100,
    )
    res_default = engine_default.execute_query(sql_raw)
    assert "**Rows Returned:** 100 (capped at max limit of 100)" in res_default


def test_watchdog_cartesian_explosion_stress(sample_db):
    """Test multi-table Cartesian explosion cross join generating millions of rows is safely aborted."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=250_000,
    )

    t0 = time.perf_counter()
    # 5-table cross join of 50 rows each = 312.5M rows
    sql = """
        WITH RECURSIVE
            c1(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c1 WHERE x < 50),
            c2(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c2 WHERE x < 50),
            c3(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c3 WHERE x < 50),
            c4(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c4 WHERE x < 50),
            c5(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c5 WHERE x < 50)
        SELECT count(*) FROM c1, c2, c3, c4, c5;
    """
    res = engine.execute_query(sql)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert "Query aborted by execution watchdog" in res
    assert "exceeded CPU opcode budget" in res
    assert elapsed_ms < 1000.0


def test_watchdog_abort_latency_benchmark(sample_db):
    """Benchmark precision and timing of watchdog abort over multiple iterations."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=50_000,
    )

    sql = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT count(*) FROM loop;"
    timings = []

    for _ in range(20):
        t0 = time.perf_counter()
        res = engine.execute_query(sql)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert "Query aborted by execution watchdog" in res
        timings.append(elapsed_ms)

    avg_timing = sum(timings) / len(timings)
    min_timing = min(timings)
    max_timing = max(timings)

    # Validate sub-millisecond to low millisecond performance under CI environments
    assert avg_timing < 100.0, f"Average abort latency too high: {avg_timing:.2f} ms"
    assert max_timing < 500.0, f"Max abort latency too high: {max_timing:.2f} ms"


def test_watchdog_memory_stability_no_leak(sample_db):
    """Verify that executing 100 runaway queries in sequence does not leak memory."""
    engine = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=100_000,
    )

    sql = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT count(*) FROM loop;"

    # Warmup and garbage collect
    gc.collect()
    tracemalloc.start()
    mem_before, _ = tracemalloc.get_traced_memory()

    for _ in range(100):
        res = engine.execute_query(sql)
        assert "Query aborted by execution watchdog" in res

    gc.collect()
    mem_after, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    delta_kb = (mem_after - mem_before) / 1024
    peak_kb = peak / 1024

    # Memory delta after 100 aborted queries must be strictly bounded (< 256KB)
    assert delta_kb < 256, f"Potential memory leak detected: delta={delta_kb:.2f} KB, peak={peak_kb:.2f} KB"


def test_watchdog_custom_opcode_limits_50k_and_5m(sample_db):
    """Test behavior with small opcode limit (50k) vs large opcode limit (5M)."""
    # 1. 50k Opcode Limit -> Aborts moderate query
    engine_small = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=50_000,
    )
    moderate_sql = """
        WITH RECURSIVE seq(x) AS (
            SELECT 1 UNION ALL SELECT x+1 FROM seq WHERE x < 20000
        )
        SELECT count(*) FROM seq;
    """
    res_small = engine_small.execute_query(moderate_sql)
    assert "Query aborted by execution watchdog" in res_small
    assert "50,000" in res_small

    # 2. 5M Opcode Limit -> Allows moderate query to succeed
    engine_large = SQLiteEngine(
        default_db=sample_db,
        readonly=False,
        opcode_limit=5_000_000,
    )
    res_large = engine_large.execute_query(moderate_sql)
    assert "Query aborted by execution watchdog" not in res_large
    assert "| 20000 |" in res_large or "20000" in res_large

    # 3. 5M Opcode Limit -> Still aborts infinite runaway query
    infinite_sql = "WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT count(*) FROM loop;"
    res_inf = engine_large.execute_query(infinite_sql)
    assert "Query aborted by execution watchdog" in res_inf
    assert "5,000,000" in res_inf


def test_server_tools_high_concurrency(sample_db):
    """Test FastMCP server registered tool functions under high concurrency."""
    mcp = create_server(
        db_path=sample_db,
        readonly=False,
        opcode_limit=500_000,
    )

    errors = []

    def call_tool_worker(worker_id: int):
        try:
            # Test schema
            s = mcp._tool_manager._tools["schema"].fn()
            if "SQLite Schema Overview" not in s:
                errors.append(f"Worker {worker_id} schema failed")

            # Test query
            q = mcp._tool_manager._tools["query"].fn(sql="SELECT count(*) FROM users;")
            if "Rows Returned" not in q:
                errors.append(f"Worker {worker_id} query failed")

            # Test table_info
            t = mcp._tool_manager._tools["table_info"].fn(table="users")
            if "Table Info: `users`" not in t:
                errors.append(f"Worker {worker_id} table_info failed")

            # Test explain
            e = mcp._tool_manager._tools["explain"].fn(sql="SELECT * FROM users WHERE id = 1;")
            if "Query Plan" not in e:
                errors.append(f"Worker {worker_id} explain failed")
        except Exception as ex:
            errors.append(f"Worker {worker_id} server tool exception: {ex}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(call_tool_worker, w) for w in range(25)]
        for f in futures:
            f.result(timeout=15.0)

    assert len(errors) == 0, f"Server tools concurrency errors: {errors}"
