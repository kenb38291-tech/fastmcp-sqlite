"""Tests for WAL Concurrency and Lock Hygiene under multi-threaded read/write load."""

import concurrent.futures
import sqlite3
import time
from fastmcp_sqlite.engine import SQLiteEngine


def test_concurrent_wal_readers_and_writer(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False, timeout=5.0)

    # Initialize WAL mode
    conn_init = engine.get_connection(sample_db, readonly=False)
    conn_init.close()

    writer_errors = []
    reader_errors = []

    def writer_task():
        try:
            conn = engine.get_connection(sample_db, readonly=False)
            cursor = conn.cursor()
            for i in range(10):
                cursor.execute(
                    "INSERT INTO users (username, email, role) VALUES (?, ?, ?);",
                    (f"user_thread_{i}", f"user_{i}@test.com", "member"),
                )
                conn.commit()
                time.sleep(0.02)
            conn.close()
        except Exception as e:
            writer_errors.append(e)

    def reader_task(thread_id: int):
        try:
            for _ in range(15):
                res = engine.execute_query(
                    "SELECT count(*) FROM users;",
                    db=sample_db,
                    readonly=True,
                )
                if "Error" in res and "SQLite OperationalError" in res:
                    reader_errors.append(res)
                time.sleep(0.01)
        except Exception as e:
            reader_errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        writer_future = executor.submit(writer_task)
        reader_futures = [
            executor.submit(reader_task, i) for i in range(7)
        ]

        writer_future.result(timeout=10.0)
        for f in reader_futures:
            f.result(timeout=10.0)

    assert len(writer_errors) == 0, f"Writer encountered errors: {writer_errors}"
    assert len(reader_errors) == 0, f"Readers encountered lock errors: {reader_errors}"
