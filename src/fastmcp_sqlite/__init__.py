"""FastMCP SQLite Server - Production-Grade High-Performance SQLite MCP Server.

Designed for zero-overhead AI Agent integration, sub-millisecond O(1) schema discovery,
opcode execution watchdog protection, and token-optimized serialization.
"""

from typing import Optional, List

__version__ = "1.0.0"

from .engine import SQLiteEngine
from .server import create_server


def main(argv: Optional[List[str]] = None) -> None:
    """Entrypoint for the CLI."""
    from .cli import main as _cli_main

    _cli_main(argv)


__all__ = ["SQLiteEngine", "create_server", "main", "__version__"]
