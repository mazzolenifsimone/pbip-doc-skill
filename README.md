# pbip-doc-skill

> **Documentation and semantic dependency resolution engine for Microsoft Fabric and Power BI Project (`.pbip`) semantic models.**

Hi, a human's writing here.
Would you like a simple tool that document a whole semantic model of a TMDL based (.pbip) or TMSL based (.bim) Power BI project? Me too, a lot. Then I vibed (of course I vibed it) something I find pretty useful.

This tool runs on a very *simple* python code without any dependencies. This tool has a double soul: first to provide a structured way to retrieve foundamental information from a pbip file in a json format that can be used as RAG knowledge base (very practical for our cy-friends), second to document them in a modular-structured markdown format that can be personalized with a practial json configuration file for human-ready documentation.

This tool is structured as an agentic skill with SKILL.md file and MCP Server and A LOT of documentation structured in a practical way for your little cy-workers (YAML frontmatter, TL;DR chapters, FAQ's).

Hope it helps. And now I'll leave you (or your cy-bros) to read all the following AI slop (still very usefull though - for me atleast).

---

## 🎯 Architecture Overview

The documentation workflow is designed in **two independent, modular phases**:

```text
┌─────────────────────────────────┐
│       PBIP Source Files         │
│ (.tmdl definition / model.bim)  │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   PHASE 1: Dependency Engine    │ ◄─── Core analysis
│   (Pure Python, zero-deps)      │
└────────────────┬────────────────┘
                 │ Generates standardized JSON
                 ▼
┌─────────────────────────────────┐
│  semantic_model_docs.json       │ ◄─── Single Source of Truth
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   PHASE 2: Document Generator   │
│   (Markdown / RAG-ready docs)   │
└─────────────────────────────────┘
```

1. **Phase 1 (Core Engine)**: Parses semantic model files, resolves data dependencies, and generates a standardized, enriched **JSON file**:
   - Resolves **Power Query (M)** lineage back to root physical sources (SQL Server, OData, SharePoint, Web, Excel, Lakehouse, PostgreSQL).
   - Classifies tables into roles (**Fact**, **Dimension**, **Lookup / Outrigger**) and maps all recursive **Snowflake** paths.
   - Computes the **DAX Measure Dependency DAG** (calculation depth, upstream dependencies, downstream impact, and referenced columns).
2. **Phase 2 (Document Generator)**: Consumes the extracted JSON to build clean, modular Markdown documentation pages for every table, measure, function, and ETL expression.

---

## 🛠️ Project Highlights

- **Pure Python**: 100% standard library (`re`, `json`, `pathlib`, `dataclasses`, `enum`, `typing`, `argparse`, `unittest`). Zero external dependencies required.
- **Dual Format Support**:
  - **TMDL** (Tabular Model Definition Language): parses `definition/tables/*.tmdl`, `expressions.tmdl`, `relationships.tmdl`, `model.tmdl`.
  - **TMSL / BIM**: parses `model.bim` JSON files directly.
- **Complete Dependency Resolution**:
  - ✅ **Power Query Lineage**: multi-hop tracing from raw data source -> staging queries -> merge/append -> final model table.
  - ✅ **Star Schema & Snowflake Topology**: automatically classifies tables and maps outrigger lookup paths (e.g., `FactSales` -> `DimCustomer` -> `DimGeography` -> `DimCountry`).
  - ✅ **DAX Measure DAG**: directed acyclic graph, calculation depth (Depth 0, 1, 2...), upstream dependencies, and downstream impact analysis.

---

## 📂 Repository Structure

```text
├── pbip_doc/                      # Main Python package
│   ├── __init__.py                # Package exports
│   ├── model_schema.py            # Dataclasses and JSON schema
│   ├── parser.py                  # TMDL and BIM parser
│   ├── m_lineage.py               # Power Query (M) lineage resolver
│   ├── star_schema.py             # Star schema classifier and Snowflake resolver
│   ├── measure_analyzer.py        # DAX tokenizer and measure DAG analyzer
│   ├── m_table_parser.py          # Power Query #table inline data parser
│   ├── docgen/                    # Modular Markdown document generator
│   │   ├── __init__.py
│   │   ├── config.py              # Configuration options and filters
│   │   ├── utils.py               # YAML frontmatter utilities
│   │   ├── table_doc.py           # Table Markdown builder
│   │   ├── measure_doc.py         # Measure Markdown builder
│   │   ├── function_doc.py        # DAX UDF function Markdown builder
│   │   ├── expression_doc.py     # Shared query / expression Markdown builder
│   │   ├── index_doc.py           # Master index (INDEX.md) builder
│   │   └── engine.py              # Documentation orchestrator
│   └── cli.py                     # Command-line interface (CLI)
├── samples/                       # Sample PBIP models for testing
│   ├── adventureworks_pbip/       # TMDL model (Fact, Dim, Outriggers, M Staging, DAX)
│   └── retail_sales_bim/          # TMSL model.bim file
├── tests/                         # Unit tests (standard unittest)
│   ├── __init__.py
│   └── test_pbip_doc.py
├── documentation/                 # Technical documentation and specs
│   ├── json_schema/               # Phase 1: JSON field specifications and extraction logic
│   └── markdown_generator/        # Phase 2: Markdown generation specifications and RAG patterns
├── generate_json.py               # CLI entry point for JSON extraction (Phase 1)
├── generate_docs.py               # CLI entry point for Markdown doc generation (Phase 2)
├── mcp_server.py                  # MCP server entry point (JSON-RPC 2.0 stdio)
├── SKILL.md                       # AI Agent Skill manifest and operational guide
└── README.md
```

---

## 💻 CLI Usage

The tool runs with **Python 3.8+** using standard CLI commands. No extra packages or tools are required.

### Requirements
- **Python 3.8 or higher**
- No third-party packages needed.

### Quick Commands

```bash
# 1. Generate Modular Markdown Documentation (Tables, Measures, Expressions, INDEX.md)
python generate_docs.py ./samples/adventureworks_pbip -o ./docs

# 2. Extract Complete Enriched JSON
python generate_json.py extract ./samples/adventureworks_pbip -o semantic_model_docs.json

# 3. Quick Console Inspection Summary
python generate_json.py inspect ./samples/adventureworks_pbip

# 4. Run the Test Suite
python -m unittest discover tests

# 5. Run Native MCP Server
python mcp_server.py
```

---

## 🤖 AI Agent Integration & MCP Server

This repository qualifies as a standalone **AI Agent Skill** and exposes a native **Model Context Protocol (MCP)** server with zero third-party dependencies.

### 1. Agent Skill Manifest (`SKILL.md`)
The [`SKILL.md`](SKILL.md) file provides autonomous AI coding assistants with:
- Intent triggers for PBIP / Fabric semantic model analysis.
- Operational decision playbooks (discovery, triage, deep lineage queries, RAG doc generation).
- Domain rules for star schema classification, snowflake outrigger paths, and DAX calculation depth.

### 2. Model Context Protocol Server (`mcp_server.py`)
Run the native JSON-RPC 2.0 stdio MCP server:
```bash
python mcp_server.py
```

#### MCP Client Configuration
Add the server to your MCP client configuration (e.g., Claude Desktop, Cursor, Antigravity):
```json
{
  "mcpServers": {
    "pbip-doc-skill": {
      "command": "python",
      "args": ["/absolute/path/to/pbip-doc-skill/mcp_server.py"]
    }
  }
}
```

#### Exposed MCP Tools
1. `get_configuration`: Returns the schema, default values, and active configuration (incorporating any `config_path` or `config_overrides`).
2. `inspect_semantic_model`: Fast topology overview (source types, table counts, roles, measures).
3. `extract_semantic_model_json`: Extracts the complete enriched metadata JSON.
4. `generate_markdown_docs`: Builds modular, RAG-ready Markdown documentation.
5. `query_measure_impact`: Analyzes DAX formula, calculation depth, and downstream KPIs impacted by changes.
6. `query_table_topology`: Analyzes table role classification, outrigger snowflake paths, and root physical data sources.

> [!TIP]
> **MCP Parametrization**: Every tool accepts an optional `config_overrides` dictionary (e.g. `{"include_table_m_code": false, "include_expression_docs": false}`), allowing agents to tune any of the 30+ settings without writing files to disk.

---

## ⚙️ Configuration & CLI Customization

You can customize all analysis and documentation settings via config file, inline JSON, individual `--set` keys, or CLI flags.

### 1. Initializing and Inspecting Configuration via CLI

```bash
# Generate a complete template configuration file with all 30+ settings and defaults
python generate_docs.py config --init pbip_doc.config.json

# Display the effective active configuration (resolving defaults, file, and CLI overrides)
python generate_docs.py config --show --set output_dir=my_docs --set include_table_m_code=false
```

### 2. Passing Configurations from the Command Line

You have three flexible methods to configure runs:

- **Config File (`-c, --config`)**:
  ```bash
  python generate_docs.py path/to/model -c pbip_doc.config.json
  ```
- **Inline JSON (`--config-json`)**:
  ```bash
  python generate_docs.py path/to/model --config-json '{"include_table_m_code": false, "exclude_auto_date_tables": false}'
  ```
- **Key-Value Overrides (`--set KEY=VALUE`)**:
  ```bash
  python generate_docs.py path/to/model --set include_table_m_code=false --set output_dir=custom_docs
  ```
- **Debug Inspection (`--print-config`)**: prints the resolved configuration before running.

### 3. Example `pbip_doc.config.json`
```json
{
  "exclude_auto_date_tables": true,
  "excluded_table_patterns": [
    "^LocalDateTable_.*",
    "^DateTableTemplate_.*",
    "^LocalDateTable\\b.*"
  ],
  "excluded_tables": [],
  "include_inherited_entities": false,
  "include_table_yaml_frontmatter": true,
  "include_table_topology_section": true,
  "include_table_lineage_section": true,
  "include_table_columns_dictionary": true,
  "include_table_relationships_section": true,
  "include_table_snowflake_paths": true,
  "include_table_measures_list": true,
  "include_table_m_code": true,
  "output_dir": "docs",
  "tables_subdir": "tables",
  "measures_subdir": "measures",
  "expressions_subdir": "expressions",
  "functions_subdir": "functions"
}
```

#### Dedicated CLI Flag Shortcuts
- `--exclude-tables Table1,Table2`: exclude specific tables directly.
- `--include-auto-tables`: include auto-generated date tables.
- `--include-inherited-entities`: include and publish standalone documentation files for inherited tables (`partition = entity`) and external measures (`EXTERNALMEASURE`).
- `--no-frontmatter`: omit YAML frontmatter at top of markdown files.
- `--no-m-code`: omit raw M code snippets from table documents.

---

## 🧮 DAX Calculated Columns & Table Formatting

The engine identifies and extracts DAX calculated columns from both **TMDL** (`column Name = <DAX>`) and **TMSL / BIM** (`"type": "calculated"`):
1. **Markdown Safety**: pipe characters (`|` and `||`) and line breaks in DAX expressions or descriptions are sanitized to prevent breaking Markdown tables.
2. **Distinct Badge**: calculated columns are marked with a `🧮 Calculated` badge in the column dictionary.
3. **Dedicated Formulas Section**: a separate section lists full multiline DAX formulas in highlighted code blocks (` ```dax `).

---

## 🔄 Incremental Refresh & Hybrid Tables

The engine reads **Incremental Refresh** policies from both **TMDL** (`refreshPolicy` blocks or inline JSON) and **TMSL / BIM** (`table.refreshPolicy`):
- **Extracted Metadata**:
  - `is_enabled`: whether incremental refresh is active.
  - `policy_type`: policy type (e.g. `basic`).
  - `mode`: storage mode (`import` standard or `hybrid` with realtime DirectQuery).
  - `rolling_window_periods` & `rolling_window_granularity`: historical storage window (e.g. `3 years`).
  - `incremental_periods` & `incremental_granularity`: refresh window (e.g. `7 days`).
  - `polling_expression`: M expression for *Detect Data Changes*.
  - `source_expression`: partitioned M expression with `RangeStart` and `RangeEnd`.
  - `raw_policy`: full raw policy metadata.
- **Dedicated Markdown Section**: tables with an active policy include parameter tables, mode badges (`🔄 Incremental` or `⚡ Hybrid`), and Power Query code snippets. Tables without a policy display a clear notice indicating full refresh.

---

## ⚡ Power Query ETL & Inline Tables (`#table`)

The engine generates documentation for shared queries and expressions in `docs/expressions/`:
- **Classified Expression Types**:
  - `📊 INLINE_TABLE`: static in-memory tables built using the literal `#table(...)` function.
  - `🔄 STAGING_QUERY`: intermediate queries transforming data to feed final model tables.
  - `⚙️ PARAMETER`: configuration and connection parameters (e.g. `ServerName`, `Environment`).
  - `λ CUSTOM_FUNCTION`: reusable custom Power Query M functions.
- **Parsing and Markdown Rendering for `#table`**:
  - Automatically extracts column names, typed schemas (`type table [...]`), and row data.
  - Converts data into formatted GitHub Flavored Markdown tables with pipe escaping.
  - Rendered inline tables appear in both expression documents and the lineage section of consuming model tables.

---

## 📦 Composite Models, Thin Reports & Inherited Entities (`partition = entity` / `EXTERNALMEASURE`)

In architectures using a central **Golden Dataset** with multiple thin reports (or DirectQuery composite models), reports inherit most tables and measures from the central semantic model:
- **Automatic Inheritance Detection**:
  - **Inherited Tables**: identified by `partition ... = entity` in TMDL or TMSL, tracking the source entity (`entityName`) and origin (`expressionSource`).
  - **External Measures**: identified by the DAX function `EXTERNALMEASURE(...)`.
  - **Local Measures and Tables**: report-specific calculations and local tables are recognized as native.
- **Out-of-Scope Filtering**:
  - **Default Behavior (`include_inherited_entities: false`)**: avoids duplicating central model documentation across thin reports. Standalone `.md` files are skipped for inherited entities, while local report measures and tables are documented normally.
  - **Link Integrity**: inherited tables and measures are still listed in `INDEX.md`, dependency trees, and relationship sections using clear indicators (e.g. `[Customer] *(Inherited Entity)*` and `[Total Sales] *(External Measure)*`), preventing broken links.
  - **Full Inclusion (`include_inherited_entities: true`)**: set this flag in the config file or via CLI to generate standalone pages for inherited entities as well.

---

## 🚀 Quickstart & Detailed Examples

### 1. Terminal Inspection (`inspect`)

Prints an overview of data sources, table classifications, calculated columns, and DAX dependencies:

```bash
python generate_json.py inspect ./samples/adventureworks_pbip
```

Example output:
```text
======================================================================
PBIP SEMANTIC MODEL: adventureworks_pbip (Format: TMDL)
======================================================================
[!] Excluded Auto Tables: 1 (Filter active: True)

[1] DATA SOURCES & POWER QUERY LINEAGE:
  * [SQL_SERVER] sql-dwh.adventureworks.com / AdventureWorksDW
  * [ODATA] https://crm.adventureworks.com/api/odata/v4/Customers
  * [SHAREPOINT] https://adventureworks.sharepoint.com/sites/bi/Shared Documents
  Power Query Expressions & Shared Queries (3):
    - Staging Orders (Upstream: [] -> Feeds: ['FactInternetSales'])
    - Staging Customers (Upstream: [] -> Feeds: ['DimCustomer'])
    - Staging Geography (Upstream: [] -> Feeds: ['DimCountry', 'DimGeography'])

[2] TABLE CLASSIFICATION & TOPOLOGY:
  * [FACT]               FactInternetSales         (Columns: 10)
      Reason: Topology: Pure Many-side endpoint filtering; High numeric density
      Connected Dimensions: DimCustomer, DimDate, DimProduct
      Snowflake Reachable Lookups: DimCountry, DimGeography, DimProductCategory, DimProductSubcategory
        Path: FactInternetSales -> DimCustomer -> DimGeography
        Path: FactInternetSales -> DimCustomer -> DimGeography -> DimCountry
        Path: FactInternetSales -> DimProduct -> DimProductSubcategory
        Path: FactInternetSales -> DimProduct -> DimProductSubcategory -> DimProductCategory

  * [DIMENSION]          DimCustomer               (Columns: 6)
  * [LOOKUP_OUTRIGGER]   DimGeography              (Columns: 4)
  * [LOOKUP_OUTRIGGER]   DimCountry                (Columns: 3)
  * [DATE_DIMENSION]     DimDate                   (Columns: 6)

[3] DAX MEASURES & DEPENDENCIES:
  * [Depth 0 ] [FactInternetSales] [Total Sales]
      Base Measure (columns only)
      Used by: Gross Margin, Margin %, Sales YTD, Prior Year Sales, Sales YoY Growth %
  * [Depth 1 ] [FactInternetSales] [Gross Margin]
      Calls: Total Cost, Total Sales
      Used by: Margin %
  * [Depth 2 ] [FactInternetSales] [Margin %]
      Calls: Gross Margin, Total Sales
======================================================================
```

### 2. JSON Extraction (`extract`)

Generates a complete metadata JSON file:

```bash
python generate_json.py extract ./samples/adventureworks_pbip -o output_documentation.json --indent 2
```

From a `model.bim` file:
```bash
python generate_json.py extract ./samples/retail_sales_bim/model.bim -o bim_docs.json
```

### 3. Markdown Document Generation (`docgen`)

Generates a dedicated Markdown document for every table, measure, function, and expression:

```bash
# From a PBIP directory
python generate_docs.py ./samples/adventureworks_pbip -o ./docs

# Or from an extracted JSON file
python generate_docs.py ./output_documentation.json -o ./docs
```

Generated directory structure:
```text
docs/
├── INDEX.md                     # Model catalog and overview
├── tables/
│   ├── FactInternetSales.md     # Fact table document
│   ├── DimCustomer.md           # Dimension document
│   ├── DimGeography.md          # Lookup / Outrigger document
│   └── DimDate.md               # Date dimension document
├── measures/
│   └── FactInternetSales/
│       ├── Total_Sales.md       # Base measure (Depth 0)
│       ├── Gross_Margin.md      # Composite measure (Depth 1)
│       └── Margin.md            # Advanced measure (Depth 2)
└── expressions/
    ├── Staging_Orders.md        # Staging query document
    └── StatusLookup.md          # Inline #table preview document
```

---

## 🧠 Resolution Algorithms

### 1. Power Query (M) Lineage Resolution
1. **Source Function Scanning**: scans source calls (`Sql.Database`, `PostgreSQL.Database`, `OData.Feed`, `SharePoint.Files`, `Excel.Workbook`, `Fabric.Lakehouse`, etc.) to extract server names, databases, URLs, and file paths.
2. **Multi-Hop Traversal**: follows query references (`#"Query Name"`) through intermediate staging queries up to physical source endpoints.
3. **Downstream Mapping**: tracks which final model tables consume each intermediate query.

### 2. Star Schema Classification & Snowflake Resolver
- **Topology Scoring**: tables on the "Many" side of 1:N relationships with high numeric column density are classified as **FACT**. Tables on the "One" side filtering facts are classified as **DIMENSION**.
- **Snowflake Outrigger Detection**: dimension parent tables that do not directly filter any fact are classified as **LOOKUP_OUTRIGGER**.
- **Transitive Paths**: resolves all join paths from facts to outriggers:
  $$\text{Fact} \xrightarrow{N:1} \text{Dimension} \xrightarrow{N:1} \text{Lookup}_1 \xrightarrow{N:1} \text{Lookup}_2$$
- **Date & Utility Recognition**: identifies date tables (by date columns or `CALENDAR` expressions) and disconnected parameter/utility tables.

### 3. DAX Measure Dependency Analyzer
- **Tokenization**: distinguishes measure references `[MeasureName]` from table columns `'Table'[Column]`.
- **DAG & Calculation Depth**:
  - `Depth 0`: base measures aggregating columns directly.
  - `Depth 1+`: composite measures referencing other measures.
- **Impact Analysis (Downstream)**: builds a reverse index mapping which measures are affected when an upstream measure changes.

---

## 📋 JSON Schema Specification

> For complete technical field specifications, data types, nullability, and extraction logic, see the [**JSON Schema Documentation**](documentation/json_schema/README.md).

```json
{
  "model_name": "adventureworks_pbip",
  "source_format": "TMDL",
  "compatibility_level": 1600,
  "culture": "en-US",
  "data_sources_summary": [
    {
      "source_type": "SQL_SERVER",
      "connection_string": "sql-dwh.adventureworks.com / AdventureWorksDW",
      "server": "sql-dwh.adventureworks.com",
      "database": "AdventureWorksDW"
    }
  ],
  "shared_queries": [
    {
      "query_name": "Staging Orders",
      "is_staging": true,
      "direct_dependencies": [],
      "downstream_tables": ["FactInternetSales"],
      "root_sources": []
    }
  ],
  "tables": [
    {
      "name": "FactInternetSales",
      "role": "FACT",
      "classification_reasoning": {
        "role": "FACT",
        "confidence_score": 0.99,
        "criteria_matched": [
          "Topology: Pure Many-side endpoint filtering",
          "High numeric column density (88%)"
        ]
      },
      "columns": [],
      "incremental_refresh_policy": {
        "is_enabled": true,
        "policy_type": "basic",
        "mode": "hybrid",
        "rolling_window_periods": 3,
        "rolling_window_granularity": "year",
        "incremental_periods": 7,
        "incremental_granularity": "day"
      },
      "connected_dimensions": ["DimCustomer", "DimDate", "DimProduct"],
      "reachable_lookup_tables": ["DimCountry", "DimGeography"],
      "snowflake_paths": []
    }
  ],
  "measures": [
    {
      "name": "Margin %",
      "table": "FactInternetSales",
      "dax_expression": "DIVIDE([Gross Margin], [Total Sales], 0)",
      "format_string": "0.0%",
      "calculation_depth": 2,
      "direct_measure_dependencies": ["Gross Margin", "Total Sales"],
      "all_upstream_measures": ["Gross Margin", "Total Cost", "Total Sales"],
      "downstream_measures": []
    }
  ],
  "relationships": [],
  "star_schema": {
    "fact_tables": ["FactInternetSales"],
    "dimension_tables": ["DimCustomer", "DimProduct"],
    "lookup_outrigger_tables": ["DimCountry", "DimGeography"],
    "date_tables": ["DimDate"]
  }
}
```

---

## 🧪 Running Tests

To run the automated test suite:

```bash
python -m unittest discover tests
```

All tests execute with zero external dependencies.
