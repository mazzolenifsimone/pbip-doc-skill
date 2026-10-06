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


def format_yaml_frontmatter(data: Dict[str, Any]) -> str:
    """
    Serializes a dictionary into standard clean YAML frontmatter block.
    No PyYAML or external library required.
    """
    lines = ["---"]
    for key, val in data.items():
        if val is None:
            continue
        if isinstance(val, (int, float, bool)):
            lines.append(f"{key}: {str(val).lower() if isinstance(val, bool) else val}")
        elif isinstance(val, str):
            # If string contains special characters, quote it safely
            if any(ch in val for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n']):
                escaped = val.replace('"', '\\"').replace('\n', ' ')
                lines.append(f'{key}: "{escaped}"')
            else:
                lines.append(f"{key}: {val}")
        elif isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            elif all(isinstance(x, (str, int, float, bool)) for x in val) and len(val) <= 5 and not any(isinstance(x, str) and (':' in x or '"' in x) for x in val):
                # Simple inline array
                items_str = ", ".join(f'"{x}"' if isinstance(x, str) else str(x) for x in val)
                lines.append(f"{key}: [{items_str}]")
            else:
                lines.append(f"{key}:")
                for item in val:
                    if isinstance(item, dict):
                        # Nested dict inside list
                        first = True
                        for dk, dv in item.items():
                            if first:
                                lines.append(f"  - {dk}: {dv}")
                                first = False
                            else:
                                lines.append(f"    {dk}: {dv}")
                    else:
                        item_str = str(item).replace('"', '\\"')
                        lines.append(f'  - "{item_str}"')
        elif isinstance(val, dict):
            if not val:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for dk, dv in val.items():
                    if isinstance(dv, list):
                        items_str = ", ".join(f'"{x}"' for x in dv)
                        lines.append(f"  {dk}: [{items_str}]")
                    else:
                        lines.append(f"  {dk}: {dv}")
    lines.append("---")
    return "\n".join(lines)
