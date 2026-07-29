# Phase 10H evaluation

## Scope

Phase 10H exposes the existing country-neutral retirement engine through Appsmith:

- household or person-linked retirement accounts;
- API-discovered account types and installed providers;
- non-overlapping dated contribution profiles;
- backend-calculated projections with contributions, tax, fees and earnings; and
- visible assumptions and warnings.

Provider-specific JSON is an optional Advanced setting. The UI does not infer a provider from
currency, jurisdiction or account holder.

## Automated acceptance

Run:

```bash
docker compose exec -T api sh scripts/check.sh
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
git diff --exit-code -- appsmith/household-financial-planner.json
docker compose exec -T api alembic check
```

Recorded results:

- Backend: 115 tests passed on Python 3.14 with 92% coverage.
- Appsmith: 49 structural and deterministic-export tests passed.
- Ruff, formatting and Mypy passed.
- Alembic reported no schema drift.
- The live API was healthy and returned the installed retirement-provider catalogue.

## Edit-mode and deployed-mode review

Repeat the functional flow in both modes:

1. Select a household containing at least one person.
2. Open **Retirement** and confirm an empty state appears when no accounts exist.
3. Create a generic account with an explicit type, opening balance/date, return rate and fees.
4. Confirm the account appears with the household currency inherited by the backend.
5. Select the account and add a dated contribution profile.
6. Confirm entering both an employer rate and employer amount is blocked.
7. Confirm an overlapping profile is rejected with a useful API message.
8. Calculate a future projection and verify the balance, contributions, contribution tax, fees,
   earnings, assumptions and warnings are visible.
9. Create a compatible provider-backed account using a discovered provider. Confirm raw settings
   are visible only after enabling **Advanced settings**.
10. Change households and confirm the previously selected retirement account is cleared.

## Evaluation metrics

- Backend and Appsmith automated suites pass.
- API coverage remains at least 90%.
- Appsmith export regeneration is deterministic.
- Alembic reports no schema drift.
- No country/provider code is embedded in the shared Appsmith account action.
- Edit and deployed modes persist and calculate the same values.
