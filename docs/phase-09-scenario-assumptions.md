# Phase 9 scenario assumptions

Scenarios answer “what if?” questions without changing a household's recorded facts. The API
therefore receives explicit baseline metrics for each calculation and returns adjusted metrics and
event instructions. It does not persist calculated results or silently rewrite financial events.

## Supported override targets

- `METRIC` applies `SET`, `ADD`, or `MULTIPLY_PERCENT` to a named baseline metric.
- `FINANCIAL_EVENT` returns a dated instruction such as `ENABLE`, `DISABLE`, `SHIFT_DAYS`, or a
  field adjustment for a specific event owned by the same household.

An override applies when its `effective_from` is on or before the requested date and its optional
`effective_to` has not passed. Base scenarios are applied oldest-first, followed by the selected
scenario. This makes later, more specific overrides deterministic.

Metric keys are intentionally open strings. They let later projection services and external
extensions add metrics without editing the scenario tables. Callers should use stable documented
keys and show calculation warnings when a requested or adjusted metric is absent.

## Templates and jurisdictions

Bundled templates are small, editable examples such as lower income, higher household expenses,
higher interest rates, and lower property growth. They contain no tax, retirement, purchase-cost,
currency, or country assumptions. Australia is not selected or inferred anywhere in the scenario
engine. If country-specific scenario packs are introduced later, they must be optional extensions
and must not add jurisdiction branches to shared calculation or API code.

Scenario output is a planning aid, not financial advice. A scenario is only as reliable as its
baseline metrics, dates, override values, and the downstream projection engines that consume event
instructions.
