"""Security tests for C-Core SQLite Authorizer and Sandbox Lockdown."""

import sqlite3
import pytest
from fastmcp_sqlite.engine import SQLiteEngine


def test_readonly_authorizer_blocks_attach(sample_db):
    """Verify that ATTACH DATABASE is blocked at the AST compiler level by C authorizer."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)
    res = engine.execute_query("ATTACH DATABASE ':memory:' AS pwned;")
    assert (
        "forbidden in read-only mode" in res
        or "not authorized" in res
        or "OperationalError" in res
        or "DatabaseError" in res
    )


def test_readonly_authorizer_blocks_insert_update_delete(sample_db):
    """Verify that DML write operations are strictly denied in read-only mode."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    res_insert = engine.execute_query("INSERT INTO users (username) VALUES ('attacker');")
    assert (
        "forbidden in read-only mode" in res_insert
        or "not authorized" in res_insert
        or "OperationalError" in res_insert
    )

    res_update = engine.execute_query("UPDATE users SET role = 'admin' WHERE id = 2;")
    assert (
        "forbidden in read-only mode" in res_update
        or "not authorized" in res_update
        or "OperationalError" in res_update
    )

    res_delete = engine.execute_query("DELETE FROM users WHERE id = 1;")
    assert (
        "forbidden in read-only mode" in res_delete
        or "not authorized" in res_delete
        or "OperationalError" in res_delete
    )


def test_readonly_authorizer_blocks_ddl(sample_db):
    """Verify that DDL operations (ALTER, DROP, CREATE) are blocked in read-only mode."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    res_create = engine.execute_query("CREATE TABLE backdoor (x INT);")
    assert (
        "forbidden in read-only mode" in res_create
        or "not authorized" in res_create
        or "OperationalError" in res_create
    )

    res_drop = engine.execute_query("DROP TABLE users;")
    assert (
        "forbidden in read-only mode" in res_drop
        or "not authorized" in res_drop
        or "OperationalError" in res_drop
    )

    res_alter = engine.execute_query("ALTER TABLE users ADD COLUMN hacked TEXT;")
    assert (
        "forbidden in read-only mode" in res_alter
        or "not authorized" in res_alter
        or "OperationalError" in res_alter
    )


def test_readonly_authorizer_blocks_mutating_pragmas(sample_db):
    """Verify that setting PRAGMA values is blocked in read-only mode."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    res_writable = engine.execute_query("PRAGMA writable_schema = ON;")
    assert "not authorized" in res_writable or "OperationalError" in res_writable or "DatabaseError" in res_writable

    res_jmode = engine.execute_query("PRAGMA journal_mode = DELETE;")
    assert "not authorized" in res_jmode or "OperationalError" in res_jmode or "DatabaseError" in res_jmode


def test_readonly_authorizer_allows_safe_introspection_pragmas(sample_db):
    """Verify that reading metadata via introspection PRAGMAs is permitted in read-only mode."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    res_table_info = engine.execute_query("PRAGMA table_info(users);")
    assert "username" in res_table_info

    res_schema_ver = engine.execute_query("PRAGMA schema_version;")
    assert "schema_version" in res_schema_ver or "1" in res_schema_ver

    res_fk = engine.execute_query("PRAGMA foreign_key_list(posts);")
    assert "users" in res_fk or "user_id" in res_fk


def test_write_mode_authorizer_allows_dml_and_ddl(tmp_path):
    """Verify that when readonly=False, write operations execute and persist normally."""
    db_file = tmp_path / "write_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);")
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file), readonly=False)

    res_insert = engine.execute_query("INSERT INTO items (name) VALUES ('widget_a');", readonly=False)
    assert "Rows affected: 1" in res_insert

    res_query = engine.execute_query("SELECT * FROM items;", readonly=True)
    assert "widget_a" in res_query
