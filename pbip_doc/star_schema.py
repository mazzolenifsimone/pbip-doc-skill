"""
Star Schema & Snowflake Topology Resolver.
Implements a topological graph DAG heuristic to classify tables into:
- FACT
- DIMENSION
- LOOKUP_OUTRIGGER (Snowflake)
- BRIDGE (including classic M2M junction and SCD / Key-Mapping bridge tables)
- DATE_DIMENSION
- CALCULATION_GROUP
- PARAMETER_UTILITY

Resolves full transitive lookup chains from Facts through Dimensions to Outriggers.
Vanilla Python implementation.
"""

import re
from typing import Dict, List, Set, Tuple, Optional, Any
from .model_schema import (
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    SnowflakePath,
    TableRole,
    TableRoleClassification,
    StarSchemaTopology,
)


class StarSchemaResolver:
    """
    Analyzes relationship graphs, cardinalities, filtering directions, and column structures
    to classify model tables and trace snowflake lookup hierarchies.
    Uses a topological graph DAG approach with specialized bridge table resolution.
    """

    FACT_PREFIXES = ("fact", "fact_", "f_", "tbl_fact", "orders", "sales", "transactions", "movements", "ledger", "events", "gl")
    DIM_PREFIXES = ("dim", "dim_", "d_", "tbl_dim", "customer", "product", "store", "employee", "vendor", "account", "client")
    LOOKUP_PREFIXES = ("lookup", "lkp", "outrigger", "geo", "geography", "category", "subcategory", "country", "postal", "currency")
    DATE_NAMES = ("date", "calendar", "dimdate", "calendario", "dim_date", "dates", "tempo", "d_date", "d_calendar")

    def __init__(
        self,
        tables: List[TableDefinition],
        relationships: List[RelationshipDefinition],
    ):
        self.tables_map: Dict[str, TableDefinition] = {t.name: t for t in tables}
        self.relationships = [r for r in relationships if r.is_active]  # active primary relationships
        self.all_relationships = relationships
        self.fact_tables: List[str] = []
        self.dim_tables: List[str] = []
        self.lookup_tables: List[str] = []
        self.bridge_tables: List[str] = []
        self.date_tables: List[str] = []
        self.utility_tables: List[str] = []

    def _is_key_column(self, col: ColumnDefinition) -> bool:
        if col.is_key:
            return True
        name_l = col.name.lower()
        if name_l.endswith(("key", "id", "_id", "_key", "code", "cd")):
            return True
        if name_l in ("key", "id", "guid", "uuid", "sk", "bk", "pk", "fk"):
            return True
        return False

    def _is_metric_column(self, col: ColumnDefinition) -> bool:
        name_l = col.name.lower()
        type_l = col.data_type.lower()
        if type_l not in ("int64", "decimal", "double", "currency", "integer", "number", "float"):
            return False
        if self._is_key_column(col):
            return False
        if name_l in ("year", "month", "day", "quarter", "week", "datekey", "sort", "order", "index", "flag", "status", "version"):
            return False
        return True

    def _is_minimal_payload_bridge(self, table: TableDefinition) -> bool:
        """
        Bridge tables typically consist almost purely of keys/IDs (e.g. sk + id or dim1_id + dim2_id)
        with no business measures (sales/amounts) and no rich textual descriptions.
        """
        col_count = len(table.columns)
        if col_count == 0:
            return False
        metric_cols = [c for c in table.columns if self._is_metric_column(c)]
        if len(metric_cols) > 0:
            return False
        key_cols = [c for c in table.columns if self._is_key_column(c)]
        # Allow up to 4 columns, e.g. (sk, id, valid_from, valid_to) or (dim1_id, dim2_id)
        if col_count <= 4 and len(key_cols) >= max(1, col_count - 2):
            return True
        return False

    def _is_date_table(self, table: TableDefinition, many_count: int, one_count: int) -> bool:
        lower_name = table.name.lower()
        if any(d == lower_name or lower_name.startswith(f"{d}_") or lower_name.startswith(f"{d} ") or lower_name.endswith(f"_{d}") for d in self.DATE_NAMES):
            return True
        date_cols = [c.name.lower() for c in table.columns if c.name.lower() in ("date", "data", "datekey", "year", "month", "day", "quarter", "anno", "mese")]
        if len(date_cols) >= 2 and many_count == 0:
            return True
        if table.source_type == "CalculatedTable" and table.expression:
            if re.search(r'\b(?:calendar|calendarauto)\s*\(', table.expression, re.IGNORECASE):
                return True
        return False

    def classify_tables(self):
        """
        Classifies model tables using a topological graph DAG hierarchy:
        0. Special tables: Calculation groups & Disconnected Parameter/Utility tables
        1. Date dimensions
        2. Bridge tables (both M2M junction and SCD / Key-Mapping bridge tables)
        3. Fact tables (Terminal Many-side sinks of the model)
        4. Dimension tables (Direct parents filtering Fact tables, regardless of lookup outriggers)
        5. Lookup / Outrigger tables (Snowflake hierarchies filtering dimensions)
        6. Fact-to-Fact Header/Detail refinement
        7. Fallback for ambiguous structures
        """
        # Step 1: Pre-calculate relationship graph statistics
        outgoing_many_rels: Dict[str, List[RelationshipDefinition]] = {name: [] for name in self.tables_map}
        incoming_one_rels: Dict[str, List[RelationshipDefinition]] = {name: [] for name in self.tables_map}
        many_to_many_rels: Dict[str, List[RelationshipDefinition]] = {name: [] for name in self.tables_map}
        one_to_one_rels: Dict[str, List[RelationshipDefinition]] = {name: [] for name in self.tables_map}
        bidirectional_rels: Dict[str, List[RelationshipDefinition]] = {name: [] for name in self.tables_map}

        for rel in self.relationships:
            if rel.cross_filtering_behavior in ("Both", "both"):
                bidirectional_rels[rel.from_table].append(rel)
                bidirectional_rels[rel.to_table].append(rel)

            if rel.cardinality in ("1:1", "OneToOne"):
                one_to_one_rels[rel.from_table].append(rel)
                one_to_one_rels[rel.to_table].append(rel)
            elif rel.cardinality in ("N:N", "ManyToMany"):
                many_to_many_rels[rel.from_table].append(rel)
                many_to_many_rels[rel.to_table].append(rel)
            else:
                # Standard 1:N / N:1 (from_table is Many, to_table is One)
                outgoing_many_rels[rel.from_table].append(rel)
                incoming_one_rels[rel.to_table].append(rel)

        parent_tables: Dict[str, Set[str]] = {
            name: {rel.to_table for rel in outgoing_many_rels[name]} for name in self.tables_map
        }
        child_tables: Dict[str, Set[str]] = {
            name: {rel.from_table for rel in incoming_one_rels[name]} for name in self.tables_map
        }

        # Step 0: Calculation Groups & Disconnected Utility Tables
        for name, table in self.tables_map.items():
            if table.source_type == "CalculationGroup":
                self._assign_role(table, TableRole.CALCULATION_GROUP, 1.0, ["Explicit Power BI Calculation Group object"])
                continue

            total_rels = (
                len(outgoing_many_rels[name]) + len(incoming_one_rels[name])
                + len(many_to_many_rels[name]) + len(one_to_one_rels[name])
            )
            if total_rels == 0:
                if self._is_date_table(table, 0, 0):
                    criteria = ["Disconnected Date/Calendar table"]
                    if table.source_type == "CalculatedTable" and table.expression and re.search(r'\b(?:calendar|calendarauto)\s*\(', table.expression, re.IGNORECASE):
                        criteria.append("DAX Date table generator: CALENDAR / CALENDARAUTO")
                    self._assign_role(table, TableRole.DATE_DIMENSION, 0.90, criteria)
                else:
                    if table.source_type == "CalculatedTable":
                        self._assign_role(
                            table, TableRole.PARAMETER_UTILITY, 0.95,
                            [f"Disconnected DAX calculated table ({len(table.columns)} columns) - Slicer, Parameter or Measure container"]
                        )
                    else:
                        self._assign_role(
                            table, TableRole.PARAMETER_UTILITY, 0.95,
                            [f"Disconnected table with 0 active relationships ({len(table.columns)} columns) - Slicer, Parameter or Measure container"]
                        )

        # Step 1: Date Dimensions
        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue
            many_count = len(outgoing_many_rels[name])
            one_count = len(incoming_one_rels[name])
            if self._is_date_table(table, many_count, one_count):
                criteria = [f"Name or columns matched canonical date/calendar dimension patterns ({len(table.columns)} cols)"]
                if table.source_type == "CalculatedTable" and table.expression and re.search(r'\b(?:calendar|calendarauto)\s*\(', table.expression, re.IGNORECASE):
                    criteria.append("DAX Date table generator: CALENDAR / CALENDARAUTO")
                self._assign_role(
                    table, TableRole.DATE_DIMENSION, 0.95,
                    criteria
                )

        # Step 2: Bridge Tables
        # Pattern C: Native Many-to-Many relationships
        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue
            if len(many_to_many_rels[name]) > 0:
                self._assign_role(
                    table, TableRole.BRIDGE, 0.90,
                    [f"Participates in native Many-to-Many relationship ({len(many_to_many_rels[name])} M:M rels)"]
                )
                continue

            many_count = len(outgoing_many_rels[name])
            one_count = len(incoming_one_rels[name])
            is_minimal = self._is_minimal_payload_bridge(table)
            has_bidi = len(bidirectional_rels[name]) > 0

            # Pattern B: SCD / Key-Mapping Bridge Table
            # e.g. DimA[sk] (Many) -> BridgeAB[sk] (One) with Bidirectional, and BridgeAB[id] (One) -> FactB[id] (Many)
            # Table is on the One-side of 2+ relationships, minimal key-only payload, with cross-filtering
            if one_count >= 2 and is_minimal and (has_bidi or any(c in self.tables_map for c in child_tables[name])):
                children_names = list(child_tables[name])
                self._assign_role(
                    table, TableRole.BRIDGE, 0.95,
                    [f"SCD / Key-Mapping Bridge Table: connects multiple entities via dual One-side key mappings ({', '.join(children_names)}) with minimal key-only payload"]
                )
                continue

            # Pattern A: Classic M2M Junction Bridge
            # e.g. DimA (1) <- Bridge (N) -> DimB (1)
            # Table is on the Many-side of 2+ relationships, minimal key-only payload, 0 incoming One-side
            if many_count >= 2 and one_count == 0 and is_minimal:
                parents_names = list(parent_tables[name])
                self._assign_role(
                    table, TableRole.BRIDGE, 0.90,
                    [f"M2M Junction Bridge Table: junction table resolving relationship between parent tables ({', '.join(parents_names)}) with minimal payload"]
                )
                continue

        # Step 3: Fact Tables Detection
        # In a dimensional star schema, Fact tables are the endpoint sinks:
        # they have foreign keys pointing to dimensions (many_count >= 1) and NO other tables point to them as a parent (one_count == 0).
        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue
            many_count = len(outgoing_many_rels[name])
            one_count = len(incoming_one_rels[name])

            if many_count >= 1 and one_count == 0:
                parents = list(parent_tables[name])
                # If this table's only parents are Bridge tables, defer to Step 4 (Dimension via Bridge)
                bridge_names = {t.name for t in self.tables_map.values() if t.role == TableRole.BRIDGE}
                if parents and all(p in bridge_names for p in parents):
                    continue
                self._assign_role(
                    table, TableRole.FACT, 0.95,
                    [f"Topology: Pure Many-side endpoint sink (0 incoming One-side parents, {many_count} outgoing foreign keys to {', '.join(parents)})"]
                )

        # Step 4: Dimension Tables Detection
        # Any table that is directly on the One-side of a Fact table (or connected to a Fact via an SCD bridge) is a DIMENSION.
        # Crucially: Even if this dimension has outgoing Many-to-One relationships to lookup/outrigger tables (Snowflake),
        # its primary identity in the semantic model is DIMENSION!
        fact_names = {t.name for t in self.tables_map.values() if t.role == TableRole.FACT}
        bridge_names = {t.name for t in self.tables_map.values() if t.role == TableRole.BRIDGE}

        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue

            direct_fact_children = [c for c in child_tables[name] if c in fact_names]

            # Also check if this table is connected through a bridge table that links to a Fact
            bridged_facts = []
            for b in (child_tables[name] | parent_tables[name]):
                if b in bridge_names:
                    for f in (child_tables[b] | parent_tables[b]):
                        if f in fact_names and f != name:
                            bridged_facts.append(f)

            if direct_fact_children or bridged_facts:
                linked_facts = sorted(list(set(direct_fact_children + bridged_facts)))
                lookups_outgoing = [p for p in parent_tables[name] if p not in fact_names and p not in bridge_names]
                criteria = [f"Topology: Primary dimension directly filtering Fact table(s): {', '.join(linked_facts)}"]
                if lookups_outgoing:
                    criteria.append(f"Snowflake origin: connects to {len(lookups_outgoing)} outrigger/lookup tables: {', '.join(lookups_outgoing)}")
                self._assign_role(table, TableRole.DIMENSION, 0.95, criteria)

        # Step 5: Lookup / Outrigger Tables Detection (Snowflake)
        # Any remaining table that is on the One-side of relationships, but is NOT directly linked to any Fact table.
        # It is filtered exclusively by DIMENSION tables or other LOOKUP_OUTRIGGER tables.
        dim_names = {t.name for t in self.tables_map.values() if t.role in (TableRole.DIMENSION, TableRole.DATE_DIMENSION)}
        lookup_names: Set[str] = set()

        changed = True
        while changed:
            changed = False
            for name, table in self.tables_map.items():
                if table.role != TableRole.UNKNOWN:
                    continue
                incoming_from = child_tables[name]
                if not incoming_from:
                    continue
                all_from_dims = all(src in dim_names or src in lookup_names for src in incoming_from)
                if all_from_dims:
                    lookup_names.add(name)
                    self._assign_role(
                        table, TableRole.LOOKUP_OUTRIGGER, 0.95,
                        [f"Snowflake Outrigger: Normalized lookup table directly filtering dimension(s)/lookups: {', '.join(incoming_from)} (no direct Fact connection)"]
                    )
                    changed = True

        # Step 6: Fact-to-Fact Header/Detail Refinement
        # A table with one_count > 0 where all incoming children are other Fact tables (e.g. SalesOrderHeader 1:N SalesOrderLine)
        # and has outgoing foreign keys to dimensions.
        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue
            one_count = len(incoming_one_rels[name])
            many_count = len(outgoing_many_rels[name])
            if one_count > 0:
                all_children_are_facts = all(c in fact_names for c in child_tables[name])
                if all_children_are_facts and many_count >= 1:
                    self._assign_role(
                        table, TableRole.FACT, 0.90,
                        [f"Fact Header/Detail: Parent fact table filtering line-item fact table(s) ({', '.join(child_tables[name])}) and pointing to dimensions"]
                    )

        # Step 7: Fallback for any complex or remaining ambiguous tables
        for name, table in self.tables_map.items():
            if table.role != TableRole.UNKNOWN:
                continue
            lower_name = name.lower()
            many_count = len(outgoing_many_rels[name])
            one_count = len(incoming_one_rels[name])

            metric_cols = [c for c in table.columns if self._is_metric_column(c)]
            text_cols = [c for c in table.columns if c.data_type.lower() in ("string", "text", "varchar")]

            fact_score = 0.0
            dim_score = 0.0
            criteria: List[str] = []

            if many_count > one_count:
                fact_score += 0.35
            elif one_count >= many_count and one_count > 0:
                dim_score += 0.35

            if len(metric_cols) >= 2 and len(metric_cols) >= len(text_cols):
                fact_score += 0.30
                criteria.append(f"Payload: Contains {len(metric_cols)} quantitative metric columns")
            elif len(text_cols) > len(metric_cols):
                dim_score += 0.30
                criteria.append(f"Payload: Contains {len(text_cols)} descriptive text attributes")

            if any(lower_name.startswith(p) for p in self.FACT_PREFIXES):
                fact_score += 0.30
            elif any(lower_name.startswith(p) for p in self.DIM_PREFIXES):
                dim_score += 0.30

            role = TableRole.FACT if fact_score > dim_score else TableRole.DIMENSION
            score = max(0.60, min(0.95, fact_score if role == TableRole.FACT else dim_score))
            self._assign_role(table, role, score, criteria or ["Fallback topology and payload heuristic"])

    def _assign_role(self, table: TableDefinition, role: TableRole, score: float, criteria: List[str], details: Optional[Dict[str, Any]] = None):
        table.role = role
        table.classification_reasoning = TableRoleClassification(
            role=role,
            confidence_score=round(score, 2),
            criteria_matched=criteria,
            details=details or {},
        )

    def resolve_topology_and_snowflakes(self) -> StarSchemaTopology:
        """
        Builds the complete Star / Snowflake topology.
        For every Fact table:
        1. Finds all directly connected Dimension and Bridge tables.
        2. Recursively traces all Snowflake/Outrigger paths (Fact -> Dim -> Lookup 1 -> Lookup 2).
        Populates tables and returns StarSchemaTopology.
        """
        topology = StarSchemaTopology()

        # Categorize table lists
        for t in self.tables_map.values():
            if t.role == TableRole.FACT:
                topology.fact_tables.append(t.name)
            elif t.role == TableRole.DIMENSION:
                topology.dimension_tables.append(t.name)
            elif t.role == TableRole.LOOKUP_OUTRIGGER:
                topology.lookup_outrigger_tables.append(t.name)
            elif t.role == TableRole.BRIDGE:
                topology.bridge_tables.append(t.name)
            elif t.role == TableRole.DATE_DIMENSION:
                topology.date_tables.append(t.name)
            else:
                topology.utility_tables.append(t.name)

        # Build adjacency maps
        # Forward lookup map: from_table (Many) -> to_table (One) with join key details
        parent_map: Dict[str, List[Tuple[str, str, str]]] = {name: [] for name in self.tables_map}
        # Reverse map: parent (One) -> children (Many)
        child_map: Dict[str, List[Tuple[str, str, str]]] = {name: [] for name in self.tables_map}

        for rel in self.relationships:
            # from_table -> to_table
            parent_map[rel.from_table].append((rel.to_table, rel.from_column, rel.to_column))
            child_map[rel.to_table].append((rel.from_table, rel.to_column, rel.from_column))

            # Store direct related tables
            if rel.to_table not in self.tables_map[rel.from_table].direct_related_tables:
                self.tables_map[rel.from_table].direct_related_tables.append(rel.to_table)
            if rel.from_table not in self.tables_map[rel.to_table].direct_related_tables:
                self.tables_map[rel.to_table].direct_related_tables.append(rel.from_table)

        # For every Fact table, resolve:
        # 1. connected dimensions
        # 2. transitive snowflake paths to lookup tables
        for fact_name in topology.fact_tables:
            fact_table = self.tables_map[fact_name]
            direct_dims: Set[str] = set()
            reachable_lookups: Set[str] = set()
            snowflake_paths: List[SnowflakePath] = []

            # Step 1: Direct parent tables of Fact (typically Dimensions / Date tables / Bridge tables)
            for target_table, from_col, to_col in parent_map.get(fact_name, []):
                target_obj = self.tables_map.get(target_table)
                if not target_obj:
                    continue

                if target_obj.role in (TableRole.DIMENSION, TableRole.DATE_DIMENSION):
                    direct_dims.add(target_table)
                    if fact_name not in target_obj.connected_facts:
                        target_obj.connected_facts.append(fact_name)

                    # Step 2: Recursive lookup exploration from this Dimension
                    self._trace_snowflake_paths(
                        fact_name=fact_name,
                        dim_name=target_table,
                        curr_node=target_table,
                        current_path=[fact_name, target_table],
                        current_keys=[{"from": f"{fact_name}.{from_col}", "to": f"{target_table}.{to_col}"}],
                        parent_map=parent_map,
                        visited={fact_name, target_table},
                        reachable_lookups=reachable_lookups,
                        snowflake_paths=snowflake_paths,
                    )
                elif target_obj.role == TableRole.BRIDGE:
                    # Bridge table connected to Fact: trace through bridge to find bridged dimensions
                    direct_dims.add(target_table)
                    if fact_name not in target_obj.connected_facts:
                        target_obj.connected_facts.append(fact_name)

                    bridged_nodes = [
                        t for t, _, _ in parent_map.get(target_table, []) if t != fact_name
                    ] + [
                        t for t, _, _ in child_map.get(target_table, []) if t != fact_name
                    ]
                    for b_node in bridged_nodes:
                        b_obj = self.tables_map.get(b_node)
                        if b_obj and b_obj.role in (TableRole.DIMENSION, TableRole.DATE_DIMENSION):
                            direct_dims.add(b_node)
                            if fact_name not in b_obj.connected_facts:
                                b_obj.connected_facts.append(fact_name)

            fact_table.connected_dimensions = sorted(list(direct_dims))
            fact_table.reachable_lookup_tables = sorted(list(reachable_lookups))
            fact_table.snowflake_paths = snowflake_paths

            topology.fact_dimension_map[fact_name] = sorted(list(direct_dims))
            topology.fact_to_outriggers_map[fact_name] = sorted(list(reachable_lookups))
            topology.snowflake_paths.extend(snowflake_paths)

        return topology

    def _trace_snowflake_paths(
        self,
        fact_name: str,
        dim_name: str,
        curr_node: str,
        current_path: List[str],
        current_keys: List[Dict[str, str]],
        parent_map: Dict[str, List[Tuple[str, str, str]]],
        visited: Set[str],
        reachable_lookups: Set[str],
        snowflake_paths: List[SnowflakePath],
    ):
        """Recursively finds all outrigger/lookup tables reachable through a dimension."""
        for target, from_col, to_col in parent_map.get(curr_node, []):
            if target in visited:
                continue

            target_table_obj = self.tables_map.get(target)
            if not target_table_obj:
                continue

            # We found a snowflake hop! (Dimension -> Lookup)
            new_path = list(current_path) + [target]
            new_keys = list(current_keys) + [{"from": f"{curr_node}.{from_col}", "to": f"{target}.{to_col}"}]
            reachable_lookups.add(target)

            snowflake_paths.append(
                SnowflakePath(
                    fact_table=fact_name,
                    dimension_table=dim_name,
                    lookup_table=target,
                    path=new_path,
                    join_keys=new_keys,
                    hops=len(new_path) - 2,  # number of hops past direct dimension
                )
            )

            # Continue recursing (e.g. DimCustomer -> DimGeography -> DimCountry)
            self._trace_snowflake_paths(
                fact_name=fact_name,
                dim_name=dim_name,
                curr_node=target,
                current_path=new_path,
                current_keys=new_keys,
                parent_map=parent_map,
                visited=visited | {target},
                reachable_lookups=reachable_lookups,
                snowflake_paths=snowflake_paths,
            )
