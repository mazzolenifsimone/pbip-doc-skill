---
title: "10. Report & Visual Presentation Metadata (Calculation & Filter Context)"
target_json_path: "/report, report_documentation.json"
python_module: "pbip_doc/report_schema.py, pbip_doc/report_parser.py"
source_formats: ["PBIR (Enhanced Report)", "Legacy report.json"]
tags: ["report", "visuals", "filter_context", "pbir", "pages", "filters", "slicers", "coordinates"]
---

# 10. Report & Visual Presentation Metadata (Calculation & Filter Context)

> **TL;DR**:
> - Documents the presentation layer (`*.Report` component) in Power BI Projects (`.pbip`), supporting both **PBIR** and **Legacy `report.json`**.
> - Strictly non-redundant: **does not re-parse DAX expressions or semantic model internals**, which are already fully documented by Phase 1 (`*.SemanticModel`).
> - Focuses entirely on the missing link: answering the fundamental business question:
>   > *"In this visual I see a number: how was it calculated and under which exact filter context?"*
> - Captures visual spatial coordinates (calibrated on visual center `center_x`, `center_y` and screen quadrant).
> - Deconstructs the full Power BI evaluation context: locked active page filters, unlocked page filters with defaults, visual-level filters, page slicers, and slicing dimensions (rows, columns, axes).

---

## 🏛️ Architectural Boundary & Separation of Concerns

The pbip documentation ecosystem enforces a clean, modular boundary between data logic and presentation:

```text
┌────────────────────────────────────────────────────────────────────────┐
│             Phase 1: Semantic Model (*.SemanticModel)                  │
│  - Tables, columns, relationships, star schema role classification     │
│  - DAX formulas, calculation depths, tokenizer, measure dependency DAG │
│  - Power Query M lineage, staging queries, root data sources           │
│  - External measures (EXTERNALMEASURE), remote model resolution        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Joined via Key: Table[Field]
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Phase 1 (Extension): Report (*.Report)                   │
│  - Pages: display names, visibility, page roles (Normal, Tooltip)      │
│  - Visuals: visual type, title, center coordinates (center_x, center_y)│
│  - Evaluated Metric Binding: Table[Measure] or implicit aggregation    │
│  - Calculation Filter Context:                                         │
│      • Locked Active Page Filters (must constrain calculation)         │
│      • Unlocked Page Filters (available in panel with default value)   │
│      • Visual-Level Active Filters (TopN, specific inclusions)         │
│      • Page & Sync Slicers (interactive selectors with default state)  │
│      • Slicing Coordinates (Row, Column, Category, Legend dimensions)  │
└────────────────────────────────────────────────────────────────────────┘
```

> [!NOTE]
> Advanced cross-cutting features (such as **Dead Code Detection** or multi-model lineage reconcilers) operate downstream as standalone consumers of both generated JSONs, without complicating or bloating this report parser.

---

## 📋 JSON Schema Specification (`report_documentation.json`)

The normalized schema represents each visual as an autonomous, self-contained business calculation unit:

```json
{
  "report_name": "Sales Performance",
  "format": "PBIR",
  "source_path": "samples/AdventureWorks Sales/AdventureWorks Sales.Report",
  "summary": {
    "total_pages": 4,
    "visible_pages": 3,
    "hidden_pages": 1,
    "total_visuals": 17,
    "visual_types_distribution": {
      "barChart": 4,
      "donutChart": 2,
      "matrix": 3,
      "card": 5,
      "slicer": 3
    }
  },
  "pages": [
    {
      "page_id": "ReportSection1",
      "display_name": "Executive Overview",
      "page_number": 1,
      "page_type": "NORMAL",
      "is_hidden": false,
      "width": 1920,
      "height": 1080,
      "visuals": [
        {
          "visual_id": "11a03bbd46fd39147235",
          "title": "Cost by Product Category",
          "visual_type": "donutChart",
          "is_hidden": false,
          "is_slicer": false,
          "spatial_position": {
            "center_x": 1338.3,
            "center_y": 830.4,
            "zone": "Bottom-Right",
            "bounding_box": {
              "x": 1101.2,
              "y": 645.2,
              "width": 474.2,
              "height": 370.5,
              "z": 15250
            }
          },
          "calculation_context": {
            "evaluated_metrics": [
              {
                "table": "Sales",
                "field": "Cost",
                "field_type": "MEASURE",
                "role": "Y",
                "model_key": "Sales[Cost]",
                "aggregation": null
              }
            ],
            "slicing_coordinates": [
              {
                "role": "Category (Axis)",
                "table": "Product",
                "field": "Category",
                "model_key": "Product[Category]"
              }
            ],
            "visual_active_filters": [
              {
                "table": "Product",
                "field": "Category",
                "filter_type": "Categorical",
                "condition": "Exclude 'Components'"
              }
            ],
            "locked_active_filters": [
              {
                "scope": "Page Filter Panel (Locked)",
                "table": "Date",
                "field": "Year",
                "operator": "In",
                "applied_values": ["2024"],
                "is_locked": true
              }
            ],
            "unlocked_available_filters": [
              {
                "scope": "Page Filter Panel (Interactive)",
                "table": "Customer",
                "field": "Country",
                "default_value": "All (No filter applied)",
                "is_locked": false
              }
            ],
            "page_slicers": [
              {
                "slicer_visual_id": "b1c2d3e4f5a6b7",
                "table": "Product",
                "field": "Segment",
                "model_key": "Product[Segment]",
                "default_selection": "All",
                "is_synced_across_pages": true
              }
            ]
          }
        }
      ]
    }
  ]
}
```

---

## 🔎 Detailed Element Mapping

### 1. Spatial Positioning (`spatial_position`)
To allow humans and automated agents to locate visuals immediately without mental arithmetic:
- **`center_x`**: `x + (width / 2)`
- **`center_y`**: `y + (height / 2)`
- **`zone`**: Categorical canvas quadrant calculated relative to page canvas width and height:
  - Horizontal slices: `Left` (0–33%), `Center` (33–66%), `Right` (66–100%)
  - Vertical slices: `Top` (0–33%), `Middle` (33–66%), `Bottom` (66–100%)
  - Combined names: e.g. `"Top-Left"`, `"Top-Center"`, `"Bottom-Right"`.

### 2. The Filter & Evaluation Context (`calculation_context`)

| Component | Target Filter Source | Extraction Rule | Business Meaning |
| :--- | :--- | :--- | :--- |
| **`evaluated_metrics[]`** | `visual.json` ➔ `queryState` (Value slots: `Y`, `Values`) | Table and measure name (or column with implicit aggregation like `Sum`). | **The Formula**: What metric is being evaluated. |
| **`slicing_coordinates[]`** | `queryState` (Category slots: `Category`, `Series`, `Rows`, `Columns`) | Dimensional fields defining rows/slices of the visual. | **The Coordinate**: The slice of the metric (e.g. for Bikes). |
| **`visual_active_filters[]`** | `visual.json` ➔ `filterConfig.filters` or `visual.filters` | Conditions with active expressions (`Where/In/TopN`). | **The Visual Perimeter**: Specific limits on that chart (e.g. Top 10). |
| **`locked_active_filters[]`** | `page.json` ➔ `filterConfig.filters` with `isLockedInViewMode: true` | **Only included if it has an active condition**. Non-filtering items are excluded. | **The Inflexible Constraint**: Hard-coded page filters user cannot change. |
| **`unlocked_available_filters[]`**| `page.json` ➔ `filterConfig.filters` with `isLockedInViewMode: false` | Included with default value; if unconstrained, value is `"All (No filter)"`. | **The Interactive Scope**: Optional filters user can touch, with default state. |
| **`page_slicers[]`** | Visual containers of type `"slicer"` on page or synced | Slicers present on canvas and their initial selection state. | **The On-Canvas Controls**: Sliders, dropdowns, and buttons modifying the page. |

---

## 🐍 Python Dataclass Reference (`pbip_doc/report_schema.py`)

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    z: int = 0

@dataclass
class SpatialPosition:
    center_x: float
    center_y: float
    zone: str  # "Top-Left", "Top-Center", "Top-Right", "Middle-Left", "Center", "Bottom-Right", etc.
    bounding_box: BoundingBox

@dataclass
class EvaluatedMetric:
    table: str
    field: str
    field_type: str  # "MEASURE" | "COLUMN" | "IMPLICIT_MEASURE"
    role: str        # "Y" | "Values"
    model_key: str   # "Table[Field]"
    aggregation: Optional[str] = None  # "Sum", "Count", "Average"

@dataclass
class SlicingCoordinate:
    role: str        # "Category (Axis)" | "Series (Legend)" | "Rows" | "Columns"
    table: str
    field: str
    model_key: str   # "Table[Field]"

@dataclass
class ActiveFilter:
    table: str
    field: str
    filter_type: str
    condition: str
    scope: str = "Visual"

@dataclass
class PagePanelFilter:
    scope: str       # "Page Filter Panel (Locked)" | "Page Filter Panel (Interactive)"
    table: str
    field: str
    is_locked: bool
    applied_values: Optional[List[str]] = None
    default_value: Optional[str] = None
    operator: Optional[str] = None

@dataclass
class PageSlicer:
    slicer_visual_id: str
    table: str
    field: str
    model_key: str
    default_selection: str = "All"
    is_synced_across_pages: bool = False

@dataclass
class CalculationContext:
    evaluated_metrics: List[EvaluatedMetric] = field(default_factory=list)
    slicing_coordinates: List[SlicingCoordinate] = field(default_factory=list)
    visual_active_filters: List[ActiveFilter] = field(default_factory=list)
    locked_active_filters: List[PagePanelFilter] = field(default_factory=list)
    unlocked_available_filters: List[PagePanelFilter] = field(default_factory=list)
    page_slicers: List[PageSlicer] = field(default_factory=list)

@dataclass
class VisualDefinition:
    visual_id: str
    title: Optional[str]
    visual_type: str
    is_hidden: bool = False
    is_slicer: bool = False
    spatial_position: Optional[SpatialPosition] = None
    calculation_context: CalculationContext = field(default_factory=CalculationContext)

@dataclass
class PageDefinition:
    page_id: str
    display_name: str
    page_number: int
    is_hidden: bool = False
    page_type: str = "NORMAL"  # "NORMAL" | "TOOLTIP" | "DRILLTHROUGH"
    width: int = 1920
    height: int = 1080
    visuals: List[VisualDefinition] = field(default_factory=list)

@dataclass
class ReportSummary:
    total_pages: int = 0
    visible_pages: int = 0
    hidden_pages: int = 0
    total_visuals: int = 0
    visual_types_distribution: Dict[str, int] = field(default_factory=dict)

@dataclass
class PBIPReportModel:
    report_name: str
    format: str  # "PBIR" | "LEGACY"
    source_path: str
    summary: ReportSummary = field(default_factory=ReportSummary)
    pages: List[PageDefinition] = field(default_factory=list)
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why exclude DAX definitions and upstream lineage from this schema?
**A**: The semantic model documentation (`semantic_model_documentation.json`) already provides exhaustive coverage of DAX AST tokens, calculation depths, upstream/downstream DAGs, and M partition lineage. Duplicating that logic in the report schema violates single-responsibility and creates redundant code. Connecting `report_documentation.json` to the semantic model via the key `Table[Field]` is instantaneous and clean.

### Q: How are locked filters separated from unlocked filters in the Filter Pane?
**A**: Power BI marks locked filters with `"isLockedInViewMode": true`. If such a filter contains an active constraint (`filter.Where`), it is assigned to `locked_active_filters`. If it has no active constraint, it is discarded from active filtering context. Filters with `"isLockedInViewMode": false` (or omitted) are assigned to `unlocked_available_filters` along with their default state (`"All"` or preselected values).

### Q: How is the visual position zone calculated?
**A**: Using normalized screen ratios:
$$\text{center}_x = x + \frac{\text{width}}{2}, \quad \text{center}_y = y + \frac{\text{height}}{2}$$
The canvas is divided into a 3x3 grid (Left/Center/Right, Top/Middle/Bottom). This allows reporting the visual as e.g. `"Top-Left"` or `"Bottom-Right"`, offering intuitive spatial awareness to users and AI agents without requiring manual coordinate parsing.
