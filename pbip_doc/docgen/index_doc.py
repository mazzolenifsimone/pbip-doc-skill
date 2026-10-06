"""
Master Index Document Generator for Semantic Models.
Produces an overarching README / INDEX markdown linking all tables and measures.
Vanilla Python implementation.
"""

import re
from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename


class IndexDocBuilder:
    """
    Builds the master catalog INDEX.md linking all generated table and measure documents.
    """

    def __init__(self, model_data: Dict[str, Any], config: Optional[DocGenConfig] = None):
        self.model = model_data
        self.config = config or DocGenConfig()

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
            "doc_type": "semantic_model_catalog",
            "format": self.model.get("source_format"),
            "tables_count": len(valid_tables),
            "measures_count": len(valid_measures),
            "functions_count": len(valid_functions),
            "expressions_count": len(expr_list),
            "data_sources_count": len(self.model.get("data_sources_summary", [])),
            "excluded_tables_count": self.model.get("excluded_tables_count", 0),
            "tags": ["semantic_model", "catalog", "pbip", self.model.get("model_name", "model")],
        }
        sections.append(format_yaml_frontmatter(frontmatter))

        # 2. Title & Metadata
        sections.append(self._build_header_section())

        # 3. Data Sources & ETL Lineage Summary
        sections.append(self._build_sources_section())

        # 4. Table Catalog (Grouped by Role)
        sections.append(self._build_tables_catalog(valid_tables, valid_measures))

        # 5. Measure Catalog (Grouped by Calculation Depth)
        sections.append(self._build_measures_catalog(valid_measures))

        # 6. UDF Functions Catalog (if any functions exist)
        fn_section = self._build_functions_catalog(valid_functions)
        if fn_section:
            sections.append(fn_section)

        # 7. Expressions & Shared ETL Queries Catalog (if any expressions exist)
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
                link = f"[`{name}`]({self.config.tables_subdir}/{clean_tbl}.md)"
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
                link = f"[`[{m_name}]`]({self.config.measures_subdir}/{clean_tbl}/{sanitized}.md)"
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
            link = f"[`{fn_name}`]({self.config.functions_subdir}/{sanitized}.md)"
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
                    t_links.append(f"[`{dt}`]({tables_sub}/{clean_dt}.md)")
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

            doc_link = f"[`{name}`]({expressions_sub}/{clean_name}.md)"
            lines.append(f"| `{name}` | {type_badge} | {inline_info} | {downstream_str} | {sources_str} | {doc_link} |")

        return "\n".join(lines)
