# Phase 10I evaluation

## Scope

Phase 10I exposes the household financial-event timeline through Appsmith:

- observed history, planned decisions and projected estimates remain visibly distinct;
- ordering, classification and data-quality flags come from FastAPI;
- optional date filters and disabled-event inclusion are available;
- new events require an explicit type, provenance and effective timestamp;
- planned or projected events may be enabled or disabled; and
- payload JSON and idempotency keys are Advanced settings.

Observed events cannot be disabled. Appsmith does not recalculate provenance or quality flags.

## Automated acceptance

```bash
docker compose exec -T api alembic check
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
```

Recorded results:

- Backend: 115 tests passed on Python 3.14 with 92% coverage.
- Appsmith: 52 structural and deterministic-export tests passed.
- Ruff, formatting and Mypy passed.
- Alembic reported no schema drift.
- The live API readiness check passed.

## Edit-mode and deployed-mode review

Repeat in both modes:

1. Select a household and open **Timeline**.
2. Confirm existing events are ordered by effective date and display provenance, related record,
   enabled state and quality flags.
3. Filter by a valid from/to date and confirm only matching events remain.
   With both dates blank, confirm the request omits both parameters rather than sending `null`.
4. Add a planned event with an explicit ISO timestamp such as `2027-01-01T09:00:00+11:00`.
5. Confirm it appears as **Planned**, then disable and re-enable it.
6. Confirm an observed event cannot be toggled.
7. Add an intentionally inconsistent event, such as observed history in the future, and confirm
   the backend quality warning is visible.
8. Enable **Advanced settings** and confirm payload JSON and idempotency key fields appear.
9. Enter invalid JSON and confirm the save button is disabled.
10. Change the date filter to include disabled events and confirm disabled plans become visible.

## Evaluation metrics

- Backend and Appsmith suites pass.
- API coverage remains at least 90%.
- Export regeneration is deterministic.
- Alembic reports no schema drift.
- Timeline presentation uses backend classification and quality flags.
- Edit and deployed modes persist and display the same events.
