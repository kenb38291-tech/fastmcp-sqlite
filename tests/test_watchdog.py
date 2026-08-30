"""Tests for SQLite Opcode Execution Watchdog (runaway query prevention)."""

import time
from fastmcp_sqlite.engine import SQLiteEngine


def test_watchdog_infinite_cte(sample_db):
    # Standard opcode limit of 1,000,000 instructions
    engine = SQLiteEngine(
        default_db=sample_db, readonly=False, opcode_limit=500_000
    )

    t0 = time.perf_counter()
    sql = """
        WITH RECURSIVE cnt(x) AS (
            SELECT 1
            UNION ALL
            SELECT x + 1 FROM cnt
        )
        SELECT count(*) FROM cnt;
    """
    result = engine.execute_query(sql)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Must abort cleanly without hanging CPU
    assert "Query aborted by execution watchdog" in result
    assert "exceeded CPU opcode budget" in result
    # Execution should be aborted in under 1 second (typically < 20ms)
    assert elapsed_ms < 1000.0


def test_watchdog_cartesian_explosion(sample_db):
    engine = SQLiteEngine(
        default_db=sample_db, readonly=False, opcode_limit=300_000
    )

    # 10 recursive tables joined together -> Cartesian explosion
    sql = """
        WITH RECURSIVE numbers(n) AS (
            SELECT 1 UNION ALL SELECT n + 1 FROM numbers WHERE n < 100
        )
        SELECT count(*) FROM numbers n1, numbers n2, numbers n3, numbers n4;
    """
    result = engine.execute_query(sql)

    assert "Query aborted by execution watchdog" in result


def test_watchdog_custom_opcode_limit(sample_db):
    # Very small opcode limit
    engine = SQLiteEngine(
        default_db=sample_db, readonly=False, opcode_limit=20_000
    )

    sql = """
        SELECT count(*) FROM (
            WITH RECURSIVE seq(x) AS (
                SELECT 1 UNION ALL SELECT x + 1 FROM seq WHERE x < 50000
            )
            SELECT * FROM seq
        );
    """
    result = engine.execute_query(sql)
    assert "Query aborted by execution watchdog" in result


def test_normal_query_passes_watchdog(sample_db):
    engine = SQLiteEngine(
        default_db=sample_db, readonly=False, opcode_limit=1_000_000
    )
    result = engine.execute_query("SELECT count(*) as total FROM users;")
    assert "**Rows Returned:** 1" in result
    assert "| 3 |" in result
