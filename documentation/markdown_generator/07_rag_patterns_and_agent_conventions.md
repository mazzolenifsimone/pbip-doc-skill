---
title: "07. RAG Optimization & Agent Conventions"
target_path: "docs/"
python_module: "pbip_doc.docgen.utils, pbip_doc.docgen"
tags: ["rag", "llm", "agents", "frontmatter", "sanitization", "chunking", "token_economy"]
---

# 07. RAG Optimization & Agent Conventions

> **TL;DR**:
> - The Markdown documentation is designed specifically for dual human and AI agent consumption.
> - Structured YAML frontmatter provides deterministic metadata filtering for vector databases (Chroma, Pinecone, Qdrant, Weaviate).
> - File boundaries serve as natural token chunks (500–2,500 tokens), preventing context window overflows.
> - Markdown strings (DAX formulas, descriptions) undergo table sanitization to prevent broken Markdown syntax.
> - Relative cross-links allow autonomous agents to traverse dependency graphs file by file.

---

## 🏷️ Standardized Frontmatter Taxonomy

Every generated Markdown file begins with structured YAML frontmatter bounded by `---`. Vector ingestion pipelines can parse this header to apply pre-filtering and faceted searches:

### `doc_type` Classification
Vector search engines can filter on `doc_type` to immediately restrict query scopes:
- `"semantic_model_catalog"`: High-level overview and index (`INDEX.md`).
- `"table_documentation"`: Physical and calculated tables (`tables/*.md`).
- `"dax_measure_documentation"`: Business logic metrics (`measures/*/*.md`).
- `"power_query_expression_documentation"`: Shared ETL queries (`expressions/*.md`).
- `"dax_function_documentation"`: User-Defined Functions (`functions/*.md`).

### Faceted Metadata Properties
- `role`: Filter tables by `"FACT"`, `"DIMENSION"`, `"LOOKUP_OUTRIGGER"`, `"DATE_DIMENSION"`, or `"BRIDGE"`.
- `calculation_depth`: Filter measures by complexity (`0` for base metrics, `1` for secondary KPIs, `2+` for composite KPIs).
- `is_inherited`: Filter out or isolate remote entity tables in composite models.
- `tags`: Array of lowercased search keywords including sanitized table names, metric names, and domain tags.

---

## 🪙 Token Economy & Chunking Boundaries

In standard documentation generators, a single massive Markdown file (often 50,000+ tokens) is emitted. This causes severe retrieval problems:
1. Retrieval returns either truncated snippets or overloads the LLM context window.
2. Embeddings computed over giant documents suffer from loss of granular semantic specificity.

### The PBIP Engine Solution
The engine generates **fine-grained, entity-scoped documents**:
- Each table document: ~800 to 2,000 tokens.
- Each measure document: ~400 to 1,200 tokens.
- Each expression document: ~500 to 1,500 tokens.

Each document represents an **atomic semantic chunk**. When an agent asks *"How is Margin % calculated?"*, a vector search retrieves only the `Margin_Pct.md` document, providing 100% of the formula, upstream dependencies, and downstream impact without wasting context tokens on unrelated tables.

---

## 🧼 Markdown Table Sanitization (`utils.py`)

DAX formulas and Power Query code frequently contain pipe characters (`|` and `||`) and multiline line breaks. If directly inserted into Markdown table cells (such as column dictionaries or dependency tables), pipes break column alignments and line breaks corrupt row structures.

The sanitization utility (`sanitize_table_cell` in `pbip_doc/docgen/utils.py`):
1. **Replaces unescaped pipes**: transforms `|` into `\|` or `&#124;` inside table cells.
2. **Normalizes line breaks**: replaces `\r\n` and `\n` inside table cells with `<br>` tags or spaces.
3. **Multiline Formulas Isolation**: renders full formulas in dedicated fenced code blocks (` ```dax `) rather than squeezing complex logic into compact table cells.

---

## 🔗 Bidirectional Cross-Linking

All relationships and dependencies are cross-linked with relative Markdown links:

```text
[FactInternetSales.md]
        │
        ├──> [DimCustomer.md] (Relationship Link)
        │
        └──> [Total_Sales.md] (Hosted Measure Link)
                  │
                  ├──> [Gross_Margin.md] (Upstream Dependency Link)
                  │
                  └──> [FactInternetSales.md] (Parent Table Link)
```

This bidirectional web allows autonomous coding agents using file tools (e.g. `view_file` or link-following crawlers) to traverse the semantic model graph deterministically without needing global knowledge loaded in context.

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Can YAML frontmatter be disabled?
**A**: Yes. Passing `--no-frontmatter` in the CLI or setting `include_table_yaml_frontmatter: false` and `include_measure_yaml_frontmatter: false` omits the YAML headers.

### Q: How do Contextual RAG Search Hints work?
**A**: At the bottom of each document, the generator produces pre-computed search queries (e.g. *"What is the business description for DimCustomer?"*). These phrases increase dense embedding alignment with human conversational prompts during vector retrieval.
