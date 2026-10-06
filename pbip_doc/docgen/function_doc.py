"""
Modular Markdown Document Generator for DAX User-Defined Functions (UDFs).
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename


class FunctionDocBuilder:
    """
    Builds modular markdown chapters for a single DAX User-Defined Function (UDF).
    """

    def __init__(self, function_data: Dict[str, Any], full_model: Dict[str, Any], config: Optional[DocGenConfig] = None):
        self.fn = function_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.name = function_data.get("name", "UnnamedFunction")
        self.expression = function_data.get("expression", "")
        self.parameters = function_data.get("parameters", [])
        self.signature = function_data.get("parameters_signature", "()")
        self.return_type = function_data.get("return_type") or "Variant"
        self.description = function_data.get("description")
        self.downstream_measures = function_data.get("downstream_measures", [])
        self.downstream_functions = function_data.get("downstream_functions", [])
        self.referenced_functions = function_data.get("referenced_functions", [])
        self.referenced_cols = [
            rc for rc in function_data.get("referenced_columns", [])
            if not self.config.is_table_excluded(rc.get("table", ""))
        ]
        self.referenced_tables = [
            t for t in function_data.get("referenced_tables", [])
            if not self.config.is_table_excluded(t)
        ]

    def build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a pristine Markdown document."""
        sections = []

        # 1. Frontmatter
        if self.config.include_function_yaml_frontmatter:
            sections.append(self._build_frontmatter())

        # 2. Main Title & Identity Overview
        sections.append(self._build_identity_chapter())

        # 3. Parameters Specification
        if self.config.include_function_parameters_section and self.parameters:
            sections.append(self._build_parameters_chapter())

        # 4. Implementation Formula
        if self.config.include_function_formula_section:
            sections.append(self._build_formula_chapter())

        # 5. Downstream Impact Analysis (Where Used)
        if self.config.include_function_downstream_section:
            sections.append(self._build_downstream_chapter())

        # 6. Upstream Dependencies (if any)
        if self.referenced_functions or self.referenced_cols or self.referenced_tables:
            sections.append(self._build_upstream_chapter())

        # 7. Semantic Context for AI & RAG
        if self.config.include_function_rag_hints:
            sections.append(self._build_rag_hints_chapter())

        return "\n\n".join(sections) + "\n"

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG indexing and cataloging."""
        tags = [
            "semantic_model",
            "dax_udf_function",
            sanitize_filename(self.name),
        ]
        if not self.downstream_measures:
            tags.append("unused_function")
        else:
            tags.append("active_function")

        param_names = [p.get("name") for p in self.parameters if p.get("name")]

        frontmatter_data = {
            "title": f"Function: {self.name}",
            "entity_name": self.name,
            "doc_type": "dax_udf_function",
            "return_type": self.return_type,
            "parameters_count": len(self.parameters),
            "parameters_signature": self.signature,
            "parameter_names": param_names,
            "downstream_measures_count": len(self.downstream_measures),
            "downstream_measures": self.downstream_measures,
            "downstream_functions": self.downstream_functions,
            "referenced_functions": self.referenced_functions,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_identity_chapter(self) -> str:
        """Function Identity & Business Purpose."""
        sig_display = f"`{self.name}{self.signature}`"
        lines = [
            f"# Function: `{self.name}`",
            "",
            f"**Signature**: {sig_display} | **Return Type**: `{self.return_type}` | **Downstream Dependent Measures**: `{len(self.downstream_measures)}`",
            "",
            "## Business Description & Purpose",
        ]

        if self.description:
            lines.append(f"> {self.description}")
            lines.append("")

        lines.append(
            f"The User-Defined Function (UDF) **`{self.name}`** provides encapsulated, reusable DAX calculation logic "
            "defined at the semantic model level. It standardizes formulas across measures and enforces uniform evaluation rules."
        )

        return "\n".join(lines)

    def _build_parameters_chapter(self) -> str:
        """Parameters & Arguments Specification."""
        lines = [
            f"## Parameters & Arguments ({len(self.parameters)} parameters)",
            "",
            "| Parameter | Data Type | Optional | Default Value | Description |",
            "| :--- | :---: | :---: | :--- | :--- |",
        ]

        for p in self.parameters:
            p_name = f"`{p.get('name')}`"
            p_type = f"`{p.get('data_type')}`" if p.get("data_type") else "Variant"
            p_opt = "Yes" if p.get("is_optional") else "No (Required)"
            p_def = f"`{p.get('default_value')}`" if p.get("default_value") is not None else "—"
            p_desc = p.get("description") or "—"
            lines.append(f"| {p_name} | {p_type} | {p_opt} | {p_def} | {p_desc} |")

        return "\n".join(lines)

    def _build_formula_chapter(self) -> str:
        """Implementation Formula."""
        lines = [
            "## Implementation Formula",
            "```dax",
            f"function {self.name} = {self.signature} =>",
        ]
        body = self.expression.strip() if self.expression else "/* No implementation provided */"
        # Indent body
        for line in body.splitlines():
            lines.append(f"    {line}")
        lines.append("```")
        return "\n".join(lines)

    def _build_downstream_chapter(self) -> str:
        """Downstream Impact Analysis (Where Used)."""
        lines = [
            "## Downstream Impact Analysis (Where Used)",
            "",
        ]

        if not self.downstream_measures and not self.downstream_functions:
            lines.append(
                "This function is currently **not invoked by any DAX measures or functions** in the semantic model. "
                "It is available in `functions.tmdl` for future measure calculations."
            )
            return "\n".join(lines)

        total_downstream = len(self.downstream_measures) + len(self.downstream_functions)
        lines.append(
            f"⚠️ **Impact Warning**: Modifying the logic, parameter types, or return value of this function will directly "
            f"affect **{total_downstream}** downstream model objects."
        )
        lines.append("")

        if self.downstream_measures:
            lines.append(f"### Directly Dependent Measures ({len(self.downstream_measures)}):")
            lines.append("")
            lines.append("| Measure | Home Table | DAG Depth | Document Link |")
            lines.append("| :--- | :--- | :---: | :--- |")

            # Look up home table and depth for each measure
            measure_lookup = {m.get("name"): m for m in self.model.get("measures", [])}
            for m_name in sorted(self.downstream_measures):
                m_info = measure_lookup.get(m_name, {})
                tbl = m_info.get("table", "Model")
                clean_tbl = sanitize_filename(tbl)
                depth = f"Depth {m_info.get('calculation_depth', 0)}"
                sanitized = sanitize_filename(m_name)
                link = f"[`[{m_name}]`](../measures/{clean_tbl}/{sanitized}.md)" if self.config.include_markdown_links else f"`[{m_name}]`"
                doc_link = f"[View Measure Document](../measures/{clean_tbl}/{sanitized}.md)" if self.config.include_markdown_links else "—"
                lines.append(f"| {link} | `{tbl}` | {depth} | {doc_link} |")

        if self.downstream_functions:
            lines.append("")
            lines.append(f"### Directly Dependent Functions ({len(self.downstream_functions)}):")
            for fn_child in sorted(self.downstream_functions):
                sanitized = sanitize_filename(fn_child)
                fn_link = f"[{fn_child}]({sanitized}.md)" if self.config.include_markdown_links else f"`{fn_child}`"
                lines.append(f"- {fn_link}")

        return "\n".join(lines)

    def _build_upstream_chapter(self) -> str:
        """Upstream Dependencies & Referenced Objects."""
        lines = [
            "## Upstream Dependencies & Referenced Model Objects",
            "",
        ]

        if self.referenced_functions:
            lines.append("### Referenced UDF Functions:")
            for fn_dep in self.referenced_functions:
                sanitized = sanitize_filename(fn_dep)
                link = f"[{fn_dep}]({sanitized}.md)" if self.config.include_markdown_links else f"`{fn_dep}`"
                lines.append(f"- {link}")
            lines.append("")

        if self.referenced_cols:
            lines.append("### Referenced Physical Columns:")
            for rc in self.referenced_cols:
                tbl = rc.get("table", "")
                col = rc.get("column", "")
                clean_tbl = sanitize_filename(tbl)
                tbl_link = f"[{tbl}](../tables/{clean_tbl}.md)" if self.config.include_markdown_links else f"`{tbl}`"
                lines.append(f"- Table {tbl_link} ➔ Column `{col}`")
            lines.append("")
        elif self.referenced_tables:
            lines.append("### Referenced Physical Tables:")
            for tbl in self.referenced_tables:
                clean_tbl = sanitize_filename(tbl)
                tbl_link = f"[{tbl}](../tables/{clean_tbl}.md)" if self.config.include_markdown_links else f"`{tbl}`"
                lines.append(f"- Table {tbl_link}")
            lines.append("")

        return "\n".join(lines)

    def _build_rag_hints_chapter(self) -> str:
        """Semantic Context for AI & RAG."""
        param_desc = ", ".join(f"`{p.get('name')}`" for p in self.parameters) or "No parameters"
        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Semantic retrieval guidance for AI assistants and Vector Search engines:",
            "",
            f"- **Entity Represented**: DAX User-Defined Function (UDF) named `{self.name}`.",
            f"- **Signature & Contract**: Returns `{self.return_type}` given parameters ({param_desc}).",
            "- **Common Business Questions Answered by This Function**:",
            f"  - What does the function `{self.name}` compute in the semantic model?",
            f"  - What input parameters are required to invoke `{self.name}`?",
            f"  - Which measures or KPIs depend on `{self.name}`?",
        ]

        if self.downstream_measures:
            lines.append(
                f"  - If the logic of `{self.name}` is changed, which measures are impacted? ({', '.join(f'`[{m}]`' for m in self.downstream_measures[:5])}{'...' if len(self.downstream_measures) > 5 else ''})"
            )

        return "\n".join(lines)
