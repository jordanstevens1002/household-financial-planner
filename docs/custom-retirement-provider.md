# Adding a retirement provider

Retirement accounts and projections use country-neutral models. An optional provider supplies
jurisdiction or scheme-specific validation, caps, assumptions and warnings without changing the
shared retirement service.

Implement the `RetirementProvider` protocol from `app.retirement.providers.base`, then register an
instance or class from an external package:

```toml
[project.entry-points."household_financial_planner.retirement_providers"]
my_plan = "my_retirement_package:provider"
```

The provider owns its `provider_settings` structure, compatible account types and dated projection
rules. Shared code receives only generic pre-tax and post-tax caps plus human-readable assumptions
and warnings. Install the reviewed provider package in the API image and restart the service.

Australia is the bundled example at `app/retirement/providers/australia.py`. Adding another country
must not require edits to `retirement/router.py`, shared schemas, models or migrations.
