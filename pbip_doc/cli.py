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
from .docgen import DocGenConfig, MarkdownDocGenerator


def _load_cli_config(args, base_path: Optional[str] = None) -> DocGenConfig:
    """Helper to resolve DocGenConfig from --config, --config-json, --set, local pbip_doc.config.json or defaults."""
    config_file = getattr(args, "config", None)
    if config_file and os.path.exists(config_file):
        config = DocGenConfig.load_from_file(config_file)
    else:
        if base_path:
            target_dir = base_path if os.path.isdir(base_path) else os.path.dirname(base_path)
            config = DocGenConfig.find_and_load_default(target_dir)
        else:
            config = DocGenConfig.find_and_load_default()

    # 1. Inline JSON override via --config-json
    config_json_raw = getattr(args, "config_json", None)
    if config_json_raw:
        try:
            overrides = json.loads(config_json_raw)
            if isinstance(overrides, dict):
                config.apply_overrides(overrides)
            else:
                print(f"[WARNING] --config-json must be a JSON object, got {type(overrides).__name__}.", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Invalid JSON passed to --config-json: {e}", file=sys.stderr)
            sys.exit(1)

    # 2. Key=Value overrides via --set (supports multiple occurrences)
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

    return config


def _add_config_arguments(p: argparse.ArgumentParser):
    """Adds common configuration flags (--config, --config-json, --set, --print-config) to a parser."""
    p.add_argument(
        "-c", "--config",
        help="Path to custom JSON configuration file (e.g. pbip_doc.config.json)",
    )
    p.add_argument(
        "--config-json",
        help="Inline JSON string with configuration overrides (e.g. '{\"include_table_m_code\": false}')",
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
        help="Print the effective configuration JSON to stdout (incorporating --config, --config-json, and --set)",
    )
    config_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite target file if it already exists when using --init",
    )

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
        if args.no_frontmatter:
            config.include_table_yaml_frontmatter = False
            config.include_measure_yaml_frontmatter = False
            config.include_function_yaml_frontmatter = False
        if args.no_m_code:
            config.include_table_m_code = False

        generator = MarkdownDocGenerator(config)
        try:
            generated_docs = generator.write_to_directory(args.path, config.output_dir)
            table_docs = [p for p in generated_docs if p.startswith(config.tables_subdir)]
            measure_docs = [p for p in generated_docs if p.startswith(config.measures_subdir)]
            function_docs = [p for p in generated_docs if p.startswith(config.functions_subdir)]
            print(f"[SUCCESS] Documentation successfully generated in '{config.output_dir}'!")
            print(f" -> Index: {config.output_dir}/INDEX.md")
            print(f" -> Tables: {len(table_docs)} dedicated Markdown files ({config.output_dir}/{config.tables_subdir}/)")
            print(f" -> Measures: {len(measure_docs)} dedicated Markdown files ({config.output_dir}/{config.measures_subdir}/)")
            if function_docs:
                print(f" -> Functions: {len(function_docs)} dedicated Markdown files ({config.output_dir}/{config.functions_subdir}/)")
            print(f" -> Auto Date Tables Excluded: {'Yes (default)' if config.exclude_auto_date_tables else 'No (included)'}")
            print(f" -> Inherited Entities Published: {'Yes' if config.include_inherited_entities else 'No (out of scope by default)'}")
            print(f" -> Format: Pure Markdown + YAML Frontmatter (AI-RAG optimized)")
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
