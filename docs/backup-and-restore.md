# Backup and restore

Back up both PostgreSQL and Appsmith. A database-only backup does not contain the imported Appsmith
application, users or local Appsmith configuration.

## PostgreSQL backup

Create a compressed logical backup:

```bash
docker compose exec -T postgres pg_dump \
  -U household_finance \
  -d household_finance \
  --format=custom > household-finance.dump
```

Store the dump encrypted and outside the Docker host. Adjust the database user and name when your
`.env` uses different values.

## Appsmith volume backup

Stop writes before archiving the named volume:

```bash
docker compose stop appsmith
docker run --rm \
  -v financial_planner_appsmith_stacks:/source:ro \
  -v "$PWD":/backup \
  alpine tar -czf /backup/appsmith-stacks.tar.gz -C /source .
docker compose start appsmith
```

The Compose project name affects the volume name. Confirm it with `docker volume ls`.

## Restore

1. Stop the application and make a safety copy of the current volumes.
2. Start PostgreSQL and create an empty target database.
3. Restore with `pg_restore --clean --if-exists` only when intentionally replacing that database.
4. Restore the Appsmith archive into an empty Appsmith volume.
5. Start the API, allow forward migrations to complete, and check `/health/ready`.
6. Verify household access, counts and representative calculations before resuming normal use.

Test this procedure regularly. An untested backup should not be considered recoverable.
