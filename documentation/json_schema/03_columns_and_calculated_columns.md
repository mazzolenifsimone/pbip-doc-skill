---
title: "03. Physical and DAX Calculated Columns"
target_json_path: "/tables[]/columns[]"
python_module: "pbip_doc/parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["columns", "calculated_columns", "dax", "data_types", "is_key", "format_string"]
---

# 03. Physical and DAX Calculated Columns (`tables[].columns[]`)

> **TL;DR**:
> - Details all columns defined on each table, distinguishing physical source columns from DAX calculated columns.
> - Calculated columns have `is_calculated: true` and preserve their full formula in `expression`.
> - Primary key columns are flagged with `is_key: true`.
> - Multiline DAX formulas, pipe characters (`||`, `|`), and line breaks are fully parsed and preserved safely.

---

## 📋 Column Properties Schema

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `name` | `string` | No | Column name (quotes stripped). |
| `data_type` | `string` | No | Tabular data type (`string`, `int64`, `decimal`, `double`, `dateTime`, `boolean`, `binary`). Default: `"string"`. |
| `is_hidden` | `boolean` | No | `true` if hidden from the report field list (`isHidden: true`). |
| `is_key` | `boolean` | No | `true` if marked as the primary key of the table (`isKey: true`). |
| `is_calculated` | `boolean` | No | `true` for DAX calculated columns; `false` for physical source columns. |
| `format_string` | `string` | Yes | Numeric, currency, or date format string (e.g. `"$#,0.00"`, `"0.0%"`). |
| `description` | `string` | Yes | Column description defined in metadata. |
| `expression` | `string` | Yes | Full DAX formula if calculated (`is_calculated: true`); otherwise `null`. |
| `display_folder` | `string` | Yes | Logical display folder in the Power BI field list (`displayFolder`). |

---

## 🔍 Extraction & Detection Logic

### 1. TMDL Format (`tables/<TableName>.tmdl`)

In TMDL, columns are declared under the `column` keyword within the table block.

#### Standard Physical Columns
```text
column CustomerID
    dataType: int64
    isKey
    formatString: 0
    displayFolder: "Identifiers"
    description: "Unique customer identifier"
```
- **Name**: matched from `column <Name>` or `column '<Name>'`.
- **Properties**: extracted from the indented body:
  - `dataType: <type>` -> `data_type`
  - `isKey` -> `is_key = true`
  - `isHidden` -> `is_hidden = true`
  - `formatString: <val>` -> `format_string`
  - `displayFolder: <val>` -> `display_folder`
  - `description: <val>` -> `description`

#### DAX Calculated Columns
In TMDL, calculated columns are declared on single or multiple lines using `=`:

```text
column Margin = DimProduct[ListPrice] - DimProduct[StandardCost]
    dataType: decimal
    formatString: $#,0.00

column MarginRate =
        DIVIDE(
            DimProduct[ListPrice] - DimProduct[StandardCost],
            DimProduct[ListPrice],
            0
        )
    dataType: double
    formatString: 0.0%
```

- **Detection**: when an `=` sign is found on the declaration line, the column is marked as `is_calculated = true`.
- **Formula Extraction**: the DAX formula is extracted by isolating it from trailing TMDL property keywords (`dataType:`, `formatString:`, `lineageTag:`, etc.), preserving line breaks, indentation, and operators like `||` and `&&`.

---

### 2. TMSL Format (`model.bim`)

In `model.bim`, columns reside in `tables[].columns`:
- `name`: read directly from `col["name"]`.
- `data_type`: read from `col["dataType"]` (defaults to `"string"` if omitted).
- `is_hidden`: read from `col["isHidden"]` (default: `false`).
- `is_key`: read from `col["isKey"]` (default: `false`).
- `is_calculated`: set to `true` if:
  - `col["type"] == "calculated"` or
  - `col["expression"]` is present and non-empty.
- `expression`: contains the DAX formula string (or lines joined by `\n` if represented as an array).
- `format_string`: read from `col["formatString"]`.
- `description`: read from `col["description"]`.
- `display_folder`: read from `col["displayFolder"]`.

---

## 💡 Example JSON

```json
[
  {
    "name": "CustomerKey",
    "data_type": "int64",
    "is_hidden": false,
    "is_key": true,
    "is_calculated": false,
    "format_string": "0",
    "description": "Surrogate primary key for the customer.",
    "expression": null,
    "display_folder": "Keys"
  },
  {
    "name": "Full Name",
    "data_type": "string",
    "is_hidden": false,
    "is_key": false,
    "is_calculated": true,
    "format_string": null,
    "description": "Calculated concatenation of First and Last Name.",
    "expression": "DimCustomer[FirstName] & \" \" & DimCustomer[LastName]",
    "display_folder": null
  },
  {
    "name": "IncomeCategory",
    "data_type": "string",
    "is_hidden": false,
    "is_key": false,
    "is_calculated": true,
    "format_string": null,
    "description": "Yearly income segmentation.",
    "expression": "IF(\n    DimCustomer[YearlyIncome] >= 100000,\n    \"High\",\n    IF(DimCustomer[YearlyIncome] >= 50000, \"Medium\", \"Low\")\n)",
    "display_folder": "Demographics"
  }
]
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: How does the parser differentiate between a calculated column and a physical column?
**A**: In TMDL, a column is calculated if an `=` sign appears on its declaration line. In BIM, it is calculated if `type == "calculated"` or if a non-empty `expression` property is present.

### Q: Are hidden columns included in the JSON?
**A**: Yes. Hidden columns are included with `is_hidden: true`. They are critical for modeling context, foreign key relationships, and sorting orders.

### Q: What is the fallback if a column has no explicit data type?
**A**: If `dataType` is omitted in the model metadata, the engine defaults to `"string"`.
