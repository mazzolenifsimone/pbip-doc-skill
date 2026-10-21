"""
PBIP Report Parser.
Extracts presentation metadata, visual spatial positioning, and calculation filter context
from Power BI Report components (*.Report) across modern PBIR and Legacy formats.
Vanilla Python implementation.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from .report_schema import (
    BoundingBox,
    SpatialPosition,
    EvaluatedMetric,
    SlicingCoordinate,
    ActiveFilter,
    PagePanelFilter,
    PageSlicer,
    CalculationContext,
    VisualDefinition,
    PageDefinition,
    ReportSummary,
    PBIPReportModel,
)


SLICER_VISUAL_TYPES = {
    "slicer",
    "advancedslicervisual",
    "slicervisual",
    "hierarchyslicer",
    "timelineslicer",
    "chickletslicer",
}

VALUE_METRIC_ROLES = {"y", "values", "data", "size", "measure", "value"}

SLICING_COORDINATE_ROLES = {
    "category",
    "series",
    "rows",
    "columns",
    "tooltips",
    "smallmultiples",
    "grouping",
    "x",
    "axis",
    "legend",
}


def _extract_source_entity(expr_obj: Optional[Dict[str, Any]], alias_map: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Resolves table / entity name from an expression tree."""
    if not expr_obj or not isinstance(expr_obj, dict):
        return None
    if "SourceRef" in expr_obj:
        sr = expr_obj["SourceRef"]
        if "Entity" in sr:
            return sr["Entity"]
        if "Source" in sr:
            src = sr["Source"]
            if alias_map and src in alias_map:
                return alias_map[src]
            return src
    if "Hierarchy" in expr_obj:
        return _extract_source_entity(expr_obj["Hierarchy"].get("Expression"), alias_map)
    if "Expression" in expr_obj:
        return _extract_source_entity(expr_obj.get("Expression"), alias_map)
    return None


def _extract_field_details(
    field_obj: Optional[Dict[str, Any]], alias_map: Optional[Dict[str, str]] = None
) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
    """
    Extracts (table, field_name, field_type, aggregation) from a Power BI field representation.
    Field types: 'MEASURE', 'COLUMN', 'HIERARCHY', 'IMPLICIT_MEASURE'.
    """
    if not field_obj or not isinstance(field_obj, dict):
        return None, None, "UNKNOWN", None

    if "Column" in field_obj:
        col = field_obj["Column"]
        table = _extract_source_entity(col.get("Expression"), alias_map)
        prop = col.get("Property")
        return table, prop, "COLUMN", None

    if "Measure" in field_obj:
        m = field_obj["Measure"]
        table = _extract_source_entity(m.get("Expression"), alias_map)
        prop = m.get("Property")
        return table, prop, "MEASURE", None

    if "HierarchyLevel" in field_obj:
        hl = field_obj["HierarchyLevel"]
        table = _extract_source_entity(hl.get("Expression"), alias_map)
        prop = hl.get("Level")
        return table, prop, "HIERARCHY", None

    if "Aggregation" in field_obj:
        agg = field_obj["Aggregation"]
        sub_expr = agg.get("Expression", {})
        table, prop, _, _ = _extract_field_details(sub_expr, alias_map)
        fn_code = agg.get("Function", 0)
        fn_map = {0: "Sum", 1: "Average", 2: "Count", 3: "Min", 4: "Max", 5: "DistinctCount"}
        agg_name = fn_map.get(fn_code, "Sum") if isinstance(fn_code, int) else str(fn_code)
        return table, prop, "IMPLICIT_MEASURE", agg_name

    # Check for direct Property or name fallback
    if "Property" in field_obj:
        return None, field_obj.get("Property"), "COLUMN", None

    return None, None, "UNKNOWN", None


def _find_dynamic_expressions(
    data: Any, alias_map: Optional[Dict[str, str]] = None
) -> List[Tuple[str, str, str, Optional[str]]]:
    """
    Recursively scans visual objects/properties for dynamic measure or column expressions.
    Returns list of (table, field, field_type, aggregation).
    """
    results: List[Tuple[str, str, str, Optional[str]]] = []
    if not data:
        return results

    if isinstance(data, dict):
        if "Measure" in data or "Column" in data or "Aggregation" in data:
            tbl, prop, ftype, agg = _extract_field_details(data, alias_map)
            if tbl and prop:
                results.append((tbl, prop, ftype, agg))
                return results

        for k, v in data.items():
            if k == "expr" and isinstance(v, dict):
                tbl, prop, ftype, agg = _extract_field_details(v, alias_map)
                if tbl and prop:
                    results.append((tbl, prop, ftype, agg))
                else:
                    results.extend(_find_dynamic_expressions(v, alias_map))
            elif isinstance(v, (dict, list)):
                results.extend(_find_dynamic_expressions(v, alias_map))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_dynamic_expressions(item, alias_map))

    return results


def _parse_where_condition(where_list: List[Dict[str, Any]]) -> Tuple[Optional[str], List[str], str]:
    """
    Parses Power BI AST Where conditions into operator, applied values, and readable condition string.
    """
    if not where_list or not isinstance(where_list, list):
        return None, [], "All (No filter applied)"

    for item in where_list:
        cond = item.get("Condition", {})
        if not cond:
            continue

        # In condition: In { Expressions: [...], Values: [[{Literal: {Value: ...}}]] }
        if "In" in cond:
            in_obj = cond["In"]
            vals = []
            for row in in_obj.get("Values", []):
                if isinstance(row, list) and len(row) > 0 and isinstance(row[0], dict):
                    lit = row[0].get("Literal", {}).get("Value")
                    if lit is not None:
                        vals.append(str(lit).strip("'"))
            if vals:
                return "In", vals, f"In ({', '.join(vals)})"

        # Not condition
        if "Not" in cond:
            sub = cond["Not"].get("Expression", {})
            if "In" in sub:
                vals = []
                for row in sub["In"].get("Values", []):
                    if isinstance(row, list) and len(row) > 0 and isinstance(row[0], dict):
                        lit = row[0].get("Literal", {}).get("Value")
                        if lit is not None:
                            vals.append(str(lit).strip("'"))
                if vals:
                    return "NotIn", vals, f"Exclude ({', '.join(vals)})"
            if "Comparison" in sub:
                comp = sub["Comparison"]
                right_lit = comp.get("Right", {}).get("Literal", {}).get("Value")
                if right_lit is not None:
                    val = str(right_lit).strip("'")
                    return "!=", [val], f"!= {val}"

        # Comparison condition: Comparison { ComparisonKind, Left, Right }
        if "Comparison" in cond:
            comp = cond["Comparison"]
            kind = comp.get("ComparisonKind", 0)
            kind_map = {0: "==", 1: "<", 2: "<=", 3: ">", 4: ">="}
            op = kind_map.get(kind, "==")
            right_lit = comp.get("Right", {}).get("Literal", {}).get("Value")
            val = str(right_lit).strip("'") if right_lit is not None else ""
            return op, [val], f"{op} {val}"

        # Between condition
        if "Between" in cond:
            b_obj = cond["Between"]
            low = str(b_obj.get("Lower", {}).get("Literal", {}).get("Value", "")).strip("'")
            upp = str(b_obj.get("Upper", {}).get("Literal", {}).get("Value", "")).strip("'")
            return "Between", [low, upp], f"Between {low} and {upp}"

    return "Filtered", [], "Filtered"


def _calculate_spatial_position(pos: Dict[str, Any], page_width: float, page_height: float) -> SpatialPosition:
    """Calculates visual center and quadrant zone relative to canvas dimensions."""
    x = float(pos.get("x", 0.0))
    y = float(pos.get("y", 0.0))
    width = float(pos.get("width", 0.0))
    height = float(pos.get("height", 0.0))
    z = int(pos.get("z", 0))

    center_x = round(x + (width / 2.0), 1)
    center_y = round(y + (height / 2.0), 1)

    eff_width = page_width if page_width > 0 else 1920.0
    eff_height = page_height if page_height > 0 else 1080.0

    w_ratio = center_x / eff_width
    h_ratio = center_y / eff_height

    if w_ratio < 0.33:
        h_zone = "Left"
    elif w_ratio <= 0.66:
        h_zone = "Center"
    else:
        h_zone = "Right"

    if h_ratio < 0.33:
        v_zone = "Top"
    elif h_ratio <= 0.66:
        v_zone = "Middle"
    else:
        v_zone = "Bottom"

    if v_zone == "Middle" and h_zone == "Center":
        zone = "Center"
    else:
        zone = f"{v_zone}-{h_zone}"

    bbox = BoundingBox(x=round(x, 1), y=round(y, 1), width=round(width, 1), height=round(height, 1), z=z)
    return SpatialPosition(center_x=center_x, center_y=center_y, zone=zone, bounding_box=bbox)


def _resolve_canvas_position(
    container_id: str,
    containers_meta: Dict[str, Dict[str, Any]],
) -> Tuple[float, float, bool]:
    """
    Recursively resolves the absolute (x, y) coordinates on the root canvas
    by traversing up the parentGroupName hierarchy until reaching the container
    directly contained in the canvas.
    Also propagates visibility: if any ancestor container is hidden,
    the visual inherits is_hidden=True.
    """
    if container_id not in containers_meta:
        return 0.0, 0.0, False

    info = containers_meta[container_id]
    abs_x = float(info.get("x", 0.0))
    abs_y = float(info.get("y", 0.0))
    inherited_hidden = bool(info.get("is_hidden", False))

    curr_parent = info.get("parent_group_name")
    visited = {container_id}

    while curr_parent and curr_parent in containers_meta:
        if curr_parent in visited:
            break
        visited.add(curr_parent)
        parent_info = containers_meta[curr_parent]
        abs_x += float(parent_info.get("x", 0.0))
        abs_y += float(parent_info.get("y", 0.0))
        if parent_info.get("is_hidden", False):
            inherited_hidden = True
        curr_parent = parent_info.get("parent_group_name")

    return abs_x, abs_y, inherited_hidden


class ReportParser:
    """
    Parses Power BI Report projects (*.Report) into normalized PBIPReportModel.
    Supports both modern PBIR (folder-based) and Legacy (report.json monolithic) formats.
    """

    def parse(self, target_path: str) -> PBIPReportModel:
        """
        Main entry point for report parsing.
        Accepts path to *.Report directory, parent workspace folder, or report.json file.
        """
        report_dir, report_format = self._resolve_report_target(target_path)
        report_name = report_dir.stem if report_dir.suffix.lower() == ".report" else report_dir.name

        if report_format == "PBIR":
            pages = self._parse_pbir_pages(report_dir)
        else:
            pages = self._parse_legacy_pages(report_dir)

        # Build summary statistics
        total_pages = len(pages)
        visible_pages = sum(1 for p in pages if not p.is_hidden)
        hidden_pages = total_pages - visible_pages

        total_visuals = sum(len(p.visuals) for p in pages)
        visual_dist: Dict[str, int] = {}
        for p in pages:
            for v in p.visuals:
                vt = v.visual_type or "unknown"
                visual_dist[vt] = visual_dist.get(vt, 0) + 1

        summary = ReportSummary(
            total_pages=total_pages,
            visible_pages=visible_pages,
            hidden_pages=hidden_pages,
            total_visuals=total_visuals,
            visual_types_distribution=visual_dist,
        )

        return PBIPReportModel(
            report_name=report_name,
            format=report_format,
            source_path=str(report_dir),
            summary=summary,
            pages=pages,
        )

    def _resolve_report_target(self, target_path: str) -> Tuple[Path, str]:
        """Resolves directory and determines whether format is PBIR or Legacy."""
        path = Path(target_path)

        if not path.exists():
            raise FileNotFoundError(f"Report target path not found: {target_path}")

        # If a direct report.json file is given
        if path.is_file() and path.name.lower() == "report.json":
            # Check if it's inside definition/ (PBIR) or root of report (Legacy)
            if path.parent.name == "definition" and (path.parent / "pages").exists():
                return path.parent.parent, "PBIR"
            return path.parent, "LEGACY"

        # If a .pbip file is given, find sibling .Report directory
        if path.is_file() and path.suffix.lower() == ".pbip":
            sibling_report = path.parent / f"{path.stem}.Report"
            if sibling_report.exists():
                return self._resolve_report_target(str(sibling_report))

        if path.is_dir():
            # Direct .Report directory
            if (path / "definition" / "pages").exists():
                return path, "PBIR"
            if (path / "report.json").exists():
                return path, "LEGACY"

            # Check for subdirectories ending in .Report
            for sub in path.glob("*.Report"):
                if (sub / "definition" / "pages").exists():
                    return sub, "PBIR"
                if (sub / "report.json").exists():
                    return sub, "LEGACY"

            # Recursive search for definition/pages or report.json
            for sub in path.rglob("definition"):
                if sub.is_dir() and (sub / "pages").exists():
                    return sub.parent, "PBIR"
            for r_json in path.rglob("report.json"):
                if r_json.parent.name == "definition" and (r_json.parent / "pages").exists():
                    return r_json.parent.parent, "PBIR"
                return r_json.parent, "LEGACY"

        raise FileNotFoundError(f"Could not locate a valid PBIR or Legacy report structure in: {target_path}")

    # =========================================================================
    # PBIR Parser Implementation
    # =========================================================================

    def _parse_pbir_pages(self, report_dir: Path) -> List[PageDefinition]:
        def_dir = report_dir / "definition"
        pages_dir = def_dir / "pages"
        pages_meta_file = pages_dir / "pages.json"

        page_order: List[str] = []
        if pages_meta_file.exists():
            try:
                with open(pages_meta_file, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                page_order = pdata.get("pageOrder", [])
            except Exception:
                page_order = []


        # Find all page subfolders
        page_dirs = [pages_dir / p for p in page_order if (pages_dir / p).is_dir()]
        if not page_dirs:
            page_dirs = sorted([p for p in pages_dir.iterdir() if p.is_dir()], key=lambda d: d.name)

        pages: List[PageDefinition] = []

        for idx, pdir in enumerate(page_dirs, start=1):
            page_file = pdir / "page.json"
            if not page_file.exists():
                continue

            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    pjson = json.load(f)
            except Exception:
                continue


            page_id = pjson.get("name", pdir.name)
            display_name = pjson.get("displayName", page_id)
            width = int(pjson.get("width", 1920))
            height = int(pjson.get("height", 1080))
            is_hidden = pjson.get("visibility") == "HiddenInViewMode"

            raw_type = pjson.get("type", "Normal").upper()
            if "TOOLTIP" in raw_type:
                page_type = "TOOLTIP"
            elif "DRILLTHROUGH" in raw_type:
                page_type = "DRILLTHROUGH"
            else:
                page_type = "NORMAL"

            # Parse page-level filter panel filters
            locked_filters, unlocked_filters = self._parse_filter_config(pjson.get("filterConfig"))

            # First pass: collect page slicers
            page_slicers = self._collect_pbir_page_slicers(pdir)

            # Second pass: parse visuals
            visuals = self._parse_pbir_visuals(
                pdir,
                page_width=width,
                page_height=height,
                locked_filters=locked_filters,
                unlocked_filters=unlocked_filters,
                page_slicers=page_slicers,
            )

            pages.append(
                PageDefinition(
                    page_id=page_id,
                    display_name=display_name,
                    page_number=idx,
                    is_hidden=is_hidden,
                    page_type=page_type,
                    width=width,
                    height=height,
                    visuals=visuals,
                )
            )

        return pages

    def _collect_pbir_page_slicers(self, page_dir: Path) -> List[PageSlicer]:
        slicers: List[PageSlicer] = []
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.exists():
            return slicers

        for vdir in visuals_dir.iterdir():
            if not vdir.is_dir():
                continue
            vfile = vdir / "visual.json"
            if not vfile.exists():
                continue

            try:
                with open(vfile, "r", encoding="utf-8") as f:
                    vjson = json.load(f)
            except Exception:
                continue


            v_info = vjson.get("visual", {})
            vt = v_info.get("visualType", "").lower()

            if vt in SLICER_VISUAL_TYPES:
                v_id = vjson.get("name", vdir.name)
                qs = v_info.get("query", {}).get("queryState", {})
                for role, role_content in qs.items():
                    for proj in role_content.get("projections", []):
                        f_obj = proj.get("field", {})
                        table, field_name, _, _ = _extract_field_details(f_obj)
                        if table and field_name:
                            slicers.append(
                                PageSlicer(
                                    slicer_visual_id=v_id,
                                    table=table,
                                    field=field_name,
                                    model_key=f"{table}[{field_name}]",
                                    default_selection="All",
                                    is_synced_across_pages=False,
                                )
                            )
        return slicers

    def _parse_pbir_visuals(
        self,
        page_dir: Path,
        page_width: int,
        page_height: int,
        locked_filters: List[PagePanelFilter],
        unlocked_filters: List[PagePanelFilter],
        page_slicers: List[PageSlicer],
    ) -> List[VisualDefinition]:
        visuals: List[VisualDefinition] = []
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.exists():
            return visuals

        # Pass 1: Collect metadata for all containers on the page
        containers_meta: Dict[str, Dict[str, Any]] = {}
        containers_raw: List[Dict[str, Any]] = []

        for vdir in sorted(visuals_dir.iterdir(), key=lambda d: d.name):
            if not vdir.is_dir():
                continue
            vfile = vdir / "visual.json"
            if not vfile.exists():
                continue

            try:
                with open(vfile, "r", encoding="utf-8") as f:
                    vjson = json.load(f)
            except Exception:
                continue

            v_id = vjson.get("name", vdir.name)
            v_info = vjson.get("visual", {})
            pos_dict = vjson.get("position", {})
            parent_group = vjson.get("parentGroupName")
            is_group = bool("visualGroup" in vjson or (not v_info and "singleVisual" not in vjson))
            is_hidden = bool(
                vjson.get("isHidden", False)
                or v_info.get("isHidden", False)
                or vjson.get("visualGroup", {}).get("isHidden", False)
            )

            meta = {
                "id": v_id,
                "x": float(pos_dict.get("x", 0.0)),
                "y": float(pos_dict.get("y", 0.0)),
                "width": float(pos_dict.get("width", 0.0)),
                "height": float(pos_dict.get("height", 0.0)),
                "z": int(pos_dict.get("z", 0)),
                "parent_group_name": parent_group,
                "is_hidden": is_hidden,
                "is_group": is_group,
                "vjson": vjson,
                "v_info": v_info,
            }
            containers_meta[v_id] = meta
            containers_raw.append(meta)

        # Pass 2: Process leaf visual elements (skip pure visual groups)
        for meta in containers_raw:
            if meta["is_group"]:
                continue

            v_id = meta["id"]
            vjson = meta["vjson"]
            v_info = meta["v_info"]
            visual_type = v_info.get("visualType", "unknown")
            is_slicer = visual_type.lower() in SLICER_VISUAL_TYPES

            # Resolve absolute canvas position recursively from root parent
            abs_x, abs_y, inherited_hidden = _resolve_canvas_position(v_id, containers_meta)
            effective_is_hidden = meta["is_hidden"] or inherited_hidden

            # Spatial positioning relative to root canvas
            resolved_pos = {
                "x": abs_x,
                "y": abs_y,
                "width": meta["width"],
                "height": meta["height"],
                "z": meta["z"],
            }
            spatial_pos = _calculate_spatial_position(resolved_pos, page_width, page_height)

            # Query projections & active filters
            qs = v_info.get("query", {}).get("queryState", {})
            evaluated_metrics: List[EvaluatedMetric] = []
            slicing_coordinates: List[SlicingCoordinate] = []

            for role_name, role_data in qs.items():
                role_lower = role_name.lower()
                for proj in role_data.get("projections", []):
                    f_obj = proj.get("field", {})
                    table, prop, f_type, agg = _extract_field_details(f_obj)
                    if not prop:
                        continue

                    tbl_name = table or "Unknown"
                    model_key = f"{tbl_name}[{prop}]"

                    if is_slicer:
                        # Slicers are tracked in page_slicers, but also record their coordinate
                        slicing_coordinates.append(
                            SlicingCoordinate(role=f"Slicer ({role_name})", table=tbl_name, field=prop, model_key=model_key)
                        )
                    elif role_lower in VALUE_METRIC_ROLES:
                        evaluated_metrics.append(
                            EvaluatedMetric(
                                table=tbl_name,
                                field=prop,
                                field_type=f_type,
                                role=role_name,
                                model_key=model_key,
                                aggregation=agg,
                            )
                        )
                    else:
                        slicing_coordinates.append(
                            SlicingCoordinate(role=role_name, table=tbl_name, field=prop, model_key=model_key)
                        )

            # Visual active filters
            visual_active_filters: List[ActiveFilter] = []
            vf_config = vjson.get("filterConfig") or v_info.get("filterConfig")
            if vf_config:
                visual_active_filters = self._parse_active_visual_filters(vf_config)

            # Object expression scanning for dynamic text / conditional formatting
            known_keys = {m.model_key for m in evaluated_metrics}
            for obj_container in [vjson.get("visualContainerObjects"), vjson.get("objects"), v_info.get("objects")]:
                if obj_container:
                    dyn_exprs = _find_dynamic_expressions(obj_container)
                    for tbl, prop, f_type, agg in dyn_exprs:
                        m_key = f"{tbl}[{prop}]"
                        if m_key not in known_keys:
                            evaluated_metrics.append(
                                EvaluatedMetric(
                                    table=tbl,
                                    field=prop,
                                    field_type=f_type,
                                    role="DynamicProperty",
                                    model_key=m_key,
                                    aggregation=agg,
                                )
                            )
                            known_keys.add(m_key)

            # Title extraction / synthesis
            title = self._extract_custom_title(vjson)
            if not title:
                title = self._synthesize_visual_title(visual_type, evaluated_metrics, slicing_coordinates, is_slicer)

            calc_context = CalculationContext(
                evaluated_metrics=evaluated_metrics,
                slicing_coordinates=slicing_coordinates,
                visual_active_filters=visual_active_filters,
                locked_active_filters=locked_filters,
                unlocked_available_filters=unlocked_filters,
                page_slicers=page_slicers,
            )

            visuals.append(
                VisualDefinition(
                    visual_id=v_id,
                    title=title,
                    visual_type=visual_type,
                    is_hidden=effective_is_hidden,
                    is_slicer=is_slicer,
                    spatial_position=spatial_pos,
                    calculation_context=calc_context,
                    parent_group_name=meta.get("parent_group_name"),
                )
            )

        return visuals

    # =========================================================================
    # Legacy Parser Implementation
    # =========================================================================

    def _parse_legacy_pages(self, report_dir: Path) -> List[PageDefinition]:
        r_file = report_dir / "report.json"
        try:
            with open(r_file, "r", encoding="utf-8") as f:
                rdata = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load legacy report.json: {e}")

        sections = rdata.get("sections", [])
        pages: List[PageDefinition] = []

        for idx, s in enumerate(sections, start=1):
            page_id = s.get("name", f"Section_{idx}")
            display_name = s.get("displayName", page_id)
            width = int(s.get("width", 1280))
            height = int(s.get("height", 720))

            # Visibility: 1 is hidden, 0 is visible
            is_hidden = s.get("visibility") == 1

            # Parse section filter panel filters
            raw_filters = s.get("filters")
            if isinstance(raw_filters, str):
                try:
                    raw_filters = json.loads(raw_filters)
                except Exception:
                    raw_filters = []
            locked_filters, unlocked_filters = self._parse_legacy_filter_list(raw_filters or [])

            vcs = s.get("visualContainers", [])

            # First pass: collect legacy page slicers
            page_slicers = self._collect_legacy_page_slicers(vcs)

            # Second pass: parse visuals
            visuals = self._parse_legacy_visuals(
                vcs,
                page_width=width,
                page_height=height,
                locked_filters=locked_filters,
                unlocked_filters=unlocked_filters,
                page_slicers=page_slicers,
            )

            pages.append(
                PageDefinition(
                    page_id=page_id,
                    display_name=display_name,
                    page_number=idx,
                    is_hidden=is_hidden,
                    page_type="NORMAL",
                    width=width,
                    height=height,
                    visuals=visuals,
                )
            )

        return pages

    def _collect_legacy_page_slicers(self, vcs: List[Dict[str, Any]]) -> List[PageSlicer]:
        slicers: List[PageSlicer] = []
        for vc in vcs:
            cfg = self._parse_json_field(vc.get("config"))
            sv = cfg.get("singleVisual", {})
            vt = sv.get("visualType", "").lower()
            if vt in SLICER_VISUAL_TYPES:
                v_id = cfg.get("name", str(vc.get("z", "")))
                alias_map = self._build_alias_map(sv.get("prototypeQuery", {}).get("From", []))
                for role, projs in sv.get("projections", {}).items():
                    for p in projs:
                        qref = p.get("queryRef", "")
                        matched_select = self._find_select_by_name(sv.get("prototypeQuery", {}).get("Select", []), qref)
                        if matched_select:
                            table, prop, _, _ = _extract_field_details(matched_select, alias_map)
                        else:
                            parts = qref.split(".", 1)
                            table, prop = (parts[0], parts[1]) if len(parts) == 2 else ("Unknown", qref)
                        if table and prop:
                            slicers.append(
                                PageSlicer(
                                    slicer_visual_id=v_id,
                                    table=table,
                                    field=prop,
                                    model_key=f"{table}[{prop}]",
                                    default_selection="All",
                                    is_synced_across_pages=False,
                                )
                            )
        return slicers

    def _parse_legacy_visuals(
        self,
        vcs: List[Dict[str, Any]],
        page_width: int,
        page_height: int,
        locked_filters: List[PagePanelFilter],
        unlocked_filters: List[PagePanelFilter],
        page_slicers: List[PageSlicer],
    ) -> List[VisualDefinition]:
        visuals: List[VisualDefinition] = []

        # Pass 1: Collect metadata for all containers on the page
        containers_meta: Dict[str, Dict[str, Any]] = {}
        containers_raw: List[Dict[str, Any]] = []

        for idx, vc in enumerate(vcs):
            cfg = self._parse_json_field(vc.get("config"))
            sv = cfg.get("singleVisual", {})
            svg = cfg.get("singleVisualGroup", {})
            v_id = cfg.get("name", str(vc.get("z", f"vc_{idx}")))
            parent_group = cfg.get("parentGroupName") or vc.get("parentGroupName")
            is_group = bool("singleVisualGroup" in cfg or (not sv and "visual" not in cfg))
            is_hidden = bool(
                vc.get("isHidden", False)
                or cfg.get("isHidden", False)
                or svg.get("isHidden", False)
                or sv.get("isHidden", False)
            )

            meta = {
                "id": v_id,
                "x": float(vc.get("x", 0.0)),
                "y": float(vc.get("y", 0.0)),
                "width": float(vc.get("width", 0.0)),
                "height": float(vc.get("height", 0.0)),
                "z": int(vc.get("z", 0)),
                "parent_group_name": parent_group,
                "is_hidden": is_hidden,
                "is_group": is_group,
                "vc": vc,
                "cfg": cfg,
                "sv": sv,
            }
            containers_meta[v_id] = meta
            containers_raw.append(meta)

        # Pass 2: Process leaf visual elements (skip pure visual groups)
        for meta in containers_raw:
            if meta["is_group"]:
                continue

            v_id = meta["id"]
            vc = meta["vc"]
            cfg = meta["cfg"]
            sv = meta["sv"]
            visual_type = sv.get("visualType", "unknown")
            is_slicer = visual_type.lower() in SLICER_VISUAL_TYPES

            # Resolve absolute canvas position recursively from root parent
            abs_x, abs_y, inherited_hidden = _resolve_canvas_position(v_id, containers_meta)
            effective_is_hidden = meta["is_hidden"] or inherited_hidden

            # Spatial positioning relative to root canvas
            resolved_pos = {
                "x": abs_x,
                "y": abs_y,
                "width": meta["width"],
                "height": meta["height"],
                "z": meta["z"],
            }
            spatial_pos = _calculate_spatial_position(resolved_pos, page_width, page_height)

            # Query & projections
            alias_map = self._build_alias_map(sv.get("prototypeQuery", {}).get("From", []))
            select_list = sv.get("prototypeQuery", {}).get("Select", [])

            evaluated_metrics: List[EvaluatedMetric] = []
            slicing_coordinates: List[SlicingCoordinate] = []

            for role_name, projs in sv.get("projections", {}).items():
                role_lower = role_name.lower()
                for p in projs:
                    qref = p.get("queryRef", "")
                    matched_select = self._find_select_by_name(select_list, qref)
                    if matched_select:
                        table, prop, f_type, agg = _extract_field_details(matched_select, alias_map)
                    else:
                        parts = qref.split(".", 1)
                        table, prop = (parts[0], parts[1]) if len(parts) == 2 else ("Unknown", qref)
                        f_type = "MEASURE" if role_lower in VALUE_METRIC_ROLES else "COLUMN"
                        agg = None

                    if not prop:
                        continue

                    tbl_name = table or "Unknown"
                    model_key = f"{tbl_name}[{prop}]"

                    if is_slicer:
                        slicing_coordinates.append(
                            SlicingCoordinate(role=f"Slicer ({role_name})", table=tbl_name, field=prop, model_key=model_key)
                        )
                    elif role_lower in VALUE_METRIC_ROLES:
                        evaluated_metrics.append(
                            EvaluatedMetric(
                                table=tbl_name,
                                field=prop,
                                field_type=f_type,
                                role=role_name,
                                model_key=model_key,
                                aggregation=agg,
                            )
                        )
                    else:
                        slicing_coordinates.append(
                            SlicingCoordinate(role=role_name, table=tbl_name, field=prop, model_key=model_key)
                        )

            # Visual active filters
            raw_vf = self._parse_json_field(vc.get("filters"))
            visual_active_filters: List[ActiveFilter] = []
            if isinstance(raw_vf, list):
                for f_item in raw_vf:
                    f_obj = f_item.get("expression") or f_item.get("field")
                    tbl, f_name, _, _ = _extract_field_details(f_obj)
                    if tbl and f_name:
                        where = f_item.get("filter", {}).get("Where", [])
                        if where:
                            _, _, cond_str = _parse_where_condition(where)
                            visual_active_filters.append(
                                ActiveFilter(
                                    table=tbl,
                                    field=f_name,
                                    filter_type=f_item.get("type", "Categorical"),
                                    condition=cond_str,
                                    scope="Visual",
                                )
                            )

            # Object expression scanning for dynamic text / conditional formatting
            known_keys = {m.model_key for m in evaluated_metrics}
            for obj_container in [sv.get("objects"), cfg.get("objects"), vc.get("objects")]:
                if obj_container:
                    dyn_exprs = _find_dynamic_expressions(obj_container, alias_map)
                    for tbl, prop, f_type, agg in dyn_exprs:
                        m_key = f"{tbl}[{prop}]"
                        if m_key not in known_keys:
                            evaluated_metrics.append(
                                EvaluatedMetric(
                                    table=tbl,
                                    field=prop,
                                    field_type=f_type,
                                    role="DynamicProperty",
                                    model_key=m_key,
                                    aggregation=agg,
                                )
                            )
                            known_keys.add(m_key)

            title = self._extract_custom_title(cfg, alias_map) or self._extract_custom_title(sv, alias_map)
            if not title:
                title = self._synthesize_visual_title(visual_type, evaluated_metrics, slicing_coordinates, is_slicer)

            calc_context = CalculationContext(
                evaluated_metrics=evaluated_metrics,
                slicing_coordinates=slicing_coordinates,
                visual_active_filters=visual_active_filters,
                locked_active_filters=locked_filters,
                unlocked_available_filters=unlocked_filters,
                page_slicers=page_slicers,
            )

            visuals.append(
                VisualDefinition(
                    visual_id=v_id,
                    title=title,
                    visual_type=visual_type,
                    is_hidden=effective_is_hidden,
                    is_slicer=is_slicer,
                    spatial_position=spatial_pos,
                    calculation_context=calc_context,
                    parent_group_name=meta.get("parent_group_name"),
                )
            )

        return visuals

    # =========================================================================
    # Common Filter & Helper Utilities
    # =========================================================================

    def _parse_filter_config(
        self, filter_config: Optional[Dict[str, Any]]
    ) -> Tuple[List[PagePanelFilter], List[PagePanelFilter]]:
        """Parses page-level filterConfig into locked active filters and unlocked available filters."""
        locked: List[PagePanelFilter] = []
        unlocked: List[PagePanelFilter] = []

        if not filter_config or not isinstance(filter_config, dict):
            return locked, unlocked

        filters_list = filter_config.get("filters", [])
        return self._parse_legacy_filter_list(filters_list)

    def _parse_legacy_filter_list(
        self, filters_list: List[Dict[str, Any]]
    ) -> Tuple[List[PagePanelFilter], List[PagePanelFilter]]:
        locked: List[PagePanelFilter] = []
        unlocked: List[PagePanelFilter] = []

        for f_item in filters_list:
            if not isinstance(f_item, dict):
                continue

            f_obj = f_item.get("field") or f_item.get("expression")
            table, field_name, _, _ = _extract_field_details(f_obj)
            if not table or not field_name:
                continue

            is_locked = bool(f_item.get("isLockedInViewMode", False))
            where = f_item.get("filter", {}).get("Where", [])

            if where:
                op, vals, cond_str = _parse_where_condition(where)
                has_active_filter = True
            else:
                op, vals, cond_str = None, None, "All (No filter applied)"
                has_active_filter = False

            if is_locked:
                # User requirement: ONLY include locked filters if they actively constrain!
                if has_active_filter:
                    locked.append(
                        PagePanelFilter(
                            scope="Page Filter Panel (Locked)",
                            table=table,
                            field=field_name,
                            is_locked=True,
                            applied_values=vals,
                            default_value=cond_str,
                            operator=op,
                        )
                    )
            else:
                unlocked.append(
                    PagePanelFilter(
                        scope="Page Filter Panel (Interactive)",
                        table=table,
                        field=field_name,
                        is_locked=False,
                        applied_values=vals if has_active_filter else None,
                        default_value=cond_str,
                        operator=op,
                    )
                )

        return locked, unlocked

    def _parse_active_visual_filters(self, filter_config: Dict[str, Any]) -> List[ActiveFilter]:
        active: List[ActiveFilter] = []
        filters_list = filter_config.get("filters", [])
        for f_item in filters_list:
            if not isinstance(f_item, dict):
                continue
            where = f_item.get("filter", {}).get("Where", [])
            if not where:
                continue
            f_obj = f_item.get("field") or f_item.get("expression")
            table, prop, _, _ = _extract_field_details(f_obj)
            if table and prop:
                _, _, cond_str = _parse_where_condition(where)
                active.append(
                    ActiveFilter(
                        table=table,
                        field=prop,
                        filter_type=f_item.get("type", "Categorical"),
                        condition=cond_str,
                        scope="Visual",
                    )
                )
        return active

    def _extract_custom_title(
        self, vjson: Dict[str, Any], alias_map: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Tries to extract user-defined title from visual objects (both static and dynamic expressions)."""
        if not vjson or not isinstance(vjson, dict):
            return None

        candidate_containers = [
            vjson.get("visualContainerObjects", {}),
            vjson.get("visual", {}).get("objects", {}),
            vjson.get("objects", {}),
            vjson.get("singleVisual", {}).get("objects", {}),
        ]
        for container in candidate_containers:
            if not isinstance(container, dict):
                continue
            title_objs = container.get("title", [])
            if isinstance(title_objs, list) and len(title_objs) > 0:
                t_props = title_objs[0].get("properties", {})
                expr = t_props.get("text", {}).get("expr", {})
                lit_val = expr.get("Literal", {}).get("Value")
                if lit_val is not None:
                    clean_title = str(lit_val).strip("'")
                    if clean_title:
                        return clean_title
                tbl, prop, _, _ = _extract_field_details(expr, alias_map)
                if tbl and prop:
                    return f"Dynamic Title: {tbl}[{prop}]"
        return None

    def _synthesize_visual_title(
        self,
        visual_type: str,
        evaluated_metrics: List[EvaluatedMetric],
        slicing_coordinates: List[SlicingCoordinate],
        is_slicer: bool,
    ) -> str:
        """Synthesizes human-friendly title if no custom title is defined in formatting."""
        if is_slicer:
            if slicing_coordinates:
                first = slicing_coordinates[0]
                return f"Slicer: {first.table}[{first.field}]"
            return "Slicer Control"

        if evaluated_metrics and slicing_coordinates:
            m_names = ", ".join(m.field for m in evaluated_metrics[:2])
            c_name = slicing_coordinates[0].field
            return f"{m_names} by {c_name}"

        if evaluated_metrics:
            return ", ".join(m.field for m in evaluated_metrics)

        if visual_type.lower() in ("textbox", "shape", "image"):
            return visual_type.capitalize()

        return f"Untitled {visual_type}"

    def _build_alias_map(self, from_list: List[Dict[str, Any]]) -> Dict[str, str]:
        """Builds mapping from source alias (e.g. 'o1') to Entity name (e.g. 'Opportunities')."""
        alias_map: Dict[str, str] = {}
        for item in from_list:
            alias = item.get("Name")
            entity = item.get("Entity")
            if alias and entity:
                alias_map[alias] = entity
        return alias_map

    def _find_select_by_name(self, select_list: List[Dict[str, Any]], query_ref: str) -> Optional[Dict[str, Any]]:
        for s in select_list:
            if s.get("Name") == query_ref:
                return s
        return None

    def _parse_json_field(self, field_val: Any) -> Any:
        if isinstance(field_val, str):
            try:
                return json.loads(field_val)
            except Exception:
                return {}
        return field_val if field_val is not None else {}
