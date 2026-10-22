"""
HTML Documentation Generator Engine.
Coordinates HtmlLayoutBuilder, HtmlIndexBuilder, HtmlTableBuilder, HtmlMeasureBuilder,
and HtmlVisualBuilder to produce a complete, interactive, self-contained enterprise wiki portal.
100% Vanilla Python standard library.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional

from .config import DocGenConfig
from .html_layout import HtmlLayoutBuilder, get_relative_root
from .html_builders import (
    HtmlIndexBuilder,
    HtmlTableBuilder,
    HtmlMeasureBuilder,
    HtmlVisualBuilder,
    HtmlExpressionBuilder,
    HtmlFunctionBuilder,
)
from .html_assets import STYLE_CSS, APP_JS
from .visual_doc import PageVisualDocBuilder
from .utils import sanitize_filename, clean_project_name
from ..report_parser import ReportParser
from ..report_schema import PBIPReportModel


class HtmlDocGenerator:
    """
    Main entry point for generating native, interactive HTML wiki documentation
    from PBIP semantic model metadata and report visual presentations.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_documents(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, str]:
        """
        Generates in-memory dictionary of all HTML documents and static assets:
        {
          "index.html": content,
          "assets/style.css": content,
          "assets/app.js": content,
          "assets/search_index.js": content,
          "tables/FactInternetSales.html": content,
          "measures/Sales/Total_Sales.html": content,
          "visuals/Overview.html": content,
          "visuals/assets/...": svg_content,
        }
        """
        data = self._load_model_dict(model_data)
        report_model = self._resolve_report(model_data)
        project_name = self._resolve_project_name(model_data, data, report_model)
        data["project_name"] = project_name
        documents: Dict[str, str] = {}

        # 1. Static Assets (CSS and JS)
        documents["assets/style.css"] = STYLE_CSS
        documents["assets/app.js"] = APP_JS

        # Layout wrapper
        layout = HtmlLayoutBuilder(
            project_name=project_name,
            data=data,
            config=self.config,
            report_model=report_model,
        )

        search_items = []

        # 2. Master Catalog (index.html)
        if self.config.generate_index_file:
            idx_builder = HtmlIndexBuilder(data, self.config, report_model=report_model, project_name=project_name)
            idx_content = idx_builder.build_content()
            idx_html = layout.wrap_page(
                current_path="index.html",
                page_title="Model Overview",
                breadcrumbs=[("Home", None)],
                content_html=idx_content,
            )
            documents["index.html"] = idx_html
            search_items.append({
                "title": "Model Overview",
                "type": "Home",
                "url": "index.html",
                "desc": f"Project {project_name} catalog and summary."
            })

        # 3. Table Documents (tables/<Table>.html)
        tables_sub = self.config.tables_subdir.strip("/\\")
        for table in data.get("tables", []):
            if not self.config.is_table_published(table):
                continue
            tbl_name = table.get("name")
            clean_tbl_name = sanitize_filename(tbl_name)
            tbl_builder = HtmlTableBuilder(table, data, self.config, project_name=project_name)
            tbl_filename = f"{clean_tbl_name}.html"
            doc_path = f"{tables_sub}/{tbl_filename}" if tables_sub else tbl_filename
            rel_root = get_relative_root(doc_path)

            tbl_content = tbl_builder.build_content()
            tbl_html = layout.wrap_page(
                current_path=doc_path,
                page_title=f"Table: {tbl_name}",
                breadcrumbs=[("Home", f"{rel_root}/index.html"), ("Tables", None), (tbl_name, None)],
                content_html=tbl_content,
            )
            documents[doc_path] = tbl_html
            search_items.append({
                "title": tbl_name,
                "type": "Table",
                "role": table.get("role", "DIM"),
                "url": doc_path,
                "desc": f"Table with {len(table.get('columns', []))} columns."
            })

        # 4. Measure Documents (measures/<Table>/<Measure>.html)
        measures_sub = self.config.measures_subdir.strip("/\\")
        for measure in data.get("measures", []):
            if not self.config.is_measure_published(measure):
                continue
            meas_tbl = measure.get("table", "Model")
            meas_name = measure.get("name", "Measure")
            clean_tbl_name = sanitize_filename(meas_tbl)
            clean_name = sanitize_filename(meas_name)
            meas_builder = HtmlMeasureBuilder(measure, data, self.config, project_name=project_name)
            meas_filename = f"{clean_name}.html"
            if measures_sub:
                doc_path = f"{measures_sub}/{clean_tbl_name}/{meas_filename}"
            else:
                doc_path = f"{clean_tbl_name}/{meas_filename}"
            rel_root = get_relative_root(doc_path)

            meas_content = meas_builder.build_content()
            tbl_doc_url = f"{rel_root}/{tables_sub}/{clean_tbl_name}.html" if tables_sub else f"{rel_root}/{clean_tbl_name}.html"
            meas_html = layout.wrap_page(
                current_path=doc_path,
                page_title=f"Measure: [{meas_name}]",
                breadcrumbs=[
                    ("Home", f"{rel_root}/index.html"),
                    ("Measures", None),
                    (meas_tbl, tbl_doc_url),
                    (meas_name, None),
                ],
                content_html=meas_content,
            )
            documents[doc_path] = meas_html
            search_items.append({
                "title": meas_name,
                "type": "Measure",
                "table": meas_tbl,
                "url": doc_path,
                "desc": f"DAX measure in table {meas_tbl} (Depth {measure.get('calculation_depth', 0)})."
            })

        # 5. Functions Documents (functions/<Function>.html)
        functions_sub = self.config.functions_subdir.strip("/\\")
        for fn in data.get("functions", []):
            fn_name = fn.get("name", "function")
            clean_name = sanitize_filename(fn_name)
            fn_builder = HtmlFunctionBuilder(fn, data, self.config, project_name=project_name)
            fn_filename = f"{clean_name}.html"
            doc_path = f"{functions_sub}/{fn_filename}" if functions_sub else fn_filename
            rel_root = get_relative_root(doc_path)

            fn_content = fn_builder.build_content()
            fn_html = layout.wrap_page(
                current_path=doc_path,
                page_title=f"Function: {fn_name}",
                breadcrumbs=[("Home", f"{rel_root}/index.html"), ("Functions", None), (fn_name, None)],
                content_html=fn_content,
            )
            documents[doc_path] = fn_html
            search_items.append({
                "title": fn_name,
                "type": "Function",
                "url": doc_path,
                "desc": "User-Defined DAX Function."
            })

        # 6. Expressions Documents (expressions/<Expression>.html)
        if self.config.include_expression_docs:
            expressions_sub = self.config.expressions_subdir.strip("/\\")
            expr_list = data.get("expressions") or data.get("shared_queries") or []
            for expr in expr_list:
                q_name = expr.get("query_name") or "expression"
                clean_name = sanitize_filename(q_name)
                expr_builder = HtmlExpressionBuilder(expr, data, self.config, project_name=project_name)
                expr_filename = f"{clean_name}.html"
                doc_path = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                rel_root = get_relative_root(doc_path)

                expr_content = expr_builder.build_content()
                expr_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Expression: {q_name}",
                    breadcrumbs=[("Home", f"{rel_root}/index.html"), ("Expressions", None), (q_name, None)],
                    content_html=expr_content,
                )
                documents[doc_path] = expr_html
                search_items.append({
                    "title": q_name,
                    "type": "Expression",
                    "url": doc_path,
                    "desc": "Shared Power Query M expression."
                })

        # 7. Report & Visual Pages (visuals/<Page>.html)
        if self.config.include_visual_docs and report_model:
            visuals_sub = self.config.visuals_subdir.strip("/\\")
            for page in report_model.pages:
                clean_page_name = sanitize_filename(page.display_name)
                page_filename = f"{clean_page_name}.html"
                doc_path = f"{visuals_sub}/{page_filename}" if visuals_sub else page_filename
                rel_root = get_relative_root(doc_path)

                vis_builder = HtmlVisualBuilder(
                    page=page,
                    report_model=report_model,
                    config=self.config,
                    project_name=project_name,
                    model_tables=data.get("tables", []),
                    model_measures=data.get("measures", []),
                )
                vis_content = vis_builder.build_content()
                vis_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Report Page: {page.display_name}",
                    breadcrumbs=[("Home", f"{rel_root}/index.html"), ("Report Pages", None), (page.display_name, None)],
                    content_html=vis_content,
                )
                documents[doc_path] = vis_html
                search_items.append({
                    "title": page.display_name,
                    "type": "ReportPage",
                    "url": doc_path,
                    "desc": f"Report dashboard page #{page.page_number} ({page.width}x{page.height})."
                })

                # Scaled SVG canvas mini-maps (reusing PageVisualDocBuilder SVG generator)
                if self.config.include_visual_svg_maps:
                    page_svg_builder = PageVisualDocBuilder(
                        page=page,
                        report_model=report_model,
                        config=self.config,
                        project_name=project_name,
                    )
                    svg_assets = page_svg_builder.build_svg_assets()
                    for asset_rel_path, svg_content in svg_assets.items():
                        asset_doc_path = f"{visuals_sub}/{asset_rel_path}" if visuals_sub else asset_rel_path
                        documents[asset_doc_path] = svg_content

        # 8. Search Index JavaScript (file:// protocol safe)
        documents["assets/search_index.js"] = f"window.SEARCH_INDEX = {json.dumps(search_items, indent=2)};\n"

        return documents

    def write_to_directory(self, model_data: Union[Dict[str, Any], str, Path], target_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generates and writes all HTML files and assets to target directory.
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
        if not self.config.include_visual_docs:
            return None
        if self.config.report_path:
            rp = Path(self.config.report_path)
            if rp.exists():
                try:
                    parser = ReportParser()
                    return parser.parse(str(rp))
                except Exception:
                    return None
        input_path = None
        if isinstance(model_input, (str, Path)):
            input_path = Path(model_input)
        elif hasattr(model_input, "source_path") and getattr(model_input, "source_path"):
            input_path = Path(model_input.source_path)

        if input_path:
            p = input_path
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
            for c in candidates:
                if c.exists() and c.is_dir():
                    try:
                        parser = ReportParser()
                        return parser.parse(str(c))
                    except Exception:
                        continue
        return None

    def _resolve_project_name(
        self,
        model_input: Union[Dict[str, Any], str, Path],
        model_data: Dict[str, Any],
        report_model: Optional[PBIPReportModel] = None,
    ) -> str:
        if self.config.project_name:
            return clean_project_name(self.config.project_name)
        if isinstance(model_data, dict):
            if model_data.get("project_name"):
                return clean_project_name(model_data["project_name"])
            if model_data.get("model_name"):
                return clean_project_name(model_data["model_name"])
        if report_model and report_model.report_name:
            return clean_project_name(report_model.report_name)
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
            if p.suffix.lower() in (".pbip", ".semanticmodel", ".report"):
                return clean_project_name(p.stem)
            if p.name == "definition" and p.parent.suffix.lower() == ".semanticmodel":
                return clean_project_name(p.parent.stem)
            if p.name == "definition" and p.parent.suffix.lower() == ".report":
                return clean_project_name(p.parent.stem)
            return clean_project_name(p.stem)
        return "PBIP"

    def _load_model_dict(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        if hasattr(model_data, "to_dict"):
            return model_data.to_dict()
        if isinstance(model_data, dict):
            return model_data
        if isinstance(model_data, (str, Path)):
            path = Path(model_data)
            if path.is_file() and path.suffix.lower() == ".json":
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and ("model_name" in data or "source_format" in data) and "tables" in data:
                        return data
                except Exception:
                    pass

            from ..parser import PBIPParser
            parser = PBIPParser(config=self.config)
            model_obj = parser.parse(str(path), config=self.config)
            return model_obj.to_dict()
        raise ValueError(f"Unsupported model_data type: {type(model_data)}")
