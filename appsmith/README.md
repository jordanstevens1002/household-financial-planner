# Appsmith application

`household-financial-planner.json` is the deterministic, importable Appsmith Community Edition
application. It provides household selection and restoration, people and finances, cash flow,
properties and loans, retirement projections, timeline events, saved scenarios and a household
dashboard. Installed tax, retirement and purchase providers are discovered from FastAPI; the
frontend does not assume a country.

Raw provider settings, event payloads and exceptional tax-jurisdiction overrides remain behind
explicit Advanced controls. Financial calculations stay in FastAPI.

## Import locally

1. Start the stack with `docker compose up --build` and open `http://localhost:8080`.
2. From the Appsmith home screen, select **Create new** and then **Import**.
3. Import `appsmith/household-financial-planner.json`.
4. Open **Settings**. For local testing, enter a development subject only when the API has
   `ALLOW_DEVELOPMENT_AUTH=true`. For production, enter a valid bearer token.
5. Save the settings and select **Test API connection**.
6. Open **Households** to create or select a household.
7. Use **People**, **Person finances**, **Cash flow**, **Properties**, **Retirement**, **Timeline**
   and **Scenarios** to populate the household.
8. Return to **Home** to review the backend-calculated overview.
9. Click **Deploy** before testing the normal launched application. Edit and deployed modes use
   different Appsmith snapshots.

### Why import is currently manual

Appsmith requires an initial administrator account and workspace before an application can be
imported. Its documented Community Edition workflow exposes import through the authenticated
workspace interface; using Appsmith's private internal endpoints would couple this project to
unstable implementation details and require storing administrator credentials. Git-connected
applications also need a one-time authenticated connection. For v1.0.0 the supported installation
therefore keeps this one-time import manual; a later installer may automate it when Appsmith offers
a stable supported provisioning interface suitable for self-hosted Community Edition.

No bearer token, development identity, email address, household ID or financial value is stored in
the committed export. Connection credentials are session-only. The selected household is persisted
in the browser and verified again after new connection details are supplied.

## Regenerate and test

Edit `generate_app.py`, not the generated JSON:

```bash
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
```

REST actions use `http://api:8000`, the Compose service address reachable from the Appsmith
container. From inside Appsmith, `localhost` refers to the Appsmith container itself.
