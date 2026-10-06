"""
DAX Measure Dependency & Lineage Analyzer.
Parses DAX expressions to extract:
- References to other measures ([MeasureName] or 'Table'[MeasureName])
- References to table columns ('Table'[ColumnName] or Table[ColumnName])
- Calculation DAG (Directed Acyclic Graph)
- Topological sort & calculation depth
- Impact analysis (downstream referenced_by index)
Vanilla Python implementation.
"""

import re
from typing import Dict, List, Set, Tuple, Optional, Any
from .model_schema import MeasureDefinition, TableDefinition, FunctionDefinition


class MeasureDependencyResolver:
    """
    Parses DAX formulas, resolves measure-to-measure DAG,
    computes calculation depth, and tracks column/table/function dependencies.
    """

    def __init__(
        self,
        measures: List[MeasureDefinition],
        tables: List[TableDefinition],
        functions: Optional[List[FunctionDefinition]] = None,
    ):
        self.measures_map: Dict[str, MeasureDefinition] = {m.name: m for m in measures}
        self.tables_map: Dict[str, TableDefinition] = {t.name: t for t in tables}
        self.functions_list: List[FunctionDefinition] = functions or []
        self.functions_map: Dict[str, FunctionDefinition] = {f.name: f for f in self.functions_list}
        self.functions_lookup: Dict[str, str] = {f.name.lower(): f.name for f in self.functions_list}
        
        # Build lookup set of all column keys: (table_name, column_name) and naked column names
        self.known_columns: Set[Tuple[str, str]] = set()
        for t in tables:
            for c in t.columns:
                self.known_columns.add((t.name, c.name))

    def analyze(self) -> Dict[str, List[str]]:
        """
        Executes full dependency analysis across all measures and UDF functions.
        Returns the direct dependency DAG {measure_name: [dep_measure1, dep_measure2]}.
        """
        # Step 1: Extract direct measure, function & column references from DAX
        for measure_name, measure in self.measures_map.items():
            direct_measures, col_refs, table_refs, direct_funcs = self._parse_dax_references(
                measure.dax_expression, measure_name
            )
            measure.direct_measure_dependencies = sorted(list(direct_measures))
            measure.referenced_functions = sorted(list(direct_funcs))
            measure.referenced_columns = [
                {"table": t, "column": c} for t, c in sorted(list(col_refs))
            ]
            measure.referenced_tables = sorted(list(table_refs))

        # Step 2: Inverted index - compute downstream dependencies for measures and functions
        for measure_name, measure in self.measures_map.items():
            # Measure -> Measure downstream
            for dep in measure.direct_measure_dependencies:
                if dep in self.measures_map:
                    if measure_name not in self.measures_map[dep].downstream_measures:
                        self.measures_map[dep].downstream_measures.append(measure_name)
            
            # Measure -> Function downstream (Function is called by Measure)
            for fn_dep in measure.referenced_functions:
                if fn_dep in self.functions_map:
                    if measure_name not in self.functions_map[fn_dep].downstream_measures:
                        self.functions_map[fn_dep].downstream_measures.append(measure_name)

        # Step 3: Analyze functions expressions for inter-function or column references
        for fn_name, fn_obj in self.functions_map.items():
            _, fn_cols, fn_tables, fn_funcs = self._parse_dax_references(
                fn_obj.expression, current_measure_name=""
            )
            fn_obj.referenced_functions = sorted([f for f in fn_funcs if f != fn_name])
            fn_obj.referenced_columns = [
                {"table": t, "column": c} for t, c in sorted(list(fn_cols))
            ]
            fn_obj.referenced_tables = sorted(list(fn_tables))

            for called_fn in fn_obj.referenced_functions:
                if called_fn in self.functions_map:
                    if fn_name not in self.functions_map[called_fn].downstream_functions:
                        self.functions_map[called_fn].downstream_functions.append(fn_name)

        # Sort all downstream lists for consistency
        for fn_obj in self.functions_map.values():
            fn_obj.downstream_measures = sorted(list(set(fn_obj.downstream_measures)))
            fn_obj.downstream_functions = sorted(list(set(fn_obj.downstream_functions)))

        # Step 4: Compute transitive upstream measures & calculation depth (topological)
        dag: Dict[str, List[str]] = {}
        for measure_name, measure in self.measures_map.items():
            dag[measure_name] = measure.direct_measure_dependencies
            all_upstream = self._get_transitive_upstream(measure_name)
            measure.all_upstream_measures = sorted(list(all_upstream))
            measure.calculation_depth = self._calculate_depth(measure_name, visited=set())

        return dag

    def _parse_dax_references(
        self, dax: str, current_measure_name: str
    ) -> Tuple[Set[str], Set[Tuple[str, str]], Set[str], Set[str]]:
        """
        Extracts measures, columns, tables, and UDF functions from DAX string.
        DAX patterns:
        - Table[Column] or 'Table Name'[Column]
        - [Measure] (naked bracket)
        - FunctionName(...) (invocations of model UDF functions)
        """
        if not dax:
            return set(), set(), set(), set()

        direct_measures: Set[str] = set()
        referenced_columns: Set[Tuple[str, str]] = set()
        referenced_tables: Set[str] = set()
        referenced_functions: Set[str] = set()

        # Strip line comments (// or --) and block comments (/* ... */)
        cleaned_dax = re.sub(r'--.*?$', '', dax, flags=re.MULTILINE)
        cleaned_dax = re.sub(r'//.*?$', '', cleaned_dax, flags=re.MULTILINE)
        cleaned_dax = re.sub(r'/\*.*?\*/', '', cleaned_dax, flags=re.DOTALL)

        # Check for UDF function invocations
        # e.g. SafeDivide( ... ), 'Safe Divide'( ... ), [SafeDivide]( ... )
        if self.functions_lookup:
            # Pattern A: identifier followed by '('
            fn_call_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\(')
            for m in fn_call_pattern.finditer(cleaned_dax):
                ident = m.group(1).strip()
                ident_lower = ident.lower()
                # If identifier contains dot (e.g. Model.SafeDivide), take the last token
                if "." in ident_lower:
                    ident_lower = ident_lower.split(".")[-1]
                if ident_lower in self.functions_lookup:
                    referenced_functions.add(self.functions_lookup[ident_lower])

            # Pattern B: quoted identifier followed by '(': 'Function Name'(
            quoted_fn_pattern = re.compile(r"\'([^\']+)\'\s*\(")
            for m in quoted_fn_pattern.finditer(cleaned_dax):
                q_name = m.group(1).strip().lower()
                if q_name in self.functions_lookup:
                    referenced_functions.add(self.functions_lookup[q_name])

            # Pattern C: bracketed identifier followed by '(': [FunctionName](
            bracketed_fn_pattern = re.compile(r"\[([^\]]+)\]\s*\(")
            for m in bracketed_fn_pattern.finditer(cleaned_dax):
                b_name = m.group(1).strip().lower()
                if b_name in self.functions_lookup:
                    referenced_functions.add(self.functions_lookup[b_name])

        # Pattern 1: Explicit table and bracket: 'Table Name'[ColumnOrMeasure] or TableName[ColumnOrMeasure]
        table_bracket_pattern = re.compile(
            r"(?:'([^']+)'|([a-zA-Z_][a-zA-Z0-9_\s]*))\s*\[([^\]]+)\]"
        )

        # We will keep track of character spans matched by pattern 1 to avoid double-matching naked brackets
        matched_spans = []

        for match in table_bracket_pattern.finditer(cleaned_dax):
            matched_spans.append(match.span())
            table_name = match.group(1) or match.group(2)
            table_name = table_name.strip() if table_name else ""
            item_name = match.group(3).strip()

            # Check if this table actually exists in our model
            if table_name in self.tables_map:
                referenced_tables.add(table_name)
                # Check if it's a known measure stored in this table
                if item_name in self.measures_map and item_name != current_measure_name:
                    direct_measures.add(item_name)
                else:
                    referenced_columns.add((table_name, item_name))
            else:
                # If table_name is not a known table, check if item_name is a known measure
                if item_name in self.measures_map and item_name != current_measure_name:
                    direct_measures.add(item_name)

        # Pattern 2: Naked brackets [Item Name]
        naked_bracket_pattern = re.compile(r'\[([^\]]+)\]')
        for match in naked_bracket_pattern.finditer(cleaned_dax):
            start, end = match.span()
            # If this naked bracket was part of a Table[Item] match, skip
            if any(span_start <= start and end <= span_end for span_start, span_end in matched_spans):
                continue

            item_name = match.group(1).strip()
            # In DAX, naked brackets [Measure] preferentially resolve to measures
            if item_name in self.measures_map and item_name != current_measure_name:
                direct_measures.add(item_name)
            else:
                # Could be a column reference in a row context (e.g. inside FILTER or ADDCOLUMNS)
                # Check if matches any column in the model
                for tbl_name, col_name in self.known_columns:
                    if col_name == item_name:
                        referenced_columns.add((tbl_name, col_name))
                        referenced_tables.add(tbl_name)
                        break

        return direct_measures, referenced_columns, referenced_tables, referenced_functions

    def _get_transitive_upstream(self, measure_name: str) -> Set[str]:
        """Calculates transitive closure of all upstream measures."""
        upstream: Set[str] = set()
        queue = list(self.measures_map[measure_name].direct_measure_dependencies)

        while queue:
            curr = queue.pop(0)
            if curr in upstream or curr not in self.measures_map:
                continue
            upstream.add(curr)
            for parent in self.measures_map[curr].direct_measure_dependencies:
                if parent not in upstream:
                    queue.append(parent)

        return upstream

    def _calculate_depth(self, measure_name: str, visited: Set[str]) -> int:
        """
        Recursively calculates calculation depth.
        Base measures = 0.
        Measures calling base measures = 1, etc.
        """
        if measure_name in visited or measure_name not in self.measures_map:
            return 0  # prevent infinite loop in case of cyclic DAX

        measure = self.measures_map[measure_name]
        if not measure.direct_measure_dependencies:
            return 0

        visited.add(measure_name)
        max_child_depth = 0
        for dep in measure.direct_measure_dependencies:
            if dep in self.measures_map:
                dep_depth = self._calculate_depth(dep, set(visited))
                if dep_depth > max_child_depth:
                    max_child_depth = dep_depth

        return max_child_depth + 1
