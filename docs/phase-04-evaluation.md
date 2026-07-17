# Phase 4 evaluation

Phase 4 is complete only when all of the following are demonstrated in its pull request.
The API runtime and quality gates use Python 3.14, configuration uses `pydantic-settings`,
and application logging uses `structlog` with request correlation.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Phase 4 unit and integration tests | 100% passing |
| Coverage | Backend statement coverage | at least 85% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Forward upgrade from Phase 3 and Alembic schema-drift check | succeeds; no drift |
| Isolation | Cross-household loan/property/goal references | rejected or hidden |
| History | Opening snapshot plus dated loan events | resolves deterministically |
| Schedules | Daily/monthly interest and weekly/fortnightly/monthly repayment | tested |
| Features | Offset, redraw, lump sum, rate, repayment, term, IO, closure and refinance | tested |
| Goals | No hard-coded repayment target; household/loan goal required | tested |
| Performance | Warm 30-year schedule with 100 loan events | p95 below 300 ms over 100 requests |

Test results and exceptions must be recorded in the Phase 4 pull request. A missed threshold
blocks merge.

## Recorded local results

- Python 3.14.6: 43 tests passed; 90% statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: forward upgrade from Phase 3 to head and Alembic drift check passed.
- Schedule benchmark: 30-year daily-interest loan with 100 dated events; 10 warm-ups then
  100 requests; p50 24.07 ms, p95 28.65 ms, maximum 75.78 ms; required p95 below
  300 ms — **PASS**.
