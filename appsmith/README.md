# Appsmith application

`household-financial-planner.json` is the importable Appsmith Community Edition application. Phase
10D adds person selection, dated recurring income sources, and provider-backed or manual tax
settings to the tested household and people foundation. Installed tax providers and their supported
years come from the backend registry; the frontend does not assume Australia or any other country.
Phase 10D.1 removes duplicate person selection, separates the income and tax workflows, and places
raw provider JSON behind an explicit Advanced mode. Phase 10E adds progressive household-expense
and dated cash-flow-summary sections without adding duplicate household selection or navigation.
Phase 10F adds property setup from either a current position or known purchase history. Current
value and total property debt remain explicitly unrecorded when only purchase history is known.
Phase 10G adds dated ownership interests and property-linked loan records. A property may have no
loans, one loan or multiple separate components without silently creating loan assumptions.
Effective repayments are included automatically in household cash flow. Advanced dated
responsibility settings may attribute a repayment to people without duplicating or changing it.
Phase 10H adds household or person-linked retirement accounts, dated contribution profiles and
backend-calculated projections. Account types and optional providers are discovered from the API;
raw provider settings remain behind Advanced mode.
Phase 10I adds a filtered household timeline using the backend's observed, planned and projected
classifications and quality flags. Event payload JSON is available only in Advanced mode.
Phase 10J adds saved custom and inherited scenarios, country-neutral metric templates, dated
assumptions, baseline calculations and side-by-side comparisons. Scenario calculations do not
change household records; multi-metric baseline JSON remains behind Advanced mode.
Phase 10K adds a household dashboard using backend-calculated cash flow, property positions,
upcoming plans and cross-flow record counts. Household currency, national jurisdiction and person
tax-residency choices use maintained API reference data with ISO labels and country flags; no
country or currency is selected implicitly.
The application is generated deterministically by `generate_app.py`; edit the generator rather than
the JSON.

## Import locally

1. Start the stack with `docker compose up --build` and open `http://localhost:8080`.
2. From the Appsmith home screen, select **Create new** and then **Import**.
3. Import `appsmith/household-financial-planner.json`.
4. Open **Settings** in the imported application. For local testing, enter a development subject
   only when the API has `ALLOW_DEVELOPMENT_AUTH=true`. For a production-style test, enter a valid
   API bearer token instead.
5. Save the settings and select **Test API connection**.
6. Open **Households** to create a household or select an existing one.
   Currency is required; national jurisdiction is optional. Both use maintained dropdown data.
7. Open **People** to add and list identity records for the selected household.
8. Select a person and open **Person finances** to record income and tax settings.
9. Open **Cash flow** to add household expenses and calculate an explicitly dated position.
10. Open **Properties** to add a current-position snapshot or record a historical purchase.
11. Select a property to record dated ownership and zero, one or multiple actual loans.
12. Open **Retirement** to add an account, record dated contributions and calculate a projection.
13. Open **Timeline** to review provenance, add an explicitly classified event and manage plans.
14. Open **Scenarios** to save a custom or template-based possibility, add dated assumptions,
    calculate it and compare it with another saved scenario.
15. Click **Deploy** before checking the normal launched application; edit mode and published mode
   use different Appsmith snapshots.
16. Return to **Home** and confirm the household overview matches the records and backend cash-flow
    result entered in the preceding flows.

No bearer token, development identity, email address, household ID or financial value is stored in
the committed export. Appsmith stores bearer tokens and development identities for the current
browser session only. The selected household ID and display name are persisted in that browser so
the same household can be restored later. After connection details are saved in a new session, the
application verifies that the authenticated user can still access that household and refreshes its
display name. The selected person is also remembered until the household changes. An unavailable
household selection is cleared; no household or person data itself is copied into the export.

Regenerate and test the export with:

```bash
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
```

The REST actions use `http://api:8000`, the Docker Compose service address reachable from the
Appsmith container. Do not change it to `localhost`: from inside Appsmith, `localhost` refers to the
Appsmith container itself.
