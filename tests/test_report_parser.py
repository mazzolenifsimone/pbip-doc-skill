"""
Unit tests for PBIP Report Parser (pbip_doc.report_parser and pbip_doc.report_schema).
Vanilla Python unittest suite.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pbip_doc.report_schema import (
    PBIPReportModel,
    ReportSummary,
    PageDefinition,
    VisualDefinition,
    BoundingBox,
    SpatialPosition,
    CalculationContext,
    EvaluatedMetric,
    SlicingCoordinate,
    ActiveFilter,
    PagePanelFilter,
    PageSlicer,
)
from pbip_doc.report_parser import (
    ReportParser,
    _calculate_spatial_position,
    _resolve_canvas_position,
    _parse_where_condition,
    _extract_field_details,
)
from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.visual_doc import PageVisualDocBuilder


class TestReportParser(unittest.TestCase):
    def test_spatial_position_and_zone_calculation(self):
        # 1920 x 1080 canvas
        # Top-Left visual
        pos1 = {"x": 100.0, "y": 100.0, "width": 400.0, "height": 200.0, "z": 1000}
        sp1 = _calculate_spatial_position(pos1, page_width=1920, page_height=1080)
        self.assertEqual(sp1.center_x, 300.0)
        self.assertEqual(sp1.center_y, 200.0)
        self.assertEqual(sp1.zone, "Top-Left")

        # Bottom-Right visual
        pos2 = {"x": 1500.0, "y": 800.0, "width": 300.0, "height": 200.0, "z": 2000}
        sp2 = _calculate_spatial_position(pos2, page_width=1920, page_height=1080)
        self.assertEqual(sp2.center_x, 1650.0)
        self.assertEqual(sp2.center_y, 900.0)
        self.assertEqual(sp2.zone, "Bottom-Right")

        # Center visual
        pos3 = {"x": 860.0, "y": 440.0, "width": 200.0, "height": 200.0, "z": 3000}
        sp3 = _calculate_spatial_position(pos3, page_width=1920, page_height=1080)
        self.assertEqual(sp3.center_x, 960.0)
        self.assertEqual(sp3.center_y, 540.0)
        self.assertEqual(sp3.zone, "Center")

    def test_where_condition_parsing(self):
        # Test In condition
        where_in = [
            {
                "Condition": {
                    "In": {
                        "Expressions": [{"Column": {"Property": "Category"}}],
                        "Values": [[{"Literal": {"Value": "'Urban'"}}], [{"Literal": {"Value": "'Rural'"}}]],
                    }
                }
            }
        ]
        op, vals, text = _parse_where_condition(where_in)
        self.assertEqual(op, "In")
        self.assertEqual(vals, ["Urban", "Rural"])
        self.assertEqual(text, "In (Urban, Rural)")

        # Test Not In condition
        where_not_in = [
            {
                "Condition": {
                    "Not": {
                        "Expression": {
                            "In": {
                                "Expressions": [{"Column": {"Property": "Category"}}],
                                "Values": [[{"Literal": {"Value": "'Components'"}}]],
                            }
                        }
                    }
                }
            }
        ]
        op_not, vals_not, text_not = _parse_where_condition(where_not_in)
        self.assertEqual(op_not, "NotIn")
        self.assertEqual(vals_not, ["Components"])
        self.assertEqual(text_not, "Exclude (Components)")

        # Test Comparison condition
        where_comp = [
            {
                "Condition": {
                    "Comparison": {
                        "ComparisonKind": 3,  # >
                        "Left": {"Measure": {"Property": "Total Sales"}},
                        "Right": {"Literal": {"Value": "1000"}},
                    }
                }
            }
        ]
        op_c, vals_c, text_c = _parse_where_condition(where_comp)
        self.assertEqual(op_c, ">")
        self.assertEqual(vals_c, ["1000"])

    def test_extract_field_details(self):
        # Measure field
        m_obj = {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": "Sales"}},
                "Property": "Total Revenue",
            }
        }
        table, field, f_type, agg = _extract_field_details(m_obj)
        self.assertEqual(table, "Sales")
        self.assertEqual(field, "Total Revenue")
        self.assertEqual(f_type, "MEASURE")
        self.assertIsNone(agg)

        # Column field
        col_obj = {
            "Column": {
                "Expression": {"SourceRef": {"Entity": "Customer"}},
                "Property": "Region",
            }
        }
        table_c, field_c, f_type_c, agg_c = _extract_field_details(col_obj)
        self.assertEqual(table_c, "Customer")
        self.assertEqual(field_c, "Region")
        self.assertEqual(f_type_c, "COLUMN")
        self.assertIsNone(agg_c)

        # Implicit Aggregation field
        agg_obj = {
            "Aggregation": {
                "Expression": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": "Sales"}},
                        "Property": "Freight",
                    }
                },
                "Function": 0,  # Sum
            }
        }
        table_a, field_a, f_type_a, agg_a = _extract_field_details(agg_obj)
        self.assertEqual(table_a, "Sales")
        self.assertEqual(field_a, "Freight")
        self.assertEqual(f_type_a, "IMPLICIT_MEASURE")
        self.assertEqual(agg_a, "Sum")

    def test_pbir_mock_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            report_dir = tmp_path / "Sales.Report"
            def_dir = report_dir / "definition"
            pages_dir = def_dir / "pages"
            p1_dir = pages_dir / "Section1"
            v1_dir = p1_dir / "visuals" / "v1"
            s1_dir = p1_dir / "visuals" / "s1"

            v1_dir.mkdir(parents=True, exist_ok=True)
            s1_dir.mkdir(parents=True, exist_ok=True)

            # definition/pages/pages.json
            with open(pages_dir / "pages.json", "w", encoding="utf-8") as f:
                json.dump({"pageOrder": ["Section1"]}, f)

            # page.json with both locked and unlocked filters
            page_json = {
                "name": "Section1",
                "displayName": "Executive Summary",
                "width": 1920,
                "height": 1080,
                "visibility": "Visible",
                "type": "Normal",
                "filterConfig": {
                    "filters": [
                        # Locked active filter (has condition) -> MUST BE INCLUDED
                        {
                            "name": "F1",
                            "field": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Entity": "Date"}},
                                    "Property": "Year",
                                }
                            },
                            "isLockedInViewMode": True,
                            "filter": {
                                "Where": [
                                    {
                                        "Condition": {
                                            "In": {
                                                "Expressions": [{"Column": {"Property": "Year"}}],
                                                "Values": [[{"Literal": {"Value": "'2024'"}}]],
                                            }
                                        }
                                    }
                                ]
                            },
                        },
                        # Locked inactive filter (no condition) -> MUST BE EXCLUDED FROM LOCKED
                        {
                            "name": "F2",
                            "field": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Entity": "Date"}},
                                    "Property": "Month",
                                }
                            },
                            "isLockedInViewMode": True,
                        },
                        # Unlocked available filter (no condition) -> INCLUDED WITH DEFAULT "All"
                        {
                            "name": "F3",
                            "field": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Entity": "Customer"}},
                                    "Property": "Country",
                                }
                            },
                            "isLockedInViewMode": False,
                        },
                    ]
                },
            }
            with open(p1_dir / "page.json", "w", encoding="utf-8") as f:
                json.dump(page_json, f)

            # Visual 1: Bar chart with metrics, coordinates, and visual filter
            v1_json = {
                "name": "v1",
                "position": {"x": 100, "y": 100, "width": 800, "height": 400, "z": 10},
                "visual": {
                    "visualType": "barChart",
                    "query": {
                        "queryState": {
                            "Category": {
                                "projections": [
                                    {
                                        "field": {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Entity": "Product"}},
                                                "Property": "Category",
                                            }
                                        }
                                    }
                                ]
                            },
                            "Y": {
                                "projections": [
                                    {
                                        "field": {
                                            "Measure": {
                                                "Expression": {"SourceRef": {"Entity": "Sales"}},
                                                "Property": "Total Revenue",
                                            }
                                        }
                                    }
                                ]
                            },
                        }
                    },
                    "filterConfig": {
                        "filters": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": "Product"}},
                                        "Property": "Category",
                                    }
                                },
                                "filter": {
                                    "Where": [
                                        {
                                            "Condition": {
                                                "Not": {
                                                    "Expression": {
                                                        "In": {
                                                            "Expressions": [{"Column": {"Property": "Category"}}],
                                                            "Values": [[{"Literal": {"Value": "'Obsolete'"}}]],
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
            }
            with open(v1_dir / "visual.json", "w", encoding="utf-8") as f:
                json.dump(v1_json, f)

            # Slicer visual
            s1_json = {
                "name": "s1",
                "position": {"x": 1000, "y": 100, "width": 300, "height": 100, "z": 20},
                "visual": {
                    "visualType": "slicer",
                    "query": {
                        "queryState": {
                            "Values": {
                                "projections": [
                                    {
                                        "field": {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Entity": "Customer"}},
                                                "Property": "Segment",
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    },
                },
            }
            with open(s1_dir / "visual.json", "w", encoding="utf-8") as f:
                json.dump(s1_json, f)

            # Execute parser
            parser = ReportParser()
            model = parser.parse(str(report_dir))

            self.assertEqual(model.report_name, "Sales")
            self.assertEqual(model.format, "PBIR")
            self.assertEqual(model.summary.total_pages, 1)
            self.assertEqual(model.summary.total_visuals, 2)

            page = model.pages[0]
            self.assertEqual(page.display_name, "Executive Summary")
            self.assertEqual(page.page_type, "NORMAL")
            self.assertFalse(page.is_hidden)

            v1 = next(v for v in page.visuals if v.visual_id == "v1")
            self.assertEqual(v1.title, "Total Revenue by Category")
            self.assertEqual(v1.spatial_position.zone, "Top-Left")
            self.assertEqual(v1.spatial_position.center_x, 500.0)
            self.assertEqual(v1.spatial_position.center_y, 300.0)

            cc = v1.calculation_context
            # Evaluated metric
            self.assertEqual(len(cc.evaluated_metrics), 1)
            self.assertEqual(cc.evaluated_metrics[0].model_key, "Sales[Total Revenue]")
            self.assertEqual(cc.evaluated_metrics[0].field_type, "MEASURE")

            # Slicing coordinate
            self.assertEqual(len(cc.slicing_coordinates), 1)
            self.assertEqual(cc.slicing_coordinates[0].model_key, "Product[Category]")

            # Visual active filter
            self.assertEqual(len(cc.visual_active_filters), 1)
            self.assertEqual(cc.visual_active_filters[0].condition, "Exclude (Obsolete)")

            # Locked active page filter (only F1, F2 excluded!)
            self.assertEqual(len(cc.locked_active_filters), 1)
            self.assertEqual(cc.locked_active_filters[0].field, "Year")
            self.assertEqual(cc.locked_active_filters[0].applied_values, ["2024"])

            # Unlocked available page filter (F3 with default "All")
            self.assertEqual(len(cc.unlocked_available_filters), 1)
            self.assertEqual(cc.unlocked_available_filters[0].field, "Country")
            self.assertEqual(cc.unlocked_available_filters[0].default_value, "All (No filter applied)")

            # Page Slicers
            self.assertEqual(len(cc.page_slicers), 1)
            self.assertEqual(cc.page_slicers[0].model_key, "Customer[Segment]")

            # Serialization to dict test
            d = model.to_dict()
            self.assertIn("pages", d)
            self.assertIn("summary", d)

    def test_legacy_mock_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            report_dir = tmp_path / "Marketing.Report"
            report_dir.mkdir(parents=True, exist_ok=True)

            legacy_report_json = {
                "sections": [
                    {
                        "name": "ReportSection1",
                        "displayName": "Campaign Overview",
                        "width": 1280,
                        "height": 720,
                        "visibility": 0,
                        "filters": json.dumps([
                            {
                                "expression": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": "Campaign"}},
                                        "Property": "Status",
                                    }
                                },
                                "isLockedInViewMode": True,
                                "filter": {
                                    "Where": [
                                        {
                                            "Condition": {
                                                "In": {
                                                    "Expressions": [{"Column": {"Property": "Status"}}],
                                                    "Values": [[{"Literal": {"Value": "'Active'"}}]],
                                                }
                                            }
                                        }
                                    ]
                                },
                            }
                        ]),
                        "visualContainers": [
                            {
                                "x": 50,
                                "y": 50,
                                "width": 500,
                                "height": 300,
                                "z": 100,
                                "config": json.dumps({
                                    "name": "vc_chart1",
                                    "singleVisual": {
                                        "visualType": "barChart",
                                        "projections": {
                                            "Category": [{"queryRef": "Campaign.Name"}],
                                            "Y": [{"queryRef": "Metrics.Conversions"}],
                                        },
                                        "prototypeQuery": {
                                            "From": [
                                                {"Name": "c", "Entity": "Campaign", "Type": 0},
                                                {"Name": "m", "Entity": "Metrics", "Type": 0},
                                            ],
                                            "Select": [
                                                {
                                                    "Column": {
                                                        "Expression": {"SourceRef": {"Source": "c"}},
                                                        "Property": "Name",
                                                    },
                                                    "Name": "Campaign.Name",
                                                },
                                                {
                                                    "Measure": {
                                                        "Expression": {"SourceRef": {"Source": "m"}},
                                                        "Property": "Conversions",
                                                    },
                                                    "Name": "Metrics.Conversions",
                                                },
                                            ],
                                        },
                                    },
                                }),
                            }
                        ],
                    }
                ]
            }

            with open(report_dir / "report.json", "w", encoding="utf-8") as f:
                json.dump(legacy_report_json, f)

            parser = ReportParser()
            model = parser.parse(str(report_dir))

            self.assertEqual(model.report_name, "Marketing")
            self.assertEqual(model.format, "LEGACY")
            self.assertEqual(model.summary.total_pages, 1)

            page = model.pages[0]
            self.assertEqual(page.display_name, "Campaign Overview")
            self.assertEqual(len(page.visuals), 1)

            v = page.visuals[0]
            self.assertEqual(v.title, "Conversions by Name")
            self.assertEqual(v.spatial_position.zone, "Top-Left")

            cc = v.calculation_context
            self.assertEqual(len(cc.evaluated_metrics), 1)
            self.assertEqual(cc.evaluated_metrics[0].model_key, "Metrics[Conversions]")
            self.assertEqual(cc.evaluated_metrics[0].field_type, "MEASURE")

            self.assertEqual(len(cc.slicing_coordinates), 1)
            self.assertEqual(cc.slicing_coordinates[0].model_key, "Campaign[Name]")

            self.assertEqual(len(cc.locked_active_filters), 1)
            self.assertEqual(cc.locked_active_filters[0].field, "Status")
            self.assertEqual(cc.locked_active_filters[0].applied_values, ["Active"])

    def test_samples_integration_if_present(self):
        """Integration test against actual samples in the workspace if they exist."""
        samples_root = Path(__file__).resolve().parent.parent / "samples"
        pbir_aw = samples_root / "AdventureWorks_Sales" / "AdventureWorks_Sales.Report"

        if pbir_aw.exists():
            parser = ReportParser()
            model = parser.parse(str(pbir_aw))
            self.assertEqual(model.format, "PBIR")
            self.assertGreater(model.summary.total_visuals, 0)
            self.assertGreater(len(model.pages), 0)

        legacy_ai = samples_root / "temp_Samples" / "Artificial Intelligence Sample" / "Artificial Intelligence Sample.Report"
        if legacy_ai.exists():
            parser = ReportParser()
            model_leg = parser.parse(str(legacy_ai))
            self.assertEqual(model_leg.format, "LEGACY")
            self.assertGreater(model_leg.summary.total_visuals, 0)
            self.assertGreater(len(model_leg.pages), 0)

    def test_resolve_canvas_position_direct_and_nested(self):
        """Tests _resolve_canvas_position across standalone, 1-level, multi-level, and cyclic hierarchies."""
        # 1. Visual directly on canvas
        containers = {
            "v_root": {"id": "v_root", "x": 120.0, "y": 80.0, "parent_group_name": None, "is_hidden": False},
        }
        rx, ry, is_h = _resolve_canvas_position("v_root", containers)
        self.assertEqual((rx, ry, is_h), (120.0, 80.0, False))

        # 2. 1-level parent group
        containers["g1"] = {"id": "g1", "x": 200.0, "y": 150.0, "parent_group_name": None, "is_hidden": True}
        containers["v_child1"] = {"id": "v_child1", "x": 30.0, "y": 40.0, "parent_group_name": "g1", "is_hidden": False}
        rx, ry, is_h = _resolve_canvas_position("v_child1", containers)
        self.assertEqual(rx, 230.0)
        self.assertEqual(ry, 190.0)
        self.assertTrue(is_h)  # Inherited from g1

        # 3. 2-level nested groups (v_leaf -> g2 -> g1 -> canvas)
        containers["g2"] = {"id": "g2", "x": 50.0, "y": 60.0, "parent_group_name": "g1", "is_hidden": False}
        containers["v_leaf"] = {"id": "v_leaf", "x": 10.0, "y": 20.0, "parent_group_name": "g2", "is_hidden": False}
        rx, ry, is_h = _resolve_canvas_position("v_leaf", containers)
        self.assertEqual(rx, 260.0)  # 10 + 50 + 200
        self.assertEqual(ry, 230.0)  # 20 + 60 + 150
        self.assertTrue(is_h)  # Inherited from g1

        # 4. Cycle safe (g_a -> g_b -> g_a)
        containers["g_a"] = {"id": "g_a", "x": 10.0, "y": 10.0, "parent_group_name": "g_b", "is_hidden": False}
        containers["g_b"] = {"id": "g_b", "x": 20.0, "y": 20.0, "parent_group_name": "g_a", "is_hidden": False}
        rx, ry, is_h = _resolve_canvas_position("g_a", containers)
        self.assertEqual((rx, ry, is_h), (30.0, 30.0, False))

        # 5. Missing parent terminates cleanly
        containers["v_orphan"] = {"id": "v_orphan", "x": 75.0, "y": 45.0, "parent_group_name": "non_existent", "is_hidden": False}
        rx, ry, is_h = _resolve_canvas_position("v_orphan", containers)
        self.assertEqual((rx, ry, is_h), (75.0, 45.0, False))

    def test_pbir_nested_visual_groups_resolution(self):
        """Validates that PBIR visual containers nested inside groups correctly resolve canvas coordinates and visibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "TestPBIR.Report"
            page_dir = report_dir / "definition" / "pages" / "Page1"
            visuals_dir = page_dir / "visuals"
            visuals_dir.mkdir(parents=True)

            # Page json
            with open(page_dir / "page.json", "w", encoding="utf-8") as f:
                json.dump({"name": "Page1", "displayName": "Nested PBIR Test", "width": 1920, "height": 1080}, f)

            # Group 1 (Canvas root, hidden)
            g1_dir = visuals_dir / "g1"
            g1_dir.mkdir()
            with open(g1_dir / "visual.json", "w", encoding="utf-8") as f:
                json.dump({
                    "name": "g1",
                    "position": {"x": 100, "y": 200, "width": 800, "height": 600, "z": 100},
                    "visualGroup": {"displayName": "Root Group", "isHidden": True},
                }, f)

            # Group 2 (Nested in g1, visible)
            g2_dir = visuals_dir / "g2"
            g2_dir.mkdir()
            with open(g2_dir / "visual.json", "w", encoding="utf-8") as f:
                json.dump({
                    "name": "g2",
                    "position": {"x": 50, "y": 60, "width": 500, "height": 400, "z": 200},
                    "parentGroupName": "g1",
                    "visualGroup": {"displayName": "Sub Group", "isHidden": False},
                }, f)

            # Child visual (Nested in g2, visible locally)
            v1_dir = visuals_dir / "v1"
            v1_dir.mkdir()
            with open(v1_dir / "visual.json", "w", encoding="utf-8") as f:
                json.dump({
                    "name": "v1",
                    "position": {"x": 20, "y": 30, "width": 400, "height": 300, "z": 300},
                    "parentGroupName": "g2",
                    "isHidden": False,
                    "visual": {
                        "visualType": "barChart",
                        "query": {
                            "queryState": {
                                "Y": {
                                    "projections": [
                                        {
                                            "field": {
                                                "Measure": {
                                                    "Expression": {"SourceRef": {"Entity": "Sales"}},
                                                    "Property": "Amount",
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                    },
                }, f)

            parser = ReportParser()
            model = parser.parse(str(report_dir))
            page = model.pages[0]

            # Groups g1 and g2 must NOT be included as chart visuals
            self.assertEqual(len(page.visuals), 1)

            v1 = page.visuals[0]
            self.assertEqual(v1.visual_id, "v1")
            self.assertEqual(v1.parent_group_name, "g2")
            # Inherited visibility from g1: True
            self.assertTrue(v1.is_hidden)

            # Coordinates: visual(20, 30) + g2(50, 60) + g1(100, 200) = (170, 290)
            self.assertIsNotNone(v1.spatial_position)
            bbox = v1.spatial_position.bounding_box
            self.assertEqual(bbox.x, 170.0)
            self.assertEqual(bbox.y, 290.0)
            self.assertEqual(bbox.width, 400.0)
            self.assertEqual(bbox.height, 300.0)
            # Center: 170 + 200 = 370.0, 290 + 150 = 440.0
            self.assertEqual(v1.spatial_position.center_x, 370.0)
            self.assertEqual(v1.spatial_position.center_y, 440.0)

    def test_legacy_nested_visual_groups_resolution(self):
        """Validates that Legacy visualContainers nested inside singleVisualGroup correctly resolve coordinates and visibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "TestLegacy.Report"
            report_dir.mkdir(parents=True)

            legacy_report_json = {
                "sections": [
                    {
                        "name": "Sec1",
                        "displayName": "Nested Legacy Test",
                        "width": 1920,
                        "height": 1080,
                        "visualContainers": [
                            # Group 1 (Canvas root, visible)
                            {
                                "x": 200,
                                "y": 100,
                                "width": 900,
                                "height": 700,
                                "z": 100,
                                "config": json.dumps({
                                    "name": "grp_root",
                                    "singleVisualGroup": {"displayName": "Root Group", "isHidden": False},
                                }),
                            },
                            # Group 2 (Nested in grp_root, hidden)
                            {
                                "x": 50,
                                "y": 50,
                                "width": 600,
                                "height": 500,
                                "z": 200,
                                "config": json.dumps({
                                    "name": "grp_sub",
                                    "parentGroupName": "grp_root",
                                    "singleVisualGroup": {"displayName": "Sub Group", "isHidden": True},
                                }),
                            },
                            # Child visual (Nested in grp_sub, visible locally)
                            {
                                "x": 10,
                                "y": 20,
                                "width": 300,
                                "height": 200,
                                "z": 300,
                                "config": json.dumps({
                                    "name": "v_chart",
                                    "parentGroupName": "grp_sub",
                                    "singleVisual": {
                                        "visualType": "pieChart",
                                        "projections": {
                                            "Y": [{"queryRef": "Sales.Total"}],
                                        },
                                        "prototypeQuery": {
                                            "From": [{"Name": "s", "Entity": "Sales", "Type": 0}],
                                            "Select": [
                                                {
                                                    "Measure": {
                                                        "Expression": {"SourceRef": {"Source": "s"}},
                                                        "Property": "Total",
                                                    },
                                                    "Name": "Sales.Total",
                                                }
                                            ],
                                        },
                                    },
                                }),
                            },
                        ],
                    }
                ]
            }

            with open(report_dir / "report.json", "w", encoding="utf-8") as f:
                json.dump(legacy_report_json, f)

            parser = ReportParser()
            model = parser.parse(str(report_dir))
            page = model.pages[0]

            # Groups must NOT be emitted as visuals
            self.assertEqual(len(page.visuals), 1)

            v = page.visuals[0]
            self.assertEqual(v.visual_id, "v_chart")
            self.assertEqual(v.parent_group_name, "grp_sub")
            # Inherited visibility from grp_sub: True
            self.assertTrue(v.is_hidden)

            # Coordinates: visual(10, 20) + grp_sub(50, 50) + grp_root(200, 100) = (260, 170)
            self.assertIsNotNone(v.spatial_position)
            bbox = v.spatial_position.bounding_box
            self.assertEqual(bbox.x, 260.0)
            self.assertEqual(bbox.y, 170.0)
            self.assertEqual(bbox.width, 300.0)
            self.assertEqual(bbox.height, 200.0)
            # Center: 260 + 150 = 410.0, 170 + 100 = 270.0
            self.assertEqual(v.spatial_position.center_x, 410.0)
            self.assertEqual(v.spatial_position.center_y, 270.0)


class TestReportVisualDocgen(unittest.TestCase):
    """Test suite for Markdown documentation generation of Report Pages and Visuals."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_report_model(self) -> PBIPReportModel:
        locked_f = [
            PagePanelFilter(
                scope="Page Filter Panel (Locked)",
                table="Date",
                field="Year",
                is_locked=True,
                applied_values=["2024"],
                default_value="In (2024)",
                operator="In",
            )
        ]
        unlocked_f = [
            PagePanelFilter(
                scope="Page Filter Panel (Interactive)",
                table="Customer",
                field="Country",
                is_locked=False,
                applied_values=None,
                default_value="All (No filter applied)",
                operator=None,
            )
        ]
        slicers = [
            PageSlicer(
                slicer_visual_id="slicer1",
                table="Date",
                field="Date",
                model_key="Date[Date]",
                default_selection="All",
                is_synced_across_pages=False,
            )
        ]

        # Visual 1: Dynamic Chart with metric, coordinate, filter
        v1_calc = CalculationContext(
            evaluated_metrics=[
                EvaluatedMetric(
                    table="Sales",
                    field="Cost",
                    field_type="MEASURE",
                    role="Y",
                    model_key="Sales[Cost]",
                )
            ],
            slicing_coordinates=[
                SlicingCoordinate(
                    role="Category",
                    table="Product",
                    field="Category",
                    model_key="Product[Category]",
                )
            ],
            visual_active_filters=[
                ActiveFilter(
                    table="Product",
                    field="Category",
                    filter_type="Categorical",
                    condition="In (Bikes)",
                    scope="Visual",
                )
            ],
            locked_active_filters=locked_f,
            unlocked_available_filters=unlocked_f,
            page_slicers=slicers,
        )
        v1 = VisualDefinition(
            visual_id="v1_chart",
            title="Cost by Category",
            visual_type="donutChart",
            spatial_position=SpatialPosition(
                center_x=500.0,
                center_y=300.0,
                zone="Top-Center",
                bounding_box=BoundingBox(x=100.0, y=100.0, width=800.0, height=400.0),
            ),
            calculation_context=v1_calc,
        )

        # Visual 2: Dynamic Shape with text bound to a measure
        v2_calc = CalculationContext(
            evaluated_metrics=[
                EvaluatedMetric(
                    table="Sales",
                    field="DynamicTitle",
                    field_type="MEASURE",
                    role="DynamicProperty",
                    model_key="Sales[DynamicTitle]",
                )
            ],
            locked_active_filters=locked_f,
            unlocked_available_filters=unlocked_f,
            page_slicers=slicers,
        )
        v2 = VisualDefinition(
            visual_id="v2_shape_dynamic",
            title="Shape with Metric",
            visual_type="shape",
            spatial_position=SpatialPosition(
                center_x=200.0,
                center_y=100.0,
                zone="Top-Left",
                bounding_box=BoundingBox(x=50.0, y=50.0, width=300.0, height=100.0),
            ),
            calculation_context=v2_calc,
        )

        # Visual 3: Static Decorative Shape (out-of-scope)
        v3_calc = CalculationContext(
            locked_active_filters=locked_f,
            unlocked_available_filters=unlocked_f,
            page_slicers=slicers,
        )
        v3 = VisualDefinition(
            visual_id="v3_static_line",
            title="Shape",
            visual_type="shape",
            spatial_position=SpatialPosition(
                center_x=100.0,
                center_y=50.0,
                zone="Top-Left",
                bounding_box=BoundingBox(x=0.0, y=0.0, width=200.0, height=100.0),
            ),
            calculation_context=v3_calc,
        )

        page = PageDefinition(
            page_id="ReportSection1",
            display_name="Executive Overview",
            page_number=1,
            is_hidden=False,
            page_type="NORMAL",
            width=1920,
            height=1080,
            visuals=[v1, v2, v3],
        )

        return PBIPReportModel(
            report_name="Sales Performance",
            format="PBIR",
            source_path=str(self.root / "Sales Performance.Report"),
            summary=ReportSummary(
                total_pages=1,
                visible_pages=1,
                hidden_pages=0,
                total_visuals=3,
                visual_types_distribution={"donutChart": 1, "shape": 2},
            ),
            pages=[page],
        )

    def test_page_visual_doc_builder(self):
        from pbip_doc.docgen.visual_doc import PageVisualDocBuilder
        from pbip_doc.docgen.config import DocGenConfig

        report = self._create_mock_report_model()
        page = report.pages[0]
        config = DocGenConfig()

        builder = PageVisualDocBuilder(
            page=page,
            report_model=report,
            config=config,
            known_measure_keys={("Sales", "Cost"), ("Sales", "DynamicTitle")},
            known_table_names={"Sales", "Product", "Date", "Customer"},
        )
        md = builder.build_markdown()

        # Check frontmatter
        self.assertIn("title: \"Report Page: Executive Overview\"", md)
        self.assertIn("dynamic_visuals_count: 2", md)
        self.assertIn("omitted_static_elements_count: 1", md)

        # Check locked and unlocked filter panels
        self.assertIn("Locked Active Page Filters", md)
        self.assertIn("2024", md)
        self.assertIn("Interactive Page Filters", md)
        self.assertIn("All (No filter applied)", md)

        # Check slicers
        self.assertIn("Date[Date]", md)

        # Check dynamic visuals: v1 and v2 present, v3 omitted from in-scope catalog
        self.assertIn("### 1. Shape with Metric", md)
        self.assertIn("### 2. Cost by Category", md)
        self.assertIn("[Sales[Cost]](../measures/Sales/Cost.md)", md)
        self.assertIn("[Sales[DynamicTitle]](../measures/Sales/DynamicTitle.md)", md)
        self.assertIn("[Product](../tables/Product.md)", md)
        self.assertIn("In (Bikes)", md)

        # Check omitted static elements section
        self.assertIn("## Omitted Static Elements", md)
        self.assertIn("1", md)

    def test_page_visual_doc_builder_custom_base_url(self):
        from pbip_doc.docgen.visual_doc import PageVisualDocBuilder
        from pbip_doc.docgen.config import DocGenConfig

        report = self._create_mock_report_model()
        page = report.pages[0]
        config = DocGenConfig(base_doc_url="https://portal.internal.net/analytics")

        builder = PageVisualDocBuilder(
            page=page,
            report_model=report,
            config=config,
            known_measure_keys={("Sales", "Cost")},
            known_table_names={"Sales", "Product"},
        )
        md = builder.build_markdown()

        self.assertIn(
            "[Sales[Cost]](https://portal.internal.net/analytics/measures/Sales/Cost.md)",
            md,
        )
        self.assertIn(
            "[Product](https://portal.internal.net/analytics/tables/Product.md)",
            md,
        )

    def test_index_doc_builder_includes_report_catalog(self):
        from pbip_doc.docgen.index_doc import IndexDocBuilder
        from pbip_doc.docgen.config import DocGenConfig

        report = self._create_mock_report_model()
        model_data = {
            "model_name": "SalesModel",
            "source_format": "PBIP",
            "tables": [{"name": "Sales", "role": "Fact"}, {"name": "Product", "role": "Dimension"}],
            "measures": [{"name": "Cost", "table": "Sales"}],
        }

        config = DocGenConfig()
        builder = IndexDocBuilder(model_data, config, report_model=report)
        md = builder.build_markdown()

        self.assertIn("## Report Presentation & Visuals: `Sales Performance`", md)
        self.assertIn("[Executive Overview](visuals/Executive_Overview.md)", md)
        self.assertIn("1920x1080", md)
        self.assertIn("[Sales[Cost]](measures/Sales/Cost.md)", md)

    def test_markdown_doc_generator_with_sibling_report(self):
        from pbip_doc.docgen import MarkdownDocGenerator, DocGenConfig, VisualDocLabels

        # Setup synthetic PBIP root with .SemanticModel and .Report
        pbip_root = self.root / "AdventureWorks"
        pbip_root.mkdir(parents=True)
        sem_dir = pbip_root / "AdventureWorks.SemanticModel"
        sem_dir.mkdir()
        def_dir = sem_dir / "definition"
        def_dir.mkdir()

        # Write model.tmdl
        with open(def_dir / "model.tmdl", "w", encoding="utf-8") as f:
            f.write("model Model\n\tculture: en-US\n\ttable Sales\n\ttable Product\n")
        with open(def_dir / "relationships.tmdl", "w", encoding="utf-8") as f:
            f.write("")

        tables_dir = def_dir / "tables"
        tables_dir.mkdir()
        with open(tables_dir / "Sales.tmdl", "w", encoding="utf-8") as f:
            f.write("table Sales\n\tmeasure Cost = SUM(Sales[Amount])\n\tcolumn Amount\n\t\tdataType: int64\n\tpartition Sales = m\n\t\tmode: import\n\t\tsource =\n\t\t\t#\"Source\"\n")
        with open(tables_dir / "Product.tmdl", "w", encoding="utf-8") as f:
            f.write("table Product\n\tcolumn Category\n\t\tdataType: string\n\tpartition Product = m\n\t\tmode: import\n\t\tsource =\n\t\t\t#\"Source\"\n")

        # Setup .Report
        rep_dir = pbip_root / "AdventureWorks.Report"
        pages_dir = rep_dir / "definition" / "pages" / "p1" / "visuals" / "v1"
        pages_dir.mkdir(parents=True)

        with open(rep_dir / "definition" / "pages" / "pages.json", "w", encoding="utf-8") as f:
            json.dump({"pageOrder": ["p1"]}, f)

        with open(rep_dir / "definition" / "pages" / "p1" / "page.json", "w", encoding="utf-8") as f:
            json.dump({"name": "p1", "displayName": "Overview", "width": 1920, "height": 1080}, f)

        v_json = {
            "name": "v1",
            "position": {"x": 100, "y": 100, "width": 400, "height": 300},
            "visual": {
                "visualType": "barChart",
                "query": {
                    "queryState": {
                        "Y": {
                            "projections": [
                                {
                                    "field": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": "Sales"}},
                                            "Property": "Cost",
                                        }
                                    }
                                }
                            ]
                        }
                    }
                },
            },
        }
        with open(pages_dir / "visual.json", "w", encoding="utf-8") as f:
            json.dump(v_json, f)

        # 1. Test standard generation (with visual docs and SVG maps auto-discovered)
        cfg = DocGenConfig()
        gen = MarkdownDocGenerator(cfg)
        docs = gen.generate_all_documents(pbip_root)

        self.assertIn("AdventureWorks.md", docs)
        self.assertIn("tables/Sales.md", docs)
        self.assertIn("measures/Sales/Cost.md", docs)
        self.assertIn("visuals/Overview.md", docs)
        self.assertIn("visuals/assets/Overview/v1.svg", docs)
        self.assertIn("## Report Presentation & Visuals: `AdventureWorks`", docs["AdventureWorks.md"])

        # Check pbip_project frontmatter across all document types
        self.assertIn("pbip_project: AdventureWorks", docs["AdventureWorks.md"])
        self.assertIn("pbip_project: AdventureWorks", docs["tables/Sales.md"])
        self.assertIn("pbip_project: AdventureWorks", docs["measures/Sales/Cost.md"])

        # Check visual markdown contains pure markdown image, indicative position, filter perimeter
        overview_md = docs["visuals/Overview.md"]
        self.assertIn("pbip_project: AdventureWorks", overview_md)
        self.assertIn("![Cost - Canvas Location](assets/Overview/v1.svg)", overview_md)
        self.assertNotIn("<img", overview_md)
        self.assertNotIn("<div", overview_md)
        self.assertIn("**Indicative Position**:", overview_md)
        self.assertIn("**Applicable Filter Perimeter**:", overview_md)

        # 2. Test generation with include_visual_docs=False
        cfg_novis = DocGenConfig(include_visual_docs=False)
        gen_novis = MarkdownDocGenerator(cfg_novis)
        docs_novis = gen_novis.generate_all_documents(pbip_root)

        self.assertIn("AdventureWorks.md", docs_novis)
        self.assertNotIn("visuals/Overview.md", docs_novis)
        self.assertNotIn("visuals/assets/Overview/v1.svg", docs_novis)
        self.assertNotIn("## Report Presentation & Visuals", docs_novis["AdventureWorks.md"])

    def test_visual_svg_map_specifications(self):
        """Tests that generated SVG mini-maps comply with dark gray, 80% transparency, and square corner specs."""
        from pbip_doc.docgen.visual_doc import PageVisualDocBuilder
        from pbip_doc.docgen.config import DocGenConfig

        report = self._create_mock_report_model()
        page = report.pages[0]
        config = DocGenConfig()

        builder = PageVisualDocBuilder(
            page=page,
            report_model=report,
            config=config,
        )

        # Test visible visual SVG
        v_vis = page.visuals[0]
        v_vis.is_hidden = False
        svg_vis = builder.generate_visual_svg(v_vis)

        # Compact responsive width 360px
        self.assertIn('width="360"', svg_vis)
        # Semi-transparent neutral borders and grid lines
        self.assertIn('stroke="rgba(128, 128, 128, 0.35)"', svg_vis)
        self.assertIn('stroke="rgba(128, 128, 128, 0.22)"', svg_vis)
        # Visual fill with semi-transparent accent highlight
        self.assertIn('fill="rgba(59, 130, 246, 0.22)"', svg_vis)
        # Center marker: Accent X
        self.assertIn('stroke="rgba(59, 130, 246, 0.95)"', svg_vis)
        self.assertIn('stroke-linecap="square"', svg_vis)
        # Solid border for visible visual
        self.assertNotIn('stroke-dasharray="16,10"', svg_vis)
        # No dimension badge in SVG
        self.assertNotIn("1920 × 1080", svg_vis)

        # Test hidden visual SVG
        v_vis.is_hidden = True
        svg_hid = builder.generate_visual_svg(v_vis)
        self.assertIn('stroke-dasharray="16,10"', svg_hid)

        # Test build_svg_assets returns all dynamic visual SVGs
        assets = builder.build_svg_assets()
        self.assertEqual(len(assets), 2)
        self.assertTrue(any(k.endswith(".svg") for k in assets.keys()))

    def test_visual_doc_labels_abstraction_and_text_fallback(self):
        """Tests that VisualDocLabels are centralized and used consistently in both table mode and text list fallback mode."""
        from pbip_doc.docgen.visual_doc import PageVisualDocBuilder, VisualDocLabels
        from pbip_doc.docgen.config import DocGenConfig

        report = self._create_mock_report_model()
        page = report.pages[0]

        # 1. Mode with SVG Maps (Pure Markdown with image)
        cfg_table = DocGenConfig(include_visual_svg_maps=True)
        builder_table = PageVisualDocBuilder(page=page, report_model=report, config=cfg_table)
        md_table = builder_table.build_markdown()

        # Check pure markdown image syntax and absence of raw HTML
        self.assertIn("![Shape with Metric - Canvas Location](assets/Executive_Overview/v2_shape_dynamic.svg)", md_table)
        self.assertNotIn("<img", md_table)
        self.assertNotIn("<div", md_table)
        self.assertNotIn("<br", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_VISUAL_TYPE}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_INDICATIVE_POSITION}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_EVALUATED_METRICS}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_SLICING_DIMENSIONS}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_FILTER_PERIMETER}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_LOCKED_PAGE_FILTERS}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_INTERACTIVE_PAGE_FILTERS}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_CANVAS_PAGE_SLICERS}**:", md_table)
        self.assertIn(f"**{VisualDocLabels.LABEL_VISUAL_LEVEL_FILTERS}**:", md_table)
        self.assertIn(VisualDocLabels.BADGE_VISIBLE, md_table)
        self.assertIn(VisualDocLabels.BADGE_HARD_CONSTRAINT, md_table)

        # 2. Mode without SVG Maps (Standard Markdown bullet list fallback)
        cfg_text = DocGenConfig(include_visual_svg_maps=False)
        builder_text = PageVisualDocBuilder(page=page, report_model=report, config=cfg_text)
        md_text = builder_text.build_markdown()

        # Check bullet list structure without image
        self.assertNotIn("![Shape with Metric - Canvas Location]", md_text)
        self.assertNotIn("<img", md_text)
        self.assertNotIn("<div", md_text)
        self.assertNotIn("<br", md_text)
        self.assertIn(f"- **{VisualDocLabels.LABEL_VISUAL_TYPE}**:", md_text)
        self.assertIn(f"- **{VisualDocLabels.LABEL_INDICATIVE_POSITION}**:", md_text)
        self.assertIn(f"- **{VisualDocLabels.LABEL_EVALUATED_METRICS}**:", md_text)
        self.assertIn(f"- **{VisualDocLabels.LABEL_SLICING_DIMENSIONS}**:", md_text)
        self.assertIn(f"- **{VisualDocLabels.LABEL_FILTER_PERIMETER}**:", md_text)
        self.assertIn(f"  - **{VisualDocLabels.LABEL_LOCKED_PAGE_FILTERS}**:", md_text)
        self.assertIn(f"  - **{VisualDocLabels.LABEL_INTERACTIVE_PAGE_FILTERS}**:", md_text)
        self.assertIn(f"  - **{VisualDocLabels.LABEL_CANVAS_PAGE_SLICERS}**:", md_text)
        self.assertIn(f"  - **{VisualDocLabels.LABEL_VISUAL_LEVEL_FILTERS}**:", md_text)


class TestReportExternalSourcesLinking(unittest.TestCase):
    """
    Tests external sources resolution and linking in report visual documentation.
    Validates definition.pbir datasetReference parsing, inherited tables, and external measures.
    """

    def test_pbir_dataset_reference_parsing_by_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rep_dir = Path(tmpdir) / "SalesAnalytics.Report"
            rep_dir.mkdir()
            (rep_dir / "definition" / "pages" / "p1").mkdir(parents=True)
            with open(rep_dir / "definition" / "pages" / "pages.json", "w", encoding="utf-8") as f:
                json.dump([{"name": "p1"}], f)
            with open(rep_dir / "definition" / "pages" / "p1" / "page.json", "w", encoding="utf-8") as f:
                json.dump({"name": "p1", "displayName": "Summary"}, f)

            # definition.pbir with byPath
            pbir_content = {
                "datasetReference": {
                    "byPath": {"path": "../CentralSupplyChain.SemanticModel"}
                }
            }
            with open(rep_dir / "definition.pbir", "w", encoding="utf-8") as f:
                json.dump(pbir_content, f)

            parser = ReportParser()
            model = parser.parse(str(rep_dir))
            self.assertEqual(model.target_dataset_name, "CentralSupplyChain")
            self.assertIsNotNone(model.dataset_reference)

    def test_pbir_dataset_reference_parsing_by_connection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rep_dir = Path(tmpdir) / "DirectQueryReport.Report"
            rep_dir.mkdir()
            (rep_dir / "definition" / "pages" / "p1").mkdir(parents=True)
            with open(rep_dir / "definition" / "pages" / "pages.json", "w", encoding="utf-8") as f:
                json.dump([{"name": "p1"}], f)
            with open(rep_dir / "definition" / "pages" / "p1" / "page.json", "w", encoding="utf-8") as f:
                json.dump({"name": "p1", "displayName": "Executive"}, f)

            # definition.pbir with byConnection
            pbir_content = {
                "datasetReference": {
                    "byConnection": {
                        "connectionString": "Data Source=powerbi://api.powerbi.com/v1.0/org;Initial Catalog=FabricWarehouse;Integrated Security=ClaimsToken",
                        "pbiModelDatabaseName": "FabricWarehouse",
                    }
                }
            }
            with open(rep_dir / "definition.pbir", "w", encoding="utf-8") as f:
                json.dump(pbir_content, f)

            parser = ReportParser()
            model = parser.parse(str(rep_dir))
            self.assertEqual(model.target_dataset_name, "FabricWarehouse")

    def test_visual_doc_links_to_external_sources(self):
        """Verifies that external and inherited tables/measures link to external docs instead of broken 404s."""
        from pbip_doc.report_schema import PageDefinition, VisualDefinition, CalculationContext, EvaluatedMetric, SlicingCoordinate

        calc = CalculationContext(
            evaluated_metrics=[
                EvaluatedMetric(table="DimRemoteStore", field="RemoteRevenue", field_type="MEASURE", role="Values", model_key="DimRemoteStore[RemoteRevenue]"),
            ],
            slicing_coordinates=[
                SlicingCoordinate(table="DimRemoteStore", field="StoreCountry", model_key="DimRemoteStore[StoreCountry]", role="Rows"),
            ],
        )
        visual = VisualDefinition(
            visual_id="v_external",
            visual_type="barChart",
            title="External Store Sales",
            calculation_context=calc,
        )
        page = PageDefinition(
            page_id="page_ext",
            display_name="External Overview",
            page_number=1,
            visuals=[visual],
        )

        mock_report = PBIPReportModel(
            report_name="ThinReport",
            format="PBIR",
            source_path="c:/test/ThinReport.Report",
            target_dataset_name="RetailAS",
            pages=[page],
        )

        model_tables = [
            {
                "name": "DimRemoteStore",
                "is_inherited": True,
                "inherited_model_name": "RetailAS",
                "inherited_entity_name": "DimRemoteStore",
            }
        ]
        model_measures = [
            {
                "name": "RemoteRevenue",
                "table": "DimRemoteStore",
                "is_external_measure": True,
                "inherited_model_name": "RetailAS",
                "dax_expression": 'EXTERNALMEASURE("RemoteRevenue", DOUBLE, "DirectQuery to AS - RetailAS")',
            }
        ]

        cfg = DocGenConfig(
            external_docs_base_url="https://docs.company.internal/bi/models",
            include_inherited_entities=False,  # Local files for inherited entities are NOT generated
        )

        builder = PageVisualDocBuilder(
            page=page,
            report_model=mock_report,
            config=cfg,
            model_tables=model_tables,
            model_measures=model_measures,
        )

        md = builder.build_markdown()

        # 1. Check table link points to external model URL
        expected_table_url = "https://docs.company.internal/bi/models/RetailAS/tables/DimRemoteStore.md"
        self.assertIn(f"[DimRemoteStore]({expected_table_url}) *(Inherited Entity)*", md)

        # 2. Check measure link points to external measure URL
        expected_measure_url = "https://docs.company.internal/bi/models/RetailAS/measures/DimRemoteStore/RemoteRevenue.md"
        self.assertIn(f"[DimRemoteStore[RemoteRevenue]]({expected_measure_url}) *(External)*", md)

    def test_visual_doc_fallback_when_external_not_configured(self):
        """Verifies that unmapped external tables/measures render safely without emitting 404 links."""
        from pbip_doc.report_schema import PageDefinition, VisualDefinition, CalculationContext, EvaluatedMetric, SlicingCoordinate

        calc = CalculationContext(
            evaluated_metrics=[
                EvaluatedMetric(table="DimRemoteStore", field="RemoteRevenue", field_type="MEASURE", role="Values", model_key="DimRemoteStore[RemoteRevenue]"),
            ],
            slicing_coordinates=[
                SlicingCoordinate(table="DimRemoteStore", field="StoreCountry", model_key="DimRemoteStore[StoreCountry]", role="Rows"),
            ],
        )
        visual = VisualDefinition(
            visual_id="v_external",
            visual_type="barChart",
            title="External Store Sales",
            calculation_context=calc,
        )
        page = PageDefinition(
            page_id="page_ext",
            display_name="External Overview",
            page_number=1,
            visuals=[visual],
        )

        mock_report = PBIPReportModel(
            report_name="ThinReport",
            format="PBIR",
            source_path="c:/test/ThinReport.Report",
            target_dataset_name="RetailAS",
            pages=[page],
        )

        model_tables = [
            {"name": "DimRemoteStore", "is_inherited": True}
        ]
        model_measures = [
            {"name": "RemoteRevenue", "table": "DimRemoteStore", "is_external_measure": True}
        ]

        cfg = DocGenConfig(include_inherited_entities=False)

        builder = PageVisualDocBuilder(
            page=page,
            report_model=mock_report,
            config=cfg,
            model_tables=model_tables,
            model_measures=model_measures,
        )

        md = builder.build_markdown()

        # Should render safely without broken markdown link ../tables/DimRemoteStore.md
        self.assertNotIn("../tables/DimRemoteStore.md", md)
        self.assertIn("`DimRemoteStore` *(Inherited Entity)*", md)
        self.assertIn("`[DimRemoteStore[RemoteRevenue]]` *(External)*", md)

    def test_extract_custom_title(self):
        parser = ReportParser()
        # 1. Modern leaf visual with literal title in visual.visualContainerObjects
        vjson_literal = {
            "visual": {
                "visualType": "clusteredBarChart",
                "visualContainerObjects": {
                    "title": [
                        {
                            "properties": {
                                "show": {"expr": {"Literal": {"Value": "true"}}},
                                "text": {"expr": {"Literal": {"Value": "'All Group Sales'"}}},
                            }
                        }
                    ]
                },
            }
        }
        title, is_cond = parser._extract_custom_title(vjson_literal, {})
        self.assertEqual(title, "All Group Sales")
        self.assertFalse(is_cond)

        # 2. Modern leaf visual with conditional title (DAX measure) in visual.visualContainerObjects
        vjson_cond = {
            "visual": {
                "visualType": "clusteredBarChart",
                "visualContainerObjects": {
                    "title": [
                        {
                            "properties": {
                                "show": {"expr": {"Literal": {"Value": "true"}}},
                                "text": {
                                    "expr": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Source": "s"}},
                                            "Property": "MeasureTitleTest",
                                        }
                                    }
                                },
                            }
                        }
                    ]
                },
            }
        }
        alias_map = {"s": "Sales"}
        title, is_cond = parser._extract_custom_title(vjson_cond, alias_map)
        self.assertEqual(title, "Sales[MeasureTitleTest]")
        self.assertTrue(is_cond)

        # 3. Disabled title (show is false)
        vjson_disabled = {
            "visual": {
                "visualContainerObjects": {
                    "title": [
                        {
                            "properties": {
                                "show": {"expr": {"Literal": {"Value": "false"}}},
                                "text": {"expr": {"Literal": {"Value": "'Hidden Title'"}}},
                            }
                        }
                    ]
                }
            }
        }
        title, is_cond = parser._extract_custom_title(vjson_disabled, {})
        self.assertIsNone(title)
        self.assertFalse(is_cond)

    def test_ensure_conditional_title_metric(self):
        parser = ReportParser()

        # Case 1: Existing metric with DynamicProperty role gets updated to Conditional Title
        metrics = [
            EvaluatedMetric(
                table="Sales",
                field="MeasureTitleTest",
                field_type="MEASURE",
                role="DynamicProperty",
                model_key="Sales[MeasureTitleTest]",
            )
        ]
        parser._ensure_conditional_title_metric("Sales[MeasureTitleTest]", metrics)
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].role, "Conditional Title")

        # Case 2: New metric not in list gets appended with role Conditional Title
        parser._ensure_conditional_title_metric("Customer[DynamicHeader]", metrics)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[1].table, "Customer")
        self.assertEqual(metrics[1].field, "DynamicHeader")
        self.assertEqual(metrics[1].role, "Conditional Title")
        self.assertEqual(metrics[1].model_key, "Customer[DynamicHeader]")

        # Case 3: Title formatted as [StandaloneMeasure]
        parser._ensure_conditional_title_metric("[StandaloneMeasure]", metrics)
        self.assertEqual(len(metrics), 3)
        self.assertEqual(metrics[2].field, "StandaloneMeasure")
        self.assertEqual(metrics[2].role, "Conditional Title")


if __name__ == "__main__":
    unittest.main()



