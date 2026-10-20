"""
Data contracts and schema definitions for the PBIP Report documentation JSON output.
Fully serializable with Python standard library.
"""

from dataclasses import dataclass, field, asdict
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
    zone: str  # "Top-Left", "Top-Center", "Top-Right", "Middle-Left", "Center", "Middle-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right"
    bounding_box: BoundingBox


@dataclass
class EvaluatedMetric:
    table: str
    field: str
    field_type: str  # "MEASURE" | "COLUMN" | "IMPLICIT_MEASURE"
    role: str        # "Y", "Values", "Data", "Size"
    model_key: str   # "Table[Field]"
    aggregation: Optional[str] = None  # "Sum", "Count", "Average", "Min", "Max", etc.


@dataclass
class SlicingCoordinate:
    role: str        # "Category (Axis)", "Series (Legend)", "Rows", "Columns", "Tooltips", etc.
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

    @property
    def is_dynamic(self) -> bool:
        """
        Determines whether this visual element is dynamic (in-scope for documentation)
        vs static (purely decorative line, shape, or static image).
        """
        if self.is_slicer:
            return True
        if self.calculation_context.evaluated_metrics:
            return True
        if self.calculation_context.slicing_coordinates:
            return True
        if self.calculation_context.visual_active_filters:
            return True
        return False


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire report model to standard Python dictionary ready for JSON dump."""
        return asdict(self)
