# Post-Phase 9 architecture alignment evaluation

This checkpoint reconciles the implemented backend with the cross-cutting priorities established
during Phases 1–9. It is not a new product phase.

| Area | Metric | Required threshold |
|---|---|---:|
| Correctness | Full unit and integration suite | 100% passing |
| Coverage | Backend statement coverage | at least 90% |
| Static quality | Ruff formatting/lint and strict mypy | no errors |
| Migration | Forward upgrade from Phase 9 and Alembic schema drift | succeeds; no drift |
| Terminology | Shared ownership enum | `RETIREMENT_FUND`; no `SUPER_FUND` |
| Provider abstraction | Bundled tax example | loaded through neutral built-in registry boundary |
| Explicit inputs | Purchase feasibility material assumptions | required and reported |
| Loan assumptions | Missing loan term | no implicit 360-month projection |
| Day-count visibility | Daily loan/rental calculations | basis disclosed in response |
| Performance | Existing Phase 9 1,000-override benchmark | p95 below 100 ms |

## Audit disposition

- Historical migrations retain the names and operations that originally shipped. Phase 5 already
  renames the old `applies_landlord_expenses` column in the resulting schema, so rewriting Phase 1
  or Phase 5 migration history is neither required nor safe.
- Australian tax, retirement and purchase modules remain bundled examples. They are isolated from
  shared services by provider contracts and neutral built-in registries.
- Config remains centralized in `pydantic-settings`; all API modules use structured `structlog`
  logging and request correlation. No alternate environment-variable boundary was found.
- The current daily calculations use an actual/365 planning basis. This checkpoint makes that
  visible; configurable day-count conventions can be added with future loan-product modelling.

## Recorded local results

- Python 3.14.6: 106 tests passed; 92% backend statement coverage.
- Ruff formatting/lint and strict mypy: no errors.
- PostgreSQL 16: forward upgrade from `0009_scenarios` to
  `0010_architecture_alignment` passed; the enum retained all values with
  `RETIREMENT_FUND` replacing `SUPER_FUND`; Alembic reported no schema drift.
- Explicit-assumption regressions passed for purchase feasibility, open-ended loan schedules,
  actual/365 daily loan interest, and recurring rental allocation.
- Provider and terminology architecture tests passed.
- The unchanged Phase 9 scenario benchmark remains p95 5.29 ms against the 100 ms threshold.
