"""
Pure Python Model Context Protocol (MCP) Stdio Server for pbip-doc-skill.
Zero external dependencies - runs on Python 3.8+ standard library.
Implements the JSON-RPC 2.0 stdio transport protocol.
"""

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional

from .parser import PBIPParser
from .docgen import DocGenConfig, MarkdownDocGenerator


SERVER_INFO = {
    "name": "pbip-doc-skill",
    "version": "1.0.0",
}

CONFIG_PROPERTIES = {
    "config_path": {
        "type": "string",
        "description": "Optional path to a custom pbip_doc.config.json file.",
    },
    "config_overrides": {
        "type": "object",
        "description": "Optional dictionary of arbitrary DocGenConfig overrides (e.g. {'include_table_m_code': false, 'include_expression_docs': false, 'output_dir': 'custom_docs'}). Allows setting ANY configuration setting without modifying files on disk.",
    },
}

TOOLS = [
    {
        "name": "get_configuration",
        "description": "Retrieves the full list of configuration settings, their descriptions, default values, and the currently active/resolved configuration (incorporating any config_path or config_overrides).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **CONFIG_PROPERTIES,
            },
        },
    },
    {
        "name": "inspect_semantic_model",
        "description": "Inspects a Power BI PBIP semantic model (TMDL or BIM) and returns a summary of data sources, table roles, and DAX measures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the PBIP folder, definition/ folder, or model.bim file.",
                },
                "include_auto_tables": {
                    "type": "boolean",
                    "description": "Whether to include Power BI auto-generated date tables (default: false).",
                    "default": False,
                },
                "include_inherited_entities": {
                    "type": "boolean",
                    "description": "Whether to include inherited entity tables (partition = entity) and external measures as in-scope (default: false).",
                    "default": False,
                },
                **CONFIG_PROPERTIES,
            },
            "required": ["path"],
        },
    },
    {
        "name": "extract_semantic_model_json",
        "description": "Parses a PBIP semantic model and extracts the complete enriched metadata JSON, resolving Power Query M lineage, star schema topology, and DAX dependency DAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the PBIP folder, definition/ folder, or model.bim file.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional file path to save the JSON. If omitted, the JSON is returned directly in the response.",
                },
                "include_auto_tables": {
                    "type": "boolean",
                    "description": "Whether to include auto date tables (default: false).",
                    "default": False,
                },
                "include_inherited_entities": {
                    "type": "boolean",
                    "description": "Whether to mark inherited tables and external measures as in-scope (default: false).",
                    "default": False,
                },
                **CONFIG_PROPERTIES,
            },
            "required": ["path"],
        },
    },
    {
        "name": "generate_markdown_docs",
        "description": "Generates complete modular, RAG-ready Markdown documentation for every table, measure, function, and expression from a PBIP model or extracted JSON file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the PBIP model folder, model.bim, or previously extracted metadata JSON file.",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Target directory to write the Markdown files (default: docs, or output_dir configured in config_overrides).",
                },
                "include_auto_tables": {
                    "type": "boolean",
                    "description": "Whether to include auto date tables in documentation (default: false).",
                    "default": False,
                },
                "include_inherited_entities": {
                    "type": "boolean",
                    "description": "Whether to generate standalone files for inherited entities and external measures (default: false).",
                    "default": False,
                },
                **CONFIG_PROPERTIES,
            },
            "required": ["path"],
        },
    },
    {
        "name": "query_measure_impact",
        "description": "Performs impact analysis for a specific DAX measure: returns its formula, upstream dependencies, calculation depth, and all downstream measures that depend on it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the PBIP model or extracted JSON file.",
                },
                "measure_name": {
                    "type": "string",
                    "description": "Exact name of the DAX measure to analyze (e.g. 'Total Sales' or 'Margin %').",
                },
                **CONFIG_PROPERTIES,
            },
            "required": ["path", "measure_name"],
        },
    },
    {
        "name": "query_table_topology",
        "description": "Inspects the role, classification reasoning, root data sources, connected dimensions/facts, and snowflake outrigger paths for a specific table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the PBIP model or extracted JSON file.",
                },
                "table_name": {
                    "type": "string",
                    "description": "Exact name of the table to inspect (e.g. 'FactInternetSales').",
                },
                **CONFIG_PROPERTIES,
            },
            "required": ["path", "table_name"],
        },
    },
]


class PBIPMCPServer:
    """JSON-RPC 2.0 stdio server implementing the Model Context Protocol."""

    def __init__(self):
        pass

    def run(self):
        """Main stdio loop reading line-by-line JSON-RPC messages."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                self.handle_message(request)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                self.send_error(None, -32603, f"Internal JSON-RPC error: {str(e)}")

    def handle_message(self, req: Dict[str, Any]):
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Handle notifications (no id)
        if msg_id is None:
            if method == "notifications/initialized":
                return
            return

        # Methods
        if method == "initialize":
            self.send_result(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": SERVER_INFO,
            })
        elif method == "ping":
            self.send_result(msg_id, {})
        elif method == "tools/list":
            self.send_result(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            self.execute_tool(msg_id, tool_name, tool_args)
        else:
            self.send_error(msg_id, -32601, f"Method not found: {method}")

    def execute_tool(self, msg_id: Any, name: str, args: Dict[str, Any]):
        try:
            if name == "get_configuration":
                res = self._get_config_details(args)
            elif name == "inspect_semantic_model":
                res = self._inspect_model(args)
            elif name == "extract_semantic_model_json":
                res = self._extract_json(args)
            elif name == "generate_markdown_docs":
                res = self._generate_docs(args)
            elif name == "query_measure_impact":
                res = self._query_measure(args)
            elif name == "query_table_topology":
                res = self._query_table(args)
            else:
                self.send_error(msg_id, -32601, f"Unknown tool: {name}")
                return

            self.send_result(msg_id, {
                "content": [
                    {
                        "type": "text",
                        "text": res if isinstance(res, str) else json.dumps(res, indent=2),
                    }
                ]
            })
        except Exception as e:
            err_msg = f"Tool execution failed: {str(e)}\n{traceback.format_exc()}"
            self.send_result(msg_id, {
                "isError": True,
                "content": [{"type": "text", "text": err_msg}],
            })

    def _get_config(self, args: Dict[str, Any], base_path: Optional[str] = None) -> DocGenConfig:
        config_path = args.get("config_path")
        if config_path and os.path.exists(config_path):
            config = DocGenConfig.load_from_file(config_path)
        elif base_path:
            config = DocGenConfig.find_and_load_default(base_path)
        else:
            config = DocGenConfig.find_and_load_default()

        # Apply arbitrary overrides dictionary if supplied
        overrides = args.get("config_overrides")
        if isinstance(overrides, dict):
            config.apply_overrides(overrides)

        # Legacy / convenience booleans
        if args.get("include_auto_tables"):
            config.exclude_auto_date_tables = False
        if args.get("include_inherited_entities"):
            config.include_inherited_entities = True
        return config

    def _get_config_details(self, args: Dict[str, Any]) -> Dict[str, Any]:
        config = self._get_config(args, None)
        descriptions = DocGenConfig.get_descriptions()
        template = DocGenConfig.get_template_dict()
        return {
            "active_configuration": config.to_dict(),
            "total_settings": len(descriptions),
            "available_settings": {
                k: {
                    "default": template.get(k),
                    "description": desc,
                }
                for k, desc in descriptions.items()
            },
        }

    def _inspect_model(self, args: Dict[str, Any]) -> str:
        path = args["path"]
        config = self._get_config(args, path)
        parser = PBIPParser(config=config)
        model = parser.parse(path, config=config)

        lines = [
            f"=== PBIP SEMANTIC MODEL: {model.model_name} (Format: {model.source_format}) ===",
            f"Culture: {model.culture} | Compatibility: {model.compatibility_level}",
            f"Tables: {len(model.tables)} | Measures: {len(model.measures)} | Expressions: {len(model.expressions)}",
            "",
            "[DATA SOURCES]",
        ]
        for src in model.data_sources_summary:
            lines.append(f"  * [{src.source_type}] {src.connection_string}")

        lines.append("\n[TABLES & TOPOLOGY]")
        for t in model.tables:
            calc_badge = f" (Calc Cols: {sum(1 for c in t.columns if c.is_calculated)})" if any(c.is_calculated for c in t.columns) else ""
            inherited_badge = " [Inherited Entity]" if t.is_inherited else ""
            lines.append(f"  * [{t.role.value:<16}] {t.name:<25}{inherited_badge} (Columns: {len(t.columns)}{calc_badge})")

        lines.append("\n[KEY MEASURES (Depth sorted)]")
        for m in sorted(model.measures, key=lambda x: (x.calculation_depth, x.name))[:15]:
            ext_badge = " [EXTERNAL]" if m.is_external_measure else ""
            lines.append(f"  * [Depth {m.calculation_depth}] [{m.table}] [{m.name}]{ext_badge}")

        if len(model.measures) > 15:
            lines.append(f"  ... and {len(model.measures) - 15} more measures.")

        return "\n".join(lines)

    def _extract_json(self, args: Dict[str, Any]) -> Any:
        path = args["path"]
        config = self._get_config(args, path)
        parser = PBIPParser(config=config)
        model = parser.parse(path, config=config)
        data = model.to_dict()

        out_path = args.get("output_path")
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return f"Successfully extracted model JSON to: {p.resolve()}"
        return data

    def _generate_docs(self, args: Dict[str, Any]) -> str:
        path = args["path"]
        config = self._get_config(args, path)
        out_dir = args.get("output_dir") or config.output_dir
        config.output_dir = out_dir

        generator = MarkdownDocGenerator(config=config)
        generated = generator.write_to_directory(path, out_dir)
        return (
            f"Successfully generated {len(generated)} Markdown documentation files in '{out_dir}/'.\n"
            f"Master index available at: {out_dir}/INDEX.md"
        )

    def _query_measure(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        meas_name = args["measure_name"].strip()
        config = self._get_config(args, path)
        parser = PBIPParser(config=config)
        model = parser.parse(path, config=config)

        target = next((m for m in model.measures if m.name.lower() == meas_name.lower()), None)
        if not target:
            return {"error": f"Measure '{meas_name}' not found in semantic model."}

        return {
            "name": target.name,
            "table": target.table,
            "dax_expression": target.dax_expression,
            "calculation_depth": target.calculation_depth,
            "direct_dependencies": target.direct_measure_dependencies,
            "all_upstream_measures": target.all_upstream_measures,
            "downstream_measures": target.downstream_measures,
            "referenced_columns": target.referenced_columns,
            "is_inherited": target.is_inherited,
            "is_external_measure": target.is_external_measure,
        }

    def _query_table(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        tbl_name = args["table_name"].strip()
        config = self._get_config(args, path)
        parser = PBIPParser(config=config)
        model = parser.parse(path, config=config)

        target = next((t for t in model.tables if t.name.lower() == tbl_name.lower()), None)
        if not target:
            return {"error": f"Table '{tbl_name}' not found in semantic model."}

        return {
            "name": target.name,
            "role": target.role.value,
            "classification_reasoning": {
                "confidence_score": target.classification_reasoning.confidence_score,
                "criteria_matched": target.classification_reasoning.criteria_matched,
            },
            "source_type": target.source_type,
            "is_inherited": target.is_inherited,
            "column_count": len(target.columns),
            "calculated_columns": [c.name for c in target.columns if c.is_calculated],
            "connected_dimensions": target.connected_dimensions,
            "connected_facts": target.connected_facts,
            "reachable_lookup_tables": target.reachable_lookup_tables,
            "snowflake_paths": [
                {"lookup": sp.lookup_table, "path": sp.path, "hops": sp.hops}
                for sp in target.snowflake_paths
            ],
            "root_data_sources": [
                {"type": s.source_type, "connection": s.connection_string}
                for s in target.root_data_sources
            ],
        }

    def send_result(self, msg_id: Any, result: Any):
        self._write_msg({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def send_error(self, msg_id: Any, code: int, message: str):
        self._write_msg({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        })

    def _write_msg(self, data: Dict[str, Any]):
        out = json.dumps(data)
        sys.stdout.write(out + "\n")
        sys.stdout.flush()


def main():
    server = PBIPMCPServer()
    server.run()


if __name__ == "__main__":
    main()
