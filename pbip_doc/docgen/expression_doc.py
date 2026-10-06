"""
Modular Markdown Document Generator for Power Query (M) Expressions and Shared ETL Queries.
Supports Staging Queries, Parameters, Custom Functions, and Inline Tables (#table).
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

import re
from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename
from ..m_table_parser import parse_m_inline_table


class ExpressionDocBuilder:
    """
    Builds modular markdown documentation for a single Power Query expression / shared staging query.
    """

    def __init__(self, expr_data: Dict[str, Any], full_model: Dict[str, Any], config: Optional[DocGenConfig] = None):
        self.expr = expr_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.name = expr_data.get("query_name", "UnnamedExpression")
        self.is_staging = expr_data.get("is_staging", True)
        self.full_m = expr_data.get("full_m_expression", "")
        self.steps = expr_data.get("steps", [])
        self.direct_deps = expr_data.get("direct_dependencies", [])
        self.upstream_queries = expr_data.get("all_upstream_queries", [])
        self.downstream_queries = expr_data.get("downstream_queries", [])
        self.downstream_tables = [
            t for t in expr_data.get("downstream_tables", [])
            if not self.config.is_table_excluded(t)
        ]
        self.root_sources = expr_data.get("root_sources", [])
        self.description = expr_data.get("description")
        self.query_group = expr_data.get("query_group")
        self.lineage_tag = expr_data.get("lineage_tag")

        # Classify expression category
        self.expression_type = self._classify_expression_type()

        # Parse inline table if applicable
        self.is_inline_table = expr_data.get("is_inline_table", False)
        self.inline_cols = expr_data.get("inline_table_columns", [])
        self.inline_types = expr_data.get("inline_table_column_types", {})
        self.inline_rows = expr_data.get("inline_table_rows", [])
        self.inline_md = expr_data.get("inline_table_markdown")

        if not self.is_inline_table and "#table" in self.full_m:
            parsed = parse_m_inline_table(self.full_m)
            if parsed:
                self.is_inline_table = True
                self.inline_cols = parsed.columns
                self.inline_types = parsed.column_types
                self.inline_rows = parsed.rows
                self.inline_md = parsed.to_markdown_table()

    def _classify_expression_type(self) -> str:
        """Determines if the expression is an inline table, parameter, function, or staging query."""
        if "#table" in self.full_m:
            return "INLINE_TABLE"
        if "meta [IsParameterQuery=true" in self.full_m or "IsParameterQueryRequired" in self.full_m:
            return "PARAMETER"
        if re.search(r'^\s*(\([^\)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*=>', self.full_m, re.MULTILINE):
            return "CUSTOM_FUNCTION"
        return "STAGING_QUERY"

    def build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a complete Markdown document."""
        sections = []

        # 1. Frontmatter
        if self.config.include_expression_yaml_frontmatter:
            sections.append(self._build_frontmatter())

        # 2. Main Title & Semantic Overview
        if self.config.include_expression_overview_section:
            sections.append(self._build_overview_chapter())

        # 3. Inline Table Data Preview (#table)
        if self.config.include_expression_inline_table and self.is_inline_table and self.inline_md:
            sections.append(self._build_inline_table_chapter())

        # 4. Power Query Lineage & Dependency Graph
        if self.config.include_expression_lineage_section:
            sections.append(self._build_lineage_chapter())

        # 5. Transformation Steps Breakdown
        if self.config.include_expression_steps_section and self.steps:
            sections.append(self._build_steps_chapter())

        # 6. Full Power Query M Expression
        if self.config.include_expression_m_code and self.full_m:
            sections.append(self._build_m_code_chapter())

        # 7. Semantic Context for AI & RAG
        if self.config.include_expression_rag_hints:
            sections.append(self._build_rag_hints_chapter())

        return "\n\n".join(sections) + "\n"

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG vector indexing."""
        tags = ["power_query", "expression", "etl", self.expression_type.lower(), sanitize_filename(self.name)]
        if self.is_inline_table:
            tags.extend(["inline_table", "table_literal", "static_lookup"])
        elif self.expression_type == "PARAMETER":
            tags.extend(["parameter", "configuration"])
        elif self.expression_type == "CUSTOM_FUNCTION":
            tags.extend(["custom_function", "m_function"])
        else:
            tags.extend(["staging_query", "data_transformation"])

        root_source_strings = [
            s.get("connection_string", s.get("source_type"))
            for s in self.root_sources
        ]

        frontmatter_data = {
            "title": f"Expression: {self.name}",
            "entity_name": self.name,
            "doc_type": "power_query_expression",
            "expression_type": self.expression_type,
            "is_inline_table": self.is_inline_table,
            "is_staging": self.is_staging,
            "steps_count": len(self.steps),
            "direct_dependencies": self.direct_deps,
            "upstream_queries": self.upstream_queries,
            "downstream_queries": self.downstream_queries,
            "downstream_tables": self.downstream_tables,
            "root_sources": root_source_strings,
            "query_group": self.query_group,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_overview_chapter(self) -> str:
        """Chapter 1: Expression Overview & Business Purpose."""
        type_badges = {
            "INLINE_TABLE": "📊 `INLINE_TABLE` (#table)",
            "PARAMETER": "⚙️ `PARAMETER`",
            "CUSTOM_FUNCTION": "λ `CUSTOM_FUNCTION`",
            "STAGING_QUERY": "🔄 `STAGING_QUERY` (ETL Transformation)",
        }
        badge = type_badges.get(self.expression_type, f"`{self.expression_type}`")

        lines = [
            f"# Expression: `{self.name}`",
            "",
            f"**Type**: {badge} | **Steps**: `{len(self.steps)}` | **Downstream Tables**: `{len(self.downstream_tables)}` | **Sources**: `{len(self.root_sources)}`",
            "",
            "## 1. Overview & ETL Purpose",
        ]

        if self.description:
            lines.append(f"> {self.description}")
            lines.append("")

        if self.expression_type == "INLINE_TABLE":
            col_count = len(self.inline_cols)
            row_count = len(self.inline_rows)
            lines.append(
                f"The expression **`{self.name}`** defines an in-memory, static **Inline Table (`#table`)** "
                f"containing **{col_count} columns** and **{row_count} rows**. "
                "It serves as a hardcoded reference dataset, lookup table, or static mapping matrix within the semantic model."
            )
        elif self.expression_type == "PARAMETER":
            lines.append(
                f"The expression **`{self.name}`** is an ETL **Parameter**. "
                "It parameterizes connection endpoints, environment settings, or query filters, "
                "enabling dynamic deployment across environments (Dev, Test, Prod)."
            )
        elif self.expression_type == "CUSTOM_FUNCTION":
            lines.append(
                f"The expression **`{self.name}`** is a reusable **Power Query Custom Function**. "
                "It encapsulates transformation logic invoked across multiple queries or row-level operations."
            )
        else:
            lines.append(
                f"The expression **`{self.name}`** is a Power Query **Staging / Intermediate ETL Query**. "
                "It extracts, cleanses, and reshapes data from physical sources or upstream queries before loading into destination tables."
            )

        if self.query_group:
            lines.append(f"- **Query Folder / Group**: `{self.query_group}`")

        return "\n".join(lines)

    def _build_inline_table_chapter(self) -> str:
        """Chapter 2: Rendered Markdown Table for #table definitions."""
        lines = [
            "## 2. Inline Table Definition (`#table`)",
            "",
            f"This expression contains a static in-memory table defined via `#table` with **{len(self.inline_cols)} columns** and **{len(self.inline_rows)} rows**:",
            "",
        ]

        if self.inline_types:
            type_items = [f"`{col}`: *{t}*" for col, t in self.inline_types.items()]
            lines.append(f"- **Column Types**: {', '.join(type_items)}")
            lines.append("")

        lines.append(self.inline_md)
        return "\n".join(lines)

    def _build_lineage_chapter(self) -> str:
        """Chapter 3: Lineage, Upstream Data Sources & Downstream Consumer Tables."""
        lines = [
            "## 3. Power Query Lineage & Dependencies",
            "",
            "This section maps data flow through this expression across the ETL compartment.",
        ]

        # Physical data sources
        if self.root_sources:
            lines.append("")
            lines.append("### Physical Data Sources of Origin:")
            for s in self.root_sources:
                stype = s.get("source_type", "GENERIC")
                conn = s.get("connection_string", "N/A")
                server = s.get("server")
                db = s.get("database")
                desc = f"- **`[{stype}]`** `{conn}`"
                if server and db:
                    desc += f" (Server: `{server}`, Database: `{db}`)"
                lines.append(desc)

        # Upstream dependencies
        if self.direct_deps:
            lines.append("")
            lines.append("### Directly Referenced Queries:")
            for dep in self.direct_deps:
                clean_dep = sanitize_filename(dep)
                link = f"[{dep}]({clean_dep}.md)" if self.config.include_markdown_links else f"`{dep}`"
                lines.append(f"- {link}")

        # Downstream queries
        if self.downstream_queries:
            lines.append("")
            lines.append("### Downstream Queries Consuming this Expression:")
            for dq in self.downstream_queries:
                clean_dq = sanitize_filename(dq)
                link = f"[{dq}]({clean_dq}.md)" if self.config.include_markdown_links else f"`{dq}`"
                lines.append(f"- {link}")

        # Target model tables
        if self.downstream_tables:
            lines.append("")
            lines.append("### Final Model Tables Loaded from this Pipeline:")
            tables_sub = self.config.tables_subdir.strip("/\\")
            for tbl in self.downstream_tables:
                clean_tbl = sanitize_filename(tbl)
                rel_prefix = f"../{tables_sub}/" if tables_sub else "../"
                link = f"[{tbl}]({rel_prefix}{clean_tbl}.md)" if self.config.include_markdown_links else f"`{tbl}`"
                lines.append(f"- {link}")
        else:
            lines.append("")
            lines.append("> ℹ️ **Unloaded / Utility Query**: This expression is not loaded directly into a model table. It serves as an intermediate staging query or configuration parameter.")

        return "\n".join(lines)

    def _build_steps_chapter(self) -> str:
        """Chapter 4: Power Query Steps Breakdown."""
        lines = [
            f"## 4. Transformation Steps ({len(self.steps)} steps)",
            "",
            "Step-by-step transformations executed within the `let ... in` block:",
            "",
            "| Step | Operation | Referenced Queries |",
            "| :--- | :--- | :--- |",
        ]

        for idx, st in enumerate(self.steps, 1):
            s_name = st.get("step_name", f"Step_{idx}")
            op = st.get("operation", "Transformation")
            refs = ", ".join(f"`{r}`" for r in st.get("referenced_queries", [])) or "—"
            lines.append(f"| `#{idx} {s_name}` | {op} | {refs} |")

        return "\n".join(lines)

    def _build_m_code_chapter(self) -> str:
        """Chapter 5: Full M Expression."""
        lines = [
            "## 5. Full Power Query M Expression",
            "",
            "```powerquery",
            self.full_m.strip(),
            "```",
        ]
        return "\n".join(lines)

    def _build_rag_hints_chapter(self) -> str:
        """Chapter 6: RAG Semantic Retrieval Context."""
        lines = [
            "## 6. Semantic Context for AI & RAG",
            "",
            "Synthesized context for semantic vector search and AI assistants:",
            "",
            f"- **Entity Type**: Power Query expression of type `{self.expression_type}`.",
            f"- **Primary Responsibility**: {self._synthesize_ai_summary()}",
        ]

        if self.downstream_tables:
            tables_str = ", ".join(f"`{t}`" for t in self.downstream_tables)
            lines.append(f"- **Impacted Data Model Tables**: {tables_str}.")

        lines.extend([
            "- **Resolvable ETL & Business Questions**:",
            f"  - How is data ingested and transformed before reaching downstream tables?",
            f"  - What data sources or parameters does `{self.name}` rely on?",
            f"  - What happens if the schema or transformations in `{self.name}` are modified?",
        ])

        return "\n".join(lines)

    def _synthesize_ai_summary(self) -> str:
        """Generates a concise 1-sentence summary of what this expression does."""
        if self.is_inline_table:
            return f"Provides an in-memory static lookup table with columns {', '.join(f'`{c}`' for c in self.inline_cols[:5])}."
        if self.expression_type == "PARAMETER":
            return f"Configures environment or connection parameter `{self.name}`."
        if self.expression_type == "CUSTOM_FUNCTION":
            return f"Encapsulates reusable Power Query M transformation function `{self.name}`."
        if self.downstream_tables:
            return f"Staging transformation pipeline feeding model table(s) {', '.join(f'`{t}`' for t in self.downstream_tables)}."
        return f"Intermediate ETL transformation step in Power Query."
