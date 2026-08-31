"""Tests for Zero-Trust path traversal security and Dual-SDK tool annotations."""

import os
import sqlite3
import pytest
from fastmcp_sqlite.engine import SQLiteEngine
from fastmcp_sqlite.server import create_server


def test_allowed_dir_init_with_valid_default_db(tmp_path):
    """Verify engine initializes cleanly when default_db is inside allowed_dir."""
    db_file = tmp_path / "valid.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INT);")
    conn.close()

    engine = SQLiteEngine(
        default_db=str(db_file),
        allowed_dir=str(tmp_path),
    )
    assert engine.default_db == str(db_file)
    assert engine.allowed_dir == str(tmp_path)


def test_allowed_dir_init_with_outside_default_db(tmp_path):
    """Verify engine rejects default_db located outside allowed_dir."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_db = outside_dir / "secret.db"
    conn = sqlite3.connect(str(outside_db))
    conn.execute("CREATE TABLE secret (val TEXT);")
    conn.close()

    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()

    with pytest.raises(PermissionError) as excinfo:
        SQLiteEngine(
            default_db=str(outside_db),
            allowed_dir=str(allowed_dir),
        )
    assert "outside allowed directory" in str(excinfo.value)


def test_resolve_db_path_traversal_attack(tmp_path):
    """Verify resolve_db_path rejects path traversal attempts outside allowed_dir."""
    allowed_dir = tmp_path / "sandbox"
    allowed_dir.mkdir()
    inside_db = allowed_dir / "app.db"
    conn = sqlite3.connect(str(inside_db))
    conn.execute("CREATE TABLE t (x INT);")
    conn.close()

    engine = SQLiteEngine(
        default_db=str(inside_db),
        allowed_dir=str(allowed_dir),
    )

    # 1. Accessing inside db succeeds
    resolved = engine.resolve_db_path(str(inside_db))
    assert os.path.abspath(resolved) == str(inside_db)

    # 2. Accessing outside via relative traversal ../ raises PermissionError
    outside_attempt = str(allowed_dir / ".." / "outside.db")
    with pytest.raises(PermissionError) as excinfo:
        engine.resolve_db_path(outside_attempt)
    assert "Access denied" in str(excinfo.value)


def test_export_query_traversal_attack(sample_db, tmp_path):
    """Verify export_query blocks writes to target files outside allowed_dir."""
    allowed_dir = tmp_path / "sandbox"
    allowed_dir.mkdir()

    # Move sample_db into allowed_dir
    safe_db = allowed_dir / "data.db"
    with open(sample_db, "rb") as src, open(safe_db, "wb") as dst:
        dst.write(src.read())

    engine = SQLiteEngine(
        default_db=str(safe_db),
        allowed_dir=str(allowed_dir),
    )

    # Target file outside allowed_dir
    evil_target = tmp_path / "stolen" / "export.csv"
    res = engine.export_query(
        sql="SELECT * FROM users;",
        target_file=str(evil_target),
    )
    assert "Error: Access denied" in res
    assert "outside allowed directory" in res
    assert not os.path.exists(str(evil_target))


def test_list_dbs_traversal_attack(tmp_path):
    """Verify list_dbs blocks scanning directories outside allowed_dir."""
    allowed_dir = tmp_path / "sandbox"
    allowed_dir.mkdir()
    forbidden_dir = tmp_path / "forbidden"
    forbidden_dir.mkdir()

    engine = SQLiteEngine(
        allowed_dir=str(allowed_dir),
    )

    res = engine.list_dbs(str(forbidden_dir))
    assert "Error: Access denied" in res
    assert "outside allowed directory" in res


def test_tools_block_traversal_database(tmp_path):
    """Verify schema, query, explain, and table_info gracefully return permission errors."""
    allowed_dir = tmp_path / "sandbox"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "forbidden"
    outside_dir.mkdir()
    outside_db = outside_dir / "private.db"
    conn = sqlite3.connect(str(outside_db))
    conn.execute("CREATE TABLE sensitive (data TEXT);")
    conn.close()

    engine = SQLiteEngine(
        allowed_dir=str(allowed_dir),
    )

    # 1. describe_schema on outside_db
    schema_res = engine.describe_schema(db=str(outside_db))
    assert "Access denied" in schema_res

    # 2. execute_query on outside_db
    query_res = engine.execute_query(sql="SELECT * FROM sensitive;", db=str(outside_db))
    assert "Access denied" in query_res

    # 3. explain_query on outside_db
    explain_res = engine.explain_query(sql="SELECT * FROM sensitive;", db=str(outside_db))
    assert "Access denied" in explain_res

    # 4. describe_table on outside_db
    table_res = engine.describe_table(table="sensitive", db=str(outside_db))
    assert "Access denied" in table_res


def test_server_creation_with_allowed_dir(sample_db, tmp_path):
    """Verify create_server accepts allowed_dir and registers all 6 tools."""
    server = create_server(
        db_path=sample_db,
        allowed_dir=os.path.dirname(sample_db),
    )
    assert server is not None

    # Check that all 6 tools exist in tool manager
    registered_tools = server._tool_manager._tools
    expected_tools = {
        "schema",
        "query",
        "export_query",
        "table_info",
        "explain",
        "list_databases",
    }
    assert expected_tools.issubset(set(registered_tools.keys()))
