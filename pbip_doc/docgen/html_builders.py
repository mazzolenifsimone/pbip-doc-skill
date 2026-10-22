"""
Modular HTML Document Builders for Tables, Measures, Master Index, and Report Visuals.
Renders executive C-level interactive HTML5 components with data dictionary filters,
tabs, copy buttons, KPI metric cards, and responsive layouts.
100% Vanilla Python standard library.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
import html

from .config import DocGenConfig
from .utils import sanitize_filename, clean_project_name
from .html_layout import get_relative_root, get_table_role_badge_class, get_table_role_short
from ..report_schema import PBIPReportModel, VisualDefinition
from ..dax_formatter import format_dax
from ..m_formatter import format_m


def escape(val: Any) -> str:
    """Safe HTML escaping for strings and values."""
    if val is None:
        return ""
    return html.escape(str(val))


class HtmlIndexBuilder:
    """Builds the Master Catalog & Model Architecture dashboard (index.html)."""

    def __init__(
        self,
        data: Dict[str, Any],
        config: DocGenConfig,
        report_model: Optional[PBIPReportModel] = None,
        project_name: Optional[str] = None,
    ):
        self.data = data
        self.config = config
        self.report = report_model
        self.project_name = clean_project_name(
            project_name or config.project_name or data.get("project_name") or data.get("model_name") or "PBIP"
        )

    def build_content(self) -> str:
        tables = [t for t in self.data.get("tables", []) if self.config.is_table_published(t)]
        
        # Robust measure collection: from top-level measures or gathered from tables
        measures = [m for m in self.data.get("measures", []) if self.config.is_measure_published(m)]
        if not measures:
            for t in tables:
                for m in t.get("measures", []):
                    if not m.get("table"):
                        m["table"] = t.get("name")
                    if self.config.is_measure_published(m):
                        measures.append(m)

        total_cols = sum(len(t.get("columns", [])) for t in tables)
        total_pages = len(self.report.pages) if self.report and self.report.pages else 0
        
        # Additional catalog items
        expr_list = self.data.get("expressions") or self.data.get("shared_queries") or []
        funcs = self.data.get("functions", [])
        data_sources = self.data.get("data_sources_summary", [])
        relationships = self.data.get("relationships", [])

        # Count tables by role
        fact_count = len([t for t in tables if (t.get("role") or "").upper() in ("FACT", "FACT_TABLE")])
        dim_count = len([t for t in tables if (t.get("role") or "").upper() in ("DIMENSION", "DIM", "DATE_DIMENSION", "DATE")])

        # KPI Summary Cards (Executive Clean Style)
        kpis_html = f"""
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Tables</div>
          <div class="kpi-value">{len(tables)}</div>
          <div class="kpi-sub">{fact_count} Fact, {dim_count} Dimension</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Measures</div>
          <div class="kpi-value">{len(measures)}</div>
          <div class="kpi-sub">DAX Business Calculations</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Physical Columns</div>
          <div class="kpi-value">{total_cols}</div>
          <div class="kpi-sub">Data Model Attributes</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Report Pages</div>
          <div class="kpi-value">{total_pages}</div>
          <div class="kpi-sub">Interactive Dashboards</div>
        </div>
      </div>
"""

        # Tab 1: Tables Catalog rows
        tables_rows = []
        for t in sorted(tables, key=lambda x: x.get("name", "")):
            t_name = t.get("name", "Table")
            clean_name = sanitize_filename(t_name)
            t_url = f"{self.config.tables_subdir.strip('/\\\\')}/{clean_name}.html"
            role = t.get("role", "DIM")
            role_class = get_table_role_badge_class(role)
            role_label = get_table_role_short(role)

            cols_cnt = len(t.get("columns", []))
            meas_cnt = len([m for m in measures if m.get("table") == t_name])
            storage = t.get("storage_mode", "Import")

            # Check refresh status
            inc = t.get("incremental_refresh_policy")
            has_inc_enabled = bool(inc and inc.get("is_enabled"))
            refresh_badge = "Incremental" if has_inc_enabled else "Full Refresh"
            refresh_badge_class = "badge-status-active" if has_inc_enabled else "badge-dim"

            tables_rows.append(f"""          <tr>
            <td><strong><a href="{t_url}">{escape(t_name)}</a></strong></td>
            <td><span class="badge {role_class}">{escape(role_label)}</span></td>
            <td><code>{escape(storage)}</code></td>
            <td>{cols_cnt}</td>
            <td>{meas_cnt}</td>
            <td><span class="badge {refresh_badge_class}">{refresh_badge}</span></td>
            <td>{escape(t.get('description', '') or '—')}</td>
          </tr>""")

        # Tab 2: Measures Inventory rows
        measures_rows = []
        for m in sorted(measures, key=lambda x: (x.get("table", ""), x.get("name", ""))):
            m_name = m.get("name", "Measure")
            m_tbl = m.get("table", "Model")
            clean_tbl = sanitize_filename(m_tbl)
            clean_m = sanitize_filename(m_name)
            m_url = f"{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_m}.html"
            depth = m.get("calculation_depth", 0)

            measures_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(m_name)}]</a></strong></td>
            <td><a href="{self.config.tables_subdir.strip('/\\\\')}/{clean_tbl}.html">{escape(m_tbl)}</a></td>
            <td><span class="badge badge-type">Depth {depth}</span></td>
            <td>{escape(m.get('display_folder', '') or '—')}</td>
            <td><code>{escape(m.get('format_string', '') or '—')}</code></td>
            <td>{escape(m.get('description', '') or '—')}</td>
          </tr>""")

        # Tab 3: Report Pages rows
        pages_rows = []
        if self.report and self.report.pages:
            for p in self.report.pages:
                clean_p = sanitize_filename(p.display_name)
                p_url = f"{self.config.visuals_subdir.strip('/\\\\')}/{clean_p}.html"
                v_cnt = len([v for v in p.visuals if v.is_dynamic])
                pages_rows.append(f"""          <tr>
            <td><strong><a href="{p_url}">{escape(p.display_name)}</a></strong></td>
            <td>#{p.page_number}</td>
            <td><code>{p.width}x{p.height}</code></td>
            <td>{v_cnt} dynamic visuals</td>
            <td><span class="badge badge-dim">{'Hidden' if p.is_hidden else 'Visible'}</span></td>
          </tr>""")

        # Tab 4: Shared Expressions rows
        expr_rows = []
        for e in expr_list:
            q_name = e.get("query_name") or "Expression"
            clean_q = sanitize_filename(q_name)
            e_url = f"{self.config.expressions_subdir.strip('/\\\\')}/{clean_q}.html" if self.config.include_expression_docs else "#"
            target_t = e.get("target_table") or "—"
            is_staging = "Staging Query" if e.get("is_staging") else "Model Entity"
            deps = ", ".join(e.get("direct_dependencies", [])) or "—"

            expr_rows.append(f"""          <tr>
            <td><strong><a href="{e_url}">{escape(q_name)}</a></strong></td>
            <td>{escape(target_t)}</td>
            <td><span class="badge badge-dim">{is_staging}</span></td>
            <td><code>{escape(deps)}</code></td>
          </tr>""")

        # Tab 5: DAX Functions (UDF) rows
        func_rows = []
        for fn in funcs:
            f_name = fn.get("name") or "Function"
            clean_f = sanitize_filename(f_name)
            f_url = f"{self.config.functions_subdir.strip('/\\\\')}/{clean_f}.html"
            params_cnt = len(fn.get("parameters", []))
            ret_type = fn.get("return_type") or "Variant"
            func_rows.append(f"""          <tr>
            <td><strong><a href="{f_url}">{escape(f_name)}</a></strong></td>
            <td><code>{escape(ret_type)}</code></td>
            <td>{params_cnt} parameters</td>
            <td>{escape(fn.get('description', '') or '—')}</td>
          </tr>""")

        # Tab 6: Physical Data Sources rows
        source_rows = []
        for src in data_sources:
            stype = src.get("source_type") or "Connector"
            conn = src.get("connection_string") or "—"
            server = src.get("server") or "—"
            db = src.get("database") or "—"
            source_rows.append(f"""          <tr>
            <td><span class="badge badge-type">{escape(stype)}</span></td>
            <td><code>{escape(conn)}</code></td>
            <td>{escape(server)}</td>
            <td>{escape(db)}</td>
          </tr>""")

        # Tab 7: Relationships Summary rows
        rel_rows = []
        for r in relationships:
            from_str = f"{r.get('from_table')}[{r.get('from_column')}]"
            to_str = f"{r.get('to_table')}[{r.get('to_column')}]"
            card = r.get("cardinality") or "1:N"
            cross_dir = r.get("cross_filtering_behavior") or "Single"
            status = "Active" if r.get("is_active", True) else "Inactive"
            status_class = "badge-status-active" if status == "Active" else "badge-status-inactive"
            rel_rows.append(f"""          <tr>
            <td><code>{escape(from_str)}</code></td>
            <td><code>{escape(to_str)}</code></td>
            <td><span class="badge badge-dim">{escape(card)}</span></td>
            <td>{escape(cross_dir)}</td>
            <td><span class="badge {status_class}">{status}</span></td>
          </tr>""")

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>{escape(self.project_name)}</span>
          <span class="badge badge-role-fact">Knowledge Base</span>
        </h1>
        <p class="page-subtitle">Centralized technical documentation, data dictionary, and metric dependency catalog.</p>
      </div>

{kpis_html}

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-tables">Tables ({len(tables)})</button>
          <button class="tab-btn" data-tab-target="tab-measures">Measures ({len(measures)})</button>
          {'<button class="tab-btn" data-tab-target="tab-reports">Report Pages (' + str(len(pages_rows)) + ')</button>' if pages_rows else ''}
          {'<button class="tab-btn" data-tab-target="tab-expressions">Expressions (' + str(len(expr_rows)) + ')</button>' if expr_rows else ''}
          {'<button class="tab-btn" data-tab-target="tab-functions">Functions (' + str(len(func_rows)) + ')</button>' if func_rows else ''}
          {'<button class="tab-btn" data-tab-target="tab-sources">Data Sources (' + str(len(source_rows)) + ')</button>' if source_rows else ''}
          <button class="tab-btn" data-tab-target="tab-architecture">Model Architecture</button>
        </div>

        <div id="tab-tables" class="tab-content active">
          <div class="content-card">
            <h3 class="content-card-title">Published Data Model Tables</h3>
            <div class="table-toolbar">
              <input type="text" class="table-filter-input" data-target-table="index-tables-table" placeholder="Filter tables by name or role...">
            </div>
            <div class="table-responsive">
              <table class="data-table" id="index-tables-table">
                <thead>
                  <tr>
                    <th>Table Name</th>
                    <th>Star Schema Role</th>
                    <th>Storage Mode</th>
                    <th>Columns</th>
                    <th>Measures</th>
                    <th>Refresh Policy</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(tables_rows) if tables_rows else '<tr><td colspan="7"><em>No tables cataloged.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="tab-measures" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Cataloged DAX Measures</h3>
            <div class="table-toolbar">
              <input type="text" class="table-filter-input" data-target-table="index-measures-table" placeholder="Filter measures by name or table...">
            </div>
            <div class="table-responsive">
              <table class="data-table" id="index-measures-table">
                <thead>
                  <tr>
                    <th>Measure Name</th>
                    <th>Host Table</th>
                    <th>Calculation Depth</th>
                    <th>Display Folder</th>
                    <th>Format String</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(measures_rows) if measures_rows else '<tr><td colspan="6"><em>No measures cataloged.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {f'''<div id="tab-reports" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Interactive Report Pages</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Report Page</th>
                    <th>Order</th>
                    <th>Dimensions</th>
                    <th>Visuals</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(pages_rows)}
                </tbody>
              </table>
            </div>
          </div>
        </div>''' if pages_rows else ''}

        {f'''<div id="tab-expressions" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Power Query Expressions & Queries</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Query Name</th>
                    <th>Target Table</th>
                    <th>Pipeline Role</th>
                    <th>Direct Dependencies</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(expr_rows)}
                </tbody>
              </table>
            </div>
          </div>
        </div>''' if expr_rows else ''}

        {f'''<div id="tab-functions" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">DAX Custom Functions (UDFs)</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Function Name</th>
                    <th>Return Type</th>
                    <th>Parameters</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(func_rows)}
                </tbody>
              </table>
            </div>
          </div>
        </div>''' if func_rows else ''}

        {f'''<div id="tab-sources" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Physical Data Sources</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Connector Type</th>
                    <th>Connection / Endpoint</th>
                    <th>Server</th>
                    <th>Database</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(source_rows)}
                </tbody>
              </table>
            </div>
          </div>
        </div>''' if source_rows else ''}

        <div id="tab-architecture" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Star Schema & Topological Summary</h3>
            <p style="color: var(--text-muted); margin-bottom: 1rem;">
              The semantic model contains <strong>{len(tables)}</strong> tables interconnected via 
              <strong>{len(relationships)}</strong> logical relationships.
            </p>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>From (Many Side)</th>
                    <th>To (One Side)</th>
                    <th>Cardinality</th>
                    <th>Cross-Filtering</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(rel_rows) if rel_rows else '<tr><td colspan="5"><em>No active relationships defined in model.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
"""


class HtmlTableBuilder:
    """Builds individual Table documentation page (tables/<TableName>.html)."""

    def __init__(
        self,
        table_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.table = table_data
        self.model = full_model
        self.config = config
        self.project_name = project_name or full_model.get("project_name") or "PBIP"
        self.name = table_data.get("name", "UnnamedTable")
        self.role = table_data.get("role", "UNKNOWN")
        self.classification = table_data.get("classification_reasoning", {})
        self.columns = table_data.get("columns", [])
        
        # Hosted measures
        self.measures = [m for m in full_model.get("measures", []) if m.get("table") == self.name]
        if not self.measures:
            self.measures = [m for m in table_data.get("measures", [])]

        self.snowflake_paths = table_data.get("snowflake_paths", [])

    def build_content(self) -> str:
        rel_root = ".."
        role_class = get_table_role_badge_class(self.role)
        role_label = get_table_role_short(self.role)

        # Tab 1: Columns & Calculated Columns Separation
        calc_cols = []
        col_rows = []
        for col in self.columns:
            c_name = col.get("name", "col")
            c_type = col.get("data_type", "String")
            c_fmt = col.get("format_string") or "—"
            c_desc = col.get("description") or "—"

            is_calc = col.get("is_calculated") or bool(col.get("expression"))
            if is_calc:
                calc_cols.append(col)
                slug = sanitize_filename(c_name)
                origin_badge = f'<a href="#calc-col-{slug}" class="badge badge-calc link-to-tab" data-tab="tab-calc-cols" title="Click to view DAX formula in Calculated Columns tab">Calculated</a>'
            elif col.get("is_key"):
                origin_badge = '<span class="badge badge-key">Key</span> <span class="badge badge-imported">Imported</span>'
            else:
                origin_badge = '<span class="badge badge-imported">Imported</span>'

            col_rows.append(f"""          <tr>
            <td><strong>`{escape(c_name)}`</strong></td>
            <td><span class="badge badge-type">{escape(c_type)}</span></td>
            <td>{origin_badge}</td>
            <td><code>{escape(c_fmt)}</code></td>
            <td>{escape(c_desc)}</td>
          </tr>""")

        # Tab 2: Calculated Columns Cards
        calc_col_cards = []
        for cc in calc_cols:
            c_name = cc.get("name", "col")
            slug = sanitize_filename(c_name)
            c_type = cc.get("data_type", "String")
            c_fmt = cc.get("format_string") or ""
            c_desc = cc.get("description") or ""
            c_expr = cc.get("expression") or ""
            formatted_dax = format_dax(
                c_expr,
                name=c_name,
                entity_type="calculated_column",
                table_name=self.name,
            ) if c_expr else "-- No DAX expression provided"

            calc_col_cards.append(f"""
        <div id="calc-col-{slug}" class="calc-col-card">
          <div class="calc-col-header">
            <div class="calc-col-title-group">
              <span class="calc-col-name">`{escape(c_name)}`</span>
              <span class="badge badge-type">{escape(c_type)}</span>
              {f'<span class="badge badge-dim">Format: {escape(c_fmt)}</span>' if c_fmt else ''}
            </div>
            <button class="copy-btn" data-copy-target="code-calc-col-{slug}">Copy</button>
          </div>
          {f'<p class="calc-col-desc">{escape(c_desc)}</p>' if c_desc else ''}
          <div class="code-container">
            <pre><code id="code-calc-col-{slug}">{escape(formatted_dax)}</code></pre>
          </div>
        </div>
""")

        # Tab 3: Direct Relationships
        direct_rels = [
            r for r in self.model.get("relationships", [])
            if (r.get("from_table") == self.name or r.get("to_table") == self.name)
            and not self.config.is_table_excluded(r.get("from_table"))
            and not self.config.is_table_excluded(r.get("to_table"))
        ]
        rel_rows = []
        for r in direct_rels:
            is_from = (r.get("from_table") == self.name)
            target_tbl = r.get("to_table") if is_from else r.get("from_table")
            target_col = r.get("to_column") if is_from else r.get("from_column")
            local_col = r.get("from_column") if is_from else r.get("to_column")

            clean_target = sanitize_filename(target_tbl)
            target_url = f"{clean_target}.html"
            card = r.get("cardinality", "1:N")
            cross = r.get("cross_filtering_behavior", "Single")
            status = "Active" if r.get("is_active", True) else "Inactive"
            status_class = "badge-status-active" if status == "Active" else "badge-status-inactive"

            rel_rows.append(f"""          <tr>
            <td><strong><a href="{target_url}">{escape(target_tbl)}</a></strong></td>
            <td><code>[{escape(local_col)}]</code> ➔ <code>[{escape(target_col)}]</code></td>
            <td><span class="badge badge-dim">{escape(card)}</span></td>
            <td>{escape(cross)}</td>
            <td><span class="badge {status_class}">{status}</span></td>
          </tr>""")

        # Snowflake Outrigger Paths
        snowflake_html = []
        if self.snowflake_paths:
            for p in self.snowflake_paths:
                path_nodes = p.get("path", [])
                hops = p.get("hops", 1)
                join_keys = p.get("join_keys", [])
                path_str = " ➔ ".join(f"`{escape(n)}`" for n in path_nodes)
                keys_str = ", ".join(f"<code>{escape(jk.get('from'))}</code> ➔ <code>{escape(jk.get('to'))}</code>" for jk in join_keys)
                snowflake_html.append(f"<li><strong>Path ({hops} hops)</strong>: {path_str}<br><span style='color: var(--text-muted); font-size: 0.8rem;'>Join Keys: {keys_str}</span></li>")

        # Tab 4: Hosted Measures
        meas_rows = []
        for m in sorted(self.measures, key=lambda x: x.get("name", "")):
            m_name = m.get("name", "Measure")
            clean_m = sanitize_filename(m_name)
            clean_tbl = sanitize_filename(self.name)
            m_url = f"{rel_root}/{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_m}.html"
            dax = m.get("dax_expression", "")
            dax_preview = dax[:120] + ("..." if len(dax) > 120 else "")

            meas_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(m_name)}]</a></strong></td>
            <td><span class="badge badge-type">Depth {m.get('calculation_depth', 0)}</span></td>
            <td><code>{escape(dax_preview)}</code></td>
            <td>{escape(m.get('description', '') or '—')}</td>
          </tr>""")

        # Tab 5: M Lineage / Code
        lineage_node = self.table.get("power_query_lineage") or self.table.get("lineage_node") or {}
        raw_m = (
            lineage_node.get("full_m_expression")
            or self.table.get("power_query_expression")
            or self.table.get("m_code")
            or ""
        )
        m_code = format_m(raw_m) if raw_m else ""
        m_steps = lineage_node.get("steps", []) if lineage_node else []
        m_steps_rows = []
        for idx, st in enumerate(m_steps, start=1):
            s_name = st.get("step_name", f"Step_{idx}")
            op = st.get("operation", "Transform")
            refs = ", ".join(f"`{r}`" for r in st.get("referenced_queries", [])) or "—"
            m_steps_rows.append(f"""          <tr>
            <td><code>#{idx} {escape(s_name)}</code></td>
            <td><span class="badge badge-dim">{escape(op)}</span></td>
            <td>{escape(refs)}</td>
          </tr>""")

        m_html = f"""
        {('<div class="table-responsive" style="margin-bottom: 1.25rem;"><table class="data-table"><thead><tr><th>Step</th><th>Operation</th><th>Referenced Queries</th></tr></thead><tbody>' + chr(10).join(m_steps_rows) + '</tbody></table></div>') if m_steps_rows else ''}
        <div class="code-container">
          <div class="code-header">
            <span>Power Query (M) Script</span>
            <button class="copy-btn" data-copy-target="m-script-code">Copy</button>
          </div>
          <pre><code id="m-script-code">{escape(m_code)}</code></pre>
        </div>
""" if m_code else "<p style='color: var(--text-muted);'><em>No Power Query M transformation detected (DirectQuery or Calculated table).</em></p>"

        # Tab 6: Technical Details & Refresh Specs
        inc = self.table.get("incremental_refresh_policy") or {}
        has_inc = bool(inc.get("is_enabled"))
        criteria_list = self.classification.get("criteria_matched", [])

        # KPIs
        kpis_html = f"""
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Role</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><span class="badge {role_class}">{escape(role_label)}</span></div>
          <div class="kpi-sub">Star Schema Role</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Columns</div>
          <div class="kpi-value">{len(self.columns)}</div>
          <div class="kpi-sub">{len(calc_cols)} Calculated, {len(self.columns) - len(calc_cols)} Imported</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Host Measures</div>
          <div class="kpi-value">{len(self.measures)}</div>
          <div class="kpi-sub">Formulas Hosted</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Storage</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><code>{escape(self.table.get('storage_mode', 'Import'))}</code></div>
          <div class="kpi-sub">Partition Strategy</div>
        </div>
      </div>
"""

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>Table: {escape(self.name)}</span>
          <span class="badge {role_class}">{escape(role_label)}</span>
        </h1>
        <p class="page-subtitle">{escape(self.table.get('description', '') or 'Semantic model table definition and data dictionary.')}</p>
      </div>

{kpis_html}

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-cols">Data Dictionary ({len(self.columns)})</button>
          {'<button class="tab-btn" data-tab-target="tab-calc-cols">Calculated Columns (' + str(len(calc_cols)) + ')</button>' if calc_cols else ''}
          <button class="tab-btn" data-tab-target="tab-rels">Relationships ({len(direct_rels)})</button>
          <button class="tab-btn" data-tab-target="tab-meas">Measures ({len(self.measures)})</button>
          <button class="tab-btn" data-tab-target="tab-m">Power Query Lineage</button>
          <button class="tab-btn" data-tab-target="tab-tech">Technical Details</button>
        </div>

        <div id="tab-cols" class="tab-content active">
          <div class="table-toolbar">
            <input type="text" class="table-filter-input" data-target-table="table-columns-table" placeholder="Filter columns by name or type...">
          </div>
          <div class="table-responsive">
            <table class="data-table" id="table-columns-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Data Type</th>
                  <th>Type / Origin</th>
                  <th>Format</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(col_rows) if col_rows else '<tr><td colspan="5"><em>No columns defined.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>

        {f'''<div id="tab-calc-cols" class="tab-content">
          <div style="margin-bottom: 1rem; color: var(--text-muted); font-size: 0.85rem;">
            Calculated columns evaluated via DAX expressions inside this table container:
          </div>
{chr(10).join(calc_col_cards)}
        </div>''' if calc_cols else ''}

        <div id="tab-rels" class="tab-content">
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Target Table</th>
                  <th>Key Mapping</th>
                  <th>Cardinality</th>
                  <th>Cross Filter</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rel_rows) if rel_rows else '<tr><td colspan="5"><em>No direct active relationships for this table.</em></td></tr>'}
              </tbody>
            </table>
          </div>
          {('<div class="content-card" style="margin-top: 1.25rem;"><h4 class="content-card-title">Transitive Snowflake Outriggers</h4><ul class="spec-list">' + chr(10).join(snowflake_html) + '</ul></div>') if snowflake_html else ''}
        </div>

        <div id="tab-meas" class="tab-content">
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Calculation Depth</th>
                  <th>DAX Preview</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(meas_rows) if meas_rows else '<tr><td colspan="4"><em>No measures hosted in this table.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>

        <div id="tab-m" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Staging & ETL Transformation</h3>
{m_html}
          </div>
        </div>

        <div id="tab-tech" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Star Schema Classification Analysis</h3>
            <p style="margin-bottom: 0.75rem;"><strong>Assigned Role</strong>: <span class="badge {role_class}">{escape(self.role)}</span> (Confidence: {self.classification.get('confidence_score', 1.0):.0%})</p>
            <div style="font-size: 0.825rem; color: var(--text-muted); margin-bottom: 0.5rem;">Criteria Matched:</div>
            <ul class="spec-list">
              {chr(10).join('<li>• ' + escape(c) + '</li>' for c in criteria_list) if criteria_list else '<li>• Standard heuristic criteria applied.</li>'}
            </ul>
          </div>

          <div class="content-card">
            <h3 class="content-card-title">Incremental Refresh Policy</h3>
            <table class="data-table">
              <tbody>
                <tr><td><strong>Policy Status</strong></td><td><span class="badge {'badge-status-active' if has_inc else 'badge-status-inactive'}">{'Enabled' if has_inc else 'Disabled'}</span></td></tr>
                <tr><td><strong>Storage Mode</strong></td><td><code>{escape(inc.get('mode', self.table.get('storage_mode', 'Import')))}</code></td></tr>
                <tr><td><strong>Historical Retention (Store)</strong></td><td>{escape(str(inc.get('rolling_window_periods', '—')))} {escape(str(inc.get('rolling_window_granularity', '')))}</td></tr>
                <tr><td><strong>Refresh Period (Refresh)</strong></td><td>{escape(str(inc.get('incremental_periods', '—')))} {escape(str(inc.get('incremental_granularity', '')))}</td></tr>
              </tbody>
            </table>
            {f'''<div style="margin-top: 1rem;"><div class="spec-group-title">Detect Data Changes Expression</div><div class="code-container"><pre><code>{escape(inc.get('polling_expression', ''))}</code></pre></div></div>''' if inc.get('polling_expression') else ''}
          </div>
        </div>
      </div>
"""


class HtmlMeasureBuilder:
    """Builds individual Measure documentation page (measures/<Table>/<Measure>.html)."""

    def __init__(
        self,
        measure_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.measure = measure_data
        self.model = full_model
        self.config = config
        self.project_name = project_name or full_model.get("project_name") or "PBIP"
        self.name = measure_data.get("name", "UnnamedMeasure")
        self.table = measure_data.get("table", "Model")
        self.depth = measure_data.get("calculation_depth", 0)

    def build_content(self) -> str:
        rel_root = "../.."
        clean_tbl = sanitize_filename(self.table)
        tbl_url = f"{rel_root}/{self.config.tables_subdir.strip('/\\\\')}/{clean_tbl}.html"

        upstream_m = self.measure.get("upstream_measures", [])
        downstream_m = self.measure.get("downstream_measures", [])
        ref_cols = self.measure.get("referenced_columns", [])

        # Format DAX with formatting utility
        dax = self.measure.get("dax_expression", "")
        formatted_dax = format_dax(dax) if dax else "-- No DAX expression provided"

        # Upstream table
        up_rows = []
        for um in upstream_m:
            target_tbl = self.table
            clean_u = sanitize_filename(um)
            m_url = f"{rel_root}/{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_u}.html"
            up_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(um)}]</a></strong></td>
            <td><a href="{tbl_url}">{escape(target_tbl)}</a></td>
          </tr>""")

        # Downstream table
        down_rows = []
        for dm in downstream_m:
            target_tbl = self.table
            clean_d = sanitize_filename(dm)
            m_url = f"{rel_root}/{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_d}.html"
            down_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(dm)}]</a></strong></td>
            <td><a href="{tbl_url}">{escape(target_tbl)}</a></td>
          </tr>""")

        # Ref cols rows
        col_rows = []
        for c in ref_cols:
            if isinstance(c, dict):
                t_name = c.get("table", self.table)
                c_name = c.get("column", "")
            elif isinstance(c, (list, tuple)) and len(c) > 0 and isinstance(c[0], dict):
                t_name = c[0].get("table", self.table)
                c_name = c[0].get("column", "")
            elif isinstance(c, (list, tuple)) and len(c) >= 2:
                t_name, c_name = str(c[0]), str(c[1])
            elif isinstance(c, str) and "[" in c:
                t_name, c_name = c.split("[", 1)
                c_name = c_name.rstrip("]")
            else:
                t_name, c_name = self.table, str(c)

            clean_t = sanitize_filename(t_name)
            t_link = f"{rel_root}/{self.config.tables_subdir.strip('/\\\\')}/{clean_t}.html"
            col_rows.append(f"""          <tr>
            <td><a href="{t_link}">{escape(t_name)}</a></td>
            <td><code>[{escape(c_name)}]</code></td>
          </tr>""")

        # KPI Summary Cards
        kpis_html = f"""
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Host Table</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><a href="{tbl_url}">{escape(self.table)}</a></div>
          <div class="kpi-sub">Container Entity</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Calculation Depth</div>
          <div class="kpi-value">Depth {self.depth}</div>
          <div class="kpi-sub">{len(upstream_m)} Upstream Precedents</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Downstream Impact</div>
          <div class="kpi-value">{len(downstream_m)}</div>
          <div class="kpi-sub">Dependent Measures</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Format String</div>
          <div class="kpi-value" style="font-size: 1.25rem;"><code>{escape(self.measure.get('format_string', '') or '—')}</code></div>
          <div class="kpi-sub">{escape(self.measure.get('display_folder', '') or 'Root Folder')}</div>
        </div>
      </div>
"""

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>Measure: [{escape(self.name)}]</span>
          <span class="badge badge-role-fact">Depth {self.depth}</span>
        </h1>
        <p class="page-subtitle">{escape(self.measure.get('description', '') or 'Business calculation formula and dependency DAG.')}</p>
      </div>

{kpis_html}

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-dax">DAX Formula</button>
          <button class="tab-btn" data-tab-target="tab-deps">Dependencies & Impact ({len(upstream_m) + len(downstream_m)})</button>
          <button class="tab-btn" data-tab-target="tab-cols">Referenced Columns ({len(ref_cols)})</button>
          <button class="tab-btn" data-tab-target="tab-tech">Technical Details</button>
        </div>

        <div id="tab-dax" class="tab-content active">
          <div class="content-card">
            <h3 class="content-card-title">DAX Expression</h3>
            <div class="code-container">
              <div class="code-header">
                <span>DAX Formula</span>
                <button class="copy-btn" data-copy-target="measure-dax-code">Copy</button>
              </div>
              <pre><code id="measure-dax-code">{escape(formatted_dax)}</code></pre>
            </div>
          </div>
        </div>

        <div id="tab-deps" class="tab-content">
          <div class="content-card" style="margin-bottom: 1.25rem;">
            <h3 class="content-card-title">Preceding Measures in DAG (Upstream - {len(upstream_m)})</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Measure</th>
                    <th>Host Table</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(up_rows) if up_rows else '<tr><td colspan="2"><em>Leaf calculation: No upstream measures referenced.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div class="content-card">
            <h3 class="content-card-title">Dependent Measures (Downstream Impact - {len(downstream_m)})</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Measure</th>
                    <th>Host Table</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(down_rows) if down_rows else '<tr><td colspan="2"><em>Terminal calculation: No other measures depend on this formula.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="tab-cols" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Referenced Model Columns</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Table</th>
                    <th>Column Name</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(col_rows) if col_rows else '<tr><td colspan="2"><em>No physical or calculated columns directly referenced.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="tab-tech" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Technical Specifications</h3>
            <table class="data-table">
              <tbody>
                <tr><td><strong>Model Key</strong></td><td><code>{escape(self.measure.get('model_key', f'{self.table}[{self.name}]'))}</code></td></tr>
                <tr><td><strong>Display Folder</strong></td><td>{escape(self.measure.get('display_folder', '') or '—')}</td></tr>
                <tr><td><strong>Format String</strong></td><td><code>{escape(self.measure.get('format_string', '') or '—')}</code></td></tr>
                <tr><td><strong>Hidden in View Mode</strong></td><td>{'Yes' if self.measure.get('is_hidden') else 'No'}</td></tr>
                <tr><td><strong>External Bound (Composite)</strong></td><td>{'Yes' if self.measure.get('is_external_measure') else 'No'}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
"""


class HtmlVisualBuilder:
    """Builds individual Report Page documentation (visuals/<PageName>.html)."""

    def __init__(
        self,
        page,
        report_model: PBIPReportModel,
        config: DocGenConfig,
        project_name: Optional[str] = None,
        model_tables: Optional[List[Dict[str, Any]]] = None,
        model_measures: Optional[List[Dict[str, Any]]] = None,
    ):
        self.page = page
        self.report = report_model
        self.config = config
        self.project_name = project_name or "PBIP"
        self.model_tables = model_tables or []
        self.model_measures = model_measures or []
        self.table_map = {t.get("name"): t for t in self.model_tables if t.get("name")}
        self.measure_map = {m.get("name"): m for m in self.model_measures if m.get("name")}

    def build_content(self) -> str:
        rel_root = ".."
        dynamic_visuals = [v for v in self.page.visuals if v.is_dynamic]

        kpis_html = f"""
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Dynamic Visuals</div>
          <div class="kpi-value">{len(dynamic_visuals)}</div>
          <div class="kpi-sub">Data-Bound Containers</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Canvas Dimensions</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><code>{self.page.width}x{self.page.height}</code></div>
          <div class="kpi-sub">Pixels (Width x Height)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Page Order</div>
          <div class="kpi-value">#{self.page.page_number}</div>
          <div class="kpi-sub">Sequence in Report</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Visibility</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{'Hidden' if self.page.is_hidden else 'Visible'}</div>
          <div class="kpi-sub">View Mode State</div>
        </div>
      </div>
"""

        # Visual cards
        visual_cards = []
        for idx, v in enumerate(dynamic_visuals, start=1):
            title = v.title or f"Visual {idx}"
            cond_badge = ' <span class="badge badge-dim" style="margin-left: 0.5rem;">Conditional Title</span>' if v.is_conditional_title else ""
            s_pos = v.spatial_position
            zone = s_pos.zone if s_pos else "Center"
            indicative_pos = zone.replace("Middle-", "Center-")
            if indicative_pos in ("Center-Center", "Canvas"):
                indicative_pos = "Center"

            calc = v.calculation_context
            metrics_html = []
            for m in calc.evaluated_metrics:
                m_name = m.field
                clean_m = sanitize_filename(m_name)
                clean_tbl = sanitize_filename(m.table or "Model")
                is_implicit = bool(m.aggregation) or m.field_type in ("IMPLICIT_MEASURE", "COLUMN")

                if not is_implicit and m.field_type == "MEASURE":
                    m_url = f"{rel_root}/{self.config.measures_subdir.strip('/\\\\')}/{clean_tbl}/{clean_m}.html"
                    link_html = f'<a href="{m_url}"><strong>[{escape(m_name)}]</strong></a>'
                    type_badge = ""
                else:
                    t_url = f"{rel_root}/{self.config.tables_subdir.strip('/\\\\')}/{clean_tbl}.html"
                    link_html = f'<a href="{t_url}"><code>{escape(m.model_key or m_name)}</code></a>'
                    type_badge = ' <span class="badge badge-type" style="font-size: 0.72rem;">Implicit Measure</span>'

                agg_str = f" ({escape(m.aggregation)})" if m.aggregation else ""
                screen_str = f' <span class="badge badge-dim" style="font-size: 0.72rem;">Screen: "{escape(m.display_name)}"</span>' if m.display_name else ""
                metrics_html.append(f'<li>{link_html}{agg_str}{type_badge} <span style="color: var(--text-muted);">(Role: {escape(m.role)})</span>{screen_str}</li>')

            slicing_html = []
            for s in calc.slicing_coordinates:
                clean_tbl = sanitize_filename(s.table)
                t_url = f"{rel_root}/{self.config.tables_subdir.strip('/\\\\')}/{clean_tbl}.html"
                screen_str = f' <span class="badge badge-dim" style="font-size: 0.72rem;">Screen: "{escape(s.display_name)}"</span>' if s.display_name else ""
                slicing_html.append(f'<li><a href="{t_url}">{escape(s.table)}</a> ➔ <code>[{escape(s.field)}]</code> <span style="color: var(--text-muted);">(Role: {escape(s.role)})</span>{screen_str}</li>')

            # Mini-map image
            svg_url = self.config.resolve_visual_svg_url(self.page.display_name, v.visual_id)

            visual_cards.append(f"""
      <div class="visual-card">
        <div class="visual-card-header">
          <div>
            <strong>#{idx}. {escape(title)}</strong>
            <span class="badge badge-dim" style="margin-left: 0.5rem;">{escape(v.visual_type)}</span>{cond_badge}
          </div>
          <span class="badge badge-type">Position: {escape(indicative_pos)}</span>
        </div>
        <div class="visual-card-body">
          <div class="visual-minimap-col">
            <img src="{svg_url}" class="visual-minimap-img" alt="{escape(title)} Canvas Location">
          </div>
          <div class="visual-specs-col">
            <div>
              <div class="spec-group-title">Evaluated Metrics</div>
              {('<ul class="spec-list">' + chr(10).join(metrics_html) + '</ul>') if metrics_html else '<p style="color: var(--text-muted);"><em>No metrics evaluated (slicer or structural visual).</em></p>'}
            </div>
            <div>
              <div class="spec-group-title">Slicing Coordinates</div>
              {('<ul class="spec-list">' + chr(10).join(slicing_html) + '</ul>') if slicing_html else '<p style="color: var(--text-muted);"><em>No slicing coordinates.</em></p>'}
            </div>
            <div>
              <div class="spec-group-title">Filter Perimeter</div>
              <ul class="spec-list">
                <li>Locked Page Filters: {len(calc.locked_active_filters)} active</li>
                <li>Interactive Panel Filters: {len(calc.unlocked_available_filters)} available</li>
                <li>Visual-Level Filters: {len(calc.visual_active_filters)} active</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
""")

        # Tab 2: Canvas Filter Context
        locked_filters_rows = []
        interactive_filters_rows = []
        slicers_rows = []

        # Find filters from calculation context across visuals
        if dynamic_visuals:
            first_v = dynamic_visuals[0]
            for lf in first_v.calculation_context.locked_active_filters:
                vals = ", ".join(lf.applied_values) if lf.applied_values else (lf.default_value or "Active")
                locked_filters_rows.append(f"""          <tr>
            <td><strong>{escape(lf.table)}</strong></td>
            <td><code>[{escape(lf.field)}]</code></td>
            <td><code>{escape(lf.operator or 'In')}</code></td>
            <td>{escape(vals)}</td>
            <td><span class="badge badge-role-fact">Hard Constraint</span></td>
          </tr>""")

            for uf in first_v.calculation_context.unlocked_available_filters:
                interactive_filters_rows.append(f"""          <tr>
            <td><strong>{escape(uf.table)}</strong></td>
            <td><code>[{escape(uf.field)}]</code></td>
            <td>{escape(uf.default_value or 'All (No filter applied)')}</td>
          </tr>""")

            for sl in first_v.calculation_context.page_slicers:
                slicers_rows.append(f"""          <tr>
            <td><code>{escape(sl.model_key)}</code></td>
            <td><strong>{escape(sl.table)}</strong> ➔ <code>[{escape(sl.field)}]</code></td>
            <td>{escape(sl.default_selection)}</td>
            <td>{'Yes' if sl.is_synced_across_pages else 'No'}</td>
          </tr>""")

        # Tab 3: Technical Layout Coordinates
        coords_rows = []
        for idx, v in enumerate(dynamic_visuals, start=1):
            sp = v.spatial_position
            bbox = sp.bounding_box if sp else None
            bx = f"{bbox.x:.0f}" if bbox else "—"
            by = f"{bbox.y:.0f}" if bbox else "—"
            bw = f"{bbox.width:.0f}" if bbox else "—"
            bh = f"{bbox.height:.0f}" if bbox else "—"
            bz = f"{bbox.z}" if bbox else "0"

            coords_rows.append(f"""          <tr>
            <td>#{idx}</td>
            <td><strong>{escape(v.title or f'Visual {idx}')}</strong></td>
            <td><code>{escape(v.visual_id)}</code></td>
            <td><span class="badge badge-type">{escape(v.visual_type)}</span></td>
            <td><code>({bx}, {by})</code></td>
            <td><code>{bw}x{bh}</code></td>
            <td>{bz}</td>
          </tr>""")

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>Report Page: {escape(self.page.display_name)}</span>
          <span class="badge badge-dim">#{self.page.page_number}</span>
        </h1>
        <p class="page-subtitle">Interactive visual layout, spatial coordinates, metric evaluations, and canvas filter context.</p>
      </div>

{kpis_html}

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-visuals">Visuals ({len(dynamic_visuals)})</button>
          <button class="tab-btn" data-tab-target="tab-filters">Canvas Filter Context</button>
          <button class="tab-btn" data-tab-target="tab-tech">Spatial Layout & Geometry</button>
        </div>

        <div id="tab-visuals" class="tab-content active">
{chr(10).join(visual_cards) if visual_cards else '<p style="color: var(--text-muted);"><em>No dynamic data-bound visual containers on this page.</em></p>'}
        </div>

        <div id="tab-filters" class="tab-content">
          <div class="content-card" style="margin-bottom: 1.25rem;">
            <h3 class="content-card-title">Locked Active Page Filters (Hard Constraints)</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Target Table</th>
                    <th>Target Field</th>
                    <th>Operator</th>
                    <th>Applied Values</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(locked_filters_rows) if locked_filters_rows else '<tr><td colspan="5"><em>No locked page filters active on this canvas.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div class="content-card" style="margin-bottom: 1.25rem;">
            <h3 class="content-card-title">Interactive Filter Pane Defaults</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Target Table</th>
                    <th>Target Field</th>
                    <th>Default Selection</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(interactive_filters_rows) if interactive_filters_rows else '<tr><td colspan="3"><em>No interactive filter panel filters exposed.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div class="content-card">
            <h3 class="content-card-title">Canvas Slicer Controls</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Slicer Control</th>
                    <th>Target Field</th>
                    <th>Default Selection</th>
                    <th>Synced Across Pages</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(slicers_rows) if slicers_rows else '<tr><td colspan="4"><em>No interactive on-canvas slicers detected.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="tab-tech" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Exact Spatial Coordinates & Container Specifications</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Visual Title</th>
                    <th>Visual ID</th>
                    <th>Type</th>
                    <th>Position (X, Y)</th>
                    <th>Size (W x H)</th>
                    <th>Z-Index</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(coords_rows) if coords_rows else '<tr><td colspan="7"><em>No visual containers detected.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
"""


class HtmlExpressionBuilder:
    """Builds individual Shared Expression page (expressions/<Expression>.html)."""

    def __init__(
        self,
        expression_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.expression = expression_data
        self.model = full_model
        self.config = config
        self.project_name = project_name or "PBIP"
        self.name = expression_data.get("query_name", "SharedExpression")

    def build_content(self) -> str:
        q_name = self.expression.get("query_name", "Expression")
        target_table = self.expression.get("target_table") or "None (Staging Query)"
        is_staging = self.expression.get("is_staging", True)
        direct_deps = self.expression.get("direct_dependencies", [])
        raw_m = self.expression.get("full_m_expression") or self.expression.get("raw_m_code") or ""
        m_code = format_m(raw_m) if raw_m else ""

        dep_links = []
        for d in direct_deps:
            clean_d = sanitize_filename(d)
            dep_links.append(f'<li><a href="{clean_d}.html"><code>{escape(d)}</code></a></li>')

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>Expression: {escape(q_name)}</span>
          <span class="badge badge-dim">{'Staging' if is_staging else 'Entity'}</span>
        </h1>
        <p class="page-subtitle">Power Query M shared ETL query and transformation pipeline.</p>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Pipeline Role</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{'Staging' if is_staging else 'Model Table'}</div>
          <div class="kpi-sub">Data Load Mode</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Target Table</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{escape(target_table)}</div>
          <div class="kpi-sub">Loaded Entity</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Dependencies</div>
          <div class="kpi-value">{len(direct_deps)}</div>
          <div class="kpi-sub">Direct Upstream Queries</div>
        </div>
      </div>

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-m">Power Query (M) Script</button>
          <button class="tab-btn" data-tab-target="tab-deps">Dependencies ({len(direct_deps)})</button>
        </div>

        <div id="tab-m" class="tab-content active">
          <div class="content-card">
            <h3 class="content-card-title">M Formula</h3>
            <div class="code-container">
              <div class="code-header">
                <span>Power Query Script</span>
                <button class="copy-btn" data-copy-target="expression-m-code">Copy</button>
              </div>
              <pre><code id="expression-m-code">{escape(m_code)}</code></pre>
            </div>
          </div>
        </div>

        <div id="tab-deps" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Direct Upstream Queries</h3>
            {('<ul class="spec-list">' + chr(10).join(dep_links) + '</ul>') if dep_links else '<p style="color: var(--text-muted);"><em>Root query: No direct dependencies.</em></p>'}
          </div>
        </div>
      </div>
"""


class HtmlFunctionBuilder:
    """Builds individual DAX UDF page (functions/<Function>.html)."""

    def __init__(
        self,
        function_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.function = function_data
        self.model = full_model
        self.config = config
        self.project_name = project_name or "PBIP"
        self.name = function_data.get("name", "UDF")

    def build_content(self) -> str:
        f_name = self.function.get("name", "Function")
        ret_type = self.function.get("return_type", "Variant")
        params = self.function.get("parameters", [])
        body = self.function.get("expression") or self.function.get("body") or ""

        param_rows = []
        for p in params:
            param_rows.append(f"""          <tr>
            <td><strong>`{escape(p.get('name'))}`</strong></td>
            <td><code>{escape(p.get('data_type', 'Variant'))}</code></td>
            <td>{escape(p.get('description', '') or '—')}</td>
          </tr>""")

        return f"""
      <div class="page-header">
        <h1 class="page-title">
          <span>Function: {escape(f_name)}</span>
          <span class="badge badge-dim">UDF</span>
        </h1>
        <p class="page-subtitle">User-Defined DAX Function specification and parameters.</p>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Return Type</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><code>{escape(ret_type)}</code></div>
          <div class="kpi-sub">Result Data Type</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Parameters</div>
          <div class="kpi-value">{len(params)}</div>
          <div class="kpi-sub">Input Arguments</div>
        </div>
      </div>

      <div class="tabs-container">
        <div class="tabs-header">
          <button class="tab-btn active" data-tab-target="tab-body">DAX Function Body</button>
          <button class="tab-btn" data-tab-target="tab-params">Parameters ({len(params)})</button>
        </div>

        <div id="tab-body" class="tab-content active">
          <div class="content-card">
            <h3 class="content-card-title">Implementation Expression</h3>
            <div class="code-container">
              <div class="code-header">
                <span>DAX Body</span>
                <button class="copy-btn" data-copy-target="function-dax-code">Copy</button>
              </div>
              <pre><code id="function-dax-code">{escape(body)}</code></pre>
            </div>
          </div>
        </div>

        <div id="tab-params" class="tab-content">
          <div class="content-card">
            <h3 class="content-card-title">Parameters</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Parameter Name</th>
                    <th>Data Type</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(param_rows) if param_rows else '<tr><td colspan="3"><em>No parameters required.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
"""
