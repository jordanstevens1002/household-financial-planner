# Household Financial Planner

Household Financial Planner is an open-source, self-hosted application for exploring how a household's financial position may change over time. It is intended to combine dated financial records, assumptions, planned events and scenarios so users can inspect historical and projected cash flow, property, debt, income and retirement positions.

## Project status

The project is in its initial setup phase. The detailed product and architecture specification is available in [PROJECT_PLAN.md](PROJECT_PLAN.md).

The planned stack is:

- Python 3.14 and FastAPI for APIs and financial calculations;
- PostgreSQL, SQLAlchemy and Alembic for durable data and migrations;
- Appsmith Community Edition for the initial user interface; and
- Docker Compose for self-hosted deployment.

## Delivery approach

Development is divided into reviewed phases. Each implementation phase is completed on its own branch and pull request, with `main` remaining releasable.

Tests and evaluation metrics are mandatory in every phase. A phase is not complete unless its automated tests pass and its documented acceptance and quality thresholds are met.

## Principles

- Household financial data remains isolated and self-hosted by default.
- Historical facts, user estimates, planned events and projections remain distinguishable.
- Financial calculations live in the tested backend, not in UI formulas.
- The application provides planning estimates, not financial, tax, legal or lending advice.
- No real or assumed household financial data is seeded automatically.

## Running the application

Copy `.env.example` to `.env`, replace every placeholder secret and OIDC value, then run:

```bash
docker compose up --build
```

The API is served at `http://localhost:8000` and Appsmith at `http://localhost:8080`.
Development authentication remains disabled unless `ALLOW_DEVELOPMENT_AUTH=true` is set explicitly.

Application configuration is loaded from environment variables through `pydantic-settings`.
API logs are structured JSON by default; set `LOG_FORMAT=console` for local human-readable
output and use `LOG_LEVEL` to select `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`.
Every API response includes an `X-Request-ID`, which is also attached to its request log.

Phase 3 adds a dated financial-event engine and unified household timeline. Event records use
explicit observed, planned or projected classification; planned events can be moved or toggled
without rewriting observed history. Property state can be resolved at an arbitrary date from the
latest applicable baseline plus deterministically ordered enabled events. Interactive API
documentation is available at `http://localhost:8000/docs`.

Phase 4 adds household-scoped loans, optional split-loan groups, dated loan events, offsets,
redraw, atomic refinancing, amortisation schedules, interest comparisons, and configurable loan
goals. Loan assumptions such as currency, opening balance/date, rate, repayment frequency,
interest method and interest-only status remain explicit rather than jurisdictional defaults.

Phase 5 adds dated rental portions and property expenses with status-driven cash-flow reporting.
A household can model a whole rented home or named portions such as a room, granny flat, or half
of a duplex while still living in the rest of the property. The product remains focused on clear
personal decisions for a small household property setup, not professional property management.

Phase 6 adds multiple dated income sources per person, dated household expenses, manual or
automatic net-income planning, and annual/monthly household cash flow. The initial Australian
tax estimator is explicitly versioned for 2025–26, rejects unsupported years, and reports its
limitations; estimates are for planning and are not tax advice.

## Contributing

Contribution guidance, security reporting and the full development workflow will be added as the implementation foundation is established.

## Licence

This project will be released under the GNU General Public License v3.0. The licence file will be included before implementation code is accepted.
