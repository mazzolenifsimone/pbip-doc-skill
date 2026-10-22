"""
Command-line interface (CLI) for pbip-doc-skill.
Vanilla Python - no third-party CLI dependencies required.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .parser import PBIPParser
from .docgen import DocGenConfig, MarkdownDocGenerator, HtmlDocGenerator


def _load_cli_config(args, base_path: Optional[str] = None) -> DocGenConfig:
    """Helper to resolve DocGenConfig from --config, --set, local pbip_doc.config.json or defaults."""
    config_file = getattr(args, "config", None)
    if config_file and os.path.exists(config_file):
        config = DocGenConfig.load_from_file(config_file)
    else:
        if base_path:
            target_dir = base_path if os.path.isdir(base_path) else os.path.dirname(base_path)
            config = DocGenConfig.find_and_load_default(target_dir)
        else:
            config = DocGenConfig.find_and_load_default()

    # 1. Key=Value overrides via --set (supports multiple occurrences)
    set_args = getattr(args, "set", None)
    if set_args:
        for item in set_args:
            try:
                k, v = DocGenConfig.parse_set_arg(item)
                config.apply_overrides({k: v})
            except Exception as e:
                print(f"[ERROR] Failed to apply --set '{item}': {e}", file=sys.stderr)
                sys.exit(1)

    # 3. CLI flag overrides (backward compatibility & ergonomical shortcuts)
    if getattr(args, "include_auto_tables", False):
        config.exclude_auto_date_tables = False

    if getattr(args, "include_inherited_entities", False):
        config.include_inherited_entities = True

    if getattr(args, "exclude_tables", None):
        extra_excludes = [t.strip() for t in args.exclude_tables.split(",") if t.strip()]
        config.excluded_tables.extend(extra_excludes)

    if getattr(args, "base_doc_url", None):
        config.base_doc_url = args.base_doc_url

    if getattr(args, "external_docs_base_url", None):
        config.external_docs_base_url = args.external_docs_base_url

    if getattr(args, "external_doc_path", None):
        for item in args.external_doc_path:
            if "=" in item:
                k, v = item.split("=", 1)
                config.external_doc_paths[k.strip()] = v.strip()

    if getattr(args, "project_name", None):
        config.project_name = args.project_name

    if getattr(args, "report_dataset_name", None):
        config.report_dataset_name = args.report_dataset_name

    if getattr(args, "format", None):
        config.output_format = args.format

    if getattr(args, "theme", None):
        config.html_theme = args.theme

    if getattr(args, "html_title", None):
        config.html_title = args.html_title

    return config


def _add_config_arguments(p: argparse.ArgumentParser):
    """Adds common configuration flags (--config, --set, --print-config, URL flags) to a parser."""
    p.add_argument(
        "-c", "--config",
        help="Path to custom JSON configuration file (e.g. pbip_doc.config.json)",
    )
    p.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Override a specific configuration setting (e.g. --set include_table_m_code=false). Can be repeated.",
    )
    p.add_argument(
        "--print-config",
        action="store_true",
        help="Print the effective configuration to stdout before executing.",
    )
    p.add_argument(
        "--base-doc-url", "--base-doc-path",
        dest="base_doc_url",
        default=None,
        help="Base URL or absolute path for the documentation currently being generated (e.g. web portal, intranet wiki, or documentation server root).",
    )
    p.add_argument(
        "--external-docs-base-url", "--external-docs-base-path",
        dest="external_docs_base_url",
        default=None,
        help="Base URL or directory path containing documentation for all external models (organized as <url>/<model_name>/).",
    )
    p.add_argument(
        "--external-doc-path",
        action="append",
        metavar="NAME=URL",
        help="Set documentation absolute path for a specific external reference by name (e.g. --external-doc-path CentralDataModel=https://docs.company.internal/CentralDataModel). Can be repeated.",
    )


def main():
    parser = argparse.ArgumentParser(
        prog="pbip-doc-skill",
        description="pbip-doc-skill: PBIP Semantic Model Documentation & Dependency Resolver Engine (Pure Vanilla Python)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: extract
    extract_parser = subparsers.add_parser("extract", help="Parse semantic model and export standardized JSON")
    extract_parser.add_argument("path", help="Path to PBIP folder, definition/ folder, or model.bim file")
    extract_parser.add_argument(
        "-o", "--output",
        default="semantic_model_documentation.json",
        help="Target output JSON file path (default: semantic_model_documentation.json)",
    )
    extract_parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2, use 0 for minified)",
    )
    _add_config_arguments(extract_parser)
    extract_parser.add_argument(
        "--include-auto-tables",
        action="store_true",
        help="Include Power BI auto-generated date tables (LocalDateTable_*, DateTableTemplate_*) in documentation",
    )
    extract_parser.add_argument(
        "--include-inherited-entities",
        action="store_true",
        help="Mark inherited entities (partition = entity) and external measures as in-scope in extracted JSON",
    )
    extract_parser.add_argument(
        "--exclude-tables",
        help="Comma-separated table names to exclude from documentation (e.g. TableA,TableB)",
    )

    # Command: inspect
    inspect_parser = subparsers.add_parser("inspect", help="Display console summary of semantic model topology and dependencies")
    inspect_parser.add_argument("path", help="Path to PBIP folder, definition/ folder, or model.bim file")
    _add_config_arguments(inspect_parser)
    inspect_parser.add_argument(
        "--include-auto-tables",
        action="store_true",
        help="Include Power BI auto-generated date tables in inspection",
    )
    inspect_parser.add_argument(
        "--include-inherited-entities",
        action="store_true",
        help="Include inherited entities (partition = entity) and external measures as in-scope during inspection",
    )
    inspect_parser.add_argument(
        "--exclude-tables",
        help="Comma-separated table names to exclude from inspection",
    )

    # Command: docgen
    docgen_parser = subparsers.add_parser("docgen", help="Generate modular, RAG-ready Markdown docs for every table and measure")
    docgen_parser.add_argument("path", help="Path to semantic model docs JSON file or PBIP folder/model.bim")
    docgen_parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Target output directory for Markdown documents (default: docs/)",
    )
    _add_config_arguments(docgen_parser)
    docgen_parser.add_argument(
        "--include-auto-tables",
        action="store_true",
        help="Include Power BI auto-generated date tables in markdown documentation",
    )
    docgen_parser.add_argument(
        "--include-inherited-entities",
        action="store_true",
        help="Generate standalone documentation files for inherited entities and external measures",
    )
    docgen_parser.add_argument(
        "--exclude-tables",
        help="Comma-separated table names to exclude from markdown documentation",
    )
    docgen_parser.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Omit YAML frontmatter at the top of markdown documents",
    )
    docgen_parser.add_argument(
        "--no-m-code",
        action="store_true",
        help="Omit raw Power Query M code snippets from table documents",
    )
    docgen_parser.add_argument(
        "--tables-dir",
        default=None,
        help="Subdirectory name for table markdowns (default: tables)",
    )
    docgen_parser.add_argument(
        "--measures-dir",
        default=None,
        help="Subdirectory name for measure markdowns (default: measures)",
    )
    docgen_parser.add_argument(
        "--functions-dir",
        default=None,
        help="Subdirectory name for UDF function markdowns (default: functions)",
    )
    docgen_parser.add_argument(
        "--visuals-dir",
        default=None,
        help="Subdirectory name for report page and visual markdowns (default: visuals)",
    )
    docgen_parser.add_argument(
        "--report-path",
        default=None,
        help="Explicit path to associated *.Report folder or report.json file",
    )
    docgen_parser.add_argument(
        "--no-visuals",
        action="store_true",
        help="Disable generation of report page and visual documentation",
    )
    docgen_parser.add_argument(
        "--no-visual-svg-maps",
        action="store_true",
        help="Disable generation of scaled SVG canvas mini-maps for visual documentation",
    )
    docgen_parser.add_argument(
        "--project-name",
        default=None,
        help="Explicit PBIP project name override for frontmatter indexing",
    )
    docgen_parser.add_argument(
        "--report-dataset-name",
        default=None,
        help="Explicit remote/bound semantic model dataset name for report visual table/measure links",
    )
    docgen_parser.add_argument(
        "-f", "--format",
        choices=["markdown", "html", "both"],
        default=None,
        help="Documentation output format: 'markdown', 'html', or 'both' (default: markdown or from config)",
    )
    docgen_parser.add_argument(
        "--theme",
        choices=["auto", "light", "dark"],
        default=None,
        help="Theme for HTML documentation portal (default: auto)",
    )
    docgen_parser.add_argument(
        "--html-title",
        default=None,
        help="Custom header title for HTML documentation portal",
    )

    # Command: config
    config_parser = subparsers.add_parser("config", help="Inspect, export or initialize configuration JSON files")
    _add_config_arguments(config_parser)
    config_parser.add_argument(
        "--init",
        nargs="?",
        const="pbip_doc.config.json",
        metavar="FILEPATH",
        help="Generate a complete configuration JSON file with all settings and defaults (default: pbip_doc.config.json)",
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Print the effective configuration JSON to stdout (incorporating --config and --set)",
    )
    config_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite target file if it already exists when using --init",
    )

    # Command: report-extract
    rep_extract_parser = subparsers.add_parser(
        "report-extract", help="Parse a PBIP *.Report folder and export JSON documentation"
    )
    rep_extract_parser.add_argument("path", help="Path to *.Report folder, PBIP directory, or report.json file")
    rep_extract_parser.add_argument(
        "-o", "--output", default="report_documentation.json", help="Output JSON path (default: report_documentation.json)"
    )
    rep_extract_parser.add_argument(
        "--indent", type=int, default=2, help="Indentation level for output JSON (default: 2)"
    )

    # Command: report-inspect
    rep_inspect_parser = subparsers.add_parser(
        "report-inspect", help="Display console summary of report pages, visuals, spatial zones, and calculation context"
    )
    rep_inspect_parser.add_argument("path", help="Path to *.Report folder, PBIP directory, or report.json file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "config":
        if args.init:
            target_path = Path(args.init)
            if target_path.exists() and not getattr(args, "force", False):
                print(f"[ERROR] Target configuration file '{target_path}' already exists. Use --force to overwrite.", file=sys.stderr)
                sys.exit(1)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            template_data = DocGenConfig.get_template_dict()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] Initialized configuration template at: {target_path.resolve()}")
            print(f"Contains {len(DocGenConfig.get_descriptions())} customizable settings.")
            return

        config = _load_cli_config(args, None)
        print(config.to_json())
        return

    if args.command in ("report-extract", "report-inspect"):
        from .report_parser import ReportParser
        report_parser = ReportParser()
        try:
            report_model = report_parser.parse(args.path)
        except Exception as e:
            print(f"[ERROR] Failed to parse PBIP report: {e}", file=sys.stderr)
            sys.exit(1)

        if args.command == "report-extract":
            indent = args.indent if args.indent > 0 else None
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_model.to_dict(), f, indent=indent, ensure_ascii=False)
            print(f"[SUCCESS] Report presentation metadata successfully extracted!")
            print(f" -> Output written to: {output_path.resolve()}")
            print(f" -> Format: {report_model.format} | Pages: {report_model.summary.total_pages} | Visuals: {report_model.summary.total_visuals}")
            return

        elif args.command == "report-inspect":
            print("=" * 70)
            print(f"PBIP REPORT: {report_model.report_name} (Format: {report_model.format})")
            print("=" * 70)
            print(f"Pages: {report_model.summary.total_pages} ({report_model.summary.visible_pages} visible, {report_model.summary.hidden_pages} hidden) | Total Visuals: {report_model.summary.total_visuals}")
            print(f"Visual types: {report_model.summary.visual_types_distribution}")

            for p in report_model.pages:
                hidden_tag = " [HIDDEN]" if p.is_hidden else ""
                type_tag = f" [{p.page_type}]" if p.page_type != "NORMAL" else ""
                print(f"\nPAGE: '{p.display_name}' (ID: {p.page_id}){type_tag}{hidden_tag} - Size: {p.width}x{p.height}")
                if p.visuals:
                    first_cc = p.visuals[0].calculation_context
                    if first_cc.locked_active_filters:
                        locked_strs = [f"{f.field} {f.default_value}" for f in first_cc.locked_active_filters]
                        print(f"  * Locked Active Page Filters ({len(first_cc.locked_active_filters)}): {', '.join(locked_strs)}")
                    if first_cc.unlocked_available_filters:
                        unlocked_strs = [f"{f.field} (default: {f.default_value})" for f in first_cc.unlocked_available_filters]
                        print(f"  * Unlocked Page Filters ({len(first_cc.unlocked_available_filters)}): {', '.join(unlocked_strs)}")
                    if first_cc.page_slicers:
                        slicer_strs = [s.model_key for s in first_cc.page_slicers]
                        print(f"  * Page Slicers ({len(first_cc.page_slicers)}): {', '.join(slicer_strs)}")

                    print(f"  * Visuals ({len(p.visuals)}):")
                    for v in p.visuals:
                        pos_str = f"Center: ({v.spatial_position.center_x}, {v.spatial_position.center_y}) in {v.spatial_position.zone}" if v.spatial_position else "No position"
                        slicer_tag = " [SLICER]" if v.is_slicer else ""
                        print(f"    - [{v.visual_type}]{slicer_tag} \"{v.title}\" | {pos_str}")
                        cc = v.calculation_context
                        if cc.evaluated_metrics:
                            m_strs = [f"{m.model_key}{f' ({m.aggregation})' if m.aggregation else ''}" for m in cc.evaluated_metrics]
                            print(f"        Evaluated Metrics: {', '.join(m_strs)}")
                        if cc.slicing_coordinates:
                            c_strs = [f"{c.model_key} [{c.role}]" for c in cc.slicing_coordinates]
                            print(f"        Slicing Coordinates: {', '.join(c_strs)}")
                        if cc.visual_active_filters:
                            f_strs = [f"{f.field} ({f.condition})" for f in cc.visual_active_filters]
                            print(f"        Visual Active Filters: {', '.join(f_strs)}")
            print("=" * 70)
            return

    config = _load_cli_config(args, getattr(args, "path", None))

    if getattr(args, "print_config", False):
        print("=== EFFECTIVE CONFIGURATION ===")
        print(config.to_json())
        print("===============================\n")

    if args.command == "docgen":
        # Override specific docgen flags if explicitly provided
        if args.output_dir is not None:
            config.output_dir = args.output_dir
        if args.tables_dir is not None:
            config.tables_subdir = args.tables_dir
        if args.measures_dir is not None:
            config.measures_subdir = args.measures_dir
        if args.functions_dir is not None:
            config.functions_subdir = args.functions_dir
        if getattr(args, "visuals_dir", None) is not None:
            config.visuals_subdir = args.visuals_dir
        if getattr(args, "report_path", None) is not None:
            config.report_path = args.report_path
        if getattr(args, "no_visuals", False):
            config.include_visual_docs = False
        if getattr(args, "no_visual_svg_maps", False):
            config.include_visual_svg_maps = False
        if getattr(args, "project_name", None) is not None:
            config.project_name = args.project_name
        if getattr(args, "report_dataset_name", None) is not None:
            config.report_dataset_name = args.report_dataset_name
        if args.no_frontmatter:
            config.include_table_yaml_frontmatter = False
            config.include_measure_yaml_frontmatter = False
            config.include_function_yaml_frontmatter = False
            config.include_visual_yaml_frontmatter = False
        if args.no_m_code:
            config.include_table_m_code = False

        out_fmt = (config.output_format or "markdown").lower()
        try:
            if out_fmt in ("markdown", "both"):
                md_dir = f"{config.output_dir}/markdown" if out_fmt == "both" else config.output_dir
                md_generator = MarkdownDocGenerator(config)
                generated_docs = md_generator.write_to_directory(args.path, md_dir)
                table_docs = [p for p in generated_docs if p.startswith(config.tables_subdir)]
                measure_docs = [p for p in generated_docs if p.startswith(config.measures_subdir)]
                function_docs = [p for p in generated_docs if p.startswith(config.functions_subdir)]
                visual_docs = [p for p in generated_docs if p.startswith(config.visuals_subdir) and p.endswith(".md")]
                svg_docs = [p for p in generated_docs if p.startswith(config.visuals_subdir) and p.endswith(".svg")]
                index_doc = next((p for p in generated_docs if "/" not in p and "\\" not in p and p.endswith(".md")), "INDEX.md")
                print(f"[SUCCESS] Markdown documentation successfully generated in '{md_dir}'!")
                print(f" -> Index: {md_dir}/{index_doc}")
                print(f" -> Tables: {len(table_docs)} dedicated Markdown files ({md_dir}/{config.tables_subdir}/)")
                print(f" -> Measures: {len(measure_docs)} dedicated Markdown files ({md_dir}/{config.measures_subdir}/)")
                if function_docs:
                    print(f" -> Functions: {len(function_docs)} dedicated Markdown files ({md_dir}/{config.functions_subdir}/)")
                if visual_docs:
                    print(f" -> Visuals: {len(visual_docs)} dedicated Page Markdown files ({md_dir}/{config.visuals_subdir}/)")
                if svg_docs:
                    print(f" -> Visual Maps: {len(svg_docs)} scaled SVG canvas mini-maps ({md_dir}/{config.visuals_subdir}/{config.visual_assets_subdir}/)")
                elif not config.include_visual_docs:
                    print(f" -> Visuals: Disabled (--no-visuals)")
                print(f" -> Format: Pure Markdown + YAML Frontmatter (AI-RAG optimized)")

            if out_fmt in ("html", "both"):
                html_dir = f"{config.output_dir}/html" if out_fmt == "both" else config.output_dir
                html_generator = HtmlDocGenerator(config)
                generated_html = html_generator.write_to_directory(args.path, html_dir)
                table_html = [p for p in generated_html if p.startswith(config.tables_subdir) and p.endswith(".html")]
                measure_html = [p for p in generated_html if p.startswith(config.measures_subdir) and p.endswith(".html")]
                function_html = [p for p in generated_html if p.startswith(config.functions_subdir) and p.endswith(".html")]
                visual_html = [p for p in generated_html if p.startswith(config.visuals_subdir) and p.endswith(".html")]
                svg_html = [p for p in generated_html if p.startswith(config.visuals_subdir) and p.endswith(".svg")]
                print(f"[SUCCESS] Native HTML Wiki Documentation successfully generated in '{html_dir}'!")
                print(f" -> Portal Entry: {html_dir}/index.html")
                print(f" -> Tables: {len(table_html)} dedicated HTML pages ({html_dir}/{config.tables_subdir}/)")
                print(f" -> Measures: {len(measure_html)} dedicated HTML pages ({html_dir}/{config.measures_subdir}/)")
                if function_html:
                    print(f" -> Functions: {len(function_html)} dedicated HTML pages ({html_dir}/{config.functions_subdir}/)")
                if visual_html:
                    print(f" -> Visuals: {len(visual_html)} dedicated Page HTML files ({html_dir}/{config.visuals_subdir}/)")
                if svg_html:
                    print(f" -> Visual Maps: {len(svg_html)} scaled SVG canvas mini-maps ({html_dir}/{config.visuals_subdir}/{config.visual_assets_subdir}/)")
                print(f" -> Assets: CSS stylesheet, Vanilla JS app, and offline search index ({html_dir}/assets/)")
                print(f" -> Format: Native HTML5 + Responsive Enterprise Wiki Portal (Zero dependencies, file:// safe)")

            print(f" -> Auto Date Tables Excluded: {'Yes (default)' if config.exclude_auto_date_tables else 'No (included)'}")
            print(f" -> Inherited Entities Published: {'Yes' if config.include_inherited_entities else 'No (out of scope by default)'}")
            if config.base_doc_url:
                print(f" -> Base Doc URL: {config.base_doc_url}")
            if config.external_docs_base_url:
                print(f" -> External Docs Base URL: {config.external_docs_base_url}")
            if config.external_doc_paths:
                print(f" -> External Models Configured: {len(config.external_doc_paths)} ({', '.join(config.external_doc_paths.keys())})")
        except Exception as e:
            print(f"[ERROR] Failed to generate documentation: {e}", file=sys.stderr)
            sys.exit(1)
        return

    pbip_parser = PBIPParser(config=config)

    try:
        model = pbip_parser.parse(args.path, config=config)
    except Exception as e:
        print(f"[ERROR] Failed to parse PBIP semantic model: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "extract":
        indent = args.indent if args.indent > 0 else None
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(model.to_dict(), f, indent=indent, ensure_ascii=False)

        print(f"[SUCCESS] Semantic model successfully parsed and enriched!")
        print(f" -> Output written to: {output_path.resolve()}")
        print(f" -> Tables: {len(model.tables)} | Measures: {len(model.measures)} | Expressions: {len(model.expressions)} | Functions: {len(model.functions)} | Relationships: {len(model.relationships)}")
        if model.excluded_tables_count > 0:
            print(f" -> Excluded Auto/Template Tables: {model.excluded_tables_count} ({', '.join(model.excluded_tables_list[:5])}{'...' if len(model.excluded_tables_list) > 5 else ''})")
        inherited_count = sum(1 for t in model.tables if t.is_inherited)
        if inherited_count > 0:
            status_str = "in-scope" if config.include_inherited_entities else "out-of-scope"
            print(f" -> Inherited Entities detected: {inherited_count} ({status_str})")
        print(f" -> Root Data Sources detected: {len(model.data_sources_summary)}")
        if model.star_schema:
            print(f" -> Facts: {len(model.star_schema.fact_tables)} | Dims: {len(model.star_schema.dimension_tables)} | Snowflake Lookups: {len(model.star_schema.lookup_outrigger_tables)}")

    elif args.command == "inspect":
        print("=" * 70)
        print(f"PBIP SEMANTIC MODEL: {model.model_name} (Format: {model.source_format})")
        print("=" * 70)

        if model.excluded_tables_count > 0:
            print(f"\n[!] Excluded Auto Tables: {model.excluded_tables_count} (Filter active: {config.exclude_auto_date_tables})")

        print("\n[1] DATA SOURCES & POWER QUERY LINEAGE:")
        for src in model.data_sources_summary:
            print(f"  * [{src.source_type}] {src.connection_string}")
        if model.expressions:
            print(f"  Power Query Expressions & Shared Queries ({len(model.expressions)}):")
            for q in model.expressions:
                tag = f" [Inline Table: {len(q.inline_table_rows)}r x {len(q.inline_table_columns)}c]" if q.is_inline_table else ""
                print(f"    - {q.query_name}{tag} (Upstream: {q.all_upstream_queries} -> Feeds: {q.downstream_tables})")

        print("\n[2] TABLE CLASSIFICATION & TOPOLOGY:")
        for t in model.tables:
            role_badge = f"[{t.role.value}]"
            inherited_badge = " [Inherited Entity]" if t.is_inherited else ""
            calc_tbl_badge = " [DAX Calculated Table]" if t.source_type == "CalculatedTable" else ""
            reasons = "; ".join(t.classification_reasoning.criteria_matched)
            calc_cols = [c.name for c in t.columns if c.is_calculated or c.expression]
            calc_badge = f" (DAX Calc Cols: {len(calc_cols)})" if calc_cols else ""
            print(f"  * {role_badge:<20} {t.name:<25}{inherited_badge}{calc_tbl_badge} (Columns: {len(t.columns)}{calc_badge})")
            if t.source_type == "CalculatedTable" and t.expression:
                first_expr_line = t.expression.strip().split('\n')[0][:70]
                print(f"      DAX Table Expression: {first_expr_line}")
                if t.referenced_tables:
                    print(f"      Referenced Tables: {', '.join(t.referenced_tables)}")
            if reasons:
                print(f"      Reason: {reasons}")
            if t.role.value == "FACT":
                print(f"      Connected Dimensions: {', '.join(t.connected_dimensions) or 'None'}")
                if t.reachable_lookup_tables:
                    print(f"      Snowflake Reachable Lookups: {', '.join(t.reachable_lookup_tables)}")
                    for p in t.snowflake_paths:
                        print(f"        Path: {' -> '.join(p.path)}")

        print("\n[3] DAX MEASURES & DEPENDENCIES:")
        # Sort by calculation depth
        sorted_measures = sorted(model.measures, key=lambda m: (m.calculation_depth, m.name))
        for m in sorted_measures:
            depth_str = f"Depth {m.calculation_depth}"
            ext_badge = " [EXTERNAL]" if m.is_external_measure else ""
            deps_str = f"Calls: {', '.join(m.direct_measure_dependencies)}" if m.direct_measure_dependencies else "Base Measure (columns only)"
            fn_str = f" | UDFs: {', '.join(m.referenced_functions)}" if m.referenced_functions else ""
            down_str = f"Used by: {', '.join(m.downstream_measures)}" if m.downstream_measures else "Not referenced downstream"
            print(f"  * [{depth_str:<8}] [{m.table}] [{m.name}]{ext_badge}{fn_str}")
            print(f"      {deps_str}")
            print(f"      {down_str}")

        if model.functions:
            print("\n[4] USER-DEFINED FUNCTIONS (UDFs):")
            for fn in model.functions:
                down_str = f"Used in {len(fn.downstream_measures)} measure(s): {', '.join(fn.downstream_measures)}" if fn.downstream_measures else "Not currently invoked by any measure"
                print(f"  * [FUNCTION] {fn.name}{fn.parameters_signature} -> {fn.return_type or 'Variant'}")
                print(f"      {down_str}")
                if fn.description:
                    print(f"      Description: {fn.description}")

        print("=" * 70)


if __name__ == "__main__":
    main()
