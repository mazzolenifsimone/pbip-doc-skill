---
title: "03. Table Documentation Pages"
target_path: "docs/tables/<TableName>.md"
python_module: "pbip_doc.docgen.table_doc"
tags: ["table", "data_dictionary", "calculated_columns", "incremental_refresh", "snowflake_paths"]
---

# 03. Table Documentation Pages (`docs/tables/<TableName>.md`)

> **TL;DR**:
> - Each published table has a dedicated, self-contained Markdown file.
> - Begins with rich YAML frontmatter for faceted agent and vector indexing.
> - Details architectural role classification, star schema topology, and multi-hop snowflake outrigger paths.
> - Includes a complete Column Data Dictionary with special badges and formula blocks for DAX calculated columns.
> - Documents Power Query M lineage, incremental refresh policies, and hosted DAX measures.

---

## 📋 Frontmatter Specification

```yaml
---
title: "Table: FactInternetSales"
doc_type: "table_documentation"
table_name: "FactInternetSales"
role: "FACT"
source_type: "PowerQuery"
is_hidden: false
is_inherited: false
columns_count: 22
measures_count: 6
root_data_sources:
  - "sql-analytics.database.windows.net;DW"
connected_dimensions:
  - "DimCustomer"
  - "DimProduct"
  - "DimDate"
snowflake_lookup_tables:
  - "DimGeography"
  - "DimCountry"
tags:
  - "semantic_model"
  - "table"
  - "fact"
  - "fact_table"
  - "metrics"
  - "FactInternetSales"
---
```

---

## 🏛️ Modular Chapters Breakdown

Each table document is built from modular, toggleable chapters:

### 1. Semantic Overview & Role Badge
Displays table name, hidden status, business description (if present in metadata), and the assigned Star Schema role:
- **Role Badge**: `[FACT]`, `[DIMENSION]`, `[LOOKUP_OUTRIGGER]`, `[DATE_DIMENSION]`, etc.
- **Classification Reasoning**: Shows the confidence score (e.g. `0.95 / 1.0`) and matching criteria (e.g. `"Many-side endpoint in relationships with DimCustomer, DimProduct"`).

### 2. Model Topology & Relationships
Breaks down relational connections:
- **For Fact Tables**: Lists all connected dimensions and reachable snowflake lookup tables.
- **For Dimension Tables**: Lists all connected fact tables and outgoing lookup joins.
- **Relationships Table**:
  | Target Table | Cardinality | Direction | Active | Foreign Key (From) | Primary Key (To) |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | `DimCustomer` | `N:1` | Both | `true` | `[CustomerKey]` | `[CustomerKey]` |

### 3. Power Query (M) Lineage & Data Sources
Shows how data flows from physical systems into this table:
- **Root Physical Sources**: Connector type and connection string.
- **Staging Query Chain**: Multi-hop path through Power Query shared expressions (e.g. `Raw_Orders -> Staging_Orders -> FactInternetSales`).

### 4. Incremental Refresh & Hybrid Policy
When an incremental refresh policy is configured on the table, a dedicated chapter displays:
- **Status**: Enabled / Disabled.
- **Storage Mode**: `import` or `hybrid` (DirectQuery + Import).
- **Rolling Window**: Historical data retention (e.g. `3 Years`).
- **Incremental Refresh Period**: Period refreshed on each cycle (e.g. `7 Days`).
- **Polling Expression / Detect Data Changes**: Column or M expression used for watermark change detection.

### 5. Column Data Dictionary
Comprehensive reference for all physical and calculated attributes:

| Column Name | Data Type | Key | Calculated | Format | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SalesOrderNumber` | `string` | No | No | — | Unique order identifier |
| `OrderDateKey` | `int64` | Yes | No | — | Foreign key to `DimDate` |
| `MarginAmount` | `decimal` | No | `🧮 Calculated` | `$#,0.00` | UnitPrice minus TotalProductCost |

#### Calculated Columns Detail Section
If the table contains DAX calculated columns:
- Marked with a distinct `🧮 Calculated` badge in the table above.
- Followed by a dedicated subsection rendering the complete multiline DAX expression in highlighted code blocks (` ```dax `).
- Expressions with pipes (`|`) or line breaks are sanitized to preserve table structure.

### 6. Recursive Snowflake Outrigger Paths
Documents multi-hop normalization paths reachable from this table:
- **Lookup Table**: `DimCountry`
- **Hop Count**: 2
- **Path**: `FactInternetSales -> DimCustomer -> DimGeography -> DimCountry`

### 7. Hosted DAX Measures
Catalog of measures belonging to this table with calculation depth badges and relative Markdown links to their dedicated pages:
- `[Depth 0] [Total Sales](../measures/FactInternetSales/Total_Sales.md)`
- `[Depth 1] [Gross Margin](../measures/FactInternetSales/Gross_Margin.md)`

### 8. Raw Power Query M Code
Complete, unedited M expression inside a ` ```powerquery ` block for ETL auditing and reproducibility.

### 9. Contextual RAG Search Hints
A set of pre-calculated natural language questions that an AI agent or search engine might associate with this table (e.g. *"Which table contains customer transactions?"*, *"What dimensions are related to FactInternetSales?"*).

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why are calculated columns separated from measures in table docs?
**A**: Calculated columns are evaluated during data refresh and stored at row level within the table, whereas measures are evaluated on the fly at query time. Documenting calculated column formulas within the table page makes schema comprehension seamless.

### Q: Can sections be hidden if not needed?
**A**: Yes. Every section has a boolean toggle in `DocGenConfig` (e.g. `include_table_m_code: false` or `--set include_table_m_code=false`).
