"""Tests for DML RETURNING ACID guarantees and versatile parameter binding."""

import sqlite3
from fastmcp_sqlite.engine import SQLiteEngine


def test_insert_returning_acid(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # 1. Execute INSERT ... RETURNING
    insert_sql = """
        INSERT INTO users (username, email, role)
        VALUES ('diana', 'diana@example.com', 'developer')
        RETURNING id, username, role;
    """
    res = engine.execute_query(insert_sql, readonly=False, format="json")

    # Verify returned result set
    assert "diana" in res
    assert "developer" in res

    # 2. Verify data was ACID-committed and persists on fresh connection
    verify_conn = sqlite3.connect(sample_db)
    cur = verify_conn.cursor()
    cur.execute("SELECT username, email, role FROM users WHERE username = 'diana';")
    row = cur.fetchone()
    verify_conn.close()

    assert row is not None
    assert row[0] == "diana"
    assert row[1] == "diana@example.com"
    assert row[2] == "developer"


def test_update_returning(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    update_sql = """
        UPDATE users
        SET role = 'principal'
        WHERE username = 'alice'
        RETURNING id, username, role;
    """
    res = engine.execute_query(update_sql, readonly=False, format="table")

    assert "principal" in res
    assert "alice" in res

    # Verify persistence
    verify_conn = sqlite3.connect(sample_db)
    cur = verify_conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = 'alice';")
    assert cur.fetchone()[0] == "principal"
    verify_conn.close()


def test_delete_returning(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    delete_sql = """
        DELETE FROM posts
        WHERE id = 1
        RETURNING id, title;
    """
    res = engine.execute_query(delete_sql, readonly=False, format="json")

    assert "First Post" in res

    # Verify record was deleted
    verify_conn = sqlite3.connect(sample_db)
    cur = verify_conn.cursor()
    cur.execute("SELECT count(*) FROM posts WHERE id = 1;")
    assert cur.fetchone()[0] == 0
    verify_conn.close()


def test_parameter_binding_positional(sample_db):
    engine = SQLiteEngine(default_db=sample_db)

    res = engine.execute_query(
        "SELECT username FROM users WHERE role = ? ORDER BY id ASC;",
        params=["user"],
    )
    assert "bob" in res
    assert "charlie" in res


def test_parameter_binding_named(sample_db):
    engine = SQLiteEngine(default_db=sample_db)

    # Named with : and $ and @ prefixes or plain
    res1 = engine.execute_query(
        "SELECT username FROM users WHERE role = :role;",
        params={":role": "admin"},
    )
    assert "alice" in res1

    res2 = engine.execute_query(
        "SELECT username FROM users WHERE role = $target_role;",
        params={"$target_role": "admin"},
    )
    assert "alice" in res2


def test_parameter_binding_json_string(sample_db):
    engine = SQLiteEngine(default_db=sample_db)

    # LLM passed a JSON-encoded string
    res_list = engine.execute_query(
        "SELECT username FROM users WHERE role = ?;",
        params='["admin"]',
    )
    assert "alice" in res_list

    res_dict = engine.execute_query(
        "SELECT username FROM users WHERE role = :r;",
        params='{"r": "admin"}',
    )
    assert "alice" in res_dict


def test_parameter_binding_nested_object_serialization(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # Insert a nested dict/list into a text column
    insert_sql = "INSERT INTO config_kv (cfg_key, cfg_val) VALUES (?, ?);"
    nested_data = {"theme": "cyberpunk", "font_size": 14, "tags": ["ui", "dark"]}

    engine.execute_query(
        insert_sql,
        params=["editor_settings", nested_data],
        readonly=False,
    )

    # Verify JSON string was inserted properly
    verify_conn = sqlite3.connect(sample_db)
    cur = verify_conn.cursor()
    cur.execute("SELECT cfg_val FROM config_kv WHERE cfg_key = 'editor_settings';")
    val = cur.fetchone()[0]
    verify_conn.close()

    assert "cyberpunk" in val
    assert '"font_size": 14' in val


def test_transaction_rollback_on_error(sample_db):
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # Violate UNIQUE constraint on username ('alice' already exists)
    fail_sql = "INSERT INTO users (username, email) VALUES ('alice', 'duplicate@example.com');"
    res = engine.execute_query(fail_sql, readonly=False)

    assert "UNIQUE constraint failed" in res

    # Subsequent query should execute cleanly without transaction corruption
    clean_res = engine.execute_query("SELECT count(*) FROM users;")
    assert "**Rows Returned:** 1" in clean_res
