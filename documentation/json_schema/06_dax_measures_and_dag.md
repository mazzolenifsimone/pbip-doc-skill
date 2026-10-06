---
title: "06. DAX Measures and Dependency DAG"
target_json_path: "/measures[], /measure_dependency_dag"
python_module: "pbip_doc/measure_analyzer.py, pbip_doc/parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["measures", "dax", "dag", "calculation_depth", "upstream", "downstream", "dependencies"]
---

# 06. DAX Measures and Dependency DAG (`measures[]` and `measure_dependency_dag`)

> **TL;DR**:
> - Analyzes all DAX measures, their host tables, formatting, and formulas.
> - Computes hierarchical `calculation_depth`: 0 for base measures aggregating columns, and $\max(\text{upstream}) + 1$ for composite measures.
> - Resolves direct measure calls (`direct_measure_dependencies`) and full transitive closures (`all_upstream_measures`).
> - Generates an inverted downstream impact index (`downstream_measures`) showing which measures are affected by changes.
> - Preserves top-level dependency adjacency in `measure_dependency_dag`.

---

## 📋 Measure Properties Schema (`measures[]`)

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `name` | `string` | No | Measure name (e.g. `"Total Sales"`, `"Margin %"`). |
| `table` | `string` | No | Host table where the measure is defined. |
| `dax_expression` | `string` | No | Complete DAX formula of the measure. |
| `format_string` | `string` | Yes | Numeric, percentage, or currency format string (`formatString`). |
| `description` | `string` | Yes | Measure description defined in metadata. |
| `is_hidden` | `boolean` | No | `true` if hidden from the report view (`isHidden: true`). |
| `display_folder` | `string` | Yes | Folder grouping in the field list (`displayFolder`). |
| `calculation_depth` | `integer` | No | Hierarchical calculation depth in the DAG (`0`, `1`, `2`, ...). |
| `direct_measure_dependencies`| `array[string]` | No | Measures directly called within the DAX formula. |
| `all_upstream_measures` | `array[string]` | No | Complete transitive closure of all ancestor measures needed for this calculation. |
| `referenced_functions` | `array[string]` | No | Custom DAX UDF functions directly invoked in the formula. |
| `referenced_columns` | `array[object]` | No | Table columns referenced: `[{"table": "...", "column": "..."}]`. |
| `referenced_tables` | `array[string]` | No | Unique list of tables containing the referenced columns. |
| `downstream_measures` | `array[string]` | No | Reverse index: all measures in the model that depend on this measure. |
| `is_inherited` | `boolean` | No | `true` if inherited from a central model (e.g. via `EXTERNALMEASURE`). |
| `is_external_measure` | `boolean` | No | `true` if defined with the DAX function `EXTERNALMEASURE(...)`. |
| `out_of_scope` | `boolean` | No | `true` if excluded from standalone documentation generation. |

---

## 🔍 DAX Tokenization & Resolution (`MeasureDependencyResolver`)

The analyzer in `pbip_doc/measure_analyzer.py` performs lexical scanning of each DAX formula to extract:
1. **Referenced Measures** (`[MeasureName]`):
   - In DAX, measures can be written as `[MeasureName]` or `'TableName'[MeasureName]`.
   - The engine checks tokens against the global measure catalog to disambiguate measures from unqualified column references.
2. **Referenced Columns** (`'TableName'[ColumnName]` or `TableName[ColumnName]`):
   - Extracts `{ "table": "<TableName>", "column": "<ColumnName>" }`.
   - If the referenced table was excluded from the model, the reference is purged.
3. **Custom DAX Functions (UDFs)**:
   - Identifies custom function calls by comparing identifiers against the model's function registry (see [`07_user_defined_functions.md`](./07_user_defined_functions.md)).

---

## 🧮 Calculation Depth (`calculation_depth`)

The `calculation_depth` property indicates the hierarchical level of a measure in the Directed Acyclic Graph (DAG):

```text
  [Physical Columns / Table]
              │
              ▼
    [Depth 0: Base Measure]        --> Total Sales = SUM(Sales[Amount])
              │
              ▼
   [Depth 1: Composite Measure]    --> Total Margin = [Total Sales] - [Total Cost]
              │
              ▼
   [Depth 2: KPI / Ratios]         --> Margin % = DIVIDE([Total Margin], [Total Sales])
```

- **Depth 0 (Base Measure)**:
  - Measures that **do not reference any other measure** (`direct_measure_dependencies` is empty).
  - They aggregate physical table columns directly or compute scalar values.
- **Depth N (Composite Measure)**:
  - Measures that call one or more existing measures.
  - Calculated recursively as:
    $$\text{calculation\_depth} = \max(\{\text{depth}(m) \mid m \in \text{direct\_dependencies}\}) + 1$$
- **Cycle Safety**:
  - If unexpected recursive or circular references occur, traversal stops safely to prevent infinite loops.

---

## 🔄 Upstream & Downstream Dependency Trees

1. **`all_upstream_measures`**:
   - Built using depth-first graph traversal: if measure $A$ calls $B$ and $B$ calls $C$, then for $A$:
     - `direct_measure_dependencies` = `["B"]`
     - `all_upstream_measures` = `["B", "C"]`
2. **`downstream_measures`**:
   - Reverse index: indicates which measures will be affected if the current measure is modified.

---

## 💡 Example JSON

```json
{
  "name": "Margin %",
  "table": "FactInternetSales",
  "dax_expression": "DIVIDE([Total Margin], [Total Sales], 0)",
  "format_string": "0.0%",
  "description": "Margin percentage calculated over total sales.",
  "is_hidden": false,
  "display_folder": "Profitability",
  "calculation_depth": 2,
  "direct_measure_dependencies": ["Total Margin", "Total Sales"],
  "all_upstream_measures": ["Total Cost", "Total Margin", "Total Sales"],
  "referenced_functions": [],
  "referenced_columns": [],
  "referenced_tables": [],
  "downstream_measures": ["Stretch Margin KPI"],
  "is_inherited": false,
  "is_external_measure": false,
  "out_of_scope": false
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: How does the tokenizer tell `[Column]` apart from `[Measure]`?
**A**: When a token appears without a table qualifier (e.g. `[Total Sales]`), the resolver checks whether `Total Sales` exists in the model's measure dictionary. If it does, it is cataloged as a measure dependency; otherwise, it is treated as a column reference.

### Q: What is the difference between direct_measure_dependencies and all_upstream_measures?
**A**: `direct_measure_dependencies` lists only the measures called directly in the formula string. `all_upstream_measures` is the full transitive closure of all ancestor measures required across the entire calculation chain.

### Q: Why is downstream_measures useful for agents and developers?
**A**: It acts as an impact analysis index. If a developer or agent refactors a base measure (e.g. `[Total Sales]`), `downstream_measures` immediately identifies every composite measure that could be affected.
