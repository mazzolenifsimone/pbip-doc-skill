---
name: pbip-doc-skill
description: |
  Analyzes, documents, and queries Microsoft Fabric and Power BI Project (PBIP) semantic models
  (TMDL folder structures and TMSL model.bim files).
  Use this skill when:
    - Discovering or inspecting Power BI semantic models in PBIP or Fabric git repositories.
    - Inspecting model topology (table roles, star schema, snowflake outrigger paths).
    - Analyzing DAX measures, calculation depths, formula lineages, and downstream impact.
    - Tracing Power Query (M) lineage back to root physical data sources.
    - Generating modular, RAG-ready Markdown documentation for tables, measures, and expressions.
    - Filtering or identifying inherited tables and external measures from central semantic models.
license: MIT
metadata:
  version: 1.0.0
  author: pbip-doc-skill
---

# pbip-doc-skill - Agent Skill Guide

## TL;DR

The **pbip-doc-skill** is a zero-external-dependency tool (pure Python standard library) designed to parse, analyze, and document Microsoft Fabric and Power BI semantic models (`.pbip`, TMDL `definition/` folders, and TMSL `model.bim` files).

It resolves:
1. **Power Query (M) lineage** from raw sources through staging queries to final tables.
2. **Star Schema topology** and recursive **Snowflake outrigger paths**.
3. **DAX Measure Dependency DAG**, calculating calculation depth (Depth 0, 1, 2...), upstream dependencies, and downstream impact.
4. **Inherited entity scoping** (`partition = entity` and `EXTERNALMEASURE`).

It operates either as a **native Model Context Protocol (MCP) server** over JSON-RPC 2.0 stdio, or as a **CLI tool** executable via terminal.

---

## Operational Modes

### Mode A: Native MCP Tools (Recommended)

When connected to the `pbip-doc-skill` MCP server, use the following tools directly. **All tools accept `config_overrides: dict`** (allowing you to customize any of the 30+ settings on the fly without writing files) and `config_path: str`:

| Tool | Purpose | Primary Arguments |
| :--- | :--- | :--- |
| `get_configuration` | Inspects all 30+ settings, default values, and resolved config | `config_path?`, `config_overrides?` |
| `inspect_semantic_model` | Quick topology overview, table roles, and top measures | `path`, `config_overrides?` |
| `extract_semantic_model_json` | Complete enriched JSON metadata extraction | `path`, `output_path?`, `config_overrides?` |
| `generate_markdown_docs` | Builds modular, RAG-ready Markdown files | `path`, `output_dir?`, `config_overrides?` |
| `query_measure_impact` | Deep DAX formula, depth, upstream & downstream analysis | `path`, `measure_name`, `config_overrides?` |
| `query_table_topology` | Role reasoning, snowflake outriggers, and root sources | `path`, `table_name`, `config_overrides?` |

### Mode B: Terminal CLI Fallback

If running in a standard shell without MCP tool bindings, execute the CLI entry points. You can pass arbitrary configuration overrides via `--config-json` or `--set key=value`:

```bash
# 1. Quick model inspection (with inline config override)
python -m pbip_doc.cli inspect path/to/definition --set include_inherited_entities=true

# 2. Extract complete metadata JSON (with inline JSON config)
python generate_json.py path/to/definition -o semantic_model_docs.json --config-json '{"exclude_auto_date_tables": false}'

# 3. Generate modular Markdown documentation
python generate_docs.py path/to/definition -o docs/ --set include_table_m_code=false

# 4. Initialize a complete configuration template file
python generate_docs.py config --init pbip_doc.config.json

# 5. Display active effective configuration
python generate_docs.py config --show --set output_dir=custom_docs

# 6. Launch MCP stdio server
python mcp_server.py
```

---

## Agent Decision Playbook

Follow this workflow when answering questions, analyzing models, or generating documentation:

### Step 1: Discover & Locate Semantic Models

Locate the PBIP semantic model path in the workspace:
- Look for a directory ending in `.Dataset`, `.SemanticModel`, or containing a `definition/` folder.
- If TMDL format: path contains `definition/model.tmdl` and `definition/tables/*.tmdl`.
- If TMSL / BIM format: path points to `model.bim` or contains `model.bim`.

### Step 2: Fast Model Triage (Inspection)

Before reading hundreds of TMDL files or dumping entire JSON files into context:
- Call `inspect_semantic_model(path=...)` or run `python -m pbip_doc.cli inspect --input ...`.
- Review the total table count, measure count, identified data sources, and table role classifications.
- Determine if the model contains inherited entities (`partition = entity`).

### Step 3: Targeted Lineage & Impact Queries

When asked about a specific calculation, table, or refactoring:
- **For Measure Impact Analysis**: Call `query_measure_impact(path=..., measure_name="...")`.
  - Check `calculation_depth`:
    - `0`: Base measure (depends only on table columns).
    - `1+`: Higher-level KPI (depends on other measures).
  - Check `downstream_measures`: lists all KPIs that will be broken or affected if this measure is modified.
  - Check `is_external_measure`: indicates whether the measure is defined externally via `EXTERNALMEASURE`.
- **For Table Topology**: Call `query_table_topology(path=..., table_name="...")`.
  - Check `role`: `Fact`, `Dimension`, `Snowflake Dimension`, `Bridge`, or `Disconnected`.
  - Check `snowflake_paths`: reveals normalization chains (e.g., `FactSales -> DimCustomer -> DimGeography -> DimCountry`).
  - Check `root_data_sources`: provides physical data store endpoints.

### Step 4: Documentation Generation & RAG Ingestion

When the user asks to document the semantic model or prepare files for search/RAG:
- Call `generate_markdown_docs(path=..., output_dir="docs")` or run `python generate_docs.py`.
- The engine produces:
  - `docs/INDEX.md`: Global model index and table/measure inventories.
  - `docs/tables/<TableName>.md`: Star schema role, join paths, column schemas, and measures.
  - `docs/measures/<MeasureName>.md`: DAX code, upstream/downstream DAG, referenced columns.
  - `docs/functions/<FunctionName>.md`: User-defined DAX functions (if present).
  - `docs/expressions/<ExpressionName>.md`: Shared Power Query M queries and parameters.
- Every generated document includes structured YAML frontmatter, making it ready for vector chunking or LLM search.

---

## Domain Logic & Semantic Rules

### Table Role Classification Hierarchy

The engine classifies each table using the following prioritized criteria:

1. **Date / Calendar Table (`Date`)**: Marked as date table in metadata, contains date columns, or matches standard date naming patterns.
2. **Fact Table (`Fact`)**: Positioned on the "many" (`*`) side of active relationships with dimensions; frequently contains numeric measures and foreign keys.
3. **Lookup / Outrigger Table (`Snowflake Dimension`)**: Dimension table positioned on the "one" (`1`) side of another dimension table (normalized snowflake schema).
4. **Dimension Table (`Dimension`)**: Positioned on the "one" (`1`) side of relationships to fact tables.
5. **Bridge Table (`Bridge`)**: Connects two dimensions or resolves many-to-many relationships without hosting core business facts.
6. **Disconnected Table (`Disconnected`)**: No relationships to any other table (often used for what-if parameters or report slicers).

### Inherited Entities & Thin Reports (`is_inherited`)

In Power BI architectures using a centralized golden dataset and thin reports connected via DirectQuery or Live Connection:
- Tables with `partition = entity` derive from an external source model.
- Measures defined with `EXTERNALMEASURE` are bound to remote semantic models.
- **Handling**:
  - By default, inherited tables and external measures are flagged with `"is_inherited": true` and `"out_of_scope": true`.
  - They remain present in global JSON indexes, relationship graphs, and DAG dependencies so the model graph remains intact.
  - They are excluded from generating standalone markdown documentation files unless `include_inherited_entities: true` is configured.

### DAX Measure DAG and Calculation Depth

The dependency graph between DAX measures is evaluated using topological sorting:
- **Depth 0**: Measure contains no references to other measures (references only columns like `'Fact'[Amount]`).
- **Depth N**: Measure references at least one measure with depth `N - 1`.
- **Cyclic Reference Protection**: In case of invalid or recursive DAX references, cycles are detected and isolated to prevent infinite loops.

---

## Frequently Asked Questions (FAQ)

### Q: Can this engine run without installing external pip packages?
**Yes.** The engine uses only the Python standard library (`json`, `re`, `pathlib`, `dataclasses`, `sys`, `typing`, `argparse`). No pip installs are required.

### Q: Does it support TMDL and BIM formats simultaneously?
**Yes.** The parser automatically detects whether the target path is a TMDL folder (with `definition/model.tmdl` or `.tmdl` files) or a TMSL JSON file (`model.bim`).

### Q: How should I handle very large models with hundreds of tables?
Start by calling `inspect_semantic_model` or querying specific measures using `query_measure_impact`. Avoid loading the complete metadata JSON directly into your chat context window if you only need details for specific tables or measures.

### Q: How do I configure custom filters or include inherited entities?
Pass `include_inherited_entities=True` or `include_auto_tables=True` in MCP tool calls, or edit the local `pbip_doc.config.json` configuration file.
