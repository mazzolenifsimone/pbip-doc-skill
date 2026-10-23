"""
Unit tests for PBIP CodebaseScanner & Workspace Lineage Discovery.
"""

import os
import tempfile
import unittest
from pathlib import Path

from pbip_doc.codebase_scanner import CodebaseScanner, WorkspaceScanResult
from pbip_doc.docgen.config import DocGenConfig


class TestCodebaseScanner(unittest.TestCase):

    def setUp(self):
        self.samples_dir = Path(__file__).resolve().parent.parent / "samples"

    def test_scan_samples_workspace(self):
        scanner = CodebaseScanner(self.samples_dir)
        result = scanner.scan(populate_symbols=True)

        # Check models discovered
        # Expected: AdventureWorks Sales, Competitive Marketing Analysis, Artificial Intelligence Sample, retail_sales_bim
        self.assertGreaterEqual(len(result.models), 4)
        aw_model = result.get_model("AdventureWorks_Sales")
        self.assertIsNotNone(aw_model, "AdventureWorks_Sales model should be discovered")
        cma_model = result.get_model("Competitive_Marketing_Analysis")
        self.assertIsNotNone(cma_model, "Competitive_Marketing_Analysis model should be discovered")
        bim_model = result.get_model("retail_sales_bim")
        self.assertIsNotNone(bim_model, "retail_sales_bim standalone model should be discovered")

        # Check reports discovered
        self.assertGreaterEqual(len(result.reports), 3)
        aw_report = result.get_report("AdventureWorks_Sales")
        self.assertIsNotNone(aw_report, "AdventureWorks_Sales report should be discovered")
        cma_report = result.get_report("Competitive_Marketing_Analysis")
        self.assertIsNotNone(cma_report, "Competitive_Marketing_Analysis report should be discovered")

        # Check lineage bindings
        self.assertFalse(aw_report.is_external_model)
        self.assertEqual(aw_report.bound_model_name, aw_model.name)
        self.assertIn(aw_report.artifact_id, aw_model.bound_reports)

        self.assertFalse(cma_report.is_external_model)
        self.assertEqual(cma_report.bound_model_name, cma_model.name)
        self.assertIn(cma_report.artifact_id, cma_model.bound_reports)

        # Check symbol lookup
        sales_matches = result.find_measure("Sales by Order Date")
        self.assertGreaterEqual(len(sales_matches), 1)
        found_aw = any(m[0].name == aw_model.name for m in sales_matches)
        self.assertTrue(found_aw, "Should find Sales by Order Date in AdventureWorks_Sales model")

        # Check measure in CMA
        revenue_matches = result.find_measure("Revenue")
        self.assertGreaterEqual(len(revenue_matches), 1)
        found_cma = any(m[0].name == cma_model.name for m in revenue_matches)
        self.assertTrue(found_cma, "Should find Revenue in Competitive_Marketing_Analysis model")

        # Check table lookup
        tbl_matches = result.find_table("Customer")
        self.assertGreaterEqual(len(tbl_matches), 1)

    def test_scan_single_artifact_direct_target(self):
        # Scan just the AdventureWorks SemanticModel folder directly
        aw_model_dir = self.samples_dir / "AdventureWorks_Sales" / "AdventureWorks Sales.SemanticModel"
        scanner = CodebaseScanner(aw_model_dir)
        result = scanner.scan(populate_symbols=True)

        self.assertEqual(len(result.models), 1)
        self.assertTrue(result.is_single_artifact())

    def test_external_dataset_thin_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            report_dir = tmp_path / "Finance.Report"
            report_dir.mkdir()
            def_dir = report_dir / "definition"
            def_dir.mkdir()

            # definition.pbir with byConnection to remote Fabric dataset
            pbir_content = """{
  "version": "4.0",
  "datasetReference": {
    "byConnection": {
      "connectionString": "Data Source=powerbi://api.powerbi.com/v1.0/myorg/CorpWorkspace;Initial Catalog=EnterpriseGL;Integrated Security=ClaimsToken",
      "pbiModelDatabaseName": "EnterpriseGL"
    }
  }
}"""
            (def_dir / "definition.pbir").write_text(pbir_content, encoding="utf-8")
            (def_dir / "report.json").write_text('{"sections": []}', encoding="utf-8")

            scanner = CodebaseScanner(tmp_path)
            result = scanner.scan(populate_symbols=False)

            self.assertEqual(len(result.reports), 1)
            report = result.get_report("Finance")
            self.assertIsNotNone(report)
            self.assertTrue(report.is_external_model)
            self.assertEqual(report.bound_model_name, "EnterpriseGL")

    def test_scanner_respects_configuration_exclusions(self):
        """
        Verifies that CodebaseScanner dynamically excludes tables and their measures
        strictly based on what is declared in configuration (excluded_tables or patterns),
        without hardcoding specific table names.
        """
        custom_cfg = DocGenConfig(
            excluded_tables=["Customer", "Products"],
            excluded_table_patterns=["^Sales Territory$"],
        )
        scanner = CodebaseScanner(self.samples_dir, config=custom_cfg)
        result = scanner.scan(populate_symbols=True)

        aw_model = result.get_model("AdventureWorks_Sales")
        self.assertIsNotNone(aw_model)

        # Configured exclusions must not be in model.tables
        self.assertNotIn("Customer", aw_model.tables)
        self.assertNotIn("Sales Territory", aw_model.tables)

        # Non-excluded tables must be present
        self.assertIn("Category", aw_model.tables)
        self.assertIn("Sales", aw_model.tables)

        # find_table should not find excluded tables
        self.assertEqual(len(result.find_table("Customer")), 0)
        self.assertGreater(len(result.find_table("Category")), 0)


if __name__ == "__main__":
    unittest.main()
