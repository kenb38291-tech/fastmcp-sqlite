"""FastMCP SQLite Server - Production-Grade High-Performance SQLite MCP Server.

Designed for zero-overhead AI Agent integration, sub-millisecond O(1) schema discovery,
opcode execution watchdog protection, and token-optimized serialization.
"""

from typing import Optional, List

__version__ = "1.0.0"

def __getattr__(name: str):
    if name == "create_server":
        from .server import create_server

        return create_server
    if name == "SQLiteEngine":
        from .engine import SQLiteEngine

        return SQLiteEngine
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def main(argv: Optional[List[str]] = None) -> None:
    """Entrypoint for the CLI."""
    from .cli import main as _cli_main

    _cli_main(argv)


__all__ = ["SQLiteEngine", "create_server", "main", "__version__"]
