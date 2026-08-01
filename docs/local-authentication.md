# Local authentication API

Local accounts and OIDC operate in parallel during the React migration. Appsmith continues to use
the existing authentication path until the explicit authentication cutover.

Set a random bootstrap secret before starting the API:

```bash
openssl rand -hex 32
```

Store that value in `LOCAL_AUTH_BOOTSTRAP_TOKEN`. Keep `SESSION_COOKIE_SECURE=true` whenever the
application is served over HTTPS. Local HTTP testing must explicitly set it to `false`.

`GET /api/v1/auth/status` reports whether the first administrator still needs to be created.
`POST /api/v1/auth/bootstrap` requires the secret in `X-Bootstrap-Token` and permanently closes
through the supported API after it creates the first local administrator. The bootstrap secret
should then be removed from the deployment environment.

Login and bootstrap responses set an HttpOnly `hfp_session` cookie and a readable `hfp_csrf`
cookie. Browser clients must copy the CSRF value into `X-CSRF-Token` for every
cookie-authenticated mutation. Cookies use SameSite=Lax and Path=/; production cookies are Secure.
Raw session and CSRF tokens are never stored in the database.

Local sessions expire after one idle hour by default and always expire after 12 hours. Failed
logins are temporarily blocked after the configured attempt limit, and blocked responses include
`Retry-After`. Password changes invalidate every other session for the account.

## Legacy identity migration

OIDC identities are captured for migration without copying household financial records into the
identity API. A global administrator can list them through
`GET /api/v1/admin/legacy-identities`; the response includes identity metadata, household names and
roles, mapping status, and the unresolved count used by the eventual authentication cutover.

`POST /api/v1/admin/legacy-identities/{legacy_identity_id}/mapping` maps one identity to either an
existing local account or a newly created standard user account. Mapping copies the identity's
household memberships to the selected account, retaining the strongest role when that account is
already a member. The OIDC user's memberships remain operational during the parallel migration;
the mapping record permanently identifies the target account and administrator who performed the
mapping. A newly created account receives a temporary password once and must change it at first
login.
