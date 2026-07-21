# Architecture principles

This document consolidates the priorities established while implementing Phases 1–9. It is a
review checklist for all later work and complements the detailed product plan.

## Household product scope and language

- Build for a household exploring personal decisions across a small property portfolio, typically
  two or three properties. Do not shape workflows around professional property management.
- Prefer casual, understandable terms such as owner and renter. Industry-specific concepts remain
  available only where they are genuinely useful to a household.
- Historical facts, estimates, projections, and scenario changes must remain distinguishable.

## Country and scheme abstraction

- Shared models, schemas, orchestration, and calculations use country-neutral names and contracts.
- Tax, retirement, and purchase rules that vary by country or scheme live behind provider
  interfaces and registries. Providers are selected explicitly; never infer one from currency,
  household jurisdiction, address, or location.
- Built-in country implementations are examples using the same boundary available to external
  packages. Australia is the first bundled example, not a shared-code default.
- New external providers must be installable through the documented Python entry-point groups
  without editing shared services or database structures.
- Currency is explicit at the household boundary and may be overridden by a resource. Currency
  codes describe amounts; they do not select legal, tax, retirement, or purchase rules.

## Explicit financial assumptions

- Inputs that materially change a financial result must be supplied or stored explicitly. Do not
  silently assume a country, interest rate, loan term, income, expenses, borrowing limit, growth
  rate, tax year, contribution cap, or retirement rule.
- Calculation responses list the material assumptions used, warnings, applicable ruleset/provider,
  and currency where relevant.
- Manual inputs remain available when no suitable provider exists. Estimates are planning aids,
  not tax, lending, legal, or financial advice.

## Engineering completion standard

- Python 3.14 is used for the API runtime and quality tooling.
- Environment configuration crosses one typed `pydantic-settings` boundary. Application and
  request logging uses `structlog` with request correlation.
- A change is not complete without proportionate unit, integration, regression, access-control,
  household-isolation, migration, and performance tests. Required tests may not be bypassed.
- Before v1.0, migrations move forward only as a release requirement. Every change proves upgrade
  from the previous schema and checks for Alembic drift; downgrade functions are best-effort only.
- Phase evaluation documents record thresholds and measured results. `main` remains releasable and
  implementation changes are reviewed through ready-for-review pull requests.

## Review questions

Before merging, ask:

1. Does shared code contain a country, scheme, currency, or industry-specific branch or name?
2. Can another provider implement the same capability without changing shared orchestration?
3. Are all financially material defaults visible and intentional?
4. Can a household understand the terminology and the assumptions shown in the result?
5. Are data ownership, historical integrity, tests, metrics, migration, and documentation complete?
