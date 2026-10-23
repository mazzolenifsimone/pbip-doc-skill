"""
Multi-Artifact Workspace & Codebase Documentation Engine.
Generates unified, modular, cross-referenced Markdown and HTML portals
for entire Power BI PBIP workspaces containing multiple Semantic Models and Reports.
100% Vanilla Python standard library.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple, Union

from .config import (
    DocGenConfig,
    DEFAULT_MODELS_SUBDIR,
    DEFAULT_REPORTS_SUBDIR,
    DEFAULT_TABLES_SUBDIR,
    DEFAULT_MEASURES_SUBDIR,
    DEFAULT_FUNCTIONS_SUBDIR,
    DEFAULT_EXPRESSIONS_SUBDIR,
    DEFAULT_VISUALS_SUBDIR,
    DEFAULT_ASSETS_SUBDIR,
)
from .utils import sanitize_filename, clean_project_name
from .engine import MarkdownDocGenerator
from .html_engine import HtmlDocGenerator
from .html_layout import get_relative_root, get_table_role_badge_class, get_table_role_short
from .html_assets import STYLE_CSS
from .visual_doc import PageVisualDocBuilder
from .html_builders import HtmlVisualBuilder, escape
from ..codebase_scanner import WorkspaceScanResult, DiscoveredModel, DiscoveredReport
from ..report_schema import PBIPReportModel


class WorkspaceHtmlLayoutBuilder:
    """
    Renders the unified enterprise HTML shell wrapping all workspace pages
    with an accordion navigation tree spanning all Semantic Models and Reports.
    """

    def __init__(
        self,
        workspace_scan: WorkspaceScanResult,
        config: DocGenConfig,
        workspace_title: Optional[str] = None,
    ):
        self.scan = workspace_scan
        self.config = config
        self.workspace_title = workspace_title or self.config.html_title or f"{clean_project_name(self.scan.root_path.name)} Workspace"

    def wrap_page(
        self,
        current_path: str,
        page_title: str,
        breadcrumbs: List[Tuple[str, Optional[str]]],
        content_html: str,
    ) -> str:
        """Wraps content_html into a responsive enterprise layout with unified sidebar."""
        rel_root = get_relative_root(current_path)
        css_url = f"{rel_root}/assets/style.css"
        index_url = f"{rel_root}/index.html"

        sidebar_html = self._build_unified_sidebar(current_path, rel_root)
        breadcrumbs_html = self._build_breadcrumbs(breadcrumbs)

        escaped_title = escape(page_title)
        escaped_workspace = escape(self.workspace_title)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} | {escaped_workspace}</title>
  <link rel="stylesheet" href="{css_url}">
</head>
<body>
  <div class="wiki-layout">
    <!-- Sidebar Navigation -->
    <aside class="wiki-sidebar" id="sidebar">
      <div class="sidebar-header">
        <a href="{index_url}" class="sidebar-logo">
          <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="3" width="20" height="18" rx="2"></rect>
            <path d="M7 8h10M7 12h10M7 16h6"></path>
          </svg>
          <span class="logo-text">{escaped_workspace}</span>
        </a>
      </div>

      <nav class="sidebar-nav">
{sidebar_html}
      </nav>

      <div class="sidebar-footer">
        <div class="engine-badge">
          <span>pbip-doc-skill</span>
          <span class="version-tag">Workspace v0.2.0</span>
        </div>
      </div>
    </aside>

    <!-- Main Content Container -->
    <div class="wiki-main">
      <header class="wiki-topbar">
        <div class="topbar-left">
          <div class="wiki-breadcrumbs">
            {breadcrumbs_html}
          </div>
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
            escaped_lbl = escape(label)
            if idx > 0:
                lines.append('<span class="breadcrumb-sep">/</span>')
            if link:
                lines.append(f'<a href="{escape(link)}">{escaped_lbl}</a>')
            else:
                lines.append(f'<span class="breadcrumb-current">{escaped_lbl}</span>')
        return " ".join(lines)

    def _build_unified_sidebar(self, current_path: str, rel_root: str) -> str:
        lines = []
        index_active = " active" if current_path == "index.html" else ""
        lines.append(f"""        <div class="nav-section">
          <ul class="nav-list">
            <li class="nav-item">
              <a href="{rel_root}/index.html" class="nav-link{index_active}">
                <span>Workspace Catalog</span>
              </a>
            </li>
          </ul>
        </div>""")

        # 1. Semantic Models Section
        if self.scan.models:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Semantic Models</span>
            <span class="sidebar-badge">{len(self.scan.models)}</span>
          </div>
          <ul class="nav-list">""")

            for m_id, model in sorted(self.scan.models.items(), key=lambda x: x[1].name):
                scoped_cfg = self.config.get_scoped_config(model.artifact_id)
                safe_m = sanitize_filename(model.name)
                m_base = f"models/{safe_m}"
                is_current_model = current_path.startswith(f"{m_base}/")
                open_attr = " open" if is_current_model else ""
                overview_active = " active" if current_path == f"{m_base}/index.html" else ""

                lines.append(f"""            <li class="nav-subgroup">
              <details class="nav-details"{open_attr}>
                <summary class="nav-subgroup-header">
                  <span>{escape(model.name)}</span>
                </summary>
                <ul class="nav-list nav-subgroup-items">
                  <li class="nav-item">
                    <a href="{rel_root}/{m_base}/index.html" class="nav-link{overview_active}">
                      <span>Model Overview</span>
                    </a>
                  </li>""")

                # Model Tables Sub-items (if populated)
                if model.tables:
                    for t in sorted(model.tables):
                        if scoped_cfg.is_table_excluded(t):
                            continue
                        clean_t = sanitize_filename(t)
                        t_path = f"{m_base}/tables/{clean_t}.html"
                        t_active = " active" if current_path == t_path else ""
                        lines.append(f"""                <li class="nav-item">
                  <a href="{rel_root}/{t_path}" class="nav-link{t_active}" title="{escape(t)}">
                    <span>{escape(t)}</span>
                  </a>
                </li>""")

                lines.append("                </ul>\n              </details>\n            </li>")

            lines.append("          </ul>\n        </div>")

        # 2. Reports Section
        if self.scan.reports:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Reports & Dashboards</span>
            <span class="sidebar-badge">{len(self.scan.reports)}</span>
          </div>
          <ul class="nav-list">""")

            for r_id, report in sorted(self.scan.reports.items(), key=lambda x: x[1].name):
                safe_r = sanitize_filename(report.name)
                r_base = f"reports/{safe_r}"
                is_current_report = current_path.startswith(f"{r_base}/")
                open_attr = " open" if is_current_report else ""
                overview_active = " active" if current_path == f"{r_base}/index.html" else ""

                lines.append(f"""            <li class="nav-subgroup">
              <details class="nav-details"{open_attr}>
                <summary class="nav-subgroup-header">
                  <span>{escape(report.name)}</span>
                </summary>
                <ul class="nav-list nav-subgroup-items">
                  <li class="nav-item">
                    <a href="{rel_root}/{r_base}/index.html" class="nav-link{overview_active}">
                      <span>Report Overview</span>
                    </a>
                  </li>""")

                # Report Pages
                if report.page_names:
                    for p in report.page_names:
                        clean_p = sanitize_filename(p)
                        p_path = f"{r_base}/visuals/{clean_p}.html"
                        p_active = " active" if current_path == p_path else ""
                        lines.append(f"""                <li class="nav-item">
                  <a href="{rel_root}/{p_path}" class="nav-link{p_active}" title="{escape(p)}">
                    <span>{escape(p)}</span>
                  </a>
                </li>""")

                lines.append("                </ul>\n              </details>\n            </li>")

            lines.append("          </ul>\n        </div>")

        return "\n".join(lines)


class WorkspaceDocGenerator:
    """
    Main entry point for generating complete multi-artifact workspace documentation
    for both Markdown and HTML portals.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_markdown_documents(self, scan_result: WorkspaceScanResult) -> Dict[str, str]:
        """
        Generates dictionary of all Markdown documents across the workspace:
        {
          "README.md": workspace_catalog,
          "models/<ModelName>/README.md": model_catalog,
          "models/<ModelName>/tables/<Table>.md": table_doc,
          ...
          "reports/<ReportName>/README.md": report_overview,
          "reports/<ReportName>/visuals/<Page>.md": page_doc,
        }
        """
        documents: Dict[str, str] = {}

        # 1. Root Workspace Catalog (README.md)
        documents["README.md"] = self._build_workspace_index_markdown(scan_result)

        # 2. Generate Documentation for each Semantic Model
        for m_id, model in scan_result.models.items():
            safe_m = sanitize_filename(model.name)
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            md_gen = MarkdownDocGenerator(scoped_cfg)

            # Generate model docs
            model_input = model.model_obj if model.model_obj else model.path
            m_docs = md_gen.generate_all_documents(model_input)

            for rel_file, content in m_docs.items():
                # Normalize index to README.md
                if "/" not in rel_file and "\\" not in rel_file and rel_file.endswith(".md"):
                    documents[f"models/{safe_m}/README.md"] = content
                else:
                    documents[f"models/{safe_m}/{rel_file}"] = content

        # 3. Generate Documentation for each Report
        for r_id, report in scan_result.reports.items():
            safe_r = sanitize_filename(report.name)
            scoped_cfg = self.config.get_scoped_config(report.artifact_id)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            bound_m_name = bound_m.name if bound_m else report.bound_model_name

            # Report Overview README.md
            documents[f"reports/{safe_r}/README.md"] = self._build_report_overview_markdown(report, scan_result, bound_m)

            # Visual Pages
            if scoped_cfg.include_visual_docs and report.report_obj:
                m_dict = bound_m.model_obj.to_dict() if bound_m and bound_m.model_obj else {}
                tables_list = m_dict.get("tables", [])
                measures_list = m_dict.get("measures", [])

                for page in report.report_obj.pages:
                    clean_page = sanitize_filename(page.display_name)
                    vis_builder = PageVisualDocBuilder(
                        page=page,
                        report_model=report.report_obj,
                        model_tables=tables_list,
                        model_measures=measures_list,
                        config=scoped_cfg,
                        project_name=report.name,
                    )
                    # Override target dataset name to bound model
                    if bound_m_name:
                        vis_builder.target_dataset_name = bound_m_name

                    p_md = vis_builder.build_markdown()
                    documents[f"reports/{safe_r}/visuals/{clean_page}.md"] = p_md

                    # SVG maps
                    svg_assets = vis_builder.build_svg_assets()
                    for svg_rel, svg_content in svg_assets.items():
                        documents[f"reports/{safe_r}/visuals/{svg_rel}"] = svg_content

        return documents

    def generate_all_html_documents(self, scan_result: WorkspaceScanResult) -> Dict[str, str]:
        """
        Generates dictionary of all HTML documents and static assets across the workspace:
        {
          "index.html": workspace_catalog,
          "assets/style.css": css,
          "models/<ModelName>/index.html": model_catalog,
          ...
          "reports/<ReportName>/index.html": report_catalog,
          "reports/<ReportName>/visuals/<Page>.html": page_doc,
        }
        """
        documents: Dict[str, str] = {}
        layout = WorkspaceHtmlLayoutBuilder(scan_result, self.config)

        # 1. Static Assets (CSS only - 100% Zero-JS)
        documents["assets/style.css"] = STYLE_CSS

        # 2. Master Workspace Catalog (index.html)
        index_content = self._build_workspace_index_html(scan_result)
        documents["index.html"] = layout.wrap_page(
            current_path="index.html",
            page_title="Workspace Catalog",
            breadcrumbs=[("Workspace", None)],
            content_html=index_content,
        )

        # 3. Generate HTML for each Semantic Model
        for m_id, model in scan_result.models.items():
            safe_m = sanitize_filename(model.name)
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            html_gen = HtmlDocGenerator(scoped_cfg)

            model_input = model.model_obj if model.model_obj else model.path
            m_docs = html_gen.generate_all_documents(
                model_input,
                layout_override=layout,
                base_prefix=f"models/{safe_m}",
            )

            for target_path, content in m_docs.items():
                documents[target_path] = content

        # 4. Generate HTML for each Report
        for r_id, report in scan_result.reports.items():
            safe_r = sanitize_filename(report.name)
            scoped_cfg = self.config.get_scoped_config(report.artifact_id)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            bound_m_name = bound_m.name if bound_m else report.bound_model_name

            # Report Overview index.html
            rep_overview_content = self._build_report_overview_html(report, scan_result, bound_m)
            rep_overview_path = f"reports/{safe_r}/index.html"
            documents[rep_overview_path] = layout.wrap_page(
                current_path=rep_overview_path,
                page_title=f"{report.name} - Report Overview",
                breadcrumbs=[("Workspace", "../../index.html"), ("Reports", None), (report.name, None)],
                content_html=rep_overview_content,
            )

            # Visual Pages
            if scoped_cfg.include_visual_docs and report.report_obj:
                m_dict = bound_m.model_obj.to_dict() if bound_m and bound_m.model_obj else {}
                tables_list = m_dict.get("tables", [])
                measures_list = m_dict.get("measures", [])

                for page in report.report_obj.pages:
                    clean_page = sanitize_filename(page.display_name)
                    vis_builder = HtmlVisualBuilder(
                        page=page,
                        report_model=report.report_obj,
                        config=scoped_cfg,
                        project_name=report.name,
                        model_tables=tables_list,
                        model_measures=measures_list,
                    )
                    page_content = vis_builder.build_content()
                    page_path = f"reports/{safe_r}/visuals/{clean_page}.html"

                    documents[page_path] = layout.wrap_page(
                        current_path=page_path,
                        page_title=f"{page.display_name} - Visuals",
                        breadcrumbs=[
                            ("Workspace", "../../../index.html"),
                            ("Reports", None),
                            (report.name, "../index.html"),
                            (page.display_name, None),
                        ],
                        content_html=page_content,
                    )

                    # SVG Maps
                    p_doc_builder = PageVisualDocBuilder(
                        page=page,
                        report_model=report.report_obj,
                        config=scoped_cfg,
                    )
                    svg_assets = p_doc_builder.build_svg_assets()
                    for svg_rel, svg_content in svg_assets.items():
                        documents[f"reports/{safe_r}/visuals/{svg_rel}"] = svg_content

        return documents

    def write_to_directory(
        self,
        scan_result: WorkspaceScanResult,
        output_dir: Union[str, Path],
        output_format: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Writes multi-project workspace documentation to output_dir according to output_format."""
        out_path = Path(output_dir).resolve()
        fmt = (output_format or self.config.output_format or "both").lower()
        results: Dict[str, List[str]] = {"markdown": [], "html": []}

        # 1. Markdown Generation
        if fmt in ("markdown", "both"):
            md_dir = out_path / "markdown" if fmt == "both" else out_path
            md_docs = self.generate_all_markdown_documents(scan_result)
            for rel_file, content in md_docs.items():
                f_path = md_dir / rel_file
                f_path.parent.mkdir(parents=True, exist_ok=True)
                with open(f_path, "w", encoding="utf-8") as f:
                    f.write(content)
                results["markdown"].append(str(f_path))

        # 2. HTML Generation
        if fmt in ("html", "both"):
            html_dir = out_path / "html" if fmt == "both" else out_path
            html_docs = self.generate_all_html_documents(scan_result)
            for rel_file, content in html_docs.items():
                f_path = html_dir / rel_file
                f_path.parent.mkdir(parents=True, exist_ok=True)
                with open(f_path, "w", encoding="utf-8") as f:
                    f.write(content)
                results["html"].append(str(f_path))

        return results

    def _build_workspace_index_markdown(self, scan_result: WorkspaceScanResult) -> str:
        """Builds Markdown master workspace catalog (README.md)."""
        lines = []
        workspace_name = clean_project_name(scan_result.root_path.name)
        total_tables = sum(
            len([t for t in m.tables if not self.config.get_scoped_config(m.artifact_id).is_table_excluded(t)])
            for m in scan_result.models.values()
        )
        total_measures = sum(
            len([k for k, tbl in m.measures.items() if not self.config.get_scoped_config(m.artifact_id).is_table_excluded(tbl)])
            for m in scan_result.models.values()
        )
        total_pages = sum(len(r.page_names) for r in scan_result.reports.values())

        lines.append(f"# {workspace_name} - Workspace Documentation Catalog\n")
        lines.append("## Description\n")
        lines.append(f"> Automated multi-artifact documentation for Power BI & Fabric Git Codebase `{workspace_name}`. Provides cross-artifact data lineage, semantic models inventory, and report presentation catalogs.\n")

        # KPI Summary Table
        lines.append("## Workspace Overview\n")
        lines.append("| Metric | Count | Details |")
        lines.append("| --- | --- | --- |")
        lines.append(f"| **Semantic Models** | `{len(scan_result.models)}` | Tabular datasets |")
        lines.append(f"| **Reports & Dashboards** | `{len(scan_result.reports)}` | PBIR / Legacy presentation items |")
        lines.append(f"| **Physical Tables** | `{total_tables}` | Tables across all local models |")
        lines.append(f"| **Business Measures** | `{total_measures}` | DAX calculations |")
        lines.append(f"| **Report Pages** | `{total_pages}` | Visual canvas dashboards |\n")

        # Lineage Matrix
        lines.append("## Data Lineage & Dependency Matrix\n")
        lines.append("| Report | Format | Bound Model | Scope | Evaluated Measures | Pages | Documentation |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r_id, report in sorted(scan_result.reports.items(), key=lambda x: x[1].name):
            safe_r = sanitize_filename(report.name)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            if bound_m:
                safe_bm = sanitize_filename(bound_m.name)
                m_str = f"[{bound_m.name}](models/{safe_bm}/README.md)"
                scope_str = "Local Workspace"
            elif report.bound_model_name:
                m_str = f"`{report.bound_model_name}`"
                scope_str = "Remote Fabric / PBI Service"
            else:
                m_str = "—"
                scope_str = "Standalone / Unknown"

            pages_count = len(report.page_names)
            measures_count = len(bound_m.measures) if bound_m else "—"
            lines.append(f"| **{report.name}** | `{report.report_format}` | {m_str} | {scope_str} | {measures_count} | {pages_count} | [Explore](reports/{safe_r}/README.md) |")
        lines.append("")

        # Models Inventory
        lines.append("## Semantic Models Inventory\n")
        lines.append("| Semantic Model | Format | Tables | Measures | Bound Reports | Documentation |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for m_id, model in sorted(scan_result.models.items(), key=lambda x: x[1].name):
            safe_m = sanitize_filename(model.name)
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            t_cnt = len([t for t in model.tables if not scoped_cfg.is_table_excluded(t)])
            m_cnt = len([k for k, tbl in model.measures.items() if not scoped_cfg.is_table_excluded(tbl)])
            rep_links = []
            for r_art_id in model.bound_reports:
                rep = scan_result.get_report(r_art_id)
                if rep:
                    safe_rep = sanitize_filename(rep.name)
                    rep_links.append(f"[{rep.name}](reports/{safe_rep}/README.md)")
            reps_str = ", ".join(rep_links) if rep_links else "None (Standalone)"
            lines.append(f"| **{model.name}** | `{model.model_format}` | {t_cnt} | {m_cnt} | {reps_str} | [Open Catalog](models/{safe_m}/README.md) |")
        lines.append("")

        # Reports Inventory
        lines.append("## Reports Inventory\n")
        lines.append("| Report | Format | Pages | Bound Dataset | Link |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r_id, report in sorted(scan_result.reports.items(), key=lambda x: x[1].name):
            safe_r = sanitize_filename(report.name)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            ds_name = bound_m.name if bound_m else (report.bound_model_name or "Unknown")
            lines.append(f"| **{report.name}** | `{report.report_format}` | {len(report.page_names)} | `{ds_name}` | [Open Report](reports/{safe_r}/README.md) |")

        return "\n".join(lines) + "\n"

    def _build_workspace_index_html(self, scan_result: WorkspaceScanResult) -> str:
        """Builds HTML master workspace dashboard content (index.html)."""
        workspace_name = clean_project_name(scan_result.root_path.name)
        total_tables = sum(
            len([t for t in m.tables if not self.config.get_scoped_config(m.artifact_id).is_table_excluded(t)])
            for m in scan_result.models.values()
        )
        total_measures = sum(
            len([k for k, tbl in m.measures.items() if not self.config.get_scoped_config(m.artifact_id).is_table_excluded(tbl)])
            for m in scan_result.models.values()
        )
        total_pages = sum(len(r.page_names) for r in scan_result.reports.values())

        # Header Hero
        html_out = f"""
      <div class="wiki-header">
        <div class="wiki-title-group">
          <div class="wiki-title-row">
            <h1 class="wiki-title">{escape(workspace_name)}</h1>
            <span class="badge badge-type">PBIP Enterprise Workspace</span>
          </div>
          <p class="wiki-subtitle">Master Unified Analytics Catalog & Cross-Artifact Lineage Matrix</p>
        </div>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Semantic Models</div>
          <div class="kpi-value">{len(scan_result.models)}</div>
          <div class="kpi-sub">Tabular Data Models</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Reports & Dashboards</div>
          <div class="kpi-value">{len(scan_result.reports)}</div>
          <div class="kpi-sub">Presentation Items</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Physical Tables</div>
          <div class="kpi-value">{total_tables}</div>
          <div class="kpi-sub">Across All Datasets</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Business Measures</div>
          <div class="kpi-value">{total_measures}</div>
          <div class="kpi-sub">DAX Calculations</div>
        </div>
      </div>

      <!-- In-Page Quick Navigation (Zero-JS) -->
      <nav class="page-quicknav" aria-label="Catalog Sections">
        <span class="page-quicknav-label">Sections:</span>
        <a href="#tab-desc" class="page-quicknav-link">Description</a>
        <span class="page-quicknav-sep">&bull;</span>
        <a href="#tab-lineage" class="page-quicknav-link">Data Lineage Matrix</a>
        <span class="page-quicknav-sep">&bull;</span>
        <a href="#tab-models" class="page-quicknav-link">Semantic Models</a>
        <span class="page-quicknav-sep">&bull;</span>
        <a href="#tab-reports" class="page-quicknav-link">Reports & Dashboards</a>
      </nav>

      <div id="tab-desc" class="content-section">
        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          <p class="description-text">Unified master analytics catalog and cross-artifact lineage matrix for workspace <strong>{escape(workspace_name)}</strong>. Provides central access to all published semantic models, tabular datasets, Power BI reports, and visual metrics.</p>
        </div>
      </div>

      <div id="tab-lineage" class="content-section">
        <h2 class="section-title">Data Lineage & Dependency Matrix</h2>
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Report Name</th>
                <th>Format</th>
                <th>Bound Semantic Model</th>
                <th>Binding Scope</th>
                <th>Pages</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
"""
        for r_id, report in sorted(scan_result.reports.items(), key=lambda x: x[1].name):
            safe_r = sanitize_filename(report.name)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            if bound_m:
                safe_bm = sanitize_filename(bound_m.name)
                m_link = f'<a href="models/{safe_bm}/index.html"><strong>{escape(bound_m.name)}</strong></a>'
                scope_badge = '<span class="badge badge-status-active">Local Model</span>'
            elif report.bound_model_name:
                m_link = f'<code>{escape(report.bound_model_name)}</code>'
                scope_badge = '<span class="badge badge-dim">Remote Fabric / Service</span>'
            else:
                m_link = '<em>Unknown</em>'
                scope_badge = '<span class="badge badge-dim">Standalone</span>'

            html_out += f"""              <tr>
                <td><strong><a href="reports/{safe_r}/index.html">{escape(report.name)}</a></strong></td>
                <td><code>{escape(report.report_format)}</code></td>
                <td>{m_link}</td>
                <td>{scope_badge}</td>
                <td>{len(report.page_names)}</td>
                <td><a href="reports/{safe_r}/index.html" class="badge badge-type">Open Report</a></td>
              </tr>
"""
        html_out += """            </tbody>
          </table>
        </div>
      </div>

      <div id="tab-models" class="content-section">
        <h2 class="section-title">Semantic Models Inventory</h2>
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Model Name</th>
                <th>Format</th>
                <th>Tables</th>
                <th>Measures</th>
                <th>Dependent Reports</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
"""
        for m_id, model in sorted(scan_result.models.items(), key=lambda x: x[1].name):
            safe_m = sanitize_filename(model.name)
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            t_cnt = len([t for t in model.tables if not scoped_cfg.is_table_excluded(t)])
            m_cnt = len([k for k, tbl in model.measures.items() if not scoped_cfg.is_table_excluded(tbl)])
            rep_links = []
            for r_art_id in model.bound_reports:
                rep = scan_result.get_report(r_art_id)
                if rep:
                    safe_rep = sanitize_filename(rep.name)
                    rep_links.append(f'<a href="reports/{safe_rep}/index.html">{escape(rep.name)}</a>')
            rep_str = ", ".join(rep_links) if rep_links else '<span style="color: var(--text-muted);">None</span>'

            html_out += f"""              <tr>
                <td><strong><a href="models/{safe_m}/index.html">{escape(model.name)}</a></strong></td>
                <td><code>{escape(model.model_format)}</code></td>
                <td>{t_cnt}</td>
                <td>{m_cnt}</td>
                <td>{rep_str}</td>
                <td><a href="models/{safe_m}/index.html" class="badge badge-type">Open Model</a></td>
              </tr>
"""
        html_out += """            </tbody>
          </table>
        </div>
      </div>

      <div id="tab-reports" class="content-section">
        <h2 class="section-title">Reports & Dashboards Inventory</h2>
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Report Name</th>
                <th>Format</th>
                <th>Pages</th>
                <th>Bound Model</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
"""
        for r_id, report in sorted(scan_result.reports.items(), key=lambda x: x[1].name):
            safe_r = sanitize_filename(report.name)
            bound_m = scan_result.get_bound_model_for_report(r_id)
            ds_name = bound_m.name if bound_m else (report.bound_model_name or "Unknown")

            html_out += f"""              <tr>
                <td><strong><a href="reports/{safe_r}/index.html">{escape(report.name)}</a></strong></td>
                <td><code>{escape(report.report_format)}</code></td>
                <td>{len(report.page_names)}</td>
                <td><code>{escape(ds_name)}</code></td>
                <td><a href="reports/{safe_r}/index.html" class="badge badge-type">Explore</a></td>
              </tr>
"""
        html_out += """            </tbody>
          </table>
        </div>
      </div>
"""
        return html_out

    def _build_report_overview_markdown(
        self,
        report: DiscoveredReport,
        scan_result: WorkspaceScanResult,
        bound_m: Optional[DiscoveredModel],
    ) -> str:
        """Builds Markdown overview for an individual report (reports/<ReportName>/README.md)."""
        lines = []
        lines.append(f"# Report: {report.name}\n")
        lines.append("## Description\n")
        lines.append(f"> Power BI presentation and visual analytics catalog for report `{report.name}`. Documents canvas pages, layout structure, and underlying semantic model bindings.\n")

        # Identity Table
        lines.append("## Report Identity & Dataset Binding\n")
        lines.append("| Attribute | Value |")
        lines.append("| --- | --- |")
        lines.append(f"| **Report Name** | `{report.name}` |")
        lines.append(f"| **Report Format** | `{report.report_format}` |")
        if bound_m:
            safe_bm = sanitize_filename(bound_m.name)
            lines.append(f"| **Bound Semantic Model** | [{bound_m.name}](../../models/{safe_bm}/README.md) *(Local Workspace)* |")
        elif report.bound_model_name:
            lines.append(f"| **Bound Semantic Model** | `{report.bound_model_name}` *(Remote Fabric / PBI Service)* |")
        else:
            lines.append(f"| **Bound Semantic Model** | *Standalone / Unknown* |")
        lines.append(f"| **Total Pages** | `{len(report.page_names)}` |\n")

        # Pages Catalog
        lines.append("## Report Canvas Pages\n")
        lines.append("| # | Page Name | Visuals Catalog |")
        lines.append("| --- | --- | --- |")
        for idx, p_name in enumerate(report.page_names, start=1):
            clean_p = sanitize_filename(p_name)
            lines.append(f"| {idx} | **{p_name}** | [View Page Visuals & Metrics](visuals/{clean_p}.md) |")

        return "\n".join(lines) + "\n"

    def _build_report_overview_html(
        self,
        report: DiscoveredReport,
        scan_result: WorkspaceScanResult,
        bound_m: Optional[DiscoveredModel],
    ) -> str:
        """Builds HTML overview content for an individual report (reports/<ReportName>/index.html)."""
        if bound_m:
            safe_bm = sanitize_filename(bound_m.name)
            model_badge = f'<a href="../../models/{safe_bm}/index.html" class="badge badge-status-active">Bound Model: {escape(bound_m.name)}</a>'
        elif report.bound_model_name:
            model_badge = f'<span class="badge badge-dim">Remote Model: {escape(report.bound_model_name)}</span>'
        else:
            model_badge = '<span class="badge badge-dim">Standalone Report</span>'

        html_out = f"""
      <div class="wiki-header">
        <div class="wiki-title-group">
          <div class="wiki-title-row">
            <h1 class="wiki-title">{escape(report.name)}</h1>
            <span class="badge badge-type">Report ({escape(report.report_format)})</span>
            {model_badge}
          </div>
          <p class="wiki-subtitle">Power BI Presentation & Visual Analytics Catalog</p>
        </div>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Report Pages</div>
          <div class="kpi-value">{len(report.page_names)}</div>
          <div class="kpi-sub">Interactive Canvas Views</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Bound Model</div>
          <div class="kpi-value" style="font-size: 1.25rem;">{escape(bound_m.name if bound_m else (report.bound_model_name or 'None'))}</div>
          <div class="kpi-sub">Underlying Tabular Dataset</div>
        </div>
      </div>

      <div class="content-card description-card" style="margin-top: 1.5rem;">
        <h3 class="content-card-title">Description</h3>
        <p class="description-text">Power BI presentation and visual analytics catalog for report <strong>{escape(report.name)}</strong>. Documents canvas pages, layout structure, and underlying semantic model bindings.</p>
      </div>

      <div class="card" style="margin-top: 1.5rem;">
        <div class="card-header">
          <h2 class="card-title">Pages & Dashboards Catalog</h2>
        </div>
        <div class="card-body">
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Page Display Name</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
"""
        for idx, p_name in enumerate(report.page_names, start=1):
            clean_p = sanitize_filename(p_name)
            html_out += f"""                <tr>
                  <td>#{idx}</td>
                  <td><strong><a href="visuals/{clean_p}.html">{escape(p_name)}</a></strong></td>
                  <td><a href="visuals/{clean_p}.html" class="badge badge-type">View Visuals & Specs</a></td>
                </tr>
"""
        html_out += """              </tbody>
            </table>
          </div>
        </div>
      </div>
"""
        return html_out
