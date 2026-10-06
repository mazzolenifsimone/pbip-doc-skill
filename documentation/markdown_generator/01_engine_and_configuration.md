---
title: "01. Documentation Engine & Configuration"
target_path: "pbip_doc/docgen/engine.py, pbip_doc/docgen/config.py"
python_module: "pbip_doc.docgen"
tags: ["engine", "orchestration", "configuration", "publishing_rules", "filters"]
---

# 01. Documentation Engine & Configuration

> **TL;DR**:
> - `MarkdownDocGenerator` orchestrates the rendering of all model entities into Markdown files.
> - Supports direct execution from raw PBIP folders, TMSL `model.bim` files, or previously extracted JSON files.
> - Governed by `DocGenConfig`, which controls publishing filters, modular sections, directory paths, and YAML frontmatter.
> - Implements publishing rules that exclude auto-generated date tables and out-of-scope inherited entities.

---

## ⚙️ Orchestration Workflow (`MarkdownDocGenerator`)

The generator processes semantic model metadata through an assembly pipeline:

```text
 ┌────────────────────────────────────────────────────────┐
 │ Input: PBIP Folder / model.bim / Pre-extracted JSON    │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │              Normalization (_load_model_dict)          │
 └───────────────────────────┬────────────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Master Index  │     │ Table Pages   │     │ Measure Pages │
│  (INDEX.md)   │     │ (tables/*.md) │     │(measures/*/*.md)
└───────────────┘     └───────────────┘     └───────────────┘
     │                       │                       │
     ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐
│ Function Pages│     │Expression Docs│
│(functions/*.md│     │(expressions/*.md)
└───────────────┘     └───────────────┘
```

1. **Input Normalization (`_load_model_dict`)**:
   - If an in-memory dictionary is passed, it is used directly.
   - If a file path pointing to an extracted JSON is passed, it is loaded.
   - If a directory (PBIP TMDL folder) or `model.bim` file is passed, `PBIPParser` parses it directly on the fly.
2. **In-Memory Document Generation (`generate_all_documents`)**:
   - Compiles each Markdown document in memory and returns a dictionary of `{relative_path: markdown_content}`.
3. **Directory Export (`write_to_directory`)**:
   - Ensures output directories exist and writes out each document encoded in UTF-8.

---

## 🛡️ Publishing Rules & Exclusion Filters

Not every table or measure in a Power BI project should have its own standalone Markdown page. The engine uses two deterministic filter functions:

### 1. Table Publishing Filter (`is_table_published`)

A table is evaluated for publication through the following conditions:

| Condition | Result | Explanation |
|---|---|---|
| Matches `excluded_table_patterns` | **Skipped** | Regex pattern matches auto-generated date tables (`LocalDateTable_*`, `DateTableTemplate_*`). |
| In `excluded_tables` list | **Skipped** | Explicitly excluded by name via config or `--exclude-tables`. |
| `is_inherited == true` or `out_of_scope == true` | **Skipped** (by default) | Derived from a remote entity (`partition = entity`). Only published if `include_inherited_entities: true`. |
| Regular native table | **Published** | Written to `tables/<TableName>.md`. |

### 2. Measure Publishing Filter (`is_measure_published`)

A measure is evaluated for publication through the following conditions:

| Condition | Result | Explanation |
|---|---|---|
| Host table is excluded | **Skipped** | If the parent table is excluded, its measures are not published. |
| `is_inherited == true` or `is_external_measure == true` | **Skipped** (by default) | Measure defined via `EXTERNALMEASURE` in a composite model. Only published if `include_inherited_entities: true`. |
| Regular native DAX measure | **Published** | Written to `measures/<HostTable>/<MeasureName>.md`. |

---

## 🎛️ Configuration Structure (`DocGenConfig`)

`DocGenConfig` defines all generator settings with default values:

### General & Path Settings
- `output_dir` (default: `"docs"`): Root output directory.
- `tables_subdir` (default: `"tables"`): Subdirectory for table pages.
- `measures_subdir` (default: `"measures"`): Subdirectory for measure pages.
- `functions_subdir` (default: `"functions"`): Subdirectory for UDF function pages.
- `expressions_subdir` (default: `"expressions"`): Subdirectory for expression pages.
- `generate_index_file` (default: `true`): Generates `INDEX.md`.
- `sanitize_filenames` (default: `true`): Replaces characters invalid in filesystems (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) with underscores.
- `include_markdown_links` (default: `true`): Enables cross-linking between measures, tables, and expressions.

### Section Toggle Flags
Each document type provides modular section toggles:
- **Table Sections**: `include_table_yaml_frontmatter`, `include_table_topology_section`, `include_table_lineage_section`, `include_table_incremental_refresh`, `include_table_columns_dictionary`, `include_table_relationships_section`, `include_table_snowflake_paths`, `include_table_measures_list`, `include_table_m_code`, `include_table_rag_hints`.
- **Measure Sections**: `include_measure_yaml_frontmatter`, `include_measure_dax_formula`, `include_measure_upstream_deps`, `include_measure_downstream_impact`, `include_measure_referenced_columns`, `include_measure_rag_hints`.
- **Expression Sections**: `include_expression_docs`, `include_expression_yaml_frontmatter`, `include_expression_overview_section`, `include_expression_inline_table`, `include_expression_lineage_section`, `include_expression_steps_section`, `include_expression_m_code`, `include_expression_rag_hints`.
- **Function Sections**: `include_function_yaml_frontmatter`, `include_function_parameters_section`, `include_function_formula_section`, `include_function_downstream_section`, `include_function_rag_hints`.

---

## ❓ Frequently Asked Questions (FAQ)

### Q: What happens if an excluded table is part of a relationship?
**A**: When a table is excluded, relationships pointing to it are filtered out from the published table documentation and relationship graphs, keeping the documentation clean.

### Q: Why are measures grouped into folders by host table?
**A**: Real-world semantic models can have hundreds or thousands of DAX measures. Grouping measures under `measures/<HostTable>/` avoids placing thousands of files in a single flat directory, making navigation cleaner for both humans and operating systems.

### Q: How can an agent override settings dynamically?
**A**: In the MCP server, pass `config_overrides: {"include_table_m_code": false}`. In the CLI, pass `--config-json '{"include_table_m_code": false}'` or `--set include_table_m_code=false`.
