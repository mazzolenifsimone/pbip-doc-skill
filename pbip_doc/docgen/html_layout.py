"""
Master HTML Shell & Layout Builder for Native Documentation Portal.
Generates responsive executive layout with collapsible tree sidebar, client-side search,
breadcrumbs, and theme toggling.
100% Vanilla Python standard library.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import html

from .config import DocGenConfig
from .utils import sanitize_filename, clean_project_name
from ..report_schema import PBIPReportModel


def get_relative_root(current_path: str) -> str:
    """Calculates relative root path (e.g. '.', '..', '../..') from current file path."""
    parts = current_path.replace("\\", "/").strip("/").split("/")
    depth = len(parts) - 1
    if depth <= 0:
        return "."
    return "/".join([".."] * depth)


def get_table_role_badge_class(role: str) -> str:
    r = (role or "UNKNOWN").upper()
    if r in ("FACT", "FACT_TABLE"):
        return "badge-role-fact"
    elif r in ("DIMENSION", "DIM"):
        return "badge-role-dim"
    elif r in ("LOOKUP_OUTRIGGER", "SNOWFLAKE", "OUTRIGGER"):
        return "badge-role-snowflake"
    elif r in ("BRIDGE", "BRIDGE_TABLE"):
        return "badge-role-bridge"
    elif r in ("DATE_DIMENSION", "DATE", "CALENDAR"):
        return "badge-role-date"
    elif r in ("CALCULATION_GROUP", "CALCGROUP"):
        return "badge-role-calcgroup"
    return "badge-role-utility"


def get_table_role_short(role: str) -> str:
    r = (role or "UNKNOWN").upper()
    if r in ("FACT", "FACT_TABLE"):
        return "Fact"
    elif r in ("DIMENSION", "DIM"):
        return "Dim"
    elif r in ("LOOKUP_OUTRIGGER", "SNOWFLAKE", "OUTRIGGER"):
        return "Snow"
    elif r in ("BRIDGE", "BRIDGE_TABLE"):
        return "Bridge"
    elif r in ("DATE_DIMENSION", "DATE", "CALENDAR"):
        return "Date"
    elif r in ("CALCULATION_GROUP", "CALCGROUP"):
        return "CalcGroup"
    return "Utility"


class HtmlLayoutBuilder:
    """
    Renders the outer HTML5 responsive shell wrapping all modular documentation pages.
    """

    def __init__(
        self,
        project_name: str,
        data: Dict[str, Any],
        config: DocGenConfig,
        report_model: Optional[PBIPReportModel] = None,
    ):
        self.project_name = project_name
        self.data = data
        self.config = config
        self.report = report_model

    def wrap_page(
        self,
        current_path: str,
        page_title: str,
        breadcrumbs: List[Tuple[str, Optional[str]]],
        content_html: str,
    ) -> str:
        """
        Wraps content_html into complete HTML document with sidebar, topbar, and assets.
        """
        rel_root = get_relative_root(current_path)
        css_url = f"{rel_root}/assets/style.css"
        index_url = f"{rel_root}/index.html"

        sidebar_html = self._build_sidebar(current_path, rel_root)
        breadcrumbs_html = self._build_breadcrumbs(breadcrumbs)

        escaped_title = html.escape(page_title)
        escaped_project = html.escape(self.config.html_title or self.project_name)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - {escaped_project} Documentation</title>
  <link rel="stylesheet" href="{css_url}">
</head>
<body>
  <div class="wiki-layout">
    <aside class="wiki-sidebar" id="sidebar">
      <div class="sidebar-header">
        <a href="{index_url}" class="sidebar-title-link">
          <svg class="sidebar-title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
          </svg>
          <span>{escaped_project}</span>
          <span class="sidebar-badge">Docs</span>
        </a>
      </div>
      <nav class="sidebar-nav">
{sidebar_html}
      </nav>
    </aside>

    <div class="wiki-main">
      <header class="wiki-topbar">
        <div class="breadcrumbs">
{breadcrumbs_html}
        </div>
      </header>

      <main class="wiki-article">
{content_html}
      </main>
    </div>
  </div>
</body>
</html>
"""

    def _build_breadcrumbs(self, breadcrumbs: List[Tuple[str, Optional[str]]]) -> str:
        lines = []
        for idx, (label, link) in enumerate(breadcrumbs):
            escaped_lbl = html.escape(label)
            if idx > 0:
                lines.append('<span class="breadcrumb-sep">/</span>')
            if link:
                lines.append(f'<a href="{html.escape(link)}">{escaped_lbl}</a>')
            else:
                lines.append(f'<span class="breadcrumb-current">{escaped_lbl}</span>')
        return " ".join(lines)

    def _build_sidebar(self, current_path: str, rel_root: str) -> str:
        lines = []
        index_active = " active" if current_path == "index.html" else ""
        lines.append(f"""        <div class="nav-section">
          <ul class="nav-list">
            <li class="nav-item">
              <a href="{rel_root}/index.html" class="nav-link{index_active}">
                <span>Model Overview</span>
              </a>
            </li>
          </ul>
        </div>""")

        # 1. Tables Section
        tables = [t for t in self.data.get("tables", []) if self.config.is_table_published(t)]
        if tables:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Tables</span>
            <span class="sidebar-badge">{len(tables)}</span>
          </div>
          <ul class="nav-list">""")
            for t in sorted(tables, key=lambda x: x.get("name", "")):
                t_name = t.get("name", "Table")
                clean_name = sanitize_filename(t_name)
                t_rel = f"{self.config.tables_subdir.strip('/\\\\')}/{clean_name}.html"
                is_active = " active" if current_path == t_rel else ""
                role = t.get("role", "DIM")
                role_class = get_table_role_badge_class(role)
                role_short = get_table_role_short(role)

                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{t_rel}" class="nav-link{is_active}" title="{html.escape(t_name)}">
                <span>{html.escape(t_name)}</span>
                <span class="nav-item-badge badge {role_class}">{role_short}</span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        # 2. Measures Section (Grouped by host table)
        published_measures = [m for m in self.data.get("measures", []) if self.config.is_measure_published(m)]
        # Fallback if self.data["measures"] was empty
        if not published_measures:
            for t in tables:
                for m in t.get("measures", []):
                    if not m.get("table"):
                        m["table"] = t.get("name")
                    if self.config.is_measure_published(m):
                        published_measures.append(m)

        if published_measures:
            measures_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for m in published_measures:
                tbl = m.get("table", "Model")
                measures_by_table.setdefault(tbl, []).append(m)

            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Measures</span>
            <span class="sidebar-badge">{len(published_measures)}</span>
          </div>
          <ul class="nav-list">""")

            for tbl, m_list in sorted(measures_by_table.items()):
                clean_tbl = sanitize_filename(tbl)
                is_current_table = current_path.startswith(f"{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/")
                open_attr = " open" if is_current_table else ""

                lines.append(f"""            <li class="nav-subgroup">
              <details class="nav-details"{open_attr}>
                <summary class="nav-subgroup-header">
                  <span>{html.escape(tbl)} ({len(m_list)})</span>
                </summary>
                <ul class="nav-list nav-subgroup-items">""")

                for m in sorted(m_list, key=lambda x: x.get("name", "")):
                    m_name = m.get("name", "Measure")
                    clean_m = sanitize_filename(m_name)
                    m_rel = f"{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_m}.html"
                    is_active = " active" if current_path == m_rel else ""
                    lines.append(f"""                <li class="nav-item">
                  <a href="{rel_root}/{m_rel}" class="nav-link{is_active}" title="{html.escape(m_name)}">
                    <span>{html.escape(m_name)}</span>
                  </a>
                </li>""")
                lines.append("                </ul>\n              </details>\n            </li>")

            lines.append("          </ul>\n        </div>")

        # 3. Report & Visual Pages Section
        if self.config.include_visual_docs and self.report and self.report.pages:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Report Pages</span>
            <span class="sidebar-badge">{len(self.report.pages)}</span>
          </div>
          <ul class="nav-list">""")
            for p in self.report.pages:
                clean_p = sanitize_filename(p.display_name)
                p_rel = f"{self.config.visuals_subdir.strip('/\\\\')}/{clean_p}.html"
                is_active = " active" if current_path == p_rel else ""
                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{p_rel}" class="nav-link{is_active}" title="{html.escape(p.display_name)}">
                <span>{html.escape(p.display_name)}</span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        # 4. Shared Expressions Section
        if self.config.include_expression_docs:
            exprs = self.data.get("expressions") or self.data.get("shared_queries") or []
            if exprs:
                lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Expressions</span>
            <span class="sidebar-badge">{len(exprs)}</span>
          </div>
          <ul class="nav-list">""")
                for e in exprs:
                    q_name = e.get("query_name") or "Expression"
                    clean_q = sanitize_filename(q_name)
                    e_rel = f"{self.config.expressions_subdir.strip('/\\\\')}/{clean_q}.html"
                    is_active = " active" if current_path == e_rel else ""
                    lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{e_rel}" class="nav-link{is_active}">
                <span>{html.escape(q_name)}</span>
              </a>
            </li>""")
                lines.append("          </ul>\n        </div>")

        # 5. Functions Section
        funcs = self.data.get("functions", [])
        if funcs:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Functions</span>
            <span class="sidebar-badge">{len(funcs)}</span>
          </div>
          <ul class="nav-list">""")
            for fn in funcs:
                f_name = fn.get("name") or "Function"
                clean_f = sanitize_filename(f_name)
                f_rel = f"{self.config.functions_subdir.strip('/\\\\')}/{clean_f}.html"
                is_active = " active" if current_path == f_rel else ""
                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{f_rel}" class="nav-link{is_active}">
                <span>{html.escape(f_name)}</span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        return "\n".join(lines)
