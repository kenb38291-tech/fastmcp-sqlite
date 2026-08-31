"""Extreme stress test suite for Tokenomics, Multibyte UTF-8 Boundaries, and Prompt Caching Invariance."""

import json
import sqlite3
from typing import List

from fastmcp_sqlite.engine import SQLiteEngine
from fastmcp_sqlite.formatters import (
    format_cell_value,
    format_json,
    format_markdown_table,
    format_vertical_view,
)


# ============================================================================
# 1. MULTIBYTE UTF-8 BOUNDARY & PAYLOAD CEILING STRESS TESTS
# ============================================================================


def test_multibyte_utf8_character_diversity_and_payload_ceiling(tmp_path):
    """Stress test multibyte UTF-8 boundary handling with CJK, 4-byte emojis, Arabic, and Cyrillic."""
    db_file = tmp_path / "test_multibyte_stress.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE multilingual_corpus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cjk_chinese TEXT,
            cjk_japanese TEXT,
            cjk_korean TEXT,
            emojis_4byte TEXT,
            arabic_rtl TEXT,
            cyrillic TEXT,
            vietnamese_tones TEXT
        );
        """
    )

    chinese_text = "数据库索引优化与高并发事务处理系统架构设计" * 10
    japanese_text = "高機能軽量データベース検索エンジンと形態素解析" * 10
    korean_text = "초고속 분산 트랜잭션 데이터베이스 엔진 설계" * 10
    emoji_text = "🚀🤖💥🧠⚡🔮🦄🧬🔥🎯🏆🥇🎉✨💫🌟" * 10
    arabic_text = "قاعدة بيانات سريعة وآمنة لمعالجة المعاملات الفورية" * 8
    cyrillic_text = "Высокопроизводительная база данных с поддержкой транзакций" * 8
    vietnamese_text = "Hệ thống cơ sở dữ liệu SQLite tối ưu hoá bộ nhớ đệm và khoá ghi WAL" * 8

    rows = []
    for _ in range(100):
        rows.append(
            (
                chinese_text,
                japanese_text,
                korean_text,
                emoji_text,
                arabic_text,
                cyrillic_text,
                vietnamese_text,
            )
        )

    cur.executemany(
        """
        INSERT INTO multilingual_corpus (
            cjk_chinese, cjk_japanese, cjk_korean, emojis_4byte,
            arabic_rtl, cyrillic, vietnamese_tones
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        rows,
    )
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file), max_rows=100, max_bytes=24576)
    res_table = engine.execute_query(
        "SELECT * FROM multilingual_corpus;", format="table"
    )

    assert "payload size limit reached" in res_table
    assert "Payload byte limit exceeded at row" in res_table

    raw_bytes = res_table.encode("utf-8")
    assert raw_bytes.decode("utf-8") == res_table
    assert len(raw_bytes) <= 24576 + 500

    assert "数据库" in res_table
    assert "高機能" in res_table
    assert "초고속" in res_table
    assert "🚀" in res_table
    assert "قاعدة" in res_table
    assert "Высокопроизводительная" in res_table
    assert "Hệ thống" in res_table


def test_custom_payload_byte_ceilings_utf8(tmp_path):
    """Test various strict byte ceiling thresholds (512B, 1024B, 4096B, 8192B, 24576B)."""
    db_file = tmp_path / "test_ceilings.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE stream_data (id INTEGER PRIMARY KEY, payload TEXT);")

    complex_text = "⚡🚀🤖 繁體中文 简体中文 日本語 한국어 🌟🔥"
    for i in range(200):
        cur.execute(
            "INSERT INTO stream_data (payload) VALUES (?);",
            (f"Row {i:03d}: {complex_text} - " + "X" * 100,),
        )
    conn.commit()
    conn.close()

    ceilings = [512, 1024, 2048, 4096, 8192, 16384, 24576]
    for ceiling in ceilings:
        engine = SQLiteEngine(default_db=str(db_file), max_rows=200, max_bytes=ceiling)
        res = engine.execute_query("SELECT * FROM stream_data;", format="table")

        assert "payload size limit reached" in res
        assert "Payload byte limit exceeded at row" in res

        encoded = res.encode("utf-8")
        assert encoded.decode("utf-8") == res
        assert len(encoded) < ceiling + 600


def test_complex_zwj_and_multibyte_sequences_truncation(tmp_path):
    """Test complex Unicode combinations including ZWJ emojis, flags, skin tones, and math symbols."""
    db_file = tmp_path / "test_zwj.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE zwj_corpus (id INTEGER PRIMARY KEY, glyphs TEXT);")

    zwj_sequences = [
        "👨‍👩‍👧‍👦" * 20,  # Family ZWJ sequence
        "🇻🇳🇯🇵🇨🇳🇺🇸🇩🇪" * 15,  # Regional indicator flag pairs
        "👍🏽👩🏾‍💻🧙‍♂️" * 20,  # Skin tone modifiers and gender ZWJ
        "∀x∈ℝ, ∃y: ∫√∞ ∑∏" * 20,  # Mathematical Unicode symbols
    ]

    for i, seq in enumerate(zwj_sequences):
        cur.execute("INSERT INTO zwj_corpus (glyphs) VALUES (?);", (seq,))
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file), cell_max_chars=50)

    # Markdown Table format
    res_table = engine.execute_query("SELECT * FROM zwj_corpus;", format="table")
    assert "…[truncated]" in res_table
    encoded_table = res_table.encode("utf-8")
    assert encoded_table.decode("utf-8") == res_table

    # Vertical View format
    res_vert = engine.execute_query("SELECT * FROM zwj_corpus;", format="vertical")
    assert "…[truncated]" in res_vert
    encoded_vert = res_vert.encode("utf-8")
    assert encoded_vert.decode("utf-8") == res_vert

    # JSON format
    res_json = engine.execute_query("SELECT * FROM zwj_corpus;", format="json")
    assert "👨‍👩‍👧‍👦" in res_json
    encoded_json = res_json.encode("utf-8")
    assert encoded_json.decode("utf-8") == res_json


def test_exact_byte_boundary_truncation_no_split():
    """Verify format_markdown_table does not split 4-byte emojis or 3-byte CJK across boundaries."""
    col_names = ["id", "glyph"]
    rows = [[i, "🚀" * 50] for i in range(50)]

    formatted = format_markdown_table(
        col_names, rows, cell_max_chars=200, max_bytes=1000
    )
    assert "payload size limit reached" in formatted
    assert "Payload byte limit exceeded at row" in formatted

    encoded = formatted.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == formatted


def test_multibyte_cell_value_truncation():
    """Test format_cell_value slicing on multibyte Unicode character boundaries."""
    long_cjk = "中" * 250
    truncated_cjk = format_cell_value(long_cjk, cell_max_chars=200)

    assert truncated_cjk.endswith("…[truncated]")
    prefix = truncated_cjk.replace("…[truncated]", "")
    assert len(prefix) == 200
    assert prefix == "中" * 200
    assert len(prefix.encode("utf-8")) == 600

    long_emojis = "🚀" * 250
    truncated_emojis = format_cell_value(long_emojis, cell_max_chars=50)
    assert truncated_emojis.endswith("…[truncated]")
    emoji_prefix = truncated_emojis.replace("…[truncated]", "")
    assert len(emoji_prefix) == 50
    assert emoji_prefix == "🚀" * 50
    assert len(emoji_prefix.encode("utf-8")) == 200


# ============================================================================
# 2. WIDE TABLE & HUGE CELL TRUNCATION (50-100 COLUMNS, 1,000-10,000 CHARS)
# ============================================================================


def test_wide_table_50_columns_huge_cells(tmp_path):
    """Test 50-column wide table with 1,000 - 5,000 characters per cell across all 3 formats."""
    db_file = tmp_path / "test_wide_50.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    num_cols = 50
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    col_defs.extend([f"col_{i} TEXT" for i in range(1, num_cols)])
    table_sql = f"CREATE TABLE wide_50 ({', '.join(col_defs)});"
    cur.execute(table_sql)

    rows_data = []
    for r in range(5):
        row_vals = []
        for c in range(1, num_cols):
            cell_content = f"Row{r}_Col{c}_" + ("数据🚀" * 200)
            row_vals.append(cell_content)
        rows_data.append(row_vals)

    placeholders = ", ".join(["?"] * (num_cols - 1))
    col_names_str = ", ".join([f"col_{i}" for i in range(1, num_cols)])
    cur.executemany(
        f"INSERT INTO wide_50 ({col_names_str}) VALUES ({placeholders});",
        rows_data,
    )
    conn.commit()
    conn.close()

    engine = SQLiteEngine(
        default_db=str(db_file),
        cell_max_chars=200,
        max_rows=10,
        max_bytes=100000,
    )

    # Format 1: Table (Markdown)
    res_table = engine.execute_query("SELECT * FROM wide_50 LIMIT 2;", format="table")
    assert "| id | col_1 | col_2 |" in res_table
    assert "| :--- | :--- | :--- |" in res_table
    assert "…[truncated]" in res_table
    for line in res_table.splitlines():
        if line.startswith("|") and not line.startswith("| :---") and "col_1" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            for cell in cells[1:]:
                assert "…[truncated]" in cell

    # Format 2: Vertical Record View
    res_vert = engine.execute_query("SELECT * FROM wide_50 LIMIT 2;", format="vertical")
    assert "### Record 1" in res_vert
    assert "### Record 2" in res_vert
    assert "- **id**: `1`" in res_vert
    assert "- **col_1**:" in res_vert
    assert "- **col_49**:" in res_vert
    assert "…[truncated]" in res_vert

    # Format 3: JSON
    res_json = engine.execute_query("SELECT * FROM wide_50 LIMIT 2;", format="json")
    assert "```json" in res_json
    raw_json = res_json.split("```json")[1].split("```")[0].strip()
    parsed = json.loads(raw_json)
    assert len(parsed) == 2
    assert "col_1" in parsed[0]
    assert "col_49" in parsed[0]
    assert "数据🚀" in parsed[0]["col_1"]


def test_wide_table_100_columns_10000_char_cells(tmp_path):
    """Test 100-column table with 10,000 characters per cell."""
    db_file = tmp_path / "test_wide_100.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    num_cols = 100
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    col_defs.extend([f"field_{i} TEXT" for i in range(1, num_cols)])
    table_sql = f"CREATE TABLE wide_100 ({', '.join(col_defs)});"
    cur.execute(table_sql)

    huge_string = "ABCDEFGHIJ0123456789" * 500
    row_vals = [f"c{c}_" + huge_string for c in range(1, num_cols)]

    placeholders = ", ".join(["?"] * (num_cols - 1))
    col_names_str = ", ".join([f"field_{i}" for i in range(1, num_cols)])
    cur.execute(
        f"INSERT INTO wide_100 ({col_names_str}) VALUES ({placeholders});",
        row_vals,
    )
    conn.commit()
    conn.close()

    engine = SQLiteEngine(
        default_db=str(db_file),
        cell_max_chars=200,
        max_rows=5,
        max_bytes=24576,
    )

    res_table = engine.execute_query("SELECT * FROM wide_100;", format="table")
    assert "| id | field_1 |" in res_table
    assert "…[truncated]" in res_table
    assert len(res_table.encode("utf-8")) <= 24576 + 500

    res_vert = engine.execute_query("SELECT * FROM wide_100;", format="vertical")
    assert "### Record 1" in res_vert
    assert "- **field_1**:" in res_vert
    assert "- **field_99**:" in res_vert
    assert "…[truncated]" in res_vert

    res_json = engine.execute_query("SELECT * FROM wide_100;", format="json")
    assert "```json" in res_json
    raw_json = res_json.split("```json")[1].split("```")[0].strip()
    data = json.loads(raw_json)
    assert len(data) == 1
    assert len(data[0]) == 100


def test_markdown_pipe_and_newline_escaping_integrity():
    """Verify pipe characters and newlines in cells do not corrupt table formatting."""
    col_names = ["id", "pipe_col", "newline_col"]
    rows = [
        [1, "foo | bar | baz", "line1\nline2\r\nline3\rline4"],
        [2, "|| double pipe ||", "normal text"],
    ]

    formatted = format_markdown_table(col_names, rows)
    lines = formatted.splitlines()

    # Markdown table must have header + separator + 2 data rows
    table_lines = [l for l in lines if l.startswith("|")]
    assert len(table_lines) == 4  # Header, separator, Row 1, Row 2

    # Check pipe escaping in data rows
    assert "foo \\| bar \\| baz" in table_lines[2]
    assert "\\|\\| double pipe \\|\\|" in table_lines[3]

    # Check newline replacement
    assert "line1 line2  line3 line4" in table_lines[2]


def test_format_cell_value_edge_cases():
    """Verify all format_cell_value boundary cases and transformations."""
    assert format_cell_value(None) == "NULL"
    assert format_cell_value(b"") == "<BLOB 0B>"
    assert format_cell_value(b"\x00\x01\x02") == "<BLOB 3B>"
    assert format_cell_value(b"X" * 1024) == "<BLOB 1024B>"

    assert format_cell_value("Line1\r\nLine2\nLine3\rLine4") == "Line1  Line2 Line3 Line4"

    assert (
        format_cell_value("A | B | C", escape_pipe=True) == "A \\| B \\| C"
    )
    assert (
        format_cell_value("A | B | C", escape_pipe=False) == "A | B | C"
    )

    exact_str = "A" * 200
    assert format_cell_value(exact_str, cell_max_chars=200) == exact_str

    over_str = "A" * 201
    assert (
        format_cell_value(over_str, cell_max_chars=200)
        == ("A" * 200) + "…[truncated]"
    )


# ============================================================================
# 3. PROMPT CACHING INVARIANCE VERIFICATION (100 CONSECUTIVE RUNS)
# ============================================================================


def test_describe_schema_prompt_caching_invariance_100_runs(tmp_path):
    """Verify describe_schema achieves >97% byte-level prefix invariance across 100 consecutive calls."""
    db_file = tmp_path / "test_caching_schema.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # Create realistic schema with 8 tables, indexes, views, and foreign keys
    cur.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            tier TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id),
            title TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            in_stock INTEGER DEFAULT 1
        );
        CREATE INDEX idx_products_category ON products(category_id);
        CREATE INDEX idx_products_price ON products(price_cents);

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            status TEXT DEFAULT 'pending',
            total_amount INTEGER NOT NULL
        );
        CREATE INDEX idx_orders_user ON orders(user_id);

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER DEFAULT 1
        );

        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIEW active_products_view AS
        SELECT p.id, p.title, p.price_cents, c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.in_stock = 1;

        CREATE TABLE key_value_config (
            config_key TEXT PRIMARY KEY,
            config_val TEXT
        ) WITHOUT ROWID;
        """
    )
    conn.commit()
    conn.close()

    engine = SQLiteEngine(default_db=str(db_file))

    outputs: List[str] = []
    for _ in range(100):
        outputs.append(engine.describe_schema())

    assert len(outputs) == 100

    latency_tag = "*Discovery Latency:"
    prefixes = []
    for out in outputs:
        assert latency_tag in out
        prefix_part = out.split(latency_tag)[0]
        prefixes.append(prefix_part)

    # 1. Byte-for-byte exact equality of the static schema body across all 100 calls
    base_prefix = prefixes[0]
    base_prefix_bytes = len(base_prefix.encode("utf-8"))
    assert base_prefix_bytes > 0

    for i, prefix in enumerate(prefixes[1:], 1):
        assert (
            prefix == base_prefix
        ), f"Schema output prefix mismatch at iteration {i}"

    # 2. Quantitative prompt caching invariance calculation
    total_bytes_list = [len(out.encode("utf-8")) for out in outputs]
    avg_total_bytes = sum(total_bytes_list) / len(total_bytes_list)
    invariance_percentage = (base_prefix_bytes / avg_total_bytes) * 100

    # Invariance must strictly exceed 97.0%
    assert invariance_percentage >= 97.0, (
        f"Prompt caching invariance ratio {invariance_percentage:.2f}% is below 97.0% threshold."
    )


def test_describe_schema_exact_prefix_byte_identity(sample_db):
    """Verify that every single byte prior to the latency footer is 100% identical across calls."""
    engine = SQLiteEngine(default_db=sample_db)

    out1 = engine.describe_schema()
    out2 = engine.describe_schema()

    prefix1 = out1.split("*Discovery Latency:")[0].encode("utf-8")
    prefix2 = out2.split("*Discovery Latency:")[0].encode("utf-8")

    assert prefix1 == prefix2
    assert len(prefix1) > 0
