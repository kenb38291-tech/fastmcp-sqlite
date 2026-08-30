# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-30

### Added
- Complete rewrite using standard library `sqlite3` and the official `mcp` SDK.
- Sub-millisecond O(1) Schema Discovery engine using `sqlite_stat1` and `MAX(_rowid_)` B-tree leaf probing.
- Opcode Instruction Watchdog (`conn.set_progress_handler`) interrupting runaway CTEs and Cartesian explosions within 5ms.
- Token-efficient serialization suite: Markdown Table, Vertical Record View (`format="vertical"`), and JSON with cell truncation and 24KB payload ceiling guard.
- Fuzzy Schema Self-Healing diagnostics providing instant "Did you mean?" suggestions on misspelled tables or columns.
- 100% ACID transaction safety and commit persistence for DML `RETURNING` clauses (`INSERT/UPDATE/DELETE ... RETURNING`).
- Multi-dialect parameter binding supporting positional lists, named parameters (`:key`, `$key`, `@key`), and JSON strings.
- Full matrix CI/CD covering Linux, macOS, and Windows across Python 3.10 through 3.14.
- Automated PyPI release workflow utilizing GitHub Actions OpenID Connect (OIDC) Trusted Publishing.
