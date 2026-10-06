---
title: "Markdown Documentation Generator Reference"
target_path: "docs/"
python_package: "pbip_doc/docgen/"
source_inputs: ["PBIP Semantic Model", "model.bim", "semantic_model_documentation.json"]
tags: ["docgen", "markdown", "rag", "documentation", "catalog", "power_bi"]
---

# Markdown Documentation Generator Reference

> **TL;DR**:
> - Phase 2 takes the semantic model (directly or from Phase 1 JSON) and generates modular, human-readable, and RAG-ready Markdown documentation.
> - Produces a master catalog (`INDEX.md`) and dedicated, self-contained Markdown files for every table, DAX measure, User-Defined Function (UDF), and Power Query expression.
> - Every file includes structured YAML frontmatter, enabling vector databases and AI agents to filter and search model metadata efficiently.
> - Handles Power BI auto date table exclusion, inherited entities scoping, table role classification, DAX calculation depths, and `#table` inline data rendering.

---

## 🏛️ Documentation File Structure

When executed, the Markdown Generator builds a clean, structured directory tree in the configured output directory (default: `docs/`):

```text
docs/
├── INDEX.md                               # Master catalog and global inventory
├── tables/                                # Dedicated Markdown page per table
│   ├── FactInternetSales.md
│   ├── DimCustomer.md
│   ├── DimGeography.md
│   └── ...
├── measures/                              # Dedicated Markdown page per DAX measure
│   ├── FactInternetSales/                 # Grouped by host table folder
│   │   ├── Total_Sales.md
│   │   ├── Gross_Margin.md
│   │   ├── Margin_Pct.md
│   │   └── ...
│   └── DimCustomer/
│       └── Customer_Count.md
├── functions/                             # User-Defined DAX Functions (UDFs)
│   ├── fn_FormatCurrency.md
│   └── ...
└── expressions/                           # Shared Power Query M expressions
    ├── Staging_Orders.md
    ├── DimGeography_Source.md
    └── Parameter_Environment.md
```

---

## 📑 Specification Index

| No. | Document | Module | Key Topics |
|---|---|---|---|
| 01 | [`01_engine_and_configuration.md`](./01_engine_and_configuration.md) | `engine.py`, `config.py` | Orchestration engine, input formats, table/measure publishing filters, and config overrides |
| 02 | [`02_index_catalog_page.md`](./02_index_catalog_page.md) | `index_doc.py` | Structure of `INDEX.md`, summary KPI cards, star schema table directory, and depth-sorted measure list |
| 03 | [`03_table_pages.md`](./03_table_pages.md) | `table_doc.py` | Table pages, role reasoning, columns dictionary, calculated column badges, relationships, and snowflake paths |
| 04 | [`04_measure_pages.md`](./04_measure_pages.md) | `measure_doc.py` | Measure pages, DAX formula formatting, calculation depth (Depth 0..N), upstream DAG, and downstream impact |
| 05 | [`05_expression_and_query_pages.md`](./05_expression_and_query_pages.md) | `expression_doc.py` | Power Query expressions, staging queries, `#table` inline Markdown rendering, and downstream tables |
| 06 | [`06_function_pages.md`](./06_function_pages.md) | `function_doc.py` | DAX UDF functions, parameter signatures, formulas, and consuming measures |
| 07 | [`07_rag_patterns_and_agent_conventions.md`](./07_rag_patterns_and_agent_conventions.md) | `utils.py` | RAG optimization, YAML frontmatter schemas, token economy, Markdown table sanitization, and linking |

---

## 🎯 Core Design Principles

1. **Dual Audience**: Every page is structured to be instantly readable by human BI engineers and directly indexable by vector search engines and AI agents.
2. **Modular Granularity**: Rather than generating a single monolithic file of tens of thousands of lines, each entity has its own Markdown page. This fits within LLM context windows and prevents token exhaustion during retrieval.
3. **Structured YAML Frontmatter**: Every file begins with clean, parseable YAML metadata specifying entity type, roles, calculation depth, and tags.
4. **Relational Traceability**: Tables link to their measures, measures link to their host tables, and measures link to both upstream prerequisites and downstream dependents.
5. **Deterministic Sanitization**: Expressions with pipes (`|`), brackets, and newlines are sanitized so Markdown tables and syntax render without formatting corruption.

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Does the generator require Phase 1 JSON, or can it run directly on PBIP files?
**A**: Both workflows are supported. You can pass a `semantic_model_documentation.json` file or pass the PBIP folder / `model.bim` path directly. When passed PBIP files directly, the generator invokes `PBIPParser` internally.

### Q: What happens to Power BI auto-generated date tables?
**A**: By default (`exclude_auto_date_tables: true`), all hidden `LocalDateTable_*` and `DateTableTemplate_*` tables are excluded from table documentation, relationships, and the master index.

### Q: How are inherited entities handled?
**A**: Central dataset tables inherited in composite models (`partition = entity`) and external measures (`EXTERNALMEASURE`) are kept in the global index and relationship maps, but excluded from generating standalone markdown pages unless `include_inherited_entities: true` is configured.
