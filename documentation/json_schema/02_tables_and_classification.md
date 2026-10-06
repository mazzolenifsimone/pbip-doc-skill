---
title: "02. Tables and Role Classification"
target_json_path: "/tables[]"
python_module: "pbip_doc/star_schema.py, pbip_doc/parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["tables", "star_schema", "fact", "dimension", "outrigger", "role", "partitions"]
---

# 02. Tables and Role Classification (`tables[]`)

> **TL;DR**:
> - Each table object represents a distinct entity loaded or defined in the semantic model.
> - The engine classifies every table into an architectural role (`FACT`, `DIMENSION`, `LOOKUP_OUTRIGGER`, `DATE_DIMENSION`, `BRIDGE`, `PARAMETER_UTILITY`, `CALCULATION_GROUP`, `UNKNOWN`).
> - Classification uses a deterministic, topology-driven scoring model with an explicit `confidence_score` and list of `criteria_matched`.
> - Identifies partition modes: Power Query M, DAX calculated tables, calculation groups, and inherited remote entities.

---

## 📋 Table Properties Schema

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `name` | `string` | No | Table name (e.g. `"FactInternetSales"`, `"DimCustomer"`). |
| `role` | `string` (enum) | No | Classified role (`FACT`, `DIMENSION`, `LOOKUP_OUTRIGGER`, `DATE_DIMENSION`, `BRIDGE`, `CALCULATION_GROUP`, `PARAMETER_UTILITY`, `UNKNOWN`). |
| `classification_reasoning` | `object` | No | Detailed explanation of the role assignment (`role`, `confidence_score`, `criteria_matched`, `details`). |
| `columns` | `array[object]` | No | Columns defined in the table (see [`03_columns_and_calculated_columns.md`](./03_columns_and_calculated_columns.md)). |
| `is_hidden` | `boolean` | No | `true` if hidden in Power BI report view (`isHidden: true`). Default: `false`. |
| `description` | `string` | Yes | Table description defined in metadata. |
| `source_type` | `string` | No | How the table is fed: `"PowerQuery"`, `"CalculatedTable"`, `"CalculationGroup"`, `"InheritedEntity"`. |
| `power_query_lineage` | `object` | Yes | Linked Power Query lineage node (when `source_type == "PowerQuery"`). |
| `root_data_sources` | `array[object]` | No | Physical or remote data sources feeding this table. |
| `upstream_queries_chain` | `array[string]` | No | Ordered list of intermediate staging queries in the ETL chain. |
| `incremental_refresh_policy`| `object` | Yes | Incremental refresh settings (see [`04_incremental_refresh_policy.md`](./04_incremental_refresh_policy.md)). |
| `direct_related_tables` | `array[string]` | No | Tables connected by direct relationships (active or inactive). |
| `connected_dimensions` | `array[string]` | No | For Facts: dimension tables on the "One" side of 1:N relationships. |
| `connected_facts` | `array[string]` | No | For Dimensions: fact tables on the "Many" side of 1:N relationships. |
| `reachable_lookup_tables` | `array[string]` | No | For Facts: outrigger/lookup tables reachable through connected dimensions. |
| `snowflake_paths` | `array[object]` | No | Full multi-hop join paths from this table to outrigger tables. |
| `is_inherited` | `boolean` | No | `true` if inherited from an external model (e.g. `entity` partition). |
| `inherited_entity_name` | `string` | Yes | Entity name in the remote source model. |
| `inherited_expression_source`| `string` | Yes | Connector or expression source name for the remote entity. |
| `out_of_scope` | `boolean` | No | `true` if excluded from standalone documentation generation based on configuration. |

---

## 🔍 Extraction & Partition Logic

### 1. Table Name and Partition Type (`source_type`)
- **TMDL (`tables/<TableName>.tmdl`)**:
  - `name`: parsed from `table <Name>` or `table '<Name>'`. Quotes are stripped.
  - If the header has a DAX formula (`table Name = <DAX Expression>`) or contains `partition ... = calculated`:
    - `source_type` = `"CalculatedTable"`.
  - If it contains `partition ... = entity`:
    - `source_type` = `"InheritedEntity"`.
    - `is_inherited` = `true`.
    - Reads `entityName` into `inherited_entity_name`.
    - Reads `expressionSource` into `inherited_expression_source`.
  - If it contains `calculationGroup`:
    - `source_type` = `"CalculationGroup"`.
  - If it contains `partition ... = m` with `source = let ...`:
    - `source_type` = `"PowerQuery"`.
- **TMSL (`model.bim`)**:
  - `name`: read from `tbl["name"]`.
  - Partitions read from `tbl["partitions"]`:
    - If `source.type == "entity"` or `entityName` is present: `source_type = "InheritedEntity"`.
    - If `source.type == "calculated"` or DAX in `source.expression`: `source_type = "CalculatedTable"`.
    - If `source.type == "m"`: `source_type = "PowerQuery"`.
    - If `tbl.calculationGroup` is present: `source_type = "CalculationGroup"`.

---

## 🧠 Role Classification Algorithm (`StarSchemaResolver`)

The classifier in `pbip_doc/star_schema.py` evaluates table relationships and column statistics to determine each table's role and compute a `confidence_score` (`0.0` to `1.0`):

```text
               ┌────────────────────────────────────────────────────────┐
               │           Relational & Topological Evaluation          │
               └───────────────────────────┬────────────────────────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────────────┐
          ▼                                ▼                                ▼
   [Pure Many Endpoints]            [Pure One Endpoints]           [No Relationships]
   Filtered by multiple Dims        Filters Facts, not filtered    Disconnected tables
          │                                │                                │
          ▼                                ▼                                ▼
        FACT                           DIMENSION                    PARAMETER_UTILITY
   (or BRIDGE if N:N)               (or DATE_DIMENSION)                     │
          │                                │                                │
          │                                ▼                                │
          │                   [Parent of another Dimension                  │
          │                    with no direct Fact links]                   │
          │                                │                                │
          │                                ▼                                │
          │                        LOOKUP_OUTRIGGER                         │
          │                                                                 │
          └─────────────────────────────────────────────────────────────────┘
```

### Classification Criteria:

1. **`FACT`**:
   - Lies on the "Many" side of 1:N relationships from one or more dimension tables.
   - Does not filter other tables downstream.
   - Has a high percentage of numeric columns or foreign keys (> 50%).
   - Criteria logged: `"Topology: Pure Many-side endpoint filtering"`, `"High numeric column density (> X%)"`.

2. **`DIMENSION`**:
   - Lies on the "One" side of 1:N relationships pointing to Fact tables.
   - Contains unique primary keys (`isKey = true`) or mostly descriptive text columns.
   - Criteria logged: `"Topology: Filters fact tables (out-degree > 0)"`, `"Text/categorical attribute density"`.

3. **`LOOKUP_OUTRIGGER` (Snowflake)**:
   - Lies on the "One" side of a relationship coming from another Dimension, but **does not directly filter any Fact table**.
   - Normalizes a dimension hierarchy (e.g. `DimGeography` -> `DimCountry`).
   - Criteria logged: `"Topology: Outrigger parent table of dimension DimX with no direct fact links"`.

4. **`DATE_DIMENSION`**:
   - Contains standard date attributes (columns with `dataType: dateTime`, names like `Date`, `Year`, `Month`).
   - Or generated via DAX functions like `CALENDAR(...)` or `CALENDARAUTO(...)`.
   - Criteria logged: `"Temporal attributes: [Date, Year, Month]"`, `"DAX Date table generator: CALENDAR"`.

5. **`BRIDGE`**:
   - Intermediate table participating in Many-to-Many (`N:N`) relationships, or a bidirectional bridge resolving different granularities.
   - Criteria logged: `"Bridge: participates in N:N relationship or bidirectional bridge"`.

6. **`CALCULATION_GROUP`**:
   - Defines calculation items for dynamic formatting or reusable calculation patterns.

7. **`PARAMETER_UTILITY`**:
   - Disconnected table (zero inbound and zero outbound relationships), typically used for what-if parameters or slicers.

---

## 💡 Example JSON

```json
{
  "name": "FactInternetSales",
  "role": "FACT",
  "classification_reasoning": {
    "role": "FACT",
    "confidence_score": 0.95,
    "criteria_matched": [
      "Topology: Pure Many-side endpoint filtering",
      "High numeric column density (72.5%)",
      "Inbound 1:N relationships from 4 dimension tables"
    ],
    "details": {
      "inbound_many_relations": 4,
      "outbound_one_relations": 0,
      "numeric_columns_count": 8,
      "total_columns_count": 11
    }
  },
  "is_hidden": false,
  "description": "Fact table containing e-commerce sales transactions.",
  "source_type": "PowerQuery",
  "direct_related_tables": ["DimCustomer", "DimDate", "DimProduct", "DimPromotion"],
  "connected_dimensions": ["DimCustomer", "DimDate", "DimProduct", "DimPromotion"],
  "connected_facts": [],
  "reachable_lookup_tables": ["DimGeography", "DimCountry", "DimProductCategory", "DimProductSubcategory"],
  "is_inherited": false,
  "inherited_entity_name": null,
  "inherited_expression_source": null,
  "out_of_scope": false
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: How does the engine distinguish a DIMENSION from a LOOKUP_OUTRIGGER?
**A**: A table is a `DIMENSION` if it directly filters at least one `FACT` table on the "One" side of a relationship. A table is a `LOOKUP_OUTRIGGER` if it sits on the "One" side of a relationship coming from another dimension, but has no direct relationship pointing to a `FACT`.

### Q: What if a table has no relationships at all?
**A**: Disconnected tables are classified as `PARAMETER_UTILITY`. These are commonly used for what-if parameters, metric pickers, or static disconnected slicers.

### Q: Why does classification include a confidence_score?
**A**: The `confidence_score` reflects how many distinct heuristics agreed on the role (e.g. relationship endpoints, numeric vs text density, presence of primary keys). A score of 0.95 means multiple strong heuristics aligned.
