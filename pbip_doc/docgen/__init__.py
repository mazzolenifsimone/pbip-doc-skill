"""
Documentation Generator Package for PBIP Semantic Models.
Produces modular, AI-RAG-optimized and human-readable Markdown documents with YAML frontmatter.
"""

from .config import DocGenConfig
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder
from .index_doc import IndexDocBuilder
from .engine import MarkdownDocGenerator

__all__ = [
    "DocGenConfig",
    "TableDocBuilder",
    "MeasureDocBuilder",
    "FunctionDocBuilder",
    "ExpressionDocBuilder",
    "IndexDocBuilder",
    "MarkdownDocGenerator",
]
