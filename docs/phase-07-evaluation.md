# Phase 7 evaluation

Phase 7 is complete only when all retirement-account quality gates below pass. The API runtime,
tests and static analysis use Python 3.14; configuration remains at the `pydantic-settings`
boundary and request/application logging remains structured with `structlog`.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Full unit and integration suite | 100% passing |
| Coverage | Backend statement coverage | at least 90% |
| Static quality | Ruff formatting/lint and strict mypy | no errors |
| Migration | Forward upgrade from Phase 6 and Alembic schema-drift check | succeeds; no drift |
| Projection | Opening balance, contributions, tax, fees, earnings and adjustments | tested |
| History | Dated contribution profiles and adjustments | deterministic and tested |
| Australian super | Preservation age and contribution-cap metadata | validated and tested |
| Isolation | Cross-household people and retirement accounts | rejected or hidden |
| Reliability | Duplicate correction event | rejected by idempotency key |
| Performance | Warm 40-year monthly calculation | p95 below 300 ms over 100 runs |

Test and benchmark results must be recorded here and in the Phase 7 pull request. A missed
threshold blocks merge.

## Recorded local results

- Python 3.14.6: 85 tests passed; 91.70% backend statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: forward upgrade from Phase 6 to Phase 7 passed; Alembic reported no schema drift.
- Packaged Docker test image: full quality suite passed.
- Forty-year monthly calculation benchmark: 10 warm-ups then 100 runs; p50 8.69 ms,
  p95 10.18 ms, maximum 40.24 ms; required p95 below 300 ms — **PASS**.
