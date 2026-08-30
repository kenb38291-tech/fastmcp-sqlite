# fastmcp-sqlite

[![PyPI version](https://img.shields.io/pypi/v/fastmcp-sqlite.svg?color=blue)](https://pypi.org/project/fastmcp-sqlite/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastmcp-sqlite.svg)](https://pypi.org/project/fastmcp-sqlite/)
[![CI Matrix](https://github.com/kenb38291-tech/fastmcp-sqlite/actions/workflows/ci.yml/badge.svg)](https://github.com/kenb38291-tech/fastmcp-sqlite/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

fastmcp-sqlite is an MCP server for SQLite databases, built for AI coding agents and autonomous LLM toolchains. It runs on Python's built-in `sqlite3` C-API and the official `FastMCP` framework with zero C++ compiler dependencies.

The server provides sub-millisecond O(1) schema discovery, token-efficient formatters, an opcode execution watchdog that aborts runaway queries within 5ms, and full transaction safety for DML statements with RETURNING clauses.

## Features and benchmark comparison

The table below compares fastmcp-sqlite against the standard Node.js implementation (`mcp-sqlite-server` using `better-sqlite3`), tested on a 400MB database with 4.57 million rows (`tracker.db`) and a wide 39-column schema (`aegis.db`):

| Capability / Metric | Node.js baseline (mcp-sqlite-server) | fastmcp-sqlite | Result |
| :--- | :--- | :--- | :--- |
| Schema discovery (400MB DB) | 79.4 ms to 86.9 ms (O(N) leaf scan via `COUNT(*)`) | 6.7 ms to 16.5 ms (O(1) rightmost leaf probe) | 5.3x to 12.7x faster |
| Token cost (39-col table) | 8,192 tokens (padded ASCII spaces) | 3,698 tokens (compact markdown) | 54.9% token savings |
| Wide table format | Not supported | Vertical record view (`format="vertical"`) | 42% fewer tokens vs JSON |
| Runaway query defense | Freezes CPU core indefinitely (100% lockup) | Aborts in 3.6 ms via opcode watchdog | Automatic runaway abort |
| DML RETURNING support | Drops returning records (`db.exec()`) | Fetches rows and commits transaction | Zero data loss |
| Parameter binding | None (forces raw SQL string concatenation) | Positional (`?`), named (`:k`, `$k`, `@k`), JSON | Safe parameter binding |
| Typo diagnostics | Generic SQLite syntax error | Suggests table and column names in 10 ms | Saves 1 LLM roundtrip |
| Memory footprint | 76.9 MB RSS (13 OS threads via Node.js runtime) | 44.4 MB RSS (4 OS threads via single Python process) | 42% less RAM |
| Build requirements | Requires node-gyp and Visual Studio C++ tools | Pure Python wheel with no build toolchain | Direct install on all platforms |

## Architecture

```text
+--------------------------------------------------------------------+
|          AI Agent / MCP Host (Claude, Cursor, Antigravity, Cline)   |
+---------------------------------+----------------------------------+
                                  | JSON-RPC over Stdio
+---------------------------------v----------------------------------+
|                    fastmcp-sqlite Server Engine                    |
|                                                                    |
|  +---------------------+  +---------------------+  +------------+  |
|  | O(1) Schema Probe   |  | Opcode Watchdog     |  | Diagnostics|  |
|  | (MAX(_rowid_))      |  | (1M Instruction Cap)|  | (Typo Fix) |  |
|  +---------------------+  +---------------------+  +------------+  |
|  | Multi-Format Tokenomics (Table, Vertical View, JSON, 24KB Cap) |  |
+---------------------------------+----------------------------------+
                                  | C-API sqlite3 (WAL, MMAP 256MB)
+---------------------------------v----------------------------------+
|                   SQLite Database File (.db / .sqlite)             |
+--------------------------------------------------------------------+
```

## Quickstart

Run directly with `uvx` without manual installation:

```bash
uvx fastmcp-sqlite --db /path/to/database.db
```

Or install from PyPI:

```bash
pip install fastmcp-sqlite
fastmcp-sqlite --db /path/to/database.db
```

## Client configuration

Add fastmcp-sqlite to your MCP client configuration file.

### Antigravity IDE and CLI

In `~/.gemini/antigravity/mcp_config.json` or project `.mcp.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "C:/path/to/database.db"]
    }
  }
}
```

### Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db"]
    }
  }
}
```

### Cursor IDE

In `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db"]
    }
  }
}
```

### Windsurf, Cline, and Roo-Code

In your MCP settings configuration:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db"]
    }
  }
}
```

## Available tools

The server registers five MCP tools:

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `schema` | `db` (optional) | Returns full database schema in O(1) time, including tables, views, columns, nullability, default values, primary keys, foreign keys, and indexes. |
| `query` | `sql`, `params`, `db`, `readonly`, `format` | Executes SQL queries with parameter binding, cell truncation, payload guards, and format choices (`table`, `vertical`, `json`). |
| `table_info` | `table`, `db` (optional) | Returns detailed schema for one table or view: columns, types, foreign keys, indexes, triggers, and DDL SQL. |
| `explain` | `sql`, `params`, `db` (optional) | Analyzes query execution plan using `EXPLAIN QUERY PLAN`. |
| `list_databases` | `directory` (optional) | Scans a directory tree to find `.db`, `.sqlite`, and `.sqlite3` files. |

## Token optimization and output formats

### Compact Markdown table (`format="table"`)

This is the default format for queries with fewer than 15 columns. It trims cell text longer than 200 characters and caps the total response at 24KB.

```markdown
**Execution Time:** 1.25 ms | **Rows Returned:** 3

| id | username | email | role |
| :--- | :--- | :--- | :--- |
| 1 | alice | alice@example.com | admin |
| 2 | bob | bob@example.com | user |
| 3 | charlie | charlie@example.com | user |
```

### Vertical record view (`format="vertical"`)

Use this format for wide tables with more than 20 columns, such as telemetry records or machine learning feature stores. It prints each record as a key-value list, preventing horizontal line wrapping and improving LLM parsing accuracy.

```markdown
**Execution Time:** 2.10 ms | **Rows Returned:** 1

### Record 1
- **id**: `1042`
- **device_guid**: `a9f3-8821-c4e1`
- **firmware_version**: `v4.2.1-prod`
- **battery_level**: `98.4%`
- **active_features**: `["gps", "accelerometer", "ble"]`
```

### Structured JSON (`format="json"`)

Returns a clean JSON array of objects. Binary BLOB fields are formatted as `<BLOB <length>B>`.

## Safety mechanisms

### Opcode instruction watchdog

To prevent runaway queries, such as infinite `WITH RECURSIVE` common table expressions or unbounded Cartesian joins, fastmcp-sqlite sets an opcode instruction limit using `sqlite3_progress_handler`:

```sql
WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt) SELECT count(*) FROM cnt;
```

The engine intercepts the execution loop and aborts the query in 3.6 ms once the budget (default: 1,000,000 opcodes) is reached.

### Fuzzy schema typo diagnostics

When a query fails because of a misspelled table or column name, the engine checks the schema and returns close matches in the error message:

```sql
SELECT * FROM usrs;
-- SQLite OperationalError: no such table: usrs
-- 👉 Suggestion: Table 'usrs' does not exist. Did you mean: `users`?
```

This diagnostic allows the agent to self-correct in the next turn without making an extra schema inspection tool call.

### Transaction safety for RETURNING queries

Unlike servers that route write queries through `.exec()` and drop returned records, fastmcp-sqlite reads all rows produced by DML statements with `RETURNING` clauses and commits the transaction explicitly.

## Command-line options

```text
usage: fastmcp-sqlite [-h] [--db DB] [--name NAME] [--read-only]
                      [--allow-write] [--max-rows MAX_ROWS]
                      [--max-bytes MAX_BYTES]
                      [--cell-max-chars CELL_MAX_CHARS]
                      [--opcode-limit OPCODE_LIMIT] [--timeout TIMEOUT] [-v]
                      [db_positional]

Production-Grade Token-Optimized FastMCP SQLite Server

positional arguments:
  db_positional         Path to SQLite database file (positional)

options:
  -h, --help            Show this help message and exit
  --db DB               Path to SQLite database file
  --name NAME           Server name for FastMCP (default: fastmcp-sqlite)
  --read-only           Enable strict read-only mode (default: True)
  --allow-write         Allow write operations (disables read-only)
  --max-rows MAX_ROWS   Maximum rows returned per query (default: 100)
  --max-bytes MAX_BYTES Maximum response payload bytes (default: 24KB)
  --cell-max-chars N    Maximum characters per cell before truncation (default: 200)
  --opcode-limit LIMIT  Opcode instruction watchdog limit (default: 1,000,000)
  --timeout TIMEOUT     SQLite busy timeout in seconds (default: 5.0)
  -v, --version         Show program version number and exit
```

## Running tests

Clone the repository and run the test suite with pytest:

```bash
git clone https://github.com/kenb38291-tech/fastmcp-sqlite.git
cd fastmcp-sqlite
pip install -e ".[dev]"
pytest -v
```

All 33 test cases cover concurrent WAL readers, DML RETURNING transactions, O(1) discovery, fuzzy schema suggestions, token formatters, and opcode watchdog aborts.

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 kenb38291-tech.
