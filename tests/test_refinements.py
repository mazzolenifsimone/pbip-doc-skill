import unittest
from pbip_doc.m_formatter import format_m, strip_m_comments
from pbip_doc.report_schema import (
    PageDefinition,
    VisualDefinition,
    PBIPReportModel,
    CalculationContext,
    EvaluatedMetric,
    SlicingCoordinate,
    BoundingBox,
    SpatialPosition,
)
from pbip_doc.docgen.visual_doc import PageVisualDocBuilder
from pbip_doc.docgen.html_builders import HtmlVisualBuilder, HtmlTableBuilder, HtmlIndexBuilder
from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.parser import PBIPParser


class TestMFormatter(unittest.TestCase):
    def test_basic_let_in_formatting(self):
        raw = 'let Source = Csv.Document(File.Contents("C:\\data.csv"), [Delimiter=",", Columns=3]), #"Changed Type" = Table.TransformColumnTypes(Source,{{"ID", Int64.Type}, {"Name", type text}}) in #"Changed Type"'
        formatted = format_m(raw)
        lines = formatted.splitlines()
        self.assertEqual(lines[0], "let")
        self.assertTrue(lines[1].startswith("    Source = "))
        self.assertTrue(lines[2].startswith('    #"Changed Type" = '))
        self.assertEqual(lines[3], "in")
        self.assertEqual(lines[4], '    #"Changed Type"')

    def test_quoted_commas_and_brackets_not_split(self):
        # Commas inside quotes or list/record must not split
        raw = 'let Step1 = Table.AddColumn(Prev, "Col,With,Commas", each [A] + [B]), Step2 = Table.SelectRows(Step1, each [X] > 10) in Step2'
        formatted = format_m(raw)
        lines = formatted.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "let")
        self.assertTrue(lines[1].strip().startswith("Step1 = Table.AddColumn"))
        self.assertTrue(lines[2].strip().startswith("Step2 = Table.SelectRows"))
        self.assertEqual(lines[3], "in")
        self.assertEqual(lines[4], "    Step2")

    def test_comments_and_whitespace(self):
        raw = '''// Initial query
let
    /* multi line comment */
    Source = #table({"A"}, {{1}})
in
    Source'''
        formatted = format_m(raw)
        self.assertIn("let", formatted)
        self.assertIn("in", formatted)
        self.assertIn("Source = #table", formatted)


class TestVisualDocumentationRefinements(unittest.TestCase):
    def test_visual_title_and_display_name(self):
        metric = EvaluatedMetric(
            model_key="Sales[Total Revenue]",
            table="Sales",
            field="Total Revenue",
            field_type="MEASURE",
            role="Values",
            display_name="Revenue ($)",
        )
        coord = SlicingCoordinate(
            role="Rows",
            table="Products",
            field="Category",
            model_key="Products[Category]",
            display_name="Product Category",
        )
        calc = CalculationContext(
            evaluated_metrics=[metric],
            slicing_coordinates=[coord],
        )
        visual = VisualDefinition(
            visual_id="vis_table_1",
            visual_type="matrix",
            title="Sales by Category Matrix",
            spatial_position=SpatialPosition(
                bounding_box=BoundingBox(x=10, y=20, width=500, height=300, z=1),
                zone="Top-Left",
                center_x=260,
                center_y=170,
            ),
            calculation_context=calc,
        )
        page = PageDefinition(
            page_id="ReportSection1",
            display_name="Overview",
            page_number=1,
            visuals=[visual],
            width=1920,
            height=1080,
        )
        report = PBIPReportModel(
            report_name="Sales_Report",
            format="PBIR",
            source_path="mock/path",
            pages=[page],
        )

        # 1. Test Markdown generation includes Screen Name
        doc_builder = PageVisualDocBuilder(page=page, report_model=report)
        md = doc_builder.build_markdown()
        self.assertIn('Screen Name: "Revenue ($)"', md)
        self.assertIn('Screen Name: "Product Category"', md)

        # 2. Test HTML generation includes Screen Name
        html_builder = HtmlVisualBuilder(page=page, report_model=report, config=DocGenConfig())
        html = html_builder.build_content()
        self.assertIn('Screen: "Revenue ($)"', html)
        self.assertIn('Screen: "Product Category"', html)


class TestHtmlBadgesAndRelationships(unittest.TestCase):
    def test_status_badges_active_and_inactive(self):
        data = {
            "tables": [
                {
                    "name": "Sales",
                    "role": "FACT",
                    "incremental_refresh_policy": {"is_enabled": True},
                    "columns": [{"name": "Amount", "data_type": "Decimal"}],
                },
                {
                    "name": "Date",
                    "role": "DIM",
                    "incremental_refresh_policy": {"is_enabled": False},
                    "columns": [{"name": "Date", "data_type": "DateTime"}],
                },
            ],
            "relationships": [
                {
                    "from_table": "Sales",
                    "from_column": "DateKey",
                    "to_table": "Date",
                    "to_column": "DateKey",
                    "is_active": True,
                },
                {
                    "from_table": "Sales",
                    "from_column": "DueDateKey",
                    "to_table": "Date",
                    "to_column": "DateKey",
                    "is_active": False,
                },
            ],
        }

        # Index builder
        index_builder = HtmlIndexBuilder(data=data, config=DocGenConfig())
        index_html = index_builder.build_content()
        self.assertIn("badge-status-active", index_html)
        self.assertIn("badge-status-inactive", index_html)

        # Table builder
        sales_table = data["tables"][0]
        table_builder = HtmlTableBuilder(table_data=sales_table, full_model=data, config=DocGenConfig())
        table_html = table_builder.build_content()
        self.assertIn("badge-status-active", table_html)


class TestYamlFrontmatterEscaping(unittest.TestCase):
    def test_windows_paths_escaping(self):
        from pbip_doc.docgen.utils import format_yaml_frontmatter
        data = {
            "title": "Table: Accounts",
            "root_sources": [
                r"C:\Users\mazzosi1\OneDrive - Reti\Documents\Data.xlsx",
                r"C:\Program Files\Common\test.csv",
            ],
            "single_path": r"C:\Users\mazzosi1\test.xlsx",
        }
        fm = format_yaml_frontmatter(data)
        # Verify no raw unescaped backslashes in quoted strings
        for line in fm.splitlines():
            if '"' in line:
                # Should not contain single backslash before U
                self.assertNotIn(r"\U", line.replace(r"\\", ""))

    def test_table_doc_normalizes_root_sources(self):
        from pbip_doc.docgen.table_doc import TableDocBuilder
        table_data = {
            "name": "Accounts",
            "role": "DIMENSION",
            "root_data_sources": [
                {"connection_string": r"C:\Users\mazzosi1\Documents\Accounts.xlsx"}
            ],
            "columns": [{"name": "ID", "data_type": "Int64"}],
        }
        builder = TableDocBuilder(table_data=table_data, full_model={"tables": [table_data]})
        md = builder.build_markdown()
        self.assertIn("C:/Users/mazzosi1/Documents/Accounts.xlsx", md)
        self.assertNotIn(r"C:\Users", md)


class TestDecompositionTreeAndImplicitMeasures(unittest.TestCase):
    def test_implicit_measure_badges_and_links_in_markdown_and_html(self):
        implicit_metric = EvaluatedMetric(
            model_key="Opportunities[Value]",
            table="Opportunities",
            field="Value",
            field_type="IMPLICIT_MEASURE",
            role="Analyze",
            aggregation="Sum",
            display_name="Value",
        )
        slicing_coord = SlicingCoordinate(
            role="ExplainBy",
            table="Products",
            field="Product category",
            model_key="Products[Product category]",
            display_name="Product LOB",
        )
        calc = CalculationContext(
            evaluated_metrics=[implicit_metric],
            slicing_coordinates=[slicing_coord],
        )
        visual = VisualDefinition(
            visual_id="decomp_1",
            visual_type="decompositionTreeVisual",
            title="Decomposition Tree: Value",
            calculation_context=calc,
        )
        page = PageDefinition(
            page_id="p1",
            display_name="Decomposition Tree",
            page_number=1,
            visuals=[visual],
            width=1920,
            height=1080,
        )
        report = PBIPReportModel(
            report_name="AI_Report",
            format="PBIR",
            source_path="mock",
            pages=[page],
        )

        # 1. Test Markdown: has *(Implicit Measure)* and links to table Opportunities.md
        doc_builder = PageVisualDocBuilder(page=page, report_model=report)
        md = doc_builder.build_markdown()
        self.assertIn("*(Implicit Measure)*", md)
        self.assertIn("[Opportunities[Value]](../tables/Opportunities.md)", md)
        # Should NOT link to measures/Opportunities/Value.md
        self.assertNotIn("../measures/Opportunities/Value.md", md)

        # 2. Test HTML: has badge "Implicit Measure" and links to table Opportunities.html (preventing 404)
        html_builder = HtmlVisualBuilder(page=page, report_model=report, config=DocGenConfig())
        html = html_builder.build_content()
        self.assertIn('class="badge badge-type" style="font-size: 0.72rem;">Implicit Measure</span>', html)
        self.assertIn('href="../tables/Opportunities.html"', html)
        self.assertNotIn('href="../measures/Opportunities/Value.html"', html)

    def test_selector_not_parsed_as_dynamic_metric(self):
        from pbip_doc.report_parser import _find_dynamic_expressions
        obj_with_selector = {
            "insights": [
                {
                    "properties": {"isAINode": {"expr": {"Literal": {"Value": "true"}}}},
                    "selector": {
                        "data": [
                            {
                                "scopeId": {
                                    "Comparison": {
                                        "ComparisonKind": 0,
                                        "Left": {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Entity": "Products"}},
                                                "Property": "Product category",
                                            }
                                        },
                                        "Right": {"Literal": {"Value": "'Software'"}},
                                    }
                                }
                            }
                        ]
                    },
                }
            ]
        }
        dyn = _find_dynamic_expressions(obj_with_selector)
        # Selector scopeId comparison must be ignored
        self.assertEqual(len(dyn), 0)


class TestConditionalVisualTitles(unittest.TestCase):
    def test_conditional_title_detection_and_badging(self):
        from pbip_doc.report_parser import ReportParser
        parser = ReportParser()
        # Mock visual json with title bound to measure
        vjson = {
            "visualContainerObjects": {
                "title": [
                    {
                        "properties": {
                            "text": {
                                "expr": {
                                    "Measure": {
                                        "Expression": {"SourceRef": {"Entity": "Sales"}},
                                        "Property": "DynamicTitle",
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
        title, is_conditional = parser._extract_custom_title(vjson)
        self.assertEqual(title, "Sales[DynamicTitle]")
        self.assertTrue(is_conditional)

        # Build visual with is_conditional_title=True
        calc = CalculationContext(
            evaluated_metrics=[
                EvaluatedMetric(table="Sales", field="Revenue", field_type="MEASURE", role="Values", model_key="Sales[Revenue]")
            ]
        )
        visual = VisualDefinition(
            visual_id="v_cond",
            visual_type="columnChart",
            title=title,
            is_conditional_title=is_conditional,
            calculation_context=calc,
        )
        page = PageDefinition(
            page_id="p1",
            display_name="Page1",
            page_number=1,
            visuals=[visual],
            width=1920,
            height=1080,
        )
        report = PBIPReportModel(report_name="Rep", format="PBIR", source_path="mock", pages=[page])

        # 1. Test Markdown: title heading has *(Conditional Title)* and metric is in Evaluated DAX Metrics
        doc_builder = PageVisualDocBuilder(page=page, report_model=report)
        md = doc_builder.build_markdown()
        self.assertIn("### 1. Sales[DynamicTitle] *(Conditional Title)*", md)
        self.assertIn("*(Role: Conditional Title)*", md)

        # 2. Test HTML: visual card header has badge Conditional Title and metric is in Evaluated Metrics
        html_builder = HtmlVisualBuilder(page=page, report_model=report, config=DocGenConfig())
        html = html_builder.build_content()
        self.assertIn("Sales[DynamicTitle]", html)
        self.assertIn('class="badge badge-dim" style="margin-left: 0.5rem;">Conditional Title</span>', html)
        self.assertIn("(Role: Conditional Title)", html)


if __name__ == "__main__":
    unittest.main()

