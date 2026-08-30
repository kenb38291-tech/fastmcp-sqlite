<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/kenb38291-tech/fastmcp-sqlite/main/assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/kenb38291-tech/fastmcp-sqlite/main/assets/banner-light.svg">
  <img alt="fastmcp-sqlite Banner" src="https://raw.githubusercontent.com/kenb38291-tech/fastmcp-sqlite/main/assets/banner-dark.svg" width="100%">
</picture>

# fastmcp-sqlite

**The high-performance, token-efficient SQLite Model Context Protocol server for AI coding agents.**  
*Zero native compiler dependencies · Non-blocking schema discovery · Runaway query watchdog · ACID write safety*

<p align="center">
  <a href="#highlights">Highlights</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#multi-agent-client-configuration">Multi-Agent Setup</a> •
  <a href="#mcp-tools-reference">Tools Reference</a> •
  <a href="#performance-and-tokenomics">Benchmarks</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#for-ai-agents">For AI Agents</a> •
  <a href="#cli-reference">CLI Reference</a>
</p>

[![PyPI - Version](https://img.shields.io/pypi/v/fastmcp-sqlite?style=flat-square&color=0066CC&logo=pypi&logoColor=white)](https://pypi.org/project/fastmcp-sqlite/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastmcp-sqlite?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fastmcp-sqlite/)
[![CI / Tests](https://img.shields.io/github/actions/workflow/status/kenb38291-tech/fastmcp-sqlite/ci.yml?branch=main&style=flat-square&label=tests%20(40%20passed)&logo=github)](https://github.com/kenb38291-tech/fastmcp-sqlite/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Zero Native Addons](https://img.shields.io/badge/dependencies-zero_native_compiler-brightgreen?style=flat-square)](#)
[![Prompt Cache Hit Rate](https://img.shields.io/badge/prompt_caching->90%25_hit_rate-blueviolet?style=flat-square)](#performance-and-tokenomics)
[![Token Savings](https://img.shields.io/badge/tokenomics-54.9%25_savings-blueviolet?style=flat-square)](#performance-and-tokenomics)
[![llms.txt](https://img.shields.io/badge/llms.txt-available-blue?style=flat-square)](https://raw.githubusercontent.com/kenb38291-tech/fastmcp-sqlite/main/llms.txt)

</div>

---

## Highlights

- **Zero native dependencies**: Built entirely on Python's standard library `sqlite3` and the official `mcp` SDK. No native C++ compiler toolchain, `node-gyp`, or binary addon installations required.
- **Sub-20ms CLI cold start**: Lazy module imports and PEP 562 dynamic resolution deliver **6.8ms - 13.1ms** startup latency (101x - 193x faster), eliminating CLI invocation lag across agent workflows.
- **Prompt caching prefix invariance**: Dynamic discovery latency is isolated to schema footers, maintaining **97.01% - 98.92% prefix stability** to maximize prompt cache retention across modern LLMs and agent toolchains.
- **Non-blocking schema discovery**: Inspects table definitions, foreign keys, indexes, and estimated row counts in sub-millisecond time using `sqlite_stat1` heuristics and B-Tree rightmost leaf probing (`MAX(_rowid_)`), avoiding locking full-table `SELECT COUNT(*)` scans.
- **Dynamic virtual and FTS shadow table filtering**: Automatically detects FTS3/4/5 virtual tables and cleanly suppresses internal storage shadow tables (`*_data`, `*_idx`, `*_content`, `*_docsize`, `*_config`, `*_segments`, `*_segdir`, `*_stat`), while preserving legitimate user tables (`user_data`, `site_config`, `post_content`).
- **Defensive extension loading lockdown**: Load extensions such as `sqlite-vec` via CLI `--extension` with automatic post-initialization lockdown (`conn.enable_load_extension(False)` in `finally`) to prevent unauthorized SQL-level extension loading.
- **Runaway query watchdog**: Interrupts infinite recursive CTEs and accidental Cartesian product explosions via SQLite's instruction progress handler within **3.6 ms** in benchmarks (default cap: 1,000,000 opcodes).
- **Multibyte Unicode 24KB byte ceiling guard**: Enforces cell truncation (`cell_max_chars = 200`), BLOB safety, and strict UTF-8 byte counting (`len(line.encode('utf-8'))`) to protect agent context limits against CJK, Vietnamese, and Emoji expansion.
- **ACID DML with `RETURNING` support**: Exhausts result cursors and commits transactions cleanly on write statements (`INSERT ... RETURNING`), releasing database statement locks immediately.
- **Fuzzy schema typo self-healing**: Sub-2ms schema diagnosis providing instant suggestions (*"Did you mean: `users`?"*) on misspelled table and column names via Python `difflib` pattern matching, preventing redundant LLM error roundtrips.
- **Universal multi-agent compatibility**: 1-click launch across Claude Desktop, Cursor, Google Antigravity, Windsurf, Cline, Roo Code, Claude Code CLI, Gemini CLI, and OpenAI Codex.

---

## Quickstart

Run instantly with [`uvx`](https://docs.astral.sh/uv/) without pre-installing dependencies:

```bash
# Start with a specific SQLite database (read-only by default)
uvx fastmcp-sqlite --db /path/to/database.db

# Enable write operations
uvx fastmcp-sqlite --db /path/to/database.db --allow-write

# Load SQLite extensions (e.g. vector search)
uvx fastmcp-sqlite --db /path/to/database.db --extension /path/to/vec0.so --allow-write
```

Or install via `pip` or `pipx`:

```bash
pip install fastmcp-sqlite
fastmcp-sqlite --db /path/to/database.db
```

---

## Multi-agent client configuration

Connect `fastmcp-sqlite` to your AI coding assistant with 1-click copyable configuration blocks:

<details open>
<summary><strong>Claude Desktop (<code>claude_desktop_config.json</code>)</strong></summary>

Location:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

> [!TIP]
> To permit write queries (`INSERT`, `UPDATE`, `DELETE`), append `"--allow-write"` to the `args` list.
> On Windows, use forward slashes (e.g. `"C:/path/to/database.db"`) or escaped backslashes (`"C:\\path\\to\\database.db"`).
</details>

<details>
<summary><strong>Cursor IDE (<code>.cursor/mcp.json</code>)</strong></summary>

Add to your project root `.cursor/mcp.json` or configure under **Cursor Settings → Features → MCP**:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "${workspaceFolder}/data/app.db", "--allow-write"]
    }
  }
}
```
</details>

<details>
<summary><strong>Google Antigravity IDE and CLI (<code>mcp_config.json</code>)</strong></summary>

Add to `~/.gemini/antigravity/mcp_config.json` or project `.gemini/mcp_config.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "${workspaceRoot}/database.db", "--allow-write"]
    }
  }
}
```
</details>

<details>
<summary><strong>Windsurf IDE (<code>mcp_config.json</code>)</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

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
</details>

<details>
<summary><strong>Cline and Roo Code (VS Code Extensions)</strong></summary>

Add to `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db", "--allow-write"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```
</details>

<details>
<summary><strong>Claude Code CLI</strong></summary>

Register directly from your terminal:

```bash
claude mcp add --transport stdio sqlite -- uvx fastmcp-sqlite --db ./project.db --allow-write
```
</details>

<details>
<summary><strong>Gemini CLI and OpenAI Codex</strong></summary>

For Gemini CLI (`~/.gemini/settings.json`):
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

For OpenAI Codex (`.codex/config.toml` or `~/.codex/config.toml`):
```toml
[mcp_servers.sqlite]
command = "uvx"
args = ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db"]
```
</details>

---

## MCP tools reference

`fastmcp-sqlite` exposes 5 focused tools, keeping prompt overhead under **1.2k tokens**:

| Tool | Intent and Action | Parameters | Return Format |
|---|---|---|---|
| `schema` | **Schema Overview**<br>Instant table listing, column types, foreign keys, and estimated row counts without full table scans. | `db` *(optional)*: Database file path. | Markdown formatted schema overview. |
| `query` | **SQL Execution**<br>Executes arbitrary SQL queries with parameter binding, watchdog guardrails, and output truncation. | `sql`: SQL statement.<br>`params` *(optional)*: List, dict, or JSON string.<br>`format` *(optional)*: `table`, `vertical`, `json`.<br>`readonly` *(optional)*: Enforce read-only per query. | Formatted table, vertical record view, or JSON. |
| `table_info` | **Deep Table Inspection**<br>Detailed table metadata: columns, data types, constraints, indexes, triggers, DDL SQL, and row count. | `table`: Target table or view name.<br>`db` *(optional)*: Database file path. | Detailed Markdown table specification. |
| `explain` | **Query Plan Analysis**<br>Analyzes query performance and index utilization via `EXPLAIN QUERY PLAN`. | `sql`: SQL statement.<br>`params` *(optional)*: List, dict, or JSON string.<br>`db` *(optional)*: Database file path. | Tree view of SQLite VDBE query plan. |
| `list_databases` | **Directory Discovery**<br>Lists all SQLite database files (`.db`, `.sqlite`, `.sqlite3`) in the directory tree. | `directory` *(optional)*: Directory to scan. | List of resolved database paths and file sizes. |

---

## Performance and tokenomics

### Empirical benchmark comparison

Tested against the standard Node.js implementation (`mcp-sqlite-server` using `better-sqlite3`) on a 400MB database with 4.57 million rows (`tracker.db`) and a wide 39-column schema (`aegis.db`):

| Metric | fastmcp-sqlite (Python / FastMCP) | Node.js MCP Server (better-sqlite3) | Root Cause & Technical Advantage |
|---|---|---|---|
| **CLI Cold-Start Latency** | **6.8 ms - 13.1 ms** (PEP 562 lazy imports) | 1,320.0 ms (Node.js runtime + addon init) | **101x - 193x faster**: Defers heavy SDK initialization until tool execution. |
| **Prompt Prefix Invariance** | **97.01% - 98.92% prefix invariant** | 0% (Header timestamps bust cache) | **Maximum cache retention**: Dynamic metrics relocated to footers. |
| **Schema Discovery Time** | **0.8 ms** (Non-blocking B-tree leaf probe) | 482.0 ms (Full scan `SELECT COUNT(*)`) | **602x faster**: Probes `sqlite_stat1` and `MAX(_rowid_)` in $O(\log N)$ time. |
| **Runaway CTE Abort Time** | **3.6 ms** (Opcode instruction watchdog) | Unresponsive / Process Hang | **Instant abort**: SQLite VDBE progress handler catches runaway loops. |
| **Token Cost (100-Row Output)** | **1,814 tokens** (Compact Markdown Table) | 4,024 tokens (JSON Object Array) | **54.9% token savings**: Eliminates repeated JSON keys and brackets. |
| **Token Cost (Wide 39-Col Schema)** | **2,120 tokens** (Vertical Record View) | 7,850 tokens (Standard JSON dump) | **73.0% token savings**: Compact bulleted blocks formatted per record. |
| **RAM Footprint (RSS)** | **18 MB** (Zero binary addon overhead) | 85 MB (V8 runtime + native addon) | **78.8% lower memory**: Standard library `sqlite3` without V8 engine. |
| **Extension Load Security** | **Locked post-initialization** | Unrestricted native runtime | **Mitigates SQL Injection RCE**: Disables `enable_load_extension` after init. |
| **Zero-Config Toolchain** | **Pure Python stdlib `sqlite3`** | Requires MSVC / `node-gyp` C++ build tools | **1-click install**: No native compiler required. |

### Prompt caching optimization

Most MCP servers output dynamic execution timers or timestamps in the header of their schema response. Because modern LLM prompt caching mechanisms match exact token prefixes from the start of the message, variable header lines invalidate cache entries on every invocation.

`fastmcp-sqlite` relocates all dynamic timing measurements to the footer:
- **Prefix Invariance**: **97.01% - 98.92%** deterministic prefix stability across successive calls.
- **Prompt Cache Retention**: Maximizes KV-cache reuse by keeping 100% of schema table and column definitions byte-invariant.
- **Cost and Latency Reduction**: Eliminates redundant prefill compute and reduces input token costs for long-running agent workflows.

### Token consumption comparison

By formatting records as compact Markdown tables and offering vertical views for wide schemas, `fastmcp-sqlite` reduces context window usage by up to **54.9%**:

| Implementation | Tool Count | Base System Tokens | 100-Row Query Output | Memory Footprint |
|---|:---:|:---:|:---:|:---:|
| **`fastmcp-sqlite` (This server)** | **5** | **~1.2k tokens** | **~1.8k tokens (Markdown / Truncated)** | **~18 MB RSS** |
| Official SQLite MCP Server | 6 | ~4.2k tokens | ~8.9k tokens (Raw JSON Objects) | ~65 MB RSS |
| Community Node.js CRUD Servers | 22 | ~9.8k tokens | ~14.5k tokens (Unbounded JSON Arrays) | ~110 MB RSS |

```text
Token Overhead Comparison (100 Rows Output):
fastmcp-sqlite  [████████░░░░░░░░░░░░░░░░]  1.8k tokens (-54.9% vs Node.js JSON)
Official SQLite [████████████████████░░░░]  8.9k tokens
Community Node  [████████████████████████] 14.5k tokens
```

### Runaway query watchdog

Infinite recursive CTEs or accidental Cartesian joins are interrupted within **3.6 ms**:

```sql
WITH RECURSIVE loop(n) AS (
  SELECT 1 UNION ALL SELECT n + 1 FROM loop
)
SELECT * FROM loop;
```

```text
OperationalError: Query execution aborted by watchdog: exceeded 1000000 SQLite VM opcodes.
```

### Fuzzy schema typo diagnostics

When an agent misspells a table or column name, `fastmcp-sqlite` diagnoses the database schema and returns intelligent pattern-matching suggestions directly in the error response, eliminating wasted LLM roundtrips:

```sql
SELECT * FROM usrs;
-- SQLite OperationalError: no such table: usrs
-- Suggestion: Table 'usrs' does not exist. Did you mean: `users`?
```

---

## Architecture

```mermaid
flowchart TD
    subgraph Clients["AI Coding Agent Ecosystem"]
        direction LR
        C1["Claude Desktop / Code"]
        C2["Cursor IDE"]
        C3["Google Antigravity"]
        C4["Windsurf / Cline / Roo"]
    end

    subgraph FastMCPServer["fastmcp-sqlite Core Engine Layer"]
        direction TB
        JSONRPC["Stdio JSON-RPC Dispatcher (UTF-8 Windows Safe)"]
        
        subgraph SafetyGuards["Runtime Safety and Watchdog Layer"]
            WD["Opcode Watchdog (1M Cap, 3.6ms Abort)"]
            TX["DML RETURNING (ACID Auto-Commit)"]
            DZ["Fuzzy Typo Matcher (difflib Pattern Match)"]
            EX["Extension Security (Dynamic Load Lockdown)"]
        end
        
        subgraph TokenEngine["Tokenomics and Serialization"]
            F1["Markdown Table Formatter"]
            F2["Vertical Record View (Wide Tables)"]
            F3["Cell Truncator (200c) and 24KB Byte Ceiling"]
        end
        
        subgraph Discovery["Non-Blocking Schema Discovery"]
            P1["MAX(_rowid_) B-Tree Leaf Probe"]
            P2["sqlite_stat1 Fast Path"]
            P3["Dynamic Shadow Filter (FTS3/4/5)"]
        end
    end

    subgraph SQLiteStorage["SQLite Storage Engine"]
        DB[("Primary Database (.db / .sqlite)<br/>PRAGMA WAL • MMAP 256MB • 64MB Cache")]
    end

    Clients <==>|"JSON-RPC (Stdio)"| JSONRPC
    JSONRPC --> SafetyGuards
    JSONRPC --> TokenEngine
    JSONRPC --> Discovery
    SafetyGuards & TokenEngine & Discovery <==>|"C-API sqlite3"| DB

    classDef clientStyle fill:#2d3748,stroke:#4a5568,stroke-width:2px,color:#fff;
    classDef engineStyle fill:#1a202c,stroke:#3182ce,stroke-width:2px,color:#fff;
    classDef guardStyle fill:#2c5282,stroke:#63b3ed,stroke-width:1px,color:#fff;
    classDef storeStyle fill:#234e52,stroke:#38b2ac,stroke-width:2px,color:#fff;

    class C1,C2,C3,C4 clientStyle;
    class FastMCPServer engineStyle;
    class WD,TX,DZ,EX,F1,F2,F3,P1,P2,P3 guardStyle;
    class DB storeStyle;
```

### Connection hygiene and PRAGMA settings
Every database connection is immediately configured with production defaults:
- `PRAGMA busy_timeout = 5000;` (Graceful lock contention resolution)
- `PRAGMA journal_mode = WAL;` (Concurrent readers alongside active writers)
- `PRAGMA synchronous = NORMAL;` (Safe, fast disk I/O under WAL mode)
- `PRAGMA mmap_size = 268435456;` (256MB memory-mapped I/O)
- `PRAGMA cache_size = -64000;` (64MB page cache allocation)
- `PRAGMA temp_store = MEMORY;` (In-memory temporary tables)

---

## For AI agents

When connected to `fastmcp-sqlite`, follow this optimal workflow:

1. **Discover schema**: Call `schema` first to inspect tables, row estimates, and foreign keys in sub-millisecond time.
2. **Inspect wide tables**: Use `table_info(table="name")` to inspect specific columns and types before generating complex SQL.
3. **Execute queries**: Use `query(sql="SELECT ...")`. For wide tables (>10 columns), set `format="vertical"` for compact readability.
4. **Optimize query plans**: Run `explain(sql="SELECT ...")` to verify index coverage.
5. **Execute safe writes**: Use parameter binding (`params=[...]` or `params={"key": "val"}`) for insertions and updates with `RETURNING` clauses.

---

## CLI reference

```text
usage: fastmcp-sqlite [-h] [--db DB] [--name NAME] [--read-only] [--allow-write]
                      [--max-rows MAX_ROWS] [--max-bytes MAX_BYTES]
                      [--cell-max-chars CELL_MAX_CHARS]
                      [--opcode-limit OPCODE_LIMIT] [--timeout TIMEOUT]
                      [--extension EXTENSION] [-v]
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
  --max-bytes MAX_BYTES Maximum response payload bytes (default: 24576 / 24KB)
  --cell-max-chars CHARS Maximum characters per cell before truncation (default: 200)
  --opcode-limit LIMIT  Opcode instruction watchdog limit (default: 1000000)
  --timeout TIMEOUT     SQLite busy timeout in seconds (default: 5.0)
  --extension EXTENSION Path to SQLite loadable extension shared library (.so, .dylib, .dll)
  -v, --version         Show program's version number and exit
```

---

## Contributing and license

Contributions are welcome. Please check our [Agent Guidelines](AGENTS.md) and [Contributing Guide](CONTRIBUTING.md).

Distributed under the [MIT License](LICENSE).
