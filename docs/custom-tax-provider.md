# Adding a tax provider

Tax is an extension point. The income and cash-flow services do not import a country implementation
or interpret country-specific settings. Australia is included as a working example in
`api/app/income/tax/australia.py`.

An external provider implements the `TaxProvider` and `TaxEngine` protocols from
`app.income.tax.base`. A provider is responsible for:

- its jurisdiction code and supported tax years;
- mapping a calendar date to the jurisdiction's applicable tax year;
- validating and normalising the values in `settings.parameters` through the engine's
  `validate_parameters` method;
- selecting a versioned engine; and
- returning generic named components, totals, warnings, and a ruleset version.

Register the provider from the external package's `pyproject.toml`:

```toml
[project.entry-points."household_financial_planner.tax_providers"]
my_country = "my_tax_package:provider"
```

`provider` may be a provider instance or provider class. Install that package in the API container
and restart the service; the registry discovers it at startup. Installed providers execute as
trusted application code, so self-hosters should review a provider before including it in an image.

Automatic profiles use a generic settings shape:

```json
{
  "calculation_mode": "AUTOMATIC",
  "parameters": {
    "country_specific_option": true
  }
}
```

Manual net-income profiles do not require a provider, which lets a household use an unsupported
jurisdiction without waiting for an automatic engine. Every provider and financial year must have
boundary tests and documented assumptions before it is considered complete.
