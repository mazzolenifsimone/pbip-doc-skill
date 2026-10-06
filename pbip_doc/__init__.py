"""
pbip-doc-skill
Automatic extraction and semantic model dependency resolver for Power BI Project (PBIP) files.
"""

from .model_schema import (
    PBIPSemanticModel,
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    MeasureDefinition,
    PowerQuerySource,
    PowerQueryLineageNode,
    SnowflakePath,
    TableRole,
)
from .parser import PBIPParser
from .m_lineage import MLineageResolver
from .star_schema import StarSchemaResolver
from .measure_analyzer import MeasureDependencyResolver
from .docgen import DocGenConfig, MarkdownDocGenerator

__version__ = "0.2.0"
__all__ = [
    "PBIPSemanticModel",
    "TableDefinition",
    "ColumnDefinition",
    "RelationshipDefinition",
    "MeasureDefinition",
    "PowerQuerySource",
    "PowerQueryLineageNode",
    "SnowflakePath",
    "TableRole",
    "PBIPParser",
    "MLineageResolver",
    "StarSchemaResolver",
    "MeasureDependencyResolver",
    "DocGenConfig",
    "MarkdownDocGenerator",
]
