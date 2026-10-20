---
title: "08. Report Pages & Visual Context Documentation"
target_path: "docs/visuals/<page_name>.md"
python_module: "pbip_doc/docgen/visual_doc.py, pbip_doc/docgen/engine.py"
tags: ["visuals", "report_pages", "markdown", "filter_context", "spatial_position", "slicers"]
---

# 08. Report Pages & Visual Context Documentation

> **TL;DR**:
> - Generates dedicated, modular Markdown documents for each page in the presentation layer (`docs/visuals/<page_name>.md`).
> - Focuses on answering the key business question: *"In this visual I see a number: how was it calculated and under which filter context?"*
> - Details the canvas filter context: locked active filters (hard constraints), unlocked interactive filters with default selections, and canvas slicers.
> - Catalogs in-scope dynamic visuals (charts, tables, cards, and shapes/buttons with dynamic text) with spatial center coordinates and quadrant zones (`Top-Left`, `Center`, `Bottom-Right`).
> - Establishes direct clickable Markdown links to DAX measure documentation (`docs/measures/<Table>/<Measure>.md`) and table dictionaries (`docs/tables/<Table>.md`).
> - Omits purely static/decorative elements (lines, decorative shapes, static background textboxes, fixed images) into a summary count to maintain high RAG relevance and signal-to-noise ratio.

---

## 🏛️ Directory Structure

When visual documentation is enabled (enabled by default), `MarkdownDocGenerator` creates the `visuals/` subdirectory:

```text
docs/
├── INDEX.md                               # Includes "Report Presentation & Visuals" table
├── tables/                                # Dedicated table pages
├── measures/                              # Dedicated measure pages
├── visuals/                               # Dedicated report page markdowns
│   ├── Overview.md
│   ├── Executive_Overview.md
│   ├── Detailed_Info.md
│   └── Tooltip.md
└── ...
```

---

## 📋 Markdown Page Specification (`docs/visuals/<page_name>.md`)

Each page document follows a standardized structure optimized for human analysis and AI-RAG retrieval:

### 1. YAML Frontmatter
```yaml
---
title: "Report Page: Overview"
doc_type: report_page_visuals
page_id: ReportSection
display_name: Overview
page_number: 1
page_type: NORMAL
is_hidden: false
dimensions: 1920x1080
dynamic_visuals_count: 10
omitted_static_elements_count: 7
evaluated_measures:
  - "Sales[Cost]"
  - "Sales[Sales]"
  - "Sales[Profit]"
tags: ["report_page", "visuals", "filter_context", "Overview", "PBIR"]
---
```

### 2. Page Canvas Identity
Canvas dimensions (`1920x1080`, `600x450` for tooltips), page order number, report format (`PBIR` or `LEGACY`), and view-mode visibility (`Visible` or `Hidden in View Mode`).

### 3. Canvas Filter & Slicing Context
Deconstructs the 3 foundational filter sources:
- **Locked Active Page Filters**: Hard-coded constraints that cannot be changed by the user (only included if an active filter condition exists).
- **Interactive Page Filters**: Filters present in the Power BI Filter Pane, documented with their initial default state (e.g. `"All (No filter applied)"`).
- **Canvas Slicers**: Interactive slicer controls placed on the canvas and their default state.

### 4. Dynamic Visuals Catalog (In-Scope)
Sorted in natural reading order (Top-to-Bottom, Left-to-Right):
- **Visual Title & Type**: User-defined title (or synthesized title) with visual type badge.
- **Spatial Position**: Center coordinates `(center_x, center_y)` and screen quadrant zone (`Top-Left`, `Middle-Right`, `Bottom-Center`, etc.) + bounding box.
- **Evaluated Metric(s)**: Measures with clickable links to their dedicated markdown documents (`[Sales[Cost]](../measures/Sales/Cost.md)`).
- **Slicing Coordinate(s)**: Categorical fields defining axes, rows, or columns with links to table dictionaries (`[Product](../tables/Product.md)`).
- **Visual Active Filter(s)**: Visual-level filters such as Top N, exclusions, or comparison conditions.

### 5. Omitted Static Elements Summary
Reports the exact count of decorative shapes, background lines, static textboxes, and fixed images excluded from the catalog to maintain clean documentation.

---

## ⚙️ CLI Flags & Configuration

Visual documentation is **enabled by default** and automatically discovers the sibling `*.Report` folder alongside the semantic model.

To disable or customize visual documentation via CLI:

```bash
# Disable visuals generation entirely
python generate_docs.py "samples/AdventureWorks Sales" --no-visuals

# Customize visuals output folder
python generate_docs.py "samples/AdventureWorks Sales" --visuals-dir "report_pages"

# Explicitly specify report path if not colocated
python generate_docs.py "path/to/Model.SemanticModel" --report-path "path/to/Custom.Report"
```

In `pbip_doc.config.json`:

```json
{
  "include_visual_docs": true,
  "include_visual_yaml_frontmatter": true,
  "visuals_subdir": "visuals",
  "report_path": null
}
```
