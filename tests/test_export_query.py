"""Tests for streaming query export functionality (CSV and JSONL)."""

import csv
import json
import os
import sqlite3
import pytest
from fastmcp_sqlite.engine import SQLiteEngine


def test_export_query_csv_basic(sample_db, tmp_path):
    target_csv = tmp_path / "exported_users.csv"
    engine = SQLiteEngine(default_db=sample_db)

    res = engine.export_query(
        "SELECT id, username, email, role FROM users ORDER BY id ASC;",
        target_file=str(target_csv),
        format="csv",
    )

    assert "# Query Export Successful" in res
    assert "Rows Exported:** 3" in res
    assert "CSV" in res
    assert os.path.exists(target_csv)

    with open(target_csv, "r", encoding="utf-8", newline="") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 4  # 1 header + 3 data rows
        assert reader[0] == ["id", "username", "email", "role"]
        assert reader[1] == ["1", "alice", "alice@example.com", "admin"]
        assert reader[2] == ["2", "bob", "bob@example.com", "user"]
        assert reader[3] == ["3", "charlie", "charlie@example.com", "user"]


def test_export_query_jsonl_basic(sample_db, tmp_path):
    target_jsonl = tmp_path / "exported_users.jsonl"
    engine = SQLiteEngine(default_db=sample_db)

    res = engine.export_query(
        "SELECT id, username, role FROM users ORDER BY id ASC;",
        target_file=str(target_jsonl),
        format="jsonl",
    )

    assert "# Query Export Successful" in res
    assert "Rows Exported:** 3" in res
    assert "JSONL" in res
    assert os.path.exists(target_jsonl)

    with open(target_jsonl, "r", encoding="utf-8") as f:
        lines = [json.loads(line.strip()) for line in f if line.strip()]
        assert len(lines) == 3
        assert lines[0] == {"id": 1, "username": "alice", "role": "admin"}
        assert lines[1] == {"id": 2, "username": "bob", "role": "user"}
        assert lines[2] == {"id": 3, "username": "charlie", "role": "user"}


def test_export_query_with_params(sample_db, tmp_path):
    target_csv = tmp_path / "filtered_users.csv"
    engine = SQLiteEngine(default_db=sample_db)

    res = engine.export_query(
        "SELECT id, username FROM users WHERE role = :role;",
        target_file=str(target_csv),
        format="csv",
        params={"role": "user"},
    )

    assert "# Query Export Successful" in res
    assert "Rows Exported:** 2" in res

    with open(target_csv, "r", encoding="utf-8", newline="") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 3  # header + 2 users
        usernames = [row[1] for row in reader[1:]]
        assert usernames == ["bob", "charlie"]


def test_export_query_large_dataset_streaming(tmp_path):
    db_file = tmp_path / "large_test.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE large_records (id INTEGER PRIMARY KEY, title TEXT, score REAL);")
    data = [(i, f"Record title #{i}", i * 1.5) for i in range(5000)]
    cur.executemany("INSERT INTO large_records VALUES (?, ?, ?);", data)
    conn.commit()
    conn.close()

    target_csv = tmp_path / "large_export.csv"
    engine = SQLiteEngine(default_db=str(db_file))

    res = engine.export_query(
        "SELECT * FROM large_records ORDER BY id ASC;",
        target_file=str(target_csv),
        format="csv",
    )

    assert "# Query Export Successful" in res
    assert "Rows Exported:** 5,000" in res
    assert os.path.getsize(target_csv) > 100_000

    target_jsonl = tmp_path / "large_export.jsonl"
    res_jsonl = engine.export_query(
        "SELECT * FROM large_records ORDER BY id ASC;",
        target_file=str(target_jsonl),
        format="jsonl",
    )
    assert "Rows Exported:** 5,000" in res_jsonl
    assert os.path.getsize(target_jsonl) > 100_000


def test_export_query_blob_handling(large_payload_db, tmp_path):
    target_csv = tmp_path / "blob_export.csv"
    engine = SQLiteEngine(default_db=large_payload_db)

    res = engine.export_query(
        "SELECT id, doc_name, raw_blob FROM documents ORDER BY id ASC LIMIT 2;",
        target_file=str(target_csv),
        format="csv",
    )

    assert "# Query Export Successful" in res
    with open(target_csv, "r", encoding="utf-8", newline="") as f:
        reader = list(csv.reader(f))
        assert "<BLOB 400B>" in reader[1][2]


def test_export_query_invalid_format(sample_db, tmp_path):
    target_file = tmp_path / "test.xml"
    engine = SQLiteEngine(default_db=sample_db)

    res = engine.export_query(
        "SELECT * FROM users;",
        target_file=str(target_file),
        format="xml",
    )
    assert "Error: Unsupported export format 'xml'" in res


def test_export_query_watchdog_abort(sample_db, tmp_path):
    target_file = tmp_path / "infinite.csv"
    engine = SQLiteEngine(default_db=sample_db, opcode_limit=50_000)

    infinite_sql = "WITH RECURSIVE cte(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cte) SELECT * FROM cte;"
    res = engine.export_query(
        infinite_sql,
        target_file=str(target_file),
        format="csv",
    )
    assert "Export aborted by execution watchdog" in res or "OperationalError" in res
