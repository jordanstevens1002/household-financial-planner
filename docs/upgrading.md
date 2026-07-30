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

The original database migration chain through v1.0.0 does not support downgrades. To reverse the
v1.0.0 upgrade, stop the stack, check out the preceding commit and restore matching pre-upgrade
database and Appsmith backups. Later releases must provide a tested downgrade to the preceding
release unless their release notes explicitly identify an irreversible migration.

Downgrading the local-account persistence migration to the preceding OIDC-only schema preserves
local-only user rows and household memberships by assigning a deterministic
`local-account:<user UUID>` OIDC subject. The older release cannot authenticate those accounts,
and local-only fields such as username and password hash are discarded by the older schema.
Restore the pre-upgrade backup instead when continued local-account access is required.
