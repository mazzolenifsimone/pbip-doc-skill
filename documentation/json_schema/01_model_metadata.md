---
title: "01. General Model Metadata"
target_json_path: "/"
python_module: "pbip_doc/parser.py, pbip_doc/model_schema.py"
source_formats: ["TMDL", "BIM"]
tags: ["metadata", "model_name", "compatibility_level", "culture", "exclusions", "data_sources"]
---

# 01. General Model Metadata (Root Object)

> **TL;DR**:
> - The root object provides high-level context, format detection, and model-wide summaries.
> - Automatically detects whether the source is a TMDL folder structure (`definition/`) or a TMSL `model.bim` file.
> - Excluded tables (such as Power BI automatic date tables) are removed across the entire model and recorded in `excluded_tables_list`.
> - Physical data sources across all queries are deduplicated and summarized in `data_sources_summary`.

---

## 📋 Root Properties Schema

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `model_name` | `string` | No | Name of the analyzed semantic model. |
| `source_format` | `string` | No | Detected source format: `"TMDL"` or `"BIM"`. |
| `compatibility_level` | `integer` | Yes | Tabular database compatibility level (e.g. `1550`, `1600`). |
| `culture` | `string` | No | Default culture / language locale (e.g. `"en-US"`, `"it-IT"`). |
| `created_timestamp` | `string` | Yes | Extraction timestamp in ISO-8601 UTC format. |
| `data_sources_summary` | `array[object]` | No | List of unique physical data sources discovered across the model. |
| `measure_dependency_dag` | `object` | No | Directed adjacency map connecting each measure to its direct dependencies. |
| `excluded_tables_count` | `integer` | No | Total number of tables excluded by active configuration filters. |
| `excluded_tables_list` | `array[string]` | No | Sorted list of names of all excluded tables. |
| `tables` | `array[object]` | No | All model tables (see [`02_tables_and_classification.md`](./02_tables_and_classification.md)). |
| `relationships` | `array[object]` | No | All active and inactive relationships (see [`05_relationships_and_star_schema.md`](./05_relationships_and_star_schema.md)). |
| `measures` | `array[object]` | No | All DAX measures defined in the model (see [`06_dax_measures_and_dag.md`](./06_dax_measures_and_dag.md)). |
| `functions` | `array[object]` | No | All custom DAX UDF functions (see [`07_user_defined_functions.md`](./07_user_defined_functions.md)). |
| `shared_queries` / `expressions` | `array[object]` | No | Power Query M staging queries, parameters, and inline tables (see [`08_power_query_lineage_and_inline_tables.md`](./08_power_query_lineage_and_inline_tables.md)). |
| `star_schema` | `object` | Yes | High-level star schema topology and Snowflake paths (see [`05_relationships_and_star_schema.md`](./05_relationships_and_star_schema.md)). |

---

## 🔍 Extraction & Population Logic

### 1. `model_name`
- **TMDL**:
  - If pointing to `.../definition/`, uses the parent folder name (`path.parent.stem`).
  - If pointing to the PBIP folder, uses the folder name (`path.stem`).
- **BIM**:
  - Uses the filename without extension (e.g. `model` for `model.bim`).
  - If specified via CLI, the explicit argument takes precedence.

### 2. `source_format`
Detected by inspecting the filesystem in `PBIPParser.parse()`:
- `"TMDL"`: when a `definition/` directory or a `tables/` directory with `.tmdl` files exists.
- `"BIM"`: when the target is a `.bim` file or a JSON file containing a `"model"` root key.

### 3. `compatibility_level`
- **TMDL**: read from `definition/model.tmdl` (defaults to `1550` or `1600` if omitted).
- **BIM**: read from `model.compatibilityLevel`.

### 4. `culture`
- **TMDL**: read from `cultureInfo` or annotations in `definition/model.tmdl` (default: `"en-US"`).
- **BIM**: read from `model.culture` (default: `"en-US"`).

### 5. `created_timestamp`
Generated at extraction time using `datetime.now(timezone.utc).isoformat()`.

### 6. `data_sources_summary`
Populated after resolving Power Query lineage (`MLineageResolver.get_all_root_sources()`):
- Represents the deduplicated list of all `PowerQuerySource` instances found across queries and table partitions.
- Each entry contains `source_type` (e.g. `SQL_SERVER`, `SHAREPOINT`, `ODATA`, `POSTGRESQL`, `EXCEL`, `LAKEHOUSE`, `INHERITED_ENTITY`), `connection_string`, `server`, `database`, `endpoint_or_path`, and `raw_snippet`.

### 7. `measure_dependency_dag`
Built by `MeasureDependencyResolver`:
- Adjacency dictionary where each key is a measure name, and the value is the list of other measures directly called by its DAX formula.

### 8. `excluded_tables_count` and `excluded_tables_list`
Populated by `PBIPSemanticModel.filter_excluded_tables()`:
- The engine applies exclusion filters from `DocGenConfig` (`exclude_auto_date_tables`, `excluded_table_patterns`, `excluded_tables`).
- Excluded tables (such as internal Power BI auto date tables `LocalDateTable_*` and `DateTableTemplate_*`) are purged from the active model and tracked in `excluded_tables_list`.
- `excluded_tables_count` records the total count.
- Relationships, snowflake paths, and measure references pointing to excluded tables are cleaned up automatically to prevent dead references.

---

## 💡 Example JSON

```json
{
  "model_name": "SalesAnalytics_Dataset",
  "source_format": "TMDL",
  "compatibility_level": 1600,
  "culture": "en-US",
  "created_timestamp": "2026-10-05T08:30:00Z",
  "excluded_tables_count": 2,
  "excluded_tables_list": [
    "DateTableTemplate_4f2a7b8e",
    "LocalDateTable_9c1d3e5f"
  ],
  "data_sources_summary": [
    {
      "source_type": "SQL_SERVER",
      "connection_string": "sql-prod.company.com / DataWarehouse",
      "server": "sql-prod.company.com",
      "database": "DataWarehouse",
      "endpoint_or_path": null,
      "authentication_mode": null,
      "raw_snippet": "Sql.Database(\"sql-prod.company.com\", \"DataWarehouse\")"
    },
    {
      "source_type": "INHERITED_ENTITY",
      "connection_string": "Entity: RemoteCustomer (Source: CentralDataModel)",
      "server": null,
      "database": null,
      "endpoint_or_path": "RemoteCustomer",
      "authentication_mode": null,
      "raw_snippet": null
    }
  ],
  "measure_dependency_dag": {
    "Total Sales": [],
    "Gross Margin": ["Total Sales", "Total Cost"],
    "Margin %": ["Gross Margin", "Total Sales"]
  }
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: How does the engine distinguish between TMDL and BIM source models?
**A**: The parser inspects the input path. If it finds a directory containing `definition/` or `.tmdl` files inside a `tables/` subfolder, it uses TMDL mode. If it finds a `.bim` or JSON file containing a `"model"` root key, it uses BIM mode.

### Q: What happens to measures or relationships linked to excluded tables?
**A**: When a table is excluded, the engine automatically removes any relationships connecting to it, purges measures residing inside it, and removes references to its columns from remaining measures and functions.

### Q: Can I keep auto-generated date tables in the output if needed?
**A**: Yes. Set `"exclude_auto_date_tables": false` in `pbip_doc.config.json` or pass the `--include-auto-tables` flag on the command line.
