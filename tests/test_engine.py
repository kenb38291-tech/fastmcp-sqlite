"""Tests for SQLiteEngine core discovery, resolution, and PRAGMA tuning."""

import os
import pytest
from fastmcp_sqlite.engine import SQLiteEngine


def test_resolve_db_path_valid(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    assert engine.resolve_db_path() == os.path.abspath(sample_db)
    assert engine.resolve_db_path(sample_db) == os.path.abspath(sample_db)


def test_resolve_db_path_missing():
    engine = SQLiteEngine(default_db=None)
    with pytest.raises(ValueError, match="No database specified"):
        engine.resolve_db_path(None)

    with pytest.raises(FileNotFoundError, match="Database file not found"):
        engine.resolve_db_path("non_existent_file_xyz123.db")


def test_describe_schema(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    schema_doc = engine.describe_schema()

    assert "# SQLite Schema Overview" in schema_doc
    assert "users" in schema_doc
    assert "posts" in schema_doc
    assert "active_users_view" in schema_doc
    assert "config_kv" in schema_doc
    assert "[View]" in schema_doc
    assert "[WITHOUT ROWID]" in schema_doc
    assert "Discovery Latency" in schema_doc


def test_describe_table(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    table_doc = engine.describe_table("posts")

    assert "# Table Info: `posts` (TABLE)" in table_doc
    assert "`id`" in table_doc
    assert "`user_id`" in table_doc
    assert "`title`" in table_doc
    assert "`content`" in table_doc
    assert "Foreign Keys" in table_doc
    assert "`users(id)`" in table_doc
    assert "idx_posts_user_id" in table_doc


def test_describe_table_not_found(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.describe_table("non_existent_tbl")
    assert "does not exist" in res


def test_explain_query(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    explain_doc = engine.explain_query(
        "SELECT * FROM posts WHERE user_id = ?", params=[1]
    )

    assert "# Query Plan:" in explain_doc
    assert "idx_posts_user_id" in explain_doc or "SCAN" in explain_doc or "SEARCH" in explain_doc


def test_list_databases(tmp_path, sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.list_dbs(str(tmp_path))

    assert "# SQLite Databases in" in res
    assert "test_sample.db" in res


def test_readonly_enforcement(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=True)
    res = engine.execute_query("INSERT INTO users (username) VALUES ('hacker')")
    assert "forbidden in read-only mode" in res

    res_drop = engine.execute_query("DROP TABLE users")
    assert "forbidden in read-only mode" in res_drop


def test_pragma_hygiene(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)
    conn = engine.get_connection(sample_db, readonly=False)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode;")
    jmode = cursor.fetchone()[0].upper()
    assert jmode == "WAL"

    cursor.execute("PRAGMA synchronous;")
    sync = cursor.fetchone()[0]
    assert sync == 1  # 1 is NORMAL

    cursor.execute("PRAGMA temp_store;")
    temp_store = cursor.fetchone()[0]
    assert temp_store == 2  # 2 is MEMORY

    conn.close()
