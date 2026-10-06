"""
Unit tests for pbip_doc package.
Vanilla Python unittest suite.
"""

import unittest
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pbip_doc.parser import PBIPParser
from pbip_doc.m_lineage import MLineageResolver
from pbip_doc.star_schema import StarSchemaResolver
from pbip_doc.measure_analyzer import MeasureDependencyResolver
from pbip_doc.model_schema import PBIPSemanticModel, TableDefinition, ColumnDefinition, RelationshipDefinition, MeasureDefinition, TableRole, TableRoleClassification
from pbip_doc.docgen import MarkdownDocGenerator, DocGenConfig


class TestMarkdownDocGenerator(unittest.TestCase):
    def test_generate_table_and_measure_docs(self):
        sample_model = {
            "model_name": "TestModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "FactOrders",
                    "role": "FACT",
                    "classification_reasoning": {"criteria_matched": ["Many-side endpoint"], "confidence_score": 0.95},
                    "columns": [
                        {"name": "OrderID", "data_type": "int64", "is_key": True},
                        {"name": "Amount", "data_type": "decimal"},
                    ],
                    "connected_dimensions": ["DimCustomer"],
                    "reachable_lookup_tables": [],
                    "root_data_sources": [{"source_type": "SQL_SERVER", "connection_string": "sql.server.net"}],
                    "upstream_queries_chain": [],
                }
            ],
            "measures": [
                {
                    "name": "Total Sales",
                    "table": "FactOrders",
                    "dax_expression": "SUM(FactOrders[Amount])",
                    "format_string": "$#,0.00",
                    "calculation_depth": 0,
                    "direct_measure_dependencies": [],
                    "all_upstream_measures": [],
                    "downstream_measures": ["Margin"],
                    "referenced_columns": [{"table": "FactOrders", "column": "Amount"}],
                }
            ],
            "relationships": [],
            "data_sources_summary": [{"source_type": "SQL_SERVER", "connection_string": "sql.server.net"}],
        }

        generator = MarkdownDocGenerator()
        docs = generator.generate_all_documents(sample_model)

        self.assertIn("INDEX.md", docs)
        self.assertIn("tables/FactOrders.md", docs)
        self.assertIn("measures/FactOrders/Total_Sales.md", docs)

        fact_doc = docs["tables/FactOrders.md"]
        self.assertTrue(fact_doc.startswith("---"))
        self.assertIn("doc_type: data_model_table", fact_doc)
        self.assertIn("role: FACT", fact_doc)
        self.assertIn("# Table: `FactOrders`", fact_doc)
        self.assertIn("Columns Data Dictionary", fact_doc)
        # Verify the measures chapter in fact_doc contains the cross-link without error
        self.assertIn("[Total Sales](../measures/FactOrders/Total_Sales.md)", fact_doc)

        measure_doc = docs["measures/FactOrders/Total_Sales.md"]
        self.assertTrue(measure_doc.startswith("---"))
        self.assertIn("doc_type: dax_measure", measure_doc)
        self.assertIn("calculation_depth: 0", measure_doc)
        self.assertIn("```dax", measure_doc)
        self.assertIn("SUM(FactOrders[Amount])", measure_doc)
        self.assertIn("## 6. Semantic Context for AI & RAG", measure_doc)


class TestMLineage(unittest.TestCase):
    def test_multi_hop_m_lineage(self):
        raw_queries = {
            "Raw_Source": {
                "m_code": 'let Source = Sql.Database("prod-sql.server.net", "FinanceDB") in Source',
                "target_table": None,
                "is_staging": True,
            },
            "Staging_Invoices": {
                "m_code": 'let Source = #"Raw_Source", Cleaned = Table.SelectRows(Source, each [Amount] > 0) in Cleaned',
                "target_table": None,
                "is_staging": True,
            },
            "FactInvoices": {
                "m_code": 'let Source = #"Staging_Invoices" in Source',
                "target_table": "FactInvoices",
                "is_staging": False,
            },
        }

        resolver = MLineageResolver(raw_queries)
        fact_node = resolver.get_lineage_for_table("FactInvoices")

        self.assertIsNotNone(fact_node)
        self.assertIn("Staging_Invoices", fact_node.direct_dependencies)
        self.assertIn("Raw_Source", fact_node.all_upstream_queries)
        self.assertIn("Staging_Invoices", fact_node.all_upstream_queries)
        self.assertEqual(len(fact_node.root_sources), 1)
        self.assertEqual(fact_node.root_sources[0].source_type, "SQL_SERVER")
        self.assertEqual(fact_node.root_sources[0].database, "FinanceDB")

    def test_postgresql_not_duplicated_as_sql_server(self):
        raw_queries = {
            "Staging_Postgres": {
                "m_code": 'let Source = PostgreSQL.Database("pg-server:5432", "production_db") in Source',
                "target_table": None,
                "is_staging": True,
            },
            "FactOrders": {
                "m_code": 'let Source = #"Staging_Postgres" in Source',
                "target_table": "FactOrders",
                "is_staging": False,
            },
        }

        resolver = MLineageResolver(raw_queries)
        fact_node = resolver.get_lineage_for_table("FactOrders")

        self.assertIsNotNone(fact_node)
        # Verify it has exactly 1 root source, which is POSTGRESQL and NOT SQL_SERVER
        self.assertEqual(len(fact_node.root_sources), 1)
        self.assertEqual(fact_node.root_sources[0].source_type, "POSTGRESQL")
        self.assertEqual(fact_node.root_sources[0].server, "pg-server:5432")
        self.assertEqual(fact_node.root_sources[0].database, "production_db")

        # Verify model-wide root sources also only has 1 POSTGRESQL entry
        all_sources = resolver.get_all_root_sources()
        self.assertEqual(len(all_sources), 1)
        self.assertEqual(all_sources[0].source_type, "POSTGRESQL")
        self.assertEqual(all_sources[0].connection_string, "pg-server:5432 / production_db")

    def test_mysql_not_duplicated_as_sql_server(self):
        raw_queries = {
            "DimUsers": {
                "m_code": 'let Source = MySQL.Database("mysql.server.net", "users_db") in Source',
                "target_table": "DimUsers",
                "is_staging": False,
            },
        }
        resolver = MLineageResolver(raw_queries)
        dim_node = resolver.get_lineage_for_table("DimUsers")
        self.assertIsNotNone(dim_node)
        self.assertEqual(len(dim_node.root_sources), 1)
        self.assertEqual(dim_node.root_sources[0].source_type, "MYSQL")
        self.assertEqual(dim_node.root_sources[0].server, "mysql.server.net")
        self.assertEqual(dim_node.root_sources[0].database, "users_db")


class TestStarSchemaAndOutriggers(unittest.TestCase):
    def test_fact_dim_lookup_snowflake_resolution(self):
        # Setup: FactSales -> DimCustomer -> DimGeography
        tables = [
            TableDefinition(
                name="FactSales",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="SalesKey", data_type="int64"),
                    ColumnDefinition(name="CustomerKey", data_type="int64"),
                    ColumnDefinition(name="Amount", data_type="decimal"),
                ],
            ),
            TableDefinition(
                name="DimCustomer",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="CustomerKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="GeographyKey", data_type="int64"),
                    ColumnDefinition(name="Name", data_type="string"),
                ],
            ),
            TableDefinition(
                name="DimGeography",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="GeographyKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="City", data_type="string"),
                    ColumnDefinition(name="Country", data_type="string"),
                ],
            ),
        ]

        relationships = [
            RelationshipDefinition(
                id="rel1",
                from_table="FactSales",
                from_column="CustomerKey",
                to_table="DimCustomer",
                to_column="CustomerKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
            RelationshipDefinition(
                id="rel2",
                from_table="DimCustomer",
                from_column="GeographyKey",
                to_table="DimGeography",
                to_column="GeographyKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
        ]

        resolver = StarSchemaResolver(tables, relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        fact_table = next(t for t in tables if t.name == "FactSales")
        dim_table = next(t for t in tables if t.name == "DimCustomer")
        geo_table = next(t for t in tables if t.name == "DimGeography")

        self.assertEqual(fact_table.role, TableRole.FACT)
        self.assertEqual(dim_table.role, TableRole.DIMENSION)
        self.assertEqual(geo_table.role, TableRole.LOOKUP_OUTRIGGER)

        self.assertIn("DimCustomer", fact_table.connected_dimensions)
        self.assertIn("DimGeography", fact_table.reachable_lookup_tables)
        self.assertEqual(len(fact_table.snowflake_paths), 1)
        self.assertEqual(fact_table.snowflake_paths[0].path, ["FactSales", "DimCustomer", "DimGeography"])

    def test_snowflake_with_multiple_lookups_and_no_dim_prefix(self):
        # Customers has 2 lookups (Geography and Status) and high numeric key density
        # In previous heuristic, Customers would be misclassified as FACT.
        tables = [
            TableDefinition(
                name="Transactions",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="TxKey", data_type="int64"),
                    ColumnDefinition(name="CustomerKey", data_type="int64"),
                    ColumnDefinition(name="Amount", data_type="decimal"),
                ],
            ),
            TableDefinition(
                name="Customers",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="CustomerKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="GeographyKey", data_type="int64"),
                    ColumnDefinition(name="StatusKey", data_type="int64"),
                    ColumnDefinition(name="Age", data_type="int64"),
                    ColumnDefinition(name="YearlyIncome", data_type="decimal"),
                    ColumnDefinition(name="FullName", data_type="string"),
                ],
            ),
            TableDefinition(
                name="Geography",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="GeographyKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="City", data_type="string"),
                    ColumnDefinition(name="Country", data_type="string"),
                ],
            ),
            TableDefinition(
                name="CustomerStatus",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="StatusKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="StatusDescription", data_type="string"),
                ],
            ),
        ]

        relationships = [
            RelationshipDefinition(
                id="rel1",
                from_table="Transactions",
                from_column="CustomerKey",
                to_table="Customers",
                to_column="CustomerKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
            RelationshipDefinition(
                id="rel2",
                from_table="Customers",
                from_column="GeographyKey",
                to_table="Geography",
                to_column="GeographyKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
            RelationshipDefinition(
                id="rel3",
                from_table="Customers",
                from_column="StatusKey",
                to_table="CustomerStatus",
                to_column="StatusKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
        ]

        resolver = StarSchemaResolver(tables, relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        tx_table = next(t for t in tables if t.name == "Transactions")
        cust_table = next(t for t in tables if t.name == "Customers")
        geo_table = next(t for t in tables if t.name == "Geography")
        status_table = next(t for t in tables if t.name == "CustomerStatus")

        self.assertEqual(tx_table.role, TableRole.FACT)
        self.assertEqual(cust_table.role, TableRole.DIMENSION)
        self.assertEqual(geo_table.role, TableRole.LOOKUP_OUTRIGGER)
        self.assertEqual(status_table.role, TableRole.LOOKUP_OUTRIGGER)

        self.assertIn("Customers", tx_table.connected_dimensions)
        self.assertIn("Geography", tx_table.reachable_lookup_tables)
        self.assertIn("CustomerStatus", tx_table.reachable_lookup_tables)

    def test_scd_mapping_bridge_table(self):
        # DimA[sk] --N:1-> [sk] BridgeAB [id] --1:N--> FactB[id]
        tables = [
            TableDefinition(
                name="DimA",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="sk", data_type="int64", is_key=True),
                    ColumnDefinition(name="Name", data_type="string"),
                    ColumnDefinition(name="VersionLabel", data_type="string"),
                ],
            ),
            TableDefinition(
                name="BridgeAB",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="sk", data_type="int64", is_key=True),
                    ColumnDefinition(name="id", data_type="int64", is_key=True),
                ],
            ),
            TableDefinition(
                name="FactB",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="id", data_type="int64"),
                    ColumnDefinition(name="Amount", data_type="decimal"),
                ],
            ),
        ]

        # DimA[sk] is Many, BridgeAB[sk] is One (with crossFilter: Both)
        # FactB[id] is Many, BridgeAB[id] is One
        relationships = [
            RelationshipDefinition(
                id="rel_dima_bridge",
                from_table="DimA",
                from_column="sk",
                to_table="BridgeAB",
                to_column="sk",
                cardinality="1:N",
                cross_filtering_behavior="Both",
            ),
            RelationshipDefinition(
                id="rel_factb_bridge",
                from_table="FactB",
                from_column="id",
                to_table="BridgeAB",
                to_column="id",
                cardinality="1:N",
                cross_filtering_behavior="Single",
            ),
        ]

        resolver = StarSchemaResolver(tables, relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        dima = next(t for t in tables if t.name == "DimA")
        bridge = next(t for t in tables if t.name == "BridgeAB")
        factb = next(t for t in tables if t.name == "FactB")

        self.assertEqual(bridge.role, TableRole.BRIDGE)
        self.assertEqual(factb.role, TableRole.FACT)
        self.assertEqual(dima.role, TableRole.DIMENSION)

        self.assertIn("BridgeAB", topology.bridge_tables)
        self.assertIn("FactB", topology.fact_tables)
        self.assertIn("DimA", topology.dimension_tables)
        self.assertIn("DimA", factb.connected_dimensions)

    def test_m2m_junction_bridge_table(self):
        tables = [
            TableDefinition(
                name="DimStudent",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="StudentID", data_type="int64", is_key=True),
                    ColumnDefinition(name="StudentName", data_type="string"),
                ],
            ),
            TableDefinition(
                name="StudentCourseBridge",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="StudentID", data_type="int64", is_key=True),
                    ColumnDefinition(name="CourseID", data_type="int64", is_key=True),
                ],
            ),
            TableDefinition(
                name="DimCourse",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="CourseID", data_type="int64", is_key=True),
                    ColumnDefinition(name="CourseName", data_type="string"),
                ],
            ),
        ]

        relationships = [
            RelationshipDefinition(
                id="rel_student",
                from_table="StudentCourseBridge",
                from_column="StudentID",
                to_table="DimStudent",
                to_column="StudentID",
                cardinality="1:N",
                cross_filtering_behavior="Both",
            ),
            RelationshipDefinition(
                id="rel_course",
                from_table="StudentCourseBridge",
                from_column="CourseID",
                to_table="DimCourse",
                to_column="CourseID",
                cardinality="1:N",
                cross_filtering_behavior="Both",
            ),
        ]

        resolver = StarSchemaResolver(tables, relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        bridge = next(t for t in tables if t.name == "StudentCourseBridge")
        student = next(t for t in tables if t.name == "DimStudent")
        course = next(t for t in tables if t.name == "DimCourse")

        self.assertEqual(bridge.role, TableRole.BRIDGE)
        self.assertEqual(student.role, TableRole.DIMENSION)
        self.assertEqual(course.role, TableRole.DIMENSION)
        self.assertIn("StudentCourseBridge", topology.bridge_tables)


class TestMeasureDAG(unittest.TestCase):
    def test_measure_dependency_dag(self):
        tables = [
            TableDefinition(
                name="FactSales",
                role=TableRole.FACT,
                classification_reasoning=None,
                columns=[ColumnDefinition(name="Amount", data_type="decimal")],
            )
        ]
        measures = [
            MeasureDefinition(
                name="Total Sales",
                table="FactSales",
                dax_expression="SUM(FactSales[Amount])",
            ),
            MeasureDefinition(
                name="Total Margin",
                table="FactSales",
                dax_expression="[Total Sales] * 0.2",
            ),
            MeasureDefinition(
                name="Margin Ratio",
                table="FactSales",
                dax_expression="DIVIDE([Total Margin], [Total Sales])",
            ),
        ]

        analyzer = MeasureDependencyResolver(measures, tables)
        dag = analyzer.analyze()

        m_sales = next(m for m in measures if m.name == "Total Sales")
        m_margin = next(m for m in measures if m.name == "Total Margin")
        m_ratio = next(m for m in measures if m.name == "Margin Ratio")

        self.assertEqual(m_sales.calculation_depth, 0)
        self.assertEqual(m_margin.calculation_depth, 1)
        self.assertEqual(m_ratio.calculation_depth, 2)

        self.assertEqual(m_margin.direct_measure_dependencies, ["Total Sales"])
        self.assertEqual(sorted(m_ratio.all_upstream_measures), ["Total Margin", "Total Sales"])
        self.assertIn("Total Margin", m_sales.downstream_measures)
        self.assertIn("Margin Ratio", m_sales.downstream_measures)


class TestCalculatedColumns(unittest.TestCase):
    def test_tmdl_calculated_column_parsing(self):
        tmdl_content = """
table DimProduct
\tlineageTag: 12345

\tcolumn ProductKey
\t\tdataType: int64
\t\tisKey

\tcolumn StandardCost
\t\tdataType: decimal

\tcolumn ListPrice
\t\tdataType: decimal

\tcolumn Margin = DimProduct[ListPrice] - DimProduct[StandardCost]
\t\tdataType: decimal
\t\tformatString: $#,0.00

\tcolumn MarginRate =
\t\tDIVIDE(
\t\t\tDimProduct[ListPrice] - DimProduct[StandardCost],
\t\t\tDimProduct[ListPrice],
\t\t\t0
\t\t)
\t\tdataType: double
\t\tformatString: 0.0%

\tcolumn 'Price Class' = IF(DimProduct[ListPrice] > 1000 || DimProduct[ListPrice] = 0, "Special", "Regular")
\t\tdataType: string
\t\tdescription: "Fascia prezzo calcolata"
"""
        parser = PBIPParser()
        table, _, _ = parser._parse_single_table_tmdl(tmdl_content, "DimProduct")

        cols_by_name = {c.name: c for c in table.columns}
        self.assertIn("Margin", cols_by_name)
        self.assertIn("MarginRate", cols_by_name)
        self.assertIn("Price Class", cols_by_name)

        # Margin: single line DAX
        c_margin = cols_by_name["Margin"]
        self.assertTrue(c_margin.is_calculated)
        self.assertIn("DimProduct[ListPrice] - DimProduct[StandardCost]", c_margin.expression)

        # MarginRate: multiline DAX
        c_rate = cols_by_name["MarginRate"]
        self.assertTrue(c_rate.is_calculated)
        self.assertIn("DIVIDE(", c_rate.expression)

        # Price Class: DAX with pipe operator ||
        c_class = cols_by_name["Price Class"]
        self.assertTrue(c_class.is_calculated)
        self.assertIn("||", c_class.expression)

    def test_calculated_column_markdown_rendering_safety(self):
        sample_model = {
            "model_name": "CalcModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "DimProduct",
                    "role": "DIMENSION",
                    "classification_reasoning": {"criteria_matched": [], "confidence_score": 1.0},
                    "columns": [
                        {"name": "ProductID", "data_type": "int64", "is_key": True},
                        {
                            "name": "Category_Group",
                            "data_type": "string",
                            "is_calculated": True,
                            "expression": "IF([Cat] = 'A' || [Cat] = 'B', 'Group 1', 'Group 2')",
                            "description": "Calculated with | pipe character",
                        },
                        {
                            "name": "Multiline_Calc",
                            "data_type": "double",
                            "is_calculated": True,
                            "expression": "DIVIDE(\n  [Sales],\n  [Cost]\n)",
                        },
                    ],
                    "connected_dimensions": [],
                    "connected_facts": [],
                    "reachable_lookup_tables": [],
                    "root_data_sources": [],
                    "upstream_queries_chain": [],
                }
            ],
            "measures": [],
            "relationships": [],
            "data_sources_summary": [],
        }

        generator = MarkdownDocGenerator()
        docs = generator.generate_all_documents(sample_model)
        prod_doc = docs["tables/DimProduct.md"]

        # 1. The main table row must NOT have unescaped pipes or unescaped newlines in table cells
        in_table = False
        for line in prod_doc.splitlines():
            if line.startswith("| Nome Colonna |"):
                in_table = True
                continue
            if in_table and line.startswith("| :---"):
                continue
            if in_table:
                if not line.startswith("|"):
                    in_table = False
                    continue
                # Split table row by unescaped pipe
                import re
                parts = [p.strip() for p in re.split(r'(?<!\\)\|', line) if p.strip()]
                self.assertEqual(len(parts), 5, f"Broken markdown table row: {line}")

        # 2. Must contain dedicated Section for calculated columns
        self.assertIn("### 5.1 Calculated Column DAX Formulas", prod_doc)
        self.assertIn("#### Calculated Column: `Category_Group`", prod_doc)
        self.assertIn("#### Calculated Column: `Multiline_Calc`", prod_doc)
        self.assertIn("```dax", prod_doc)


class TestTableExclusion(unittest.TestCase):
    def test_auto_date_tables_excluded_by_default(self):
        config = DocGenConfig(exclude_auto_date_tables=True)
        self.assertTrue(config.is_table_excluded("LocalDateTable_5f73d6e5-4eb8-4ca7"))
        self.assertTrue(config.is_table_excluded("DateTableTemplate_42e47e30-b3b3"))
        self.assertFalse(config.is_table_excluded("FactInternetSales"))
        self.assertFalse(config.is_table_excluded("DimCustomer"))
        self.assertFalse(config.is_table_excluded("DimDate"))

    def test_model_filter_purges_excluded_tables_and_dependencies(self):
        from pbip_doc.model_schema import PBIPSemanticModel, TableDefinition, RelationshipDefinition, MeasureDefinition, TableRole, TableRoleClassification

        tables = [
            TableDefinition(name="FactSales", role=TableRole.FACT, classification_reasoning=TableRoleClassification(TableRole.FACT, 1.0)),
            TableDefinition(name="DimCustomer", role=TableRole.DIMENSION, classification_reasoning=TableRoleClassification(TableRole.DIMENSION, 1.0)),
            TableDefinition(name="LocalDateTable_xyz123", role=TableRole.DATE_DIMENSION, classification_reasoning=TableRoleClassification(TableRole.DATE_DIMENSION, 1.0)),
        ]
        relationships = [
            RelationshipDefinition(id="r1", from_table="FactSales", from_column="CustKey", to_table="DimCustomer", to_column="CustKey", cardinality="1:N", cross_filtering_behavior="Single"),
            RelationshipDefinition(id="r2", from_table="FactSales", from_column="DateKey", to_table="LocalDateTable_xyz123", to_column="Date", cardinality="1:N", cross_filtering_behavior="Single"),
        ]
        measures = [
            MeasureDefinition(
                name="Total Sales",
                table="FactSales",
                dax_expression="SUM(FactSales[Amount])",
                referenced_tables=["FactSales", "LocalDateTable_xyz123"],
                referenced_columns=[{"table": "FactSales", "column": "Amount"}, {"table": "LocalDateTable_xyz123", "column": "Date"}],
            ),
            MeasureDefinition(
                name="Auto Measure",
                table="LocalDateTable_xyz123",
                dax_expression="COUNTROWS(LocalDateTable_xyz123)",
            ),
        ]

        model = PBIPSemanticModel(
            model_name="TestExclude",
            source_format="TMDL",
            tables=tables,
            relationships=relationships,
            measures=measures,
        )

        config = DocGenConfig(exclude_auto_date_tables=True)
        model.filter_excluded_tables(config.is_table_excluded)

        # Excluded table purged
        remaining_names = [t.name for t in model.tables]
        self.assertIn("FactSales", remaining_names)
        self.assertIn("DimCustomer", remaining_names)
        self.assertNotIn("LocalDateTable_xyz123", remaining_names)
        self.assertEqual(model.excluded_tables_count, 1)

        # Relationship pointing to excluded table purged
        self.assertEqual(len(model.relationships), 1)
        self.assertEqual(model.relationships[0].to_table, "DimCustomer")

        # Measure in excluded table purged
        remaining_measures = [m.name for m in model.measures]
        self.assertIn("Total Sales", remaining_measures)
        self.assertNotIn("Auto Measure", remaining_measures)

        # References to excluded table inside surviving measure purged
        m_sales = model.measures[0]
        self.assertNotIn("LocalDateTable_xyz123", m_sales.referenced_tables)
        self.assertEqual(len(m_sales.referenced_columns), 1)
        self.assertEqual(m_sales.referenced_columns[0]["table"], "FactSales")

    def test_parameter_table_connected_only_to_localdatetable_classified_as_utility(self):
        """
        Verify that when excluded tables are filtered according to configuration before
        estimating topology, a date parameter table (e.g. LastRefreshDate) has 0 active
        relationships and is correctly classified as PARAMETER_UTILITY (not FACT).
        """
        tables = [
            TableDefinition(
                name="LastRefreshDate",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[ColumnDefinition(name="LastRefresh", data_type="dateTime")],
            ),
            TableDefinition(
                name="LocalDateTable_a1b2c3-4d5e-6f7a",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="Date", data_type="dateTime", is_key=True),
                    ColumnDefinition(name="Year", data_type="int64"),
                    ColumnDefinition(name="Month", data_type="string"),
                    ColumnDefinition(name="Day", data_type="int64"),
                ],
            ),
        ]
        relationships = [
            RelationshipDefinition(
                id="r_auto_date",
                from_table="LastRefreshDate",
                from_column="LastRefresh",
                to_table="LocalDateTable_a1b2c3-4d5e-6f7a",
                to_column="Date",
                cardinality="1:N",
                cross_filtering_behavior="Single",
                is_active=True,
            ),
        ]

        config = DocGenConfig(exclude_auto_date_tables=True)

        # 1. Filter excluded tables according to configuration first
        filtered_tables = [t for t in tables if not config.is_table_excluded(t.name)]
        filtered_relationships = [
            r for r in relationships
            if not config.is_table_excluded(r.from_table) and not config.is_table_excluded(r.to_table)
        ]

        # 2. Then estimate topology on filtered in-scope tables & relationships
        resolver = StarSchemaResolver(filtered_tables, filtered_relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        refresh_tbl = next(t for t in filtered_tables if t.name == "LastRefreshDate")
        self.assertEqual(refresh_tbl.role, TableRole.PARAMETER_UTILITY)
        self.assertEqual(refresh_tbl.classification_reasoning.confidence_score, 0.95)
        self.assertIn("Disconnected table with 0 active relationships", refresh_tbl.classification_reasoning.criteria_matched[0])
        self.assertEqual(refresh_tbl.connected_dimensions, [])
        self.assertEqual(refresh_tbl.direct_related_tables, [])
        self.assertNotIn("LastRefreshDate", topology.fact_tables)
        self.assertIn("LastRefreshDate", topology.utility_tables)

        # 3. Test model filter_excluded_tables recalculation
        model = PBIPSemanticModel(
            model_name="TestParamModel",
            source_format="TMDL",
            tables=tables,
            relationships=relationships,
        )
        model.filter_excluded_tables(config.is_table_excluded)

        self.assertEqual(len(model.tables), 1)
        self.assertEqual(model.tables[0].name, "LastRefreshDate")
        self.assertEqual(model.tables[0].role, TableRole.PARAMETER_UTILITY)
        self.assertEqual(model.star_schema.fact_tables, [])
        self.assertEqual(model.star_schema.utility_tables, ["LastRefreshDate"])

    def test_full_model_parse_with_parameter_table_and_localdatetable(self):
        """
        Verify end-to-end model parsing with PBIPParser filters excluded tables
        before estimating topology, accurately classifying the date parameter table as PARAMETER_UTILITY.
        """
        bim_data = {
            "model": {
                "tables": [
                    {
                        "name": "RefreshTimestamp",
                        "columns": [{"name": "LastRefreshed", "dataType": "dateTime"}],
                    },
                    {
                        "name": "LocalDateTable_77777777",
                        "columns": [{"name": "Date", "dataType": "dateTime"}],
                    },
                ],
                "relationships": [
                    {
                        "name": "rel_refresh_auto",
                        "fromTable": "RefreshTimestamp",
                        "fromColumn": "LastRefreshed",
                        "toTable": "LocalDateTable_77777777",
                        "toColumn": "Date",
                        "cardinality": "1:N",
                    }
                ],
            }
        }

        parser = PBIPParser(config=DocGenConfig(exclude_auto_date_tables=True))
        model = parser.parse_bim_dict(bim_data, model_name="TestBimModel")

        table_names = [t.name for t in model.tables]
        self.assertEqual(table_names, ["RefreshTimestamp"])
        self.assertNotIn("LocalDateTable_77777777", table_names)
        self.assertEqual(model.excluded_tables_count, 1)
        self.assertIn("LocalDateTable_77777777", model.excluded_tables_list)

        refresh_table = model.tables[0]
        self.assertEqual(refresh_table.role, TableRole.PARAMETER_UTILITY)
        self.assertEqual(refresh_table.classification_reasoning.confidence_score, 0.95)
        self.assertEqual(model.star_schema.fact_tables, [])
        self.assertEqual(model.star_schema.utility_tables, ["RefreshTimestamp"])

    def test_out_of_scope_inherited_tables_remain_in_topology_and_references(self):
        """
        Verify that out_of_scope tables (e.g. inherited composite model entities) are NOT excluded
        from model topology or relational references. They must participate fully in StarSchemaResolver.
        """
        tables = [
            TableDefinition(
                name="FactSales",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                columns=[
                    ColumnDefinition(name="SalesKey", data_type="int64"),
                    ColumnDefinition(name="CustomerKey", data_type="int64"),
                    ColumnDefinition(name="Amount", data_type="decimal"),
                ],
            ),
            TableDefinition(
                name="DimCustomer",
                role=TableRole.UNKNOWN,
                classification_reasoning=None,
                is_inherited=True,
                out_of_scope=True,  # out_of_scope is True, but NOT in excluded_tables
                columns=[
                    ColumnDefinition(name="CustomerKey", data_type="int64", is_key=True),
                    ColumnDefinition(name="Name", data_type="string"),
                ],
            ),
        ]
        relationships = [
            RelationshipDefinition(
                id="r_fact_dim",
                from_table="FactSales",
                from_column="CustomerKey",
                to_table="DimCustomer",
                to_column="CustomerKey",
                cardinality="1:N",
                cross_filtering_behavior="Single",
                is_active=True,
            ),
        ]

        # Topology resolver executes with both tables present
        resolver = StarSchemaResolver(tables, relationships)
        resolver.classify_tables()
        topology = resolver.resolve_topology_and_snowflakes()

        fact = next(t for t in tables if t.name == "FactSales")
        dim = next(t for t in tables if t.name == "DimCustomer")

        # Topology roles are resolved accurately
        self.assertEqual(fact.role, TableRole.FACT)
        self.assertEqual(dim.role, TableRole.DIMENSION)

        # Relational references are preserved
        self.assertIn("DimCustomer", fact.connected_dimensions)
        self.assertIn("FactSales", dim.connected_facts)
        self.assertIn("FactSales", topology.fact_tables)
        self.assertIn("DimCustomer", topology.dimension_tables)
        self.assertTrue(dim.out_of_scope)


class TestTMDLRelationshipNormalization(unittest.TestCase):
    def test_tmdl_from_cardinality_one_normalization(self):
        tmdl_content = """
relationship rel1
\tfromColumn: DimCustomer.CustomerKey
\ttoColumn: FactSales.CustomerKey
\tfromCardinality: one
\ttoCardinality: many
\tcrossFilteringBehavior: both
"""
        parser = PBIPParser()
        rels = parser._parse_tmdl_relationships(tmdl_content)
        self.assertEqual(len(rels), 1)
        r = rels[0]
        # Verified that it normalized: FactSales is from_table (Many) and DimCustomer is to_table (One)
        self.assertEqual(r.from_table, "FactSales")
        self.assertEqual(r.to_table, "DimCustomer")
        self.assertEqual(r.cardinality, "1:N")
        self.assertEqual(r.cross_filtering_behavior, "both")


class TestIncrementalRefreshPolicy(unittest.TestCase):
    def test_parse_tmdl_incremental_refresh_block(self):
        tmdl_content = """
table FactSales
\tlineageTag: 12345

\trefreshPolicy
\t\tpolicyType: basic
\t\tmode: hybrid
\t\trollingWindowPeriods: 3
\t\trollingWindowGranularity: year
\t\tincrementalPeriods: 14
\t\tincrementalGranularity: day
\t\tpollingExpression: let MaxDate = ... in MaxDate
\t\tsourceExpression: let Source = ... in Source

\tcolumn OrderDate
\t\tdataType: dateTime
"""
        parser = PBIPParser()
        policy = parser._parse_tmdl_refresh_policy(tmdl_content)
        self.assertIsNotNone(policy)
        self.assertTrue(policy.is_enabled)
        self.assertEqual(policy.policy_type, "basic")
        self.assertEqual(policy.mode, "hybrid")
        self.assertEqual(policy.rolling_window_periods, 3)
        self.assertEqual(policy.rolling_window_granularity, "year")
        self.assertEqual(policy.incremental_periods, 14)
        self.assertEqual(policy.incremental_granularity, "day")
        self.assertEqual(policy.polling_expression, "let MaxDate = ... in MaxDate")
        self.assertEqual(policy.source_expression, "let Source = ... in Source")

    def test_parse_tmdl_incremental_refresh_json(self):
        tmdl_content = """
table FactSales
\trefreshPolicy = {"policyType":"basic","mode":"import","rollingWindowPeriods":5,"rollingWindowGranularity":"year","incrementalPeriods":7,"incrementalGranularity":"day"}
"""
        parser = PBIPParser()
        policy = parser._parse_tmdl_refresh_policy(tmdl_content)
        self.assertIsNotNone(policy)
        self.assertTrue(policy.is_enabled)
        self.assertEqual(policy.rolling_window_periods, 5)
        self.assertEqual(policy.incremental_periods, 7)
        self.assertEqual(policy.mode, "import")

    def test_table_doc_with_incremental_refresh(self):
        from pbip_doc.docgen.table_doc import TableDocBuilder
        table_data = {
            "name": "FactOrders",
            "role": "FACT",
            "classification_reasoning": {"confidence_score": 1.0, "criteria_matched": ["Pure Fact Sink"]},
            "columns": [{"name": "ID", "data_type": "int64"}],
            "incremental_refresh_policy": {
                "is_enabled": True,
                "policy_type": "basic",
                "mode": "hybrid",
                "rolling_window_periods": 3,
                "rolling_window_granularity": "year",
                "incremental_periods": 7,
                "incremental_granularity": "day",
                "polling_expression": "let Check = ... in Check",
                "source_expression": "let Range = ... in Range",
            },
        }
        full_model = {"tables": [table_data], "measures": [], "relationships": []}
        builder = TableDocBuilder(table_data, full_model)
        md = builder.build_markdown()

        self.assertIn("has_incremental_refresh: true", md)
        self.assertIn("hybrid_table", md)
        self.assertIn("## 4. Incremental Refresh Policy", md)
        self.assertIn("⚡ Hybrid (Import + DirectQuery)", md)
        self.assertIn("3 Years", md)
        self.assertIn("7 Days", md)
        self.assertIn("let Check = ... in Check", md)
        self.assertIn("## 5. Columns Data Dictionary", md)

    def test_table_doc_without_incremental_refresh(self):
        from pbip_doc.docgen.table_doc import TableDocBuilder
        table_data = {
            "name": "DimCustomer",
            "role": "DIMENSION",
            "classification_reasoning": {"confidence_score": 1.0},
            "columns": [{"name": "CustID", "data_type": "int64"}],
            "incremental_refresh_policy": None,
        }
        full_model = {"tables": [table_data], "measures": [], "relationships": []}
        builder = TableDocBuilder(table_data, full_model)
        md = builder.build_markdown()

        self.assertIn("has_incremental_refresh: false", md)
        self.assertIn("## 4. Incremental Refresh Policy", md)
        self.assertIn("No Incremental Refresh Configured", md)


class TestMInlineTableParser(unittest.TestCase):
    def test_parse_typed_inline_table(self):
        from pbip_doc.m_table_parser import parse_m_inline_table
        m_code = """
let
    Source = #table(
        type table [ID = Int64.Type, #"Status Name" = text, IsActive = logical],
        {
            {1, "Active", true},
            {2, "Pending", true},
            {3, "Archived", false}
        }
    )
in
    Source
"""
        tbl = parse_m_inline_table(m_code)
        self.assertIsNotNone(tbl)
        self.assertEqual(tbl.column_count, 3)
        self.assertEqual(tbl.row_count, 3)
        self.assertEqual(tbl.columns, ["ID", "Status Name", "IsActive"])
        self.assertEqual(tbl.column_types["ID"], "Int64.Type")
        self.assertEqual(tbl.column_types["Status Name"], "text")
        self.assertEqual(tbl.rows[0], ["1", "Active", "true"])
        self.assertEqual(tbl.rows[2], ["3", "Archived", "false"])

        md = tbl.to_markdown_table()
        self.assertIn("`ID`", md)
        self.assertIn("*Int64.Type*", md)
        self.assertIn("| 1 | Active | true |", md)

    def test_parse_untyped_inline_table_with_commas_in_strings(self):
        from pbip_doc.m_table_parser import parse_m_inline_table
        m_code = '#table({"City", "Country"}, {{"Milan, Lombardy", "Italy"}, {"Paris", "France"}})'
        tbl = parse_m_inline_table(m_code)
        self.assertIsNotNone(tbl)
        self.assertEqual(tbl.columns, ["City", "Country"])
        self.assertEqual(tbl.rows[0], ["Milan, Lombardy", "Italy"])
        self.assertEqual(tbl.rows[1], ["Paris", "France"])


class TestExpressionDocGen(unittest.TestCase):
    def test_generate_expression_doc(self):
        from pbip_doc.docgen.expression_doc import ExpressionDocBuilder
        expr_data = {
            "query_name": "StatusLookup",
            "is_staging": True,
            "full_m_expression": '#table(type table [Code = text, Label = text], {{"A", "Alpha"}, {"B", "Beta"}})',
            "steps": [],
            "direct_dependencies": [],
            "all_upstream_queries": [],
            "downstream_queries": [],
            "downstream_tables": ["FactOrders"],
            "root_sources": [],
            "is_inline_table": True,
            "inline_table_columns": ["Code", "Label"],
            "inline_table_column_types": {"Code": "text", "Label": "text"},
            "inline_table_rows": [["A", "Alpha"], ["B", "Beta"]],
            "inline_table_markdown": "| `Code` | `Label` |\n| :--- | :--- |\n| A | Alpha |\n| B | Beta |",
        }
        full_model = {"tables": [{"name": "FactOrders"}], "measures": [], "expressions": [expr_data]}
        builder = ExpressionDocBuilder(expr_data, full_model)
        md = builder.build_markdown()

        self.assertIn("doc_type: power_query_expression", md)
        self.assertIn("expression_type: INLINE_TABLE", md)
        self.assertIn("## 2. Inline Table Definition (`#table`)", md)
        self.assertIn("| `Code` | `Label` |", md)
        self.assertIn("| A | Alpha |", md)
        self.assertIn("FactOrders", md)

    def test_markdown_doc_generator_with_expressions(self):
        sample_model = {
            "model_name": "TestModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "FactOrders",
                    "role": "FACT",
                    "classification_reasoning": {"confidence_score": 1.0},
                    "columns": [{"name": "ID", "data_type": "int64"}],
                }
            ],
            "measures": [],
            "expressions": [
                {
                    "query_name": "Staging_Orders",
                    "is_staging": True,
                    "full_m_expression": 'let Source = Sql.Database("srv", "db") in Source',
                    "steps": [{"step_name": "Source", "operation": "Source Connection", "referenced_queries": []}],
                    "direct_dependencies": [],
                    "all_upstream_queries": [],
                    "downstream_queries": [],
                    "downstream_tables": ["FactOrders"],
                    "root_sources": [{"source_type": "SQL_SERVER", "connection_string": "srv/db"}],
                }
            ],
        }
        generator = MarkdownDocGenerator()
        docs = generator.generate_all_documents(sample_model)

        self.assertIn("INDEX.md", docs)
        self.assertIn("tables/FactOrders.md", docs)
        self.assertIn("expressions/Staging_Orders.md", docs)
        self.assertIn("## 4. Power Query Expressions & Shared ETL Queries", docs["INDEX.md"])
        self.assertIn("Staging_Orders", docs["INDEX.md"])


class TestInheritedEntitiesAndExternalMeasures(unittest.TestCase):
    def test_parse_entity_partition_and_external_measure_tmdl(self):
        parser = PBIPParser()
        tmdl_content = """table Customer
    lineageTag: cust-lineage-123

    partition Customer = entity
        mode: directQuery
        source
            entityName: DimCustomer
            expressionSource: DatabaseQuery

    column CustomerID
        dataType: int64

    column CustomerName
        dataType: string

    measure 'Total Sales' = EXTERNALMEASURE("Total Sales", DOUBLE, "DatabaseQuery")
        formatString: $#,0.00
        lineageTag: meas-ext-1

    measure 'Local KPI' = [Total Sales] * 1.1
        formatString: $#,0.00
        lineageTag: meas-local-2
"""
        table_def, measures, m_code = parser._parse_single_table_tmdl(tmdl_content, "Customer")

        # Table assertions
        self.assertTrue(table_def.is_inherited)
        self.assertTrue(table_def.out_of_scope)
        self.assertEqual(table_def.source_type, "InheritedEntity")
        self.assertEqual(table_def.inherited_entity_name, "DimCustomer")
        self.assertEqual(table_def.inherited_expression_source, "DatabaseQuery")
        self.assertEqual(len(table_def.columns), 2)

        # Measures assertions
        self.assertEqual(len(measures), 2)
        ext_m = next(m for m in measures if m.name == "Total Sales")
        self.assertTrue(ext_m.is_inherited)
        self.assertTrue(ext_m.is_external_measure)
        self.assertTrue(ext_m.out_of_scope)

        local_m = next(m for m in measures if m.name == "Local KPI")
        self.assertFalse(local_m.is_inherited)
        self.assertFalse(local_m.is_external_measure)
        self.assertFalse(local_m.out_of_scope)

    def test_docgen_skips_inherited_entities_when_flag_false(self):
        sample_model = {
            "model_name": "CompositeReportModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "Customer",
                    "role": "DIMENSION",
                    "is_inherited": True,
                    "out_of_scope": True,
                    "inherited_entity_name": "DimCustomer",
                    "inherited_expression_source": "DatabaseQuery",
                    "source_type": "InheritedEntity",
                    "columns": [{"name": "CustomerID", "data_type": "int64"}],
                    "classification_reasoning": {"confidence_score": 1.0},
                },
                {
                    "name": "LocalTargets",
                    "role": "FACT",
                    "is_inherited": False,
                    "out_of_scope": False,
                    "columns": [{"name": "TargetID", "data_type": "int64"}],
                    "connected_dimensions": ["Customer"],
                    "classification_reasoning": {"confidence_score": 1.0},
                }
            ],
            "measures": [
                {
                    "name": "Total Sales",
                    "table": "Customer",
                    "dax_expression": 'EXTERNALMEASURE("Total Sales", DOUBLE, "DatabaseQuery")',
                    "is_inherited": True,
                    "is_external_measure": True,
                    "out_of_scope": True,
                    "calculation_depth": 0,
                },
                {
                    "name": "Local Stretch KPI",
                    "table": "Customer",
                    "dax_expression": "[Total Sales] * 1.2",
                    "is_inherited": False,
                    "is_external_measure": False,
                    "out_of_scope": False,
                    "calculation_depth": 1,
                    "direct_measure_dependencies": ["Total Sales"],
                    "all_upstream_measures": ["Total Sales"],
                }
            ],
            "relationships": [],
        }

        # Test default configuration: include_inherited_entities = False
        config = DocGenConfig(include_inherited_entities=False)
        generator = MarkdownDocGenerator(config=config)
        docs = generator.generate_all_documents(sample_model)

        # 1. Local files generated, inherited standalone files skipped
        self.assertIn("INDEX.md", docs)
        self.assertIn("tables/LocalTargets.md", docs)
        self.assertNotIn("tables/Customer.md", docs)
        self.assertNotIn("measures/Customer/Total_Sales.md", docs)
        self.assertIn("measures/Customer/Local_Stretch_KPI.md", docs)

        # 2. In INDEX.md, inherited table and external measure are indexed without dead links
        index_md = docs["INDEX.md"]
        self.assertIn("`Customer`", index_md)
        self.assertIn("— *(Inherited Entity)*", index_md)
        self.assertIn("📦 Inherited", index_md)
        self.assertIn("[`LocalTargets`](tables/LocalTargets.md)", index_md)
        self.assertIn("`[Total Sales]`", index_md)
        self.assertIn("— *(External Measure)*", index_md)
        self.assertIn("measures/Customer/Local_Stretch_KPI.md", index_md)

        # 3. In local measure doc, reference to external measure is formatted without dead link
        kpi_md = docs["measures/Customer/Local_Stretch_KPI.md"]
        self.assertIn("`[Total Sales]` *(External Measure)*", kpi_md)
        self.assertIn("`Customer` *(Inherited Entity)*", kpi_md)

        # 4. In local table doc, reference to inherited dimension is formatted without dead link
        target_md = docs["tables/LocalTargets.md"]
        self.assertIn("`Customer` *(Inherited Entity)*", target_md)

    def test_docgen_publishes_inherited_entities_when_flag_true(self):
        sample_model = {
            "model_name": "CompositeReportModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "Customer",
                    "role": "DIMENSION",
                    "is_inherited": True,
                    "out_of_scope": True,
                    "inherited_entity_name": "DimCustomer",
                    "source_type": "InheritedEntity",
                    "columns": [{"name": "CustomerID", "data_type": "int64"}],
                    "classification_reasoning": {"confidence_score": 1.0},
                }
            ],
            "measures": [
                {
                    "name": "Total Sales",
                    "table": "Customer",
                    "dax_expression": 'EXTERNALMEASURE("Total Sales", DOUBLE, "DatabaseQuery")',
                    "is_inherited": True,
                    "is_external_measure": True,
                    "out_of_scope": True,
                    "calculation_depth": 0,
                }
            ],
            "relationships": [],
        }

        # Test with include_inherited_entities = True
        config = DocGenConfig(include_inherited_entities=True)
        generator = MarkdownDocGenerator(config=config)
        docs = generator.generate_all_documents(sample_model)

        self.assertIn("tables/Customer.md", docs)
        self.assertIn("measures/Customer/Total_Sales.md", docs)

    def test_cli_config_and_parser_out_of_scope_flag(self):
        from pbip_doc.cli import _load_cli_config
        import argparse

        # Default args without --include-inherited-entities
        parser = argparse.ArgumentParser()
        parser.add_argument("--include-inherited-entities", action="store_true")
        args_default = parser.parse_args([])
        cfg_default = _load_cli_config(args_default, "dummy_path")
        self.assertFalse(cfg_default.include_inherited_entities)

        # Args with --include-inherited-entities
        args_with_flag = parser.parse_args(["--include-inherited-entities"])
        cfg_enabled = _load_cli_config(args_with_flag, "dummy_path")
        self.assertTrue(cfg_enabled.include_inherited_entities)

        # Verify parser sets out_of_scope on model based on config
        bim_sample = {
            "model": {
                "tables": [
                    {
                        "name": "ExtTable",
                        "partitions": [{"name": "p1", "source": {"type": "entity", "entityName": "RemoteTable"}}],
                        "measures": [
                            {"name": "ExtM", "expression": "EXTERNALMEASURE(\"ExtM\", DOUBLE, \"src\")"}
                        ]
                    }
                ]
            }
        }
        # Default parser (include_inherited_entities=False)
        p_def = PBIPParser(config=cfg_default)
        m_def = p_def.parse_bim_dict(bim_sample)
        self.assertTrue(m_def.tables[0].is_inherited)
        self.assertTrue(m_def.tables[0].out_of_scope)
        self.assertTrue(m_def.measures[0].is_inherited)
        self.assertTrue(m_def.measures[0].out_of_scope)

        # Parser with include_inherited_entities=True
        p_inc = PBIPParser(config=cfg_enabled)
        m_inc = p_inc.parse_bim_dict(bim_sample)
        self.assertTrue(m_inc.tables[0].is_inherited)
        self.assertFalse(m_inc.tables[0].out_of_scope)
        self.assertTrue(m_inc.measures[0].is_inherited)
        self.assertFalse(m_inc.measures[0].out_of_scope)

    def test_config_overrides_coercion_and_set(self):
        cfg = DocGenConfig()
        # Test apply_overrides with string boolean, int, and list coercion
        cfg.apply_overrides({
            "include_table_m_code": "false",
            "exclude_auto_date_tables": "0",
            "include_inherited_entities": "true",
            "excluded_tables": "TableA, TableB",
            "output_dir": "custom_docs",
        })
        self.assertFalse(cfg.include_table_m_code)
        self.assertFalse(cfg.exclude_auto_date_tables)
        self.assertTrue(cfg.include_inherited_entities)
        self.assertEqual(cfg.excluded_tables, ["TableA", "TableB"])
        self.assertEqual(cfg.output_dir, "custom_docs")

        # Test parse_set_arg
        k, v = DocGenConfig.parse_set_arg("include_expression_docs=false")
        self.assertEqual(k, "include_expression_docs")
        self.assertEqual(v, "false")

        # Test template dict and descriptions
        tmpl = DocGenConfig.get_template_dict()
        self.assertIn("include_table_m_code", tmpl)
        self.assertIn("$schema", tmpl)
        descs = DocGenConfig.get_descriptions()
        self.assertIn("include_table_m_code", descs)

    def test_cli_load_config_with_json_and_set(self):
        from pbip_doc.cli import _load_cli_config
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--config")
        parser.add_argument("--config-json")
        parser.add_argument("--set", action="append")
        parser.add_argument("--include-auto-tables", action="store_true")
        parser.add_argument("--include-inherited-entities", action="store_true")
        parser.add_argument("--exclude-tables")

        # Test --config-json
        args1 = parser.parse_args(["--config-json", '{"include_table_m_code": false, "tables_subdir": "custom_tbls"}'])
        cfg1 = _load_cli_config(args1)
        self.assertFalse(cfg1.include_table_m_code)
        self.assertEqual(cfg1.tables_subdir, "custom_tbls")

        # Test --set
        args2 = parser.parse_args(["--set", "include_table_m_code=false", "--set", "output_dir=ci_docs"])
        cfg2 = _load_cli_config(args2)
        self.assertFalse(cfg2.include_table_m_code)
        self.assertEqual(cfg2.output_dir, "ci_docs")

    def test_mcp_server_config_overrides_and_get_configuration(self):
        from pbip_doc.mcp_server import PBIPMCPServer

        server = PBIPMCPServer()
        cfg = server._get_config({
            "config_overrides": {
                "include_table_m_code": False,
                "output_dir": "agent_docs",
            }
        })
        self.assertFalse(cfg.include_table_m_code)
        self.assertEqual(cfg.output_dir, "agent_docs")

        # Test _get_config_details
        details = server._get_config_details({
            "config_overrides": {"output_dir": "agent_docs"}
        })
        self.assertIn("active_configuration", details)
        self.assertEqual(details["active_configuration"]["output_dir"], "agent_docs")
        self.assertIn("available_settings", details)
        self.assertIn("include_table_m_code", details["available_settings"])

    def test_parse_tmdl_function_with_triple_backticks(self):
        from pbip_doc.parser import PBIPParser

        tmdl_content = """
function 'Safe Divide' = ```
	(Numerator: double, Denominator: double, Alt: double = 0) =>
		DIVIDE(Numerator, Denominator, Alt)
	```
	dataType: double
	lineageTag: 489c7d05-b072-4dcf-8bb5-38fc76781234
	description: "Safely divide two numbers"
"""
        parser = PBIPParser()
        fns = parser._parse_tmdl_functions(tmdl_content)
        self.assertEqual(len(fns), 1)
        fn = fns[0]
        self.assertEqual(fn.name, "Safe Divide")
        self.assertEqual(fn.return_type, "double")
        self.assertEqual(fn.description, "Safely divide two numbers")
        self.assertEqual(fn.lineage_tag, "489c7d05-b072-4dcf-8bb5-38fc76781234")
        self.assertEqual(fn.expression, "DIVIDE(Numerator, Denominator, Alt)")
        self.assertNotIn("```", fn.expression)

        # Check parameters
        self.assertEqual(len(fn.parameters), 3)
        self.assertEqual(fn.parameters[0].name, "Numerator")
        self.assertEqual(fn.parameters[0].data_type, "double")
        self.assertFalse(fn.parameters[0].is_optional)
        self.assertIsNone(fn.parameters[0].default_value)

        self.assertEqual(fn.parameters[1].name, "Denominator")
        self.assertEqual(fn.parameters[1].data_type, "double")
        self.assertFalse(fn.parameters[1].is_optional)

        self.assertEqual(fn.parameters[2].name, "Alt")
        self.assertEqual(fn.parameters[2].data_type, "double")
        self.assertTrue(fn.parameters[2].is_optional)
        self.assertEqual(fn.parameters[2].default_value, "0")

        self.assertEqual(fn.parameters_signature, "(Numerator: double, Denominator: double, Alt: double = 0)")

    def test_parse_tmdl_function_multiline_params_dax_tag(self):
        from pbip_doc.parser import PBIPParser

        tmdl_content = """
function ComplexCalc = ```dax
	(
		ParamA: double,
		ParamB: string = "default",
		ParamC: int64 = 100
	): double =>
		ParamA * ParamC
	```
	lineageTag: tag-123
"""
        parser = PBIPParser()
        fns = parser._parse_tmdl_functions(tmdl_content)
        self.assertEqual(len(fns), 1)
        fn = fns[0]
        self.assertEqual(fn.name, "ComplexCalc")
        self.assertEqual(fn.return_type, "double")
        self.assertEqual(fn.expression, "ParamA * ParamC")
        self.assertNotIn("```", fn.expression)

        self.assertEqual(len(fn.parameters), 3)
        self.assertEqual(fn.parameters[0].name, "ParamA")
        self.assertEqual(fn.parameters[0].data_type, "double")

        self.assertEqual(fn.parameters[1].name, "ParamB")
        self.assertEqual(fn.parameters[1].data_type, "string")
        self.assertTrue(fn.parameters[1].is_optional)
        self.assertEqual(fn.parameters[1].default_value, '"default"')

        self.assertEqual(fn.parameters[2].name, "ParamC")
        self.assertEqual(fn.parameters[2].data_type, "int64")
        self.assertTrue(fn.parameters[2].is_optional)
        self.assertEqual(fn.parameters[2].default_value, "100")

        self.assertEqual(
            fn.parameters_signature,
            '(ParamA: double, ParamB: string = "default", ParamC: int64 = 100)'
        )

    def test_parse_tmdl_function_without_backticks(self):
        from pbip_doc.parser import PBIPParser

        tmdl_content = """
function SimpleAdd = (x: int64, y: int64) => x + y
	dataType: int64
"""
        parser = PBIPParser()
        fns = parser._parse_tmdl_functions(tmdl_content)
        self.assertEqual(len(fns), 1)
        fn = fns[0]
        self.assertEqual(fn.name, "SimpleAdd")
        self.assertEqual(fn.return_type, "int64")
        self.assertEqual(fn.expression, "x + y")
        self.assertEqual(len(fn.parameters), 2)
        self.assertEqual(fn.parameters[0].name, "x")
        self.assertEqual(fn.parameters[1].name, "y")
        self.assertEqual(fn.parameters_signature, "(x: int64, y: int64)")


class TestCalculatedTables(unittest.TestCase):
    def test_parse_tmdl_calculated_partition_date(self):
        tmdl_content = """table LocalDateTable_28491a2e-49b9-4a92-9a09-1a051d93b0a1
\tisHidden
\tshowAsVariationsOnly
\tlineageTag: e8f9a0b1-c2d3-e4f5-a6b7-c8d9e0f1a2b3

\tcolumn Date
\t\tdataType: dateTime
\t\tisHidden
\t\tlineageTag: 11111111-2222-3333-4444-555555555555
\t\tdataCategory: PaddedDateTableDates
\t\tsummarizeBy: none
\t\tsourceColumn: [Date]

\tpartition LocalDateTable_28491a2e = calculated
\t\tmode: import
\t\tsource = Calendar(Date(2020,1,1), Date(2025,12,31))

\tannotation __PBI_LocalDateTable = true
"""
        parser = PBIPParser()
        table_def, measures, m_code = parser._parse_single_table_tmdl(
            tmdl_content, "LocalDateTable_28491a2e-49b9-4a92-9a09-1a051d93b0a1"
        )
        self.assertEqual(table_def.source_type, "CalculatedTable")
        self.assertEqual(table_def.expression, "Calendar(Date(2020,1,1), Date(2025,12,31))")
        self.assertEqual(m_code, "")

        # Test Star Schema classification recognizes DAX Calendar generator
        resolver = StarSchemaResolver([table_def], [])
        resolver.classify_tables()
        self.assertEqual(table_def.role, TableRole.DATE_DIMENSION)
        self.assertIn("DAX Date table generator: CALENDAR / CALENDARAUTO", table_def.classification_reasoning.criteria_matched)

    def test_parse_tmdl_calculated_partition_multiline_dax(self):
        tmdl_content = """table 'Customer Summary'

\tcolumn CustomerKey
\t\tdataType: int64

\tpartition 'Customer Summary' = calculated
\t\tmode: import
\t\tsource =
\t\t\tSUMMARIZECOLUMNS(
\t\t\t\t'DimCustomer'[CustomerKey],
\t\t\t\t"TotalSales", [Total Sales],
\t\t\t\t"TotalQty", SUM('FactOrders'[Quantity])
\t\t\t)
"""
        parser = PBIPParser()
        table_def, _, _ = parser._parse_single_table_tmdl(tmdl_content, "Customer Summary")
        self.assertEqual(table_def.source_type, "CalculatedTable")
        self.assertIn("SUMMARIZECOLUMNS", table_def.expression)
        self.assertIn("'DimCustomer'[CustomerKey]", table_def.expression)

        # Test measure analyzer dependency extraction on calculated table
        dim_cust = TableDefinition(name="DimCustomer", role=TableRole.DIMENSION, classification_reasoning=TableRoleClassification(TableRole.DIMENSION, 1.0))
        dim_cust.columns = [ColumnDefinition(name="CustomerKey", data_type="int64", is_key=True)]
        fact_ord = TableDefinition(name="FactOrders", role=TableRole.FACT, classification_reasoning=TableRoleClassification(TableRole.FACT, 1.0))
        fact_ord.columns = [ColumnDefinition(name="Quantity", data_type="int64")]

        m_sales = MeasureDefinition(name="Total Sales", table="FactOrders", dax_expression="SUM(FactOrders[Quantity])")

        analyzer = MeasureDependencyResolver(
            measures=[m_sales],
            tables=[dim_cust, fact_ord, table_def],
        )
        analyzer.analyze()

        self.assertIn("DimCustomer", table_def.referenced_tables)
        self.assertIn("FactOrders", table_def.referenced_tables)
        self.assertIn("Total Sales", table_def.referenced_measures)
        col_names = [(rc["table"], rc["column"]) for rc in table_def.referenced_columns]
        self.assertIn(("DimCustomer", "CustomerKey"), col_names)
        self.assertIn(("FactOrders", "Quantity"), col_names)

    def test_parse_bim_calculated_table_partition(self):
        bim_data = {
            "name": "TestBimModel",
            "compatibilityLevel": 1550,
            "model": {
                "culture": "en-US",
                "tables": [
                    {
                        "name": "DimDatesCalc",
                        "columns": [{"name": "Date", "dataType": "dateTime"}],
                        "partitions": [
                            {
                                "name": "DimDatesCalc-Partition",
                                "mode": "import",
                                "source": {
                                    "type": "calculated",
                                    "expression": [
                                        "CALENDARAUTO()"
                                    ]
                                }
                            }
                        ]
                    }
                ],
                "relationships": []
            }
        }
        parser = PBIPParser()
        model = parser.parse_bim_dict(bim_data)
        self.assertEqual(len(model.tables), 1)
        tbl = model.tables[0]
        self.assertEqual(tbl.name, "DimDatesCalc")
        self.assertEqual(tbl.source_type, "CalculatedTable")
        self.assertEqual(tbl.expression, "CALENDARAUTO()")
        self.assertEqual(tbl.role, TableRole.DATE_DIMENSION)

    def test_calculated_table_markdown_documentation(self):
        sample_model = {
            "model_name": "TestCalcModel",
            "source_format": "TMDL",
            "tables": [
                {
                    "name": "DimDate",
                    "role": "DATE_DIMENSION",
                    "source_type": "CalculatedTable",
                    "expression": "CALENDAR(DATE(2020, 1, 1), DATE(2025, 12, 31))",
                    "referenced_tables": [],
                    "referenced_columns": [],
                    "referenced_measures": [],
                    "columns": [
                        {"name": "Date", "data_type": "dateTime", "is_key": True},
                    ],
                    "connected_dimensions": [],
                    "connected_facts": [],
                    "reachable_lookup_tables": [],
                    "root_data_sources": [],
                    "upstream_queries_chain": [],
                    "classification_reasoning": {
                        "confidence_score": 0.95,
                        "criteria_matched": ["DAX Date table generator: CALENDAR / CALENDARAUTO"]
                    }
                }
            ],
            "measures": [],
            "relationships": [],
            "data_sources_summary": [],
        }

        generator = MarkdownDocGenerator()
        docs = generator.generate_all_documents(sample_model)

        # 1. Index contains DAX Calc badge and notice
        self.assertIn("INDEX.md", docs)
        index_doc = docs["INDEX.md"]
        self.assertIn("🧮 DAX Calc", index_doc)
        self.assertIn("Calculated Tables", index_doc)

        # 2. Table doc contains DAX Table Expression chapter & banner
        self.assertIn("tables/DimDate.md", docs)
        tbl_doc = docs["tables/DimDate.md"]
        self.assertIn("source_type: CalculatedTable", tbl_doc)
        self.assertIn("🧮 **DAX Calculated Table**", tbl_doc)
        self.assertIn("## 3. DAX Table Expression & Lineage", tbl_doc)
        self.assertIn("```dax", tbl_doc)
        self.assertIn("CALENDAR(DATE(2020, 1, 1), DATE(2025, 12, 31))", tbl_doc)
        self.assertIn("In-Memory Calculated Table", tbl_doc)


if __name__ == "__main__":
    unittest.main()


