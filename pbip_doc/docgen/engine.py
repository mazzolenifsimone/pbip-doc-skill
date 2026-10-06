"""
Documentation Generator Engine.
Coordinates TableDocBuilder, MeasureDocBuilder, and IndexDocBuilder
to emit granular, AI-RAG-ready, human-readable markdown documents.
Vanilla Python implementation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Union, Optional

from .config import DocGenConfig
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder
from .index_doc import IndexDocBuilder
from .utils import sanitize_filename


class MarkdownDocGenerator:
    """
    Main entry point for generating modular documentation from semantic model JSON.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_documents(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, str]:
        """
        Generates in-memory dictionary of all markdown documents:
        {
          "INDEX.md": content,
          "tables/FactInternetSales.md": content,
          "measures/Total_Sales.md": content,
          "expressions/Staging_Orders.md": content,
          ...
        }
        """
        data = self._load_model_dict(model_data)
        documents: Dict[str, str] = {}

        # 1. Master Catalog (INDEX.md)
        if self.config.generate_index_file:
            index_builder = IndexDocBuilder(data, self.config)
            documents["INDEX.md"] = index_builder.build_markdown()

        # 2. Table Documents (one markdown per table)
        tables_sub = self.config.tables_subdir.strip("/\\")
        for table in data.get("tables", []):
            if not self.config.is_table_published(table):
                continue
            tbl_name = table.get("name")
            tbl_builder = TableDocBuilder(table, data, self.config)
            clean_tbl_name = sanitize_filename(tbl_name)
            tbl_filename = f"{clean_tbl_name}.md"
            doc_path = f"{tables_sub}/{tbl_filename}" if tables_sub else tbl_filename
            documents[doc_path] = tbl_builder.build_markdown()

        # 3. Measure Documents (one markdown per measure grouped by clean host table folder)
        measures_sub = self.config.measures_subdir.strip("/\\")
        for measure in data.get("measures", []):
            if not self.config.is_measure_published(measure):
                continue
            meas_tbl = measure.get("table", "Model")
            meas_builder = MeasureDocBuilder(measure, data, self.config)
            clean_tbl_name = sanitize_filename(meas_tbl)
            clean_name = sanitize_filename(measure.get("name", "measure"))
            meas_filename = f"{clean_name}.md"
            if measures_sub:
                doc_path = f"{measures_sub}/{clean_tbl_name}/{meas_filename}"
            else:
                doc_path = f"{clean_tbl_name}/{meas_filename}"
            documents[doc_path] = meas_builder.build_markdown()

        # 4. Function Documents (one markdown per UDF function)
        functions_sub = self.config.functions_subdir.strip("/\\")
        for fn in data.get("functions", []):
            fn_builder = FunctionDocBuilder(fn, data, self.config)
            clean_name = sanitize_filename(fn.get("name", "function"))
            fn_filename = f"{clean_name}.md"
            doc_path = f"{functions_sub}/{fn_filename}" if functions_sub else fn_filename
            documents[doc_path] = fn_builder.build_markdown()

        # 5. Expression Documents (one markdown per shared Power Query expression)
        if self.config.include_expression_docs:
            expressions_sub = self.config.expressions_subdir.strip("/\\")
            expr_list = data.get("expressions") or data.get("shared_queries") or []
            for expr in expr_list:
                expr_builder = ExpressionDocBuilder(expr, data, self.config)
                clean_name = sanitize_filename(expr.get("query_name", "expression"))
                expr_filename = f"{clean_name}.md"
                doc_path = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                documents[doc_path] = expr_builder.build_markdown()

        return documents

    def write_to_directory(self, model_data: Union[Dict[str, Any], str, Path], target_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generates and writes all markdown files to target directory.
        Returns the dictionary of generated relative file paths and contents.
        """
        out_path = Path(target_dir or self.config.output_dir)
        docs = self.generate_all_documents(model_data)

        for rel_path, content in docs.items():
            dest_file = out_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_file, "w", encoding="utf-8") as f:
                f.write(content)

        return docs

    def _load_model_dict(self, model_input: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        """Ensures input is converted to standard dictionary."""
        if isinstance(model_input, dict):
            return model_input
        
        path = Path(model_input)
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # If this is already an enriched model dictionary generated by pbip_doc
                if isinstance(data, dict) and ("model_name" in data or "source_format" in data) and "tables" in data:
                    return data
            except Exception:
                pass
        
        # If passed a PBIP directory, definition folder, or model.bim, parse it directly via PBIPParser
        from ..parser import PBIPParser
        parser = PBIPParser(config=self.config)
        model_obj = parser.parse(str(path), config=self.config)
        return model_obj.to_dict()
