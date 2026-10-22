"""
Power Query (M) Code Formatter.
Provides standardized, readable formatting for Power Query M expressions.
100% Vanilla Python standard library with zero external dependencies.
"""

import re
from typing import List, Tuple, Optional


# Immutable, standardized Power Query M language core keywords
M_KEYWORDS = {
    "let", "in", "if", "then", "else", "try", "otherwise", "each", "type", "meta"
}


def strip_m_comments(code: str) -> str:
    """Removes single-line (//) and multi-line (/* */) comments while preserving string literals."""
    if not code:
        return ""
    
    result = []
    i = 0
    n = len(code)
    in_str = False
    in_ident = False
    
    while i < n:
        ch = code[i]
        
        # Handle quoted identifier #"..."
        if not in_str and ch == '#' and i + 1 < n and code[i + 1] == '"':
            in_ident = True
            result.append(ch)
            result.append('"')
            i += 2
            continue
            
        if in_ident:
            result.append(ch)
            if ch == '"':
                in_ident = False
            i += 1
            continue
            
        # Handle string literals "..."
        if ch == '"' and not in_ident:
            in_str = not in_str
            result.append(ch)
            i += 1
            continue
            
        if in_str:
            result.append(ch)
            i += 1
            continue
            
        # Multi-line comment /* ... */
        if ch == '/' and i + 1 < n and code[i + 1] == '*':
            end = code.find('*/', i + 2)
            if end != -1:
                i = end + 2
                continue
            else:
                break
                
        # Single-line comment // ...
        if ch == '/' and i + 1 < n and code[i + 1] == '/':
            end = code.find('\n', i + 2)
            if end != -1:
                i = end
                continue
            else:
                break
                
        result.append(ch)
        i += 1
        
    return "".join(result)


def _split_m_let_in(code: str) -> Optional[Tuple[List[str], str]]:
    """
    Parses a Power Query M expression into (steps, in_expression).
    Respects string literals, quoted identifiers, and nested delimiters (), {}, [].
    Returns None if the expression is not a top-level let ... in block.
    """
    cleaned = code.strip()
    # Check leading 'let'
    m_let = re.match(r'^let\b', cleaned, re.IGNORECASE)
    if not m_let:
        return None
        
    body_and_in = cleaned[m_let.end():].strip()
    
    # Scan for top-level 'in' keyword
    i = 0
    n = len(body_and_in)
    in_str = False
    in_ident = False
    nesting = 0
    in_pos = -1
    
    while i < n:
        ch = body_and_in[i]
        
        if not in_str and ch == '#' and i + 1 < n and body_and_in[i + 1] == '"':
            in_ident = True
            i += 2
            continue
            
        if in_ident:
            if ch == '"':
                in_ident = False
            i += 1
            continue
            
        if ch == '"' and not in_ident:
            in_str = not in_str
            i += 1
            continue
            
        if in_str:
            i += 1
            continue
            
        # Delimiters
        if ch in '({[':
            nesting += 1
            i += 1
            continue
        elif ch in ')}]':
            if nesting > 0:
                nesting -= 1
            i += 1
            continue
            
        if nesting == 0:
            # Check for word boundary 'in'
            if (i == 0 or body_and_in[i - 1] in ' \t\r\n,;)]}') and body_and_in[i:i + 2].lower() == "in":
                # Ensure followed by boundary
                if i + 2 == n or body_and_in[i + 2] in ' \t\r\n([{':
                    in_pos = i
                    break
                    
        i += 1
        
    if in_pos == -1:
        return None
        
    let_body = body_and_in[:in_pos].strip()
    in_expr = body_and_in[in_pos + 2:].strip()
    
    # Split let_body into top-level steps by comma
    steps: List[str] = []
    i = 0
    n = len(let_body)
    start = 0
    nesting = 0
    in_str = False
    in_ident = False
    
    while i < n:
        ch = let_body[i]
        
        if not in_str and ch == '#' and i + 1 < n and let_body[i + 1] == '"':
            in_ident = True
            i += 2
            continue
            
        if in_ident:
            if ch == '"':
                in_ident = False
            i += 1
            continue
            
        if ch == '"' and not in_ident:
            in_str = not in_str
            i += 1
            continue
            
        if in_str:
            i += 1
            continue
            
        if ch in '({[':
            nesting += 1
            i += 1
            continue
        elif ch in ')}]':
            if nesting > 0:
                nesting -= 1
            i += 1
            continue
            
        if ch == ',' and nesting == 0:
            step = let_body[start:i].strip()
            if step:
                steps.append(step + ",")
            start = i + 1
            
        i += 1
        
    last_step = let_body[start:].strip()
    if last_step:
        steps.append(last_step)
        
    return steps, in_expr


def format_m(raw_code: str, indent_size: int = 4) -> str:
    """
    Formats a Power Query M expression into clean, standard, indented M code.
    
    Standard rules:
    - Normalizes erratic TMDL tabs and indentation.
    - 'let' is positioned at base indentation (0).
    - Every assignment step inside 'let' is placed on a new line and indented by 4 spaces.
    - 'in' is positioned at base indentation (0).
    - The output expression after 'in' is indented by 4 spaces.
    - Preserves string literals and quoted identifiers exactly.
    - Keeps keywords limited strictly to immutable M language keywords.
    """
    if not raw_code or not raw_code.strip():
        return ""

    cleaned = raw_code.strip()
    indent = " " * indent_size
    
    # 1. Try structural let ... in parser
    parsed = _split_m_let_in(cleaned)
    if parsed:
        steps, in_expr = parsed
        formatted_lines = ["let"]
        
        for st in steps:
            # Clean erratic leading/trailing whitespace inside step lines
            st_lines = [l.strip() for l in st.splitlines() if l.strip()]
            if len(st_lines) <= 1:
                formatted_lines.append(f"{indent}{st.strip()}")
            else:
                # Multi-line step (e.g. nested table transform column types)
                # First line at 1 indent, subsequent lines at 2 indents
                formatted_lines.append(f"{indent}{st_lines[0]}")
                for sub_line in st_lines[1:]:
                    formatted_lines.append(f"{indent * 2}{sub_line}")
                    
        formatted_lines.append("in")
        in_lines = [l.strip() for l in in_expr.splitlines() if l.strip()]
        for inl in in_lines:
            formatted_lines.append(f"{indent}{inl}")
            
        return "\n".join(formatted_lines)

    # 2. Fallback: clean line-by-line whitespace
    lines = [line.rstrip() for line in cleaned.splitlines()]
    min_indent = None
    for l in lines:
        if l.strip():
            indent_len = len(l) - len(l.lstrip())
            if min_indent is None or indent_len < min_indent:
                min_indent = indent_len
                
    if min_indent and min_indent > 0:
        cleaned_lines = [l[min_indent:] if len(l) >= min_indent else l for l in lines]
    else:
        cleaned_lines = lines
        
    return "\n".join(cleaned_lines)
