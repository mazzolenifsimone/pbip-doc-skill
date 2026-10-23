"""
Modular Markdown Document Generator for DAX Measures.
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

import re
from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename, join_doc_path, clean_project_name
from ..dax_formatter import format_dax


class MeasureDocBuilder:
    """
    Builds modular markdown chapters for a single DAX measure in the semantic model.
    """

    def __init__(
        self,
        measure_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.measure = measure_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or full_model.get("project_name") or full_model.get("model_name")
        )
        self.name = measure_data.get("name", "UnnamedMeasure")
        self.table = measure_data.get("table", "Model")
        self.depth = measure_data.get("calculation_depth", 0)
        self.dax = measure_data.get("dax_expression", "")
        self.format_string = measure_data.get("format_string")
        self.description = measure_data.get("description")
        self.direct_deps = measure_data.get("direct_measure_dependencies", [])
        self.all_upstream = measure_data.get("all_upstream_measures", [])
        self.downstream = measure_data.get("downstream_measures", [])
        self.referenced_functions = measure_data.get("referenced_functions", [])
        norm_cols = []
        for rc in measure_data.get("referenced_columns", []):
            if isinstance(rc, dict):
                t_name = rc.get("table", self.table)
                c_name = rc.get("column", "")
            elif isinstance(rc, (list, tuple)) and len(rc) >= 2:
                t_name, c_name = str(rc[0]), str(rc[1])
            elif isinstance(rc, str) and "[" in rc:
                t_name, c_name = rc.split("[", 1)
                c_name = c_name.rstrip("]")
            else:
                t_name, c_name = self.table, str(rc)
            if not self.config.is_table_excluded(t_name):
                norm_cols.append({"table": t_name, "column": c_name})
        self.referenced_cols = norm_cols
        self.referenced_tables = [
            t for t in measure_data.get("referenced_tables", [])
            if not self.config.is_table_excluded(t)
        ]
        self.measure_table_map = {
            m.get("name"): m.get("table", "Model")
            for m in full_model.get("measures", [])
        }

    def _is_measure_published(self, target_measure_name: str) -> bool:
        """Checks if a target measure is published as a dedicated markdown file."""
        target_m = next((m for m in self.model.get("measures", []) if m.get("name") == target_measure_name), None)
        if target_m:
            return self.config.is_measure_published(target_m)
        return True

    def _get_measure_link(self, target_measure_name: str) -> str:
        """Computes the relative or absolute markdown link to another measure file."""
        target_table = self.measure_table_map.get(target_measure_name, self.table)
        clean_target_tbl = sanitize_filename(target_table)
        clean_target_m = sanitize_filename(target_measure_name)
        if self.config.base_doc_url:
            meas_sub = self.config.measures_subdir.strip("/\\")
            if meas_sub:
                return join_doc_path(self.config.base_doc_url, meas_sub, clean_target_tbl, f"{clean_target_m}.md")
            return join_doc_path(self.config.base_doc_url, clean_target_tbl, f"{clean_target_m}.md")
        return f"../{clean_target_tbl}/{clean_target_m}.md"

    def build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a pristine Markdown document."""
        sections = []

        # 1. Frontmatter
        if self.config.include_measure_yaml_frontmatter:
            sections.append(self._build_frontmatter())

        # 2. Header & Business Identity
        sections.append(self._build_identity_chapter())

        # 3. DAX Expression
        if self.config.include_measure_dax_formula:
            sections.append(self._build_dax_chapter())

        # 4. Calculation DAG & Upstream Dependencies
        if self.config.include_measure_upstream_deps:
            sections.append(self._build_upstream_chapter())

        # 5. Downstream Impact Analysis
        if self.config.include_measure_downstream_impact:
            sections.append(self._build_downstream_chapter())

        # 6. Physical Model Columns Referenced
        if self.config.include_measure_referenced_columns and (self.referenced_cols or self.referenced_tables):
            sections.append(self._build_columns_chapter())

        # 7. RAG Semantic Retrieval Hints
        if self.config.include_measure_rag_hints:
            sections.append(self._build_rag_hints_chapter())

        return "\n\n".join(sections) + "\n"

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG indexing and cataloging."""
        tags = [
            "semantic_model",
            "dax_measure",
            f"depth_{self.depth}",
            sanitize_filename(self.table),
            sanitize_filename(self.name),
        ]
        if self.project_name:
            tags.append(sanitize_filename(self.project_name))
        if self.depth == 0:
            tags.append("base_measure")
        else:
            tags.append("composite_measure")

        col_refs_str = [f"{rc.get('table')}[{rc.get('column')}]" for rc in self.referenced_cols]

        frontmatter_data = {
            "title": f"Measure: [{self.name}]",
            "pbip_project": self.project_name,
            "entity_name": self.name,
            "doc_type": "dax_measure",
            "table_name": self.table,
            "calculation_depth": self.depth,
            "is_base_measure": self.depth == 0,
            "is_inherited": self.measure.get("is_inherited", False),
            "is_external_measure": self.measure.get("is_external_measure", False),
            "out_of_scope": self.measure.get("out_of_scope", False),
            "description": self.description,
            "format_string": self.format_string or "Standard",
            "direct_dependencies": self.direct_deps,
            "all_upstream_dependencies": self.all_upstream,
            "referenced_functions": self.referenced_functions,
            "downstream_measures_count": len(self.downstream),
            "downstream_measures": self.downstream,
            "referenced_tables": self.referenced_tables,
            "referenced_columns": col_refs_str,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_identity_chapter(self) -> str:
        """Chapter 1: Measure Identity & Business Description."""
        depth_label = (
            "Base Measure (Depth 0 - direct calculation over physical columns)"
            if self.depth == 0
            else f"Composite Measure (Depth {self.depth} - calculated over other measures)"
        )

        clean_tbl = sanitize_filename(self.table)
        host_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == self.table), None)
        tbl_published = self.config.is_table_published(host_tbl) if host_tbl else True
        if tbl_published and self.config.include_markdown_links:
            if self.config.base_doc_url:
                tables_sub = self.config.tables_subdir.strip("/\\")
                target_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
            else:
                target_url = f"../../tables/{clean_tbl}.md"
            table_link = f"[{self.table}]({target_url})"
        else:
            ext_url = self.config.resolve_external_table_url(host_tbl) if host_tbl else None
            if ext_url and self.config.include_markdown_links:
                table_link = f"[{self.table}]({ext_url}) *(Inherited Entity)*"
            else:
                badge = " *(Inherited Entity)*" if (host_tbl and host_tbl.get("is_inherited")) else ""
                table_link = f"`{self.table}`{badge}"

        lines = [
            f"# Measure: `[{self.name}]`",
            "",
            f"**Home Table**: {table_link} | **DAG Hierarchy**: `{depth_label}`",
        ]

        if self.format_string:
            lines.append(f"**Format String**: `{self.format_string}`")

        if self.measure.get("display_folder"):
            lines.append(f"**Display Folder**: `{self.measure.get('display_folder')}`")

        lines.extend([
            "",
            "## Description",
            "",
        ])

        if self.description:
            lines.append(f"> {self.description}")
        else:
            lines.append("*No description provided.*")
        lines.append("")

        if self.measure.get("is_inherited") or self.measure.get("is_external_measure"):
            ext_url = self.config.resolve_external_measure_url(self.measure, self.model.get("tables", []))
            if ext_url and self.config.include_markdown_links:
                lines.append(f"> ℹ️ **External Measure**: This measure is declared via `EXTERNALMEASURE(...)` pointing to upstream measure [{self.name}]({ext_url}).")
            else:
                lines.append(f"> ℹ️ **External Measure**: This measure is declared via `EXTERNALMEASURE(...)` pointing to an upstream semantic model.")
            lines.append("")

        if self.depth == 0:
            lines.append(
                f"The measure **`[{self.name}]`** is a base-level metric that directly aggregates records "
                f"from the physical table `{self.table}` without intermediate measures."
            )
        else:
            lines.append(
                f"The measure **`[{self.name}]`** is a derived KPI of level {self.depth}. It combines or alters the evaluation "
                f"context of {len(self.direct_deps)} upstream measures ({', '.join(f'`[{d}]`' for d in self.direct_deps)})."
            )

        return "\n".join(lines)

    def _build_dax_chapter(self) -> str:
        """DAX Expression."""
        dax_formatted = format_dax(
            self.dax,
            name=self.name,
            entity_type="measure",
            table_name=self.table,
        )
        return "\n".join([
            "## DAX Formula",
            "```dax",
            dax_formatted,
            "```",
        ])

    def _build_upstream_chapter(self) -> str:
        """Upstream Calculation Tree (Dependencies)."""
        lines = ["## Upstream Calculation Tree (Direct and Transitive Dependencies)"]

        if not self.direct_deps:
            lines.append(
                "- **Dependencies on other Measures**: None (Terminal base measure computed directly over physical columns)."
            )
        else:
            lines.append("### Directly Referenced Measures:")
            for dep in self.direct_deps:
                dep_m = next((m for m in self.model.get("measures", []) if m.get("name") == dep), None)
                if self._is_measure_published(dep) and self.config.include_markdown_links:
                    meas_link = self._get_measure_link(dep)
                    link = f"[{dep}]({meas_link})"
                else:
                    ext_url = self.config.resolve_external_measure_url(dep_m, self.model.get("tables", [])) if dep_m else None
                    if ext_url and self.config.include_markdown_links:
                        link = f"[{dep}]({ext_url}) *(External Measure)*"
                    else:
                        badge = " *(External Measure)*" if (dep_m and (dep_m.get("is_inherited") or dep_m.get("is_external_measure"))) else ""
                        link = f"`[{dep}]`{badge}"
                lines.append(f"- {link}")

            if len(self.all_upstream) > len(self.direct_deps):
                lines.append("")
                lines.append("### Full Transitive Closure (All recursively upstream measures):")
                for u in self.all_upstream:
                    u_m = next((m for m in self.model.get("measures", []) if m.get("name") == u), None)
                    if self._is_measure_published(u) and self.config.include_markdown_links:
                        meas_link = self._get_measure_link(u)
                        link = f"[{u}]({meas_link})"
                    else:
                        ext_url = self.config.resolve_external_measure_url(u_m, self.model.get("tables", [])) if u_m else None
                        if ext_url and self.config.include_markdown_links:
                            link = f"[{u}]({ext_url}) *(External Measure)*"
                        else:
                            badge = " *(External Measure)*" if (u_m and (u_m.get("is_inherited") or u_m.get("is_external_measure"))) else ""
                            link = f"`[{u}]`{badge}"
                    lines.append(f"- {link}")

        if self.referenced_functions:
            lines.append("")
            lines.append("### Referenced User-Defined Functions (UDFs):")
            lines.append("This measure invokes the following custom model functions defined in `functions.tmdl`:")
            for fn_name in self.referenced_functions:
                sanitized_fn = sanitize_filename(fn_name)
                if self.config.base_doc_url:
                    functions_sub = self.config.functions_subdir.strip("/\\")
                    fn_url = join_doc_path(self.config.base_doc_url, functions_sub, f"{sanitized_fn}.md") if functions_sub else join_doc_path(self.config.base_doc_url, f"{sanitized_fn}.md")
                else:
                    fn_url = f"../../functions/{sanitized_fn}.md"
                fn_link = f"[`{fn_name}`]({fn_url})" if self.config.include_markdown_links else f"`{fn_name}`"
                lines.append(f"- {fn_link}")

        return "\n".join(lines)

    def _build_downstream_chapter(self) -> str:
        """Downstream Impact Analysis (Where Used)."""
        lines = [
            "## Downstream Impact Analysis (Where Used)",
            "",
        ]

        if not self.downstream:
            lines.append(
                "This measure is **not referenced by any other DAX measures**. "
                "It serves as an end-user indicator exposed directly to reports, visual cards, or dashboards."
            )
        else:
            lines.append(
                f"⚠️ **Impact Warning**: Modifying the logic or data type of this measure will directly affect **{len(self.downstream)}** downstream measures:"
            )
            lines.append("")
            for child in sorted(self.downstream):
                child_link = self._get_measure_link(child)
                link = f"[{child}]({child_link})" if self.config.include_markdown_links else f"`[{child}]`"
                lines.append(f"- {link}")

        return "\n".join(lines)

    def _build_columns_chapter(self) -> str:
        """Referenced Physical Columns & Tables."""
        lines = ["## Referenced Physical Columns & Tables"]

        if self.referenced_cols:
            lines.append("The DAX formula directly accesses the following fields from the data model:")
            lines.append("")
            for rc in self.referenced_cols:
                tbl = rc.get("table", "")
                col = rc.get("column", "")
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tables_sub = self.config.tables_subdir.strip("/\\")
                        t_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        t_url = f"../../tables/{clean_tbl}.md"
                    table_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        table_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        table_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    table_link = f"`{tbl}`"
                lines.append(f"- Table {table_link} ➔ Column `{col}`")
        elif self.referenced_tables:
            lines.append("The DAX formula references the following tables:")
            lines.append("")
            for tbl in self.referenced_tables:
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tables_sub = self.config.tables_subdir.strip("/\\")
                        t_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        t_url = f"../../tables/{clean_tbl}.md"
                    table_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        table_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        table_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    table_link = f"`{tbl}`"
                lines.append(f"- Table {table_link}")

        return "\n".join(lines)

    def _build_rag_hints_chapter(self) -> str:
        """RAG Semantic Context & Business Questions."""
        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Semantic retrieval guidance for AI assistants and Vector Search engines:",
            "",
            f"- **Business Concept**: `{self.name}` within the `{self.table}` domain.",
            f"- **Complexity Level**: Level {self.depth} in the Directed Acyclic Graph (DAG).",
            "- **Common Business Questions Answered by This Measure**:",
            f"  - What is the value or trend of `{self.name}`?",
            f"  - How is `{self.name}` calculated in the semantic model?",
            f"  - Which underlying metrics contribute to `{self.name}`?",
        ]

        if self.downstream:
            lines.append(f"  - If the logic of `{self.name}` changes, which other measures will be affected?")

        return "\n".join(lines)
