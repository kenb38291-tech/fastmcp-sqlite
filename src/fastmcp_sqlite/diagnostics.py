"""Fuzzy schema typo diagnostics and self-healing suggestions for SQLite errors.

Provides instant 'Did you mean?' suggestions for misspelled table and column names
to eliminate redundant LLM schema roundtrips.
"""

import difflib
import re
import sqlite3
from typing import Dict, Optional


def get_fuzzy_schema_hint(
    conn: sqlite3.Connection, err_msg: str, sql: str
) -> Optional[str]:
    """Intelligently diagnose table/column typos and suggest corrections.

    Args:
        conn: Active SQLite connection for metadata introspection.
        err_msg: SQLite OperationalError message string.
        sql: Original SQL query string executed.

    Returns:
        A human-readable suggestion string if a close match is found, else None.
    """
    # 1. Check "no such table: <name>"
    tbl_match = re.search(r"no such table:\s*([^\s,;]+)", err_msg, re.IGNORECASE)
    if tbl_match:
        target_tbl = tbl_match.group(1).strip("`\"'[]")
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
            )
            tables = [r[0] for r in cursor.fetchall()]
            cursor.close()
            matches = difflib.get_close_matches(target_tbl, tables, n=3, cutoff=0.5)
            if matches:
                return (
                    f"Table '{target_tbl}' does not exist. "
                    f"Did you mean: {', '.join(f'`{m}`' for m in matches)}?"
                )
            elif tables:
                return (
                    f"Table '{target_tbl}' does not exist. "
                    f"Available tables: {', '.join(f'`{m}`' for m in tables[:6])}."
                )
        except Exception:
            pass
        return None

    # 2. Check "no such column: <name>"
    col_match = re.search(r"no such column:\s*([^\s,;]+)", err_msg, re.IGNORECASE)
    if col_match:
        target_col_raw = col_match.group(1).strip("`\"'[]")
        target_col = (
            target_col_raw.split(".")[-1]
            if "." in target_col_raw
            else target_col_raw
        )
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
            )
            all_tables = [r[0] for r in cursor.fetchall()]

            # Targeted PRAGMA probing: identify tables referenced in the query SQL
            sql_tokens = set(re.findall(r"\b[A-Za-z0-9_]+\b", sql))
            queried_tables = [t for t in all_tables if t in sql_tokens]
            candidate_tables = queried_tables if queried_tables else all_tables[:10]

            col_map: Dict[str, str] = {}
            for t in candidate_tables:
                try:
                    cursor.execute(f'PRAGMA table_info("{t}")')
                    for c in cursor.fetchall():
                        col_map[c[1]] = t  # c[1] is column name in PRAGMA table_info
                except Exception:
                    pass

            cursor.close()
            matches = difflib.get_close_matches(
                target_col, list(col_map.keys()), n=3, cutoff=0.5
            )
            if matches:
                suggestions = [
                    f"`{m}` (in table `{col_map[m]}`)" for m in matches
                ]
                return (
                    f"Column '{target_col_raw}' does not exist. "
                    f"Did you mean: {', '.join(suggestions)}?"
                )
        except Exception:
            pass
        return None

    return None
