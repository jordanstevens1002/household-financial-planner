# Phase 10D person finances evaluation

Phase 10D is complete only when an authenticated user can select a person, create and revisit dated
income sources, and save either provider-backed or manual tax settings in both Appsmith edit mode
and the deployed application. Household expenses and calculated household cash flow remain Phase
10E work.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Person-scoped finance actions | 100% |
| Hardcoded frontend country, provider, or tax-year choices | 0 |
| Tax providers and supported years sourced from registry API | 100% |
| Distinct v1.93 table column identities | 100% |
| Backend provider-discovery and regression tests | 100% passing |
| Compose and migration validation | Pass |

## Runtime review

Import `appsmith/household-financial-planner.json` into the Appsmith version pinned by Docker
Compose. Confirm all of the following in edit mode and again after **Deploy**:

1. Select a household and an existing person before opening Person finances.
2. Changing household clears the previously selected person.
3. Income types are loaded from active backend lookups rather than frontend constants.
4. A dated taxable recurring income source can be created and returns in the correct table columns.
5. A non-taxable source and optional end date, growth rate, contribution and notes are preserved.
6. Invalid amounts, dates, growth rates and missing material fields cannot be submitted.
7. Automatic tax choices come entirely from `/api/v1/tax-providers`.
8. Provider parameters require valid JSON and are validated by the selected backend provider.
9. Manual annual net income accepts an explicit jurisdiction and tax year even when no provider is
   installed for that jurisdiction.
10. Saved automatic and manual profiles return with the correct jurisdiction, year, mode and dates.
11. Switching people isolates each person's income sources and tax profiles.
12. No household expense or household cash-flow workflow is included yet.
13. Home, Households, People, Person finances and Settings remain usable at desktop and narrow
    mobile widths.

Record the Appsmith version, browser, viewport sizes and results before merging.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required imported pages: Home, Households, People, Person finances and Settings.
- Appsmith structural tests: 23 passed.
- Generated export drift: none.
- Hardcoded frontend country, provider or tax-year choices: none.
- Tax-provider registry endpoint: authenticated live request returned the installed provider and
  supported-year metadata.
- Person, income and tax table column identities: unique and complete for every column.
- Backend regression suite: 108 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login. They must be completed before merging the Phase 10D PR.
