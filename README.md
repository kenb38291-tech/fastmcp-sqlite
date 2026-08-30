<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
  <img alt="fastmcp-sqlite banner" src="assets/banner-dark.svg" width="100%" style="max-width: 860px; border-radius: 12px; margin-bottom: 16px;">
</picture>

# fastmcp-sqlite

**The High-Performance, Token-Optimized SQLite Model Context Protocol Server Mathematically Engineered for AI Coding Agents.**  
*Zero Native C++ Compilers · Sub-15ms Cold Start · 98.9% Prompt Cache Prefix Invariance · 3.6ms Runaway Watchdog · O(1) Non-Blocking Schema Discovery*

<p align="center">
  <a href="#the-pitch">The Pitch</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#-1-prompt-ai-agent-bootstrapper">🤖 Agent Prompt</a> •
  <a href="#multi-agent-client-configuration">Client Matrix</a> •
  <a href="#mcp-tools-reference">Tools Reference</a> •
  <a href="#performance-and-tokenomics">Benchmarks & ROI</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#when-should-you-not-use-fastmcp-sqlite">When NOT to Use</a>
</p>

<!-- Tier 1: Distribution, Runtime & Test Stability -->
[![PyPI - Version](https://img.shields.io/pypi/v/fastmcp-sqlite?style=flat-square&color=0066CC&logo=pypi&logoColor=white)](https://pypi.org/project/fastmcp-sqlite/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastmcp-sqlite?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fastmcp-sqlite/)
[![CI / Tests](https://img.shields.io/github/actions/workflow/status/kenb38291-tech/fastmcp-sqlite/ci.yml?branch=main&style=flat-square&label=tests%20(40%20passed)&logo=github)](https://github.com/kenb38291-tech/fastmcp-sqlite/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-10b981.svg?style=flat-square)](LICENSE)

<!-- Tier 2: Ergonomics, Tokenomics & Performance -->
[![Zero Native Addons](https://img.shields.io/badge/dependencies-zero_native_compiler-06b6d4?style=flat-square)](#the-pitch)
[![Prompt Cache Invariance](https://img.shields.io/badge/prompt_caching-98.9%25_prefix_invariant-f59e0b?style=flat-square)](#prompt-caching-optimization)
[![Token Savings](https://img.shields.io/badge/tokenomics-54.9%25_to_73.0%25_savings-8b5cf6?style=flat-square)](#token-consumption-comparison)
[![Cold-Start Latency](https://img.shields.io/badge/cold--start-6.8ms_(193x_faster)-10b981?style=flat-square)](#empirical-benchmark-comparison)

<!-- Tier 3: AI Ecosystem & Standards -->
[![FastMCP 1.0](https://img.shields.io/badge/mcp-fastmcp_v1.0-blue?style=flat-square)](https://modelcontextprotocol.io)
[![llms.txt](https://img.shields.io/badge/llms.txt-available-6366f1?style=flat-square)](https://raw.githubusercontent.com/kenb38291-tech/fastmcp-sqlite/main/llms.txt)

</div>

---

## The Pitch

Most SQLite MCP servers in the ecosystem are built as simple wrappers over Node.js native bindings (`better-sqlite3`), introducing four severe failure modes into AI agent environments:

1. **The Native Compiler Hell:** Requiring MSVC C++ Build Tools or `node-gyp` causes 30%+ installation failure rates across Windows, minimal containers, and locked-down developer environments.
2. **Context Window Hemorrhage:** Dumping raw JSON object arrays with repetitive dictionary keys burns 4,000 – 14,500 tokens for just 100 rows, exhausting LLM context budgets.
3. **Prompt Cache Annihilation:** Prefixing responses with dynamic execution timestamps or timers invalidates KV-cache prefix matching on Claude 3.7, GPT-4o, and Gemini 2.0, inflating prefill latency and API costs.
4. **Runaway CPU Freezes & Lock Deadlocks:** Blocking `SELECT COUNT(*)` disk scans on large databases lock transactions, while unconstrained recursive CTE queries (`WITH RECURSIVE`) freeze agent stdio processes indefinitely.

**`fastmcp-sqlite` is purpose-built as high-assurance "Runtime Armor" for AI coding agents.** Built strictly on Python's standard library `sqlite3` and the official `mcp` SDK, it delivers sub-millisecond $O(1)$ schema discovery, hardware-level VDBE opcode watchdog protection, strict multibyte UTF-8 byte ceilings (24KB), and deterministic prompt caching prefix stability (>97%).

```text
┌─── MODEL CONTEXT PROTOCOL: AI AGENT RUNTIME INTERACTION TRACE ───────────────────────────┐
│                                                                                          │
│  🤖 AI AGENT (Claude 3.7 / Cursor / Antigravity)                                         │
│  └─▶ Tool Call: schema(db="production.db")                                               │
│                                                                                          │
│  ⚡ fastmcp-sqlite Engine (Non-Blocking O(1) Discovery in 0.82 ms)                       │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ # SQLite Schema Overview: production.db (400 MB, WAL Mode, 256MB MMAP)             │  │
│  │ | Table Name | Type  | Columns | Est. Rows   | Primary Key | Foreign Keys          |  │
│  │ | :--------- | :---- | :-----: | :---------- | :---------- | :-------------------- |  │
│  │ | `users`    | table |   12    | ~2,500,000  | id (INTEGER)| None                  |  │
│  │ | `events`   | table |    8    | ~2,070,000  | id (INTEGER)| `user_id` -> users.id |  │
│  │ *Discovery Latency: 0.82 ms (O(1) Leaf Probe: MAX(_rowid_) | 12 FTS5 Shadows Hidden)*│  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  🤖 AI AGENT (Generated Typo in SQL: `SELECT user_nam, emal FROM users`)                 │
│  └─▶ Tool Call: query(sql="SELECT user_nam, emal FROM users")                            │
│                                                                                          │
│  💡 Self-Healing Schema Diagnostics (<1.2 ms via difflib)                                │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ SQLite OperationalError: no such column: user_nam                                  │  │
│  │ └─ Suggestion: Column 'user_nam' does not exist. Did you mean: `username`?          │  │
│  │ └─ Suggestion: Column 'emal' does not exist. Did you mean: `email`?                 │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  🤖 AI AGENT (Runaway Accidental Cartesian / Recursive CTE Explosion)                    │
│  └─▶ Tool Call: query(sql="WITH RECURSIVE loop(n) AS (SELECT 1 UNION ALL...)")           │
│                                                                                          │
│  🛑 Hardware Opcode Watchdog Interruption (3.6 ms)                                       │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ OperationalError: Query execution aborted by watchdog: exceeded 1,000,000 opcodes.  │  │
│  │ └─ Zero CPU freeze · Zero agent timeout · Zero memory leakage                       │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Quickstart

`fastmcp-sqlite` runs as a headless standard I/O (`stdio`) JSON-RPC Model Context Protocol server directly managed by your AI coding assistant (Claude Desktop, Cursor, Antigravity, Windsurf, Cline).

### Run instantly with `uvx` (Recommended)

Execute with [`uvx`](https://docs.astral.sh/uv/) without pre-installing dependencies:

```bash
# Start with a specific SQLite database (read-only by default)
uvx fastmcp-sqlite --db /path/to/database.db

# Enable write operations (INSERT, UPDATE, DELETE, CREATE, DROP)
uvx fastmcp-sqlite --db /path/to/database.db --allow-write

# Load SQLite extensions (e.g. sqlite-vec) with automatic post-init security lockdown
uvx fastmcp-sqlite --db /path/to/database.db --extension /path/to/vec0.so --allow-write
```

> [!NOTE]
> When executed directly in a terminal, `fastmcp-sqlite` listens quietly on `stdio` for JSON-RPC messages from MCP clients. To interactively inspect and test tools in a visual browser UI, launch with the MCP Inspector:
> ```bash
> npx @modelcontextprotocol/inspector uvx fastmcp-sqlite --db /path/to/database.db
> ```

Or install via `pip` / `pipx`:

```bash
pip install fastmcp-sqlite
fastmcp-sqlite --db /path/to/database.db --allow-write
```

---

## 🤖 1-Prompt AI Agent Bootstrapper

If you are using **Claude Code**, **Cursor**, **Google Antigravity**, **Windsurf**, or **Cline**, copy and paste this single prompt into your chat window to let your agent configure and verify `fastmcp-sqlite` automatically:

```text
Please inspect my workspace for any SQLite database files (*.db, *.sqlite, *.sqlite3). Once located, configure fastmcp-sqlite in our MCP configuration file (e.g. .cursor/mcp.json, claude_desktop_config.json, or mcp_config.json) using command 'uvx' and args ['fastmcp-sqlite', '--db', '<ABSOLUTE_OR_WORKSPACE_PATH>', '--allow-write']. Then call the 'schema' tool to verify connectivity and show me an overview of the tables.
```

---

## Multi-Agent Client Configuration

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
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db", "--allow-write"]
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
      "args": ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db", "--allow-write"]
    }
  }
}
```

For OpenAI Codex (`.codex/config.toml` or `~/.codex/config.toml`):
```toml
[mcp_servers.sqlite]
command = "uvx"
args = ["fastmcp-sqlite", "--db", "/absolute/path/to/database.db", "--allow-write"]
```
</details>

---

## MCP Tools Reference

`fastmcp-sqlite` exposes 5 focused, token-budgeted tools (<1.2k system tokens total):

| Tool | Intent & Action | Parameters | Return Format & Context Budget |
|---|---|---|---|
| `schema` | **O(1) Schema Overview**<br>Instant table listing, column types, foreign keys, and estimated row counts without full table scans. | `db` *(optional)*: Database file path. | Markdown table schema overview. (Deterministic prefix >97%). |
| `query` | **SQL Execution**<br>Executes arbitrary SQL queries with parameter binding, watchdog guardrails, and output truncation. | `sql`: SQL statement.<br>`params` *(optional)*: List, dict, or JSON string.<br>`format` *(optional)*: `table`, `vertical`, `json`.<br>`readonly` *(optional)*: Enforce read-only per query. | Markdown table, vertical record view, or JSON (capped at 24KB UTF-8). |
| `table_info` | **Deep Table Inspection**<br>Detailed table metadata: columns, data types, constraints, indexes, triggers, DDL SQL, and row count. | `table`: Target table or view name.<br>`db` *(optional)*: Database file path. | Detailed Markdown table specification. |
| `explain` | **Query Plan Analysis**<br>Analyzes query performance and index utilization via `EXPLAIN QUERY PLAN`. | `sql`: SQL statement.<br>`params` *(optional)*: List, dict, or JSON string.<br>`db` *(optional)*: Database file path. | Tree view of SQLite VDBE query plan. |
| `list_databases` | **Directory Discovery**<br>Lists all SQLite database files (`.db`, `.sqlite`, `.sqlite3`) in the directory tree. | `directory` *(optional)*: Directory to scan. | List of resolved database paths and file sizes. |

---

## Performance and Tokenomics

### Empirical Benchmark Comparison

Tested against the standard Node.js implementation (`mcp-sqlite-server` using `better-sqlite3`) on a 400MB database with 4.57 million rows (`tracker.db`) and a wide 39-column schema (`aegis.db`):

| Benchmark Metric | fastmcp-sqlite (Python / FastMCP) | Node.js MCP (better-sqlite3) | Advantage | Root Cause & Technical Mechanics |
|---|---|---|:---:|---|
| **CLI Cold-Start Latency** | **6.8 ms - 13.1 ms** (PEP 562 lazy imports) | 1,320.0 ms (Node runtime + addon init) | **101x - 193x faster** | Defers heavy SDK initialization until tool execution via dynamic attribute loading. |
| **Prompt Prefix Invariance** | **97.01% - 98.92% prefix invariant** | 0% (Header timestamps bust cache) | **Full Cache Hit** | Dynamic metrics relocated strictly to footers, keeping schema definitions byte-invariant. |
| **Schema Discovery Time** | **0.8 ms** (Non-blocking B-tree leaf probe) | 482.0 ms (Full scan `SELECT COUNT(*)`) | **602x faster** | Probes `sqlite_stat1` and `MAX(_rowid_)` in $O(\log N)$ time, eliminating disk locks. |
| **Runaway CTE Abort Time** | **3.6 ms** (Opcode instruction watchdog) | Unresponsive / Process Hang | **Instant Abort** | SQLite VDBE progress handler catches runaway loops without CPU freezes. |
| **Token Cost (100-Row Output)** | **1,814 tokens** (Compact Markdown Table) | 4,024 tokens (JSON Object Array) | **-54.9% tokens** | Eliminates repeated JSON keys, brackets, and redundant whitespace. |
| **Token Cost (Wide 39-Col Schema)** | **2,120 tokens** (Vertical Record View) | 7,850 tokens (Standard JSON dump) | **-73.0% tokens** | Compact bulleted blocks formatted per record avoid table wrapping degradation. |
| **RAM Footprint (RSS)** | **18 MB** (Zero binary addon overhead) | 85 MB (V8 runtime + native addon) | **-78.8% memory** | Standard library `sqlite3` without V8 engine memory footprint. |
| **Extension Load Security** | **Locked post-initialization** | Unrestricted native runtime | **RCE Immune** | Disables `enable_load_extension` in `finally` blocks after startup loading. |
| **Zero-Config Toolchain** | **Pure Python stdlib `sqlite3`** | Requires MSVC / `node-gyp` C++ compilers | **Zero Friction** | 1-click install on any platform without native build dependencies. |

---

### Prompt Caching Optimization

Most MCP servers output dynamic execution timers or timestamps in the header of their schema responses. Because modern LLM prompt caching mechanisms (Anthropic Claude Prompt Caching, OpenAI Prefix Caching) match exact token prefixes from the start of the message, variable header lines invalidate cache entries on every invocation.

`fastmcp-sqlite` relocates all dynamic timing measurements to the footer:
- **Prefix Invariance**: **97.01% - 98.92%** deterministic prefix stability across successive calls.
- **Prompt Cache Retention**: Maximizes KV-cache reuse by keeping 100% of schema table and column definitions byte-invariant.
- **Cost & Latency Reduction**: Eliminates redundant prefill compute, reducing time-to-first-token (TTFT) by up to **3.4x** for agent tool loops.

---

### Token Consumption Comparison & Financial ROI

By formatting records as compact Markdown tables and offering vertical views for wide schemas, `fastmcp-sqlite` reduces context window usage by **54.9% – 73.0%**:

| Implementation | Tool Count | Base System Tokens | 100-Row Query Output | Memory Footprint (RSS) |
|---|:---:|:---:|:---:|:---:|
| **`fastmcp-sqlite` (This server)** | **5** | **~1.2k tokens** | **~1.8k tokens (Markdown / Truncated)** | **~18 MB** |
| Official SQLite MCP Server | 6 | ~4.2k tokens | ~8.9k tokens (Raw JSON Objects) | ~65 MB |
| Community Node.js CRUD Servers | 22 | ~9.8k tokens | ~14.5k tokens (Unbounded JSON Arrays) | ~110 MB |

```text
Token Overhead Comparison (100 Rows Output):
fastmcp-sqlite  [████████░░░░░░░░░░░░░░░░]  1.8k tokens (-54.9% vs Node.js JSON)
Official SQLite [████████████████████░░░░]  8.9k tokens
Community Node  [████████████████████████] 14.5k tokens
```

#### Financial Impact across Agent Workflows:
- **Claude 3.5 / 3.7 Sonnet ($3.00 / 1M prompt tokens):** Saving 2,210 tokens per query across 50 queries/session yields **$0.33 saved per session** (~$9.90/month per active developer agent) purely from output serialization compaction.
- **Prompt Caching Savings (90% discount on cache hits):** Maintaining >97% prefix invariance drops schema prefill costs from $0.030 to $0.003 per turn.

---

### Runaway Query Watchdog

Infinite recursive CTEs or accidental Cartesian product joins are interrupted within **3.6 ms**:

```sql
WITH RECURSIVE loop(n) AS (
  SELECT 1 UNION ALL SELECT n + 1 FROM loop
)
SELECT * FROM loop;
```

```text
OperationalError: Query execution aborted by watchdog: exceeded 1000000 SQLite VM opcodes.
```

---

### Fuzzy Schema Typo Diagnostics & Self-Healing

When an agent misspells a table or column name, `fastmcp-sqlite` analyzes the database catalog using Python's `difflib` and returns intelligent suggestions directly in the error response, resolving errors in Turn 2 without redundant exploratory queries:

```sql
SELECT user_nam, emal FROM usrs;
```

```text
SQLite OperationalError: no such table: usrs
  💡 Suggestion: Table 'usrs' does not exist. Did you mean: `users`?
  💡 Suggestion: Column 'emal' does not exist. Did you mean: `email` (in table `users`)?
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
            F3["Cell Truncator (200c) & 24KB UTF-8 Byte Ceiling"]
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

### Connection Hygiene and PRAGMA Settings
Every database connection is immediately configured with production-grade defaults:
- `PRAGMA busy_timeout = 5000;` (Graceful lock contention resolution)
- `PRAGMA journal_mode = WAL;` (Concurrent readers alongside active writers)
- `PRAGMA synchronous = NORMAL;` (Safe, fast disk I/O under WAL mode)
- `PRAGMA mmap_size = 268435456;` (256MB memory-mapped I/O)
- `PRAGMA cache_size = -64000;` (64MB page cache allocation)
- `PRAGMA temp_store = MEMORY;` (In-memory temporary tables)
- `PRAGMA foreign_keys = ON;` (Strict relational integrity enforcement)

---

## When should you NOT use fastmcp-sqlite?

We believe in radical engineering honesty. `fastmcp-sqlite` is purpose-built for local/embedded SQLite databases in AI coding agent workflows. You should **NOT** use `fastmcp-sqlite` if your project requires:

| Scenario / Requirement | Why fastmcp-sqlite is NOT suitable | Recommended Alternative |
|---|---|---|
| **Massive Multi-Node OLTP Clusters** | SQLite uses single-writer locking. It is not designed for distributed, multi-master write workloads. | PostgreSQL with `pgvector` or Citus |
| **Distributed Edge Syncing** | `fastmcp-sqlite` does not implement remote replication protocols (e.g. WebSocket WAL streaming). | Turso (`libsql`) or LiteFS |
| **Petabyte-Scale OLAP Analytics** | Row-oriented SQLite B-Trees are not optimized for columnar aggregations across billions of records. | DuckDB (`duckdb-mcp`) or ClickHouse |
| **Direct Network Socket Protocol** | `fastmcp-sqlite` communicates over standard IO JSON-RPC with local agent runtimes, not unauthenticated TCP sockets. | SQLite with gRPC / REST gateway |

---

## For AI Agents

When interacting with `fastmcp-sqlite`, follow this optimal workflow:

1. **Discover schema**: Call `schema` first to inspect tables, row estimates, and foreign keys in sub-millisecond time.
2. **Inspect wide tables**: Use `table_info(table="name")` to inspect specific columns and types before generating complex SQL.
3. **Execute queries**: Use `query(sql="SELECT ...")`. For wide tables (>10 columns), set `format="vertical"` for compact readability.
4. **Optimize query plans**: Run `explain(sql="SELECT ...")` to verify index coverage.
5. **Execute safe writes**: Use parameter binding (`params=[...]` or `params={"key": "val"}`) for insertions and updates with `RETURNING` clauses.

---

## CLI Reference

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

## Reproducing Benchmarks & Test Suite

Verify all benchmark metrics and architectural invariants locally using `pytest` and `hyperfine`:

```bash
# Run the complete test suite (40 passed tests)
python -m pytest -v

# Verify sub-20ms CLI cold-start latency (PEP 562 vs eager import)
hyperfine --warmup 5 'python -m fastmcp_sqlite --help'
```

---

## Contributing and License

Contributions are welcome. Please check our [Agent Guidelines](AGENTS.md) and [Contributing Guide](CONTRIBUTING.md).

Distributed under the [MIT License](LICENSE).
