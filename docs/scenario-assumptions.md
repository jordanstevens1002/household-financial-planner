# Scenario assumptions

Scenarios answer “what if?” questions without changing recorded facts. The API receives explicit
baseline metrics and returns adjusted metrics and event instructions. It does not persist calculated
results or silently rewrite financial events.

## Supported override targets

- `METRIC` applies `SET`, `ADD` or `MULTIPLY_PERCENT` to a named baseline metric.
- `FINANCIAL_EVENT` returns an instruction such as `ENABLE`, `DISABLE`, `SHIFT_DAYS` or a field
  adjustment for a specific event owned by the same household.

An override applies when its `effective_from` is on or before the requested date and its optional
`effective_to` has not passed. Base scenarios are applied oldest-first, followed by the selected
scenario.

Metric keys are intentionally open strings so later projection services and extensions can add
metrics without editing scenario tables. Callers should use stable keys and show warnings when a
requested or adjusted metric is absent.

Bundled templates contain no tax, retirement, purchase-cost, currency or country assumptions.
Australia is not selected or inferred by the scenario engine.

Scenario output is an estimate, not financial advice. It is only as reliable as its baselines,
dates, overrides and downstream calculation engines.
