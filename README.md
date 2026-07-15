# Household Financial Planner

Household Financial Planner is an open-source, self-hosted application for exploring how a household's financial position may change over time. It is intended to combine dated financial records, assumptions, planned events and scenarios so users can inspect historical and projected cash flow, property, debt, income and retirement positions.

## Project status

The project is in its initial setup phase. The detailed product and architecture specification is available in [PROJECT_PLAN.md](PROJECT_PLAN.md).

The planned stack is:

- Python and FastAPI for APIs and financial calculations;
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

## Contributing

Contribution guidance, security reporting and the full development workflow will be added as the implementation foundation is established.

## Licence

This project will be released under the GNU General Public License v3.0. The licence file will be included before implementation code is accepted.
