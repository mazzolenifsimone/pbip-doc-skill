---
title: "05. Relationships and Star Schema"
target_json_path: "/relationships[], /star_schema"
python_module: "pbip_doc/star_schema.py, pbip_doc/parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["relationships", "cardinality", "star_schema", "snowflake", "join_keys", "cross_filtering"]
---

# 05. Relationships and Star Schema (`relationships[]` and `star_schema`)

> **TL;DR**:
> - Normalizes all model relationships so that `from_table` is consistently the "Many" side (Foreign Key) for 1:N relations.
> - Captures relationship state (active vs inactive), filtering direction (`Single` vs `Both`), and RLS security behavior.
> - Provides a model-wide `star_schema` summary grouping tables into Fact, Dimension, Outrigger, Date, Bridge, and Utility tables.
> - Computes full transitive `SnowflakePath` chains tracing Fact -> Dimension -> Outrigger with exact join keys.

---

## 📋 Relationships Schema (`relationships[]`)

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `id` | `string` | No | Unique identifier of the relationship. |
| `from_table` | `string` | No | Source table (normalized to the "Many" side for 1:N relationships). |
| `from_column` | `string` | No | Source key column (Foreign Key). |
| `to_table` | `string` | No | Target table (the "One" side for 1:N relationships). |
| `to_column` | `string` | No | Target key column (Primary Key). |
| `cardinality` | `string` | No | Standardized cardinality: `"1:N"`, `"N:1"`, `"1:1"`, `"N:N"`. |
| `cross_filtering_behavior`| `string` | No | Cross-filtering direction: `"Single"` or `"Both"`. |
| `is_active` | `boolean` | No | `true` if active; `false` if inactive (used with `USERELATIONSHIP`). |
| `security_filtering_behavior`| `string`| Yes | Row-Level Security (RLS) behavior: `"None"`, `"Both"`. Default: `"None"`. |

---

## 🔍 Cardinality Normalization Logic

In Power BI, a relationship can be declared with either side as `from` or `to`. To keep downstream algorithms consistent, the engine normalizes all 1:N relationships:

1. **Many-to-One Inversion**:
   - If source metadata specifies `fromCardinality == "one"` and `toCardinality == "many"`, the engine inverts the pair:
     - `from_table` and `to_table` are swapped.
     - `from_column` and `to_column` are swapped.
     - Cardinality is normalized to `"1:N"`.
     - This ensures that `from_table` always represents the Foreign Key (Many side).
2. **Standard String Formats**:
   - `"OneToMany"` and `"1:N"` -> `"1:N"`
   - `"ManyToOne"` and `"N:1"` -> `"1:N"` (with swapped endpoints)
   - `"OneToOne"` and `"1:1"` -> `"1:1"`
   - `"ManyToMany"` and `"N:N"` -> `"N:N"`

---

## ❄️ Star Schema & Snowflake Topology (`star_schema`)

The `star_schema` object provides a high-level view of the relational structure:

| JSON Property | Data Type | Description |
|---|---|---|
| `fact_tables` | `array[string]` | List of tables classified as `FACT`. |
| `dimension_tables` | `array[string]` | List of tables classified as `DIMENSION` (including date dimensions). |
| `lookup_outrigger_tables` | `array[string]` | List of tables classified as `LOOKUP_OUTRIGGER` (snowflake lookups). |
| `bridge_tables` | `array[string]` | List of `BRIDGE` tables (Many-to-Many relationships). |
| `date_tables` | `array[string]` | List of `DATE_DIMENSION` tables. |
| `utility_tables` | `array[string]` | List of disconnected `PARAMETER_UTILITY` tables. |
| `fact_dimension_map` | `object` | Map of `{ "FactTable": ["Dim1", "Dim2", ...] }` with direct dimensions. |
| `fact_to_outriggers_map` | `object` | Map of `{ "FactTable": ["Lookup1", "Lookup2", ...] }` with transitive lookups. |
| `snowflake_paths` | `array[object]` | Detailed list of all resolved transitive paths (`SnowflakePath`). |

---

## 🛤️ Snowflake Path Resolution (`SnowflakePath`)

The engine traverses the relationship graph recursively starting from each Fact table to identify all parent dimension chains:

$$\text{Fact} \xrightarrow{\text{1:N}} \text{Dimension} \xrightarrow{\text{1:N}} \text{Lookup}_1 \xrightarrow{\text{1:N}} \text{Lookup}_2$$

Each path is modeled as a `SnowflakePath` object:

| JSON Property | Data Type | Description |
|---|---|---|
| `fact_table` | `string` | Starting Fact table (e.g. `"FactInternetSales"`). |
| `dimension_table` | `string` | First connected dimension table (e.g. `"DimCustomer"`). |
| `lookup_table` | `string` | Target lookup table reached at the end of the chain (e.g. `"DimCountry"`). |
| `path` | `array[string]` | Ordered table sequence: `["FactInternetSales", "DimCustomer", "DimGeography", "DimCountry"]`. |
| `join_keys` | `array[object]` | Join key pairs for each hop: `[{"from": "TableA.ColA", "to": "TableB.ColB"}]`. |
| `hops` | `integer` | Number of intermediate hops (`1` for Dim -> Lookup, `2` for Dim -> Lookup -> Lookup). |

---

## 💡 Example JSON

```json
{
  "relationships": [
    {
      "id": "rel_sales_customer",
      "from_table": "FactInternetSales",
      "from_column": "CustomerKey",
      "to_table": "DimCustomer",
      "to_column": "CustomerKey",
      "cardinality": "1:N",
      "cross_filtering_behavior": "Single",
      "is_active": true,
      "security_filtering_behavior": "None"
    },
    {
      "id": "rel_customer_geography",
      "from_table": "DimCustomer",
      "from_column": "GeographyKey",
      "to_table": "DimGeography",
      "to_column": "GeographyKey",
      "cardinality": "1:N",
      "cross_filtering_behavior": "Single",
      "is_active": true,
      "security_filtering_behavior": "None"
    }
  ],
  "star_schema": {
    "fact_tables": ["FactInternetSales"],
    "dimension_tables": ["DimCustomer", "DimDate", "DimProduct"],
    "lookup_outrigger_tables": ["DimGeography", "DimCountry"],
    "bridge_tables": [],
    "date_tables": ["DimDate"],
    "utility_tables": [],
    "fact_dimension_map": {
      "FactInternetSales": ["DimCustomer", "DimDate", "DimProduct"]
    },
    "fact_to_outriggers_map": {
      "FactInternetSales": ["DimGeography", "DimCountry"]
    },
    "snowflake_paths": [
      {
        "fact_table": "FactInternetSales",
        "dimension_table": "DimCustomer",
        "lookup_table": "DimGeography",
        "path": ["FactInternetSales", "DimCustomer", "DimGeography"],
        "join_keys": [
          {"from": "FactInternetSales.CustomerKey", "to": "DimCustomer.CustomerKey"},
          {"from": "DimCustomer.GeographyKey", "to": "DimGeography.GeographyKey"}
        ],
        "hops": 1
      }
    ]
  }
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why does the engine normalize 1:N relationship endpoints?
**A**: In TMDL/BIM files, some relationships are authored with the parent table as `fromTable` and the fact table as `toTable`. Normalizing `from_table` to always be the Many side guarantees that downstream graph traversals and join key builders behave deterministically.

### Q: Are inactive relationships included in Snowflake paths?
**A**: Only active relationships (`is_active: true`) are used by the Snowflake resolver to construct automatic join paths, mirroring Power BI's default filter propagation behavior.

### Q: What is the maximum number of hops in a Snowflake path?
**A**: The resolver traverses outriggers transitively until reaching leaf dimensions. Each hop increments `hops` by 1 and appends the join keys to `join_keys`.
