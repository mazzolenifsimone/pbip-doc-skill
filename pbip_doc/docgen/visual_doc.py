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
                "| Target Table | Target Field | Operator | Applied Value(s) |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for f in locked_filters:
                t_link = self._format_table_link(f.table)
                vals_str = ", ".join(f.applied_values) if f.applied_values else (f.default_value or "Active Filter")
                lines.append(f"| {t_link} | `{f.field}` | `{f.operator or 'Custom'}` | `{vals_str}` |")
        else:
            lines.append("> ℹ️ *No locked active filters constraining this page.*")

        lines.extend([
            "",
            "### 2. Interactive Page Filters (Available in Filter Pane)",
        ])

        if unlocked_filters:
            lines.extend([
                "These filters are exposed in the filter panel for end-user interaction. The default state before user modification:",
                "",
                "| Target Table | Target Field | Default Selection / Value |",
                "| :--- | :--- | :--- |",
            ])
            for f in unlocked_filters:
                t_link = self._format_table_link(f.table)
                lines.append(f"| {t_link} | `{f.field}` | `{f.default_value or 'All (No filter applied)'}` |")
        else:
            lines.append("> ℹ️ *No unlocked filters present in the page filter panel.*")

        lines.extend([
            "",
            "### 3. Canvas Slicer Controls",
        ])

        if slicers:
            lines.extend([
                "Interactive on-canvas slicers and selectors available on this page:",
                "",
                "| Slicer Control | Target Field | Default State | Synced Across Pages |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for s in slicers:
                t_link = self._format_table_link(s.table)
                synced = "Yes" if s.is_synced_across_pages else "No"
                lines.append(f"| `{s.model_key}` | {t_link} ➔ `{s.field}` | `{s.default_selection}` | `{synced}` |")
        else:
            lines.append("> ℹ️ *No canvas slicer controls present on this page.*")

        return "\n".join(lines)

    def _build_visuals_catalog(self, dynamic_visuals: List[VisualDefinition]) -> str:
        lines = [
            "## In-Scope Dynamic Visuals",
            "",
            f"A total of **{len(dynamic_visuals)}** dynamic visual elements were detected on this canvas. "
            "Each element evaluates data model metrics or controls interactive slicing dimensions.",
            "",
        ]

        if not dynamic_visuals:
            lines.append("> ℹ️ *No dynamic visuals with metric evaluation or slicing context were detected on this page.*")
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
            center_str = f"({s_pos.center_x}, {s_pos.center_y})" if s_pos else "N/A"
            bbox_str = (
                f"x: {s_pos.bounding_box.x}, y: {s_pos.bounding_box.y}, w: {s_pos.bounding_box.width}, h: {s_pos.bounding_box.height}"
                if s_pos
                else "N/A"
            )

            lines.extend([
                f"### {idx}. {title}",
                "",
                f"- **Visual Type**: `{v.visual_type}`" + (" *(Slicer Control)*" if v.is_slicer else ""),
                f"- **Visual ID**: `{v.visual_id}`",
                f"- **Spatial Position**: Center **`{center_str}`** in **`{zone}`** (`{bbox_str}`)",
            ])

            # Evaluated Metrics
            calc = v.calculation_context
            if calc.evaluated_metrics:
                lines.append("- **Evaluated Metric(s)**:")
                for m in calc.evaluated_metrics:
                    m_link = self._format_metric_link(m)
                    agg_badge = f" (Aggregation: `{m.aggregation}`)" if m.aggregation else ""
                    role_badge = f" *(Role: {m.role})*" if m.role else ""
                    lines.append(f"  - {m_link}{agg_badge}{role_badge}")
            elif not v.is_slicer:
                lines.append("- **Evaluated Metric(s)**: None (Dimension/Categorical visual without value metrics)")

            # Slicing Coordinates
            if calc.slicing_coordinates:
                lines.append("- **Slicing Coordinate(s)**:")
                for c in calc.slicing_coordinates:
                    t_link = self._format_table_link(c.table)
                    lines.append(f"  - {t_link} ➔ `{c.field}` *(Role: {c.role})*")

            # Active Visual Filters
            if calc.visual_active_filters:
                lines.append("- **Visual Active Filter(s)**:")
                for vf in calc.visual_active_filters:
                    t_link = self._format_table_link(vf.table)
                    lines.append(f"  - {t_link} ➔ `{vf.field}`: `{vf.condition}` *(Type: {vf.filter_type})*")

            lines.append("")

        return "\n".join(lines).rstrip()

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
