# Phase 9 evaluation

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Full unit and integration suite | 100% passing |
| Coverage | Backend statement coverage | at least 90% |
| Static quality | Ruff formatting/lint and strict mypy | no errors |
| Migration | Forward upgrade from Phase 8 and Alembic schema drift | succeeds; no drift |
| Scenario behaviour | Dates, operations, inheritance and comparisons | tested |
| Event safety | Scenario event override | returned without changing recorded event |
| Isolation | Cross-household scenarios, bases and event targets | rejected or hidden |
| Abstraction | Country assumptions in shared scenario engine | none |
| Performance | 1,000 overrides over 100 warm calculations | p95 below 100 ms |

## Recorded local results

- Python 3.14.6: 101 tests passed; 92% statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- Scenario behaviour: effective dates, metric operations, inheritance, comparison and event
  immutability passed.
- Isolation: cross-household event targets were rejected and inaccessible scenarios were hidden.
- Abstraction: all templates passed the generic override-contract check, and identical inputs
  produced identical results for AU/AUD and CA/CAD households.
- PostgreSQL 16: forward upgrade through Phase 9 passed; Alembic reported no schema drift.
- Calculation benchmark: 10 warm-ups then 100 runs with 1,000 overrides; p50 4.36 ms,
  p95 5.29 ms, maximum 6.09 ms; required p95 below 100 ms — **PASS**.
