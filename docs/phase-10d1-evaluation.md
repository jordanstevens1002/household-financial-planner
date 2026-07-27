# Phase 10D.1 person-finance UX evaluation

This refinement is complete only when the Phase 10D functionality remains intact while the normal
person-finance journey no longer exposes duplicate selection controls or specialist provider JSON.

## Automated thresholds

| Measure | Required |
| --- | --- |
| Appsmith export regeneration | No uncommitted difference |
| Appsmith structural tests | 100% passing |
| Duplicate person-selection controls on Person finances | 0 |
| Raw provider JSON visible in normal mode | 0 |
| Income and tax tables with friendly enum/boolean labels | 100% |
| Existing backend regression suite | 100% passing |

## Runtime review

Confirm the following in edit mode and after deploying the imported application:

1. A person is selected once on People and Person finances opens for that person.
2. **Change person** returns to People; there is no second people table.
3. Income and Tax settings act as separate progressive sections.
4. The empty state in each section explains what to add next.
5. Successful submissions refresh their list and clear the completed form.
6. Failed submissions preserve the entered values and show the backend error.
7. Income frequency and taxable values use friendly labels in the table.
8. Automatic tax settings use provider defaults without requiring JSON.
9. **Advanced mode** is available only in Tax settings and reveals provider JSON.
10. Leaving Advanced mode hides JSON without changing the provider and year selection.
11. Manual net-income settings remain available without an installed provider.
12. The flow remains usable at desktop and narrow mobile widths.

Professional currency and national-jurisdiction dropdowns, including maintained flag presentation,
are recorded for Phase 10K because they require shared reference data and cross-application design.

## Recorded automated results

- Appsmith structural tests: 28 passed.
- Generated export drift: none.
- Duplicate person-selection widgets and actions: none.
- Provider JSON visibility: Advanced mode only.
- Backend regression suite: 108 passed with 92% coverage.
- Ruff, formatting and Mypy: passed in the Python 3.14 test container.
- Docker Compose configuration: passed.
