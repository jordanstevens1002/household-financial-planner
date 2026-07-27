# Phase 10E household cash-flow evaluation

Phase 10E is complete only when an authenticated household can create and revisit dated expenses
and request a backend-calculated cash-flow position for an explicit date in both Appsmith edit mode
and the deployed application.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Expense and summary sections overlapping in edit mode | 0 |
| Duplicate household selection or secondary navigation | 0 |
| Expense categories sourced from backend lookups | 100% |
| Financial summary values calculated in Appsmith | 0 |
| Backend regression suite | 100% passing |
| Compose and migration validation | Pass |

## Runtime review

Confirm all of the following in edit mode and again after **Deploy**:

1. Cash flow is unavailable until a household is selected.
2. The page uses the existing household context and does not show another household chooser.
3. Expenses and Cash-flow summary are separate progressive sections.
4. Hidden edit-mode widgets occupy separate rows and never overlap.
5. An empty expense list explains how to add the first cost.
6. Expense categories come from active backend lookups.
7. An expense may apply to the whole household or one existing household person.
8. Amount, frequency, priority and effective-from date are explicit.
9. Optional end date, annual growth and notes are preserved.
10. Successful creation refreshes the list and clears the form; failure preserves entered values.
11. Tables use friendly frequency, priority, person and tax-method labels.
12. The summary requires an explicit ISO position date.
13. Annual net income, expenses and surplus plus monthly net income, expenses and surplus come from
    the backend response and display the household currency.
14. For dates beyond installed tax schedules, the newest installed schedule is used as a planning
    fallback and the specific fallback is visible in planning notes.
15. Expense changes affect positions only on dates where the expense is effective.
16. The page remains usable at desktop and narrow mobile widths.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required pages: Home, Households, People, Person finances, Cash flow and Settings.
- Appsmith structural tests: 36 passed.
- Generated export drift: none.
- Expense and summary edit-mode overlap: none.
- Duplicate household selection or navigation: none.
- Expense categories: backend lookup action only.
- Summary calculations performed in frontend: none.
- Backend regression suite: 110 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login.
