"""Tests for Fuzzy Schema Typo Self-Healing Diagnostics."""

from fastmcp_sqlite.engine import SQLiteEngine


def test_fuzzy_table_typo(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query("SELECT * FROM usrs;")

    assert "SQLite OperationalError: no such table: usrs" in res
    assert "Suggestion: Table 'usrs' does not exist." in res
    assert "`users`" in res


def test_fuzzy_table_typo_posts(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query("SELECT * FROM post;")

    assert "Suggestion: Table 'post' does not exist." in res
    assert "`posts`" in res


def test_fuzzy_column_typo(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query("SELECT user_nam FROM users;")

    assert "SQLite OperationalError: no such column: user_nam" in res
    assert "Suggestion: Column 'user_nam' does not exist." in res
    assert "`username`" in res
    assert "table `users`" in res


def test_fuzzy_column_typo_email(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.execute_query("SELECT emai FROM users;")

    assert "Suggestion: Column 'emai' does not exist." in res
    assert "`email`" in res


def test_fuzzy_in_explain(sample_db):
    engine = SQLiteEngine(default_db=sample_db)
    res = engine.explain_query("SELECT * FROM usrs;")

    assert "Explain OperationalError: no such table: usrs" in res
    assert "Suggestion: Table 'usrs' does not exist." in res
    assert "`users`" in res
