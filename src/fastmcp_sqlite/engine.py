"""Core high-performance SQLite engine with safety, lock hygiene, and token optimization.

Features:
- Direct single-process execution
- Fast O(1) Schema Discovery (PRAGMA table_xinfo, foreign_key_list, MAX(_rowid_) rightmost probe)
- Concurrency & Lock Hygiene (WAL mode, busy_timeout=5000ms, mmap_size=256MB, query_only=ON)
- Opcode Execution Watchdog (conn.set_progress_handler instruction cap)
- Token-Efficient Serialization (Compact Markdown Table, Vertical View, JSON, cell truncation, payload guards)
- ACID Transaction Safety for DML RETURNING clauses
"""

import json
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .diagnostics import get_fuzzy_schema_hint
from .formatters import (
    format_json,
    format_markdown_table,
    format_vertical_view,
)


READONLY_SAFE_PRAGMAS = {
    "table_info",
    "table_xinfo",
    "foreign_key_list",
    "foreign_key_check",
    "index_list",
    "index_info",
    "index_xinfo",
    "database_list",
    "collation_list",
    "compile_options",
    "integrity_check",
    "quick_check",
    "schema_version",
    "user_version",
    "data_version",
    "freelist_count",
    "page_count",
    "page_size",
    "max_page_count",
    "table_list",
    "stats",
    "encoding",
}

READONLY_QUERY_ONLY_PRAGMAS = {
    "busy_timeout",
    "cache_size",
    "cache_spill",
    "case_sensitive_like",
    "defer_foreign_keys",
    "foreign_keys",
    "hard_heap_limit",
    "journal_mode",
    "locking_mode",
    "mmap_size",
    "query_only",
    "recursive_triggers",
    "secure_delete",
    "soft_heap_limit",
    "synchronous",
    "temp_store",
    "threads",
}


SHADOW_TABLE_SUFFIXES = (
    "_node",
    "_rowid",
    "_parent",
    "_segments",
    "_segdir",
    "_stat",
    "_data",
    "_idx",
    "_content",
    "_docsize",
    "_config",
)


def _readonly_authorizer(
    action_code: int,
    arg1: Optional[str],
    arg2: Optional[str],
    db_name: Optional[str],
    trigger_name: Optional[str],
) -> int:
    """SQLite C-Core Authorizer callback to enforce strict sandbox read-only AST constraints."""
    # Strictly forbid attaching or detaching external databases (anti-exfiltration / sandbox boundary)
    if action_code in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY

    # Forbid DML write mutations on standard user tables
    if action_code in (
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
    ):
        if arg1 and any(arg1.endswith(sfx) for sfx in SHADOW_TABLE_SUFFIXES):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    # Forbid destructive DDL schema modifications
    deny_ddl_mutations = {
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VTABLE,
    }
    if action_code in deny_ddl_mutations:
        return sqlite3.SQLITE_DENY

    # Validate PRAGMAs: allow safe introspection and standard read-only query settings
    if action_code == sqlite3.SQLITE_PRAGMA:
        pname = (arg1 or "").lower()
        if pname in READONLY_SAFE_PRAGMAS:
            return sqlite3.SQLITE_OK
        if pname in READONLY_QUERY_ONLY_PRAGMAS and arg2 is None:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return sqlite3.SQLITE_OK


def _is_safe_path(path: str, allowed_dir: Optional[str]) -> bool:
    """Validate that a target path resides strictly inside the allowed root directory."""
    if not allowed_dir:
        return True
    try:
        norm_path = os.path.normcase(os.path.realpath(os.path.abspath(path)))
        norm_allowed = os.path.normcase(os.path.realpath(os.path.abspath(allowed_dir)))
        if norm_path == norm_allowed:
            return True
        common = os.path.commonpath([norm_path, norm_allowed])
        return common == norm_allowed
    except Exception:
        return False


class SQLiteEngine:
    """Core high-performance SQLite engine with safety and lock hygiene."""

    def __init__(
        self,
        default_db: Optional[str] = None,
        readonly: bool = True,
        max_rows: int = 100,
        max_bytes: int = 24576,
        cell_max_chars: int = 200,
        opcode_limit: int = 1_000_000,
        timeout: float = 5.0,
        extensions: Optional[List[str]] = None,
        allowed_dir: Optional[str] = None,
    ) -> None:
        """Initialize the SQLite engine.

        Args:
            default_db: Optional default path to SQLite database file.
            readonly: Default read-only security mode.
            max_rows: Maximum rows returned per query (default: 100).
            max_bytes: Maximum response payload size in bytes (default: 24KB).
            cell_max_chars: Maximum characters per cell before truncation (default: 200).
            opcode_limit: SQLite opcode instruction limit for runaway query watchdog.
            timeout: Busy timeout in seconds for lock contention.
            extensions: Optional list of paths to loadable SQLite extension libraries.
            allowed_dir: Optional directory boundary to restrict database and export operations.
        """
        self.allowed_dir = (
            os.path.abspath(allowed_dir) if allowed_dir else None
        )
        self.default_db = (
            os.path.abspath(default_db)
            if (default_db and default_db != ":memory:")
            else default_db
        )
        if self.default_db and self.default_db != ":memory:" and self.allowed_dir:
            if not _is_safe_path(self.default_db, self.allowed_dir):
                raise PermissionError(
                    f"Access denied: Default database path '{self.default_db}' is outside allowed directory root '{self.allowed_dir}'."
                )
        self.readonly = readonly
        self.max_rows = max_rows
        self.max_bytes = max_bytes
        self.cell_max_chars = cell_max_chars
        self.opcode_limit = opcode_limit
        self.timeout = timeout
        self.extensions = list(extensions) if extensions else []

    def resolve_db_path(self, db: Optional[str] = None) -> str:
        """Resolve database path from argument or default configured path.

        Args:
            db: Optional path passed by tool caller.

        Returns:
            Resolved absolute path to database or ':memory:'.

        Raises:
            ValueError: If no database is specified and no default is set.
            PermissionError: If the path is outside the configured allowed_dir.
            FileNotFoundError: If the specified file does not exist.
        """
        raw_path = db.strip() if db and db.strip() else self.default_db
        if not raw_path:
            raise ValueError(
                "No database specified and no default database configured. "
                "Please specify the 'db' parameter with an absolute path to a .db file."
            )
        if raw_path == ":memory:":
            return ":memory:"

        path = os.path.abspath(raw_path)
        if self.allowed_dir and not _is_safe_path(path, self.allowed_dir):
            raise PermissionError(
                f"Access denied: Database path '{path}' is outside allowed directory root '{self.allowed_dir}'."
            )
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Database file not found at: {path}")
        return path

    def get_connection(
        self, db_path: str, readonly: bool = True
    ) -> sqlite3.Connection:
        """Open a tuned SQLite connection with lock hygiene and watchdog.

        Args:
            db_path: Path to database file or ':memory:'.
            readonly: Whether to open in read-only mode.

        Returns:
            Configured sqlite3.Connection object.
        """
        resolved = self.resolve_db_path(db_path)
        if resolved == ":memory:":
            conn = sqlite3.connect(":memory:", timeout=self.timeout)
        else:
            norm_path = resolved.replace("\\", "/")
            uri = (
                f"file:{norm_path}?mode=ro"
                if readonly
                else f"file:{norm_path}?mode=rw"
            )
            conn = sqlite3.connect(uri, uri=True, timeout=self.timeout)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout = 5000;")
        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            pass  # May be read-only filesystem or mode

        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA mmap_size = 268435456;")  # 256MB MMAP
        cursor.execute("PRAGMA cache_size = -64000;")  # 64MB Page Cache
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        if readonly:
            try:
                cursor.execute("PRAGMA query_only = ON;")
            except sqlite3.OperationalError:
                pass
            conn.set_authorizer(_readonly_authorizer)

        cursor.close()

        # Opcode progress watchdog to abort runaway queries
        opcodes_executed = 0

        def progress_watchdog() -> int:
            nonlocal opcodes_executed
            opcodes_executed += 10000
            if opcodes_executed > self.opcode_limit:
                return 1  # Abort query execution
            return 0

        conn.set_progress_handler(progress_watchdog, 10000)

        # Dynamic Extension Loading with Sandbox Lockdown
        if self.extensions:
            try:
                conn.enable_load_extension(True)
                for ext in self.extensions:
                    conn.load_extension(ext)
            finally:
                try:
                    conn.enable_load_extension(False)
                except (AttributeError, sqlite3.OperationalError):
                    pass

        return conn

    def get_estimated_row_count(
        self, cursor: sqlite3.Cursor, table_name: str, is_view: bool
    ) -> str:
        """Fast O(1) row count estimation avoiding sequential B-Tree scans.

        Args:
            cursor: Active cursor for metadata inspection.
            table_name: Target table or view name.
            is_view: Whether the target is a view.

        Returns:
            String representing row count estimation or status.
        """
        if is_view:
            return "[View]"

        # 1. Check sqlite_stat1 if available
        try:
            cursor.execute(
                "SELECT stat FROM sqlite_stat1 WHERE tbl = ? LIMIT 1",
                (table_name,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                stat_parts = str(row[0]).split()
                if stat_parts and stat_parts[0].isdigit():
                    return f"~{int(stat_parts[0]):,}"
        except Exception:
            pass

        # 2. Check if table is WITHOUT ROWID
        try:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            sql_row = cursor.fetchone()
            if sql_row and sql_row[0] and "WITHOUT ROWID" in sql_row[0].upper():
                return "[WITHOUT ROWID]"
        except Exception:
            pass

        # 3. O(1) Fast MAX(_rowid_) index lookup
        try:
            safe_name = table_name.replace('"', '""')
            cursor.execute(f'SELECT MAX(_rowid_) FROM "{safe_name}"')
            result = cursor.fetchone()
            if result is None or result[0] is None:
                return "0"
            return f"~{int(result[0]):,}"
        except Exception:
            return "unknown"

    def describe_schema(self, db: Optional[str] = None) -> str:
        """Return full database schema overview in O(1) time.

        Args:
            db: Optional path to database file.

        Returns:
            Markdown formatted schema overview document.
        """
        t0 = time.perf_counter()
        try:
            db_path = self.resolve_db_path(db)
        except Exception as e:
            return f"Error resolving database: {e}"

        file_size_mb = 0.0
        file_size_bytes = 0
        if db_path != ":memory:" and os.path.exists(db_path):
            file_size_bytes = os.path.getsize(db_path)
            file_size_mb = file_size_bytes / (1024 * 1024)

        try:
            conn = self.get_connection(db_path, readonly=True)
        except Exception as e:
            return f"Error connecting to database: {e}"

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT type, name, tbl_name, sql 
                FROM sqlite_master 
                WHERE type IN ('table', 'view') 
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY type, name
            """
            )
            raw_items = cursor.fetchall()

            # Dynamically identify shadow tables created by virtual tables (e.g. FTS3/4/5, RTree)
            virtual_tables = {
                item["name"]
                for item in raw_items
                if item["sql"] and "USING " in item["sql"].upper()
            }
            shadow_suffixes = (
                "_data", "_idx", "_content", "_docsize", "_config",
                "_segments", "_segdir", "_stat",
                "_node", "_rowid", "_parent",
            )
            shadow_names = {
                f"{vt}{sfx}"
                for vt in virtual_tables
                for sfx in shadow_suffixes
            }
            items = [item for item in raw_items if item["name"] not in shadow_names]

            tables_summary = []
            tables_detail = []

            for item in items:
                itype = item["type"]
                name = item["name"]
                is_view = itype == "view"
                est_rows = self.get_estimated_row_count(cursor, name, is_view)

                safe_name = name.replace('"', '""')

                # Column Info via PRAGMA table_xinfo
                cursor.execute(f'PRAGMA table_xinfo("{safe_name}")')
                cols = cursor.fetchall()
                col_defs = []
                pk_cols = []
                for c in cols:
                    col_name = c["name"]
                    col_type = c["type"] or "ANY"
                    notnull = " NOT NULL" if c["notnull"] else ""
                    dflt = (
                        f" DEFAULT {c['dflt_value']}"
                        if c["dflt_value"] is not None
                        else ""
                    )
                    pk = f" [PK:{c['pk']}]" if c["pk"] > 0 else ""
                    if c["pk"] > 0:
                        pk_cols.append(col_name)
                    hidden_tag = " [HIDDEN/GENERATED]" if c["hidden"] > 0 else ""
                    col_defs.append(
                        f"  - `{col_name}` ({col_type}{notnull}{dflt}{pk}{hidden_tag})"
                    )

                # Foreign Keys
                fk_defs = []
                try:
                    cursor.execute(f'PRAGMA foreign_key_list("{safe_name}")')
                    fks = cursor.fetchall()
                    for fk in fks:
                        fk_defs.append(
                            f"  - `{fk['from']}` -> `{fk['table']}`(`{fk['to']}`)"
                        )
                except Exception:
                    pass

                # Indexes
                idx_defs = []
                try:
                    cursor.execute(f'PRAGMA index_list("{safe_name}")')
                    indexes = cursor.fetchall()
                    for idx in indexes:
                        idx_name = idx["name"]
                        if not idx_name.startswith("sqlite_autoindex"):
                            uniq = "UNIQUE " if idx["unique"] else ""
                            idx_defs.append(f"  - {uniq}`{idx_name}`")
                except Exception:
                    pass

                tables_summary.append(
                    {
                        "name": name,
                        "type": itype,
                        "columns_count": len(cols),
                        "est_rows": est_rows,
                        "pk": ", ".join(pk_cols) if pk_cols else "None",
                    }
                )

                detail_str = [
                    f"### Table: `{name}` ({itype.upper()}) | Est. Rows: {est_rows}",
                    "**Columns:**",
                ]
                detail_str.extend(col_defs if col_defs else ["  - (No columns)"])
                if fk_defs:
                    detail_str.append("**Foreign Keys:**")
                    detail_str.extend(fk_defs)
                if idx_defs:
                    detail_str.append("**Indexes:**")
                    detail_str.extend(idx_defs)
                tables_detail.append("\n".join(detail_str))

            elapsed_ms = (time.perf_counter() - t0) * 1000

            lines = [
                f"# SQLite Schema Overview: `{os.path.basename(db_path)}`",
                f"- **Path:** `{db_path}`",
                f"- **Size:** {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)",
                f"- **Tables & Views Count:** {len(items)}\n",
                "## Tables Summary",
                "| Table Name | Type | Columns | Est. Rows | Primary Key |",
                "| :--- | :--- | :---: | :---: | :--- |",
            ]
            for ts in tables_summary:
                lines.append(
                    f"| `{ts['name']}` | {ts['type']} | {ts['columns_count']} | {ts['est_rows']} | {ts['pk']} |"
                )

            lines.append("\n## Detailed Table Definitions")
            lines.append("\n\n".join(tables_detail))
            lines.append(
                f"\n*Discovery Latency: {elapsed_ms:.2f} ms (O(1) non-blocking scan)*"
            )
            return "\n".join(lines)
        finally:
            conn.close()

    def describe_table(self, table: str, db: Optional[str] = None) -> str:
        """Detailed schema analysis for a specific table.

        Args:
            table: Name of the table or view.
            db: Optional path to database file.

        Returns:
            Markdown formatted table inspection report.
        """
        t0 = time.perf_counter()
        try:
            db_path = self.resolve_db_path(db)
            conn = self.get_connection(db_path, readonly=True)
        except Exception as e:
            return f"Error: {e}"

        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE name = ?",
                (table,),
            )
            tbl = cursor.fetchone()
            if not tbl:
                return f"Error: Table or view '{table}' does not exist in {db_path}."

            itype = tbl["type"]
            is_view = itype == "view"
            est_rows = self.get_estimated_row_count(cursor, table, is_view)

            safe_table = table.replace('"', '""')

            cursor.execute(f'PRAGMA table_xinfo("{safe_table}")')
            cols = cursor.fetchall()
            col_rows = []
            for c in cols:
                col_rows.append(
                    f"| {c['cid']} | `{c['name']}` | `{c['type'] or 'ANY'}` | "
                    f"{'YES' if not c['notnull'] else 'NO'} | "
                    f"`{c['dflt_value'] if c['dflt_value'] is not None else 'NULL'}` | "
                    f"{c['pk'] if c['pk'] > 0 else '-'} |"
                )

            cursor.execute(f'PRAGMA foreign_key_list("{safe_table}")')
            fks = cursor.fetchall()
            fk_rows = []
            for fk in fks:
                fk_rows.append(
                    f"| `{fk['from']}` | `{fk['table']}({fk['to']})` | {fk['on_update']} | {fk['on_delete']} |"
                )

            cursor.execute(f'PRAGMA index_list("{safe_table}")')
            indexes = cursor.fetchall()
            idx_rows = []
            for idx in indexes:
                idx_name = idx["name"]
                safe_idx = idx_name.replace('"', '""')
                cursor.execute(f'PRAGMA index_info("{safe_idx}")')
                idx_cols = [r["name"] for r in cursor.fetchall()]
                idx_rows.append(
                    f"| `{idx_name}` | {'YES' if idx['unique'] else 'NO'} | {', '.join(idx_cols)} |"
                )

            cursor.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                (table,),
            )
            triggers = cursor.fetchall()

            elapsed_ms = (time.perf_counter() - t0) * 1000

            out = [
                f"# Table Info: `{table}` ({itype.upper()})",
                f"- **Database:** `{db_path}`",
                f"- **Est. Rows:** {est_rows}",
                f"- **Query Time:** {elapsed_ms:.2f} ms\n",
                "### Columns",
                "| CID | Column Name | Data Type | Nullable | Default | PK Order |",
                "| :---: | :--- | :--- | :---: | :--- | :---: |",
            ]
            out.extend(col_rows)

            if fk_rows:
                out.append("\n### Foreign Keys")
                out.append("| From Column | Target | On Update | On Delete |")
                out.append("| :--- | :--- | :--- | :--- |")
                out.extend(fk_rows)

            if idx_rows:
                out.append("\n### Indexes")
                out.append("| Index Name | Unique | Indexed Columns |")
                out.append("| :--- | :---: | :--- |")
                out.extend(idx_rows)

            if triggers:
                out.append("\n### Triggers")
                for tr in triggers:
                    out.append(f"```sql\n{tr['sql']}\n```")

            if tbl["sql"]:
                out.append("\n### SQL DDL Definition")
                out.append(f"```sql\n{tbl['sql']}\n```")

            return "\n".join(out)
        finally:
            conn.close()

    @staticmethod
    def _normalize_params(
        params: Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...], str]]
    ) -> Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...]]]:
        """Defensively parse and normalize parameters for SQLite execution.

        Handles JSON-stringified payloads from LLMs, strips parameter prefixes
        (:key, $key, @key), and serializes nested objects to JSON.

        Args:
            params: Raw parameter input from client.

        Returns:
            Normalized parameters suitable for sqlite3 cursor execution.
        """
        if params is None:
            return None

        # 1. Parse JSON string if sent as a raw string by LLM/client
        if isinstance(params, str):
            clean_str = params.strip()
            if (clean_str.startswith("[") and clean_str.endswith("]")) or (
                clean_str.startswith("{") and clean_str.endswith("}")
            ):
                try:
                    params = json.loads(clean_str)
                except Exception:
                    pass

        # 2. Dict handling (Named parameters)
        if isinstance(params, dict):
            normalized_dict = {}
            for k, v in params.items():
                clean_key = str(k).lstrip(":$@")
                if isinstance(v, (dict, list)):
                    normalized_dict[clean_key] = json.dumps(
                        v, ensure_ascii=False
                    )
                else:
                    normalized_dict[clean_key] = v
            return normalized_dict

        # 3. List/Tuple handling (Positional parameters)
        if isinstance(params, (list, tuple)):
            normalized_list = []
            for v in params:
                if isinstance(v, (dict, list)):
                    normalized_list.append(json.dumps(v, ensure_ascii=False))
                else:
                    normalized_list.append(v)
            return normalized_list

        # 4. Single primitive value
        return [params]

    def execute_query(
        self,
        sql: str,
        params: Optional[
            Union[List[Any], Dict[str, Any], Tuple[Any, ...], str]
        ] = None,
        db: Optional[str] = None,
        readonly: Optional[bool] = None,
        format: str = "table",
        cell_max_chars: Optional[int] = None,
    ) -> str:
        """Execute a SQL query with parameter binding, formatting & watchdog.

        Args:
            sql: SQL statement to execute.
            params: Optional positional or named parameter bindings.
            db: Optional path to database file.
            readonly: Override read-only security mode.
            format: Output format ('table', 'vertical', or 'json').
            cell_max_chars: Optional cell character limit override (0 for unlimited).

        Returns:
            Serialized query results or error message with diagnostic hints.
        """
        t0 = time.perf_counter()
        try:
            db_path = self.resolve_db_path(db)
        except Exception as e:
            return f"Error: {e}"

        is_readonly = self.readonly if readonly is None else readonly
        effective_cell_max_chars = (
            self.cell_max_chars if cell_max_chars is None else cell_max_chars
        )

        clean_sql = sql.strip()
        if not clean_sql:
            return "Error: Empty SQL query provided."

        if is_readonly:
            lines = [
                line.split("--")[0]
                for line in clean_sql.splitlines()
                if not line.strip().startswith("--")
            ]
            clean_sql_no_comment = " ".join(lines).strip()
            first_word = (
                clean_sql_no_comment.split()[0].upper()
                if clean_sql_no_comment.split()
                else ""
            )
            allowed_verbs = {"SELECT", "WITH", "PRAGMA", "EXPLAIN"}
            if first_word not in allowed_verbs:
                return (
                    f"Error: Operation '{first_word}' is forbidden in read-only mode. "
                    f"Only SELECT, WITH, PRAGMA, and EXPLAIN queries are permitted."
                )

        norm_params = self._normalize_params(params)

        try:
            conn = self.get_connection(db_path, readonly=is_readonly)
        except Exception as e:
            return f"Error connecting to database: {e}"

        cursor = conn.cursor()
        try:
            if norm_params is not None:
                cursor.execute(sql, norm_params)
            else:
                cursor.execute(sql)

            if cursor.description is None:
                if not is_readonly and conn.in_transaction:
                    conn.commit()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return (
                    f"Query executed successfully in {elapsed_ms:.2f} ms. "
                    f"Rows affected: {cursor.rowcount}."
                )

            col_names = [col[0] for col in cursor.description]
            rows = cursor.fetchmany(self.max_rows + 1)

            # Explicitly commit DML statements with RETURNING (e.g. INSERT...RETURNING)
            if not is_readonly and conn.in_transaction:
                try:
                    cursor.fetchall()  # Exhaust cursor to release statement lock before commit
                except Exception:
                    pass
                conn.commit()

            elapsed_ms = (time.perf_counter() - t0) * 1000

            has_more = len(rows) > self.max_rows
            display_rows = rows[: self.max_rows]

            summary_header = (
                f"**Execution Time:** {elapsed_ms:.2f} ms | "
                f"**Rows Returned:** {len(display_rows)}"
                + (
                    f" (capped at max limit of {self.max_rows})"
                    if has_more
                    else ""
                )
            )

            fmt_lower = format.strip().lower() if format else "table"

            if fmt_lower == "json":
                return format_json(
                    col_names,
                    display_rows,
                    cell_max_chars=effective_cell_max_chars,
                    max_bytes=self.max_bytes,
                    summary_header=summary_header,
                )
            elif fmt_lower == "vertical":
                return format_vertical_view(
                    col_names,
                    display_rows,
                    cell_max_chars=effective_cell_max_chars,
                    max_bytes=self.max_bytes,
                    summary_header=summary_header,
                )
            else:
                return format_markdown_table(
                    col_names,
                    display_rows,
                    cell_max_chars=effective_cell_max_chars,
                    max_bytes=self.max_bytes,
                    summary_header=summary_header,
                )

        except sqlite3.OperationalError as oe:
            if not is_readonly:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except Exception:
                    pass
            if "interrupted" in str(oe).lower():
                return (
                    f"Error: Query aborted by execution watchdog "
                    f"(exceeded CPU opcode budget of {self.opcode_limit:,} instructions)."
                )
            err_msg = str(oe)
            hint = get_fuzzy_schema_hint(conn, err_msg, sql)
            if hint:
                return f"SQLite OperationalError: {err_msg}\nSuggestion: {hint}"
            return f"SQLite OperationalError: {err_msg}"
        except sqlite3.ProgrammingError as pe:
            if not is_readonly:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except Exception:
                    pass
            return f"SQLite ProgrammingError (Parameter/Syntax): {pe}"
        except sqlite3.DatabaseError as de:
            if not is_readonly:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except Exception:
                    pass
            return f"SQLite DatabaseError: {de}"
        except Exception as e:
            if not is_readonly:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except Exception:
                    pass
            return f"Query Execution Error: {type(e).__name__}: {e}"
        finally:
            conn.close()

    def explain_query(
        self,
        sql: str,
        params: Optional[
            Union[List[Any], Dict[str, Any], Tuple[Any, ...], str]
        ] = None,
        db: Optional[str] = None,
    ) -> str:
        """Explain SQL query execution plan via EXPLAIN QUERY PLAN.

        Args:
            sql: SQL statement to analyze.
            params: Optional parameter bindings.
            db: Optional path to database file.

        Returns:
            Markdown table detailing the query execution plan.
        """
        t0 = time.perf_counter()
        try:
            db_path = self.resolve_db_path(db)
            conn = self.get_connection(db_path, readonly=True)
        except Exception as e:
            return f"Error: {e}"

        norm_params = self._normalize_params(params)
        cursor = conn.cursor()
        try:
            if norm_params is not None:
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}", norm_params)
            else:
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            rows = cursor.fetchall()
            elapsed_ms = (time.perf_counter() - t0) * 1000

            lines = [
                f"# Query Plan: `{sql}`",
                f"- **Database:** `{db_path}`",
                f"- **Time:** {elapsed_ms:.2f} ms\n",
                "| ID | Parent | Detail |",
                "| :---: | :---: | :--- |",
            ]
            for r in rows:
                rid = r[0]
                parent = r[1]
                detail = r[3] if len(r) > 3 else r[2]
                lines.append(f"| {rid} | {parent} | {detail} |")
            return "\n".join(lines)
        except sqlite3.OperationalError as oe:
            err_msg = str(oe)
            hint = get_fuzzy_schema_hint(conn, err_msg, sql)
            if hint:
                return f"Explain OperationalError: {err_msg}\nSuggestion: {hint}"
            return f"Explain OperationalError: {err_msg}"
        except Exception as e:
            return f"Explain Error: {e}"
        finally:
            conn.close()

    def export_query(
        self,
        sql: str,
        target_file: str,
        format: str = "csv",
        params: Optional[
            Union[List[Any], Dict[str, Any], Tuple[Any, ...], str]
        ] = None,
        db: Optional[str] = None,
    ) -> str:
        """Execute query and stream results directly to a local file (CSV or JSONL) with zero context token consumption.

        Args:
            sql: SQL query statement to execute.
            target_file: Destination file path on the local filesystem.
            format: Export file format ('csv' or 'jsonl', default: 'csv').
            params: Optional query parameter bindings.
            db: Optional database path.

        Returns:
            Markdown summary containing row count, file size, and execution latency.
        """
        t0 = time.perf_counter()
        try:
            db_path = self.resolve_db_path(db)
        except Exception as e:
            return f"Error: {e}"

        clean_sql = sql.strip()
        if not clean_sql:
            return "Error: Empty SQL query provided."

        fmt_lower = format.strip().lower() if format else "csv"
        if fmt_lower not in ("csv", "jsonl"):
            return (
                f"Error: Unsupported export format '{format}'. "
                f"Allowed export formats are 'csv' and 'jsonl'."
            )

        target_path = os.path.abspath(target_file)
        if self.allowed_dir and not _is_safe_path(target_path, self.allowed_dir):
            return (
                f"Error: Access denied: Target export file '{target_path}' "
                f"is outside allowed directory root '{self.allowed_dir}'."
            )
        parent_dir = os.path.dirname(target_path)
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                return f"Error: Failed to create target directory '{parent_dir}': {e}"

        norm_params = self._normalize_params(params)

        try:
            conn = self.get_connection(db_path, readonly=True)
        except Exception as e:
            return f"Error connecting to database: {e}"

        cursor = conn.cursor()
        try:
            if norm_params is not None:
                cursor.execute(sql, norm_params)
            else:
                cursor.execute(sql)

            if cursor.description is None:
                return "Error: Statement produced no result rows to export."

            col_names = [col[0] for col in cursor.description]
            total_rows = 0

            if fmt_lower == "csv":
                import csv

                with open(target_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(col_names)
                    while True:
                        batch = cursor.fetchmany(1000)
                        if not batch:
                            break
                        for row in batch:
                            writer.writerow(
                                [
                                    f"<BLOB {len(cell)}B>"
                                    if isinstance(cell, bytes)
                                    else cell
                                    for cell in row
                                ]
                            )
                        total_rows += len(batch)
            else:
                # jsonl format
                with open(target_path, "w", encoding="utf-8") as f:
                    while True:
                        batch = cursor.fetchmany(1000)
                        if not batch:
                            break
                        for row in batch:
                            row_dict = {}
                            for col_name, cell in zip(col_names, row):
                                if isinstance(cell, bytes):
                                    row_dict[col_name] = f"<BLOB {len(cell)}B>"
                                else:
                                    row_dict[col_name] = cell
                            f.write(
                                json.dumps(
                                    row_dict,
                                    ensure_ascii=False,
                                    default=str,
                                )
                                + "\n"
                            )
                        total_rows += len(batch)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            file_size_bytes = (
                os.path.getsize(target_path) if os.path.exists(target_path) else 0
            )
            file_size_mb = file_size_bytes / (1024 * 1024)

            return (
                f"# Query Export Successful\n"
                f"- **Destination File:** `{target_path}`\n"
                f"- **Format:** `{fmt_lower.upper()}`\n"
                f"- **Rows Exported:** {total_rows:,}\n"
                f"- **File Size:** {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)\n"
                f"- **Execution Time:** {elapsed_ms:.2f} ms"
            )

        except sqlite3.OperationalError as oe:
            if "interrupted" in str(oe).lower():
                return (
                    f"Error: Export aborted by execution watchdog "
                    f"(exceeded CPU opcode budget of {self.opcode_limit:,} instructions)."
                )
            err_msg = str(oe)
            hint = get_fuzzy_schema_hint(conn, err_msg, sql)
            if hint:
                return f"SQLite OperationalError: {err_msg}\nSuggestion: {hint}"
            return f"SQLite OperationalError: {err_msg}"
        except sqlite3.ProgrammingError as pe:
            return f"SQLite ProgrammingError: {pe}"
        except sqlite3.DatabaseError as de:
            return f"SQLite DatabaseError: {de}"
        except Exception as e:
            return f"Export Error: {type(e).__name__}: {e}"
        finally:
            conn.close()

    def list_dbs(self, directory: str = ".", max_depth: int = 2) -> str:
        """List SQLite databases in a directory or show configured default.

        Args:
            directory: Directory to search for database files.
            max_depth: Maximum recursion depth for directory scan.

        Returns:
            Markdown report of discovered SQLite database files.
        """
        dir_path = os.path.abspath(directory)
        if self.allowed_dir and not _is_safe_path(dir_path, self.allowed_dir):
            return (
                f"Error: Access denied: Directory '{dir_path}' "
                f"is outside allowed directory root '{self.allowed_dir}'."
            )
        if not os.path.isdir(dir_path):
            return f"Error: Directory not found: {dir_path}"

        valid_extensions = {".db", ".sqlite", ".sqlite3"}
        ignored_dirs = {
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".hypothesis",
        }
        found = []

        base_depth = dir_path.rstrip(os.path.sep).count(os.path.sep)
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [
                d
                for d in dirs
                if d not in ignored_dirs and not d.startswith(".")
            ]
            current_depth = (
                root.rstrip(os.path.sep).count(os.path.sep) - base_depth
            )
            if current_depth > max_depth:
                dirs.clear()
                continue

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in valid_extensions:
                    full_p = os.path.join(root, file)
                    try:
                        sz = os.path.getsize(full_p)
                        found.append((full_p, sz))
                    except Exception:
                        pass

        lines = [
            f"# SQLite Databases in `{dir_path}`",
            f"- Default Configured DB: `{self.default_db or 'None'}`",
            f"- Total found: {len(found)}\n",
            "| Path | Size (MB) |",
            "| :--- | :---: |",
        ]
        for p, sz in found:
            lines.append(f"| `{p}` | {sz / (1024 * 1024):.2f} MB |")
        return "\n".join(lines)
