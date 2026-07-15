# Phase 1 evaluation

Phase 1 is complete only when all of the following are demonstrated in its pull request.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Automated unit and integration tests | 100% passing |
| Coverage | Backend statement coverage | at least 80% |
| Static quality | Ruff and strict mypy | no errors |
| Migrations | Upgrade from empty PostgreSQL database | succeeds |
| Containerisation | API image and Compose configuration | build/validate successfully |
| Availability | Liveness without DB and readiness with DB | expected status responses |
| Isolation | Unauthorised household identifier | returns 404 without data disclosure |
| Authentication | Development identity when opt-in is disabled | rejected with 401 |
| Performance | Warm liveness endpoint, local container | p95 below 250 ms over 100 requests |

Test results and any exceptions must be recorded in the Phase 1 pull request. A missed threshold blocks merge.

