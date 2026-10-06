---
title: "08. Power Query Lineage & Inline Tables"
target_json_path: "/expressions[], /shared_queries[], /tables[]/power_query_lineage"
python_module: "pbip_doc/m_lineage.py, pbip_doc/m_table_parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["power_query", "m_code", "lineage", "staging", "inline_table", "sources", "etl"]
---

# 08. Power Query Lineage & Inline Tables (`expressions[]` and `#table`)

> **TL;DR**:
> - Traces Power Query M lineage through multi-hop staging queries back to physical data sources (`PowerQuerySource`).
> - Maps staging dependencies and tracks downstream consuming model tables.
> - Automatically detects static in-memory tables built with `#table(...)`, extracting typed columns, schemas, and row values.
> - Produces sanitized GitHub Flavored Markdown table previews with pipe escaping.

---

## 📋 Lineage Node Schema (`PowerQueryLineageNode`)

Lineage nodes appear both in the top-level shared queries list (`expressions[]` / `shared_queries[]`) and as the `power_query_lineage` property on individual tables.

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `query_name` | `string` | No | Name of the M query or staging node. |
| `target_table` | `string` | Yes | Target model table loaded by this query, or `null` if intermediate (*staging*). |
| `is_staging` | `boolean` | No | `true` if not loaded directly into the model (Enable Load = false); `false` if loaded. |
| `direct_dependencies` | `array[string]` | No | Other M queries directly referenced (e.g. `#"Staging Orders"`). |
| `all_upstream_queries` | `array[string]` | No | Full transitive closure of all ancestor M queries in the ETL chain. |
| `downstream_queries` | `array[string]` | No | Other staging queries consuming the output of this query. |
| `downstream_tables` | `array[string]` | No | Final model tables fed by this query. |
| `root_sources` | `array[object]` | No | Physical or remote data sources (`PowerQuerySource`) reached by tracing upstream. |
| `full_m_expression` | `string` | No | Complete M code of the query (`let ... in` block). |
| `steps` | `array[object]` | No | Ordered transformation steps (`PowerQueryLineageStep`). |
| `description` | `string` | Yes | Semantic description of the query. |
| `query_group` | `string` | Yes | Query group folder name in Power Query Desktop (`queryGroup`). |
| `lineage_tag` | `string` | Yes | Unique lineage tag from TMDL/BIM. |
| `expression_kind` | `string` | Yes | Type: `"m"`, `"table"` (for `#table`), `"parameter"`, `"function"`. |
| `is_inline_table` | `boolean` | No | `true` if defined using `#table(...)`; otherwise `false`. |
| `inline_table_columns` | `array[string]` | No | Column names extracted from the `#table` declaration. |
| `inline_table_column_types`| `object` | No | Map of column -> M type (e.g. `{"ID": "Int64.Type", "Desc": "text"}`). |
| `inline_table_rows` | `array[array]` | No | Matrix of row values extracted from `#table`. |
| `inline_table_markdown` | `string` | Yes | GitHub Flavored Markdown table preview with pipe escaping. |

---

## 🔌 Data Source Schema (`PowerQuerySource`)

Each physical or remote data source reached along the pipeline is represented as:

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `source_type` | `string` | No | Connector type: `SQL_SERVER`, `POSTGRESQL`, `SHAREPOINT`, `ODATA`, `EXCEL`, `CSV`, `WEB`, `LAKEHOUSE`, `INHERITED_ENTITY`, `MANUAL`. |
| `connection_string` | `string` | No | Synthetic connection string or target URL. |
| `server` | `string` | Yes | Server host or database instance name. |
| `database` | `string` | Yes | Database name or catalog. |
| `endpoint_or_path` | `string` | Yes | URL path, folder path, or remote entity name. |
| `authentication_mode` | `string` | Yes | Configured authentication mode (if specified). |
| `raw_snippet` | `string` | Yes | Original M connector call (e.g. `Sql.Database("srv", "db")`). |

---

## 🔄 Multi-Hop Resolution Algorithm (`MLineageResolver`)

In enterprise semantic models, tables frequently source data through shared staging queries rather than connecting directly to databases:

```text
  [SQL Database] ──> [Staging Orders] ──┐
                                        ├──> [FactSales] (Model Table)
  [SharePoint]   ──> [Staging Rates]  ──┘
```

1. **Connector Call Scanning**:
   - `MLineageResolver` detects connector functions (`Sql.Database`, `PostgreSQL.Database`, `OData.Feed`, `SharePoint.Files`, `Excel.Workbook`, `Fabric.Lakehouse`, etc.) and extracts servers, databases, and paths.
2. **Inter-Query Dependencies**:
   - Matches references to other queries (`#"Query Name"`).
3. **Graph Traversal**:
   - Traces the query tree upstream to leaf nodes (`root_sources`).
   - Propagates impact downstream to final model tables (`downstream_tables`).

---

## 📊 Parsing and Markdown Rendering for `#table` (`m_table_parser.py`)

When a query uses the `#table(...)` constructor:

```powerquery
#table(
    type table [ID = Int64.Type, Status = text, Code = text],
    {
        {1, "Active", "ACT"},
        {2, "Suspended", "SUS"},
        {3, "Closed", "CLS"}
    }
)
```

1. **Detection**: identifies calls to `#table`.
2. **Column Schema & Types**: parses `type table [...]` or `{...}` to populate `inline_table_columns` and `inline_table_column_types`.
3. **Rows & Values**: extracts data rows, handling Power Query literals (dates `#date(YYYY, MM, DD)`, numbers, text).
4. **Markdown Table Generation (`inline_table_markdown`)**:
   - Formats data into a standard Markdown table.
   - Pipe characters (`|`) in text are sanitized (`\|`) so the Markdown table remains intact.

---

## 💡 Example JSON

```json
{
  "query_name": "Staging_OrderStatus",
  "target_table": null,
  "is_staging": true,
  "direct_dependencies": [],
  "all_upstream_queries": [],
  "downstream_queries": ["DimOrderHeader"],
  "downstream_tables": ["DimOrderHeader"],
  "root_sources": [
    {
      "source_type": "MANUAL",
      "connection_string": "Inline Table (#table)",
      "server": null,
      "database": null,
      "endpoint_or_path": "Inline Table (#table)",
      "authentication_mode": null,
      "raw_snippet": "#table(...)"
    }
  ],
  "full_m_expression": "let\n    Source = #table(type table [StatusCode = text, StatusDesc = text], {{\"A\", \"Active\"}, {\"C\", \"Closed\"}})\nin\n    Source",
  "is_inline_table": true,
  "inline_table_columns": ["StatusCode", "StatusDesc"],
  "inline_table_column_types": {
    "StatusCode": "text",
    "StatusDesc": "text"
  },
  "inline_table_rows": [
    ["A", "Active"],
    ["C", "Closed"]
  ],
  "inline_table_markdown": "| StatusCode | StatusDesc |\n| --- | --- |\n| A | Active |\n| C | Closed |"
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: What is the difference between expressions and shared_queries in the JSON?
**A**: They point to the same collection of `PowerQueryLineageNode` objects. `expressions` aligns with the TMDL naming convention (`expressions.tmdl`), while `shared_queries` reflects TMSL nomenclature (`sharedExpressions`).

### Q: How does the engine identify physical root sources across chained staging queries?
**A**: It performs graph traversal. Starting from the loaded table, it follows intermediate query references upstream until it encounters leaf queries calling native data connector functions (like `Sql.Database` or `OData.Feed`).

### Q: How are inline tables (#table) preserved in Markdown without breaking table borders?
**A**: The parser escapes any internal pipe characters (`|`) into `\|` and normalizes multi-line text into single-line cells, ensuring clean GitHub Flavored Markdown rendering.
