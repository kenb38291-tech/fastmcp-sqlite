"""Token-efficient serialization formatters for SQLite query results.

Provides Markdown Table, Vertical Record View, and JSON formatters with
automatic cell text truncation and payload byte ceiling safeguards.
"""

from typing import Any, List, Sequence
import json


def format_cell_value(
    cell: Any, cell_max_chars: int = 200, escape_pipe: bool = False
) -> str:
    """Format an individual cell value with BLOB handling and character truncation.

    Args:
        cell: The cell value from SQLite row.
        cell_max_chars: Maximum characters allowed per cell before truncation.
        escape_pipe: Whether to escape markdown table pipes (`|` -> `\\|`).

    Returns:
        Formatted string representation of the cell.
    """
    if cell is None:
        return "NULL"
    if isinstance(cell, bytes):
        return f"<BLOB {len(cell)}B>"

    val_str = str(cell).replace("\r", " ").replace("\n", " ")
    if escape_pipe:
        val_str = val_str.replace("|", "\\|")

    if len(val_str) > cell_max_chars:
        return val_str[:cell_max_chars] + "…[truncated]"
    return val_str


def format_markdown_table(
    col_names: Sequence[str],
    display_rows: Sequence[Sequence[Any]],
    cell_max_chars: int = 200,
    max_bytes: int = 24576,
    summary_header: str = "",
) -> str:
    """Format query rows into a compact GitHub-flavored Markdown table.

    Safeguards agent context by enforcing a maximum byte payload ceiling.

    Args:
        col_names: List of column names.
        display_rows: List of row tuples or sqlite3.Row objects.
        cell_max_chars: Maximum characters per cell.
        max_bytes: Hard ceiling on response payload in bytes.
        summary_header: Optional performance summary header text.

    Returns:
        Formatted Markdown table string.
    """
    if not col_names:
        return summary_header if summary_header else "No columns returned."

    header_line = "| " + " | ".join(col_names) + " |"
    sep_line = "| " + " | ".join([":---"] * len(col_names)) + " |"

    formatted_lines = [header_line, sep_line]
    total_bytes = sum(len(h.encode("utf-8")) for h in [header_line, sep_line])
    payload_truncated = False

    for row_idx, row in enumerate(display_rows):
        cell_strs = [
            format_cell_value(cell, cell_max_chars=cell_max_chars, escape_pipe=True)
            for cell in row
        ]
        row_line = "| " + " | ".join(cell_strs) + " |"
        total_bytes += len(row_line.encode("utf-8")) + 1

        if total_bytes > max_bytes:
            payload_truncated = True
            formatted_lines.append(
                f"| … [Payload byte limit exceeded at row {row_idx + 1}] |"
            )
            break
        formatted_lines.append(row_line)

    header_suffix = " (payload size limit reached)" if payload_truncated else ""
    summary = [
        (summary_header + header_suffix).strip(),
        "",
    ]
    summary.extend(formatted_lines)
    return "\n".join(summary)


def format_vertical_view(
    col_names: Sequence[str],
    display_rows: Sequence[Sequence[Any]],
    cell_max_chars: int = 200,
    summary_header: str = "",
) -> str:
    """Format query rows into vertical record views for wide tables (>20 columns).

    Each record is rendered as an isolated bulleted block to eliminate line-wrapping
    confusion and improve LLM inference accuracy.

    Args:
        col_names: List of column names.
        display_rows: List of row tuples or sqlite3.Row objects.
        cell_max_chars: Maximum characters per cell.
        summary_header: Optional performance summary header text.

    Returns:
        Formatted Vertical Record View string.
    """
    if not display_rows:
        return (summary_header + "\n\n(No records found.)").strip()

    formatted_records = []
    for row_idx, row in enumerate(display_rows, 1):
        record_lines = [f"### Record {row_idx}"]
        for col_name, cell in zip(col_names, row):
            val_str = format_cell_value(
                cell, cell_max_chars=cell_max_chars, escape_pipe=False
            )
            record_lines.append(f"- **{col_name}**: `{val_str}`")
        formatted_records.append("\n".join(record_lines))

    summary = summary_header + "\n\n" if summary_header else ""
    return summary + "\n\n".join(formatted_records)


def format_json(
    col_names: Sequence[str],
    display_rows: Sequence[Sequence[Any]],
    summary_header: str = "",
) -> str:
    """Format query rows into a structured JSON payload.

    Args:
        col_names: List of column names.
        display_rows: List of row tuples or sqlite3.Row objects.
        summary_header: Optional performance summary header text.

    Returns:
        Formatted JSON code block string.
    """
    data = []
    for row in display_rows:
        row_dict = {}
        for col_name, cell in zip(col_names, row):
            if isinstance(cell, bytes):
                row_dict[col_name] = f"<BLOB {len(cell)}B>"
            else:
                row_dict[col_name] = cell
        data.append(row_dict)

    json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    summary = summary_header + "\n\n" if summary_header else ""
    return f"{summary}```json\n{json_str}\n```"
