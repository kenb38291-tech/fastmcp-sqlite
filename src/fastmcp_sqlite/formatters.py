"""Token-efficient serialization formatters for SQLite query results.

Provides Markdown Table, Vertical Record View, and JSON formatters with
automatic cell text truncation and payload byte ceiling safeguards.
"""

from typing import Any, Dict, List, Sequence
import json


def format_cell_value(
    cell: Any, cell_max_chars: int = 200, escape_pipe: bool = False
) -> str:
    """Format an individual cell value with BLOB handling and character truncation.

    Args:
        cell: The cell value from SQLite row.
        cell_max_chars: Maximum characters allowed per cell before truncation.
            If <= 0, no character truncation is applied.
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

    if cell_max_chars > 0 and len(val_str) > cell_max_chars:
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
        cell_max_chars: Maximum characters per cell (0 or negative for unlimited).
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
    # Calculate base bytes for headers and worst-case suffix overhead
    header_suffix_overhead = len(" (payload size limit reached)\n\n".encode("utf-8"))
    summary_overhead = (
        len((summary_header + "\n\n").encode("utf-8")) if summary_header else 0
    )
    total_bytes = (
        sum(len(h.encode("utf-8")) + 1 for h in [header_line, sep_line])
        + header_suffix_overhead
        + summary_overhead
    )

    payload_truncated = False

    for row_idx, row in enumerate(display_rows):
        cell_strs = [
            format_cell_value(
                cell, cell_max_chars=cell_max_chars, escape_pipe=True
            )
            for cell in row
        ]
        row_line = "| " + " | ".join(cell_strs) + " |"
        row_bytes = len(row_line.encode("utf-8")) + 1
        trunc_bytes = len(
            f"| … [Payload byte limit exceeded at row {row_idx + 1}] |\n".encode(
                "utf-8"
            )
        )

        if total_bytes + row_bytes + trunc_bytes > max_bytes:
            payload_truncated = True
            formatted_lines.append(
                f"| … [Payload byte limit exceeded at row {row_idx + 1}] |"
            )
            break
        formatted_lines.append(row_line)
        total_bytes += row_bytes

    header_suffix = " (payload size limit reached)" if payload_truncated else ""
    header_text = (
        (summary_header + header_suffix).strip()
        if (summary_header or header_suffix)
        else ""
    )

    if header_text:
        return f"{header_text}\n\n" + "\n".join(formatted_lines)
    return "\n".join(formatted_lines)


def format_vertical_view(
    col_names: Sequence[str],
    display_rows: Sequence[Sequence[Any]],
    cell_max_chars: int = 200,
    max_bytes: int = 24576,
    summary_header: str = "",
) -> str:
    """Format query rows into vertical record views for wide tables (>20 columns).

    Each record is rendered as an isolated bulleted block to eliminate line-wrapping
    confusion and improve LLM inference accuracy.

    Args:
        col_names: List of column names.
        display_rows: List of row tuples or sqlite3.Row objects.
        cell_max_chars: Maximum characters per cell (0 or negative for unlimited).
        max_bytes: Hard ceiling on response payload in bytes.
        summary_header: Optional performance summary header text.

    Returns:
        Formatted Vertical Record View string.
    """
    if not display_rows:
        return (summary_header + "\n\n(No records found.)").strip()

    formatted_records: List[str] = []
    payload_truncated = False

    header_suffix_overhead = len(" (payload size limit reached)\n\n".encode("utf-8"))
    summary_overhead = (
        len((summary_header + "\n\n").encode("utf-8")) if summary_header else 0
    )
    total_bytes = summary_overhead + header_suffix_overhead

    for row_idx, row in enumerate(display_rows, 1):
        record_lines = [f"### Record {row_idx}"]
        for col_name, cell in zip(col_names, row):
            val_str = format_cell_value(
                cell, cell_max_chars=cell_max_chars, escape_pipe=False
            )
            record_lines.append(f"- **{col_name}**: `{val_str}`")
        record_str = "\n".join(record_lines)
        record_bytes = len(record_str.encode("utf-8")) + (
            2 if formatted_records else 0
        )
        trunc_notice = f"… [Payload byte limit exceeded at record {row_idx}]"
        trunc_notice_bytes = len(f"\n\n{trunc_notice}".encode("utf-8"))

        if formatted_records and (
            total_bytes + record_bytes + trunc_notice_bytes > max_bytes
        ):
            payload_truncated = True
            formatted_records.append(trunc_notice)
            break

        formatted_records.append(record_str)
        total_bytes += record_bytes

    header_suffix = " (payload size limit reached)" if payload_truncated else ""
    header_text = (
        (summary_header + header_suffix).strip()
        if (summary_header or header_suffix)
        else ""
    )

    if header_text:
        return f"{header_text}\n\n" + "\n\n".join(formatted_records)
    return "\n\n".join(formatted_records)


def format_json(
    col_names: Sequence[str],
    display_rows: Sequence[Sequence[Any]],
    cell_max_chars: int = 200,
    max_bytes: int = 24576,
    summary_header: str = "",
) -> str:
    """Format query rows into a structured JSON payload with record-level accumulation.

    Guarantees 100% valid JSON syntax inside the markdown code block even when payload
    byte limits are reached.

    Args:
        col_names: List of column names.
        display_rows: List of row tuples or sqlite3.Row objects.
        cell_max_chars: Maximum characters per string cell (0 or negative for unlimited).
        max_bytes: Hard ceiling on response payload in bytes.
        summary_header: Optional performance summary header text.

    Returns:
        Formatted JSON code block string containing a valid JSON array.
    """
    if not display_rows:
        empty_json = json.dumps([], indent=2, ensure_ascii=False, default=str)
        summary = (summary_header + "\n\n") if summary_header else ""
        return f"{summary}```json\n{empty_json}\n```"

    accumulated_data: List[Dict[str, Any]] = []
    payload_truncated = False

    for row in display_rows:
        row_dict: Dict[str, Any] = {}
        for col_name, cell in zip(col_names, row):
            if cell is None:
                row_dict[col_name] = None
            elif isinstance(cell, bytes):
                row_dict[col_name] = f"<BLOB {len(cell)}B>"
            elif isinstance(cell, str):
                if cell_max_chars > 0 and len(cell) > cell_max_chars:
                    row_dict[col_name] = cell[:cell_max_chars] + "…[truncated]"
                else:
                    row_dict[col_name] = cell
            else:
                row_dict[col_name] = cell

        candidate_data = accumulated_data + [row_dict]
        candidate_json = json.dumps(
            candidate_data, indent=2, ensure_ascii=False, default=str
        )

        test_header_suffix = " (payload size limit reached)"
        test_header = (
            (summary_header + test_header_suffix).strip()
            if (summary_header or test_header_suffix)
            else ""
        )
        test_output = (
            f"{test_header}\n\n```json\n{candidate_json}\n```"
            if test_header
            else f"```json\n{candidate_json}\n```"
        )

        if accumulated_data and len(test_output.encode("utf-8")) > max_bytes:
            payload_truncated = True
            break

        accumulated_data = candidate_data

    final_json = json.dumps(
        accumulated_data, indent=2, ensure_ascii=False, default=str
    )
    header_suffix = " (payload size limit reached)" if payload_truncated else ""
    header_text = (
        (summary_header + header_suffix).strip()
        if (summary_header or header_suffix)
        else ""
    )

    if header_text:
        return f"{header_text}\n\n```json\n{final_json}\n```"
    return f"```json\n{final_json}\n```"
