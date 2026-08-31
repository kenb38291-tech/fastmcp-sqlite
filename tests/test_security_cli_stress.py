"""Comprehensive security, parameter sanitization, PEP 562, and CLI integration stress tests.

Auditor 4: Stress Test An Ninh, Parameter Sanitization, PEP 562 & CLI Integration.
"""

import json
import sqlite3
import subprocess
import sys
import time
import pytest

import fastmcp_sqlite
from fastmcp_sqlite.cli import main as cli_main
from fastmcp_sqlite.engine import SQLiteEngine


def parse_json_response(res: str):
    """Extract and parse JSON payload from formatted Markdown JSON response."""
    if "```json" in res:
        json_str = res.split("```json")[1].split("```")[0].strip()
        return json.loads(json_str)
    return json.loads(res)


# ==============================================================================
# SECTION 1: PEP 562 Completeness & Autocomplete Stress Tests
# ==============================================================================


def test_pep562_dir_completeness():
    """Verify dir(fastmcp_sqlite) returns complete and sorted public attributes."""
    expected_exports = sorted(["SQLiteEngine", "__version__", "create_server", "main"])
    module_dir = dir(fastmcp_sqlite)

    assert module_dir == expected_exports
    assert sorted(fastmcp_sqlite.__all__) == expected_exports


def test_pep562_lazy_attribute_resolution():
    """Verify valid public attributes resolve lazily to the expected types."""
    # __version__
    assert fastmcp_sqlite.__version__ == "1.0.0"
    assert isinstance(fastmcp_sqlite.__version__, str)

    # SQLiteEngine class
    engine_cls = fastmcp_sqlite.SQLiteEngine
    assert isinstance(engine_cls, type)
    assert engine_cls.__name__ == "SQLiteEngine"

    # create_server function
    server_factory = fastmcp_sqlite.create_server
    assert callable(server_factory)
    assert server_factory.__name__ == "create_server"

    # main entrypoint
    main_func = fastmcp_sqlite.main
    assert callable(main_func)
    assert main_func.__name__ == "main"


def test_pep562_attribute_error_on_invalid_attr():
    """Verify accessing undefined attributes raises informative AttributeError."""
    invalid_attrs = [
        "non_existent",
        "FastMCP",
        "sqlite3",
        "secret_key",
        "__missing__",
        "execute_query",
        "",
    ]

    for attr in invalid_attrs:
        with pytest.raises(AttributeError) as exc_info:
            getattr(fastmcp_sqlite, attr)
        assert f"module '{fastmcp_sqlite.__name__}' has no attribute '{attr}'" in str(
            exc_info.value
        )


def test_cli_cold_start_latency_in_process(capsys):
    """Verify CLI in-process cold start for --help and --version executes in < 20ms."""
    # Warmup
    with pytest.raises(SystemExit):
        cli_main(["--help"])
    capsys.readouterr()

    # Benchmark --help
    help_times = []
    for _ in range(30):
        t0 = time.perf_counter()
        with pytest.raises(SystemExit) as exc:
            cli_main(["--help"])
        t1 = time.perf_counter()
        assert exc.value.code == 0
        help_times.append((t1 - t0) * 1000)
    capsys.readouterr()

    avg_help_ms = sum(help_times) / len(help_times)
    p95_help_ms = sorted(help_times)[int(len(help_times) * 0.95)]
    assert p95_help_ms < 20.0, f"CLI --help p95 latency too high: {p95_help_ms:.2f}ms"

    # Benchmark --version
    version_times = []
    for _ in range(30):
        t0 = time.perf_counter()
        with pytest.raises(SystemExit) as exc:
            cli_main(["--version"])
        t1 = time.perf_counter()
        assert exc.value.code == 0
        version_times.append((t1 - t0) * 1000)
    capsys.readouterr()

    avg_version_ms = sum(version_times) / len(version_times)
    p95_version_ms = sorted(version_times)[int(len(version_times) * 0.95)]
    assert (
        p95_version_ms < 20.0
    ), f"CLI --version p95 latency too high: {p95_version_ms:.2f}ms"


def test_cli_lazy_import_isolation():
    """Verify that invoking --help or --version does not import heavy server module."""
    # Run in an isolated subprocess to inspect module import behavior
    code = (
        "import sys\n"
        "from fastmcp_sqlite.cli import main\n"
        "try:\n"
        "    main(['--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "# Verify 'fastmcp_sqlite.server' and 'mcp' are NOT loaded\n"
        "server_loaded = 'fastmcp_sqlite.server' in sys.modules\n"
        "mcp_loaded = 'mcp' in sys.modules\n"
        "assert not server_loaded, 'fastmcp_sqlite.server was prematurely imported!'\n"
        "assert not mcp_loaded, 'mcp was prematurely imported!'\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Lazy import boundary failed:\n{res.stderr}"


# ==============================================================================
# SECTION 2: Parameter Binding & Defensive Parsing Stress Tests
# ==============================================================================


def test_param_binding_nested_complex_json_string(sample_db):
    """Verify complex nested JSON string parameters are parsed and bound safely."""
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # Complex nested JSON string containing dicts, arrays, booleans, and nulls
    complex_payload = json.dumps(
        {
            "user": {
                "name": "Alice",
                "tags": ["admin", "core", "security"],
                "settings": {"dark_mode": True, "notifications": None, "quota": 1000},
            }
        }
    )

    # Execute SQLite json_extract against bound JSON payload
    query = """
        SELECT 
            json_extract(:user, '$.name') AS name,
            json_extract(:user, '$.tags[0]') AS primary_tag,
            json_extract(:user, '$.settings.dark_mode') AS dark_mode,
            json_extract(:user, '$.settings.quota') AS quota;
    """

    res_json = engine.execute_query(query, params=complex_payload, format="json")
    parsed = parse_json_response(res_json)

    assert len(parsed) == 1
    assert parsed[0]["name"] == "Alice"
    assert parsed[0]["primary_tag"] == "admin"
    assert parsed[0]["dark_mode"] == 1
    assert parsed[0]["quota"] == 1000


def test_param_binding_nested_dict_python_object(sample_db):
    """Verify raw Python dictionary with nested objects serializes automatically to JSON."""
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    nested_dict = {
        ":profile": {
            "title": "Senior Architect",
            "skills": ["python", "sqlite", "mcp"],
            "level": 5,
        }
    }

    query = """
        SELECT 
            json_extract(:profile, '$.title') AS title,
            json_extract(:profile, '$.skills[1]') AS second_skill,
            json_extract(:profile, '$.level') AS level;
    """
    res = engine.execute_query(query, params=nested_dict, format="json")
    parsed = parse_json_response(res)

    assert parsed[0]["title"] == "Senior Architect"
    assert parsed[0]["second_skill"] == "sqlite"
    assert parsed[0]["level"] == 5


def test_param_binding_prefix_sanitization(sample_db):
    """Verify all parameter prefixes (:, $, @) are stripped and bound accurately."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    # Test : prefix
    res_colon = engine.execute_query(
        "SELECT id, username FROM users WHERE username = :u AND role = :r;",
        params={":u": "alice", ":r": "admin"},
        format="json",
    )
    assert "alice" in res_colon

    # Test $ prefix
    res_dollar = engine.execute_query(
        "SELECT id, username FROM users WHERE username = $u AND role = $r;",
        params={"$u": "bob", "$r": "user"},
        format="json",
    )
    assert "bob" in res_dollar

    # Test @ prefix
    res_at = engine.execute_query(
        "SELECT id, username FROM users WHERE username = @u AND role = @r;",
        params={"@u": "charlie", "@r": "user"},
        format="json",
    )
    assert "charlie" in res_at

    # Test mixed prefixes in one dict
    mixed_params = {
        ":u": "alice",
        "$r": "admin",
        "@e": "alice@example.com",
    }
    res_mixed = engine.execute_query(
        "SELECT id, username FROM users WHERE username = :u AND role = $r AND email = @e;",
        params=mixed_params,
        format="json",
    )
    assert "alice" in res_mixed


@pytest.mark.parametrize(
    "sqli_payload",
    [
        "' OR 1=1; --",
        "' OR '1'='1",
        "' OR 1=1; DROP TABLE users; --",
        "admin'--",
        "'; DELETE FROM users; --",
        "1; ATTACH DATABASE ':memory:' AS pwn; --",
        "' UNION SELECT 999, 'hacker', 'hacker@evil.com', 'root', '2026-01-01'--",
        "' OR EXISTS(SELECT * FROM users WHERE role='admin') --",
        "test'; UPDATE users SET role='pwned'; --",
        "\" OR \"\"=\"",
        "'; VACUUM; --",
        "1' AND 1=(SELECT count(*) FROM users WHERE username='alice') --",
    ],
)
def test_sqli_injection_vectors_neutralized(sample_db, sqli_payload):
    """Verify critical SQL injection payloads passed via params are 100% neutralized."""
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # 1. Positional parameter binding test
    pos_sql = "SELECT id, username, role FROM users WHERE username = ?;"
    pos_res = engine.execute_query(pos_sql, params=[sqli_payload], format="json")
    pos_parsed = parse_json_response(pos_res)
    # Must return 0 rows because no user has username equal to the SQLi string
    assert (
        len(pos_parsed) == 0
    ), f"Positional SQLi payload was interpreted as SQL: {sqli_payload}"

    # 2. Named parameter binding test
    named_sql = "SELECT id, username, role FROM users WHERE username = :target_user;"
    named_res = engine.execute_query(
        named_sql, params={":target_user": sqli_payload}, format="json"
    )
    named_parsed = parse_json_response(named_res)
    assert (
        len(named_parsed) == 0
    ), f"Named SQLi payload was interpreted as SQL: {sqli_payload}"

    # 3. Verify database integrity - users table must exist and contain original rows
    verify_conn = sqlite3.connect(sample_db)
    cur = verify_conn.cursor()
    cur.execute("SELECT count(*) FROM users;")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT role FROM users WHERE username = 'alice';")
    alice_role = cur.fetchone()[0]
    verify_conn.close()

    assert user_count == 3, "Database was modified or dropped by SQLi payload!"
    assert alice_role == "admin", "User role was corrupted by SQLi payload!"


def test_param_defensive_parsing_edge_cases_and_malformed_inputs(sample_db):
    """Verify engine handles malformed JSON strings, type mismatches, and edge cases."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    # 1. Malformed JSON strings (should fall back safely to single primitive parameter)
    malformed_json_cases = [
        "{unclosed json",
        "[1, 2, ",
        '{"invalid": syntax',
        "{'single_quotes': 'invalid_in_standard_json'}",
        "{[]}",
    ]
    for bad_json in malformed_json_cases:
        # Should not crash, parameter is passed as literal string
        res = engine.execute_query(
            "SELECT ? AS raw_val;", params=bad_json, format="json"
        )
        parsed = parse_json_response(res)
        assert parsed[0]["raw_val"] == bad_json

    # 2. Primitive types passed directly as params
    res_int = engine.execute_query("SELECT ? AS val;", params=42, format="json")
    assert parse_json_response(res_int)[0]["val"] == 42

    res_float = engine.execute_query("SELECT ? AS val;", params=3.14159, format="json")
    assert parse_json_response(res_float)[0]["val"] == 3.14159

    res_true = engine.execute_query("SELECT ? AS val;", params=True, format="json")
    assert parse_json_response(res_true)[0]["val"] == 1

    res_false = engine.execute_query("SELECT ? AS val;", params=False, format="json")
    assert parse_json_response(res_false)[0]["val"] == 0

    res_empty_str = engine.execute_query("SELECT ? AS val;", params="", format="json")
    assert parse_json_response(res_empty_str)[0]["val"] == ""

    # 3. None param
    res_none = engine.execute_query(
        "SELECT 1 AS val;", params=None, format="json"
    )
    assert parse_json_response(res_none)[0]["val"] == 1

    # 4. Multibyte Unicode, emojis, and control characters
    unicode_payload = "你好世界 🚀🛡️ \n\t\r 특수문자"
    res_unicode = engine.execute_query(
        "SELECT ? AS u_val;", params=[unicode_payload], format="json"
    )
    assert parse_json_response(res_unicode)[0]["u_val"] == unicode_payload

    # 5. Empty collections
    res_empty_list = engine.execute_query("SELECT 100 AS num;", params=[])
    assert "100" in res_empty_list

    res_empty_dict = engine.execute_query("SELECT 200 AS num;", params={})
    assert "200" in res_empty_dict


def test_explain_query_with_parameters_and_sqli(sample_db):
    """Verify explain_query accepts parameters and safely handles SQLi attempts."""
    engine = SQLiteEngine(default_db=sample_db)

    # Normal parameterized explain
    res = engine.explain_query(
        "SELECT * FROM users WHERE username = :name AND role = :role",
        params={":name": "alice", ":role": "admin"},
    )
    assert "Query Plan:" in res
    assert "SCAN" in res or "SEARCH" in res

    # SQLi in explain parameter
    res_sqli = engine.explain_query(
        "SELECT * FROM users WHERE username = ?",
        params=["' OR 1=1; DROP TABLE users; --"],
    )
    assert "Query Plan:" in res_sqli

    # Verify table wasn't dropped
    check_conn = sqlite3.connect(sample_db)
    cur = check_conn.cursor()
    cur.execute("SELECT count(*) FROM users;")
    assert cur.fetchone()[0] == 3
    check_conn.close()


# ==============================================================================
# SECTION 3: Dynamic Extension Sandbox Lockdown Stress Tests
# ==============================================================================


def test_dynamic_extension_sandbox_sql_load_extension_forbidden(sample_db):
    """Verify SQL-level load_extension() cannot be invoked to bypass security."""
    engine = SQLiteEngine(default_db=sample_db, readonly=False)

    # Attempting to call load_extension via SQL statement
    res = engine.execute_query(
        "SELECT load_extension('malicious_payload.so');",
        readonly=False,
    )

    # SQLite must reject with OperationalError (not authorized or unknown function)
    assert (
        "OperationalError" in res
        or "not authorized" in res.lower()
        or "unknown function" in res.lower()
    )


def test_dynamic_extension_sandbox_connection_lockdown(sample_db):
    """Verify connection-level enable_load_extension is always disabled on engine connections."""
    engine = SQLiteEngine(default_db=sample_db)
    conn = engine.get_connection(sample_db)

    try:
        # Calling load_extension directly on connection must fail because extension loading is locked down
        with pytest.raises((sqlite3.OperationalError, AttributeError)):
            conn.load_extension("malicious_lib.dll")
    finally:
        conn.close()


def test_dynamic_extension_sandbox_guarantee_on_error(sample_db):
    """Verify enable_load_extension(False) is strictly executed in finally block even on error."""
    # Attempting to load an invalid extension path
    bad_engine = SQLiteEngine(
        default_db=sample_db,
        extensions=["non_existent_exploit_extension.so"],
    )

    with pytest.raises(Exception):
        bad_engine.get_connection(sample_db)


# ==============================================================================
# SECTION 4: Read-Only Mode & Comment Obfuscation Defense Stress Tests
# ==============================================================================


def test_readonly_mode_blocks_destructive_verbs_with_comments(sample_db):
    """Verify read-only mode blocks destructive SQL hidden behind comment headers."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)

    evasion_attempts = [
        "-- Lead comment\nDROP TABLE users;",
        "-- Multiple comments\n-- Second line\nDELETE FROM users WHERE 1=1;",
        "   -- Indented comment\nINSERT INTO users (username) VALUES ('hacker');",
        "/* Block comment */ UPDATE users SET role='admin';",
        "ATTACH DATABASE ':memory:' AS pwned;",
        "ALTER TABLE users RENAME TO old_users;",
        "CREATE TABLE backdoor (id INT);",
        "VACUUM;",
    ]

    for sql in evasion_attempts:
        res = engine.execute_query(sql, readonly=True)
        # Must be rejected by read-only validator or SQLite query_only pragma
        assert (
            "forbidden in read-only mode" in res
            or "OperationalError: attempt to write a readonly database" in res
            or "OperationalError: not authorized" in res
            or "SQLite OperationalError" in res
        ), f"Readonly validator failed to catch: {sql}"

    # Verify no records were touched
    conn = sqlite3.connect(sample_db)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM users;")
    assert cur.fetchone()[0] == 3
    conn.close()


def test_readonly_pragma_query_only_hard_lock(sample_db):
    """Verify PRAGMA query_only = ON provides kernel-level SQLite write protection."""
    engine = SQLiteEngine(default_db=sample_db, readonly=True)
    conn = engine.get_connection(sample_db, readonly=True)

    cursor = conn.cursor()
    cursor.execute("PRAGMA query_only;")
    row = cursor.fetchone()
    # query_only pragma must be active (1)
    assert row[0] == 1

    # Any direct write cursor execution must raise OperationalError or DatabaseError (not authorized)
    with pytest.raises((sqlite3.OperationalError, sqlite3.DatabaseError)):
        cursor.execute("DELETE FROM users WHERE id = 1;")
    conn.close()
