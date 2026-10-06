---
title: "09. Composite Models, Inherited Entities & External Measures"
target_json_path: "/tables[], /measures[] (is_inherited, out_of_scope)"
python_module: "pbip_doc/parser.py, pbip_doc/docgen/config.py"
source_formats: ["TMDL", "BIM"]
tags: ["composite_models", "thin_reports", "entity", "externalmeasure", "out_of_scope", "golden_dataset"]
---

# 09. Composite Models, Inherited Entities & External Measures

> **TL;DR**:
> - Detects inherited tables defined with `partition = entity` in composite models and thin reports connected to central Golden Datasets.
> - Detects remote measures coming from the central model via the DAX function `EXTERNALMEASURE(...)`.
> - Marks inherited entities with `out_of_scope: true` by default to avoid generating redundant duplicate documentation files.
> - Preserves inherited entities in the JSON graph, catalogs, and measure DAG so local calculations can reference them without broken links.

---

## 🏛️ Architecture Context

In organizations using a central *Golden Dataset*, downstream reports (*thin reports*) often connect via DirectQuery rather than importing all tables. In this setup:
- Central tables appear with an **`entity`** partition type.
- Measures from the central model are mapped locally using the DAX system function **`EXTERNALMEASURE(...)`**.
- Analysts can create **local measures** (report-specific KPIs) or import **local tables** (Excel sheets, targets).

---

## 📋 Inheritance Fields in the JSON Schema

### 1. On Tables (`TableDefinition`)

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `is_inherited` | `boolean` | No | `true` if the table is inherited via an `entity` partition. |
| `inherited_entity_name` | `string` | Yes | Entity name in the remote source model. |
| `inherited_expression_source`| `string` | Yes | Remote source or connector name (e.g. `"DatabaseQuery"`). |
| `out_of_scope` | `boolean` | No | `true` if excluded from standalone document generation (`include_inherited_entities: false`). |

### 2. On Measures (`MeasureDefinition`)

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `is_inherited` | `boolean` | No | `true` if the measure comes from the central model (`is_external_measure == true`). |
| `is_external_measure` | `boolean` | No | `true` if the DAX formula calls `EXTERNALMEASURE(...)`. |
| `out_of_scope` | `boolean` | No | `true` if the external measure should not produce a standalone Markdown file. |

---

## 🔍 Extraction & Detection Logic

### 1. Inherited Tables (`partition = entity`)
- **TMDL (`tables/<TableName>.tmdl`)**:
  ```text
  partition Customer = entity
      mode: directQuery
      source
          entityName: DimCustomer
          expressionSource: CentralDataModel
  ```
  - Detects `partition ... = entity`.
  - Sets `source_type = "InheritedEntity"`.
  - Sets `is_inherited = true`.
  - Reads `entityName` into `inherited_entity_name`.
  - Reads `expressionSource` into `inherited_expression_source`.
  - Creates a synthetic `PowerQuerySource`:
    - `source_type = "INHERITED_ENTITY"`
    - `connection_string = "Entity: DimCustomer (Source: CentralDataModel)"`
- **TMSL (`model.bim`)**:
  - Matches `"type": "entity"` or the presence of `"entityName"` in partitions.

### 2. External Measures (`EXTERNALMEASURE`)
- In Power BI, measures inherited from an external DirectQuery model use:
  ```dax
  EXTERNALMEASURE("Total Sales", DOUBLE, "CentralDataModel")
  ```
- **Detection**: matches case-insensitive regex `^\s*EXTERNALMEASURE\s*\(`.
- Sets `is_inherited = true`, `is_external_measure = true`.
- **Local report measures** (e.g. `[Local Margin] = [Total Sales] * 0.2`) do not use `EXTERNALMEASURE`, so they remain `is_inherited = false` and `out_of_scope = false`.

---

## ⚙️ Rules for the `out_of_scope` Flag

The `out_of_scope` flag indicates to document generators whether an entity should be skipped from standalone file output, without removing it from the metadata graph:

1. **Default Setting (`include_inherited_entities: false`)**:
   - `tbl.out_of_scope = tbl.is_inherited` -> `true` for inherited tables.
   - `m.out_of_scope = m.is_external_measure` -> `true` for external measures.
   - **Goal**: avoids cluttering thin reports with redundant duplicate copies of central model documentation.
2. **Explicit Setting (`include_inherited_entities: true`)**:
   - `tbl.out_of_scope = false` for all tables and measures.
3. **Graph Integrity**:
   - Even when `out_of_scope == true`, entities **remain present in the JSON** (`tables[]` and `measures[]`), in catalogs, and in the dependency DAG so that local measures can reference them without generating broken links.

---

## 💡 Example JSON

```json
{
  "tables": [
    {
      "name": "Customer",
      "role": "DIMENSION",
      "source_type": "InheritedEntity",
      "is_inherited": true,
      "inherited_entity_name": "DimCustomer",
      "inherited_expression_source": "CentralDataModel",
      "out_of_scope": true,
      "root_data_sources": [
        {
          "source_type": "INHERITED_ENTITY",
          "connection_string": "Entity: DimCustomer (Source: CentralDataModel)",
          "endpoint_or_path": "DimCustomer"
        }
      ]
    }
  ],
  "measures": [
    {
      "name": "Total Sales",
      "table": "Customer",
      "dax_expression": "EXTERNALMEASURE(\"Total Sales\", DOUBLE, \"CentralDataModel\")",
      "calculation_depth": 0,
      "is_inherited": true,
      "is_external_measure": true,
      "out_of_scope": true
    },
    {
      "name": "Local Sales Target",
      "table": "Customer",
      "dax_expression": "[Total Sales] * 1.15",
      "calculation_depth": 1,
      "direct_measure_dependencies": ["Total Sales"],
      "is_inherited": false,
      "is_external_measure": false,
      "out_of_scope": false
    }
  ]
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why are inherited tables and external measures kept in the JSON if they are marked out_of_scope?
**A**: Local measures and local tables often depend on central tables (via relationships or DAX formulas). Removing them from the JSON would break the dependency graph and produce missing reference errors in downstream tools.

### Q: How can I generate standalone Markdown files for inherited entities?
**A**: Set `"include_inherited_entities": true` in `pbip_doc.config.json` or pass the CLI flag `--include-inherited-entities`.

### Q: How does the engine tell local measures apart from external measures inside an inherited table?
**A**: External measures generated by Power BI use the DAX formula pattern `EXTERNALMEASURE(...)`. Any measure authored locally in the report contains regular DAX code and does not use `EXTERNALMEASURE`.
