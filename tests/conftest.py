"""Pytest fixtures for fastmcp_sqlite test suite."""

import os
import sqlite3
from typing import Generator
import pytest

from fastmcp_sqlite.engine import SQLiteEngine


@pytest.fixture
def sample_db(tmp_path) -> str:
    """Create a temporary SQLite database with standard tables, views, and indexes."""
    db_file = tmp_path / "test_sample.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    cur.execute("CREATE INDEX idx_posts_user_id ON posts(user_id);")

    cur.execute("""
        CREATE VIEW active_users_view AS
        SELECT id, username, role FROM users WHERE role != 'banned';
    """)

    cur.execute("""
        CREATE TABLE config_kv (
            cfg_key TEXT PRIMARY KEY,
            cfg_val TEXT
        ) WITHOUT ROWID;
    """)

    # Seed data
    users_data = [
        ("alice", "alice@example.com", "admin"),
        ("bob", "bob@example.com", "user"),
        ("charlie", "charlie@example.com", "user"),
    ]
    cur.executemany(
        "INSERT INTO users (username, email, role) VALUES (?, ?, ?);",
        users_data,
    )

    posts_data = [
        (1, "First Post", "Hello world from Alice"),
        (1, "Second Post", "Architecting FastMCP SQLite"),
        (2, "Bob's Log", "Testing queries"),
    ]
    cur.executemany(
        "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?);",
        posts_data,
    )

    cur.execute(
        "INSERT INTO config_kv (cfg_key, cfg_val) VALUES ('theme', 'dark'), ('timeout', '30');"
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def wide_table_db(tmp_path) -> str:
    """Create a database containing a wide 39-column table for tokenomics testing."""
    db_file = tmp_path / "test_wide.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create 39 columns: id + col_1 .. col_38
    cols_sql = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    for i in range(1, 39):
        cols_sql.append(f"col_{i} TEXT DEFAULT 'val_{i}'")

    cur.execute(f"CREATE TABLE hardware_archetypes ({', '.join(cols_sql)});")

    for row_id in range(1, 11):
        values = [f"r{row_id}_c{c}" for c in range(1, 39)]
        placeholders = ", ".join(["?"] * 38)
        col_names = ", ".join([f"col_{c}" for c in range(1, 39)])
        cur.execute(
            f"INSERT INTO hardware_archetypes ({col_names}) VALUES ({placeholders});",
            values,
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def large_payload_db(tmp_path) -> str:
    """Create a database containing large text and BLOB payloads."""
    db_file = tmp_path / "test_payload.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT NOT NULL,
            body TEXT,
            raw_blob BLOB
        );
    """)

    # 100 rows with long strings (500 chars) to easily exceed 24KB limit if unconstrained
    long_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10
    sample_blob = b"\x00\xFF\xAA\x55" * 100

    for i in range(100):
        cur.execute(
            "INSERT INTO documents (doc_name, body, raw_blob) VALUES (?, ?, ?);",
            (f"doc_{i}", f"{i}: {long_text}", sample_blob),
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def engine(sample_db) -> SQLiteEngine:
    """Provide a SQLiteEngine instance bound to sample_db."""
    return SQLiteEngine(default_db=sample_db, readonly=False)


@pytest.fixture
def readonly_engine(sample_db) -> SQLiteEngine:
    """Provide a SQLiteEngine instance bound to sample_db in read-only mode."""
    return SQLiteEngine(default_db=sample_db, readonly=True)
