---
title: "07. Custom DAX Functions"
target_json_path: "/functions[]"
python_module: "pbip_doc/parser.py, pbip_doc/measure_analyzer.py"
source_formats: ["TMDL", "BIM"]
tags: ["functions", "udf", "dax", "parameters", "signature", "user_defined_functions"]
---

# 07. Custom DAX Functions (`functions[]`)

> **TL;DR**:
> - Documents user-defined DAX functions (UDFs) available in Microsoft Fabric / Tabular semantic models.
> - Extracts full signatures, return types, and typed parameters with default values (`FunctionParameter`).
> - Automatically links downstream measures and other functions that call each UDF.

---

## 📋 Function Properties Schema (`functions[]`)

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `name` | `string` | No | Name of the UDF function. |
| `expression` | `string` | No | DAX formula implementing the function. |
| `parameters` | `array[object]` | No | Structured list of accepted parameters (`FunctionParameter`). |
| `parameters_signature` | `string` | No | Full signature string in parentheses (e.g. `"(Numerator: double, Denominator: double, Alt: double = 0)"`). |
| `return_type` | `string` | Yes | Returned data type (e.g. `"double"`, `"string"`, `"variant"`). |
| `description` | `string` | Yes | Semantic description of the function. |
| `is_hidden` | `boolean` | No | `true` if hidden from the report interface. |
| `lineage_tag` | `string` | Yes | Unique lineage tag from TMDL/BIM. |
| `referenced_functions` | `array[string]` | No | Other UDF functions called inside this function. |
| `referenced_columns` | `array[object]` | No | Columns referenced in the formula: `[{"table": "...", "column": "..."}]`. |
| `referenced_tables` | `array[string]` | No | Tables containing the referenced columns. |
| `downstream_measures` | `array[string]` | No | Measures in the model that invoke this function. |
| `downstream_functions` | `array[string]` | No | Other UDF functions that call this function. |

---

## 🧩 Parameter Schema (`parameters[]` -> `FunctionParameter`)

Each parameter entry in the `parameters` array has the following structure:

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `name` | `string` | No | Parameter name (e.g. `"Numerator"`). |
| `data_type` | `string` | Yes | Expected data type (e.g. `"double"`, `"int64"`, `"string"`). |
| `is_optional` | `boolean` | No | `true` if optional (contains a default value assignment). |
| `default_value` | `string` | Yes | Default fallback value (e.g. `"0"`, `"\"Default\""`). |
| `description` | `string` | Yes | Parameter description (if provided). |

---

## 🔍 Extraction & Detection Logic

### 1. TMDL Format
In TMDL, functions are declared with the `function` keyword:

```text
function SafeDivide = (Numerator: double, Denominator: double, AltValue: double = 0) =>
        IF(
            Denominator == 0,
            AltValue,
            Numerator / Denominator
        )
    dataType: double
    description: "Safe division with fallback value"
```

- **Signature & Parameters**: `PBIPParser._parse_function_parameters()` parses the string inside parentheses preceding `=>`.
- Each comma-separated token is analyzed to extract the parameter name, optional type annotation (`: double`), and optional default value (`= 0`).
- **Body & Attributes**: the portion following `=>` represents the calculation formula, cleaned of trailing metadata lines (`dataType:`, `description:`, `lineageTag:`, `isHidden`).

### 2. TMSL Format (`model.bim`)
In `model.bim`, functions are defined in `model.functions`:
- `name`: from `fn["name"]`.
- `expression`: from `fn["expression"]`.
- `parameters`: from `fn["parameters"]`.
- `return_type`: from `fn["dataType"]`.

### 3. Downstream Dependency Tracking
In `_enrich_and_resolve()` and `MeasureDependencyResolver`:
- When a measure's DAX formula calls a registered UDF function (e.g. `SafeDivide(...)`), the measure is automatically added to `downstream_measures` on the function, and the function is recorded in `referenced_functions` on the measure.

---

## 💡 Example JSON

```json
{
  "name": "SafeDivide",
  "expression": "IF(Denominator == 0, AltValue, Numerator / Denominator)",
  "parameters": [
    {
      "name": "Numerator",
      "data_type": "double",
      "is_optional": false,
      "default_value": null,
      "description": null
    },
    {
      "name": "Denominator",
      "data_type": "double",
      "is_optional": false,
      "default_value": null,
      "description": null
    },
    {
      "name": "AltValue",
      "data_type": "double",
      "is_optional": true,
      "default_value": "0",
      "description": null
    }
  ],
  "parameters_signature": "(Numerator: double, Denominator: double, AltValue: double = 0)",
  "return_type": "double",
  "description": "Safe division returning an alternative value when the denominator is zero.",
  "is_hidden": false,
  "lineage_tag": "fn-safedivide-001",
  "referenced_functions": [],
  "referenced_columns": [],
  "referenced_tables": [],
  "downstream_measures": ["Margin %", "Discount Rate"],
  "downstream_functions": []
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: What distinguishes a custom function from a measure?
**A**: Custom functions (UDFs) accept parameterized inputs through a declared signature (e.g. `(Numerator: double, Denominator: double) => ...`) and can be called from multiple measures, functioning like reusable helper methods.

### Q: Are functions included if no measure calls them?
**A**: Yes. All functions defined in the semantic model are extracted into `functions[]`, with `downstream_measures` being empty (`[]`) if currently unused.

### Q: Can custom functions reference columns directly?
**A**: Yes. If a function expression references table columns, they are captured in `referenced_columns` and `referenced_tables`.
