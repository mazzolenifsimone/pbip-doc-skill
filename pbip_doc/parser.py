"""
PBIP Semantic Model Parser.
Supports both TMDL (Tabular Model Definition Language) directory structures
and TMSL (model.bim) JSON files.
Vanilla Python implementation.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from .model_schema import (
    PBIPSemanticModel,
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    MeasureDefinition,
    FunctionDefinition,
    FunctionParameter,
    IncrementalRefreshPolicy,
    TableRole,
    TableRoleClassification,
    PowerQuerySource,
)
from .m_lineage import MLineageResolver
from .star_schema import StarSchemaResolver
from .measure_analyzer import MeasureDependencyResolver


def _clean_tmdl_multiline_block(expr: Optional[str]) -> Optional[str]:
    """Strips TMDL triple backticks (``` or ```dax / ```m) from multiline code blocks."""
    if not expr:
        return expr
    s = expr.strip()
    if s.startswith("```"):
        s = re.sub(r'^```[a-zA-Z]*\r?\n?', '', s)
        s = re.sub(r'\r?\n?\s*```$', '', s)
        s = s.strip()
    return s


class PBIPParser:
    """
    Parses a PBIP semantic model from either a directory (TMDL/BIM) or a single BIM file.
    Orchestrates M Lineage, Star Schema, and Measure dependency resolution.
    Supports table exclusion configuration (e.g. LocalDateTable_*, DateTableTemplate_*).
    """

    def __init__(self, config: Optional[Any] = None):
        self.config = config

    def parse(self, target_path: str, config: Optional[Any] = None) -> PBIPSemanticModel:
        """
        Auto-detects format (TMDL directory vs BIM JSON file) and executes extraction.
        Applies table exclusion filters from config (e.g. auto date/time tables).
        """
        active_config = config or self.config
        if active_config is None:
            from .docgen.config import DocGenConfig
            base_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
            active_config = DocGenConfig.find_and_load_default(base_dir)
        self.active_config = active_config

        path = Path(target_path)
        model: PBIPSemanticModel

        if path.is_file() and (path.suffix.lower() == ".json" or path.name.lower() == "model.bim"):
            model = self.parse_bim_file(str(path))
        elif path.is_dir():
            # Check if there is a definition/ subfolder (TMDL standard)
            tmdl_dir = path / "definition"
            if tmdl_dir.exists() and (tmdl_dir / "tables").exists():
                model = self.parse_tmdl_dir(str(tmdl_dir), model_name=path.stem)
            # Check if target_path is itself the definition folder
            elif (path / "tables").exists():
                model = self.parse_tmdl_dir(str(path), model_name=path.parent.stem)
            # Check for model.bim inside directory
            elif (path / "model.bim").exists():
                model = self.parse_bim_file(str(path / "model.bim"))
            else:
                # Recursive search for definition or model.bim
                found = False
                for sub in path.rglob("definition"):
                    if sub.is_dir() and (sub / "tables").exists():
                        model = self.parse_tmdl_dir(str(sub), model_name=path.stem)
                        found = True
                        break
                if not found:
                    for bim in path.rglob("model.bim"):
                        model = self.parse_bim_file(str(bim))
                        found = True
                        break
                if not found:
                    raise FileNotFoundError(
                        f"Could not find valid TMDL directory (with 'tables/' folder) or model.bim in: {target_path}"
                    )
        else:
            raise FileNotFoundError(f"Path not found: {target_path}")

        # Filter out auto-generated or user-excluded tables
        if active_config:
            model.filter_excluded_tables(active_config.is_table_excluded)

        return model

    # =========================================================================
    # BIM / TMSL Parser
    # =========================================================================

    def parse_bim_file(self, bim_path: str) -> PBIPSemanticModel:
        """Parses standard model.bim JSON format."""
        with open(bim_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self.parse_bim_dict(data, model_name=Path(bim_path).stem)

    def parse_bim_dict(self, data: Dict[str, Any], model_name: str = "SemanticModel") -> PBIPSemanticModel:
        """Parses model.bim JSON dictionary."""
        model_data = data.get("model", data)
        culture = model_data.get("culture", "en-US")
        compat_level = data.get("compatibilityLevel", 1550)

        tables: List[TableDefinition] = []
        relationships: List[RelationshipDefinition] = []
        measures: List[MeasureDefinition] = []
        raw_queries: Dict[str, Dict[str, Any]] = {}

        # 1. Parse Shared Expressions (M staging / parameters)
        for expr in model_data.get("expressions", []):
            q_name = expr.get("name", "")
            raw_m = expr.get("expression", "")
            if isinstance(raw_m, list):
                raw_m = "\n".join(raw_m)
            raw_queries[q_name] = {
                "m_code": raw_m,
                "target_table": None,
                "is_staging": True,
                "description": expr.get("description"),
                "lineage_tag": expr.get("lineageTag"),
                "query_group": expr.get("queryGroup"),
                "kind": expr.get("kind", "m"),
            }

        # 2. Parse Tables, Columns, Measures, and Table Partitions (M)
        for tbl in model_data.get("tables", []):
            t_name = tbl.get("name", "")
            description = tbl.get("description")
            is_hidden = tbl.get("isHidden", False)

            # Columns
            cols: List[ColumnDefinition] = []
            for col in tbl.get("columns", []):
                col_name = col.get("name", "")
                data_type = col.get("dataType", "string")
                is_col_hidden = col.get("isHidden", False)
                is_key = col.get("isKey", False)
                format_string = col.get("formatString")
                col_desc = col.get("description")
                col_expr = col.get("expression")
                if isinstance(col_expr, list):
                    col_expr = "\n".join(col_expr)
                is_calculated = (
                    col.get("type", "").lower() == "calculated"
                    or (col_expr is not None and len(str(col_expr).strip()) > 0)
                )
                display_folder = col.get("displayFolder")

                cols.append(
                    ColumnDefinition(
                        name=col_name,
                        data_type=data_type,
                        is_hidden=is_col_hidden,
                        is_key=is_key,
                        is_calculated=is_calculated,
                        format_string=format_string,
                        description=col_desc,
                        expression=col_expr,
                        display_folder=display_folder,
                    )
                )

            # Partitions (Power Query M, Calculated, or Inherited Entity)
            source_type = "PowerQuery"
            table_m_code = ""
            is_inherited = False
            inherited_entity_name = None
            inherited_expression_source = None
            for part in tbl.get("partitions", []):
                part_source = part.get("source", {})
                p_type = part_source.get("type", "").lower()
                query_body = part_source.get("query", "")
                if isinstance(query_body, list):
                    query_body = "\n".join(query_body)

                if p_type == "entity" or "entityName" in part_source:
                    source_type = "InheritedEntity"
                    is_inherited = True
                    inherited_entity_name = part_source.get("entityName", t_name)
                    inherited_expression_source = part_source.get("expressionSource")
                elif p_type == "m" or "let" in query_body:
                    source_type = "PowerQuery"
                    table_m_code = query_body
                elif p_type == "calculated" or part_source.get("expression"):
                    source_type = "CalculatedTable"
                    table_m_code = ""

            if tbl.get("calculationGroup"):
                source_type = "CalculationGroup"

            if table_m_code:
                raw_queries[t_name] = {
                    "m_code": table_m_code,
                    "target_table": t_name,
                    "is_staging": False,
                }

            # Measures
            for m in tbl.get("measures", []):
                m_name = m.get("name", "")
                m_expr = m.get("expression", "")
                if isinstance(m_expr, list):
                    m_expr = "\n".join(m_expr)
                m_format = m.get("formatString")
                m_desc = m.get("description")
                m_hidden = m.get("isHidden", False)
                m_folder = m.get("displayFolder")

                is_ext = bool(re.search(r'^\s*EXTERNALMEASURE\s*\(', m_expr, re.IGNORECASE))

                measures.append(
                    MeasureDefinition(
                        name=m_name,
                        table=t_name,
                        dax_expression=m_expr,
                        format_string=m_format,
                        description=m_desc,
                        is_hidden=m_hidden,
                        display_folder=m_folder,
                        is_inherited=is_ext,
                        is_external_measure=is_ext,
                        out_of_scope=is_ext,
                    )
                )

            t_refresh_policy = t.get("refreshPolicy")
            inc_policy = None
            if t_refresh_policy and isinstance(t_refresh_policy, dict):
                src_expr = t_refresh_policy.get("sourceExpression")
                if isinstance(src_expr, list):
                    src_expr = "\n".join(src_expr)
                poll_expr = t_refresh_policy.get("pollingExpression")
                if isinstance(poll_expr, list):
                    poll_expr = "\n".join(poll_expr)
                inc_policy = IncrementalRefreshPolicy(
                    is_enabled=True,
                    policy_type=t_refresh_policy.get("policyType", "basic"),
                    mode=t_refresh_policy.get("mode", "import"),
                    rolling_window_periods=t_refresh_policy.get("rollingWindowPeriods"),
                    rolling_window_granularity=t_refresh_policy.get("rollingWindowGranularity"),
                    incremental_periods=t_refresh_policy.get("incrementalPeriods") or t_refresh_policy.get("incrementalWindowPeriods"),
                    incremental_granularity=t_refresh_policy.get("incrementalGranularity") or t_refresh_policy.get("incrementalWindowGranularity"),
                    source_expression=src_expr,
                    polling_expression=poll_expr,
                    raw_policy=t_refresh_policy,
                )

            table_def = TableDefinition(
                name=t_name,
                role=TableRole.UNKNOWN,
                classification_reasoning=TableRoleClassification(TableRole.UNKNOWN, 0.0),
                columns=cols,
                is_hidden=is_hidden,
                description=description,
                source_type=source_type,
                incremental_refresh_policy=inc_policy,
                is_inherited=is_inherited,
                inherited_entity_name=inherited_entity_name,
                inherited_expression_source=inherited_expression_source,
                out_of_scope=is_inherited,
            )
            tables.append(table_def)

        # 3. Parse Relationships
        rel_index = 1
        for rel in model_data.get("relationships", []):
            from_t = rel.get("fromTable", "")
            from_c = rel.get("fromColumn", "")
            to_t = rel.get("toTable", "")
            to_c = rel.get("toColumn", "")
            cardinality = rel.get("cardinality", "1:N")
            cross_dir = rel.get("crossFilteringBehavior", "Single")
            is_active = rel.get("isActive", True)
            rel_id = rel.get("name", f"rel_{rel_index}_{from_t}_{to_t}")
            rel_index += 1

            # Standardize cardinality representation
            from_card = (rel.get("fromCardinality") or "").lower()
            to_card = (rel.get("toCardinality") or "").lower()
            if from_card == "one" and to_card == "many":
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"
            elif from_card == "one" and to_card == "one":
                cardinality = "1:1"
            elif from_card == "many" and to_card == "many":
                cardinality = "N:N"
            elif cardinality in ("OneToMany", "1:N"):
                cardinality = "1:N"
            elif cardinality in ("ManyToOne", "N:1"):
                cardinality = "1:N"
            elif cardinality in ("OneToOne", "1:1"):
                cardinality = "1:1"
            elif cardinality in ("ManyToMany", "N:N"):
                cardinality = "N:N"

            relationships.append(
                RelationshipDefinition(
                    id=rel_id,
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    cardinality=cardinality,
                    cross_filtering_behavior=cross_dir,
                    is_active=is_active,
                )
            )

        # 4. Parse Functions (if defined in BIM)
        functions: List[FunctionDefinition] = []
        for fn in model_data.get("functions", []):
            fn_name = fn.get("name", "UnnamedFunction")
            fn_expr = fn.get("expression", "")
            if isinstance(fn_expr, list):
                fn_expr = "\n".join(fn_expr)
            fn_desc = fn.get("description")
            fn_type = fn.get("dataType")
            fn_hidden = fn.get("isHidden", False)
            fn_tag = fn.get("lineageTag")

            params: List[FunctionParameter] = []
            for p in fn.get("parameters", []):
                params.append(
                    FunctionParameter(
                        name=p.get("name", "param"),
                        data_type=p.get("dataType"),
                        is_optional=p.get("isOptional", False),
                        default_value=p.get("defaultValue"),
                        description=p.get("description"),
                    )
                )

            sig = ""
            if params:
                param_strs = []
                for p in params:
                    s = p.name
                    if p.data_type:
                        s += f": {p.data_type}"
                    if p.default_value is not None:
                        s += f" = {p.default_value}"
                    param_strs.append(s)
                sig = f"({', '.join(param_strs)})"

            functions.append(
                FunctionDefinition(
                    name=fn_name,
                    expression=fn_expr,
                    parameters=params,
                    parameters_signature=sig,
                    return_type=fn_type,
                    description=fn_desc,
                    is_hidden=fn_hidden,
                    lineage_tag=fn_tag,
                )
            )

        return self._enrich_and_resolve(
            model_name=model_name,
            source_format="BIM",
            compat_level=compat_level,
            culture=culture,
            tables=tables,
            relationships=relationships,
            measures=measures,
            raw_queries=raw_queries,
            functions=functions,
        )

    # =========================================================================
    # TMDL Parser
    # =========================================================================

    def parse_tmdl_dir(self, definition_dir: str, model_name: str = "SemanticModel") -> PBIPSemanticModel:
        """Parses TMDL definition folder."""
        def_path = Path(definition_dir)
        tables: List[TableDefinition] = []
        relationships: List[RelationshipDefinition] = []
        measures: List[MeasureDefinition] = []
        functions: List[FunctionDefinition] = []
        raw_queries: Dict[str, Dict[str, Any]] = {}

        # 1. Parse expressions from expressions.tmdl or expressions/*.tmdl
        expr_file = def_path / "expressions.tmdl"
        if expr_file.exists():
            with open(expr_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._parse_tmdl_expressions(content, raw_queries)

        expr_dir = def_path / "expressions"
        if expr_dir.is_dir():
            for e_file in expr_dir.glob("*.tmdl"):
                with open(e_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._parse_tmdl_expressions(content, raw_queries, default_name=e_file.stem)

        # 2. Parse tables from tables/*.tmdl
        tables_dir = def_path / "tables"
        if tables_dir.exists():
            for t_file in tables_dir.glob("*.tmdl"):
                with open(t_file, "r", encoding="utf-8") as f:
                    content = f.read()
                table_def, tbl_measures, tbl_m_code = self._parse_single_table_tmdl(content, t_file.stem)
                tables.append(table_def)
                measures.extend(tbl_measures)
                if tbl_m_code:
                    raw_queries[table_def.name] = {
                        "m_code": tbl_m_code,
                        "target_table": table_def.name,
                        "is_staging": False,
                    }

        # 3. Parse relationships.tmdl
        rel_file = def_path / "relationships.tmdl"
        if rel_file.exists():
            with open(rel_file, "r", encoding="utf-8") as f:
                content = f.read()
            relationships = self._parse_tmdl_relationships(content)

        # 4. Parse functions from functions.tmdl or definition/functions.tmdl
        fn_candidates = [
            def_path / "functions.tmdl",
            def_path.parent / "functions.tmdl",
        ]
        fn_candidates.extend(list(def_path.glob("**/functions.tmdl")))
        if (def_path / "functions").is_dir():
            fn_candidates.extend(list((def_path / "functions").glob("*.tmdl")))

        seen_fn_files = set()
        for fn_file in fn_candidates:
            try:
                resolved = fn_file.resolve()
            except Exception:
                resolved = fn_file
            if fn_file.exists() and resolved not in seen_fn_files:
                seen_fn_files.add(resolved)
                with open(fn_file, "r", encoding="utf-8") as f:
                    f_content = f.read()
                parsed_fns = self._parse_tmdl_functions(f_content)
                functions.extend(parsed_fns)

        return self._enrich_and_resolve(
            model_name=model_name,
            source_format="TMDL",
            compat_level=1600,
            culture="en-US",
            tables=tables,
            relationships=relationships,
            measures=measures,
            raw_queries=raw_queries,
            functions=functions,
        )

    def _parse_tmdl_expressions(self, content: str, raw_queries: Dict[str, Dict[str, Any]], default_name: Optional[str] = None):
        """Extracts shared queries from expressions.tmdl or definition/expressions/*.tmdl."""
        expr_blocks = re.split(r'^\s*expression\s+', content, flags=re.MULTILINE)
        for block in expr_blocks:
            if not block.strip():
                continue
            lines = block.splitlines()
            header = lines[0].strip()
            # Name extraction
            name_match = re.match(r"^(['\"]?)([^'=]+)\1\s*=\s*(.*)$", header)
            if name_match:
                q_name = name_match.group(2).strip()
                first_line_expr = name_match.group(3)
                rest_of_code = "\n".join(lines[1:])
                combined_code = (first_line_expr + "\n" + rest_of_code).strip()
            elif default_name and "=" in header:
                parts = header.split("=", 1)
                q_name = default_name
                combined_code = (parts[1] + "\n" + "\n".join(lines[1:])).strip()
            else:
                continue

            # Extract properties before cleaning them
            desc_match = re.search(r'description:\s*["\']?(.*?)["\']?$', block, re.MULTILINE)
            description = desc_match.group(1).strip() if desc_match else None

            tag_match = re.search(r'lineageTag:\s*([^\r\n]+)', block)
            lineage_tag = tag_match.group(1).strip() if tag_match else None

            group_match = re.search(r'queryGroup:\s*([^\r\n]+)', block)
            query_group = group_match.group(1).strip() if group_match else None

            # Clean lineageTag, queryGroup, description, annotation at end of block
            m_code = re.split(r'\n\s*(?:lineageTag|queryGroup|description|annotation)\b', combined_code)[0].strip()

            # Clean triple backticks if used in TMDL M expressions
            m_code = _clean_tmdl_multiline_block(m_code) or ""

            raw_queries[q_name] = {
                "m_code": m_code.strip(),
                "target_table": None,
                "is_staging": True,
                "description": description,
                "lineage_tag": lineage_tag,
                "query_group": query_group,
            }

    def _parse_single_table_tmdl(self, content: str, default_name: str) -> Tuple[TableDefinition, List[MeasureDefinition], str]:
        """Parses a table .tmdl file into columns, measures, and M code."""
        lines = content.splitlines()
        table_name = default_name
        description = None
        is_hidden = False
        source_type = "PowerQuery"

        # Check table header (handles regular: table TableName, quoted: table 'Table Name', and calculated: table TableName = <DAX>)
        first_line = lines[0].strip() if lines else ""
        t_match = re.match(r"^table\s+(?:(['\"])(.*?)\1|([^\s=]+))(?:\s*=\s*(.*))?$", first_line)
        if t_match:
            table_name = (t_match.group(2) or t_match.group(3) or "").strip()
            if t_match.group(4) is not None:
                source_type = "CalculatedTable"

        columns: List[ColumnDefinition] = []
        measures: List[MeasureDefinition] = []
        table_m_code = ""

        # Extract partitions & M code (handles m, entity, and calculated partitions)
        is_inherited = False
        inherited_entity_name = None
        inherited_expression_source = None

        entity_partition_match = re.search(
            r'partition\s+.*?\s*=\s*entity\b(?P<body>.*?)(?=^\s{1,4}(?:column|measure|partition|hierarchy)|\Z)',
            content,
            re.DOTALL | re.IGNORECASE | re.MULTILINE
        )
        m_partition_match = re.search(r'partition\s+.*?\s*=\s*m\b.*?source\s*=\s*(.*)', content, re.DOTALL | re.IGNORECASE)

        if entity_partition_match:
            source_type = "InheritedEntity"
            is_inherited = True
            body = entity_partition_match.group("body") or ""
            ent_m = re.search(r'entityName:\s*["\']?(.*?)["\']?$', body, re.MULTILINE)
            inherited_entity_name = ent_m.group(1).strip() if ent_m else table_name
            exp_m = re.search(r'expressionSource:\s*["\']?(.*?)["\']?$', body, re.MULTILINE)
            inherited_expression_source = exp_m.group(1).strip() if exp_m else None
        elif m_partition_match:
            table_m_code = m_partition_match.group(1).strip()
            # Stop before annotations or next major block
            table_m_code = re.split(r'\n\s*(?:annotation|lineageTag)\b', table_m_code)[0]
            source_type = "PowerQuery"
        elif "partition " in content and "= calculated" in content:
            source_type = "CalculatedTable"

        # Extract Columns
        # Handles both regular columns:
        #   column ColumnName
        # and calculated columns:
        #   column 'Column Name' = <DAX Expression>
        #   column ColumnName =
        #       <Multiline DAX Expression>
        col_pattern = re.compile(
            r'^\s{1,4}column\s+(?:(?P<q>[\'"])(?P<qname>.*?)(?P=q)|(?P<uname>[^\s=]+))(?:\s*=\s*(?P<inline_expr>[^\r\n]*))?(?P<body>.*?)(?=^\s{1,4}(?:column|measure|partition)|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        for match in col_pattern.finditer(content):
            c_name = (match.group("qname") or match.group("uname") or "").strip()
            if not c_name:
                continue

            inline_expr = match.group("inline_expr")
            body = match.group("body") or ""

            is_calculated = False
            c_expr = None

            # If inline_expr matched, an '=' was present on the column declaration line
            if inline_expr is not None:
                is_calculated = True
                # Separate formula from trailing TMDL property attributes
                prop_split = re.split(
                    r'\n\s{2,8}(?:dataType|formatString|lineageTag|summarizeBy|displayFolder|description|annotation|isKey|isHidden|sourceColumn|dataCategory|sortByColumn):',
                    body,
                    maxsplit=1
                )
                multiline_expr = prop_split[0] if prop_split else ""
                full_expr = ((inline_expr or "") + "\n" + multiline_expr).strip()
                full_expr = _clean_tmdl_multiline_block(full_expr)
                c_expr = full_expr if full_expr else None

            # Check properties
            dt_match = re.search(r'dataType:\s*(\w+)', body)
            data_type = dt_match.group(1) if dt_match else "string"
            fmt_match = re.search(r'formatString:\s*(.+)', body)
            format_string = fmt_match.group(1).strip() if fmt_match else None
            is_col_hidden = "isHidden" in body
            is_key = "isKey" in body
            desc_match = re.search(r'description:\s*["\']?(.*?)["\']?$', body, re.MULTILINE)
            c_desc = desc_match.group(1).strip() if desc_match else None

            # Fallback for explicit expression: attribute if present
            if not c_expr:
                expr_match = re.search(r'expression:\s*(.+)', body)
                if expr_match:
                    c_expr = expr_match.group(1).strip()
                    is_calculated = True

            columns.append(
                ColumnDefinition(
                    name=c_name,
                    data_type=data_type,
                    is_hidden=is_col_hidden,
                    is_key=is_key,
                    is_calculated=is_calculated,
                    format_string=format_string,
                    description=c_desc,
                    expression=c_expr,
                )
            )

        # Extract Measures
        measure_pattern = re.compile(
            r"^\s{1,4}measure\s+(['\"]?)(.*?)\1\s*=\s*(.*?)(?=^\s{1,4}(?:measure|column|partition)|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        for match in measure_pattern.finditer(content):
            m_name = match.group(2).strip()
            m_body_and_props = match.group(3)

            # Separate DAX expression from TMDL property attributes (lineageTag, formatString, etc.)
            prop_split = re.split(r'\n\s{2,8}(?:lineageTag|formatString|displayFolder|description|annotation):', m_body_and_props, maxsplit=1)
            dax_expr = _clean_tmdl_multiline_block(prop_split[0].strip()) or ""
            is_ext = bool(re.search(r'^\s*EXTERNALMEASURE\s*\(', dax_expr, re.IGNORECASE))

            fmt_match = re.search(r'formatString:\s*["\']?(.*?)["\']?$', m_body_and_props, re.MULTILINE)
            format_string = fmt_match.group(1).strip() if fmt_match else None
            desc_match = re.search(r'description:\s*["\']?(.*?)["\']?$', m_body_and_props, re.MULTILINE)
            m_desc = desc_match.group(1).strip() if desc_match else None
            folder_match = re.search(r'displayFolder:\s*["\']?(.*?)["\']?$', m_body_and_props, re.MULTILINE)
            m_folder = folder_match.group(1).strip() if folder_match else None
            m_hidden = "isHidden" in m_body_and_props

            measures.append(
                MeasureDefinition(
                    name=m_name,
                    table=table_name,
                    dax_expression=dax_expr,
                    format_string=format_string,
                    description=m_desc,
                    is_hidden=m_hidden,
                    display_folder=m_folder,
                    is_inherited=is_ext,
                    is_external_measure=is_ext,
                    out_of_scope=is_ext,
                )
            )

        inc_policy = self._parse_tmdl_refresh_policy(content)

        table_def = TableDefinition(
            name=table_name,
            role=TableRole.UNKNOWN,
            classification_reasoning=TableRoleClassification(TableRole.UNKNOWN, 0.0),
            columns=columns,
            is_hidden=is_hidden,
            description=description,
            source_type=source_type,
            incremental_refresh_policy=inc_policy,
            is_inherited=is_inherited,
            inherited_entity_name=inherited_entity_name,
            inherited_expression_source=inherited_expression_source,
            out_of_scope=is_inherited,
        )

        return table_def, measures, table_m_code

    def _parse_tmdl_refresh_policy(self, content: str) -> Optional[IncrementalRefreshPolicy]:
        """Parses TMDL refreshPolicy block or JSON assignment."""
        match = re.search(
            r'^\s{1,4}refreshPolicy(?:\s*=\s*(?P<json_str>\{[\s\S]*?\}))?(?P<rest>[^\r\n]*(?:\n\s{2,}[\s\S]*?)?)(?=^\s{1,4}(?:column|measure|partition|hierarchy)|\Z)',
            content,
            re.MULTILINE
        )
        if not match:
            return None

        json_str = match.group("json_str")
        raw_dict = {}
        if json_str:
            try:
                raw_dict = json.loads(json_str)
            except Exception:
                pass

        if raw_dict:
            src_expr = raw_dict.get("sourceExpression")
            if isinstance(src_expr, list):
                src_expr = "\n".join(src_expr)
            poll_expr = raw_dict.get("pollingExpression")
            if isinstance(poll_expr, list):
                poll_expr = "\n".join(poll_expr)
            return IncrementalRefreshPolicy(
                is_enabled=True,
                policy_type=raw_dict.get("policyType", "basic"),
                mode=raw_dict.get("mode", "import"),
                rolling_window_periods=raw_dict.get("rollingWindowPeriods"),
                rolling_window_granularity=raw_dict.get("rollingWindowGranularity"),
                incremental_periods=raw_dict.get("incrementalPeriods") or raw_dict.get("incrementalWindowPeriods"),
                incremental_granularity=raw_dict.get("incrementalGranularity") or raw_dict.get("incrementalWindowGranularity"),
                source_expression=src_expr,
                polling_expression=poll_expr,
                raw_policy=raw_dict,
            )

        combined_text = match.group("rest") or ""

        policy_type_m = re.search(r'policyType:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        policy_type = policy_type_m.group(1).strip() if policy_type_m else "basic"

        mode_m = re.search(r'mode:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        mode = mode_m.group(1).strip() if mode_m else "import"

        roll_per_m = re.search(r'rollingWindowPeriods:\s*(\d+)', combined_text, re.IGNORECASE)
        roll_per = int(roll_per_m.group(1)) if roll_per_m else None

        roll_gran_m = re.search(r'rollingWindowGranularity:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        roll_gran = roll_gran_m.group(1).strip() if roll_gran_m else None

        inc_per_m = re.search(r'(?:incrementalPeriods|incrementalWindowPeriods):\s*(\d+)', combined_text, re.IGNORECASE)
        inc_per = int(inc_per_m.group(1)) if inc_per_m else None

        inc_gran_m = re.search(r'(?:incrementalGranularity|incrementalWindowGranularity):\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        inc_gran = inc_gran_m.group(1).strip() if inc_gran_m else None

        poll_m = re.search(r'pollingExpression:\s*(.+)', combined_text, re.IGNORECASE)
        poll_expr = poll_m.group(1).strip() if poll_m else None

        src_m = re.search(r'sourceExpression:\s*(.+)', combined_text, re.IGNORECASE)
        src_expr = src_m.group(1).strip() if src_m else None

        return IncrementalRefreshPolicy(
            is_enabled=True,
            policy_type=policy_type,
            mode=mode,
            rolling_window_periods=roll_per,
            rolling_window_granularity=roll_gran,
            incremental_periods=inc_per,
            incremental_granularity=inc_gran,
            source_expression=src_expr,
            polling_expression=poll_expr,
            raw_policy={
                "policyType": policy_type,
                "mode": mode,
                "rollingWindowPeriods": roll_per,
                "rollingWindowGranularity": roll_gran,
                "incrementalPeriods": inc_per,
                "incrementalGranularity": inc_gran,
            },
        )

    def _parse_tmdl_relationships(self, content: str) -> List[RelationshipDefinition]:
        """Parses relationships.tmdl."""
        relationships: List[RelationshipDefinition] = []
        blocks = re.split(r'^\s*relationship\s+', content, flags=re.MULTILINE)

        for block in blocks:
            if not block.strip():
                continue
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            rel_id = lines[0] if lines else "relationship"

            from_match = re.search(r'fromColumn:\s*(?:([^\.]+)\.([^\r\n]+)|([^\r\n]+))', block)
            to_match = re.search(r'toColumn:\s*(?:([^\.]+)\.([^\r\n]+)|([^\r\n]+))', block)

            if not from_match or not to_match:
                continue

            from_t = from_match.group(1).strip() if from_match.group(1) else ""
            from_c = from_match.group(2).strip() if from_match.group(2) else ""
            to_t = to_match.group(1).strip() if to_match.group(1) else ""
            to_c = to_match.group(2).strip() if to_match.group(2) else ""

            # Check if columns or tables were enclosed in quotes
            from_t = from_t.strip("'\"")
            from_c = from_c.strip("'\"")
            to_t = to_t.strip("'\"")
            to_c = to_c.strip("'\"")

            is_active = "isActive: false" not in block
            cross_match = re.search(r'crossFilteringBehavior:\s*(\w+)', block)
            cross_dir = cross_match.group(1) if cross_match else "Single"

            # Check cardinality
            has_from_one = bool(re.search(r'fromCardinality:\s*one\b', block, re.IGNORECASE))
            has_from_many = bool(re.search(r'fromCardinality:\s*many\b', block, re.IGNORECASE))
            has_to_one = bool(re.search(r'toCardinality:\s*one\b', block, re.IGNORECASE))
            has_to_many = bool(re.search(r'toCardinality:\s*many\b', block, re.IGNORECASE))

            cardinality = "1:N"
            if has_from_one and has_to_one:
                cardinality = "1:1"
            elif has_from_many and has_to_many:
                cardinality = "N:N"
            elif has_from_one and not has_to_one:
                # from_t is the ONE side, to_t is the MANY side!
                # Normalize so that from_table is always Many (child/FK) and to_table is One (parent/PK)
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"
            elif has_to_many and not has_from_many:
                # to_t is the MANY side, from_t is the ONE side
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"

            relationships.append(
                RelationshipDefinition(
                    id=rel_id,
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    cardinality=cardinality,
                    cross_filtering_behavior=cross_dir,
                    is_active=is_active,
                )
            )

        return relationships

    # =========================================================================
    # Enrichment & Resolution Pipeline
    # =========================================================================

    def _parse_tmdl_functions(self, content: str) -> List[FunctionDefinition]:
        """Parses DAX User-Defined Functions from functions.tmdl."""
        functions: List[FunctionDefinition] = []
        matches = list(re.finditer(r'^\s{0,2}function\s+([^\r\n=]+)\s*=', content, re.MULTILINE | re.IGNORECASE))
        if not matches:
            return functions

        for i, match in enumerate(matches):
            raw_name = match.group(1).strip()
            # Clean quotes: 'Safe Divide' -> Safe Divide
            if (raw_name.startswith("'") and raw_name.endswith("'")) or (raw_name.startswith('"') and raw_name.endswith('"')):
                fn_name = raw_name[1:-1].strip()
            else:
                fn_name = raw_name

            start_body = match.end()
            end_body = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body_block = content[start_body:end_body]

            # 1. Extract code block vs trailing TMDL metadata properties
            # If the function body is wrapped in triple backticks:
            # function Func = ``` ... ```
            backtick_match = re.search(
                r'^\s*```[a-zA-Z]*\r?\n?(?P<code>[\s\S]*?)\r?\n?\s*```(?P<meta>[\s\S]*)',
                body_block
            )
            if backtick_match:
                code_block = backtick_match.group("code").strip()
                meta_block = backtick_match.group("meta")
            else:
                # Fallback: split at the first trailing TMDL attribute line
                meta_split = re.split(
                    r'\n\s{1,8}(?:dataType|description|lineageTag|isHidden|annotation)\b',
                    body_block,
                    maxsplit=1
                )
                code_block = meta_split[0].strip()
                meta_block = body_block[len(code_block):] if len(meta_split) > 1 else ""
                # Strip any leading/trailing triple backticks that may still be present
                if code_block.startswith("```"):
                    code_block = re.sub(r'^```[a-zA-Z]*\r?\n?', '', code_block)
                    code_block = re.sub(r'\r?\n?\s*```$', '', code_block).strip()

            # 2. Extract metadata properties (description, dataType, lineageTag, isHidden)
            desc_match = re.search(
                r'^\s{0,8}description:\s*(?:"([^"]*)"|\'([^\']*)\'|([^\r\n]+))',
                meta_block,
                re.MULTILINE
            )
            description = None
            if desc_match:
                description = desc_match.group(1) or desc_match.group(2) or desc_match.group(3)
                description = description.strip() if description else None
            elif not backtick_match:
                dm = re.search(
                    r'^\s{1,8}description:\s*(?:"([^"]*)"|\'([^\']*)\'|([^\r\n]+))',
                    body_block,
                    re.MULTILINE
                )
                if dm:
                    description = dm.group(1) or dm.group(2) or dm.group(3)
                    description = description.strip() if description else None

            type_match = re.search(r'^\s{0,8}dataType:\s*([^\r\n]+)', meta_block, re.MULTILINE)
            return_type = type_match.group(1).strip() if type_match else None
            if not return_type and not backtick_match:
                tm = re.search(r'^\s{1,8}dataType:\s*([^\r\n]+)', body_block, re.MULTILINE)
                return_type = tm.group(1).strip() if tm else None

            tag_match = re.search(r'^\s{0,8}lineageTag:\s*([^\r\n]+)', meta_block, re.MULTILINE)
            lineage_tag = tag_match.group(1).strip() if tag_match else None
            if not lineage_tag and not backtick_match:
                tgm = re.search(r'^\s{1,8}lineageTag:\s*([^\r\n]+)', body_block, re.MULTILINE)
                lineage_tag = tgm.group(1).strip() if tgm else None

            is_hidden = bool(re.search(r'^\s{0,8}isHidden\b', meta_block, re.MULTILINE))
            if not is_hidden and not backtick_match:
                is_hidden = bool(re.search(r'^\s{1,8}isHidden\b', body_block, re.MULTILINE))

            # 3. Parse parameters signature and implementation expression
            # Syntax: (param1: type = default, ...) [: returnType] => expression
            parameters: List[FunctionParameter] = []
            if "=>" in code_block:
                arrow_split = re.split(r'\s*=>\s*', code_block, maxsplit=1)
                sig_raw = arrow_split[0].strip()
                expression = arrow_split[1].strip()
            else:
                sig_raw = ""
                expression = code_block.strip()

            # Clean any trailing backticks in expression
            expression = _clean_tmdl_multiline_block(expression) or ""

            # Check for inline return type annotation like (...): double =>
            ret_type_match = re.search(r'\)\s*:\s*([a-zA-Z0-9_]+)\s*$', sig_raw)
            if ret_type_match:
                if not return_type:
                    return_type = ret_type_match.group(1).strip()
                sig_raw = sig_raw[:ret_type_match.start() + 1].strip()

            # Clean signature string: strip outer backticks and parentheses
            sig_raw = re.sub(r'^[`\s]+', '', sig_raw)
            sig_raw = re.sub(r'[`\s]+$', '', sig_raw)
            if sig_raw.startswith("(") and sig_raw.endswith(")"):
                clean_sig = sig_raw[1:-1].strip()
            else:
                clean_sig = sig_raw.strip("()").strip()

            parameters = self._parse_function_parameters(clean_sig)

            # Build canonical parameters_signature string
            if parameters:
                param_strs = []
                for p in parameters:
                    s = p.name
                    if p.data_type:
                        s += f": {p.data_type}"
                    if p.default_value is not None:
                        s += f" = {p.default_value}"
                    param_strs.append(s)
                sig_str = f"({', '.join(param_strs)})"
            else:
                sig_str = "()"

            functions.append(
                FunctionDefinition(
                    name=fn_name,
                    expression=expression,
                    parameters=parameters,
                    parameters_signature=sig_str,
                    return_type=return_type,
                    description=description,
                    is_hidden=is_hidden,
                    lineage_tag=lineage_tag,
                )
            )

        return functions

    def _parse_function_parameters(self, sig: str) -> List[FunctionParameter]:
        """Parses parameter string like 'Numerator: double, Denominator: double, Alt: double = 0'."""
        params: List[FunctionParameter] = []
        if not sig or not sig.strip():
            return params

        # Strip any stray leading/trailing backticks or parentheses from the entire signature string
        sig = sig.strip()
        sig = re.sub(r'^[`()]+', '', sig).strip()
        sig = re.sub(r'[`()]+$', '', sig).strip()
        if not sig:
            return params

        # Smart split by commas, respecting quotes and parentheses
        tokens: List[str] = []
        current: List[str] = []
        in_quote = None
        paren_depth = 0
        for ch in sig:
            if in_quote:
                current.append(ch)
                if ch == in_quote:
                    in_quote = None
            elif ch in ('"', "'"):
                in_quote = ch
                current.append(ch)
            elif ch in ('(', '[', '{'):
                paren_depth += 1
                current.append(ch)
            elif ch in (')', ']', '}'):
                paren_depth -= 1
                current.append(ch)
            elif ch == ',' and paren_depth == 0:
                t = "".join(current).strip()
                if t:
                    tokens.append(t)
                current = []
            else:
                current.append(ch)
        last_t = "".join(current).strip()
        if last_t:
            tokens.append(last_t)

        for tok in tokens:
            # Strip comments
            tok = re.sub(r'/\*.*?\*/', '', tok, flags=re.DOTALL)
            tok = re.sub(r'//.*$', '', tok, flags=re.MULTILINE)
            # Strip stray backticks, parentheses, and whitespace
            tok = tok.strip()
            tok = re.sub(r'^[`()]+', '', tok).strip()
            tok = re.sub(r'[`()]+$', '', tok).strip()
            if not tok:
                continue

            default_val = None
            is_opt = False
            if "=" in tok:
                parts = tok.split("=", 1)
                tok_name_part = parts[0].strip()
                default_val = parts[1].strip()
                # Clean stray closing backticks, parentheses
                default_val = re.sub(r'[`()]+$', '', default_val).strip()
                is_opt = True
            else:
                tok_name_part = tok.strip()

            if ":" in tok_name_part:
                p_parts = tok_name_part.split(":", 1)
                p_name = p_parts[0].strip()
                p_type = p_parts[1].strip()
            else:
                p_name = tok_name_part.strip()
                p_type = None

            # Clean name: strip backticks, quotes, brackets, parentheses
            p_name = re.sub(r'^[`\'"()\[\]]+', '', p_name)
            p_name = re.sub(r'[`\'"()\[\]]+$', '', p_name).strip()
            p_name = " ".join(p_name.split())

            if p_type:
                p_type = re.sub(r'^[`\'"()]+', '', p_type)
                p_type = re.sub(r'[`\'"()]+$', '', p_type).strip()
                p_type = " ".join(p_type.split())

            if not p_name:
                continue

            params.append(
                FunctionParameter(
                    name=p_name,
                    data_type=p_type,
                    is_optional=is_opt,
                    default_value=default_val,
                )
            )

        return params

    def _enrich_and_resolve(
        self,
        model_name: str,
        source_format: str,
        compat_level: int,
        culture: str,
        tables: List[TableDefinition],
        relationships: List[RelationshipDefinition],
        measures: List[MeasureDefinition],
        raw_queries: Dict[str, Dict[str, Any]],
        functions: Optional[List[FunctionDefinition]] = None,
    ) -> PBIPSemanticModel:
        """
        Executes the resolution algorithms:
        1. Power Query M lineage (root data sources & multi-hop chains)
        2. Star Schema & Snowflake outrigger paths (Fact -> Dim -> Lookup)
        3. DAX Measure & UDF Function dependency DAG
        """
        # --- 1. Power Query M Lineage Resolution ---
        m_resolver = MLineageResolver(raw_queries)
        for tbl in tables:
            lineage = m_resolver.get_lineage_for_table(tbl.name)
            if lineage:
                tbl.power_query_lineage = lineage
                tbl.root_data_sources = lineage.root_sources
                tbl.upstream_queries_chain = lineage.all_upstream_queries
            elif tbl.is_inherited:
                entity_label = tbl.inherited_entity_name or tbl.name
                conn_str = f"Entity: {entity_label}"
                if tbl.inherited_expression_source:
                    conn_str += f" (Source: {tbl.inherited_expression_source})"
                tbl.root_data_sources = [
                    PowerQuerySource(
                        source_type="INHERITED_ENTITY",
                        connection_string=conn_str,
                        endpoint_or_path=entity_label,
                    )
                ]

        cfg = getattr(self, "active_config", None) or self.config
        if cfg is None:
            from .docgen.config import DocGenConfig
            cfg = DocGenConfig()

        include_inherited = getattr(cfg, "include_inherited_entities", False) if cfg else False
        for tbl in tables:
            if tbl.is_inherited:
                tbl.out_of_scope = not include_inherited
        for m in measures:
            if m.is_inherited or m.is_external_measure:
                m.out_of_scope = not include_inherited

        shared_queries = [
            node for node in m_resolver.get_all_nodes().values() if node.is_staging
        ]
        all_root_sources = m_resolver.get_all_root_sources()

        # --- Filter Excluded Tables according to configuration BEFORE Topology Estimation ---
        excluded_names = set()
        if hasattr(cfg, "is_table_excluded"):
            excluded_names = {t.name for t in tables if cfg.is_table_excluded(t.name)}

        if excluded_names:
            tables = [t for t in tables if t.name not in excluded_names]
            relationships = [
                r for r in relationships
                if r.from_table not in excluded_names and r.to_table not in excluded_names
            ]
            measures = [m for m in measures if m.table not in excluded_names]
            for m in measures:
                m.referenced_tables = [t for t in m.referenced_tables if t not in excluded_names]
                m.referenced_columns = [
                    rc for rc in m.referenced_columns if rc.get("table") not in excluded_names
                ]
            for fn in (functions or []):
                fn.referenced_tables = [t for t in fn.referenced_tables if t not in excluded_names]
                fn.referenced_columns = [
                    rc for rc in fn.referenced_columns if rc.get("table") not in excluded_names
                ]

        # --- 2. Star Schema & Snowflake Outrigger Resolution ---
        star_resolver = StarSchemaResolver(tables, relationships)
        star_resolver.classify_tables()
        star_topology = star_resolver.resolve_topology_and_snowflakes()

        # --- 3. DAX Measure & Function Dependency Resolution ---
        # Ensure tables defined with DAX (e.g. calculated tables) do not erroneously enter the measures list
        known_table_names = {t.name for t in tables}
        valid_measures = []
        for m in measures:
            if m.name in known_table_names and (not m.table or m.table == m.name):
                # Erroneous table entry placed in measures
                continue
            valid_measures.append(m)
        measures = valid_measures

        func_list = functions or []
        measure_resolver = MeasureDependencyResolver(measures, tables, functions=func_list)
        measure_dag = measure_resolver.analyze()

        # Assemble full model
        model = PBIPSemanticModel(
            model_name=model_name,
            source_format=source_format,
            compatibility_level=compat_level,
            culture=culture,
            tables=tables,
            relationships=relationships,
            measures=measures,
            functions=func_list,
            shared_queries=shared_queries,
            expressions=shared_queries,
            data_sources_summary=all_root_sources,
            star_schema=star_topology,
            measure_dependency_dag=measure_dag,
            excluded_tables_count=len(excluded_names),
            excluded_tables_list=sorted(list(excluded_names)),
        )

        return model
