# Adding a purchase-cost provider

Implement `PurchaseProvider` from `app.purchases.providers.base` and register an instance or class:

```toml
[project.entry-points."household_financial_planner.purchase_providers"]
my_country = "my_purchase_package:provider"
```

Providers own their JSON settings validation and return generic named cost components, assumptions
and warnings. Shared purchase services do not interpret country settings or infer a provider from
currency, jurisdiction or location. Australia is the bundled scaffold in
`app.purchases.providers.australia`; another provider requires no shared schema or service edits.
