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
