"""
Master Index Document Generator for Semantic Models.
Produces an overarching README / INDEX markdown linking all tables and measures.
Vanilla Python implementation.
"""

import re
from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename, join_doc_path, clean_project_name


class IndexDocBuilder:
    """
    Builds the master catalog INDEX.md linking all generated table and measure documents.
    """

    def __init__(
        self,
        model_data: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        report_model: Optional[Any] = None,
        project_name: Optional[str] = None,
    ):
        self.model = model_data
        self.config = config or DocGenConfig()
        self.report_model = report_model
        rep_name = getattr(report_model, "report_name", None) if report_model else None
        self.project_name = clean_project_name(
            project_name or self.config.project_name or model_data.get("project_name") or model_data.get("model_name") or rep_name
        )

    def build_markdown(self) -> str:
        sections = []

        valid_tables = [
            t for t in self.model.get("tables", [])
            if not self.config.is_table_excluded(t.get("name"))
        ]
        valid_measures = [
            m for m in self.model.get("measures", [])
            if not self.config.is_table_excluded(m.get("table"))
        ]
        valid_functions = self.model.get("functions", [])
        expr_list = self.model.get("expressions") or self.model.get("shared_queries") or []

        # 1. Frontmatter
        frontmatter = {
            "title": f"Semantic Model Documentation: {self.model.get('model_name')}",
            "pbip_project": self.project_name,
            "doc_type": "semantic_model_catalog",
            "format": self.model.get("source_format"),
            "tables_count": len(valid_tables),
            "measures_count": len(valid_measures),
            "functions_count": len(valid_functions),
            "expressions_count": len(expr_list),
            "data_sources_count": len(self.model.get("data_sources_summary", [])),
            "excluded_tables_count": self.model.get("excluded_tables_count", 0),
            "tags": ["semantic_model", "catalog", "pbip", sanitize_filename(self.project_name), self.model.get("model_name", "model")],
        }
        if self.report_model and self.config.include_visual_docs:
            rep_pages = getattr(self.report_model, "pages", []) if hasattr(self.report_model, "pages") else self.report_model.get("pages", [])
            rep_name = getattr(self.report_model, "report_name", "") if hasattr(self.report_model, "report_name") else self.report_model.get("report_name", "")
            frontmatter["report_name"] = rep_name
            frontmatter["report_pages_count"] = len(rep_pages)
            if rep_name:
                frontmatter["tags"].append(sanitize_filename(rep_name))
            frontmatter["tags"].append("report")

        sections.append(format_yaml_frontmatter(frontmatter))

        # 2. Title & Metadata
        sections.append(self._build_header_section())

        # 3. Data Sources & ETL Lineage Summary
        sections.append(self._build_sources_section())

        # 4. Table Catalog (Grouped by Role)
        sections.append(self._build_tables_catalog(valid_tables, valid_measures))

        # 5. Measure Catalog (Grouped by Calculation Depth)
        sections.append(self._build_measures_catalog(valid_measures))

        # 6. Report Pages & Visual Context (if report model present and enabled)
        if self.report_model and self.config.include_visual_docs:
            rep_section = self._build_report_pages_catalog()
            if rep_section:
                sections.append(rep_section)

        # 7. UDF Functions Catalog (if any functions exist)
        fn_section = self._build_functions_catalog(valid_functions)
        if fn_section:
            sections.append(fn_section)

        # 8. Expressions & Shared ETL Queries Catalog (if any expressions exist)
        expr_section = self._build_expressions_catalog(expr_list)
        if expr_section:
            sections.append(expr_section)

        return "\n\n".join(sections) + "\n"

    def _build_header_section(self) -> str:
        lines = [
            f"# Semantic Model Documentation: `{self.model.get('model_name')}`",
            "",
            f"**Source Format**: `{self.model.get('source_format')}` | "
            f"**Compatibility Level**: `{self.model.get('compatibility_level', 1600)}` | "
            f"**Culture**: `{self.model.get('culture', 'en-US')}`",
            "",
            "Technical documentation for the PBIP semantic model. "
            "Every table, DAX measure, User-Defined Function, and ETL expression features a dedicated Markdown document complete with structured YAML frontmatter for search, retrieval, and technical reference.",
        ]
        return "\n".join(lines)

    def _build_sources_section(self) -> str:
        lines = [
            "## Detected Physical Data Sources",
            "",
            "| Connector Type | Connection / Target | Server | Database |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for src in self.model.get("data_sources_summary", []):
            stype = f"`{src.get('source_type')}`"
            conn = f"`{src.get('connection_string')}`"
            server = f"`{src.get('server')}`" if src.get("server") else "—"
            db = f"`{src.get('database')}`" if src.get("database") else "—"
            lines.append(f"| {stype} | {conn} | {server} | {db} |")
        return "\n".join(lines)

    def _build_tables_catalog(self, tables: Optional[List[Dict[str, Any]]] = None, measures: Optional[List[Dict[str, Any]]] = None) -> str:
        lines = [
            "## Tables Catalog",
            "",
            "Tables analyzed and classified according to topological and heuristic criteria:",
            "",
            "| Table | Role | Refresh Policy | Columns | Measures | Document Link |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]

        if tables is None:
            tables = [
                t for t in self.model.get("tables", [])
                if not self.config.is_table_excluded(t.get("name"))
            ]
        if measures is None:
            measures = [
                m for m in self.model.get("measures", [])
                if not self.config.is_table_excluded(m.get("table"))
            ]

        # Sort by role (FACT first, then DIM, then LOOKUP, then DATE)
        role_order = {"FACT": 0, "DIMENSION": 1, "LOOKUP_OUTRIGGER": 2, "DATE_DIMENSION": 3, "BRIDGE": 4, "PARAMETER_UTILITY": 5}
        sorted_tables = sorted(tables, key=lambda t: (role_order.get(t.get("role"), 99), t.get("name")))

        for t in sorted_tables:
            name = t.get("name")
            role = f"`{t.get('role')}`"
            inc_pol = t.get("incremental_refresh_policy")
            if inc_pol and inc_pol.get("is_enabled"):
                mode = inc_pol.get("mode")
                if mode == "hybrid":
                    refresh_badge = "⚡ Hybrid"
                else:
                    refresh_badge = "🔄 Incremental"
            elif t.get("is_inherited"):
                refresh_badge = "📦 Inherited"
            elif t.get("source_type") == "CalculatedTable":
                refresh_badge = "🧮 DAX Calc"
            else:
                refresh_badge = "Full"
            col_count = len(t.get("columns", []))
            m_count = len([m for m in measures if m.get("table") == name])
            clean_tbl = sanitize_filename(name)
            if self.config.is_table_published(t):
                if self.config.base_doc_url:
                    tbl_url = join_doc_path(self.config.base_doc_url, self.config.tables_subdir.strip("/\\"), f"{clean_tbl}.md")
                else:
                    tbl_url = f"{self.config.tables_subdir}/{clean_tbl}.md"
                link = f"[`{name}`]({tbl_url})"
            else:
                ext_url = self.config.resolve_external_table_url(t)
                if ext_url:
                    link = f"[`{name}`]({ext_url}) *(External)*"
                else:
                    link = "— *(Inherited Entity)*"
            lines.append(f"| `{name}` | {role} | {refresh_badge} | {col_count} | {m_count} | {link} |")

        calc_count = len([t for t in sorted_tables if t.get("source_type") == "CalculatedTable"])
        if calc_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Calculated Tables**: {calc_count} tables (`source_type = CalculatedTable`) "
                "are computed dynamically in-memory using DAX table expressions (`partition = calculated`)."
            )

        inherited_count = len([t for t in sorted_tables if not self.config.is_table_published(t)])
        if inherited_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Inherited Tables**: {inherited_count} inherited tables (`partition = entity`) "
                "are cataloged in the model index, but their individual documentation pages are not generated."
            )

        excluded_count = self.model.get("excluded_tables_count", 0)
        if excluded_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Excluded Tables**: {excluded_count} internal system tables "
                "(e.g., `LocalDateTable_*`, `DateTableTemplate_*`) have been excluded from the documentation scope as per configuration."
            )

        return "\n".join(lines)

    def _build_measures_catalog(self, measures: Optional[List[Dict[str, Any]]] = None) -> str:
        lines = [
            "## DAX Measures Catalog",
            "",
            "DAX measures indexed by calculation hierarchy (Calculation Depth):",
            "",
            "| Measure | Table | DAG Depth | Dependencies | Document Link |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ]

        if measures is None:
            measures = [
                m for m in self.model.get("measures", [])
                if not self.config.is_table_excluded(m.get("table"))
            ]
        sorted_measures = sorted(measures, key=lambda m: (m.get("calculation_depth", 0), m.get("table", ""), m.get("name", "")))

        for m in sorted_measures:
            m_name = m.get("name")
            tbl = m.get("table") or "Model"
            depth = f"Depth {m.get('calculation_depth', 0)}"
            clean_tbl = sanitize_filename(tbl)
            sanitized = sanitize_filename(m_name)
            if self.config.is_measure_published(m):
                if self.config.base_doc_url:
                    meas_url = join_doc_path(self.config.base_doc_url, self.config.measures_subdir.strip("/\\"), clean_tbl, f"{sanitized}.md")
                else:
                    meas_url = f"{self.config.measures_subdir}/{clean_tbl}/{sanitized}.md"
                link = f"[`[{m_name}]`]({meas_url})"
            else:
                ext_url = self.config.resolve_external_measure_url(m, self.model.get("tables", []))
                if ext_url:
                    link = f"[`[{m_name}]`]({ext_url}) *(External)*"
                else:
                    link = "— *(External Measure)*"
            deps = ", ".join(f"`[{d}]`" for d in m.get("direct_measure_dependencies", [])) or "— (Base Measure)"
            lines.append(f"| `[{m_name}]` | `{tbl}` | {depth} | {deps} | {link} |")

        ext_count = len([m for m in sorted_measures if not self.config.is_measure_published(m)])
        if ext_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **External Measures**: {ext_count} measures declared via `EXTERNALMEASURE(...)` "
                "are cataloged in the model index, but their individual documentation pages are not generated."
            )

        return "\n".join(lines)

    def _build_functions_catalog(self, functions: Optional[List[Dict[str, Any]]] = None) -> str:
        funcs = self.model.get("functions", []) if functions is None else functions
        if not funcs:
            return ""

        lines = [
            "## User-Defined Functions Catalog (UDFs)",
            "",
            "DAX User-Defined Functions (UDFs) defined at semantic model scope (`functions.tmdl`):",
            "",
            "| Function Name | Return Type | Signature | Downstream Measures | Document Link |",
            "| :--- | :---: | :--- | :---: | :--- |",
        ]

        for fn in sorted(funcs, key=lambda f: f.get("name", "")):
            fn_name = fn.get("name")
            ret_type = fn.get("return_type") or "Variant"
            sig = fn.get("parameters_signature") or "()"
            sanitized = sanitize_filename(fn_name)
            down_count = len(fn.get("downstream_measures", []))
            if self.config.base_doc_url:
                fn_url = join_doc_path(self.config.base_doc_url, self.config.functions_subdir.strip("/\\"), f"{sanitized}.md")
            else:
                fn_url = f"{self.config.functions_subdir}/{sanitized}.md"
            link = f"[`{fn_name}`]({fn_url})"
            lines.append(f"| `{fn_name}` | `{ret_type}` | `{sig}` | {down_count} | {link} |")

        return "\n".join(lines)

    def _build_expressions_catalog(self, expressions: Optional[List[Dict[str, Any]]] = None) -> str:
        exprs = expressions if expressions is not None else (self.model.get("expressions") or self.model.get("shared_queries") or [])
        if not exprs:
            return ""

        lines = [
            f"## Power Query Expressions & Shared ETL Queries ({len(exprs)})",
            "",
            "Staging queries, parameters, functions, and inline table definitions in the ETL compartment:",
            "",
            "| Expression | Type | Inline Data | Downstream Tables | Root Sources | Document Link |",
            "| :--- | :--- | :---: | :--- | :--- | :--- |",
        ]

        expressions_sub = self.config.expressions_subdir.strip("/\\")
        tables_sub = self.config.tables_subdir.strip("/\\")

        for expr in sorted(exprs, key=lambda e: e.get("query_name", "")):
            name = expr.get("query_name", "Unnamed")
            clean_name = sanitize_filename(name)
            is_inline = expr.get("is_inline_table", False)
            full_m = expr.get("full_m_expression", "")

            if is_inline or "#table" in full_m:
                col_cnt = len(expr.get("inline_table_columns", []))
                row_cnt = len(expr.get("inline_table_rows", []))
                inline_info = f"`{row_cnt}r × {col_cnt}c`" if (col_cnt or row_cnt) else "`#table`"
                type_badge = "📊 Inline Table"
            elif "meta [IsParameterQuery=true" in full_m:
                inline_info = "—"
                type_badge = "⚙️ Parameter"
            elif re.search(r'^\s*(\([^\)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*=>', full_m, re.MULTILINE):
                inline_info = "—"
                type_badge = "λ Function"
            else:
                inline_info = "—"
                type_badge = "🔄 Staging ETL"

            # Downstream tables
            downstream = [
                t for t in expr.get("downstream_tables", [])
                if not self.config.is_table_excluded(t)
            ]
            if downstream:
                t_links = []
                for dt in downstream:
                    clean_dt = sanitize_filename(dt)
                    if self.config.base_doc_url:
                        dt_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_dt}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_dt}.md")
                    else:
                        dt_url = f"{tables_sub}/{clean_dt}.md" if tables_sub else f"{clean_dt}.md"
                    t_links.append(f"[`{dt}`]({dt_url})")
                downstream_str = ", ".join(t_links)
            else:
                downstream_str = "— *(Unloaded)*"

            # Root sources
            sources = expr.get("root_sources", [])
            if sources:
                src_types = sorted(list({s.get("source_type", "GENERIC") for s in sources}))
                sources_str = ", ".join(f"`{st}`" for st in src_types)
            else:
                sources_str = "—"

            if self.config.base_doc_url:
                expr_url = join_doc_path(self.config.base_doc_url, expressions_sub, f"{clean_name}.md") if expressions_sub else join_doc_path(self.config.base_doc_url, f"{clean_name}.md")
            else:
                expr_url = f"{expressions_sub}/{clean_name}.md" if expressions_sub else f"{clean_name}.md"
            doc_link = f"[`{name}`]({expr_url})"
            lines.append(f"| `{name}` | {type_badge} | {inline_info} | {downstream_str} | {sources_str} | {doc_link} |")

        return "\n".join(lines)

    def _build_report_pages_catalog(self) -> str:
        """Catalog of report pages with links to dedicated page documentation."""
        if not self.report_model:
            return ""

        pages = getattr(self.report_model, "pages", [])
        if not pages and isinstance(self.report_model, dict):
            pages = self.report_model.get("pages", [])

        if not pages:
            return ""

        rep_name = getattr(self.report_model, "report_name", "") or (
            self.report_model.get("report_name", "Report") if isinstance(self.report_model, dict) else "Report"
        )
        rep_format = getattr(self.report_model, "format", "") or (
            self.report_model.get("format", "PBIR") if isinstance(self.report_model, dict) else "PBIR"
        )

        lines = [
            f"## Report Presentation & Visuals: `{rep_name}`",
            "",
            f"The presentation layer `{rep_name}.Report` ({rep_format}) is organized into **{len(pages)}** pages. "
            "Each page features a dedicated documentation document detailing canvas coordinates, evaluated metrics, slicing dimensions, and filter context:",
            "",
            "| Page | Role | Canvas Size | Status | Dynamic Visuals | Key Evaluated Metrics |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        vis_sub = self.config.visuals_subdir.strip("/\\")
        meas_sub = self.config.measures_subdir.strip("/\\")

        known_measures = {
            (meas.get("table"), meas.get("name"))
            for meas in self.model.get("measures", [])
        }

        for p in pages:
            p_name = getattr(p, "display_name", "") if hasattr(p, "display_name") else p.get("display_name", "")
            p_type = getattr(p, "page_type", "NORMAL") if hasattr(p, "page_type") else p.get("page_type", "NORMAL")
            w = getattr(p, "width", 1920) if hasattr(p, "width") else p.get("width", 1920)
            h = getattr(p, "height", 1080) if hasattr(p, "height") else p.get("height", 1080)
            is_hidden = getattr(p, "is_hidden", False) if hasattr(p, "is_hidden") else p.get("is_hidden", False)
            visuals = getattr(p, "visuals", []) if hasattr(p, "visuals") else p.get("visuals", [])

            dynamic_v = [v for v in visuals if (getattr(v, "is_dynamic", False) if hasattr(v, "is_dynamic") else True)]

            clean_p = sanitize_filename(p_name)
            if self.config.base_doc_url:
                p_url = join_doc_path(self.config.base_doc_url, vis_sub, f"{clean_p}.md") if vis_sub else join_doc_path(self.config.base_doc_url, f"{clean_p}.md")
            else:
                p_url = f"{vis_sub}/{clean_p}.md" if vis_sub else f"{clean_p}.md"

            p_link = f"[{p_name}]({p_url})" if self.config.include_markdown_links else f"`{p_name}`"
            status_str = "Hidden" if is_hidden else "Visible"

            # Gather top distinct metrics
            metric_links = []
            seen_keys = set()
            for v in dynamic_v:
                calc = getattr(v, "calculation_context", None) if hasattr(v, "calculation_context") else v.get("calculation_context", {})
                v_metrics = (
                    getattr(calc, "evaluated_metrics", [])
                    if hasattr(calc, "evaluated_metrics")
                    else (calc.get("evaluated_metrics", []) if isinstance(calc, dict) else [])
                )
                for m in v_metrics:
                    m_key = getattr(m, "model_key", "") if hasattr(m, "model_key") else m.get("model_key", "")
                    tbl = getattr(m, "table", "") if hasattr(m, "table") else m.get("table", "")
                    fld = getattr(m, "field", "") if hasattr(m, "field") else m.get("field", "")
                    m_type = getattr(m, "field_type", "") if hasattr(m, "field_type") else (m.get("field_type", "") if isinstance(m, dict) else "")
                    tables_sub = self.config.tables_subdir.strip("/\\")
                    if m_key and m_key not in seen_keys:
                        seen_keys.add(m_key)
                        if self.config.include_markdown_links and tbl and fld and tbl != "Unknown":
                            is_meas = (m_type == "MEASURE") or ((tbl, fld) in known_measures)
                            if is_meas:
                                if self.config.base_doc_url:
                                    m_url = join_doc_path(self.config.base_doc_url, meas_sub, sanitize_filename(tbl), f"{sanitize_filename(fld)}.md") if meas_sub else join_doc_path(self.config.base_doc_url, sanitize_filename(tbl), f"{sanitize_filename(fld)}.md")
                                else:
                                    m_url = f"{meas_sub}/{sanitize_filename(tbl)}/{sanitize_filename(fld)}.md" if meas_sub else f"{sanitize_filename(tbl)}/{sanitize_filename(fld)}.md"
                            else:
                                if self.config.base_doc_url:
                                    m_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{sanitize_filename(tbl)}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{sanitize_filename(tbl)}.md")
                                else:
                                    m_url = f"{tables_sub}/{sanitize_filename(tbl)}.md" if tables_sub else f"{sanitize_filename(tbl)}.md"
                            metric_links.append(f"[{m_key}]({m_url})")
                        else:
                            metric_links.append(f"`{m_key}`")
                        if len(metric_links) >= 3:
                            break
                if len(metric_links) >= 3:
                    break

            metrics_display = ", ".join(metric_links) if metric_links else "—"
            lines.append(f"| {p_link} | `{p_type}` | `{w}x{h}` | {status_str} | {len(dynamic_v)} | {metrics_display} |")

        return "\n".join(lines)
