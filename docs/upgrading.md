# Upgrading

## Before upgrading

1. Read [CHANGELOG.md](../CHANGELOG.md) and the target GitHub Release notes.
2. Back up PostgreSQL and Appsmith using [Backup and restore](backup-and-restore.md).
3. Record the currently deployed Git commit or release tag.
4. Test the target release against a restored copy of your data.

## Upgrade

Check out the desired release and rebuild:

```bash
git fetch --tags
git checkout v1.0.0
docker compose pull
docker compose up -d --build
```

The API runs `alembic upgrade head` before starting. Monitor:

```bash
docker compose logs api
docker compose ps
```

Confirm the readiness endpoint, authentication, Appsmith connection and representative household
calculations.

## Rollback

Database downgrades are not supported. If an upgrade must be reversed, stop the stack, check out
the previous application version and restore the pre-upgrade PostgreSQL and Appsmith backups.
