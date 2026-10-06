---
title: "04. DAX Measure Documentation Pages"
target_path: "docs/measures/<HostTable>/<MeasureName>.md"
python_module: "pbip_doc.docgen.measure_doc"
tags: ["measure", "dax", "calculation_depth", "lineage", "impact_analysis", "dag"]
---

# 04. DAX Measure Documentation Pages (`docs/measures/<HostTable>/<MeasureName>.md`)

> **TL;DR**:
> - Every published DAX measure receives a dedicated Markdown file inside a folder named after its host table.
> - Begins with YAML frontmatter specifying calculation depth, upstream dependencies, and downstream impact.
> - Formats full multiline DAX formulas in highlighted syntax blocks.
> - Traces the complete Directed Acyclic Graph (DAG): upstream dependencies and downstream impact.
> - Lists all physical columns and tables directly referenced by the DAX formula.

---

## 📋 Frontmatter Specification

```yaml
---
title: "Measure: Margin %"
doc_type: "dax_measure_documentation"
measure_name: "Margin %"
table: "FactInternetSales"
calculation_depth: 2
format_string: "0.0%"
is_inherited: false
direct_dependencies:
  - "Gross Margin"
  - "Total Sales"
all_upstream_measures:
  - "Gross Margin"
  - "Total Cost"
  - "Total Sales"
downstream_measures:
  - "Executive KPI Score"
referenced_columns:
  - table: "FactInternetSales"
    column: "SalesAmount"
  - table: "FactInternetSales"
    column: "TotalProductCost"
tags:
  - "semantic_model"
  - "dax_measure"
  - "depth_2"
  - "FactInternetSales"
  - "Margin_Pct"
---
```

---

## 🏛️ Modular Chapters Breakdown

### 1. Identity & Host Table Link
Displays the measure name, format string (e.g. `#,##0.00` or `0.0%`), description from metadata, and a clickable Markdown link back to the parent table document:
- **Parent Table**: `[FactInternetSales](../../tables/FactInternetSales.md)`
- **Calculation Role**: Base Measure (Depth 0) vs. Derived KPI (Depth 1+).

### 2. DAX Formula Block
Renders the complete DAX calculation formatted in a highlighted code block:

```dax
Margin % = 
DIVIDE (
    [Gross Margin],
    [Total Sales],
    0
)
```

### 3. Calculation Depth & Upstream Dependencies
Explains the topological depth of the calculation:

- **Depth 0 (Base Measure)**:
  > *Base Measure (Depth 0): Aggregates physical columns directly without relying on other DAX measures.*
- **Depth N (Composite KPI)**:
  - Lists **Direct Dependencies**: immediate measures referenced inside the formula with cross-links (e.g. `[Gross Margin](../FactInternetSales/Gross_Margin.md)`).
  - Lists **All Upstream Dependencies (Transitive)**: the full ancestor lineage tree needed to calculate this metric.

### 4. Downstream Impact Analysis
Lists every measure across the entire model that depends on this calculation:

| Downstream Dependent Measure | Host Table | Link |
| :--- | :--- | :--- |
| `Executive KPI Score` | `FactInternetSales` | [View Measure](../FactInternetSales/Executive_KPI_Score.md) |
| `Regional Performance Index` | `DimGeography` | [View Measure](../DimGeography/Regional_Performance_Index.md) |

> **Impact Rationale**: Modifying or removing this measure will directly alter or break the listed dependent KPIs.

### 5. Physical Columns Referenced
Table listing all raw data model columns read by the DAX formula:

| Table | Column | Link to Table |
| :--- | :--- | :--- |
| `FactInternetSales` | `SalesAmount` | [FactInternetSales](../../tables/FactInternetSales.md) |
| `FactInternetSales` | `TotalProductCost` | [FactInternetSales](../../tables/FactInternetSales.md) |

### 6. Contextual RAG Search Hints
Natural language questions that lead to this measure during AI agent or vector search (e.g. *"How is Margin % calculated?"*, *"Which measures depend on Gross Margin?"*).

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why are measure files organized into host table folders?
**A**: Separating measures into subdirectories by host table (`measures/<Table>/<Measure>.md`) prevents filename collisions when different tables contain similarly named metrics, and keeps directories manageable.

### Q: What if a measure references measures from other tables?
**A**: The generator resolves relative Markdown paths automatically (e.g. `../DimCustomer/Customer_Count.md`), ensuring that cross-table references work regardless of folder structure.

### Q: What does calculation depth mean in practice?
**A**: Depth 0 measures can be calculated immediately from table columns. Depth 1 measures require Depth 0 measures to evaluate first. Depth N measures require all ancestors up to Depth N-1.
