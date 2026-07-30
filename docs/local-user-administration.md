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

The final active global administrator cannot be disabled or demoted. Disabled users cannot log in
or receive reset links.

## Manual review

1. Bootstrap or sign in as a global administrator and retain the cookie jar and CSRF token.
2. `POST /api/v1/admin/users` and confirm the temporary password appears in that response.
3. `GET /api/v1/admin/users` and confirm the account appears without any password or token.
4. Sign in with the temporary password and confirm ordinary APIs require a password change.
5. Change the password, then confirm the account can use APIs allowed by its household membership.
6. Issue `/password-reset`, confirm the prior session stops working, and consume the returned token.
7. Confirm a second use of that token fails.
8. Try to disable or demote the only active administrator and confirm the API returns `409`.
