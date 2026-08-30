"""Tests for SQLiteEngine core discovery, resolution, and PRAGMA tuning."""

import os
import sqlite3
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


def test_describe_schema_prompt_caching_footer(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    schema_doc = engine.describe_schema()

    # Latency should NOT be in the header lines
    first_lines = "\n".join(schema_doc.splitlines()[:5])
    assert "Discovery Latency" not in first_lines

    # Latency must be in the footer at the very bottom
    assert "*Discovery Latency:" in schema_doc
    assert schema_doc.strip().endswith("(O(1) non-blocking scan)*")

    # Detailed table definitions must appear before the latency footer
    detailed_idx = schema_doc.find("## Detailed Table Definitions")
    latency_idx = schema_doc.find("*Discovery Latency:")
    assert detailed_idx != -1
    assert latency_idx > detailed_idx


def test_fts5_shadow_table_exclusion(tmp_path):
    db_file = tmp_path / "test_fts5.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE VIRTUAL TABLE articles USING fts5(title, body);")
    cur.execute(
        "INSERT INTO articles (title, body) VALUES ('First Article', 'FastMCP SQLite search content');"
    )
    # User tables that have names ending in _data, _config, _content, etc.
    cur.execute("CREATE TABLE user_data (id INTEGER PRIMARY KEY, info TEXT);")
    cur.execute("CREATE TABLE site_config (key TEXT PRIMARY KEY, val TEXT);")
    cur.execute("CREATE TABLE post_content (id INTEGER PRIMARY KEY, body TEXT);")
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file))
    schema_doc = engine.describe_schema()

    # Virtual table is included
    assert "articles" in schema_doc
    # Shadow tables of virtual table articles are excluded
    assert "articles_data" not in schema_doc
    assert "articles_idx" not in schema_doc
    assert "articles_content" not in schema_doc
    assert "articles_docsize" not in schema_doc
    assert "articles_config" not in schema_doc

    # Legitimate user tables are preserved!
    assert "user_data" in schema_doc
    assert "site_config" in schema_doc
    assert "post_content" in schema_doc


def test_extension_loading_and_sandbox_lockdown(sample_db):
    # Non-existent extension should raise an exception during connection
    engine_with_ext = SQLiteEngine(
        default_db=sample_db,
        extensions=["non_existent_extension_xyz.so"],
    )
    with pytest.raises((sqlite3.OperationalError, FileNotFoundError, Exception)):
        engine_with_ext.get_connection(sample_db)

    # Valid engine without extensions should lock sandbox
    engine = SQLiteEngine(default_db=sample_db)
    conn = engine.get_connection(sample_db)
    try:
        # After get_connection, load_extension should fail because enable_load_extension is False
        with pytest.raises((sqlite3.OperationalError, AttributeError)):
            conn.load_extension("malicious_extension.so")
    finally:
        conn.close()
