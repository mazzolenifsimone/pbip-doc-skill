"""
Unit tests for PBIP Multi-Artifact Workspace Documentation Generation.
Tests full catalog generation, lineage matrix, and relative link resolution across models and reports.
"""

import os
import tempfile
import unittest
from pathlib import Path

from html import escape
from pbip_doc.codebase_scanner import CodebaseScanner
from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.utils import sanitize_filename
from pbip_doc.docgen.workspace_engine import WorkspaceDocGenerator


class TestWorkspaceDocGenerator(unittest.TestCase):

    def setUp(self):
        self.samples_dir = Path(__file__).resolve().parent.parent / "samples"
        self.scanner = CodebaseScanner(self.samples_dir)
        self.scan_result = self.scanner.scan(populate_symbols=True)
        self.config = DocGenConfig()

    def test_generate_workspace_markdown_documents(self):
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_markdown_documents(self.scan_result)

        # 1. Root Master Catalog
        self.assertIn("README.md", docs)
        root_content = docs["README.md"]
        self.assertIn("Workspace Documentation Catalog", root_content)
        self.assertIn("Data Lineage & Dependency Matrix", root_content)
        self.assertIn("Semantic Models Inventory", root_content)
        self.assertIn("Reports Inventory", root_content)

        # Verify lineage entries
        self.assertIn("AdventureWorks Sales", root_content)
        self.assertIn("Competitive Marketing Analysis", root_content)

        # 2. Model Markdowns
        # Should have models/AdventureWorks_Sales/README.md
        self.assertIn("models/AdventureWorks_Sales/README.md", docs)
        aw_model_index = docs["models/AdventureWorks_Sales/README.md"]
        self.assertIn("Semantic Model Documentation", aw_model_index)

        # Tables should be in models/AdventureWorks_Sales/tables/
        aw_tables = [p for p in docs if p.startswith("models/AdventureWorks_Sales/tables/")]
        self.assertGreater(len(aw_tables), 0)

        # Measures should be in models/AdventureWorks_Sales/measures/
        aw_measures = [p for p in docs if p.startswith("models/AdventureWorks_Sales/measures/")]
        self.assertGreater(len(aw_measures), 0)

        # 3. Report Markdowns
        # Should have reports/AdventureWorks_Sales/README.md
        self.assertIn("reports/AdventureWorks_Sales/README.md", docs)
        aw_rep_index = docs["reports/AdventureWorks_Sales/README.md"]
        self.assertIn("Report Identity & Dataset Binding", aw_rep_index)
        self.assertIn("../../models/AdventureWorks_Sales/README.md", aw_rep_index)

        # Visual pages
        aw_visuals = [p for p in docs if p.startswith("reports/AdventureWorks_Sales/visuals/") and p.endswith(".md")]
        self.assertGreater(len(aw_visuals), 0)

    def test_generate_workspace_html_documents(self):
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_html_documents(self.scan_result)

        # 1. Root Master Portal
        self.assertIn("index.html", docs)
        root_html = docs["index.html"]
        self.assertIn("PBIP Enterprise Workspace", root_html)
        self.assertIn("Data Lineage Matrix", root_html)
        self.assertIn("Semantic Models", root_html)
        self.assertIn("Reports", root_html)

        # 2. Centralized Static Assets (Zero dependency, pure CSS, no JS)
        self.assertIn("assets/style.css", docs)
        self.assertNotIn("assets/app.js", docs)
        self.assertNotIn("assets/search_index.js", docs)
        self.assertNotIn("<script", root_html)

        # 3. Model HTML pages
        self.assertIn("models/AdventureWorks_Sales/index.html", docs)
        aw_tables_html = [p for p in docs if p.startswith("models/AdventureWorks_Sales/tables/") and p.endswith(".html")]
        self.assertGreater(len(aw_tables_html), 0)

        # 4. Report HTML pages
        self.assertIn("reports/AdventureWorks_Sales/index.html", docs)
        aw_rep_html = docs["reports/AdventureWorks_Sales/index.html"]
        self.assertIn("Report Overview", aw_rep_html)
        self.assertIn("models/AdventureWorks_Sales/index.html", aw_rep_html)

        # 5. Table exclusions in sidebar and documents adhere to configuration
        for m_id, model in self.scan_result.models.items():
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            for tbl in model.tables:
                clean_t = sanitize_filename(tbl)
                tbl_rel = f"models/{sanitize_filename(model.name)}/tables/{clean_t}.html"
                if scoped_cfg.is_table_excluded(tbl):
                    self.assertNotIn(tbl_rel, docs, f"Excluded table {tbl} must not have document")
                    self.assertNotIn(f">{escape(tbl)}<", root_html, f"Excluded table {tbl} must not appear in sidebar")
                else:
                    self.assertIn(tbl_rel, docs, f"Non-excluded table {tbl} must have document")

    def test_write_to_directory_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceDocGenerator(self.config)
            results = generator.write_to_directory(self.scan_result, tmpdir, output_format="both")

            md_files = results["markdown"]
            html_files = results["html"]

            self.assertGreater(len(md_files), 10)
            self.assertGreater(len(html_files), 10)

            # Check files exist on disk
            self.assertTrue((Path(tmpdir) / "markdown" / "README.md").is_file())
            self.assertTrue((Path(tmpdir) / "markdown" / "models" / "AdventureWorks_Sales" / "README.md").is_file())
            self.assertTrue((Path(tmpdir) / "markdown" / "reports" / "AdventureWorks_Sales" / "README.md").is_file())

            self.assertTrue((Path(tmpdir) / "html" / "index.html").is_file())
            self.assertTrue((Path(tmpdir) / "html" / "assets" / "style.css").is_file())
            self.assertFalse((Path(tmpdir) / "html" / "assets" / "app.js").exists())
            self.assertFalse((Path(tmpdir) / "html" / "assets" / "search_index.js").exists())
            self.assertTrue((Path(tmpdir) / "html" / "models" / "AdventureWorks_Sales" / "index.html").is_file())
            self.assertTrue((Path(tmpdir) / "html" / "reports" / "AdventureWorks_Sales" / "index.html").is_file())

            # Verify on disk that tables declared excludable by configuration are absent
            for m_id, model in self.scan_result.models.items():
                scoped_cfg = self.config.get_scoped_config(model.artifact_id)
                for tbl in model.tables:
                    clean_t = sanitize_filename(tbl)
                    tbl_file = Path(tmpdir) / "html" / "models" / sanitize_filename(model.name) / "tables" / f"{clean_t}.html"
                    if scoped_cfg.is_table_excluded(tbl):
                        self.assertFalse(tbl_file.exists(), f"Excluded table {tbl} must not exist on disk")
                    else:
                        self.assertTrue(tbl_file.is_file(), f"Active table {tbl} must exist on disk")

    def test_configurable_table_exclusions(self):
        """
        Verifies that tables declared excludable via configuration
        (either by explicit name or regex pattern) are dynamically excluded
        from the sidebar navigation tree, workspace index, and generated documents,
        while non-excluded tables are preserved.
        """
        custom_config = DocGenConfig(
            excluded_tables=["Customer", "Products"],
            excluded_table_patterns=["^Sales Territory$"],
        )

        scanner = CodebaseScanner(self.samples_dir, config=custom_config)
        scan_result = scanner.scan(populate_symbols=True)

        generator = WorkspaceDocGenerator(custom_config)
        docs = generator.generate_all_html_documents(scan_result)
        root_html = docs["index.html"]

        # 1. Configured exclusions must be excluded from navigation and documents
        for ex_table in ["Customer", "Products", "Sales Territory"]:
            self.assertTrue(custom_config.is_table_excluded(ex_table))
            clean_ex = sanitize_filename(ex_table)
            matching_docs = [p for p in docs if p.endswith(f"/tables/{clean_ex}.html")]
            self.assertEqual(len(matching_docs), 0, f"No document should be generated for excluded table {ex_table}")
            self.assertNotIn(f"/tables/{clean_ex}.html", root_html, f"Excluded table {ex_table} must not be in sidebar links")

        # 2. Non-excluded tables must be preserved in navigation and documents
        for active_table in ["Category", "Reseller", "Date", "Sales"]:
            self.assertFalse(custom_config.is_table_excluded(active_table))
            clean_active = sanitize_filename(active_table)
            matching_docs = [p for p in docs if p.endswith(f"/tables/{clean_active}.html")]
            self.assertGreater(len(matching_docs), 0, f"Document should be generated for active table {active_table}")
            self.assertIn(f"/tables/{clean_active}.html", root_html, f"Active table {active_table} must be in sidebar links")


if __name__ == "__main__":
    unittest.main()
