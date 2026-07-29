# Phase 10J evaluation — saved scenarios

## Scope

Phase 10J exposes the existing scenario API through one Appsmith page. It supports saved custom
scenarios, optional inheritance, discoverable metric templates, dated metric assumptions,
calculation against an explicit baseline and comparison of two scenarios with the unchanged
baseline included.

Scenario calculations are exploratory. They do not update household, person, property, loan,
retirement or timeline records. Templates are discovered from the backend and the UI contains no
country-specific template or financial default.

## Automated acceptance

- Regenerating `appsmith/household-financial-planner.json` produces no diff.
- All Appsmith export tests pass, including:
  - the Scenario page and its eight API actions;
  - persistence and optional inheritance;
  - guarded table-row selection;
  - country-neutral template discovery;
  - dated metric overrides;
  - friendly and Advanced baseline calculation;
  - comparison output containing the unchanged baseline.
- The full FastAPI test suite passes.
- The migration head check and Docker readiness check pass.

## Manual acceptance

Test both Appsmith edit mode and the deployed application:

1. Select a household and open **Scenarios**.
2. Create a custom scenario without entering template dates.
3. Navigate away, return, and confirm the saved scenario remains in the list.
4. Create a second scenario from a metric template and confirm no country is assumed by the UI.
5. Explore the custom scenario and add a dated `annual_expenses` assumption.
6. Calculate it with an explicit as-at date and baseline metric.
7. Compare it with the template scenario and confirm the table shows the current baseline plus both
   scenario results.
8. Turn on Advanced baseline JSON, enter two numeric metrics and repeat the calculation.
9. Switch households and confirm the prior household's selected scenario is cleared.
10. Deploy the application and repeat the save, return and compare flow.

## Evaluation metrics

- Scenario export tests: 100% passing.
- Full backend regression tests: 100% passing.
- Saved scenario round trip: scenario remains available after page navigation in both edit and
  deployed modes.
- Comparison completeness: baseline and both selected scenarios are visible.
- Country assumptions in Scenario template controls: zero.
- Appsmith evaluation errors during the manual happy path: zero.

## Deliberate boundary

Backend templates that operate on a specific event require a target entity. They are not shown in
the ordinary Phase 10J template picker because silently omitting that target would create an
invalid or misleading scenario. A later UI can expose those templates with a friendly entity
selector while retaining the same backend contract.
