"""Command-line interface (CLI) entrypoint for FastMCP SQLite Server.

Supports 1-click startup via `uvx fastmcp-sqlite --db path/to/database.db` or standard
command line invocations.
"""

import argparse
import os
import sys
from typing import Optional

from . import __version__


def setup_utf8_io() -> None:
    """Ensure standard IO streams use UTF-8 on Windows environments."""
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Optional[list[str]] = None) -> None:
    """Parse CLI arguments and run the FastMCP SQLite server over Stdio."""
    setup_utf8_io()

    parser = argparse.ArgumentParser(
        prog="fastmcp-sqlite",
        description="Production-Grade Token-Optimized FastMCP SQLite Server",
    )
    parser.add_argument(
        "db_positional",
        nargs="?",
        default=None,
        help="Path to SQLite database file (positional)",
    )
    parser.add_argument(
        "--db", default=None, help="Path to SQLite database file"
    )
    parser.add_argument(
        "--name", default="fastmcp-sqlite", help="Server name for FastMCP"
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=True,
        help="Enable strict read-only mode (default: True)",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        default=False,
        help="Allow write operations (disables read-only)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=100,
        help="Maximum rows returned per query (default: 100)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=24576,
        help="Maximum response payload bytes (default: 24KB)",
    )
    parser.add_argument(
        "--cell-max-chars",
        type=int,
        default=200,
        help="Maximum characters per cell (default: 200)",
    )
    parser.add_argument(
        "--opcode-limit",
        type=int,
        default=1_000_000,
        help="Opcode instruction watchdog limit (default: 1,000,000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="SQLite busy timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--extension",
        action="append",
        type=str,
        default=None,
        help="Path to SQLite loadable extension shared library (.so, .dylib, .dll)",
    )
    parser.add_argument(
        "--allowed-dir",
        type=str,
        default=None,
        help="Root directory boundary to restrict database and export operations (Zero-Trust sandbox)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)

    # Determine database path (flag takes precedence over positional)
    db_target = args.db or args.db_positional
    readonly_mode = not args.allow_write

    # If db target exists and server name is default, name it cleanly
    server_name = args.name
    if server_name == "fastmcp-sqlite" and db_target:
        base = os.path.splitext(os.path.basename(db_target))[0]
        server_name = f"{base}-db"

    # Lazy import create_server to guarantee sub-20ms cold-start for CLI help and version
    from .server import create_server

    server = create_server(
        db_path=db_target,
        server_name=server_name,
        readonly=readonly_mode,
        max_rows=args.max_rows,
        max_bytes=args.max_bytes,
        cell_max_chars=args.cell_max_chars,
        opcode_limit=args.opcode_limit,
        timeout=args.timeout,
        extensions=args.extension,
        allowed_dir=args.allowed_dir,
    )

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
