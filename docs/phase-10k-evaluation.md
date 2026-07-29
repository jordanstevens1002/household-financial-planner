# Phase 10K evaluation — dashboard and polish

## Scope

Phase 10K completes the Version 1 Appsmith application with a useful household overview and
maintained country/currency selection. The dashboard composes existing FastAPI results; it does not
implement financial formulas in Appsmith.

FastAPI exposes authenticated ISO country and currency reference endpoints backed by `pycountry`.
Country labels include a flag, name and two-letter code. Currency labels include the three-letter
code and name. No country, jurisdiction or currency is inferred from another field.

## Automated acceptance

- Reference endpoints return sorted ISO data and tested Australian examples without making those
  examples defaults.
- The Appsmith export uses selectors rather than free-text household currency/jurisdiction fields.
- The dashboard uses the backend cash-flow response for monthly income, expenses and surplus.
- Dashboard actions safely use the health endpoint before a household is selected, avoiding
  invalid household-ID requests during initial load.
- Property and timeline dashboard tables guard response shapes.
- Every widget remains within the 64-column canvas.
- Existing progressive layout non-overlap tests continue to pass.
- Export regeneration, the full Python 3.14 quality suite, migrations and Docker health pass.

## Manual acceptance

Test in edit mode and again after deployment:

1. Open Home with no selected household and confirm it shows setup guidance without debugger errors.
2. Open Households and confirm currency is an unselected searchable dropdown.
3. Confirm national jurisdiction is optional and shows flag, country name and code.
4. Create a non-Australian household and verify its selected values persist in the household table.
5. Add a person and confirm tax residency uses the same professional country presentation.
6. Populate income, expense, property, retirement, timeline and scenario records.
7. Return Home and verify counts match their source pages.
8. Confirm monthly income, expenses and surplus match the Cash flow page for today's date.
9. Confirm property values/debts preserve `Not recorded` instead of inventing zero.
10. Confirm only enabled planned/projected events appear in the upcoming-events table.
11. Narrow the browser to a mobile-width review and confirm content remains operable without
    duplicated navigation or overlapping controls.
12. Repeat the Home and selector checks in the deployed application.

## Evaluation metrics

- Appsmith evaluation errors in the happy path: zero.
- Country or currency defaults: zero.
- Financial formulas duplicated in Appsmith: zero.
- Dashboard cash-flow variance from the backend response: zero.
- Record-count variance from source lists: zero.
- Widgets outside the canvas: zero.
- Progressive-section overlaps: zero.
- Automated suites and CI checks: 100% passing.
