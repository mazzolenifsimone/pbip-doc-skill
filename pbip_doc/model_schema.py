"""
Data contracts and schema definitions for the PBIP documentation JSON output.
Fully serializable with Python standard library.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any


class TableRole(str, Enum):
    FACT = "FACT"
    DIMENSION = "DIMENSION"
    LOOKUP_OUTRIGGER = "LOOKUP_OUTRIGGER"
    BRIDGE = "BRIDGE"
    CALCULATION_GROUP = "CALCULATION_GROUP"
    DATE_DIMENSION = "DATE_DIMENSION"
    PARAMETER_UTILITY = "PARAMETER_UTILITY"
    UNKNOWN = "UNKNOWN"


class Cardinality(str, Enum):
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    ONE_TO_ONE = "1:1"
    MANY_TO_MANY = "N:N"


class CrossFilterDirection(str, Enum):
    SINGLE = "Single"
    BOTH = "Both"


@dataclass
class PowerQuerySource:
    source_type: str  # e.g., "SQL_SERVER", "SHAREPOINT", "ODATA", "EXCEL", "CSV", "WEB", "LAKEHOUSE", "MANUAL"
    connection_string: str  # Server/database or URL or file path
    server: Optional[str] = None
    database: Optional[str] = None
    endpoint_or_path: Optional[str] = None
    authentication_mode: Optional[str] = None
    raw_snippet: Optional[str] = None


@dataclass
class PowerQueryLineageStep:
    step_name: str
    operation: str  # e.g., "Source", "Filter", "Merge", "Append", "SelectColumns"
    referenced_queries: List[str] = field(default_factory=list)
    raw_m_code: Optional[str] = None


@dataclass
class PowerQueryLineageNode:
    query_name: str
    target_table: Optional[str]  # Name of table loaded into the model, if any
    is_staging: bool  # True if this is an internal/unloaded staging query
    direct_dependencies: List[str] = field(default_factory=list)  # Queries directly referenced
    all_upstream_queries: List[str] = field(default_factory=list)  # Transitive upstream queries
    downstream_queries: List[str] = field(default_factory=list)
    downstream_tables: List[str] = field(default_factory=list)  # Final model tables fed by this query
    root_sources: List[PowerQuerySource] = field(default_factory=list)  # Ultimate physical data sources
    full_m_expression: str = ""
    steps: List[PowerQueryLineageStep] = field(default_factory=list)
    description: Optional[str] = None
    query_group: Optional[str] = None
    lineage_tag: Optional[str] = None
    expression_kind: Optional[str] = None  # "m", "table", "parameter", etc.
    is_inline_table: bool = False
    inline_table_columns: List[str] = field(default_factory=list)
    inline_table_column_types: Dict[str, str] = field(default_factory=dict)
    inline_table_rows: List[List[Any]] = field(default_factory=list)
    inline_table_markdown: Optional[str] = None


@dataclass
class FunctionParameter:
    name: str
    data_type: Optional[str] = None
    is_optional: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FunctionDefinition:
    name: str
    expression: str
    parameters: List[FunctionParameter] = field(default_factory=list)
    parameters_signature: str = ""
    return_type: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    lineage_tag: Optional[str] = None
    
    # Dependencies
    referenced_functions: List[str] = field(default_factory=list)  # Other UDFs called by this UDF
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)
    referenced_tables: List[str] = field(default_factory=list)
    downstream_measures: List[str] = field(default_factory=list)  # Measures that call this UDF
    downstream_functions: List[str] = field(default_factory=list) # Other UDFs that call this UDF


@dataclass
class ColumnDefinition:
    name: str
    data_type: str
    is_hidden: bool = False
    is_key: bool = False
    is_calculated: bool = False  # True if this is a DAX calculated column
    format_string: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None  # DAX formula if calculated
    display_folder: Optional[str] = None


@dataclass
class RelationshipDefinition:
    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str  # 1:N, N:1, 1:1, N:N
    cross_filtering_behavior: str  # Single, Both
    is_active: bool = True
    security_filtering_behavior: Optional[str] = "None"


@dataclass
class SnowflakePath:
    """
    Represents a transitive path from a Fact table through a Dimension to an Outrigger/Lookup table.
    e.g. FactSales -> DimCustomer -> DimGeography -> DimCountry
    """
    fact_table: str
    dimension_table: str
    lookup_table: str
    path: List[str]  # e.g., ["FactSales", "DimCustomer", "DimGeography"]
    join_keys: List[Dict[str, str]]  # list of {from: "DimCustomer.GeographyKey", to: "DimGeography.GeographyKey"}
    hops: int = 1


@dataclass
class TableRoleClassification:
    role: TableRole
    confidence_score: float  # 0.0 to 1.0
    criteria_matched: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncrementalRefreshPolicy:
    is_enabled: bool = False
    policy_type: Optional[str] = "basic"
    mode: Optional[str] = "import"  # "import" or "hybrid"
    rolling_window_periods: Optional[int] = None
    rolling_window_granularity: Optional[str] = None  # "year", "quarter", "month", "day"
    incremental_periods: Optional[int] = None
    incremental_granularity: Optional[str] = None  # "year", "quarter", "month", "day"
    polling_expression: Optional[str] = None  # detect data changes query
    source_expression: Optional[str] = None
    raw_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableDefinition:
    name: str
    role: TableRole
    classification_reasoning: TableRoleClassification
    columns: List[ColumnDefinition] = field(default_factory=list)
    is_hidden: bool = False
    description: Optional[str] = None
    source_type: str = "PowerQuery"  # "PowerQuery", "CalculatedTable", "CalculationGroup", "InheritedEntity"
    expression: Optional[str] = None  # DAX table expression if calculated (partition = calculated)
    
    # DAX Lineage / Dependencies (for CalculatedTable)
    referenced_tables: List[str] = field(default_factory=list)
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)
    referenced_measures: List[str] = field(default_factory=list)
    referenced_functions: List[str] = field(default_factory=list)
    
    # Power Query Lineage
    power_query_lineage: Optional[PowerQueryLineageNode] = None
    root_data_sources: List[PowerQuerySource] = field(default_factory=list)
    upstream_queries_chain: List[str] = field(default_factory=list)
    
    # Incremental Refresh Policy
    incremental_refresh_policy: Optional[IncrementalRefreshPolicy] = None
    
    # Relationships & Star Schema connections
    direct_related_tables: List[str] = field(default_factory=list)
    connected_dimensions: List[str] = field(default_factory=list)  # If this is a Fact
    connected_facts: List[str] = field(default_factory=list)  # If this is a Dim
    reachable_lookup_tables: List[str] = field(default_factory=list)  # For facts: dims of dims
    snowflake_paths: List[SnowflakePath] = field(default_factory=list)

    # Inherited Entity / Composite model flags
    is_inherited: bool = False
    inherited_entity_name: Optional[str] = None
    inherited_expression_source: Optional[str] = None
    out_of_scope: bool = False


@dataclass
class MeasureDefinition:
    name: str
    table: str
    dax_expression: str
    format_string: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    display_folder: Optional[str] = None
    
    # Measure dependency resolution
    calculation_depth: int = 0  # 0 = base measure depending only on columns/scalars
    direct_measure_dependencies: List[str] = field(default_factory=list)  # Measures directly called
    all_upstream_measures: List[str] = field(default_factory=list)  # Transitive closure of measures
    referenced_functions: List[str] = field(default_factory=list)  # UDF functions directly called
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)  # [{"table": "FactSales", "column": "Amount"}]
    referenced_tables: List[str] = field(default_factory=list)
    downstream_measures: List[str] = field(default_factory=list)  # Measures that call this measure

    # Inherited Measure / Composite model flags
    is_inherited: bool = False
    is_external_measure: bool = False
    out_of_scope: bool = False


@dataclass
class StarSchemaTopology:
    fact_tables: List[str] = field(default_factory=list)
    dimension_tables: List[str] = field(default_factory=list)
    lookup_outrigger_tables: List[str] = field(default_factory=list)
    bridge_tables: List[str] = field(default_factory=list)
    date_tables: List[str] = field(default_factory=list)
    utility_tables: List[str] = field(default_factory=list)
    fact_dimension_map: Dict[str, List[str]] = field(default_factory=dict)
    fact_to_outriggers_map: Dict[str, List[str]] = field(default_factory=dict)
    snowflake_paths: List[SnowflakePath] = field(default_factory=list)


@dataclass
class PBIPSemanticModel:
    model_name: str
    source_format: str  # "TMDL" or "BIM"
    compatibility_level: Optional[int] = None
    culture: Optional[str] = "en-US"
    created_timestamp: Optional[str] = None
    
    # Main model elements
    tables: List[TableDefinition] = field(default_factory=list)
    relationships: List[RelationshipDefinition] = field(default_factory=list)
    measures: List[MeasureDefinition] = field(default_factory=list)
    functions: List[FunctionDefinition] = field(default_factory=list)
    
    # Power Query Lineage resolution
    shared_queries: List[PowerQueryLineageNode] = field(default_factory=list)
    expressions: List[PowerQueryLineageNode] = field(default_factory=list)
    data_sources_summary: List[PowerQuerySource] = field(default_factory=list)
    
    # Star schema & Snowflake resolution
    star_schema: Optional[StarSchemaTopology] = None
    
    # Measure dependency graph
    measure_dependency_dag: Dict[str, List[str]] = field(default_factory=dict)
    
    # Excluded tables tracking
    excluded_tables_count: int = 0
    excluded_tables_list: List[str] = field(default_factory=list)
    
    def filter_excluded_tables(self, is_excluded_fn) -> None:
        """
        Purges auto-generated or user-excluded tables (e.g. LocalDateTable_*, DateTableTemplate_*)
        across all dimensions of the semantic model: tables list, relationships, star schema,
        snowflake paths, and measure dependency references.
        """
        excluded_names = {t.name for t in self.tables if is_excluded_fn(t.name)}
        if not excluded_names:
            return

        self.excluded_tables_count = len(excluded_names)
        self.excluded_tables_list = sorted(list(excluded_names))

        # 1. Filter Tables
        self.tables = [t for t in self.tables if t.name not in excluded_names]

        # 2. Filter Relationships (both from and to)
        self.relationships = [
            r for r in self.relationships
            if r.from_table not in excluded_names and r.to_table not in excluded_names
        ]

        # 3. Filter Measures belonging to excluded tables
        self.measures = [m for m in self.measures if m.table not in excluded_names]

        # Clean measure dependencies and referenced columns/tables
        for m in self.measures:
            m.referenced_tables = [t for t in m.referenced_tables if t not in excluded_names]
            m.referenced_columns = [
                rc for rc in m.referenced_columns
                if rc.get("table") not in excluded_names
            ]

        # Clean function dependencies
        valid_measure_names = {m.name for m in self.measures}
        for fn in self.functions:
            fn.referenced_tables = [t for t in fn.referenced_tables if t not in excluded_names]
            fn.referenced_columns = [
                rc for rc in fn.referenced_columns
                if rc.get("table") not in excluded_names
            ]
            fn.downstream_measures = [dm for dm in fn.downstream_measures if dm in valid_measure_names]

        # Clean calculated table dependencies
        for t in self.tables:
            if t.source_type == "CalculatedTable":
                t.referenced_tables = [rt for rt in t.referenced_tables if rt not in excluded_names]
                t.referenced_columns = [
                    rc for rc in t.referenced_columns
                    if rc.get("table") not in excluded_names
                ]
                t.referenced_measures = [rm for rm in t.referenced_measures if rm in valid_measure_names]

        # 4. Clean and re-resolve Star Schema topology with remaining in-scope tables & relationships
        # This re-evaluates all surviving tables (e.g. date parameter tables previously linked
        # solely to auto date tables now have 0 relationships and become PARAMETER_UTILITY).
        from .star_schema import StarSchemaResolver
        resolver = StarSchemaResolver(self.tables, self.relationships)
        resolver.classify_tables()
        self.star_schema = resolver.resolve_topology_and_snowflakes()

        # 6. Clean M Lineage downstream tables
        for node in self.shared_queries:
            node.downstream_tables = [
                dt for dt in node.downstream_tables if dt not in excluded_names
            ]
        for node in self.expressions:
            node.downstream_tables = [
                dt for dt in node.downstream_tables if dt not in excluded_names
            ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire model to standard Python dictionary ready for JSON dump."""
        return asdict(self)
