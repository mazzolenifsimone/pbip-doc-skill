"""
Parser and Markdown Renderer for Power Query (M) Inline Tables (#table).
Extracts column schemas, data types, and row data from #table(...) definitions
and formats them into clean, valid GitHub Flavored Markdown tables.
Vanilla Python implementation.
"""

import re
from typing import Dict, List, Optional, Any, Tuple


class MInlineTable:
    """Represents a parsed Power Query M inline table (#table)."""

    def __init__(
        self,
        columns: List[str],
        column_types: Optional[Dict[str, str]] = None,
        rows: Optional[List[List[Any]]] = None,
        raw_snippet: str = "",
    ):
        self.columns = columns
        self.column_types = column_types or {}
        self.rows = rows or []
        self.raw_snippet = raw_snippet

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "column_types": self.column_types,
            "rows": self.rows,
            "column_count": self.column_count,
            "row_count": self.row_count,
            "raw_snippet": self.raw_snippet,
        }

    def to_markdown_table(self, max_rows: int = 50) -> str:
        """
        Renders the inline table as a GitHub Flavored Markdown table.
        Escapes pipes and sanitizes newlines to avoid table corruption.
        """
        if not self.columns:
            return "*(No columns defined for this inline table)*"

        def _clean_cell(val: Any) -> str:
            if val is None:
                return "*null*"
            s = str(val).replace("|", "\\|")
            s = " ".join(s.splitlines())
            return s if s else "*empty*"

        headers = []
        for col in self.columns:
            col_type = self.column_types.get(col)
            clean_col = str(col).replace("|", "\\|")
            if col_type:
                headers.append(f"`{clean_col}` <br><sub>*{col_type}*</sub>")
            else:
                headers.append(f"`{clean_col}`")

        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join([":---"] * len(self.columns)) + " |",
        ]

        if not self.rows:
            lines.append("| " + " | ".join(["*(no rows)*"] * len(self.columns)) + " |")
            return "\n".join(lines)

        display_rows = self.rows[:max_rows]
        for row in display_rows:
            row_cells = []
            for idx in range(len(self.columns)):
                cell_val = row[idx] if idx < len(row) else None
                row_cells.append(_clean_cell(cell_val))
            lines.append("| " + " | ".join(row_cells) + " |")

        if len(self.rows) > max_rows:
            lines.append("")
            lines.append(f"*Showing first {max_rows} of {len(self.rows)} rows.*")

        return "\n".join(lines)


def parse_m_inline_table(m_code: str) -> Optional[MInlineTable]:
    """
    Parses `#table(...)` or `#table{...}` expressions in Power Query M code.
    Returns an MInlineTable object or None if no valid #table definition is found.
    """
    if not m_code or "#table" not in m_code:
        return None

    match = re.search(r'#table\s*([\(\{])', m_code)
    if not match:
        return None

    open_paren_idx = match.start(1)
    open_char = m_code[open_paren_idx]
    close_char = ')' if open_char == '(' else '}'

    # 1. Balance enclosing parenthesis/brace to extract full #table(...) snippet
    depth = 0
    in_str = False
    end_paren_idx = -1
    i = open_paren_idx

    while i < len(m_code):
        ch = m_code[i]
        if ch == '"':
            # Handle M escaped quotes ("")
            if in_str and i + 1 < len(m_code) and m_code[i + 1] == '"':
                i += 2
                continue
            in_str = not in_str
            i += 1
            continue

        if not in_str:
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    end_paren_idx = i
                    break
        i += 1

    if end_paren_idx == -1:
        return None

    raw_snippet = m_code[match.start() : end_paren_idx + 1].strip()
    inner_body = m_code[open_paren_idx + 1 : end_paren_idx].strip()

    # 2. Split inner body into Argument 1 (columns) and Argument 2 (rows) at top-level comma
    arg1_chars = []
    arg2_chars = []
    curr_arg = 1
    depth = 0
    in_str = False

    for j, ch in enumerate(inner_body):
        if ch == '"':
            if in_str and j + 1 < len(inner_body) and inner_body[j + 1] == '"':
                pass
            else:
                in_str = not in_str
            if curr_arg == 1:
                arg1_chars.append(ch)
            else:
                arg2_chars.append(ch)
            continue

        if not in_str:
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            elif ch == ',' and depth == 0 and curr_arg == 1:
                curr_arg = 2
                continue

        if curr_arg == 1:
            arg1_chars.append(ch)
        else:
            arg2_chars.append(ch)

    arg1_str = "".join(arg1_chars).strip()
    arg2_str = "".join(arg2_chars).strip()

    # 3. Parse Argument 1: Columns & Types
    columns: List[str] = []
    column_types: Dict[str, str] = {}

    if re.search(r'type\s+table\b', arg1_str, re.IGNORECASE):
        bracket_match = re.search(r'\[(.*)\]', arg1_str, re.DOTALL)
        if bracket_match:
            bracket_inner = bracket_match.group(1).strip()
            # Split fields by comma at depth 0
            col_tokens = _split_by_comma_at_depth_0(bracket_inner)
            for token in col_tokens:
                token = token.strip()
                if not token:
                    continue
                if "=" in token:
                    parts = token.split("=", 1)
                    raw_cname = parts[0].strip()
                    c_type = parts[1].strip()
                else:
                    raw_cname = token
                    c_type = ""

                # Unquote name (e.g. #"Column Name" or 'Column Name')
                c_name = _clean_identifier(raw_cname)
                columns.append(c_name)
                if c_type:
                    column_types[c_name] = c_type
    else:
        # Standard list of column names: {"Col1", "Col2", ...}
        brace_match = re.search(r'\{(.*)\}', arg1_str, re.DOTALL)
        if brace_match:
            brace_inner = brace_match.group(1).strip()
            col_tokens = _split_by_comma_at_depth_0(brace_inner)
            for token in col_tokens:
                token = token.strip()
                if not token:
                    continue
                c_name = _clean_identifier(token)
                columns.append(c_name)

    # 4. Parse Argument 2: Rows
    rows: List[List[Any]] = []
    # Rows is a list of lists: { {r1c1, r1c2}, {r2c1, r2c2} }
    outer_brace_match = re.search(r'\{(.*)\}', arg2_str, re.DOTALL)
    if outer_brace_match:
        outer_rows_body = outer_rows_body = outer_brace_match.group(1).strip()
        # Find all top-level {...} inside outer_rows_body
        row_blocks = _extract_bracketed_blocks(outer_rows_body, '{', '}')
        for r_block in row_blocks:
            cells = _split_by_comma_at_depth_0(r_block)
            cleaned_row = [_parse_cell_value(c.strip()) for c in cells]
            rows.append(cleaned_row)

    if not columns and not rows:
        return None

    return MInlineTable(
        columns=columns,
        column_types=column_types,
        rows=rows,
        raw_snippet=raw_snippet,
    )


def _clean_identifier(name: str) -> str:
    """Cleans Power Query identifier (e.g. #'Col Name' or 'Col Name' or \"Col Name\")."""
    s = name.strip()
    if s.startswith('#"') and s.endswith('"') and len(s) >= 3:
        return s[2:-1]
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _split_by_comma_at_depth_0(text: str) -> List[str]:
    """Splits string by commas that are not nested within quotes or brackets."""
    tokens: List[str] = []
    curr: List[str] = []
    depth = 0
    in_str = False
    i = 0

    while i < len(text):
        ch = text[i]
        if ch == '"':
            if in_str and i + 1 < len(text) and text[i + 1] == '"':
                curr.append('"')
                curr.append('"')
                i += 2
                continue
            in_str = not in_str
            curr.append(ch)
            i += 1
            continue

        if not in_str:
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            elif ch == ',' and depth == 0:
                tokens.append("".join(curr).strip())
                curr = []
                i += 1
                continue

        curr.append(ch)
        i += 1

    if curr:
        tokens.append("".join(curr).strip())

    return tokens


def _extract_bracketed_blocks(text: str, open_c: str = '{', close_c: str = '}') -> List[str]:
    """Finds all top-level bracketed blocks inside text."""
    blocks: List[str] = []
    depth = 0
    in_str = False
    start_idx = -1
    i = 0

    while i < len(text):
        ch = text[i]
        if ch == '"':
            if in_str and i + 1 < len(text) and text[i + 1] == '"':
                i += 2
                continue
            in_str = not in_str
            i += 1
            continue

        if not in_str:
            if ch == open_c:
                depth += 1
                if depth == 1:
                    start_idx = i + 1
            elif ch == close_c:
                depth -= 1
                if depth == 0 and start_idx != -1:
                    blocks.append(text[start_idx:i].strip())
                    start_idx = -1
        i += 1

    return blocks


def _parse_cell_value(val: str) -> Any:
    """Parses M literal values like strings, dates, numbers, booleans, and nulls."""
    val = val.strip()
    if not val or val.lower() == "null":
        return None
    if val.lower() == "true":
        return "true"
    if val.lower() == "false":
        return "false"

    # String literal
    if val.startswith('"') and val.endswith('"') and len(val) >= 2:
        inner = val[1:-1]
        return inner.replace('""', '"')

    # Date function: #date(2023, 1, 15) -> 2023-01-15
    date_m = re.match(r'#date\s*\(\s*(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*\)', val)
    if date_m:
        y, m, d = date_m.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # DateTime function: #datetime(2023, 1, 15, 10, 30, 0)
    dt_m = re.match(r'#datetime\s*\(\s*(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*\)', val)
    if dt_m:
        y, m, d, hh, mm, ss = dt_m.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d} {int(hh):02d}:{int(mm):02d}:{int(ss):02d}"

    return val
