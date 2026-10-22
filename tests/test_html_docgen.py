"""
Unit tests for the native HTML documentation generation in pbip_doc.docgen.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.html_assets import get_html_css, get_html_js
from pbip_doc.docgen.html_layout import HtmlLayoutBuilder, get_relative_root
from pbip_doc.docgen.html_builders import (
    HtmlIndexBuilder,
    HtmlTableBuilder,
    HtmlMeasureBuilder,
    HtmlVisualBuilder,
    HtmlExpressionBuilder,
    HtmlFunctionBuilder,
)
from pbip_doc.docgen.html_engine import HtmlDocGenerator
from pbip_doc.parser import PBIPParser
from pbip_doc.report_schema import (
    PBIPReportModel,
    PageDefinition,
    VisualDefinition,
    CalculationContext,
    EvaluatedMetric,
    SlicingCoordinate,
    ActiveFilter,
    PagePanelFilter,
    SpatialPosition,
    BoundingBox,
)


class TestHtmlDocGenConfig(unittest.TestCase):
    def test_default_config_html_properties(self):
        config = DocGenConfig()
        self.assertEqual(config.output_format, "markdown")
        self.assertEqual(config.html_theme, "auto")
        self.assertIsNone(config.html_title)

    def test_custom_config_html_properties(self):
        config = DocGenConfig(
            output_format="html",
            html_theme="dark",
            html_title="Enterprise BI Portal",
        )
        self.assertEqual(config.output_format, "html")
        self.assertEqual(config.html_theme, "dark")
        self.assertEqual(config.html_title, "Enterprise BI Portal")


class TestHtmlAssets(unittest.TestCase):
    def test_css_asset(self):
        css = get_html_css()
        self.assertIn(":root", css)
        self.assertIn("--bg-body", css)
        self.assertIn("[data-theme=\"dark\"]", css)
        self.assertIn(".wiki-layout", css)
        self.assertIn(".wiki-sidebar", css)
        self.assertIn(".kpi-grid", css)
        self.assertIn(".copy-btn", css)

    def test_js_asset(self):
        js = get_html_js()
        self.assertIn("localStorage", js)
        self.assertIn("theme-toggle-btn", js)
        self.assertIn("sidebar-search-input", js)
        self.assertIn("table-filter-input", js)
        self.assertIn("initCopyButtons", js)
        self.assertIn("clipboard", js)


class TestHtmlLayoutBuilder(unittest.TestCase):
    def setUp(self):
        self.config = DocGenConfig(output_format="html", html_title="Test Model Docs")
        self.sample_data = {
            "model_name": "TestModel",
            "tables": [
                {"name": "Sales", "role": "FACT", "columns": [], "measures": []},
                {"name": "Customer", "role": "DIM", "columns": [], "measures": []},
            ],
            "measures": [
                {"name": "Total Sales", "table": "Sales", "dax_expression": "SUM(Sales[Amount])"},
            ],
        }
        self.layout = HtmlLayoutBuilder(
            project_name="Test Project",
            data=self.sample_data,
            config=self.config,
        )

    def test_get_relative_root(self):
        self.assertEqual(get_relative_root("index.html"), ".")
        self.assertEqual(get_relative_root("tables/Sales.html"), "..")
        self.assertEqual(get_relative_root("measures/Sales/Total_Sales.html"), "../..")

    def test_wrap_page_root(self):
        page_html = self.layout.wrap_page(
            current_path="index.html",
            page_title="Model Overview",
            breadcrumbs=[("Home", "./index.html")],
            content_html="<h1>Welcome</h1>",
        )
        self.assertIn("<!DOCTYPE html>", page_html)
        self.assertIn("<title>Model Overview - Test Model Docs Documentation</title>", page_html)
        self.assertIn('href="./assets/style.css"', page_html)
        self.assertIn('src="./assets/search_index.js"', page_html)
        self.assertIn('src="./assets/app.js"', page_html)
        self.assertIn('id="sidebar-search-input"', page_html)
        self.assertIn("Sales", page_html)
        self.assertIn("Total Sales", page_html)
        self.assertIn("<h1>Welcome</h1>", page_html)

    def test_wrap_page_nested(self):
        page_html = self.layout.wrap_page(
            current_path="measures/Sales/Total_Sales.html",
            page_title="Measure: Total Sales",
            breadcrumbs=[("Home", "../../index.html"), ("Measures", None), ("Total Sales", None)],
            content_html="<div>Measure Details</div>",
        )
        self.assertIn('href="../../assets/style.css"', page_html)
        self.assertIn('src="../../assets/search_index.js"', page_html)
        self.assertIn('src="../../assets/app.js"', page_html)
        self.assertIn("Measure Details", page_html)


class TestHtmlBuilders(unittest.TestCase):
    def setUp(self):
        self.config = DocGenConfig(output_format="html")
        self.sample_measure = {
            "name": "Total Sales",
            "table": "Sales",
            "dax_expression": "SUM(Sales[SalesAmount])",
            "description": "Calculates gross sales revenue.",
            "displayFolder": "Financials",
            "calculation_depth": 1,
            "referenced_measures": [],
            "referenced_columns": [("Sales", "SalesAmount")],
        }
        self.sample_model = {
            "tables": [
                {
                    "name": "Sales",
                    "role": "FACT",
                    "storage_mode": "Import",
                    "description": "Fact table for sales transactions.",
                    "columns": [
                        {"name": "SalesOrderNumber", "dataType": "string"},
                        {"name": "SalesAmount", "dataType": "decimal"},
                    ],
                    "measures": [self.sample_measure],
                    "source_type": "m_partition",
                    "power_query_expression": "let\n    Source = Csv.Document(...)\nin\n    Source",
                },
                {
                    "name": "Customer",
                    "role": "DIM",
                    "storage_mode": "Import",
                    "description": "Customer demographic dimensions.",
                    "columns": [
                        {"name": "CustomerKey", "dataType": "int64"},
                        {"name": "Name", "dataType": "string"},
                    ],
                    "measures": [],
                },
            ],
            "measures": [self.sample_measure],
            "relationships": [
                {
                    "fromTable": "Sales",
                    "fromColumn": "CustomerKey",
                    "toTable": "Customer",
                    "toColumn": "CustomerKey",
                    "isActive": True,
                    "crossFilteringBehavior": "OneDirection",
                }
            ],
        }

    def test_html_index_builder(self):
        builder = HtmlIndexBuilder(self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Sales BI", content)
        self.assertIn("Published Data Model Tables", content)
        self.assertIn("Customer", content)
        self.assertIn("Sales", content)
        self.assertIn("Total Sales", content)

    def test_html_table_builder(self):
        table_data = self.sample_model["tables"][0]
        builder = HtmlTableBuilder(table_data, self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Sales", content)
        self.assertIn("SalesOrderNumber", content)
        self.assertIn("SalesAmount", content)
        self.assertIn("Total Sales", content)
        self.assertIn("Power Query (M) Script", content)
        self.assertIn("copy-btn", content)

    def test_html_measure_builder(self):
        measure_data = self.sample_measure
        builder = HtmlMeasureBuilder(measure_data, self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Total Sales", content)
        self.assertIn("Sales[SalesAmount]", content)
        self.assertIn("copy-btn", content)

    def test_html_visual_builder(self):
        v_bbox = BoundingBox(x=10, y=20, width=500, height=300, z=1)
        spatial_pos = SpatialPosition(center_x=260, center_y=170, zone="Top-Left", bounding_box=v_bbox)
        metric = EvaluatedMetric(
            table="Sales",
            field="Total Sales",
            field_type="MEASURE",
            role="Values",
            model_key="[Total Sales]",
        )
        coord = SlicingCoordinate(
            role="Category",
            table="Customer",
            field="Name",
            model_key="Customer[Name]",
        )
        calc_ctx = CalculationContext(
            evaluated_metrics=[metric],
            slicing_coordinates=[coord],
            visual_active_filters=[ActiveFilter(table="Sales", field="SalesAmount", filter_type="Range", condition="> 0")],
            locked_active_filters=[PagePanelFilter(scope="Locked", table="Date", field="Year", is_locked=True, applied_values=["2024"])],
        )
        visual = VisualDefinition(
            visual_id="v_1001",
            title="Sales by Customer",
            visual_type="columnChart",
            spatial_position=spatial_pos,
            calculation_context=calc_ctx,
        )
        page = PageDefinition(
            page_id="p_1",
            display_name="Executive Summary",
            page_number=1,
            visuals=[visual],
        )
        report_model = PBIPReportModel(
            report_name="Sales Report",
            format="PBIR",
            source_path="/path/to/report",
            pages=[page],
        )

        builder = HtmlVisualBuilder(page, report_model, self.config, project_name="Sales Report")
        content = builder.build_content()
        self.assertIn("Executive Summary", content)
        self.assertIn("Sales by Customer", content)
        self.assertIn("columnChart", content)
        self.assertIn("Total Sales", content)
        self.assertIn("Customer", content)
        self.assertIn("Name", content)
        self.assertIn("Locked Page Filters", content)


class TestHtmlDocGeneratorEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pbip_html_test_")
        self.sample_dir = Path("samples/AdventureWorks Sales")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_adventureworks_html_generation(self):
        if not self.sample_dir.exists():
            self.skipTest("Sample directory 'AdventureWorks Sales' not found.")

        parser = PBIPParser()
        model = parser.parse(str(self.sample_dir))

        config = DocGenConfig(
            output_format="html",
            output_dir=self.temp_dir,
            html_title="AdventureWorks KB",
        )
        generator = HtmlDocGenerator(config=config)
        docs = generator.write_to_directory(str(self.sample_dir), target_dir=self.temp_dir)

        # 1. Entry portal
        self.assertIn("index.html", docs)
        index_file = Path(self.temp_dir) / "index.html"
        self.assertTrue(index_file.exists())
        with open(index_file, "r", encoding="utf-8") as f:
            index_content = f.read()
        self.assertIn("AdventureWorks KB", index_content)
        self.assertIn("Model Overview", index_content)

        # 2. Assets
        self.assertTrue((Path(self.temp_dir) / "assets" / "style.css").exists())
        self.assertTrue((Path(self.temp_dir) / "assets" / "app.js").exists())
        self.assertTrue((Path(self.temp_dir) / "assets" / "search_index.js").exists())

        # 3. Tables
        self.assertTrue((Path(self.temp_dir) / "tables" / "Sales.html").exists())
        self.assertTrue((Path(self.temp_dir) / "tables" / "Customer.html").exists())

        # 4. Measures
        self.assertTrue((Path(self.temp_dir) / "measures" / "Sales" / "Orders.html").exists())

        # 5. Visuals & SVG Maps
        self.assertTrue((Path(self.temp_dir) / "visuals" / "Overview.html").exists())
        svg_maps = list((Path(self.temp_dir) / "visuals" / "assets" / "Overview").glob("*.svg"))
        self.assertGreater(len(svg_maps), 0)

        # 6. Search Index content
        with open(Path(self.temp_dir) / "assets" / "search_index.js", "r", encoding="utf-8") as f:
            search_content = f.read()
        self.assertIn("window.SEARCH_INDEX =", search_content)
        self.assertIn("Orders", search_content)
        self.assertIn("Sales", search_content)


if __name__ == "__main__":
    unittest.main()
