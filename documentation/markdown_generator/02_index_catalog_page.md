---
title: "02. Master Index Catalog (INDEX.md)"
target_path: "docs/INDEX.md"
python_module: "pbip_doc.docgen.index_doc"
tags: ["index", "catalog", "master_document", "inventory", "star_schema", "kpi_hierarchy"]
---

# 02. Master Index Catalog (`<project_name>.md` / `INDEX.md`)

> **TL;DR**:
> - `<project_name>.md` (or `INDEX.md`) is the central catalog and entry point for the entire semantic model documentation.
> - By default, the master file is dynamically named after the project (e.g. `AdventureWorks.md`), matching the `pbip_project` frontmatter tag. It can be overridden via `index_filename`.
> - Contains high-level metadata (counts, compatibility level, culture) and structured YAML frontmatter.
> - Groups tables by their architectural Star Schema role (Fact, Dimension, Snowflake Outrigger, Date, Bridge).
> - Groups DAX measures by their calculation depth (Depth 0 base measures vs. higher-level KPIs).
> - Lists detected physical data sources, shared Power Query ETL expressions, custom DAX functions, and report presentation pages.

---

## 📋 Frontmatter Specification

The master catalog starts with catalog-level YAML frontmatter:

```yaml
---
title: "Semantic Model Documentation: AdventureWorks"
pbip_project: AdventureWorks
doc_type: "semantic_model_catalog"
format: "TMDL"
tables_count: 12
measures_count: 45
functions_count: 2
expressions_count: 6
data_sources_count: 3
excluded_tables_count: 4
tags:
  - "semantic_model"
  - "catalog"
  - "pbip"
  - "AdventureWorks"
---
```

### Frontmatter Fields

| Field | Type | Description |
|---|---|---|
| `title` | `string` | Display title of the semantic model documentation. |
| `doc_type` | `string` | Fixed as `"semantic_model_catalog"` for categorization by RAG parsers. |
| `format` | `string` | Source specification: `"TMDL"` or `"BIM"`. |
| `tables_count` | `integer` | Count of published tables in the model (excluding auto tables). |
| `measures_count` | `integer` | Total number of published DAX measures. |
| `functions_count` | `integer` | Count of custom DAX functions (UDFs). |
| `expressions_count` | `integer` | Count of shared Power Query expressions / staging queries. |
| `data_sources_count` | `integer` | Count of unique physical connection endpoints. |
| `excluded_tables_count`| `integer` | Count of auto-generated or explicitly excluded tables. |

---

## 🏛️ Document Structure & Chapters

### 1. Model Header & Overview
Displays the model name, compatibility level (e.g. `1600`), culture (e.g. `en-US`), and an overview explaining the purpose of the documentation suite.

### 2. Detected Physical Data Sources
A consolidated table listing all physical systems connected to the semantic model:

| Connector Type | Connection / Target | Server | Database |
| :--- | :--- | :--- | :--- |
| `SQL_SERVER` | `sql-analytics.database.windows.net;DW` | `sql-analytics.database.windows.net` | `DW` |
| `WEB` | `https://api.ecb.europa.eu/exchange_rates` | — | — |

### 3. Table Catalog Grouped by Role
Tables are sorted and categorized according to their classified Star Schema role:
- **Fact Tables**: Measures metrics and transactions (links to `tables/FactSales.md`, showing column count and hosted measure count).
- **Dimension Tables**: Provides entity attributes for filtering and grouping.
- **Lookup / Outrigger Tables**: Normalized secondary dimensions connected to primary dimensions (Snowflake schema).
- **Date / Calendar Dimensions**: Calendar tables used for time intelligence.
- **Bridge Tables**: Resolves many-to-many relationships.
- **Utility & Disconnected Tables**: Disconnected tables used for slicers or parameters.

Each entry includes:
- Markdown link to the dedicated table page (`tables/<TableName>.md` or `<base_doc_url>/tables/<TableName>.md`). For inherited tables, links directly to the external model's documentation if configured (with an `*(External)*` badge), or displays a non-linked `*(Inherited Entity)*` indicator.
- Refresh policy badge (`Full`, `🔄 Incremental`, `⚡ Hybrid`, `📦 Inherited`).
- Total columns count.
- Hosted measures count.
- Classification confidence badge and matching criteria.

### 4. DAX Measure Catalog Grouped by Calculation Depth
Measures are grouped by their topological calculation depth:
- **Base Measures (Depth 0)**: Measures referencing only physical columns (e.g. `SUM(Sales[Amount])`).
- **Secondary KPIs (Depth 1)**: Measures referencing at least one Base Measure (e.g. `[Gross Margin] = [Total Sales] - [Total Cost]`).
- **Composite KPIs (Depth 2+)**: Complex multi-hop ratios, variance, and cumulative metrics (e.g. `[Margin %] = DIVIDE([Gross Margin], [Total Sales])`).

Each entry links to the measure's dedicated Markdown document under `measures/<HostTable>/<MeasureName>.md` (or `<base_doc_url>/measures/...`). External measures defined via `EXTERNALMEASURE(...)` link directly to their external documentation page if configured (with an `*(External)*` badge), or show a non-linked `*(External Measure)*` indicator.

### 5. Custom DAX Functions (UDFs) & Power Query Expressions
When present, additional sections list:
- User-Defined DAX Functions with signatures and links to `functions/<FunctionName>.md`.
- Shared Power Query ETL expressions with links to `expressions/<ExpressionName>.md`.

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why group measures by Calculation Depth instead of host table in INDEX.md?
**A**: While physical file paths are organized by host table (`measures/<HostTable>/<MeasureName>.md`), the `INDEX.md` groups them by **Calculation Depth**. This gives data architects and agents an instant picture of the calculation hierarchy, from raw column aggregations up to top-level business KPIs.

### Q: Are inherited entities listed in the INDEX.md?
**A**: Yes. Inherited tables and external measures appear in the inventory with an `[Inherited Entity]` badge, allowing users to see the complete model graph even when dedicated child pages are omitted.
