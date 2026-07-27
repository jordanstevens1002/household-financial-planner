# Appsmith application

`household-financial-planner.json` is the importable Appsmith Community Edition application. Phase
10B adds household creation, listing, selection and browser restoration to the tested Phase 10A
foundation. It is generated deterministically by `generate_app.py`; edit the generator rather than
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
7. Click **Deploy** before checking the normal launched application; edit mode and published mode
   use different Appsmith snapshots.

No bearer token, development identity, email address, household ID or financial value is stored in
the committed export. Appsmith stores bearer tokens and development identities for the current
browser session only. The selected household ID and display name are persisted in that browser so
the same household can be restored later. After connection details are saved in a new session, the
application verifies that the authenticated user can still access that household and refreshes its
display name. An unavailable selection is cleared; no household data itself is copied into the
export.

Regenerate and test the export with:

```bash
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
```

The REST actions use `http://api:8000`, the Docker Compose service address reachable from the
Appsmith container. Do not change it to `localhost`: from inside Appsmith, `localhost` refers to the
Appsmith container itself.
