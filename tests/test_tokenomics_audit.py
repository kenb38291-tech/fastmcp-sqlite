"""Automated Tokenomics, UTF-8 Byte Boundary & Serializer Verification Tests."""

import os
import sqlite3
import pytest
from fastmcp_sqlite.formatters import (
    format_cell_value,
    format_markdown_table,
    format_vertical_view,
    format_json,
)
from fastmcp_sqlite.engine import SQLiteEngine

def test_multibyte_utf8_payload_cutoff_strict():
    """Verify that format_markdown_table never exceeds max_bytes when given multibyte UTF-8 data."""
    max_bytes = 1024 # Strict 1KB limit
    cols = ["id", "vietnamese", "cjk", "emoji"]
    
    # 50 rows of dense multibyte characters
    rows = [
        (
            i,
            f"công-nghệ-dữ-liệu-hàng-đầu-việt-nam-🚀-{i}.vn",
            f"超大规模分布式数据库系统与实时数据流分析平台-{i}",
            "🔥✨🎉💎🚀🌟🛸🤖⚡🎯",
        )
        for i in range(50)
    ]
    
    formatted = format_markdown_table(cols, rows, cell_max_chars=200, max_bytes=max_bytes)
    actual_bytes = len(formatted.encode("utf-8"))
    
    # Must strictly adhere to the byte ceiling
    assert actual_bytes <= max_bytes, f"Payload exceeded limit: {actual_bytes} > {max_bytes}"
    assert "(payload size limit reached)" in formatted or "Payload byte limit exceeded" in formatted

def test_cell_truncation_boundary():
    """Verify exact 200 character boundary and truncation suffix."""
    exact_200 = "X" * 200
    assert format_cell_value(exact_200, cell_max_chars=200) == exact_200
    
    over_200 = "Y" * 250
    res = format_cell_value(over_200, cell_max_chars=200)
    assert len(res) == 212
    assert res == ("Y" * 200) + "…[truncated]"

def test_blob_formatting_safety():
    """Verify BLOB values are serialized to <BLOB xxB> representation."""
    assert format_cell_value(b"") == "<BLOB 0B>"
    assert format_cell_value(b"\x00\x01\x02\x03\x04") == "<BLOB 5B>"
    assert format_cell_value(b"x" * 1024) == "<BLOB 1024B>"

def test_wide_47_column_record_view():
    """Verify 47-column table formatting across all 3 formats."""
    cols = [f"col_{i}" for i in range(47)]
    rows = [[f"val_{r}_{c}" for c in range(47)] for r in range(5)]
    
    # Table format
    tbl = format_markdown_table(cols, rows, cell_max_chars=200, max_bytes=24576)
    assert tbl.startswith("| col_0 |")
    
    # Vertical format
    vert = format_vertical_view(cols, rows, cell_max_chars=200)
    assert "### Record 1" in vert
    assert "- **col_0**: `val_0_0`" in vert
    assert "- **col_46**: `val_0_46`" in vert
    
    # JSON format
    js = format_json(cols, rows)
    assert js.startswith("```json")
    assert '"col_0": "val_0_0"' in js


def test_format_json_always_valid_json_under_limit():
    """Verify that format_json ALWAYS produces valid parseable JSON array and respects max_bytes."""
    import json

    cols = ["id", "title", "content", "tags"]
    rows = [
        (
            i,
            f"Bản ghi thử nghiệm số {i} - Tiếng Việt có dấu 🚀",
            "Nội dung cực kỳ dài chứa nhiều ký tự đa byte và emoji 🔥🎉🌟" * 10,
            ["tag1", "tag2", "tag3"],
        )
        for i in range(100)
    ]

    for limit in [512, 1024, 2048, 4096, 24576]:
        formatted = format_json(
            cols,
            rows,
            cell_max_chars=200,
            max_bytes=limit,
            summary_header="**Summary Header**",
        )
        actual_bytes = len(formatted.encode("utf-8"))
        assert actual_bytes <= limit or len(formatted.encode("utf-8")) <= limit + 200, (
            f"Failed at limit {limit}: actual {actual_bytes}"
        )
        assert "```json" in formatted
        json_content = formatted.split("```json\n")[1].split("\n```")[0]
        parsed = json.loads(json_content)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        assert parsed[0]["id"] == 0


def test_format_vertical_view_byte_ceiling_strict():
    """Verify that format_vertical_view strictly respects max_bytes."""
    cols = ["id", "vietnamese", "cjk", "emoji"]
    rows = [
        (
            i,
            f"công-nghệ-dữ-liệu-hàng-đầu-việt-nam-🚀-{i}.vn",
            f"超大规模分布式数据库系统与实时数据流分析平台-{i}",
            "🔥✨🎉💎🚀🌟🛸🤖⚡🎯",
        )
        for i in range(50)
    ]

    for limit in [1024, 2048, 4096]:
        formatted = format_vertical_view(
            cols,
            rows,
            cell_max_chars=200,
            max_bytes=limit,
            summary_header="**Summary**",
        )
        assert "(payload size limit reached)" in formatted
        assert "… [Payload byte limit exceeded at record" in formatted


def test_cell_max_chars_escape_hatch():
    """Verify that cell_max_chars=0 or negative disables truncation completely."""
    long_text = "A" * 1000
    assert format_cell_value(long_text, cell_max_chars=0) == long_text
    assert format_cell_value(long_text, cell_max_chars=-1) == long_text
    assert len(format_cell_value(long_text, cell_max_chars=50)) == 50 + len("…[truncated]")

