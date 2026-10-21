"""
Page & Visual Documentation Generator.
Produces modular, AI-RAG-ready Markdown documentation for each report page,
detailing visual spatial coordinates, evaluated metrics, slicing dimensions,
and complete canvas filter context (locked active filters, unlocked interactive filters, and slicers).
100% Vanilla Python standard library.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename
from ..report_schema import (
    PageDefinition,
    VisualDefinition,
    PBIPReportModel,
    EvaluatedMetric,
    SlicingCoordinate,
    ActiveFilter,
    PagePanelFilter,
    PageSlicer,
)



class VisualDocLabels:
    """
    Centralized technical documentation labels and terminology for report pages and visuals.
    Maintains rigorous consistency across Markdown catalogs, tables, and AI-RAG metadata.
    """
    # Table column headers
    COL_CANVAS_LOCATION = "Canvas Location"
    COL_SPECS_METRICS_PERIMETER = "Technical Specifications, Metrics & Filter Perimeter"
    COL_TARGET_TABLE = "Target Table"

    COL_TARGET_FIELD = "Target Field"
    COL_OPERATOR = "Operator"
    COL_APPLIED_VALUES = "Applied Value(s)"
    COL_DEFAULT_SELECTION = "Default Selection / Value"
    COL_SLICER_CONTROL = "Slicer Control"
    COL_DEFAULT_STATE = "Default State"
    COL_SYNCED = "Synced Across Pages"

    # Visual specification bullet labels
    LABEL_VISUAL_TYPE = "Visual Type"
    LABEL_VISUAL_ID = "Visual ID"
    LABEL_INDICATIVE_POSITION = "Indicative Position"
    LABEL_EVALUATED_METRICS = "Evaluated DAX Metric(s)"
    LABEL_SLICING_DIMENSIONS = "Slicing Dimension(s) (Axis / Row Context)"
    LABEL_FILTER_PERIMETER = "Applicable Filter Perimeter"
    LABEL_LOCKED_PAGE_FILTERS = "Locked Page Filter(s)"
    LABEL_INTERACTIVE_PAGE_FILTERS = "Interactive Page Filter(s) (Panel)"
    LABEL_CANVAS_PAGE_SLICERS = "Canvas Page Slicer(s)"
    LABEL_VISUAL_LEVEL_FILTERS = "Visual-Level Filter(s)"

    # Status badges and modifiers
    BADGE_VISIBLE = "*(Visible - Solid Border)*"
    BADGE_HIDDEN = "*(Hidden - Dashed Border)*"
    BADGE_SLICER_CONTROL = "*(Slicer Control)*"
    BADGE_HARD_CONSTRAINT = "*(Hard constraint)*"
    ROLE_PREFIX = "Role"
    TYPE_PREFIX = "Type"
    DEFAULT_PREFIX = "Default"
    AGGREGATION_PREFIX = "Aggregation"

    # Placeholders & fallbacks
    VALUE_NONE = "*None*"
    VALUE_NONE_STRUCTURAL = "*None (Structural/Slicer visual)*"
    VALUE_ALL_DEFAULT = "All (No filter applied)"

    # Section callouts & notes
    MSG_NO_LOCKED_FILTERS = "> ℹ️ *No locked active filters constraining this page.*"
    MSG_NO_UNLOCKED_FILTERS = "> ℹ️ *No unlocked filters present in the page filter panel.*"
    MSG_NO_SLICERS = "> ℹ️ *No canvas slicer controls present on this page.*"
    MSG_NO_DYNAMIC_VISUALS = "> ℹ️ *No dynamic visuals with metric evaluation or slicing context were detected on this page.*"


class PageVisualDocBuilder:
    """
    Builds a standalone Markdown document for a single report page and all its dynamic visuals.
    """

    def __init__(
        self,
        page: PageDefinition,
        report_model: PBIPReportModel,
        config: Optional[DocGenConfig] = None,
        known_measure_keys: Optional[set] = None,
        known_table_names: Optional[set] = None,
    ):
        self.page = page
        self.report = report_model
        self.config = config or DocGenConfig()
        self.known_measure_keys = known_measure_keys or set()
        self.known_table_names = known_table_names or set()

    def build_markdown(self) -> str:
        """Assembles the modular markdown document for this report page."""
        sections: List[str] = []

        dynamic_visuals = [v for v in self.page.visuals if v.is_dynamic]
        static_count = len(self.page.visuals) - len(dynamic_visuals)

        # 1. YAML Frontmatter
        if self.config.include_visual_yaml_frontmatter:
            sections.append(self._build_frontmatter(dynamic_visuals, static_count))

        # 2. Header & Page Canvas Identity
        sections.append(self._build_header_section(dynamic_visuals, static_count))

        # 3. Canvas Filter & Slicing Context
        sections.append(self._build_filter_context_section())

        # 4. In-Scope Dynamic Visuals Catalog
        sections.append(self._build_visuals_catalog(dynamic_visuals))

        # 5. Out-of-Scope Static Elements Summary
        if static_count > 0:
            sections.append(self._build_static_summary(static_count))

        return "\n\n".join(sections) + "\n"

    def _build_frontmatter(self, dynamic_visuals: List[VisualDefinition], static_count: int) -> str:
        all_metrics = []
        for v in dynamic_visuals:
            for m in v.calculation_context.evaluated_metrics:
                all_metrics.append(m.model_key)
        distinct_metrics = sorted(set(all_metrics))

        data = {
            "title": f"Report Page: {self.page.display_name}",
            "doc_type": "report_page_visuals",
            "page_id": self.page.page_id,
            "display_name": self.page.display_name,
            "page_number": self.page.page_number,
            "page_type": self.page.page_type,
            "is_hidden": self.page.is_hidden,
            "dimensions": f"{self.page.width}x{self.page.height}",
            "dynamic_visuals_count": len(dynamic_visuals),
            "omitted_static_elements_count": static_count,
            "evaluated_measures": distinct_metrics[:20],
            "tags": [
                "report_page",
                "visuals",
                "filter_context",
                sanitize_filename(self.page.display_name),
                self.report.format,
            ],
        }
        return format_yaml_frontmatter(data)

    def _build_header_section(self, dynamic_visuals: List[VisualDefinition], static_count: int) -> str:
        vis_status = "Hidden in View Mode" if self.page.is_hidden else "Visible in View Mode"
        role_badge = f"`[{self.page.page_type}]`" if self.page.page_type != "NORMAL" else ""
        
        lines = [
            f"# Report Page: `{self.page.display_name}` {role_badge}".strip(),
            "",
            f"**Report**: `{self.report.report_name}` ({self.report.format}) | "
            f"**Page Order**: `#{self.page.page_number}` | "
            f"**Canvas Size**: `{self.page.width}x{self.page.height}` | "
            f"**Visibility**: `{vis_status}`",
            "",
            f"This technical document specifies the presentation and evaluation context for page **`{self.page.display_name}`**. "
            f"It details the exact filter perimeter (locked panel constraints, interactive defaults, and canvas slicers) "
            f"and provides spatial-to-metric mappings for **{len(dynamic_visuals)}** dynamic visual elements.",
        ]
        return "\n".join(lines)

    def _build_filter_context_section(self) -> str:
        first_vis = self.page.visuals[0] if self.page.visuals else None
        calc = first_vis.calculation_context if first_vis else None

        locked_filters = calc.locked_active_filters if calc else []
        unlocked_filters = calc.unlocked_available_filters if calc else []
        slicers = calc.page_slicers if calc else []

        lbl = VisualDocLabels
        lines = [
            "## Canvas Filter & Evaluation Context",
            "",
            "The filter context below defines the foundational calculation perimeter applied across visuals on this page.",
            "",
            "### 1. Locked Active Page Filters (Hard Constraints)",
        ]

        if locked_filters:
            lines.extend([
                "These filters are locked in view mode with active constraints and directly restrict all metrics computed on this canvas:",
                "",
                f"| {lbl.COL_TARGET_TABLE} | {lbl.COL_TARGET_FIELD} | {lbl.COL_OPERATOR} | {lbl.COL_APPLIED_VALUES} |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for f in locked_filters:
                t_link = self._format_table_link(f.table)
                vals_str = ", ".join(f.applied_values) if f.applied_values else (f.default_value or "Active Filter")
                lines.append(f"| {t_link} | `{f.field}` | `{f.operator or 'Custom'}` | `{vals_str}` |")
        else:
            lines.append(lbl.MSG_NO_LOCKED_FILTERS)

        lines.extend([
            "",
            "### 2. Interactive Page Filters (Available in Filter Pane)",
        ])

        if unlocked_filters:
            lines.extend([
                "These filters are exposed in the filter panel for end-user interaction. The default state before user modification:",
                "",
                f"| {lbl.COL_TARGET_TABLE} | {lbl.COL_TARGET_FIELD} | {lbl.COL_DEFAULT_SELECTION} |",
                "| :--- | :--- | :--- |",
            ])
            for f in unlocked_filters:
                t_link = self._format_table_link(f.table)
                lines.append(f"| {t_link} | `{f.field}` | `{f.default_value or lbl.VALUE_ALL_DEFAULT}` |")
        else:
            lines.append(lbl.MSG_NO_UNLOCKED_FILTERS)

        lines.extend([
            "",
            "### 3. Canvas Slicer Controls",
        ])

        if slicers:
            lines.extend([
                "Interactive on-canvas slicers and selectors available on this page:",
                "",
                f"| {lbl.COL_SLICER_CONTROL} | {lbl.COL_TARGET_FIELD} | {lbl.COL_DEFAULT_STATE} | {lbl.COL_SYNCED} |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for s in slicers:
                t_link = self._format_table_link(s.table)
                synced = "Yes" if s.is_synced_across_pages else "No"
                lines.append(f"| `{s.model_key}` | {t_link} ➔ `{s.field}` | `{s.default_selection}` | `{synced}` |")
        else:
            lines.append(lbl.MSG_NO_SLICERS)

        return "\n".join(lines)

    def _build_visuals_catalog(self, dynamic_visuals: List[VisualDefinition]) -> str:
        lbl = VisualDocLabels
        lines = [
            "## In-Scope Dynamic Visuals",
            "",
            f"A total of **{len(dynamic_visuals)}** dynamic visual elements were detected on this canvas. "
            "Each element evaluates data model metrics or controls interactive slicing dimensions.",
            "",
        ]

        if not dynamic_visuals:
            lines.append(lbl.MSG_NO_DYNAMIC_VISUALS)
            return "\n".join(lines)

        # Sort visuals in natural reading order: Top-to-Bottom, Left-to-Right
        sorted_visuals = sorted(
            dynamic_visuals,
            key=lambda v: (
                v.spatial_position.bounding_box.y if v.spatial_position else 0,
                v.spatial_position.bounding_box.x if v.spatial_position else 0,
            ),
        )

        for idx, v in enumerate(sorted_visuals, start=1):
            title = v.title or f"Visual {idx}"
            s_pos = v.spatial_position
            zone = s_pos.zone if s_pos else "Canvas"
            indicative_pos = zone.replace("Middle-", "Center-")
            if indicative_pos in ("Center-Center", "Canvas"):
                indicative_pos = "Center"

            if self.config.include_visual_svg_maps:
                svg_url = self.config.resolve_visual_svg_url(self.page.display_name, v.visual_id)
                img_tag = (
                    f'<div style="min-width: 260px; max-width: 380px;">'
                    f'<img src="{svg_url}" width="300px" alt="{title}" style="display: block; border: 1px solid #334155;" />'
                    f'</div>'
                )
                details_cell = self._build_visual_details(v, indicative_pos, is_table_cell=True)

                lines.extend([
                    f"### {idx}. {title}",
                    "",
                    f"| {lbl.COL_CANVAS_LOCATION} | {lbl.COL_SPECS_METRICS_PERIMETER} |",
                    "| :---: | :--- |",
                    f"| {img_tag} | {details_cell} |",
                    "",
                ])
            else:
                # Text-only fallback when SVG maps are disabled
                details_list = self._build_visual_details(v, indicative_pos, is_table_cell=False)
                lines.extend([
                    f"### {idx}. {title}",
                    "",
                    details_list,
                    "",
                ])

        return "\n".join(lines).rstrip()

    def _build_visual_details(self, visual: VisualDefinition, indicative_pos: str, is_table_cell: bool) -> str:
        """
        Formats technical specifications, metrics, slicing dimensions, and filter perimeter.
        Abstracts between HTML-friendly single-cell table formatting and standard Markdown bullet lists.
        """
        lbl = VisualDocLabels
        calc = visual.calculation_context
        status_str = lbl.BADGE_HIDDEN if visual.is_hidden else lbl.BADGE_VISIBLE
        slicer_badge = f" {lbl.BADGE_SLICER_CONTROL}" if visual.is_slicer else ""

        sub_bullet = "•" if is_table_cell else "  -"
        item_bullet = "&nbsp;&nbsp;&nbsp;&nbsp;•" if is_table_cell else "    -"
        sep = "<br>" if is_table_cell else "\n"
        prefix = "" if is_table_cell else "- "

        sections: List[str] = []

        # 1. Identity & Core Specs
        header_lines = [
            f"{prefix}**{lbl.LABEL_VISUAL_TYPE}**: `{visual.visual_type}`{slicer_badge} &nbsp; {status_str}",
            f"{prefix}**{lbl.LABEL_VISUAL_ID}**: `{visual.visual_id}`",
            f"{prefix}**{lbl.LABEL_INDICATIVE_POSITION}**: `{indicative_pos}`",
        ]
        sections.append(sep.join(header_lines))

        # 2. Evaluated DAX Metrics
        if calc.evaluated_metrics:
            m_lines = [f"{prefix}**{lbl.LABEL_EVALUATED_METRICS}**:"]
            for m in calc.evaluated_metrics:
                m_link = self._format_metric_link(m)
                agg_badge = f" ({lbl.AGGREGATION_PREFIX}: `{m.aggregation}`)" if m.aggregation else ""
                role_badge = f" *({lbl.ROLE_PREFIX}: {m.role})*" if m.role else ""
                m_lines.append(f"{sub_bullet} {m_link}{agg_badge}{role_badge}")
            sections.append(sep.join(m_lines))
        elif not visual.is_slicer:
            sections.append(f"{prefix}**{lbl.LABEL_EVALUATED_METRICS}**: {lbl.VALUE_NONE_STRUCTURAL}")

        # 3. Slicing Dimensions
        if calc.slicing_coordinates:
            s_lines = [f"{prefix}**{lbl.LABEL_SLICING_DIMENSIONS}**:"]
            for c in calc.slicing_coordinates:
                t_link = self._format_table_link(c.table)
                s_lines.append(f"{sub_bullet} {t_link} ➔ `{c.field}` *({lbl.ROLE_PREFIX}: {c.role})*")
            sections.append(sep.join(s_lines))

        # 4. Applicable Filter Perimeter (Each tier with listed bullet points)
        filter_lines = [f"{prefix}**{lbl.LABEL_FILTER_PERIMETER}**:"]

        # 4a. Locked Page Filters
        if calc.locked_active_filters:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_LOCKED_PAGE_FILTERS}**:")
            for f in calc.locked_active_filters:
                t_link = self._format_table_link(f.table)
                vals = ", ".join(f.applied_values) if f.applied_values else (f.default_value or "Active")
                filter_lines.append(f"{item_bullet} {t_link} ➔ `{f.field}` In (`{vals}`) {lbl.BADGE_HARD_CONSTRAINT}")
        else:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_LOCKED_PAGE_FILTERS}**: {lbl.VALUE_NONE}")

        # 4b. Interactive Page Filters
        if calc.unlocked_available_filters:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_INTERACTIVE_PAGE_FILTERS}**:")
            for f in calc.unlocked_available_filters:
                t_link = self._format_table_link(f.table)
                def_val = f.default_value or lbl.VALUE_ALL_DEFAULT
                filter_lines.append(f"{item_bullet} {t_link} ➔ `{f.field}` ({lbl.DEFAULT_PREFIX}: `{def_val}`)")
        else:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_INTERACTIVE_PAGE_FILTERS}**: {lbl.VALUE_NONE}")

        # 4c. Canvas Page Slicers
        if not visual.is_slicer and calc.page_slicers:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_CANVAS_PAGE_SLICERS}**:")
            for s in calc.page_slicers:
                t_link = self._format_table_link(s.table)
                filter_lines.append(f"{item_bullet} {t_link} ➔ `{s.field}` ({lbl.DEFAULT_PREFIX}: `{s.default_selection}`)")
        elif not visual.is_slicer:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_CANVAS_PAGE_SLICERS}**: {lbl.VALUE_NONE}")

        # 4d. Visual-Level Filters
        if calc.visual_active_filters:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_VISUAL_LEVEL_FILTERS}**:")
            for vf in calc.visual_active_filters:
                t_link = self._format_table_link(vf.table)
                filter_lines.append(f"{item_bullet} {t_link} ➔ `{vf.field}`: `{vf.condition}` *({lbl.TYPE_PREFIX}: {vf.filter_type})*")
        else:
            filter_lines.append(f"{sub_bullet} **{lbl.LABEL_VISUAL_LEVEL_FILTERS}**: {lbl.VALUE_NONE}")

        sections.append(sep.join(filter_lines))

        major_sep = "<br><br>" if is_table_cell else "\n\n"
        return major_sep.join(sections)

    def generate_visual_svg(self, visual: VisualDefinition) -> str:
        """
        Generates scaled SVG mini-map of the page canvas highlighting the visual.
        - Square dark gray page canvas border (#334155).
        - Dashed dark gray 3x3 reference grid guidelines (#64748b).
        - Square visual rectangle with dark gray border (#334155), solid if visible, dashed if hidden.
        - Visual fill: dark gray (#334155) with 80% transparency (fill-opacity="0.20").
        - Center marker: crisp black 'X' (#000000).
        """
        page_w = float(self.page.width) if self.page.width and self.page.width > 0 else 1920.0
        page_h = float(self.page.height) if self.page.height and self.page.height > 0 else 1080.0

        dark_gray_border = "#334155"
        dark_gray_grid = "#64748b"
        visual_fill = "#334155"
        fill_opacity = "0.20"

        s_pos = visual.spatial_position
        if s_pos:
            bbox = s_pos.bounding_box
            x = bbox.x
            y = bbox.y
            w = bbox.width
            h = bbox.height
            cx = s_pos.center_x
            cy = s_pos.center_y
        else:
            x, y, w, h = 0.0, 0.0, page_w, page_h
            cx, cy = page_w / 2.0, page_h / 2.0

        stroke_style = 'stroke-dasharray="16,10"' if visual.is_hidden else ""

        x1 = page_w / 3.0
        x2 = (page_w * 2.0) / 3.0
        y1 = page_h / 3.0
        y2 = (page_h * 2.0) / 3.0

        d = 14  # Size of the X arms

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {page_w} {page_h}" width="100%" height="auto" style="background: #ffffff; display: block;">
  <!-- Canvas Background & Page Border (Square & Dark Gray) -->
  <rect x="2" y="2" width="{page_w - 4}" height="{page_h - 4}" fill="#ffffff" stroke="{dark_gray_border}" stroke-width="4"/>
  
  <!-- Zone Guidelines (3x3 grid - Dashed Dark Gray) -->
  <line x1="{x1:.1f}" y1="0" x2="{x1:.1f}" y2="{page_h}" stroke="{dark_gray_grid}" stroke-width="2" stroke-dasharray="8,8"/>
  <line x1="{x2:.1f}" y1="0" x2="{x2:.1f}" y2="{page_h}" stroke="{dark_gray_grid}" stroke-width="2" stroke-dasharray="8,8"/>
  <line x1="0" y1="{y1:.1f}" x2="{page_w}" y2="{y1:.1f}" stroke="{dark_gray_grid}" stroke-width="2" stroke-dasharray="8,8"/>
  <line x1="0" y1="{y2:.1f}" x2="{page_w}" y2="{y2:.1f}" stroke="{dark_gray_grid}" stroke-width="2" stroke-dasharray="8,8"/>
  
  <!-- Visual Bounding Box (Square & Dark Gray Border, Dark Gray Fill with 80% Transparency) -->
  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{visual_fill}" fill-opacity="{fill_opacity}" stroke="{dark_gray_border}" stroke-width="5" {stroke_style}/>
  
  <!-- Visual Center Marker: Black X -->
  <line x1="{cx - d:.1f}" y1="{cy - d:.1f}" x2="{cx + d:.1f}" y2="{cy + d:.1f}" stroke="#000000" stroke-width="4" stroke-linecap="square"/>
  <line x1="{cx - d:.1f}" y1="{cy + d:.1f}" x2="{cx + d:.1f}" y2="{cy - d:.1f}" stroke="#000000" stroke-width="4" stroke-linecap="square"/>
</svg>"""
        return svg

    def build_svg_assets(self) -> Dict[str, str]:
        """
        Generates all SVG mini-map assets for dynamic visuals on this page.
        Returns a dictionary mapping relative asset path (e.g. 'assets/<Page>/<Visual_Id>.svg')
        to the SVG XML string.
        """
        if not self.config.include_visual_svg_maps:
            return {}

        assets: Dict[str, str] = {}
        clean_page = sanitize_filename(self.page.display_name)
        assets_sub = self.config.visual_assets_subdir.strip("/\\")

        dynamic_visuals = [v for v in self.page.visuals if v.is_dynamic]
        for v in dynamic_visuals:
            clean_vid = sanitize_filename(v.visual_id)
            rel_path = f"{assets_sub}/{clean_page}/{clean_vid}.svg" if assets_sub else f"{clean_page}/{clean_vid}.svg"
            assets[rel_path] = self.generate_visual_svg(v)

        return assets

    def _build_static_summary(self, static_count: int) -> str:
        lines = [
            "## Omitted Static Elements",
            "",
            f"This canvas contains **{static_count}** purely static or decorative elements "
            "(such as background shapes, separating lines, static textboxes, and fixed images) "
            "that do not evaluate dynamic model metrics or alter the filter context. "
            "They have been excluded from this technical catalog to preserve document clarity and AI search relevance.",
        ]
        return "\n".join(lines)

    def _format_metric_link(self, metric: EvaluatedMetric) -> str:
        """Formats evaluated metric as clickable link to measure document or table document."""
        if not self.config.include_markdown_links:
            return f"`{metric.model_key}`"

        # If it's a measure
        if metric.field_type == "MEASURE" or (metric.table, metric.field) in self.known_measure_keys or metric.model_key in self.known_measure_keys:
            url = self.config.resolve_measure_url_from_visual(metric.table, metric.field)
            return f"[{metric.model_key}]({url})"

        # If it's an implicit aggregation over a column
        if metric.table and metric.table != "Unknown":
            t_url = self.config.resolve_table_url_from_visual(metric.table)
            return f"[{metric.model_key}]({t_url})"

        return f"`{metric.model_key}`"

    def _format_table_link(self, table_name: str) -> str:
        """Formats table reference as clickable link to table document."""
        if not table_name or table_name == "Unknown":
            return "`Unknown`"
        if not self.config.include_markdown_links:
            return f"`{table_name}`"

        t_url = self.config.resolve_table_url_from_visual(table_name)
        return f"[{table_name}]({t_url})"
