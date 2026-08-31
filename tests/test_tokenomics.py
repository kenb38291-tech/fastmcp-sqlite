"""Tests for Tokenomics: Markdown Table, Vertical View, JSON, Truncation, and Payload Cap."""

import json
import sqlite3
from fastmcp_sqlite.engine import SQLiteEngine


def test_markdown_table_format(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query(
        "SELECT id, username, email FROM users ORDER BY id ASC;",
        format="table",
    )

    assert "| id | username | email |" in res
    assert "| :--- | :--- | :--- |" in res
    assert "| 1 | alice | alice@example.com |" in res
    assert "**Rows Returned:** 3" in res


def test_vertical_view_format(wide_table_db):
    engine = SQLiteEngine(default_db=wide_table_db)
    res = engine.execute_query(
        "SELECT * FROM hardware_archetypes LIMIT 2;",
        format="vertical",
    )

    assert "### Record 1" in res
    assert "### Record 2" in res
    assert "- **id**: `1`" in res
    assert "- **col_1**:" in res
    assert "- **col_38**:" in res


def test_json_format(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query(
        "SELECT id, username, role FROM users ORDER BY id ASC;",
        format="json",
    )

    assert "```json" in res
    json_part = res.split("```json")[1].split("```")[0].strip()
    data = json.loads(json_part)

    assert isinstance(data, list)
    assert len(data) == 3
    assert data[0]["username"] == "alice"
    assert data[0]["role"] == "admin"


def test_cell_truncation(large_payload_db):
    # Set cell_max_chars to 50
    engine = SQLiteEngine(default_db=large_payload_db, cell_max_chars=50)
    res = engine.execute_query(
        "SELECT id, body FROM documents WHERE id = 1;",
        format="table",
    )

    assert "…[truncated]" in res


def test_payload_byte_cap(large_payload_db):
    # Enforce small payload cap of 2048 bytes
    engine = SQLiteEngine(
        default_db=large_payload_db, max_rows=100, max_bytes=2048
    )
    res = engine.execute_query("SELECT * FROM documents;", format="table")

    assert "payload size limit reached" in res
    assert "Payload byte limit exceeded at row" in res
    # Size in bytes should be close to or under 2500 bytes (safely constrained)
    assert len(res.encode("utf-8")) < 3000


def test_blob_formatting(large_payload_db):
    engine = SQLiteEngine(default_db=large_payload_db)

    # Test Markdown Table
    res_table = engine.execute_query(
        "SELECT id, raw_blob FROM documents WHERE id = 1;", format="table"
    )
    assert "<BLOB 400B>" in res_table

    # Test Vertical View
    res_vert = engine.execute_query(
        "SELECT id, raw_blob FROM documents WHERE id = 1;", format="vertical"
    )
    assert "<BLOB 400B>" in res_vert

    # Test JSON
    res_json = engine.execute_query(
        "SELECT id, raw_blob FROM documents WHERE id = 1;", format="json"
    )
    assert "<BLOB 400B>" in res_json


def test_unicode_utf8_byte_cap(tmp_path):
    db_file = tmp_path / "test_unicode.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE unicode_docs (id INTEGER PRIMARY KEY, content TEXT);")

    vietnamese_text = "Hệ thống cơ sở dữ liệu SQLite hiệu năng cao với FastMCP 🚀🔥"
    cjk_text = "高性能轻量级数据库检索系统 🚀🔥🎉"
    multibyte_row = f"{vietnamese_text} | {cjk_text}"

    for i in range(50):
        cur.execute(
            "INSERT INTO unicode_docs (content) VALUES (?);",
            (f"{i}: {multibyte_row}",),
        )
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file), max_rows=50, max_bytes=1024)
    res = engine.execute_query("SELECT * FROM unicode_docs;", format="table")

    assert "payload size limit reached" in res
    assert "Payload byte limit exceeded at row" in res
    assert len(res.encode("utf-8")) < 1500


def test_cell_truncation_escape_hatch(large_payload_db):
    """Verify that cell_max_chars=0 serves as an escape hatch to return untruncated content."""
    engine = SQLiteEngine(default_db=large_payload_db, cell_max_chars=0)
    res = engine.execute_query(
        "SELECT id, body FROM documents WHERE id = 1;",
        format="table",
    )
    assert "…[truncated]" not in res
    assert "Lorem ipsum dolor sit amet" in res


def test_vertical_view_payload_byte_cap(large_payload_db):
    """Verify format_vertical_view respects max_bytes and appends truncation marker."""
    engine = SQLiteEngine(
        default_db=large_payload_db, max_rows=100, max_bytes=2048
    )
    res = engine.execute_query("SELECT * FROM documents;", format="vertical")

    assert "payload size limit reached" in res
    assert "… [Payload byte limit exceeded at record" in res
    assert len(res.encode("utf-8")) <= 2048 or len(res.encode("utf-8")) < 2500


def test_json_format_payload_byte_cap_valid_json(large_payload_db):
    """Verify format_json with max_bytes produces 100% valid JSON array."""
    engine = SQLiteEngine(
        default_db=large_payload_db, max_rows=100, max_bytes=2048
    )
    res = engine.execute_query("SELECT * FROM documents;", format="json")

    assert "payload size limit reached" in res
    assert "```json" in res
    json_block = res.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_block)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "doc_name" in data[0]

