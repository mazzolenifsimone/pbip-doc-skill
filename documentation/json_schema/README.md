---
title: "JSON Schema Reference & Field Mapping"
target_json_path: "/"
python_module: "pbip_doc/model_schema.py"
source_formats: ["TMDL", "BIM"]
tags: ["schema", "reference", "metadata", "json", "data_contracts"]
---

# JSON Schema Reference & Field Mapping

> **TL;DR**:
> - This documentation explains how every field in the output JSON (`semantic_model_documentation.json`) is populated.
> - The output JSON is the single source of truth produced by the Core Dependency Engine (Phase 1).
> - Works consistently across both TMDL folder structures and TMSL `model.bim` files without external dependencies.
> - Structured for easy navigation by developers and automated agents.

---

## 🏛️ JSON Architecture Overview

The output JSON file represents the complete, normalized structure of a Power BI / Microsoft Fabric semantic model (`.pbip`):

```text
PBIPSemanticModel (Root JSON)
├── General Metadata (model_name, source_format, compatibility_level, culture, created_timestamp)
├── tables[] (TableDefinition)
│   ├── Table Properties (name, role, source_type, is_hidden, description, is_inherited, out_of_scope)
│   ├── classification_reasoning (TableRoleClassification: confidence, criteria, details)
│   ├── columns[] (ColumnDefinition: name, data_type, is_calculated, expression, format_string, is_key)
│   ├── incremental_refresh_policy (IncrementalRefreshPolicy: periods, granularity, mode, polling)
│   ├── power_query_lineage (PowerQueryLineageNode) & root_data_sources[] & upstream_queries_chain[]
│   └── Relational Topology (connected_dimensions, connected_facts, reachable_lookup_tables, snowflake_paths)
├── relationships[] (RelationshipDefinition: id, from_table, to_table, cardinality, cross_filtering, is_active)
├── measures[] (MeasureDefinition)
│   ├── Measure Properties (name, table, dax_expression, format_string, is_inherited, out_of_scope)
│   └── Calculation Graph (calculation_depth, direct_measure_dependencies, all_upstream_measures, downstream_measures, referenced_columns)
├── functions[] (FunctionDefinition: DAX UDF, parameters, signature, return_type, downstream_measures)
├── expressions[] / shared_queries[] (PowerQueryLineageNode: staging queries, root sources, inline #table)
├── data_sources_summary[] (PowerQuerySource: unique physical data sources)
├── star_schema (StarSchemaTopology: star schema classification, Fact-Dim maps, and Snowflake paths)
├── measure_dependency_dag (Directed adjacency map of DAX measure dependencies)
└── Exclusions Tracking (excluded_tables_count, excluded_tables_list)
```

---

## 📑 Specification Index

| No. | Document | Corresponding JSON Object | Key Topics |
|---|---|---|---|
| 01 | [`01_model_metadata.md`](./01_model_metadata.md) | Model Root | General metadata, counts, auto-table exclusions, and data sources summary |
| 02 | [`02_tables_and_classification.md`](./02_tables_and_classification.md) | `tables[]` | Tables, partition types, and star schema role classification (Fact, Dim, Outrigger) |
| 03 | [`03_columns_and_calculated_columns.md`](./03_columns_and_calculated_columns.md) | `tables[].columns[]` | Physical columns, DAX calculated columns, data types, and formats |
| 04 | [`04_incremental_refresh_policy.md`](./04_incremental_refresh_policy.md) | `tables[].incremental_refresh_policy` | Incremental refresh policies, historical windows, and hybrid realtime partitions |
| 05 | [`05_relationships_and_star_schema.md`](./05_relationships_and_star_schema.md) | `relationships[]`, `star_schema` | Relationships, cardinality normalization, topology maps, and Snowflake join paths |
| 06 | [`06_dax_measures_and_dag.md`](./06_dax_measures_and_dag.md) | `measures[]`, `measure_dependency_dag` | DAX tokenizer, calculation depth (Depth 0, 1, 2...), upstream and downstream dependencies |
| 07 | [`07_user_defined_functions.md`](./07_user_defined_functions.md) | `functions[]` | Custom DAX functions (UDFs), parameters, return types, and consuming measures |
| 08 | [`08_power_query_lineage_and_inline_tables.md`](./08_power_query_lineage_and_inline_tables.md) | `expressions[]`, `shared_queries[]` | Power Query M lineage, multi-hop staging queries, and inline `#table` parsing |
| 09 | [`09_inherited_entities_composite_models.md`](./09_inherited_entities_composite_models.md) | `is_inherited`, `out_of_scope` | Composite models, inherited entity tables, external measures, and out-of-scope filtering |

---

## ⚙️ Serialization Conventions

- **Pure Python**: serializable using Python's standard `json.dump`, backed by dataclasses in `pbip_doc/model_schema.py`.
- **Empty Values vs Null**:
  - Empty lists are always serialized as `[]` rather than `null`.
  - Empty maps are serialized as `{}`.
  - Optional fields not present in the model are serialized as `null`.
- **Standardized Formats**:
  - Cardinality is always normalized to standard strings (`"1:N"`, `"N:1"`, `"1:1"`, `"N:N"`).
  - Table roles are serialized as uppercase string constants (`"FACT"`, `"DIMENSION"`, `"LOOKUP_OUTRIGGER"`, `"DATE_DIMENSION"`, `"BRIDGE"`, `"CALCULATION_GROUP"`, `"PARAMETER_UTILITY"`, `"UNKNOWN"`).

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why is there a dedicated JSON schema before Markdown generation?
**A**: Separating Phase 1 (metadata extraction and dependency resolution) from Phase 2 (document rendering) makes the JSON a permanent, tool-independent single source of truth. Any downstream tool, report generator, or agent can consume this JSON directly.

### Q: Does the schema differ if the input is TMDL vs BIM?
**A**: No. The engine normalizes both formats into the same unified `PBIPSemanticModel` schema. Only the `source_format` field indicates whether the model came from `"TMDL"` or `"BIM"`.

### Q: Can this JSON be validated against standard JSON Schema tools?
**A**: Yes. The schema maps 1:1 to typed Python dataclasses in `pbip_doc/model_schema.py` and produces standard, well-formed JSON.
