# Phase 8 evaluation

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Full unit and integration suite | 100% passing |
| Coverage | Backend statement coverage | at least 90% |
| Static quality | Ruff formatting/lint and strict mypy | no errors |
| Migration | Forward upgrade from Phase 7 and Alembic schema drift | succeeds; no drift |
| Feasibility | Funding, borrowing, costs, buffer, LVR and surplus | tested |
| Ownership | Allocations total 100% and people belong to household | enforced |
| Isolation | Cross-household plans and ownership references | rejected or hidden |
| Abstraction | Non-Australian provider uses generic contract | tested without shared changes |
| Performance | Warm feasibility calculation over 100 runs | p95 below 50 ms |

## Recorded local results

- Python 3.14.6: 92 tests passed; 91.85% statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- Provider contract: non-Australian example registered without shared planner changes.
- PostgreSQL 16: forward upgrade from Phase 7 passed; Alembic reported no schema drift.
- Feasibility benchmark: 10 warm-ups then 100 runs; p50 0.01 ms, p95 0.02 ms,
  maximum 0.16 ms; required p95 below 50 ms — **PASS**.
