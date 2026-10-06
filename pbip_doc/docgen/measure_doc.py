"""
Modular Markdown Document Generator for DAX Measures.
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename


class MeasureDocBuilder:
    """
    Builds modular markdown chapters for a single DAX measure in the semantic model.
    """

    def __init__(self, measure_data: Dict[str, Any], full_model: Dict[str, Any], config: Optional[DocGenConfig] = None):
        self.measure = measure_data
        self.model = full_model
        self.config = config or DocGenConfig()
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
        self.referenced_cols = [
            rc for rc in measure_data.get("referenced_columns", [])
            if not self.config.is_table_excluded(rc.get("table", ""))
        ]
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
        """Computes the relative markdown link to another measure file from measures/<Table>/<Measure>.md."""
        target_table = self.measure_table_map.get(target_measure_name, self.table)
        clean_target_tbl = sanitize_filename(target_table)
        clean_target_m = sanitize_filename(target_measure_name)
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
        if self.depth == 0:
            tags.append("base_measure")
        else:
            tags.append("composite_measure")

        col_refs_str = [f"{rc.get('table')}[{rc.get('column')}]" for rc in self.referenced_cols]

        frontmatter_data = {
            "title": f"Measure: [{self.name}]",
            "entity_name": self.name,
            "doc_type": "dax_measure",
            "table_name": self.table,
            "calculation_depth": self.depth,
            "is_base_measure": self.depth == 0,
            "is_inherited": self.measure.get("is_inherited", False),
            "is_external_measure": self.measure.get("is_external_measure", False),
            "out_of_scope": self.measure.get("out_of_scope", False),
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
            table_link = f"[{self.table}](../../tables/{clean_tbl}.md)"
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
            "## 1. Business Description & Purpose",
        ])

        if self.description:
            lines.append(f"> {self.description}")
            lines.append("")

        if self.measure.get("is_inherited") or self.measure.get("is_external_measure"):
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
        """Chapter 2: DAX Expression."""
        return "\n".join([
            "## 2. DAX Formula",
            "```dax",
            self.dax.strip() if self.dax else "-- No DAX expression provided",
            "```",
        ])

    def _build_upstream_chapter(self) -> str:
        """Chapter 3: Upstream Calculation Tree (Dependencies)."""
        lines = ["## 3. Upstream Calculation Tree (Direct and Transitive Dependencies)"]

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
                        badge = " *(External Measure)*" if (u_m and (u_m.get("is_inherited") or u_m.get("is_external_measure"))) else ""
                        link = f"`[{u}]`{badge}"
                    lines.append(f"- {link}")

        if self.referenced_functions:
            lines.append("")
            lines.append("### Referenced User-Defined Functions (UDFs):")
            lines.append("This measure invokes the following custom model functions defined in `functions.tmdl`:")
            for fn_name in self.referenced_functions:
                sanitized_fn = sanitize_filename(fn_name)
                fn_link = f"[`{fn_name}`](../../functions/{sanitized_fn}.md)" if self.config.include_markdown_links else f"`{fn_name}`"
                lines.append(f"- {fn_link}")

        return "\n".join(lines)

    def _build_downstream_chapter(self) -> str:
        """Chapter 4: Downstream Impact Analysis (Where Used)."""
        lines = [
            "## 4. Downstream Impact Analysis (Where Used)",
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
        """Chapter 5: Referenced Physical Columns & Tables."""
        lines = ["## 5. Referenced Physical Columns & Tables"]

        if self.referenced_cols:
            lines.append("The DAX formula directly accesses the following fields from the data model:")
            lines.append("")
            for rc in self.referenced_cols:
                tbl = rc.get("table", "")
                col = rc.get("column", "")
                clean_tbl = sanitize_filename(tbl)
                table_link = f"[{tbl}](../../tables/{clean_tbl}.md)" if self.config.include_markdown_links else f"`{tbl}`"
                lines.append(f"- Table {table_link} ➔ Column `{col}`")
        elif self.referenced_tables:
            lines.append("The DAX formula references the following tables:")
            lines.append("")
            for tbl in self.referenced_tables:
                clean_tbl = sanitize_filename(tbl)
                table_link = f"[{tbl}](../../tables/{clean_tbl}.md)" if self.config.include_markdown_links else f"`{tbl}`"
                lines.append(f"- Table {table_link}")

        return "\n".join(lines)

    def _build_rag_hints_chapter(self) -> str:
        """Chapter 6: RAG Semantic Context & Business Questions."""
        lines = [
            "## 6. Semantic Context for AI & RAG",
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
