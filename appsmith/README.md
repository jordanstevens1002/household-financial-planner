# Appsmith application

`household-financial-planner.json` is the importable Appsmith Community Edition application for
Phase 10. It is generated deterministically by `generate_app.py`; edit the generator rather than
editing the JSON by hand.

## Import locally

1. Start the stack with `docker compose up --build` and open `http://localhost:8080`.
2. From the Appsmith home screen, select **Create new** and then **Import**.
3. Import `appsmith/household-financial-planner.json`.
4. Open **Settings** in the imported application. For local testing, enter a development subject
   only when the API has `ALLOW_DEVELOPMENT_AUTH=true`. For a production-style test, enter a valid
   API bearer token instead.
5. Save the settings, then use **Onboarding** to create or select a household.

No bearer token, development identity, email address, household ID or financial value is stored in
the committed export. Appsmith stores bearer tokens and development identities for the current
browser session only; the selected household may persist locally so a user can return to it.

Regenerate and test the export with:

```bash
python3 appsmith/generate_app.py
python3 -m unittest discover -s appsmith/tests -v
```

The REST actions use `http://api:8000`, the Docker Compose service address reachable from the
Appsmith container. Do not change it to `localhost`: from inside Appsmith, `localhost` refers to the
Appsmith container itself.
