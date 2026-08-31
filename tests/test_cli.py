"""Tests for FastMCP SQLite CLI argument parsing and lazy server initialization."""

import sys
import pytest
from fastmcp_sqlite.cli import main


def test_cli_help(capsys):
    """Verify CLI --help displays available flags including --extension and --allowed-dir."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "--extension" in captured.out
    assert "--read-only" in captured.out
    assert "--allow-write" in captured.out
    assert "--opcode-limit" in captured.out
    assert "--allowed-dir" in captured.out


def test_cli_version(capsys):
    """Verify CLI --version outputs current version."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "fastmcp-sqlite" in captured.out or "1.0.0" in captured.out


def test_cli_extension_argument(monkeypatch, sample_db):
    """Verify --extension flags are correctly collected and passed to create_server."""
    captured_kwargs = {}

    def mock_create_server(**kwargs):
        captured_kwargs.update(kwargs)

        class MockServer:
            def run(self, transport="stdio"):
                pass

        return MockServer()

    # Intercept create_server when imported in main
    import fastmcp_sqlite.server as server_module

    monkeypatch.setattr(server_module, "create_server", mock_create_server)

    main(
        [
            "--db",
            sample_db,
            "--extension",
            "ext_vector.so",
            "--extension",
            "ext_crypto.dylib",
        ]
    )

    assert captured_kwargs["extensions"] == [
        "ext_vector.so",
        "ext_crypto.dylib",
    ]
    assert captured_kwargs["db_path"] == sample_db


def test_cli_allowed_dir_argument(monkeypatch, sample_db, tmp_path):
    """Verify --allowed-dir flag is correctly passed to create_server."""
    captured_kwargs = {}

    def mock_create_server(**kwargs):
        captured_kwargs.update(kwargs)

        class MockServer:
            def run(self, transport="stdio"):
                pass

        return MockServer()

    import fastmcp_sqlite.server as server_module

    monkeypatch.setattr(server_module, "create_server", mock_create_server)

    main(
        [
            "--db",
            sample_db,
            "--allowed-dir",
            str(tmp_path),
        ]
    )

    assert captured_kwargs["allowed_dir"] == str(tmp_path)
    assert captured_kwargs["db_path"] == sample_db
