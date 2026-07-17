# Phase 3 evaluation

Phase 3 is complete only when all of the following are demonstrated in its pull request.
The API runtime and quality gates use Python 3.14, configuration uses `pydantic-settings`,
and application logging uses `structlog` with request correlation.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Phase 3 unit and integration tests | 100% passing |
| Coverage | Backend statement coverage | at least 85% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Upgrade from Phase 2 and downgrade/upgrade round trip | succeeds |
| Isolation | Cross-household event references and reads | rejected or hidden |
| Ordering | Effective time, priority, recorded time and UUID | deterministic |
| Backdating | Older event added after newer records | resolves chronologically |
| Planning | Planned event enable/disable | excluded/included as selected |
| Resolution | Latest baseline plus enabled later events | correct at arbitrary date |
| Data quality | Invalid temporal/provenance combinations | explicitly flagged |
| Performance | Warm household timeline with 1,000 events | p95 below 500 ms over 100 requests |

Test results and exceptions must be recorded in the Phase 3 pull request. A missed threshold
blocks merge.

## Recorded local results

- Python 3.14.6: 32 tests passed; 90% statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: upgrade to head, downgrade to Phase 2, re-upgrade, and Alembic drift check passed.
- Timeline benchmark: 1,000 events; 10 warm-ups then 100 requests; p50 57.98 ms,
  p95 106.71 ms, maximum 130.46 ms; required p95 below 500 ms — **PASS**.
