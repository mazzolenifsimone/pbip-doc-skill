"""DAX Expression Formatter for pbip-doc.

Provides robust DAX formatting conforming to common industry standards (SQLBI / DAX Formatter style):
- Strips comments (//, --, /* ... */) while protecting string literals and identifiers.
- Cleans markdown/TMDL code fences (```dax).
- Prepends canonical entity signature header ([Measure] =, 'Table'[Column] =, 'Table' =, FUNCTION Name(...) =).
- Capitalizes standard DAX keywords and built-in functions.
- Enforces proper indentation (4 spaces per nesting level) and operator/comma spacing.
"""

import re
from typing import Optional, List, Tuple

# Fixed DAX core syntax keywords and interval / enum literals (not followed by parentheses)
DAX_SYNTAX_KEYWORDS = {
    # Structural statements
    "VAR", "RETURN",
    # Logical & Membership operators
    "IN", "NOT",
    # Sort orders
    "ASC", "DESC",
    # Standard Date / Time intervals (used as bare enum arguments in DATEDIFF, etc.)
    "SECOND", "MINUTE", "HOUR", "DAY", "WEEK", "MONTH", "QUARTER", "YEAR",
    # Literals
    "TRUE", "FALSE", "BLANK",
}


def strip_dax_comments(dax: str) -> str:
    """Strips line comments (//, --) and block comments (/* ... */) from DAX code.

    Preserves text inside string literals ("..."), bracketed identifiers ([...]),
    and single-quoted table names ('...').
    """
    if not dax:
        return ""

    result = []
    i = 0
    n = len(dax)

    while i < n:
        ch = dax[i]

        # String literal "..."
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if dax[i] == '"':
                    if i + 1 < n and dax[i + 1] == '"':
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            result.append(dax[start:i])
            continue

        # Bracketed identifier [...]
        if ch == '[':
            start = i
            i += 1
            while i < n:
                if dax[i] == ']':
                    if i + 1 < n and dax[i + 1] == ']':
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            result.append(dax[start:i])
            continue

        # Quoted table identifier '...'
        if ch == "'":
            start = i
            i += 1
            while i < n:
                if dax[i] == "'":
                    if i + 1 < n and dax[i + 1] == "'":
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            result.append(dax[start:i])
            continue

        # Single-line comment //
        if ch == '/' and i + 1 < n and dax[i + 1] == '/':
            i += 2
            while i < n and dax[i] not in ('\r', '\n'):
                i += 1
            continue

        # Single-line comment --
        if ch == '-' and i + 1 < n and dax[i + 1] == '-':
            i += 2
            while i < n and dax[i] not in ('\r', '\n'):
                i += 1
            continue

        # Multi-line comment /* ... */
        if ch == '/' and i + 1 < n and dax[i + 1] == '*':
            i += 2
            while i < n:
                if dax[i] == '*' and i + 1 < n and dax[i + 1] == '/':
                    i += 2
                    break
                i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _clean_surrounding_backticks(code: str) -> str:
    """Strips markdown code fence backticks if present."""
    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r'^```[a-zA-Z]*\r?\n?', '', code)
        code = re.sub(r'\r?\n?\s*```\s*$', '', code).strip()
    return code


def _strip_existing_signature(
    expression: str,
    name: Optional[str] = None,
    table_name: Optional[str] = None,
    entity_type: str = "measure"
) -> str:
    """Strips any existing signature (e.g. `[Total Sales] =` or `Total Sales =` or `'Table'[Col] =`)
    from the beginning of the expression to avoid duplicate headers.
    """
    expr = expression.strip()
    if not name:
        return expr

    patterns = []
    clean_name = name.strip("[]'\"")

    # Measure / column assignment patterns
    patterns.append(r'^\[' + re.escape(clean_name) + r'\]\s*=')
    patterns.append(r"^'" + re.escape(clean_name) + r"'\s*=")
    patterns.append(r'^' + re.escape(clean_name) + r'\s*=')
    if table_name:
        clean_tbl = table_name.strip("[]'\"")
        patterns.append(r"^'" + re.escape(clean_tbl) + r"'\s*\[" + re.escape(clean_name) + r"\]\s*=")
        patterns.append(r'^' + re.escape(clean_tbl) + r'\s*\[" + re.escape(clean_name) + r"\]\s*=')

    if entity_type == "function":
        patterns.append(r'^(?:FUNCTION\s+)?' + re.escape(clean_name) + r'(?:\s*\([^)]*\))?\s*=>')
        patterns.append(r'^(?:FUNCTION\s+)?' + re.escape(clean_name) + r'(?:\s*\([^)]*\))?\s*=')

    for pat in patterns:
        m = re.match(pat, expr, re.IGNORECASE)
        if m:
            expr = expr[m.end():].strip()
            break

    return expr


def _format_signature(
    name: Optional[str],
    entity_type: str = "measure",
    table_name: Optional[str] = None,
    parameters_signature: Optional[str] = None
) -> str:
    """Builds the canonical header signature for the entity.

    Examples:
    - measure: `[Total Sales] =`
    - calculated_column: `'Opportunities'[Weeks Open] =`
    - calculated_table: `'Opportunity Calendar' =`
    - function: `FUNCTION ComplexCalc = (Param: type) =>`
    """
    if not name:
        return ""

    clean_name = name.strip("[]'\"")

    if entity_type == "measure":
        return f"[{clean_name}] ="

    elif entity_type in ("column", "calculated_column"):
        if table_name:
            clean_tbl = table_name.strip("[]'\"")
            return f"'{clean_tbl}'[{clean_name}] ="
        return f"[{clean_name}] ="

    elif entity_type in ("table", "calculated_table"):
        return f"'{clean_name}' ="

    elif entity_type == "function":
        if parameters_signature:
            sig = parameters_signature.strip()
            if sig.endswith("=>"):
                return f"FUNCTION {clean_name} = {sig}"
            else:
                return f"FUNCTION {clean_name} = {sig} =>"
        return f"FUNCTION {clean_name} ="

    return f"[{clean_name}] ="


class DaxToken:
    """Represents a token in a DAX expression."""
    def __init__(self, kind: str, value: str):
        self.kind = kind
        self.value = value

    def __repr__(self):
        return f"({self.kind}, {self.value!r})"


def _tokenize(dax: str) -> List[DaxToken]:
    """Tokenizes stripped DAX code into typed tokens."""
    tokens = []
    i = 0
    n = len(dax)

    while i < n:
        ch = dax[i]

        if ch in ('\r', '\n'):
            if ch == '\r' and i + 1 < n and dax[i + 1] == '\n':
                i += 2
            else:
                i += 1
            tokens.append(DaxToken('NEWLINE', '\n'))
            continue

        if ch in (' ', '\t'):
            start = i
            while i < n and dax[i] in (' ', '\t'):
                i += 1
            tokens.append(DaxToken('WHITESPACE', ' '))
            continue

        if ch == '"':
            start = i
            i += 1
            while i < n:
                if dax[i] == '"':
                    if i + 1 < n and dax[i + 1] == '"':
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            tokens.append(DaxToken('STRING', dax[start:i]))
            continue

        if ch == '[':
            start = i
            i += 1
            while i < n and dax[i] != ']':
                i += 1
            if i < n:
                i += 1
            tokens.append(DaxToken('BRACKET', dax[start:i]))
            continue

        if ch == "'":
            start = i
            i += 1
            while i < n and dax[i] != "'":
                i += 1
            if i < n:
                i += 1
            tokens.append(DaxToken('TABLE', dax[start:i]))
            continue

        if ch == '(':
            tokens.append(DaxToken('LPAREN', '('))
            i += 1
            continue

        if ch == ')':
            tokens.append(DaxToken('RPAREN', ')'))
            i += 1
            continue

        if ch == ',':
            tokens.append(DaxToken('COMMA', ','))
            i += 1
            continue

        # Multi-char operators
        two = dax[i:i+2]
        if two in ('&&', '||', '<=', '>=', '<>', '=='):
            tokens.append(DaxToken('OPERATOR', two))
            i += 2
            continue

        if ch in ('=', '<', '>', '+', '-', '*', '/', '^', '&'):
            tokens.append(DaxToken('OPERATOR', ch))
            i += 1
            continue

        if ch.isalnum() or ch in ('_', '.'):
            start = i
            while i < n and (dax[i].isalnum() or dax[i] in ('_', '.')):
                i += 1
            tokens.append(DaxToken('WORD', dax[start:i]))
            continue

        tokens.append(DaxToken('OTHER', ch))
        i += 1

    return tokens


def _get_prev_meaningful_token(tokens: List[DaxToken], idx: int) -> Optional[DaxToken]:
    i = idx - 1
    while i >= 0:
        if tokens[i].kind not in ('WHITESPACE', 'NEWLINE'):
            return tokens[i]
        i -= 1
    return None


def _get_next_meaningful_token(tokens: List[DaxToken], idx: int) -> Optional[DaxToken]:
    i = idx + 1
    n = len(tokens)
    while i < n:
        if tokens[i].kind not in ('WHITESPACE', 'NEWLINE'):
            return tokens[i]
        i += 1
    return None


def _format_tokens(tokens: List[DaxToken]) -> str:
    """Processes tokens to capitalize functions/keywords, normalize spacing and indentation."""
    # Step 1: Normalize casing and detect function calls
    variables = set()

    for idx, tok in enumerate(tokens):
        if tok.kind == 'WORD':
            # Check if preceded by VAR
            prev_tok = _get_prev_meaningful_token(tokens, idx)
            if prev_tok and prev_tok.kind == 'WORD' and prev_tok.value.upper() == 'VAR':
                variables.add(tok.value.lower())
                continue

            # Check if followed by [ -> table name
            next_tok = _get_next_meaningful_token(tokens, idx)
            if next_tok and next_tok.kind == 'BRACKET':
                continue

            # If it's a variable reference, preserve casing
            if tok.value.lower() in variables:
                continue

            # If numeric literal, skip
            if re.match(r'^-?\d+(?:\.\d+)?$', tok.value):
                continue

            # 1. Core DAX syntax keywords and bare literals
            if tok.value.upper() in DAX_SYNTAX_KEYWORDS:
                tok.value = tok.value.upper()
                continue

            # 2. Structural DAX function invocation:
            # In DAX grammar, any identifier followed by '(' is syntactically a function call.
            # This dynamically supports 100% of current, future, and custom DAX functions without maintaining a static list.
            if next_tok and next_tok.kind == 'LPAREN':
                tok.value = tok.value.upper()
                continue

    # Step 2: Build formatted output with proper indentation
    has_newlines = any(t.kind == 'NEWLINE' for t in tokens)
    has_var = any(t.kind == 'WORD' and t.value == 'VAR' for t in tokens)
    is_multiline = has_newlines or has_var

    if not is_multiline:
        return _render_inline(tokens)
    else:
        return _render_multiline(tokens)


def _render_inline(tokens: List[DaxToken]) -> str:
    out = []

    for idx, tok in enumerate(tokens):
        if tok.kind in ('WHITESPACE', 'NEWLINE'):
            continue

        prev_tok = _get_prev_meaningful_token(tokens, idx)

        # Spacing before tok
        if prev_tok:
            if tok.kind == 'COMMA':
                pass
            elif tok.kind == 'RPAREN':
                # No space before ) if empty args ()
                if prev_tok.kind != 'LPAREN':
                    out.append(' ')
            elif tok.kind == 'LPAREN':
                # Space before ( if preceded by WORD (function call)
                if prev_tok.kind == 'WORD':
                    out.append(' ')
                elif prev_tok.kind in ('OPERATOR', 'COMMA'):
                    out.append(' ')
            elif tok.kind == 'BRACKET':
                # No space between TABLE/WORD and [ (e.g. Table[Col])
                if prev_tok.kind not in ('TABLE', 'WORD'):
                    out.append(' ')
            elif tok.kind == 'OPERATOR':
                # Check unary minus
                if tok.value == '-' and (prev_tok.kind in ('LPAREN', 'COMMA', 'OPERATOR') or prev_tok.value in ('VAR', 'RETURN')):
                    pass
                else:
                    out.append(' ')
            else:
                # Normal word, string, table, etc.
                if prev_tok.kind == 'LPAREN':
                    out.append(' ')
                elif prev_tok.kind == 'OPERATOR':
                    out.append(' ')
                elif prev_tok.kind == 'COMMA':
                    out.append(' ')
                else:
                    out.append(' ')

        out.append(tok.value)

    res = "".join(out)
    # Fix empty parens: "( )" -> "()"
    res = re.sub(r'\(\s+\)', '()', res)
    return res.strip()


def _render_multiline(tokens: List[DaxToken]) -> str:
    """Renders multiline DAX with clean 4-space indentation and aligned parens."""
    lines = []
    current_line = []
    indent_level = 0
    paren_depth_stack = []

    meaningful_tokens = [t for t in tokens if t.kind != 'WHITESPACE']
    n = len(meaningful_tokens)
    idx = 0

    while idx < n:
        tok = meaningful_tokens[idx]

        if tok.kind == 'NEWLINE':
            if current_line:
                lines.append((indent_level, current_line))
                current_line = []
            idx += 1
            continue

        # Handle VAR statement start
        if tok.kind == 'WORD' and tok.value == 'VAR':
            if current_line:
                lines.append((indent_level, current_line))
                current_line = []
            indent_level = 0
            current_line.append(tok)
            idx += 1
            continue

        # Handle RETURN statement start
        if tok.kind == 'WORD' and tok.value == 'RETURN':
            if current_line:
                lines.append((indent_level, current_line))
                current_line = []
            lines.append((0, [tok]))
            indent_level = 1
            idx += 1
            continue

        # Closing parenthesis on a line
        if tok.kind == 'RPAREN':
            if paren_depth_stack:
                target_indent = paren_depth_stack.pop()
                if not current_line:
                    indent_level = target_indent

        if tok.kind == 'LPAREN':
            paren_depth_stack.append(indent_level)

        current_line.append(tok)
        idx += 1

    if current_line:
        lines.append((indent_level, current_line))

    # Format each line using inline renderer with depth
    rendered_lines = []
    current_indent = 0
    indent_stack = []

    for raw_indent, line_toks in lines:
        if not line_toks:
            continue

        first = line_toks[0]
        # Adjust indent for closing parenthesis at start of line
        closing_count_at_start = 0
        for t in line_toks:
            if t.kind == 'RPAREN':
                closing_count_at_start += 1
            else:
                break

        if closing_count_at_start > 0:
            for _ in range(closing_count_at_start):
                if indent_stack:
                    current_indent = indent_stack.pop()
                else:
                    current_indent = max(0, current_indent - 1)

        # RETURN and VAR start at 0
        if first.kind == 'WORD' and first.value in ('VAR', 'RETURN'):
            line_indent = 0
        elif first.kind == 'OPERATOR' and first.value in ('&&', '||'):
            # Logical operator continuations are indented 1 level extra for readability
            line_indent = current_indent + 1
        else:
            line_indent = current_indent

        line_str = _render_inline(line_toks)
        rendered_lines.append(f"{'    ' * line_indent}{line_str}")

        # If line was RETURN, next line indents
        if first.kind == 'WORD' and first.value == 'RETURN':
            current_indent = 1
            continue

        # If line ended with VAR ... =, next line indents if multiline
        if any(t.kind == 'WORD' and t.value == 'VAR' for t in line_toks) and line_toks[-1].kind == 'OPERATOR' and line_toks[-1].value == '=':
            current_indent = 1

        # Calculate net change in parentheses
        open_parens = sum(1 for t in line_toks if t.kind == 'LPAREN')
        close_parens = sum(1 for t in line_toks if t.kind == 'RPAREN')
        net_parens = open_parens - close_parens

        if net_parens > 0:
            for _ in range(net_parens):
                indent_stack.append(current_indent)
                current_indent += 1

    return "\n".join(rendered_lines)


def format_dax(
    expression: str,
    name: Optional[str] = None,
    entity_type: str = "measure",
    table_name: Optional[str] = None,
    parameters_signature: Optional[str] = None,
) -> str:
    """Formats a DAX expression according to standard DAX conventions.

    Parameters:
    - expression: The raw DAX formula string.
    - name: The name of the measure, column, table, or function being defined.
    - entity_type: One of 'measure', 'column'/'calculated_column', 'table'/'calculated_table', or 'function'.
    - table_name: Parent table name (required for calculated columns, optional for measures).
    - parameters_signature: Parameters signature string for user-defined functions.

    Returns:
    The cleanly formatted DAX expression with comment stripping, normalized casing,
    4-space indentation, and canonical entity signature header.
    """
    if not expression or not expression.strip():
        sig = _format_signature(name, entity_type, table_name, parameters_signature)
        return f"{sig}\nBLANK ()" if sig else "BLANK ()"

    code = _clean_surrounding_backticks(expression)
    code = strip_dax_comments(code)
    code = _strip_existing_signature(code, name, table_name, entity_type)

    if not code:
        sig = _format_signature(name, entity_type, table_name, parameters_signature)
        return f"{sig}\nBLANK ()" if sig else "BLANK ()"

    tokens = _tokenize(code)
    formatted_body = _format_tokens(tokens)

    sig = _format_signature(name, entity_type, table_name, parameters_signature)
    if sig:
        return f"{sig}\n{formatted_body}"
    return formatted_body
