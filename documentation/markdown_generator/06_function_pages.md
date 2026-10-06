---
title: "06. User-Defined Function Pages (UDFs)"
target_path: "docs/functions/<FunctionName>.md"
python_module: "pbip_doc.docgen.function_doc"
tags: ["function", "udf", "dax", "reusable_logic", "parameters"]
---

# 06. User-Defined Function Pages (`docs/functions/<FunctionName>.md`)

> **TL;DR**:
> - Documents modern Tabular User-Defined Functions (DAX UDFs).
> - Documents formal parameter signatures, input data types, and return types.
> - Formats implementation DAX code in highlighted syntax blocks.
> - Maps downstream measures and parent functions that invoke the UDF.
> - Begins with structured YAML frontmatter for searchability.

---

## 📋 Frontmatter Specification

```yaml
---
title: "Function: fn_CalculateGrowthRate"
doc_type: "dax_function_documentation"
function_name: "fn_CalculateGrowthRate"
signature: "(currentVal, previousVal)"
return_type: "Decimal"
downstream_measures_count: 3
downstream_measures:
  - "YoY Sales Growth %"
  - "MoM Customer Growth %"
  - "Quarterly Revenue Growth"
tags:
  - "semantic_model"
  - "dax_function"
  - "udf"
  - "fn_CalculateGrowthRate"
---
```

---

## 🏛️ Modular Chapters Breakdown

### 1. Identity & Formal Signature
Displays function name, full callable signature (e.g. `fn_CalculateGrowthRate(currentVal, previousVal) -> Decimal`), and business description from model metadata.

### 2. Parameters Specification
Details input arguments expected by the function:

| Parameter Name | Data Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `currentVal` | `Decimal` | Yes | Current period numeric metric |
| `previousVal` | `Decimal` | Yes | Prior comparison period metric |

### 3. Implementation Formula Block
Displays the complete DAX body in a formatted code block:

```dax
fn_CalculateGrowthRate = 
(currentVal, previousVal) =>
    DIVIDE(currentVal - previousVal, previousVal, 0)
```

### 4. Downstream Consuming Measures
Lists every DAX measure that invokes this function:

| Consuming Measure | Host Table | Link |
| :--- | :--- | :--- |
| `YoY Sales Growth %` | `FactInternetSales` | [View Measure](../measures/FactInternetSales/YoY_Sales_Growth_Pct.md) |
| `MoM Customer Growth %` | `DimCustomer` | [View Measure](../measures/DimCustomer/MoM_Customer_Growth_Pct.md) |

### 5. Upstream Dependencies
If the function calls secondary helper functions or references model columns directly, they are cataloged with cross-links.

### 6. Contextual RAG Search Hints
Natural language questions for locating reusable business functions (e.g. *"What function calculates percentage growth?"*, *"Where is fn_CalculateGrowthRate used?"*).

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Are DAX User-Defined Functions supported in all Power BI models?
**A**: UDFs are a feature of modern Tabular compatibility levels (Microsoft Fabric and Analysis Services). In models where no UDFs are defined, the generator simply skips creating the `functions/` subdirectory.
