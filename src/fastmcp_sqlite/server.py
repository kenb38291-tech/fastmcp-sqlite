"""FastMCP server factory and tool definitions for SQLite database operations.

Registers tools for schema discovery, query execution, deep table inspection,
execution plan explanation, and filesystem database discovery.
"""

from typing import Any, Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

from .engine import SQLiteEngine


def create_server(
    db_path: Optional[str] = None,
    server_name: str = "fastmcp-sqlite",
    readonly: bool = True,
    max_rows: int = 100,
    max_bytes: int = 24576,
    cell_max_chars: int = 200,
    opcode_limit: int = 1_000_000,
    timeout: float = 5.0,
    extensions: Optional[List[str]] = None,
) -> FastMCP:
    """Create and configure FastMCP SQLite server with registered tools.

    Args:
        db_path: Optional default database file path.
        server_name: Name identifier for the FastMCP server instance.
        readonly: Default read-only security mode.
        max_rows: Maximum rows returned per query.
        max_bytes: Maximum response payload size in bytes.
        cell_max_chars: Maximum characters per cell before truncation.
        opcode_limit: SQLite opcode instruction limit for runaway watchdog.
        timeout: Busy timeout in seconds for lock contention.
        extensions: Optional list of paths to loadable SQLite extension libraries.

    Returns:
        Configured FastMCP server instance ready for stdio or SSE transport.
    """
    engine = SQLiteEngine(
        default_db=db_path,
        readonly=readonly,
        max_rows=max_rows,
        max_bytes=max_bytes,
        cell_max_chars=cell_max_chars,
        opcode_limit=opcode_limit,
        timeout=timeout,
        extensions=extensions,
    )

    mcp = FastMCP(server_name)

    @mcp.tool(
        name="schema",
        description=(
            "Get the schema of a SQLite database: all tables, views, columns, "
            "data types, constraints, indexes, foreign keys, and sub-millisecond O(1) row counts."
        ),
    )
    def schema(db: str = "") -> str:
        """Get database schema overview in O(1) time."""
        return engine.describe_schema(db if db else None)

    @mcp.tool(
        name="query",
        description=(
            "Execute a SQL query against a SQLite database with parameter binding and "
            "token-efficient formatting. Returns results as Markdown table, vertical record view, "
            "or JSON. Protected by opcode execution watchdog and cell truncation."
        ),
    )
    def query(
        sql: str,
        params: Optional[Union[List[Any], Dict[str, Any], str]] = None,
        db: str = "",
        readonly: bool = True,
        format: str = "table",
    ) -> str:
        """Execute a SQL query with token-efficient formatting and safety watchdog."""
        return engine.execute_query(
            sql,
            params=params,
            db=db if db else None,
            readonly=readonly,
            format=format,
        )

    @mcp.tool(
        name="table_info",
        description=(
            "Get detailed info about a single table or view: columns, types, constraints, "
            "indexes, foreign keys, triggers, DDL SQL, and row count estimation."
        ),
    )
    def table_info(table: str, db: str = "") -> str:
        """Get deep schema inspection for a specific table or view."""
        return engine.describe_table(table, db if db else None)

    @mcp.tool(
        name="explain",
        description=(
            "Explain the query plan for a SQL query (EXPLAIN QUERY PLAN). "
            "Helps analyze indexes and optimize query performance."
        ),
    )
    def explain(
        sql: str,
        params: Optional[Union[List[Any], Dict[str, Any], str]] = None,
        db: str = "",
    ) -> str:
        """Explain query execution plan."""
        return engine.explain_query(sql, params=params, db=db if db else None)

    @mcp.tool(
        name="list_databases",
        description=(
            "List all SQLite database files (.db, .sqlite, .sqlite3) in a directory."
        ),
    )
    def list_databases(directory: str = ".") -> str:
        """List SQLite databases in a given directory."""
        return engine.list_dbs(directory)

    return mcp
