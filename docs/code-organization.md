# Code organization

The backend uses domain-oriented packages. A domain keeps its API router, request/response schemas,
calculations, and optional provider integrations together. The test tree mirrors the application
tree so related behaviour is easy to find.

```text
api/
├── app/
│   ├── core/             authentication, settings, database, dependencies, logging
│   ├── households/       households, memberships, people, lookups
│   ├── properties/       properties, valuations, ownership, baselines
│   ├── events/           financial events and timeline resolution
│   ├── loans/            loan routes, schemas, and calculations
│   ├── rental/           rental and property-expense cash flow
│   ├── income/           income and household cash flow
│   │   └── tax/          tax contracts, registry, and bundled examples
│   ├── retirement/       retirement routes, schemas, calculations, and providers
│   ├── purchases/        purchase routes, schemas, calculations, and providers
│   ├── scenarios/        scenario routes, schemas, calculations, and templates
│   ├── main.py           FastAPI composition, middleware, and health checks
│   └── models.py         shared SQLAlchemy metadata and ORM models
└── tests/
    ├── core/
    ├── households/
    ├── properties/
    ├── events/
    ├── loans/
    ├── rental/
    ├── income/
    ├── retirement/
    ├── purchases/
    ├── scenarios/
    └── conftest.py       shared test fixtures only
```

## Placement rules

- Put a new route in its domain's `router.py`, not in `main.py`.
- Put API models in the domain's `schemas.py` and pure calculations in `calculations.py`.
- Keep country or scheme integrations below the owning domain's provider package and expose them
  through its neutral registry.
- Mirror each application domain below `tests/`. Provider tests live beside their owning domain.
- Keep `models.py` shared until model decomposition is planned as a separate migration-aware
  refactor; moving Python declarations must not accidentally change SQLAlchemy metadata.
- Cross-domain imports should use the public domain package path. Avoid compatibility modules at
  old flat paths because they allow the loose structure to return unnoticed.

This structure changes where code lives, not API paths, database names, entry-point group names, or
calculation behaviour.
