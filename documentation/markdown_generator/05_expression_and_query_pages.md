---
title: "05. Power Query Expression Pages"
target_path: "docs/expressions/<ExpressionName>.md"
python_module: "pbip_doc.docgen.expression_doc, pbip_doc.m_table_parser"
tags: ["expression", "power_query", "m_code", "staging_queries", "inline_table", "parameters"]
---

# 05. Power Query Expression Pages (`docs/expressions/<ExpressionName>.md`)

> **TL;DR**:
> - Documents shared Power Query M expressions, staging queries, ETL parameters, and inline data tables (`#table`).
> - Categorizes expressions into four distinct architectural types: `STAGING_QUERY`, `INLINE_TABLE`, `PARAMETER`, and `CUSTOM_FUNCTION`.
> - Parses inline `#table` data syntax and renders real Markdown tables for instant data inspection.
> - Breaks down ETL transformation steps (`let ... in`) in sequential order.
> - Tracks downstream model tables that consume data from this query.

---

## 📋 Frontmatter Specification

```yaml
---
title: "Expression: Staging_CustomerOrders"
doc_type: "power_query_expression_documentation"
expression_name: "Staging_CustomerOrders"
expression_type: "STAGING_QUERY"
is_staging: true
is_inline_table: false
query_group: "Staging"
root_data_sources:
  - "sql-analytics.database.windows.net;DW"
all_upstream_queries:
  - "Database_Endpoint_Parameter"
downstream_tables:
  - "FactInternetSales"
  - "FactResellerSales"
tags:
  - "semantic_model"
  - "power_query"
  - "expression"
  - "staging_query"
  - "Staging_CustomerOrders"
---
```

---

## 🔍 Expression Classification Categories

The builder inspects the M expression code and categorizes it:

| Category | Detection Criteria | Documentation Focus |
|---|---|---|
| `INLINE_TABLE` | Contains `#table(...)` construct | Parses schema and renders inline rows as a Markdown table. |
| `PARAMETER` | Contains `IsParameterQuery=true` or `IsParameterQueryRequired` | Documents parameter type, default value, and referenced queries. |
| `CUSTOM_FUNCTION` | Contains parameter signature `(...) =>` | Documents function inputs, M logic, and callers. |
| `STAGING_QUERY` | Standard query loading or transforming data | Traces upstream sources and downstream destination tables. |

---

## 🏛️ Modular Chapters Breakdown

### 1. Overview & Classification
Displays query name, classification category badge, query group (folder in Power BI), business description, and lineage tag.

### 2. Inline Table Data Rows (`#table` Parser)
When an expression defines an inline static table (frequently used for status codes, business mappings, or date offsets):
- The parser in `pbip_doc/m_table_parser.py` extracts the column definitions, types, and raw rows.
- Formats the data directly into a Markdown table:

| StatusCode | StatusName | IsActive | SortOrder |
| :--- | :--- | :--- | :--- |
| `1` | `Pending Approval` | `true` | `10` |
| `2` | `Shipped` | `true` | `20` |
| `3` | `Cancelled` | `false` | `30` |

### 3. Data Source Connection & Lineage
Identifies physical endpoints used by the query:
- Source connector (e.g. `Sql.Database`, `Web.Contents`, `OData.Feed`).
- Server, database, or URL.
- Upstream parameters referenced for credentials or environment routing.

### 4. Step-by-Step Transformation Breakdown
Analyzes the `let ... in` block and presents a sequential transformation table:

| Step Name | Operation / M Function | Input Step |
| :--- | :--- | :--- |
| `Source` | `Sql.Database(...)` | Root Connection |
| `FilteredRows` | `Table.SelectRows(...)` | `Source` |
| `RemovedColumns` | `Table.RemoveColumns(...)` | `FilteredRows` |

### 5. Downstream Target Tables
Lists every model table that ingests data from this shared expression with cross-links:
- `[FactInternetSales](../tables/FactInternetSales.md)`
- `[FactResellerSales](../tables/FactResellerSales.md)`

### 6. Raw Power Query M Code Block
Displays the complete code formatted inside a ` ```powerquery ` block for version control audits.

### 7. Contextual RAG Search Hints
Sample natural language queries addressing ETL lineage (e.g. *"Where does FactInternetSales get its staging data?"*, *"What values are in the StatusCode inline table?"*).

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why document staging queries separately from tables?
**A**: In Power BI and Microsoft Fabric, staging queries are marked with `IsDataLoaded: false`. They never become tables in the semantic model, but they perform crucial business logic, merges, and cleaning. Documenting them ensures complete ETL governance.

### Q: Are large inline tables truncated?
**A**: The `#table` parser renders up to 100 preview rows to preserve token economy and prevent massive Markdown document bloat, adding a truncation notice when more rows exist.
