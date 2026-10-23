"""
Documentation Generator Engine.
Coordinates TableDocBuilder, MeasureDocBuilder, IndexDocBuilder, and PageVisualDocBuilder
to emit granular, AI-RAG-ready, human-readable markdown documents.
Vanilla Python implementation.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional

from .config import DocGenConfig
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder
from .index_doc import IndexDocBuilder
from .visual_doc import PageVisualDocBuilder
from .utils import sanitize_filename, clean_project_name
from ..report_parser import ReportParser
from ..report_schema import PBIPReportModel


class MarkdownDocGenerator:
    """
    Main entry point for generating modular documentation from semantic model JSON
    and associated Power BI report presentation metadata.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_documents(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, str]:
        """
        Generates in-memory dictionary of all markdown documents:
        {
          "<project_name>.md": content,
          "tables/FactInternetSales.md": content,
          "measures/Sales/Total_Sales.md": content,
          "expressions/Staging_Orders.md": content,
          "visuals/Executive_Overview.md": content,
          ...
        }
        """
        data = self._load_model_dict(model_data)
        report_model = self._resolve_report(model_data)
        project_name = self._resolve_project_name(model_data, data, report_model)
        data["project_name"] = project_name
        documents: Dict[str, str] = {}

        # 1. Master Catalog (<project_name>.md)
        if self.config.generate_index_file:
            index_builder = IndexDocBuilder(data, self.config, report_model=report_model, project_name=project_name)
            safe_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', project_name).strip('. ') or "PBIP"
            index_filename = self.config.index_filename or f"{safe_name}.md"
            documents[index_filename] = index_builder.build_markdown()

        # 2. Table Documents (one markdown per table)
        tables_sub = self.config.tables_subdir.strip("/\\")
        for table in data.get("tables", []):
            if not self.config.is_table_published(table):
                continue
            tbl_name = table.get("name")
            tbl_builder = TableDocBuilder(table, data, self.config, project_name=project_name)
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
            meas_builder = MeasureDocBuilder(measure, data, self.config, project_name=project_name)
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
            fn_builder = FunctionDocBuilder(fn, data, self.config, project_name=project_name)
            clean_name = sanitize_filename(fn.get("name", "function"))
            fn_filename = f"{clean_name}.md"
            doc_path = f"{functions_sub}/{fn_filename}" if functions_sub else fn_filename
            documents[doc_path] = fn_builder.build_markdown()

        # 5. Expression Documents (one markdown per shared Power Query expression)
        if self.config.include_expression_docs:
            expressions_sub = self.config.expressions_subdir.strip("/\\")
            expr_list = data.get("expressions") or data.get("shared_queries") or []
            for expr in expr_list:
                expr_builder = ExpressionDocBuilder(expr, data, self.config, project_name=project_name)
                clean_name = sanitize_filename(expr.get("query_name") or "expression")
                expr_filename = f"{clean_name}.md"
                doc_path = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                documents[doc_path] = expr_builder.build_markdown()

        # 6. Report & Visual Documents (one markdown per page)
        if self.config.include_visual_docs and report_model:
            visuals_sub = self.config.visuals_subdir.strip("/\\")
            known_measure_keys = {
                (m.get("table"), m.get("name")) for m in data.get("measures", [])
            } | {
                f"{m.get('table')}[{m.get('name')}]" for m in data.get("measures", [])
            }
            known_table_names = {t.get("name") for t in data.get("tables", [])}

            for page in report_model.pages:
                page_builder = PageVisualDocBuilder(
                    page=page,
                    report_model=report_model,
                    config=self.config,
                    known_measure_keys=known_measure_keys,
                    known_table_names=known_table_names,
                    project_name=project_name,
                    model_tables=data.get("tables", []),
                    model_measures=data.get("measures", []),
                )
                clean_page_name = sanitize_filename(page.display_name)
                page_filename = f"{clean_page_name}.md"
                doc_path = f"{visuals_sub}/{page_filename}" if visuals_sub else page_filename
                documents[doc_path] = page_builder.build_markdown()

                # Generate and collect scaled SVG canvas mini-maps
                if self.config.include_visual_svg_maps:
                    svg_assets = page_builder.build_svg_assets()
                    for asset_rel_path, svg_content in svg_assets.items():
                        asset_doc_path = f"{visuals_sub}/{asset_rel_path}" if visuals_sub else asset_rel_path
                        documents[asset_doc_path] = svg_content

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

    def _resolve_report(self, model_input: Union[Dict[str, Any], str, Path]) -> Optional[PBIPReportModel]:
        """Attempts to locate and parse the associated PBIP *.Report component."""
        if not self.config.include_visual_docs:
            return None

        # 1. Explicit report path from config
        if self.config.report_path:
            rp = Path(self.config.report_path)
            if rp.exists():
                try:
                    parser = ReportParser()
                    return parser.parse(str(rp))
                except Exception:
                    return None

        # 2. Auto-discovery from model_input
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
            candidates = []

            if p.suffix.lower() == ".report":
                candidates.append(p)
            elif p.suffix.lower() == ".semanticmodel":
                candidates.append(p.parent / f"{p.stem}.Report")
                candidates.extend(list(p.parent.glob("*.Report")))
            elif p.suffix.lower() == ".pbip":
                candidates.append(p.parent / f"{p.stem}.Report")
                candidates.extend(list(p.parent.glob("*.Report")))
            elif p.is_dir():
                candidates.append(p / f"{p.name}.Report")
                candidates.extend(list(p.glob("*.Report")))
                candidates.extend(list(p.parent.glob("*.Report")))
                if p.name == "definition" and p.parent.suffix.lower() == ".semanticmodel":
                    candidates.append(p.parent.parent / f"{p.parent.stem}.Report")
                    candidates.extend(list(p.parent.parent.glob("*.Report")))
            elif p.is_file():
                if p.name == "report_documentation.json" or "report" in p.name.lower():
                    candidates.append(p)
                candidates.append(p.parent / "report_documentation.json")
                candidates.extend(list(p.parent.glob("*.Report")))
                candidates.extend(list(p.parent.parent.glob("*.Report")))

            for cand in candidates:
                if cand.exists():
                    try:
                        parser = ReportParser()
                        return parser.parse(str(cand))
                    except Exception:
                        continue

        return None

    def _load_model_dict(self, model_input: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        """Ensures input is converted to standard dictionary."""
        if hasattr(model_input, "to_dict"):
            return model_input.to_dict()
        if isinstance(model_input, dict):
            return model_input
        
        path = Path(model_input)
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and ("model_name" in data or "source_format" in data) and "tables" in data:
                    return data
            except Exception:
                pass
        
        # If passed a PBIP directory, definition folder, or model.bim, parse it directly via PBIPParser
        from ..parser import PBIPParser
        parser = PBIPParser(config=self.config)
        model_obj = parser.parse(str(path), config=self.config)
        return model_obj.to_dict()

    def _resolve_project_name(
        self,
        model_input: Union[Dict[str, Any], str, Path],
        data: Dict[str, Any],
        report_model: Optional[PBIPReportModel],
    ) -> str:
        """
        Resolves the PBIP project name from explicit config, input path,
        report metadata, or semantic model data.
        """
        if self.config.project_name:
            return clean_project_name(self.config.project_name)

        # 1. From model_input path if provided as string or Path
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
            stem = p.stem
            cleaned = clean_project_name(stem)
            if cleaned and cleaned not in ("model", "definition", "PBIP"):
                return cleaned

            parent_cleaned = clean_project_name(p.parent.name)
            if parent_cleaned and parent_cleaned not in ("definition", ".", "PBIP"):
                return parent_cleaned

        # 2. From report_model
        if report_model and getattr(report_model, "report_name", None):
            cleaned = clean_project_name(report_model.report_name)
            if cleaned and cleaned != "PBIP":
                return cleaned

        # 3. From semantic model data
        m_name = data.get("model_name")
        if m_name:
            cleaned = clean_project_name(m_name)
            if cleaned and cleaned != "PBIP":
                return cleaned

        return "PBIP"
