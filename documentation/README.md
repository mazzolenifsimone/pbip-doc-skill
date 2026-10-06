---
title: "pbip-doc-skill - Technical Reference Portal"
target_path: "documentation/"
tags: ["documentation", "portal", "index", "json_schema", "markdown_generator", "rag"]
---

# pbip-doc-skill - Technical Reference Portal

> **TL;DR**:
> - This portal provides comprehensive technical specifications for the two-phase pbip-doc-skill.
> - **Phase 1 (`json_schema/`)**: Documents the dependency resolver and the enriched JSON metadata schema.
> - **Phase 2 (`markdown_generator/`)**: Documents the modular, RAG-ready Markdown generator, file schemas, and agent conventions.
> - All documentation is structured for clear human reading and high-precision agent navigation.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────┐
│               PBIP Semantic Model Sources              │
│       (.tmdl definition folders / TMSL model.bim)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│          PHASE 1: Core Dependency Engine               │
│   (TMDL/BIM Parser, M Lineage, Star Schema, DAX DAG)   │
└───────────────────────────┬────────────────────────────┘
                            │ Produces Single Source of Truth
                            ▼
┌────────────────────────────────────────────────────────┐
│         Standardized Metadata JSON Specification       │
│               [documentation/json_schema/]             │
└───────────────────────────┬────────────────────────────┘
                            │ Consumed by
                            ▼
┌────────────────────────────────────────────────────────┐
│          PHASE 2: Modular Markdown Generator           │
│   (INDEX.md, tables/*.md, measures/*/*.md, RAG Hints)  │
│           [documentation/markdown_generator/]          │
└────────────────────────────────────────────────────────┘
```

---

## 📑 Documentation Suites

### 1. Phase 1: Metadata Extraction & JSON Schema Reference
Located in [`documentation/json_schema/`](./json_schema/README.md):

- [`01_model_metadata.md`](./json_schema/01_model_metadata.md): Root model metadata, counts, and auto-table exclusions.
- [`02_tables_and_classification.md`](./json_schema/02_tables_and_classification.md): Table definitions and Star Schema role classification.
- [`03_columns_and_calculated_columns.md`](./json_schema/03_columns_and_calculated_columns.md): Physical columns and DAX calculated columns.
- [`04_incremental_refresh_policy.md`](./json_schema/04_incremental_refresh_policy.md): Incremental refresh and hybrid realtime policies.
- [`05_relationships_and_star_schema.md`](./json_schema/05_relationships_and_star_schema.md): Relationships, cardinality, and snowflake paths.
- [`06_dax_measures_and_dag.md`](./json_schema/06_dax_measures_and_dag.md): DAX tokenizer, DAG, calculation depths, and impact.
- [`07_user_defined_functions.md`](./json_schema/07_user_defined_functions.md): User-Defined DAX Functions (UDFs).
- [`08_power_query_lineage_and_inline_tables.md`](./json_schema/08_power_query_lineage_and_inline_tables.md): Power Query lineage and `#table` parsing.
- [`09_inherited_entities_composite_models.md`](./json_schema/09_inherited_entities_composite_models.md): Composite models and inherited remote entities.

### 2. Phase 2: Markdown Generation & RAG Patterns Reference
Located in [`documentation/markdown_generator/`](./markdown_generator/README.md):

- [`01_engine_and_configuration.md`](./markdown_generator/01_engine_and_configuration.md): Orchestration engine and publishing filters.
- [`02_index_catalog_page.md`](./markdown_generator/02_index_catalog_page.md): Master catalog (`INDEX.md`), KPI cards, and inventories.
- [`03_table_pages.md`](./markdown_generator/03_table_pages.md): Table pages, data dictionaries, calculated columns, and snowflake joins.
- [`04_measure_pages.md`](./markdown_generator/04_measure_pages.md): Measure pages, calculation depth, and downstream impact.
- [`05_expression_and_query_pages.md`](./markdown_generator/05_expression_and_query_pages.md): Shared ETL queries, `#table` rendering, and staging lineage.
- [`06_function_pages.md`](./markdown_generator/06_function_pages.md): DAX UDF pages and parameter signatures.
- [`07_rag_patterns_and_agent_conventions.md`](./markdown_generator/07_rag_patterns_and_agent_conventions.md): RAG design, YAML frontmatter schemas, token chunking, and table sanitization.
