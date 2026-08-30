# Agent guidelines for fastmcp-sqlite

This document defines the architectural invariants, development workflows, test commands, and coding standards for AI coding agents working on fastmcp-sqlite.

## What this repository contains

fastmcp-sqlite is a Model Context Protocol (MCP) server for SQLite databases, written in Python using standard library `sqlite3` and the official `mcp` SDK. It has zero external database dependencies and requires no native C++ compiler toolchain.

The server exposes five tools over standard IO JSON-RPC:
- `schema`: O(1) database schema overview with row counts, table definitions, foreign keys, and indexes.
- `query`: SQL statement execution with parameter binding, watchdog protection, cell truncation, payload guards, and multiple serialization formats.
- `table_info`: Detailed schema inspection for a single table or view, including column types, constraints, foreign keys, triggers, and DDL SQL.
- `explain`: Query plan analysis using SQLite's EXPLAIN QUERY PLAN.
- `list_databases`: Directory discovery of SQLite database files (.db, .sqlite, .sqlite3).

## Repository layout

```text
fastmcp-sqlite/
├── src/
│   └── fastmcp_sqlite/
│       ├── __init__.py         # Package exports and semantic version (__version__ = "1.0.0")
│       ├── __main__.py         # Module runner for python -m fastmcp_sqlite
│       ├── cli.py              # CLI argument parser and Windows UTF-8 stdio setup
│       ├── engine.py           # Core SQLiteEngine, connection tuning, watchdog, execution
│       ├── formatters.py       # Markdown tables, vertical record views, JSON, truncation
│       ├── diagnostics.py      # Fuzzy schema typo matching ("Did you mean?")
│       └── server.py           # FastMCP server factory and tool registrations
├── tests/
│   ├── conftest.py             # Temporary test database fixtures
│   ├── test_concurrency.py     # Concurrent WAL readers and writer tests
│   ├── test_dml.py             # DML RETURNING ACID commit and parameter binding tests
│   ├── test_engine.py          # O(1) discovery, path resolution, PRAGMA tests
│   ├── test_fuzzy.py           # Typo autocorrection suggestion tests
│   ├── test_tokenomics.py      # Formatters, cell truncation, and 24KB ceiling tests
│   └── test_watchdog.py        # Infinite CTE and Cartesian explosion abort tests
├── .github/
│   └── workflows/
│       ├── ci.yml              # Matrix CI across Python 3.10-3.14 on Linux, macOS, Windows
│       └── publish.yml         # Automated PyPI release upon GitHub release tags
├── pyproject.toml              # PEP 621 build configuration using Hatchling
├── AGENTS.md                   # Agent developer guidelines
├── README.md                   # User and developer documentation
└── LICENSE                     # MIT License
```

## Core architectural invariants

When modifying this codebase, you must preserve the following architectural guarantees:

### 1. Connection hygiene and PRAGMAs
Every database connection created in `engine.py` must configure these settings immediately:
- `PRAGMA busy_timeout = 5000;` to resolve lock contention.
- `PRAGMA journal_mode = WAL;` to enable concurrent readers alongside an active writer.
- `PRAGMA synchronous = NORMAL;` for safe, fast disk writes under WAL.
- `PRAGMA mmap_size = 268435456;` to map up to 256MB into virtual memory.
- `PRAGMA cache_size = -64000;` to allocate a 64MB page cache.
- `PRAGMA temp_store = MEMORY;` for memory-backed temporary tables.
- `PRAGMA query_only = ON;` when running in read-only mode.

### 2. O(1) Schema discovery
Never replace `get_estimated_row_count` with `SELECT COUNT(*)`. Full scans lock large databases and cause MCP connection timeouts. The engine must check `sqlite_stat1` first, skip views and `WITHOUT ROWID` tables, and probe `SELECT MAX(_rowid_)` to read the rightmost leaf page in constant time.

### 3. Runaway query protection
Do not remove the progress handler. Infinite recursive queries or Cartesian joins must be caught by `conn.set_progress_handler(progress_watchdog, 10000)`. If a query exceeds the configured opcode limit (default: 1,000,000 instructions), the watchdog returns 1 to interrupt SQLite execution. The engine catches the operational error and returns a clean abort message within 5ms.

### 4. DML RETURNING and transaction commits
When executing write statements containing RETURNING clauses (such as `INSERT INTO ... RETURNING id`), `cursor.description` is populated. The engine must fetch the rows, exhaust the cursor to release statement locks, and call `conn.commit()`. Never use `.exec()` or discard returning records.

### 5. Parameter normalization
The engine must accept positional lists, named dictionaries, and JSON-stringified payloads. Strip parameter prefixes (`:`, `$`, `@`) before passing dictionaries to SQLite. Serialize nested dictionaries and lists to JSON strings automatically.

### 6. Token limits and truncation
Formatters in `formatters.py` must enforce:
- Cell character limit: Strings exceeding `cell_max_chars` (default: 200) are truncated with `…[truncated]`.
- BLOB representation: Raw bytes are formatted as `<BLOB <length>B>`.
- Payload byte ceiling: Output exceeding `max_bytes` (default: 24,576 bytes / 24KB) stops processing further rows and appends a limit notice.

### 7. Dependency boundaries
The package must remain lightweight. Do not add heavy third-party dependencies. The runtime requires only `mcp>=1.0.0` and Python's standard library (`sqlite3`, `json`, `difflib`, `re`, `argparse`, `os`, `sys`, `time`). Development dependencies are restricted to `pytest`.

## Development and testing commands

Run all tests using pytest from the repository root:

```bash
python -m pytest -v
```

Run a specific test module:

```bash
python -m pytest tests/test_engine.py -v
python -m pytest tests/test_watchdog.py -v
python -m pytest tests/test_dml.py -v
python -m pytest tests/test_tokenomics.py -v
python -m pytest tests/test_fuzzy.py -v
python -m pytest tests/test_concurrency.py -v
```

Test CLI execution directly:

```bash
python -m fastmcp_sqlite --help
python -m fastmcp_sqlite --version
```

Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

## Code style and engineering standards

- Target Python 3.10 through 3.14.
- Include explicit type annotations on all function and method signatures.
- Write docstrings in plain language. State what the function does directly.
- Catch specific exceptions (`sqlite3.OperationalError`, `sqlite3.ProgrammingError`, `FileNotFoundError`) before falling back to generic Exception handlers.
- Always close connections in `finally` blocks. Rollback uncommitted transactions if an exception occurs during write operations.
- Avoid em-dashes (`—`) and decorative emojis in documentation, log messages, and error strings.
- Use sentence case for all Markdown headings.
