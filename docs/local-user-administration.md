# Local user administration API

Global administrators can list, create, update, disable and reset local accounts through
`/api/v1/admin/users`. This role is separate from household membership: a global administrator
does not gain access to household financial information, and a household owner does not gain
account-administration access.

Creating a user returns a generated temporary password once. Only its Argon2id hash is stored,
the password expires after 24 hours, and the user must change it before using ordinary protected
APIs. An administrator-issued reset returns a single-use path once, expires after 30 minutes and
invalidates the account's existing sessions. Application logs record the acting and affected user
IDs but never the returned password or reset token.

An administrator can disable or demote their own account only by sending
`confirm_self_lockout: true`, and only when another recovery-capable administrator exists. That
other administrator must be active, have a password, have completed their initial password
change, and have non-expired credentials. An administrator awaiting an initial password change
or holding an expired temporary password does not satisfy the safeguard. Disabled users cannot
log in or receive reset links.

## Emergency operator recovery

If no administrator can sign in, use the interactive recovery command from a trusted shell on the
Docker host:

```bash
docker compose exec api python scripts/recover_admin.py
```

The command prompts for the local username and a temporary password. Password entry is hidden and
is never accepted as a command-line argument, which keeps it out of shell history and process
listings. It requires direct access to the API container and database; do not expose it through an
HTTP endpoint or make Docker access available to untrusted users.

Recovery performs one database transaction that:

- reactivates and promotes the selected local account;
- stores a new Argon2id password hash and requires a password change at next login;
- gives the temporary password the configured 24-hour expiry;
- invalidates every existing session and password-reset token for the account; and
- emits the structured `operator_admin_recovery_completed` audit event without the password.

After recovery, sign in with the temporary password and immediately complete the required password
change. Preserve the API container log containing the audit event according to your normal
security-log retention process.
