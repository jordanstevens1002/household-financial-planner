# Phase 10F property-setup evaluation

Phase 10F is complete only when an authenticated household can add and revisit a property from
either a known current position or purchase history in Appsmith edit mode and the deployed
application.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Property list and setup sections overlapping in edit mode | 0 |
| Duplicate household selection or secondary navigation | 0 |
| Property types and statuses sourced from backend lookups | 100% |
| Current value or debt silently inferred for purchase history | 0 |
| Backend regression suite | 100% passing |
| Compose and migration validation | Pass |

## Runtime review

Confirm all of the following in edit mode and again after **Deploy**:

1. Properties is unavailable until a household is selected.
2. The page uses the existing household context and has no second household chooser.
3. Your properties and Add a property are separate progressive sections.
4. Hidden edit-mode widgets occupy separate rows and do not overlap.
5. An empty property list explains how to add the first property.
6. Property type and current use are populated from backend lookups.
7. “Start from today's position” requires a position date, current value and explicit total debt.
8. A debt-free current position requires the user to enter zero; zero is never silently assumed.
9. “Record purchase history” requires purchase date and price and explains that it does not imply
   the property is debt-free.
10. Successful creation refreshes the summary, clears the form and returns to the property list;
    failure preserves entered values.
11. The list uses friendly type, use and setup labels.
12. Current value and total property debt display the property currency.
13. Purchase-history-only current value and debt display “Not recorded”.
14. Existing baseline values remain available after refresh and application restart.
15. The page remains usable at desktop and narrow mobile widths.

## Recorded automated results

- Appsmith version: v1.93, pinned by Docker Compose and reported healthy.
- Required pages: Home, Households, People, Person finances, Cash flow, Properties and Settings.
- Appsmith structural tests: 39 passed.
- Generated export drift: none.
- Property list and setup edit-mode overlap: none.
- Duplicate household selection or navigation: none.
- Property types and statuses: backend lookup actions only.
- Missing current value and debt silently inferred: none.
- Backend regression suite: 111 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Alembic: at head with no new upgrade operations detected.
- Compose configuration and live API readiness: passed.

Import and edit/deploy interaction checks remain reviewer actions because they require the local
Appsmith login.
