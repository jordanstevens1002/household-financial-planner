# Household Financial Planner API

FastAPI service for household financial records, projections and scenario calculations.

The API targets Python 3.14 and uses SQLAlchemy, Alembic, PostgreSQL, Pydantic Settings and
Structlog. Run the tested container from the repository root:

```bash
docker compose up --build api
```

Interactive API documentation is available at `http://localhost:8000/docs`. The complete backend
quality suite runs from the Dockerfile's `test` target as documented in the root README.
