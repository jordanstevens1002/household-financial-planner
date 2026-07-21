# Phase 5 evaluation

Phase 5 is complete only when all of the following are demonstrated in its pull request. The API
runtime and quality gates use Python 3.14, configuration uses `pydantic-settings`, and application
logging uses `structlog` with request correlation.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Phase 5 unit and integration tests | 100% passing |
| Coverage | Backend statement coverage | at least 85% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Forward upgrade from Phase 4 and Alembic schema-drift check | succeeds; no drift |
| Isolation | Cross-household rental and expense access | rejected or hidden |
| History | Backdated/future profiles and dated status transitions | tested |
| Mixed occupancy | Concurrent named portions; combined share capped at 100% | tested |
| Status rules | Rent, vacancy, fees, and rental expenses follow behavior flags | tested |
| Rent comparison | Market and chosen rent remain separately reported | tested |
| Performance | Warm ten-year property cash-flow calculation | p95 below 300 ms over 100 requests |

Test results and exceptions must be recorded in the Phase 5 pull request. A missed threshold
blocks merge.

## Recorded local results

- Python 3.14.6: 52 tests passed; 91% statement coverage, including an explicit standard
  whole-property rental calculation with vacancy and management fees.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: forward upgrade from Phase 4 to head and Alembic drift check passed.
- Cash-flow benchmark: ten-year partially rented home with three concurrent rental portions;
  10 warm-ups then 100 requests; p50 29.26 ms, p95 36.30 ms, maximum 46.49 ms;
  required p95 below 300 ms — **PASS**.
