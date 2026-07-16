# Phase 2 evaluation

Phase 2 is complete only when all of the following are demonstrated in its pull request.
The API runtime and quality gates use Python 3.14, configuration uses `pydantic-settings`,
and application logging uses `structlog`.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Phase 2 unit and integration tests | 100% passing |
| Coverage | Backend statement coverage | at least 85% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Upgrade from Phase 1 and downgrade/upgrade round trip | succeeds |
| Isolation | Cross-household property access | returns 404 |
| Ownership | Dated totals and incomplete-record warnings | tested at 100%, below and above |
| Backdating | Historical purchase and current snapshot workflows | both persist atomically |
| Flexibility | Property without loan or complete address | accepted |
| Performance | Warm property list endpoint, local container | p95 below 300 ms over 100 requests |

Test results and exceptions must be recorded in the Phase 2 pull request. A missed threshold
blocks merge.
