import os
import sqlite3
import time
import pytest
from fastmcp_sqlite.engine import SQLiteEngine

LIVE_DB = 'C:/Users/beani/Desktop/website_ranking/consensus_all_domains.db'


@pytest.mark.skipif(not os.path.exists(LIVE_DB), reason='Live DB not present')
def test_live_db_cartesian_2_table_cross_join():
    engine = SQLiteEngine(default_db=LIVE_DB, readonly=True, opcode_limit=50_000)
    sql = 'SELECT count(*) FROM domains d1 CROSS JOIN domains d2;'
    t0 = time.perf_counter()
    res = engine.execute_query(sql)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert 'Query aborted by execution watchdog' in res
    assert elapsed_ms < 1000.0

    # Vitality check
    norm = engine.execute_query('SELECT * FROM domains WHERE rank = 1;')
    assert 'google.com' in norm


@pytest.mark.skipif(not os.path.exists(LIVE_DB), reason='Live DB not present')
def test_live_db_cartesian_3_table_cross_join():
    engine = SQLiteEngine(default_db=LIVE_DB, readonly=True, opcode_limit=50_000)
    sql = 'SELECT count(*) FROM domains d1, domains d2, domains d3;'
    t0 = time.perf_counter()
    res = engine.execute_query(sql)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert 'Query aborted by execution watchdog' in res
    assert elapsed_ms < 1000.0

    # Vitality check
    norm = engine.execute_query('SELECT * FROM domains WHERE rank = 1;')
    assert 'google.com' in norm


@pytest.mark.skipif(not os.path.exists(LIVE_DB), reason='Live DB not present')
def test_live_db_infinite_recursive_cte_join():
    engine = SQLiteEngine(default_db=LIVE_DB, readonly=True, opcode_limit=50_000)
    sql = 'WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT count(*) FROM loop JOIN domains ON loop.n = domains.rank;'
    t0 = time.perf_counter()
    res = engine.execute_query(sql)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert 'Query aborted by execution watchdog' in res
    assert elapsed_ms < 1000.0

    # Vitality check
    norm = engine.execute_query('SELECT * FROM domains WHERE rank = 1;')
    assert 'google.com' in norm
