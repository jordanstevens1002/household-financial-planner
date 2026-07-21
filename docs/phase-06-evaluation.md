# Phase 6 evaluation

Phase 6 is complete only when all of the following are demonstrated in its pull request. The API
runtime and quality gates use Python 3.14, configuration uses `pydantic-settings`, and application
logging uses `structlog` with request correlation.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Full unit and integration suite | 100% passing |
| Coverage | Backend statement coverage | at least 85% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Forward upgrade from Phase 5 and Alembic schema-drift check | succeeds; no drift |
| Tax boundaries | Every 2025–26 resident, foreign-resident, LITO and HELP tier | tested |
| Extensibility | A non-Australian provider uses the generic contract without income-service changes | tested |
| Manual mode | Manual net income bypasses component estimates explicitly | tested |
| History | Future and ended income/expenses excluded from snapshots | tested |
| Isolation | Cross-household people and expense references | rejected or hidden |
| Cash flow | Multiple income sources, tax, non-taxable income and expenses | tested |
| Performance | Warm household cash-flow snapshot for 20 people and 100 records | p95 below 300 ms over 100 requests |

Test results and exceptions must be recorded in the Phase 6 pull request. A missed threshold
blocks merge.

## Recorded local results

- Python 3.14.6: 79 tests passed; 91.47% statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: forward upgrade from Phase 5 to head and Alembic drift check passed.
- Tax boundary tests: all implemented resident, foreign-resident, LITO, Medicare and 2025–26
  study-loan branches passed.
- Provider contract: a non-Australian example provider selected its own tax year and parameters
  without changes to the shared income service or response schema.
- Household snapshot benchmark: 20 people with 100 income records and automatic tax profiles;
  10 warm-ups then 100 requests; p50 42.05 ms, p95 49.19 ms, maximum 57.02 ms;
  required p95 below 300 ms — **PASS**.
