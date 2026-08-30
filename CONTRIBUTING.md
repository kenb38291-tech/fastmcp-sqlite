# Contributing to FastMCP SQLite

Thank you for your interest in contributing to `fastmcp-sqlite`. We welcome contributions that adhere to our core design principles: **sub-millisecond schema discovery, zero external database dependencies, token-efficient serialization, and robust runaway query protection**.

## Development setup

1. Clone the repository:
   ```bash
   git clone https://github.com/kenb38291-tech/fastmcp-sqlite.git
   cd fastmcp-sqlite
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Linux/macOS:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate
   ```

3. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Running tests

Run the complete pytest suite before submitting any pull request:

```bash
python -m pytest -v
```

To run a specific test module:
```bash
python -m pytest tests/test_watchdog.py -v
```

## Architectural invariants

When proposing code changes, you must preserve these architectural guarantees:
- **Zero external database dependencies:** Use only the Python standard library `sqlite3` module and the official `mcp` SDK.
- **Constant-time schema discovery:** Never replace `get_estimated_row_count` with `COUNT(*)`. Use `sqlite_stat1` and rightmost `MAX(_rowid_)` B-tree leaf probing.
- **Runaway query protection:** Preserve `conn.set_progress_handler` on all query execution paths.
- **Transaction safety:** Ensure DML write queries with `RETURNING` clauses commit properly and release locks.
- **Token limits & Truncation:** Enforce 200-character cell truncation and 24KB payload ceiling guards.
- **Type annotations & Docstrings:** All public functions and methods must include explicit type hints and clean docstrings.

## Submitting pull requests

1. Create a feature branch (`git checkout -b feature/my-feature`).
2. Commit your changes with clear, descriptive commit messages.
3. Ensure all tests pass (`python -m pytest -v`).
4. Push your branch to GitHub and open a Pull Request.
