"""
Utility functions for markdown formatting and YAML frontmatter serialization.
100% Vanilla Python standard library.
"""

import re
from typing import Any, Dict, List


def sanitize_filename(name: str) -> str:
    """
    Cleans output file names and reference links by replacing characters
    prohibited in filesystem paths (\\, /, :, *, ?, ", <, >, |, brackets, quotes, spaces, control chars)
    with the '_' character.
    """
    if not name:
        return "unnamed"
    # Replace prohibited path characters and characters unsafe in paths/links with '_'
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f\t\r\n\[\]\'#%&`]', '_', name)
    cleaned = re.sub(r'[^\w\-\.]', '_', cleaned)
    # Collapse consecutive underscores into a single underscore
    cleaned = re.sub(r'_+', '_', cleaned)
    # Strip trailing dots or spaces which are invalid in Windows filesystem paths
    cleaned = cleaned.rstrip('. ')
    return cleaned or "unnamed"


def join_doc_path(base: str, *parts: str) -> str:
    """
    Joins a base URL or file path with one or more path components using forward slashes.
    Preserves http://, https://, file://, Windows drive letters (C:/), and UNC paths (//server/share).
    Avoids duplicate slashes and normalizes paths for Markdown link compatibility.
    """
    if not base:
        sub_parts = [str(p).strip("/\\").replace("\\", "/") for p in parts if str(p).strip("/\\")]
        return "/".join(sub_parts)

    is_network = base.startswith("\\\\") or base.startswith("//")
    clean_base = base.replace("\\", "/").rstrip("/")
    if is_network and not clean_base.startswith("//"):
        clean_base = "/" + clean_base

    sub_parts = [str(p).strip("/\\").replace("\\", "/") for p in parts if str(p).strip("/\\")]
    if not sub_parts:
        return clean_base
    return clean_base + "/" + "/".join(sub_parts)


def clean_project_name(name: Any) -> str:
    """
    Normalizes a PBIP project name by stripping technical suffixes
    such as .SemanticModel, .Report, or .pbip.
    """
    if not name:
        return "PBIP"
    clean = str(name).strip()
    for suffix in [".SemanticModel", ".semanticmodel", ".Report", ".report", ".pbip", ".PBIP"]:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
    return clean or "PBIP"


def format_yaml_frontmatter(data: Dict[str, Any]) -> str:
    """
    Serializes a dictionary into standard clean YAML frontmatter block.
    Uses json.dumps for safe scalar serialization to prevent invalid escape sequences
    (such as Windows paths \\U or \\m) from breaking YAML parsers.
    No PyYAML or external library required.
    """
    import json

    lines = ["---"]
    for key, val in data.items():
        if val is None:
            continue
        if isinstance(val, (int, float, bool)):
            lines.append(f"{key}: {str(val).lower() if isinstance(val, bool) else val}")
        elif isinstance(val, str):
            # If string contains special characters or backslashes, serialize with json.dumps for safe YAML double-quoting
            if any(ch in val for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']):
                lines.append(f"{key}: {json.dumps(val)}")
            else:
                lines.append(f"{key}: {val}")
        elif isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            elif all(isinstance(x, (str, int, float, bool)) for x in val) and len(val) <= 5 and not any(isinstance(x, str) and (':' in x or '"' in x or '\\' in x or '\n' in x) for x in val):
                # Simple inline array
                items_str = ", ".join(json.dumps(x) if isinstance(x, str) else str(x) for x in val)
                lines.append(f"{key}: [{items_str}]")
            else:
                lines.append(f"{key}:")
                for item in val:
                    if isinstance(item, dict):
                        # Nested dict inside list
                        first = True
                        for dk, dv in item.items():
                            dv_str = json.dumps(dv) if isinstance(dv, str) and any(ch in dv for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']) else dv
                            if first:
                                lines.append(f"  - {dk}: {dv_str}")
                                first = False
                            else:
                                lines.append(f"    {dk}: {dv_str}")
                    else:
                        item_str = json.dumps(item) if isinstance(item, str) else str(item)
                        lines.append(f"  - {item_str}")
        elif isinstance(val, dict):
            if not val:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for dk, dv in val.items():
                    if isinstance(dv, list):
                        items_str = ", ".join(json.dumps(x) if isinstance(x, str) else str(x) for x in dv)
                        lines.append(f"  {dk}: [{items_str}]")
                    else:
                        dv_str = json.dumps(dv) if isinstance(dv, str) and any(ch in dv for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']) else dv
                        lines.append(f"  {dk}: {dv_str}")
    lines.append("---")
    return "\n".join(lines)

