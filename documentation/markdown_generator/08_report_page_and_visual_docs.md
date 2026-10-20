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
Sorted in natural reading order (Top-to-Bottom, Left-to-Right). When `include_visual_svg_maps` is enabled (default), dynamic visuals are presented in a 2-column side-by-side table layout:

| Canvas Location | Technical Specifications, Metrics & Filter Perimeter |
| :---: | :--- |
| `<div style="min-width: 260px; max-width: 380px;"><img src="assets/<Page>/<Visual_Id>.svg" width="100%" /></div>` | **Visual Type**: `barChart` &nbsp; *(Visible - Solid Border)*<br>**Visual ID**: `01af2f16...`<br>**Indicative Position**: `Center-Left`<br><br>**Evaluated DAX Metric(s)**:<br>• [Sales[Revenue]](../measures/Sales/Revenue.md) *(Role: Y)*<br><br>**Slicing Dimension(s) (Axis / Row Context)**:<br>• [Product](../tables/Product.md) ➔ `Category` *(Role: Category)*<br><br>**Applicable Filter Perimeter**:<br>• **Locked Page Filter(s)**:<br>&nbsp;&nbsp;&nbsp;&nbsp;• [Status](../tables/Status.md) ➔ `Active` In (`Won`) *(Hard constraint)*<br>• **Interactive Page Filter(s) (Panel)**:<br>&nbsp;&nbsp;&nbsp;&nbsp;• [Date](../tables/Date.md) ➔ `Year` (Default: `All (No filter applied)`)<br>• **Canvas Page Slicer(s)**:<br>&nbsp;&nbsp;&nbsp;&nbsp;• [Calendar](../tables/Calendar.md) ➔ `Date` (Default: `All`)<br>• **Visual-Level Filter(s)**:<br>&nbsp;&nbsp;&nbsp;&nbsp;• [Product](../tables/Product.md) ➔ `Category`: `In (Bikes)` *(Type: Categorical)* |

#### Scaled SVG Canvas Mini-Map Specifications:
- **Canvas Viewport**: Exact aspect ratio (`viewBox="0 0 page_width page_height"`), square corners (`rx="0" ry="0"`), and dark gray canvas border (`#334155`).
- **3x3 Reference Grid**: Dashed dark gray reference guidelines (`#64748b`, `stroke-dasharray="8,8"`) dividing the canvas into standard quadrants.
- **Visual Bounding Box**: Scaled square rectangle with dark gray border (`#334155`), solid line for visible visuals and dashed line (`stroke-dasharray="16,10"`) for hidden visual elements.
- **Visual Fill**: Dark gray (`#334155`) with **80% transparency** (`fill-opacity="0.20"`), allowing underlying grid lines to remain clearly visible.
- **Center Marker**: Crisp geometric black "X" (`#000000`, `stroke-width="4"`, `stroke-linecap="square"`).
- **Clean Aesthetic**: No dimensional badges cluttering the graphic; spatial coordinates are abstracted into standard indicative positions (`Top-Left`, `Center`, `Bottom-Right`, etc.) rather than repeated in text.

#### Abstracted Documentation Labels (`VisualDocLabels`):
All table column headers, status badges, bullet point titles, and filter categories are centralized in the `VisualDocLabels` class. This ensures strict English consistency, clean semantic RAG indexing, and seamless switching between the 2-column SVG layout and the text-only bullet list fallback mode.

### 5. Omitted Static Elements Summary
Reports the exact count of decorative shapes, background lines, static textboxes, and fixed images excluded from the catalog to maintain clean documentation.

---

## ⚙️ CLI Flags & Configuration

Visual documentation and scaled SVG canvas mini-maps are **enabled by default** and automatically discover sibling `*.Report` folders alongside the semantic model.

To disable or customize visual documentation via CLI:

```bash
# Disable visuals generation entirely
python generate_docs.py "samples/AdventureWorks Sales" --no-visuals

# Disable SVG canvas mini-maps (generates text-only visual catalogs)
python generate_docs.py "samples/AdventureWorks Sales" --no-visual-svg-maps

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
  "include_visual_svg_maps": true,
  "visuals_subdir": "visuals",
  "visual_assets_subdir": "assets",
  "report_path": null
}
```

