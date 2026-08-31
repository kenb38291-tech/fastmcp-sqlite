"""FastMCP server factory and tool definitions for SQLite database operations.

Registers tools for schema discovery, query execution, deep table inspection,
execution plan explanation, and filesystem database discovery.
Supports Dual-SDK bridge (mcp v1 FastMCP and mcp v2 MCPServer architectures)
and rich JSON Schema 2020-12 parameter metadata.
"""

from typing import Annotated, Any, Dict, List, Optional, Union
from pydantic import Field

try:
    from mcp.server.fastmcp import FastMCP
    ServerFactory = FastMCP
except ImportError:
    try:
        from mcp.server.mcpserver import MCPServer

        class FastMCPAdapter:
            """Adapter providing FastMCP-compatible interface over MCPServer."""

            def __init__(self, name: str, **kwargs: Any) -> None:
                self._server = MCPServer(name, **kwargs)
                self._tools: Dict[str, Any] = {}

            def tool(
                self,
                name: Optional[str] = None,
                description: Optional[str] = None,
            ) -> Any:
                def decorator(func: Any) -> Any:
                    tool_name = name or func.__name__
                    self._tools[tool_name] = func
                    if hasattr(self._server, "tool"):
                        self._server.tool(name=name, description=description)(func)
                    return func

                return decorator

            def run(self, transport: str = "stdio") -> None:
                if hasattr(self._server, "run"):
                    self._server.run(transport=transport)

        ServerFactory = FastMCPAdapter
    except ImportError:
        raise ImportError(
            "Could not import FastMCP or MCPServer from 'mcp'. "
            "Please ensure 'mcp>=1.0.0' is installed."
        )

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
    allowed_dir: Optional[str] = None,
) -> Any:
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
        allowed_dir: Optional root directory boundary to restrict database access.

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
        allowed_dir=allowed_dir,
    )

    mcp = ServerFactory(server_name)

    @mcp.tool(
        name="schema",
        description=(
            "Get the schema of a SQLite database: all tables, views, columns, "
            "data types, constraints, indexes, foreign keys, and sub-millisecond O(1) row counts."
        ),
    )
    def schema(
        db: Annotated[
            str,
            Field(
                description="Optional path to a SQLite database file (.db, .sqlite, .sqlite3). Defaults to configured default database."
            ),
        ] = "",
    ) -> str:
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
        sql: Annotated[
            str,
            Field(description="The SQL query to execute in SQLite engine."),
        ],
        params: Annotated[
            Optional[Union[List[Any], Dict[str, Any], str]],
            Field(
                description="Optional query parameters (positional list, named dict, or JSON string)."
            ),
        ] = None,
        db: Annotated[
            str,
            Field(
                description="Optional path to SQLite database file. Defaults to configured default database."
            ),
        ] = "",
        readonly: Annotated[
            bool,
            Field(
                description="Enforce read-only mode via PRAGMA query_only and AST authorizer."
            ),
        ] = True,
        format: Annotated[
            str,
            Field(
                description="Output format: 'table' (compact Markdown), 'vertical' (wide records), or 'json'."
            ),
        ] = "table",
        cell_max_chars: Annotated[
            int,
            Field(
                description="Maximum characters per cell before truncation (default: 200, 0 = unlimited)."
            ),
        ] = 200,
    ) -> str:
        """Execute a SQL query with token-efficient formatting and safety watchdog."""
        return engine.execute_query(
            sql,
            params=params,
            db=db if db else None,
            readonly=readonly,
            format=format,
            cell_max_chars=cell_max_chars,
        )

    @mcp.tool(
        name="export_query",
        description=(
            "Execute a SQL query and stream results directly to a local CSV or JSONL file on disk. "
            "Zero token consumption, constant O(1) memory usage, ideal for large query exports."
        ),
    )
    def export_query(
        sql: Annotated[
            str,
            Field(description="The SQL query to execute and export to disk."),
        ],
        target_file: Annotated[
            str,
            Field(
                description="Destination file path on disk (e.g. 'output.csv' or 'data.jsonl')."
            ),
        ],
        format: Annotated[
            str,
            Field(
                description="Export file format: 'csv' (comma-separated values) or 'jsonl' (line-delimited JSON)."
            ),
        ] = "csv",
        params: Annotated[
            Optional[Union[List[Any], Dict[str, Any], str]],
            Field(
                description="Optional query parameters (positional list, named dict, or JSON string)."
            ),
        ] = None,
        db: Annotated[
            str,
            Field(
                description="Optional path to SQLite database file. Defaults to configured default database."
            ),
        ] = "",
    ) -> str:
        """Export query results directly to CSV or JSONL file on disk."""
        return engine.export_query(
            sql,
            target_file=target_file,
            format=format,
            params=params,
            db=db if db else None,
        )

    @mcp.tool(
        name="table_info",
        description=(
            "Get detailed info about a single table or view: columns, types, constraints, "
            "indexes, foreign keys, triggers, DDL SQL, and row count estimation."
        ),
    )
    def table_info(
        table: Annotated[
            str,
            Field(description="Exact name of the table or view to inspect."),
        ],
        db: Annotated[
            str,
            Field(
                description="Optional path to SQLite database file. Defaults to configured default database."
            ),
        ] = "",
    ) -> str:
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
        sql: Annotated[
            str,
            Field(description="The SQL query statement to analyze."),
        ],
        params: Annotated[
            Optional[Union[List[Any], Dict[str, Any], str]],
            Field(
                description="Optional query parameters (positional list, named dict, or JSON string)."
            ),
        ] = None,
        db: Annotated[
            str,
            Field(
                description="Optional path to SQLite database file. Defaults to configured default database."
            ),
        ] = "",
    ) -> str:
        """Explain query execution plan."""
        return engine.explain_query(sql, params=params, db=db if db else None)

    @mcp.tool(
        name="list_databases",
        description=(
            "List all SQLite database files (.db, .sqlite, .sqlite3) in a directory."
        ),
    )
    def list_databases(
        directory: Annotated[
            str,
            Field(
                description="Root directory path to search for SQLite databases (default: current directory '.')."
            ),
        ] = ".",
    ) -> str:
        """List SQLite databases in a given directory."""
        return engine.list_dbs(directory)

    return mcp
