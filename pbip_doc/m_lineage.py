"""
Power Query (M) Lineage Resolver.
Analyzes M expressions, detects connector source calls, and resolves
multi-step query dependencies transitively from raw data sources to final model tables.
Vanilla Python implementation.
"""

import re
from typing import Dict, List, Set, Tuple, Optional, Any
from .model_schema import PowerQuerySource, PowerQueryLineageNode, PowerQueryLineageStep
from .m_table_parser import parse_m_inline_table


class MLineageResolver:
    """
    Parses Power Query M code, tracks inter-query dependencies,
    and extracts original data sources (SQL, SharePoint, Web, Excel, etc.).
    """

    CONNECTOR_PATTERNS = [
        # SQL / Relational
        (r'\bSql\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "SQL_SERVER", "server_db"),
        (r'\bSql\.Databases\s*\(\s*["\']([^"\']+)["\']', "SQL_SERVER", "server_only"),
        (r'\bPostgreSQL\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "POSTGRESQL", "server_db"),
        (r'\bMySQL\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "MYSQL", "server_db"),
        (r'\bOracle\.Database\s*\(\s*["\']([^"\']+)["\']', "ORACLE", "server_only"),
        (r'\bSnowflake\.Databases\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "SNOWFLAKE", "server_db"),
        (r'\bGoogleBigQuery\.Database\s*\(', "BIGQUERY", "generic"),
        
        # Files & Storage
        (r'\bExcel\.Workbook\s*\(\s*File\.Contents\s*\(\s*["\']([^"\']+)["\']', "EXCEL_FILE", "filepath"),
        (r'\bCsv\.Document\s*\(\s*File\.Contents\s*\(\s*["\']([^"\']+)["\']', "CSV_FILE", "filepath"),
        (r'\bFile\.Contents\s*\(\s*["\']([^"\']+)["\']', "LOCAL_FILE", "filepath"),
        (r'\bFolder\.Files\s*\(\s*["\']([^"\']+)["\']', "FOLDER", "filepath"),
        (r'\bSharePoint\.Files\s*\(\s*["\']([^"\']+)["\']', "SHAREPOINT", "url"),
        (r'\bSharePoint\.Tables\s*\(\s*["\']([^"\']+)["\']', "SHAREPOINT", "url"),
        (r'\bAzureStorage\.BlobContents\s*\(\s*["\']([^"\']+)["\']', "AZURE_BLOB", "url"),
        (r'\bAzureStorage\.DataLake\s*\(\s*["\']([^"\']+)["\']', "AZURE_DATALAKE", "url"),
        (r'\bFabric\.Lakehouse\s*\(\s*["\']([^"\']+)["\']', "FABRIC_LAKEHOUSE", "endpoint"),
        
        # Web & OData APIs & ODBC
        (r'\bOData\.Feed\s*\(\s*["\']([^"\']+)["\']', "ODATA", "url"),
        (r'\bWeb\.Contents\s*\(\s*["\']([^"\']+)["\']', "WEB_API", "url"),
        (r'\bWeb\.BrowserContents\s*\(\s*["\']([^"\']+)["\']', "WEB_BROWSER", "url"),
        (r'\bOdbc\.DataSource\s*\(\s*["\']([^"\']+)["\']', "ODBC", "url"),
        (r'\bOdbc\.Query\s*\(\s*["\']([^"\']+)["\']', "ODBC", "url"),
        (r'\bSalesforce\.Data\s*\(', "SALESFORCE", "generic"),
    ]

    def __init__(self, raw_queries: Dict[str, Dict[str, Any]]):
        """
        raw_queries: dictionary of query_name -> {
            "m_code": str,
            "target_table": Optional[str],
            "is_staging": bool
        }
        """
        self.raw_queries = raw_queries
        self.known_query_names = set(raw_queries.keys())
        self.nodes: Dict[str, PowerQueryLineageNode] = {}
        self._build_nodes()
        self._resolve_transitive_lineage()

    def _strip_string_literals(self, m_code: str) -> str:
        """Removes regular string literals '\"...\"' while preserving '#\"...\"' identifiers."""
        # Replace #"..." temporarily with a placeholder token
        quoted_identifiers = re.findall(r'#"[^"]+"', m_code)
        placeholder_map = {}
        for i, q in enumerate(quoted_identifiers):
            token = f"___QUOTED_ID_{i}___"
            placeholder_map[token] = q
            m_code = m_code.replace(q, token, 1)

        # Now remove string literals
        m_code_no_strings = re.sub(r'"[^"]*"', '""', m_code)

        # Restore quoted identifiers
        for token, original in placeholder_map.items():
            m_code_no_strings = m_code_no_strings.replace(token, original)

        return m_code_no_strings

    def _extract_quoted_identifiers(self, m_code: str) -> Set[str]:
        """Extracts #"Query Name" references."""
        matches = re.findall(r'#"[^"]+"', m_code)
        # Strip #" and "
        cleaned = {m[2:-1] for m in matches}
        return cleaned

    def _extract_word_identifiers(self, m_code: str, local_steps: Set[str]) -> Set[str]:
        """Extracts unquoted identifiers that match known queries, excluding string literals and local step names."""
        code_clean = self._strip_string_literals(m_code)
        # Find all valid M identifiers
        tokens = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_clean))
        # Exclude local step variables defined in this query
        external_tokens = tokens - local_steps
        return external_tokens.intersection(self.known_query_names)

    def _extract_sources(self, m_code: str) -> List[PowerQuerySource]:
        """Scans M code for connector source calls."""
        sources: List[PowerQuerySource] = []

        for pattern, source_type, mode in self.CONNECTOR_PATTERNS:
            for match in re.finditer(pattern, m_code, re.IGNORECASE):
                snippet = match.group(0)
                if mode == "server_db":
                    server = match.group(1)
                    db = match.group(2)
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string=f"{server} / {db}",
                            server=server,
                            database=db,
                            raw_snippet=snippet,
                        )
                    )
                elif mode == "server_only":
                    server = match.group(1)
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string=server,
                            server=server,
                            raw_snippet=snippet,
                        )
                    )
                elif mode in ("filepath", "url", "endpoint"):
                    val = match.group(1)
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string=val,
                            endpoint_or_path=val,
                            raw_snippet=snippet,
                        )
                    )
                else:
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string="Cloud Service / API",
                            raw_snippet=snippet,
                        )
                    )

        # Fallback detection for inline data or parameters
        if not sources:
            if "#table(" in m_code or "Table.FromRows" in m_code or "Table.FromRecords" in m_code:
                sources.append(
                    PowerQuerySource(
                        source_type="MANUAL_INLINE",
                        connection_string="Inline Table.FromRows / Static M Table",
                    )
                )

        return sources

    def _extract_steps(self, m_code: str) -> List[PowerQueryLineageStep]:
        """Extracts individual transformation steps inside a 'let ... in' block."""
        steps: List[PowerQueryLineageStep] = []
        
        # Match lines like: StepName = FunctionCall(...)
        # or #"Step Name" = FunctionCall(...)
        step_pattern = re.compile(
            r'^\s*(#"[^"]+"|[a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)(?=,\s*[\r\n]+|\s+in\s+|$)',
            re.MULTILINE | re.DOTALL,
        )

        for match in step_pattern.finditer(m_code):
            raw_name = match.group(1).strip()
            step_name = raw_name[2:-1] if raw_name.startswith('#"') and raw_name.endswith('"') else raw_name
            step_body = match.group(2).strip()

            # Identify operation category
            op = "Transformation"
            if any(k in step_body.lower() for k in [
                "sql.", "postgresql.", "mysql.", "oracle.", "snowflake.", "bigquery.",
                "odata.", "sharepoint.", "file.", "excel.", "csv.", "web.", "folder.",
                "azurestorage.", "fabric.", "odbc.", "salesforce."
            ]):
                op = "Source Connection"
            elif "Table.NestedJoin" in step_body:
                op = "Merge / Nested Join"
            elif "Table.Combine" in step_body:
                op = "Append Queries"
            elif "Table.SelectRows" in step_body:
                op = "Filter Rows"
            elif "Table.SelectColumns" in step_body or "Table.RemoveColumns" in step_body:
                op = "Column Projection"
            elif "Table.TransformColumnTypes" in step_body:
                op = "Type Casting"
            elif "Table.AddColumn" in step_body:
                op = "Calculated Column"
            elif "Table.Group" in step_body:
                op = "Group By / Aggregation"
            elif "Table.ExpandTableColumn" in step_body:
                op = "Expand Related Table"

            # Check if this step references any other top-level queries
            step_deps: Set[str] = set()
            for q_name in self.known_query_names:
                escaped = f'#"{q_name}"'
                if escaped in step_body or (q_name.isidentifier() and re.search(r'\b' + re.escape(q_name) + r'\b', step_body)):
                    step_deps.add(q_name)

            steps.append(
                PowerQueryLineageStep(
                    step_name=step_name,
                    operation=op,
                    referenced_queries=sorted(list(step_deps)),
                    raw_m_code=step_body[:250] + ("..." if len(step_body) > 250 else ""),
                )
            )

        return steps

    def _build_nodes(self):
        """Initial pass: parse dependencies and immediate sources for each query."""
        for query_name, info in self.raw_queries.items():
            m_code = info.get("m_code", "")
            target_table = info.get("target_table")
            is_staging = info.get("is_staging", False)

            steps = self._extract_steps(m_code)
            local_step_names = {s.step_name for s in steps}

            # References to other queries:
            # 1. Quoted references: #"Other Query"
            quoted_refs = self._extract_quoted_identifiers(m_code)
            # 2. Identifier references matching known query names (excluding local step names)
            ident_refs = self._extract_word_identifiers(m_code, local_step_names)
            
            all_refs = (quoted_refs | ident_refs) - {query_name}
            # Only retain references that are actual queries in our model
            direct_deps = sorted(list(all_refs.intersection(self.known_query_names)))

            immediate_sources = self._extract_sources(m_code)

            # Detect inline table (#table)
            inline_tbl = parse_m_inline_table(m_code)
            is_inline = inline_tbl is not None
            inline_cols = inline_tbl.columns if inline_tbl else []
            inline_types = inline_tbl.column_types if inline_tbl else {}
            inline_rows = inline_tbl.rows if inline_tbl else []
            inline_md = inline_tbl.to_markdown_table() if inline_tbl else None

            description = info.get("description")
            query_group = info.get("query_group")
            lineage_tag = info.get("lineage_tag")
            kind = info.get("kind")

            self.nodes[query_name] = PowerQueryLineageNode(
                query_name=query_name,
                target_table=target_table or (query_name if not is_staging else None),
                is_staging=is_staging,
                direct_dependencies=direct_deps,
                root_sources=immediate_sources,
                full_m_expression=m_code,
                steps=steps,
                description=description,
                query_group=query_group,
                lineage_tag=lineage_tag,
                expression_kind=kind,
                is_inline_table=is_inline,
                inline_table_columns=inline_cols,
                inline_table_column_types=inline_types,
                inline_table_rows=inline_rows,
                inline_table_markdown=inline_md,
            )

    def _resolve_transitive_lineage(self):
        """
        Computes transitive upstream dependencies, propagates root sources,
        and computes downstream queries and downstream final model tables.
        """
        # First compute downstream pointers
        for name, node in self.nodes.items():
            for dep in node.direct_dependencies:
                if dep in self.nodes:
                    if name not in self.nodes[dep].downstream_queries:
                        self.nodes[dep].downstream_queries.append(name)

        # Transitive closure for all_upstream_queries and root_sources
        for query_name, node in self.nodes.items():
            visited: Set[str] = set()
            all_sources: Dict[str, PowerQuerySource] = {}

            # Add direct sources
            for s in node.root_sources:
                key = f"{s.source_type}:{s.connection_string}"
                all_sources[key] = s

            # Breadth-first / depth-first search for ancestors
            queue = list(node.direct_dependencies)
            while queue:
                curr = queue.pop(0)
                if curr in visited or curr not in self.nodes or curr == query_name:
                    continue
                visited.add(curr)
                parent_node = self.nodes[curr]

                # Inherit root sources from parent
                for s in parent_node.root_sources:
                    key = f"{s.source_type}:{s.connection_string}"
                    all_sources[key] = s

                # Queue grandparents
                for p_dep in parent_node.direct_dependencies:
                    if p_dep not in visited:
                        queue.append(p_dep)

            node.all_upstream_queries = sorted(list(visited))
            node.root_sources = list(all_sources.values())

        # Now compute downstream final tables for all queries (especially staging)
        for query_name, node in self.nodes.items():
            downstream_tables: Set[str] = set()
            visited: Set[str] = set()
            queue = list(node.downstream_queries)

            if node.target_table:
                downstream_tables.add(node.target_table)

            while queue:
                curr = queue.pop(0)
                if curr in visited or curr not in self.nodes:
                    continue
                visited.add(curr)
                child_node = self.nodes[curr]
                if child_node.target_table:
                    downstream_tables.add(child_node.target_table)
                queue.extend(child_node.downstream_queries)

            node.downstream_tables = sorted(list(downstream_tables))

    def get_lineage_for_table(self, table_name: str) -> Optional[PowerQueryLineageNode]:
        """Returns the complete lineage node for a specific table."""
        # Check by query name == table_name
        if table_name in self.nodes:
            return self.nodes[table_name]
        
        # Check by target_table attribute
        for node in self.nodes.values():
            if node.target_table == table_name:
                return node
        return None

    def get_all_nodes(self) -> Dict[str, PowerQueryLineageNode]:
        return self.nodes

    def get_all_root_sources(self) -> List[PowerQuerySource]:
        """Returns unique physical sources across the entire semantic model."""
        unique_sources: Dict[str, PowerQuerySource] = {}
        for node in self.nodes.values():
            for s in node.root_sources:
                key = f"{s.source_type}:{s.connection_string}"
                if key not in unique_sources:
                    unique_sources[key] = s
        return list(unique_sources.values())
