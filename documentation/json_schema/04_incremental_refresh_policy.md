---
title: "04. Incremental Refresh Policy"
target_json_path: "/tables[]/incremental_refresh_policy"
python_module: "pbip_doc/parser.py"
source_formats: ["TMDL", "BIM"]
tags: ["incremental_refresh", "hybrid_tables", "refreshPolicy", "polling_expression", "rolling_window"]
---

# 04. Incremental Refresh Policy (`tables[].incremental_refresh_policy`)

> **TL;DR**:
> - Represents the incremental refresh policy and hybrid partitioning settings for each table.
> - Captures historical retention (`rolling_window_periods`) and incremental refresh windows (`incremental_periods`).
> - Identifies realtime DirectQuery hybrid partitions (`mode: "hybrid"`).
> - Extracts polling expressions used by Power BI Service to detect data changes.
> - If a table uses full refresh, this property is `null`.

---

## 📋 Policy Properties Schema

| JSON Property | Data Type | Nullable | Description |
|---|---|---|---|
| `is_enabled` | `boolean` | No | `true` if an incremental refresh policy is configured on the table; otherwise `false`. |
| `policy_type` | `string` | Yes | Policy type (e.g. `"basic"`). |
| `mode` | `string` | Yes | Partition storage mode: `"import"` (standard) or `"hybrid"` (realtime DirectQuery partition). |
| `rolling_window_periods` | `integer` | Yes | Size of the historical data retention window (e.g. `3` for 3 years). |
| `rolling_window_granularity` | `string` | Yes | Unit of the historical window: `"year"`, `"quarter"`, `"month"`, `"day"`. |
| `incremental_periods` | `integer` | Yes | Size of the rolling incremental refresh window (e.g. `7` for 7 days). |
| `incremental_granularity` | `string` | Yes | Unit of the refresh window: `"year"`, `"quarter"`, `"month"`, `"day"`. |
| `polling_expression` | `string` | Yes | Power Query M expression used to detect data changes (*Detect Data Changes*). |
| `source_expression` | `string` | Yes | Power Query M expression parameterized with `RangeStart` and `RangeEnd`. |
| `raw_policy` | `object` | No | Complete raw metadata dictionary from Power BI. |

---

## 🔍 Extraction & Detection Logic

### 1. TMDL Format (`tables/<TableName>.tmdl`)

In TMDL, refresh policies appear in one of two formats:

#### Syntax A: Indented `refreshPolicy` Block
```text
refreshPolicy
    policyType: basic
    rollingWindowPeriods: 3
    rollingWindowGranularity: year
    incrementalPeriods: 10
    incrementalGranularity: day
    sourceExpression:
        let
            Source = Sql.Database("server", "db"),
            Filtered = Table.SelectRows(Source, each [OrderDate] >= RangeStart and [OrderDate] < RangeEnd)
        in
            Filtered
```

#### Syntax B: Inline JSON Block
```text
refreshPolicy = {
    "policyType": "basic",
    "mode": "hybrid",
    "rollingWindowPeriods": 5,
    "rollingWindowGranularity": "year",
    "incrementalPeriods": 3,
    "incrementalGranularity": "day",
    "pollingExpression": "let ... in ..."
}
```

- **Detection**: identified by `PBIPParser._parse_tmdl_refresh_policy()`.
- **Parsing**: if valid JSON is found (`{...}`), it is deserialized directly; otherwise, individual indented properties and the multiline `sourceExpression` are extracted line-by-line.

---

### 2. TMSL Format (`model.bim`)

In `model.bim`, the policy is an object nested directly under the table:

```json
{
  "name": "FactOrders",
  "refreshPolicy": {
    "policyType": "basic",
    "mode": "import",
    "rollingWindowPeriods": 3,
    "rollingWindowGranularity": "year",
    "incrementalPeriods": 14,
    "incrementalGranularity": "day",
    "sourceExpression": [
      "let",
      "    Source = ...",
      "in",
      "    Filtered"
    ]
  }
}
```

- **Field Mapping**:
  - `rolling_window_periods`: from `rollingWindowPeriods`.
  - `rolling_window_granularity`: from `rollingWindowGranularity`.
  - `incremental_periods`: from `incrementalPeriods` (or fallback `incrementalWindowPeriods`).
  - `incremental_granularity`: from `incrementalGranularity` (or fallback `incrementalWindowGranularity`).
  - `mode`: from `mode` (defaults to `"import"`).
  - Array expressions for `sourceExpression` or `pollingExpression` are joined into single strings with `\n`.

---

## 💡 Example JSON

### Active Policy (Hybrid Mode)
```json
{
  "is_enabled": true,
  "policy_type": "basic",
  "mode": "hybrid",
  "rolling_window_periods": 3,
  "rolling_window_granularity": "year",
  "incremental_periods": 7,
  "incremental_granularity": "day",
  "polling_expression": "let\n    MaxDate = ...\nin\n    MaxDate",
  "source_expression": "let\n    Source = Sql.Database(\"sql-srv\", \"DWH\"),\n    Filtered = Table.SelectRows(Source, each [OrderDate] >= RangeStart and [OrderDate] < RangeEnd)\nin\n    Filtered",
  "raw_policy": {
    "policyType": "basic",
    "mode": "hybrid",
    "rollingWindowPeriods": 3,
    "rollingWindowGranularity": "year",
    "incrementalPeriods": 7,
    "incrementalGranularity": "day"
  }
}
```

### Table Without Incremental Refresh (Full Refresh)
When a table does not have an incremental policy, the property is set to `null`:
```json
{
  "name": "DimCustomer",
  "incremental_refresh_policy": null
}
```

---

## ❓ Frequently Asked Questions (FAQ)

### Q: What does mode: "hybrid" mean?
**A**: In Power BI, hybrid tables store older partitioned periods in Import mode, but keep the latest period in DirectQuery mode for realtime data access without full refreshes.

### Q: What is polling_expression used for?
**A**: It corresponds to the *Detect data changes* feature in Power BI. Power BI runs this query periodically (e.g. `MAX(LastUpdateDate)`), and only refreshes the incremental partitions if the returned value changes.

### Q: What is the value of incremental_refresh_policy if a table is not incrementally refreshed?
**A**: It is `null`. Consumers can simply check `if table.get("incremental_refresh_policy") is not None` to verify if a policy is active.
