"""
Modular Markdown Document Generator for Data Model Tables.
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename


class TableDocBuilder:
    """
    Builds modular markdown chapters for a single table in the semantic model.
    """

    def __init__(self, table_data: Dict[str, Any], full_model: Dict[str, Any], config: Optional[DocGenConfig] = None):
        self.table = table_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.name = table_data.get("name", "UnnamedTable")
        self.role = table_data.get("role", "UNKNOWN")
        self.classification = table_data.get("classification_reasoning", {})
        self.columns = table_data.get("columns", [])
        self.measures = [
            m for m in full_model.get("measures", []) if m.get("table") == self.name
        ]
        self.snowflake_paths = table_data.get("snowflake_paths", [])

    def build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a pristine Markdown document."""
        sections = []

        # 1. Frontmatter
        if self.config.include_table_yaml_frontmatter:
            sections.append(self._build_frontmatter())

        # 2. Main Title & Semantic Overview
        sections.append(self._build_semantic_overview_chapter())

        # 3. Model Topology & Relationships (Star / Snowflake)
        if self.config.include_table_topology_section:
            sections.append(self._build_topology_chapter())

        # 4. Power Query (M) Lineage & Data Sources
        if self.config.include_table_lineage_section:
            sections.append(self._build_lineage_chapter())

        # 5. Incremental Refresh Policy
        if self.config.include_table_incremental_refresh:
            sections.append(self._build_incremental_refresh_chapter())

        # 6. Data Dictionary (Columns)
        if self.config.include_table_columns_dictionary:
            sections.append(self._build_columns_chapter())

        # 7. Hosted DAX Measures
        if self.config.include_table_measures_list and self.measures:
            sections.append(self._build_measures_chapter())

        # 8. RAG Semantic Retrieval Hints
        if self.config.include_table_rag_hints:
            sections.append(self._build_rag_hints_chapter())

        return "\n\n".join(sections) + "\n"

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG indexing and cataloging."""
        root_sources = [
            s.get("connection_string", s.get("source_type"))
            for s in self.table.get("root_data_sources", [])
        ]
        
        inc_policy = self.table.get("incremental_refresh_policy")
        has_inc_refresh = bool(inc_policy and inc_policy.get("is_enabled"))

        tags = ["semantic_model", "table", self.role.lower(), sanitize_filename(self.name)]
        if self.role == "FACT":
            tags.extend(["fact_table", "metrics"])
        elif self.role == "DIMENSION":
            tags.extend(["dimension", "attributes"])
        elif self.role == "LOOKUP_OUTRIGGER":
            tags.extend(["outrigger", "snowflake", "lookup"])
        elif self.role == "BRIDGE":
            tags.extend(["bridge_table", "mapping", "junction"])
        elif self.role == "DATE_DIMENSION":
            tags.extend(["date_dimension", "calendar", "time_intelligence"])

        if has_inc_refresh:
            tags.append("incremental_refresh")
            if inc_policy.get("mode") == "hybrid":
                tags.append("hybrid_table")

        # Filter out any excluded tables from metadata lists
        connected_dims = [
            d for d in self.table.get("connected_dimensions", [])
            if not self.config.is_table_excluded(d)
        ]
        connected_facts = [
            f for f in self.table.get("connected_facts", [])
            if not self.config.is_table_excluded(f)
        ]
        reachable_lookups = [
            l for l in self.table.get("reachable_lookup_tables", [])
            if not self.config.is_table_excluded(l)
        ]

        frontmatter_data = {
            "title": f"Table: {self.name}",
            "entity_name": self.name,
            "doc_type": "data_model_table",
            "role": self.role,
            "confidence_score": self.classification.get("confidence_score", 1.0),
            "columns_count": len(self.columns),
            "measures_count": len(self.measures),
            "has_incremental_refresh": has_inc_refresh,
            "is_inherited": self.table.get("is_inherited", False),
            "out_of_scope": self.table.get("out_of_scope", False),
            "source_type": self.table.get("source_type", "PowerQuery"),
            "root_sources": root_sources,
            "upstream_queries": self.table.get("upstream_queries_chain", []),
            "connected_dimensions": connected_dims,
            "connected_facts": connected_facts,
            "reachable_lookups": reachable_lookups,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_semantic_overview_chapter(self) -> str:
        """Chapter 1: Semantic Overview & Business Purpose."""
        lines = [
            f"# Table: `{self.name}`",
            "",
            f"**Architectural Role**: `{self.role}` | **Source**: `{self.table.get('source_type', 'PowerQuery')}` | **Columns**: `{len(self.columns)}` | **Associated Measures**: `{len(self.measures)}`",
            "",
            "## 1. Semantic Overview & Business Purpose",
        ]

        if self.table.get("description"):
            lines.append(f"> {self.table['description']}")
            lines.append("")

        if self.table.get("is_inherited"):
            ent_label = self.table.get("inherited_entity_name") or self.name
            src_label = f" (Source: `{self.table.get('inherited_expression_source')}`)" if self.table.get("inherited_expression_source") else ""
            lines.append(f"> ℹ️ **Inherited Entity**: This table is inherited from upstream semantic model entity `{ent_label}`{src_label}.")
            lines.append("")

        if self.table.get("source_type") == "CalculatedTable":
            lines.append("> 🧮 **DAX Calculated Table**: This table is dynamically computed within the data model using a DAX table expression.")
            lines.append("")

        if self.role == "FACT":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Fact Table**. "
                "It stores quantitative numeric measurements, aggregatable metrics, and transactional events. "
                "It serves as the analytical foundation of the model and is filtered by related dimension tables."
            )
        elif self.role == "DIMENSION":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Dimension Table**. "
                "It contains descriptive attributes, master data, or business entities used to slice, dice, group, "
                "and filter transactional facts."
            )
        elif self.role == "LOOKUP_OUTRIGGER":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Lookup / Outrigger (Snowflake Dimension)**. "
                "It represents a normalized secondary dimension that does not directly filter a fact table, "
                "but connects upstream to one or more dimensions to provide detailed attributes and hierarchies."
            )
        elif self.role == "DATE_DIMENSION":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Date / Calendar Dimension**. "
                "It provides the time dimension structure required for Time Intelligence calculations (YTD, Prior Year, MTD, Rolling periods)."
            )
        else:
            lines.append(f"The table **`{self.name}`** is part of the semantic model as a utility or calculated entity.")

        # Classification Rationale
        reasons = self.classification.get("criteria_matched", [])
        if reasons:
            lines.append("")
            lines.append("### Detected Classification Criteria:")
            for r in reasons:
                lines.append(f"- {r}")

        return "\n".join(lines)

    def _build_topology_chapter(self) -> str:
        """Chapter 2: Star Schema, Snowflake Outriggers & Relationships."""
        lines = ["## 2. Model Topology & Relationships"]

        # Connected Dimensions (if Fact) - filtered for excluded tables
        connected_dims = [
            dim for dim in self.table.get("connected_dimensions", [])
            if not self.config.is_table_excluded(dim)
        ]
        if connected_dims:
            lines.append("### Directly Connected Dimensions:")
            for dim in connected_dims:
                dim_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == dim), None)
                is_pub = self.config.is_table_published(dim_tbl) if dim_tbl else True
                if is_pub and self.config.include_markdown_links:
                    link = f"[{dim}]({sanitize_filename(dim)}.md)"
                else:
                    badge = " *(Inherited Entity)*" if (dim_tbl and dim_tbl.get("is_inherited")) else ""
                    link = f"`{dim}`{badge}"
                lines.append(f"- {link} (1:N Relationship)")

        # Connected Facts (if Dim) - filtered for excluded tables
        connected_facts = [
            fact for fact in self.table.get("connected_facts", [])
            if not self.config.is_table_excluded(fact)
        ]
        if connected_facts:
            lines.append("### Directly Filtered Fact Tables:")
            for fact in connected_facts:
                fact_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == fact), None)
                is_pub = self.config.is_table_published(fact_tbl) if fact_tbl else True
                if is_pub and self.config.include_markdown_links:
                    link = f"[{fact}]({sanitize_filename(fact)}.md)"
                else:
                    badge = " *(Inherited Entity)*" if (fact_tbl and fact_tbl.get("is_inherited")) else ""
                    link = f"`{fact}`{badge}"
                lines.append(f"- {link} (1:N Relationship)")

        # Snowflake Outrigger Paths - filtered for excluded tables
        if self.config.include_table_snowflake_paths and self.snowflake_paths:
            valid_paths = [
                p for p in self.snowflake_paths
                if not any(self.config.is_table_excluded(n) for n in p.get("path", []))
            ]
            if valid_paths:
                lines.append("")
                lines.append("### Transitive Snowflake Hierarchy (Reachable Lookups):")
                lines.append(
                    "The following lookup/outrigger tables can reach this Fact table through intermediate dimensions:"
                )
                for path_info in valid_paths:
                    path_nodes = path_info.get("path", [])
                    hops = path_info.get("hops", 1)
                    join_keys = path_info.get("join_keys", [])
                    
                    path_str = " ➔ ".join(f"`{n}`" for n in path_nodes)
                    lines.append(f"- **Path ({hops} hops)**: {path_str}")
                    if join_keys:
                        key_descs = [f"`{jk.get('from')}` ═▶ `{jk.get('to')}`" for jk in join_keys]
                        lines.append(f"  - *Join Keys*: {', '.join(key_descs)}")

        # Direct Relationships Table - filtered for excluded tables
        rel_list = [
            r for r in self.model.get("relationships", [])
            if (r.get("from_table") == self.name or r.get("to_table") == self.name)
            and not self.config.is_table_excluded(r.get("from_table"))
            and not self.config.is_table_excluded(r.get("to_table"))
        ]
        if rel_list:
            lines.append("")
            lines.append("### Active Direct Relationships:")
            lines.append("| Relationship ID | From (Many) | To (One) | Cardinality | Cross-Filtering | State |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for r in rel_list:
                status = "Active" if r.get("is_active", True) else "Inactive"
                from_field = f"`{r.get('from_table')}`[{r.get('from_column')}]"
                to_field = f"`{r.get('to_table')}`[{r.get('to_column')}]"
                lines.append(
                    f"| `{r.get('id')}` | {from_field} | {to_field} | {r.get('cardinality')} | {r.get('cross_filtering_behavior')} | {status} |"
                )

        return "\n".join(lines)

    def _build_lineage_chapter(self) -> str:
        """Chapter 3: Power Query (M) Lineage & Upstream Connectors or DAX Table Calculation."""
        if self.table.get("source_type") == "CalculatedTable":
            lines = [
                "## 3. DAX Table Expression & Lineage",
                "",
                "This table is dynamically computed in-memory within the semantic model using DAX, rather than loaded from an external Power Query data source.",
            ]
            calc_expr = self.table.get("expression")
            if calc_expr:
                lines.append("")
                lines.append("### DAX Table Formula:")
                lines.append("```dax")
                clean_calc_expr = calc_expr.strip()
                if clean_calc_expr.startswith("```"):
                    clean_calc_expr = re.sub(r'^```[a-zA-Z]*\r?\n?', '', clean_calc_expr)
                    clean_calc_expr = re.sub(r'\r?\n?\s*```\s*$', '', clean_calc_expr).strip()
                lines.append(clean_calc_expr)
                lines.append("```")
            else:
                lines.append("")
                lines.append("> ℹ️ *DAX calculation formula defined at partition level.*")

            ref_tables = self.table.get("referenced_tables", [])
            ref_cols = self.table.get("referenced_columns", [])
            ref_measures = self.table.get("referenced_measures", [])

            if ref_tables or ref_cols or ref_measures:
                lines.append("")
                lines.append("### Upstream Model References:")
                if ref_tables:
                    tbl_links = []
                    for t in ref_tables:
                        clean_t = sanitize_filename(t)
                        if self.config.is_table_published({"name": t, "is_inherited": False}):
                            tbl_links.append(f"[`{t}`]({clean_t}.md)")
                        else:
                            tbl_links.append(f"`{t}`")
                    lines.append(f"- **Referenced Tables**: {', '.join(tbl_links)}")
                if ref_cols:
                    col_strs = [f"`{rc.get('table', '')}`[{rc.get('column', '')}]" for rc in ref_cols]
                    lines.append(f"- **Referenced Columns**: {', '.join(col_strs)}")
                if ref_measures:
                    m_links = [f"`[{m}]`" for m in ref_measures]
                    lines.append(f"- **Referenced Measures**: {', '.join(m_links)}")

            return "\n".join(lines)

        lines = [
            "## 3. Power Query Lineage & Physical Sources",
            "",
            "This section traces data lineage from the original physical data source to table ingestion.",
        ]

        root_sources = self.table.get("root_data_sources", [])
        if root_sources:
            lines.append("")
            lines.append("### Physical Data Sources of Origin:")
            for s in root_sources:
                stype = s.get("source_type", "GENERIC")
                conn = s.get("connection_string", "N/A")
                server = s.get("server")
                db = s.get("database")
                desc = f"- **`[{stype}]`** `{conn}`"
                if server and db:
                    desc += f" (Server: `{server}`, Database: `{db}`)"
                lines.append(desc)

        upstream = self.table.get("upstream_queries_chain", [])
        if upstream:
            lines.append("")
            lines.append("### Staging Query Chain:")
            chain = " ➔ ".join(f"`{q}`" for q in upstream + [self.name])
            lines.append(f"{chain}")

        lineage_node = self.table.get("power_query_lineage")

        # Inline Table preview if defined via #table
        if lineage_node and lineage_node.get("is_inline_table") and lineage_node.get("inline_table_markdown"):
            lines.append("")
            lines.append("### In-Memory Inline Table Data (`#table`):")
            lines.append(lineage_node["inline_table_markdown"])

        # M Steps
        if lineage_node and lineage_node.get("steps"):
            steps = lineage_node.get("steps", [])
            lines.append("")
            lines.append(f"### Power Query Transformation Steps ({len(steps)} steps):")
            lines.append("| Step | Operation | Referenced Queries |")
            lines.append("| :--- | :--- | :--- |")
            for idx, st in enumerate(steps, 1):
                s_name = st.get("step_name", f"Step_{idx}")
                op = st.get("operation", "Transform")
                refs = ", ".join(f"`{r}`" for r in st.get("referenced_queries", [])) or "—"
                lines.append(f"| `#{idx} {s_name}` | {op} | {refs} |")

        # Full M Code snippet
        if self.config.include_table_m_code and lineage_node and lineage_node.get("full_m_expression"):
            lines.append("")
            lines.append("### Full Power Query M Expression:")
            lines.append("```powerquery")
            lines.append(lineage_node["full_m_expression"].strip())
            lines.append("```")

        return "\n".join(lines)

    def _build_incremental_refresh_chapter(self) -> str:
        """Chapter 4: Incremental Refresh Policy configuration and details."""
        policy = self.table.get("incremental_refresh_policy")
        is_enabled = bool(policy and policy.get("is_enabled"))

        lines = ["## 4. Incremental Refresh Policy", ""]

        if not is_enabled:
            if self.table.get("source_type") == "CalculatedTable":
                lines.extend([
                    "> ℹ️ **In-Memory Calculated Table**: This table is computed dynamically in-memory via DAX. "
                    "Incremental refresh policies do not apply to calculated tables."
                ])
            else:
                lines.extend([
                    "> ℹ️ **No Incremental Refresh Configured**: This table is loaded via standard full refresh. "
                    "All data is reprocessed during scheduled dataset refreshes without partition-level rolling windows."
                ])
            return "\n".join(lines)

        mode = policy.get("mode", "import")
        policy_type = policy.get("policy_type", "basic")
        rolling_periods = policy.get("rolling_window_periods")
        rolling_gran = policy.get("rolling_window_granularity")
        inc_periods = policy.get("incremental_periods")
        inc_gran = policy.get("incremental_granularity")
        polling_expr = policy.get("polling_expression")
        source_expr = policy.get("source_expression")

        rolling_desc = f"{rolling_periods} {rolling_gran.capitalize() if rolling_gran else ''}s" if rolling_periods is not None else "Not specified"
        inc_desc = f"{inc_periods} {inc_gran.capitalize() if inc_gran else ''}s" if inc_periods is not None else "Not specified"
        mode_badge = "⚡ Hybrid (Import + DirectQuery)" if mode == "hybrid" else f"`{mode}` (Import)"

        lines.extend([
            f"The table **`{self.name}`** utilizes an **Incremental Refresh Policy** to partition data, "
            "optimizing refresh duration and resource consumption in Power BI / Microsoft Fabric.",
            "",
            "### Policy Configuration Parameters:",
            "",
            "| Parameter | Configuration | Description |",
            "| :--- | :--- | :--- |",
            f"| **Status** | `Enabled` | Partitioned incremental refresh active. |",
            f"| **Policy Type** | `{policy_type}` | Type of incremental policy applied. |",
            f"| **Storage Mode** | {mode_badge} | Historical partitions mode and real-time handling. |",
            f"| **Historical Window (Store)** | `{rolling_desc}` | Total historical data retained across partitions. |",
            f"| **Refresh Window (Refresh)** | `{inc_desc}` | Rolling period refreshed during scheduled updates. |",
            f"| **Detect Data Changes** | {'`Enabled`' if polling_expr else '`Disabled`'} | Polling expression to refresh only changed partitions. |",
        ])

        if polling_expr:
            lines.extend([
                "",
                "### Detect Data Changes (Polling Expression):",
                "```powerquery",
                polling_expr.strip(),
                "```",
            ])

        if source_expr:
            lines.extend([
                "",
                "### Partition Source Filter Expression:",
                "```powerquery",
                source_expr.strip(),
                "```",
            ])

        lines.extend([
            "",
            "### Architectural & Query Folding Notes:",
            "- **Query Folding Requirement**: Power Query parameters `RangeStart` and `RangeEnd` must fold to the source database to ensure efficient partition filtering.",
            "- **Partition Lifecycle**: Partitions older than the historical window are dropped, while incremental periods are refreshed dynamically.",
        ])

        if mode == "hybrid":
            lines.append(
                "- **Hybrid Real-Time Capabilities**: DirectQuery is enabled for the latest partition, ensuring up-to-the-minute data visibility without waiting for a dataset refresh."
            )

        return "\n".join(lines)

    def _build_columns_chapter(self) -> str:
        """Chapter 5: Data Dictionary of Table Columns & Calculated Columns."""
        lines = [
            f"## 5. Columns Data Dictionary ({len(self.columns)} fields)",
            "",
            "| Column Name | Data Type | Type / Origin | Format | Description |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ]

        def _clean_cell(text: Optional[str]) -> str:
            if not text:
                return "—"
            # Escape pipes to avoid markdown table breaks
            s = str(text).replace("|", "\\|")
            # Flatten newlines to spaces so table rows don't break
            s = " ".join(s.split())
            return s or "—"

        calc_cols = []
        for col in self.columns:
            name = f"`{col.get('name')}`"
            dtype = f"`{col.get('data_type')}`"
            is_calc = col.get("is_calculated") or bool(col.get("expression"))
            if is_calc:
                calc_cols.append(col)
                col_type = "🧮 Calculated"
            elif col.get("is_key"):
                col_type = "🔑 Key"
            else:
                col_type = "Imported"

            fmt = f"`{col.get('format_string')}`" if col.get("format_string") else "—"

            desc_parts = []
            if col.get("description"):
                desc_parts.append(_clean_cell(col.get("description")))
            if is_calc:
                desc_parts.append("*(DAX formula below)*")
            desc = " ".join(desc_parts) or "—"

            lines.append(f"| {name} | {dtype} | {col_type} | {fmt} | {desc} |")

        # 5.1 Dedicated section for calculated column DAX expressions (safe from table breaks)
        if calc_cols:
            lines.append("")
            lines.append(f"### 5.1 Calculated Column DAX Formulas ({len(calc_cols)})")
            lines.append("")
            lines.append("The following columns are computed via DAX expressions in the model:")
            lines.append("")
            for cc in calc_cols:
                c_name = cc.get("name")
                c_type = cc.get("data_type", "string")
                c_fmt = cc.get("format_string") or "Default"
                c_desc = cc.get("description")
                c_expr = cc.get("expression") or ""
                c_expr_clean = c_expr.strip() if c_expr else "/* No formula available */"
                if c_expr_clean.startswith("```"):
                    c_expr_clean = re.sub(r'^```[a-zA-Z]*\r?\n?', '', c_expr_clean)
                    c_expr_clean = re.sub(r'\r?\n?\s*```\s*$', '', c_expr_clean).strip()

                lines.append(f"#### Calculated Column: `{c_name}`")
                lines.append(f"- **Data Type**: `{c_type}`")
                lines.append(f"- **Format**: `{c_fmt}`")
                if c_desc:
                    lines.append(f"- **Description**: {c_desc}")
                lines.append("- **DAX Formula**:")
                lines.append("```dax")
                lines.append(c_expr_clean)
                lines.append("```")
                lines.append("")

        return "\n".join(lines)

    def _build_measures_chapter(self) -> str:
        """Chapter 6: Measures residing in this table."""
        lines = [
            f"## 6. Associated DAX Measures ({len(self.measures)})",
            "",
            "The following calculated measures are defined within this table:",
            "",
            "| Measure | DAG Depth | Direct Dependencies | Format | Description |",
            "| :--- | :---: | :--- | :--- | :--- |",
        ]

        clean_tbl = sanitize_filename(self.name)
        meas_sub = self.config.measures_subdir.strip("/\\")
        for m in sorted(self.measures, key=lambda x: (x.get("calculation_depth", 0), x.get("name", ""))):
            m_name = m.get("name")
            sanitized = sanitize_filename(m_name)
            is_m_pub = self.config.is_measure_published(m)
            if is_m_pub and self.config.include_markdown_links:
                meas_path = f"../{meas_sub}/{clean_tbl}/{sanitized}.md" if meas_sub else f"../{clean_tbl}/{sanitized}.md"
                link = f"[{m_name}]({meas_path})"
            elif is_m_pub:
                link = f"`[{m_name}]`"
            else:
                link = f"`[{m_name}]` *(External)*"
            depth = f"Depth {m.get('calculation_depth', 0)}"
            deps = ", ".join(f"`[{d}]`" for d in m.get("direct_measure_dependencies", [])) or "— (Base Measure)"
            fmt = f"`{m.get('format_string')}`" if m.get("format_string") else "—"
            desc = m.get("description") or "—"

            lines.append(f"| {link} | {depth} | {deps} | {fmt} | {desc} |")

        return "\n".join(lines)

    def _build_rag_hints_chapter(self) -> str:
        """Chapter 7: RAG Semantic Retrieval Context & Natural Language QA."""
        col_names = [f"`{c.get('name')}`" for c in self.columns[:10]]
        sample_cols = ", ".join(col_names)
        if len(self.columns) > 10:
            sample_cols += f" and {len(self.columns) - 10} other columns"

        lines = [
            "## 7. Semantic Context for AI & RAG",
            "",
            "Synthesized context for semantic vector retrieval and AI search assistants:",
            "",
            f"- **Entity Represented**: {self.role.lower()} table named `{self.name}`.",
            f"- **Key Attributes**: {sample_cols}.",
        ]

        if self.table.get("source_type") == "CalculatedTable":
            lines.append("- **Computation Type**: In-memory DAX Calculated Table (`partition = calculated`).")
            if self.table.get("expression"):
                first_line = next(
                    (line.strip() for line in self.table.get("expression", "").splitlines() if line.strip()),
                    ""
                )
                if first_line:
                    clean_first_line = first_line.replace("`", "'")
                    lines.append(f"- **DAX Table Definition**: `{clean_first_line}`")

        if self.role == "FACT":
            lines.extend([
                "- **Resolvable Business Questions**:",
                f"  - What are the historical volumes and metrics recorded in `{self.name}`?",
                f"  - How are aggregated measures distributed across dimensions {', '.join(f'`{d}`' for d in self.table.get('connected_dimensions', []))}?",
                f"  - What totals are filtered through lookup tables {', '.join(f'`{l}`' for l in self.table.get('reachable_lookup_tables', []))}?",
            ])
        elif self.role in ("DIMENSION", "LOOKUP_OUTRIGGER"):
            lines.extend([
                "- **Resolvable Business Questions**:",
                f"  - What are the unique values, categories, or entities in `{self.name}`?",
                f"  - How do entities in `{self.name}` filter transactional metrics across connected tables?",
            ])

        return "\n".join(lines)
