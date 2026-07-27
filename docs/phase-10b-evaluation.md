# Phase 10B household onboarding evaluation

Phase 10B is complete only when an authenticated user can create, list, select and restore a
household in both Appsmith edit mode and the deployed application. People and financial workflows
remain outside this PR.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Household actions using shared runtime auth | 100% |
| Country or currency defaults in household creation | 0 |
| Persistent credential values | 0 |
| Backend regression suite | 100% passing |
| Compose validation | Pass |

## Runtime review

Import `appsmith/household-financial-planner.json` into the Appsmith version pinned by Docker
Compose. Confirm all of the following in edit mode and again after **Deploy**:

1. Enter a development identity or bearer token in Settings and save the connection.
2. An empty household list renders as a table rather than an evaluation error.
3. Household creation requires a name and a three-letter currency.
4. Jurisdiction may be left blank and no country or currency is silently assumed.
5. A successful creation selects the new household and displays it on Home.
6. The created household appears when the list is refreshed.
7. A different listed household can be selected.
8. The selected household is restored after reopening the launched application in the same
   browser.
9. A new private browser session contains no bearer token or development identity.
10. API failure produces a visible error and does not falsely report creation success.
11. Home, Households and Settings remain usable at desktop and narrow mobile widths.
12. No people or financial workflow is present.

Record the Appsmith version, browser, viewport sizes and results before merging.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required imported pages: Home, Households and Settings.
- Appsmith structural tests: 12 passed.
- Generated export drift: none.
- Country or currency defaults in household creation: none.
- Persistent credentials or personal defaults: none.
- Household table columns: explicit and safe for empty, failed and refreshed responses.
- Backend regression suite: 107 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login. They must be completed before merging the Phase 10B PR.
