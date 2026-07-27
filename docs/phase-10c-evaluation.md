# Phase 10C people identity evaluation

Phase 10C is complete only when an authenticated user can create and list people for the selected
household in both Appsmith edit mode and the deployed application. This slice records identity and
effective dates only. Income, detailed tax configuration and other financial setup remain outside
this PR.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| People actions using shared runtime auth | 100% |
| Country or tax-jurisdiction defaults | 0 |
| Distinct v1.93 table column identities | 100% |
| Persistent credential values | 0 |
| Backend regression suite | 100% passing |
| Compose validation | Pass |

## Runtime review

Import `appsmith/household-financial-planner.json` into the Appsmith version pinned by Docker
Compose. Confirm all of the following in edit mode and again after **Deploy**:

1. Save a valid development identity or bearer token and restore/select a household.
2. People cannot be added without a selected household.
3. The page clearly states that identity does not complete financial setup.
4. Display name and effective-from date are required.
5. Optional legal name, birth date, residency country and tax jurisdiction may remain blank.
6. An optional residency country accepts two letters and is normalized to uppercase.
7. Dates use explicit ISO `YYYY-MM-DD` input and invalid formats cannot be submitted.
8. A successfully created person appears in the list with each value under the correct header.
9. People from another household do not appear after switching household context.
10. Empty, unauthorized and refreshed list responses do not produce table evaluation errors.
11. No income, expenses, property, timeline, retirement or scenario workflow is present.
12. Home, Households, People and Settings remain usable at desktop and narrow mobile widths.

Record the Appsmith version, browser, viewport sizes and results before merging.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required imported pages: Home, Households, People and Settings.
- Appsmith structural tests: 17 passed.
- Generated export drift: none.
- Country or tax-jurisdiction defaults in people creation: none.
- People table column identities: unique and complete for every column.
- Persistent credentials or personal defaults: none.
- Backend regression suite: 107 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login. They must be completed before merging the Phase 10C PR.
