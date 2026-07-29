# Phase 10G ownership and loans evaluation

Phase 10G is complete when an authenticated household can select an existing property, record
dated ownership interests, and represent zero, one or multiple actual loans in both Appsmith edit
mode and the deployed application.

Version 1 review prioritises functional correctness, persistence and calculation-safe inputs over
pixel-level Appsmith polish.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Ownership and loan records scoped to selected property | 100% |
| Required financial values silently defaulted | 0 |
| Loan repayments requiring duplicate ordinary expenses | 0 |
| Responsibility allocation changing household repayment total | 0 |
| Country or currency inferred by frontend | 0 |
| Backend regression suite | 100% passing |
| Compose and migration validation | Pass |

## Runtime review

Confirm in edit mode and again after **Deploy**:

1. Ownership and Loans remain unavailable until a property is selected.
2. Selecting **Manage selected property** establishes one shared property context.
3. Changing households clears the selected property.
4. Ownership accepts person, household and neutral external owner types.
5. Person ownership requires a person from the current household.
6. Percentage and effective-from date are explicit.
7. Incomplete ownership saves successfully but displays the backend warning.
8. Multiple ownership records remain visible after refresh.
9. A property with no loan shows a valid, explanatory empty state.
10. Adding a loan requires type, name, opening balance/date, interest rate, repayment frequency,
    interest calculation method and repayment type.
11. Currency inherits from the household through the backend rather than a frontend default.
12. Loan term and scheduled repayment may remain unknown rather than receiving silent defaults.
13. A second loan is added as another record and does not replace the first.
14. Loan rows are filtered to the selected property.
15. Effective loan repayments appear automatically and separately in household cash flow.
16. Total expenses equal ordinary expenses plus loan repayments without duplicate entry.
17. Advanced responsibility is optional and requires a selected loan, household person, percentage
    and effective date.
18. A newer responsibility effective date replaces the earlier attribution for reporting.
19. Responsibility allocation does not change the household repayment or surplus.
20. Successful creation refreshes the relevant list and clears the form; failure preserves values.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required pages: Home, Households, People, Person finances, Cash flow, Properties and Settings.
- Appsmith structural tests: 46 passed.
- Generated export drift: none.
- Property, setup, ownership and loan edit-mode section overlap: none.
- Ownership and loan actions scoped to the selected property: 100%.
- Required financial values silently defaulted: none.
- Frontend country or currency inference: none.
- Backend regression suite: 113 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login.
