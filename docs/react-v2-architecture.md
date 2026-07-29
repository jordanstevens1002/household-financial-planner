# React v2 architecture contract

This document defines the boundary for replacing Appsmith with the React v2
application. Changes to these decisions require an issue explaining the reason and
the effect on the migration. The work is tracked by
[epic #58](https://github.com/jordanstevens1002/household-financial-planner/issues/58).

## Product and support boundary

- React v2 is a desktop-focused SPA supporting viewport widths of 1024 px and above.
  Mobile optimisation is outside the v2.0 scope.
- React must expose every current FastAPI capability. Financial calculations remain
  exclusively in FastAPI; formulas, provider rules and projections are not
  reimplemented in the browser.
- Country-specific behaviour stays behind backend provider contracts. Australia is
  a bundled provider example, never a frontend default.
- React and Appsmith run in parallel until issue #54 passes. React uses port 3000
  and Appsmith stays on 8080 during migration. Issue #56 removes Appsmith and moves
  React to port 8080.

## Selected stack

| Concern | Contract |
| --- | --- |
| Runtime | Node 24 and npm with a committed `package-lock.json` |
| Build | Vite with a production Nginx image |
| Language | React with strict TypeScript |
| Components | MUI with one application theme |
| Routing | TanStack Router with typed lazy routes and error boundaries |
| Server state | TanStack Query |
| Forms | React Hook Form with Zod schemas |
| Component tests | Vitest, Testing Library and MSW |
| Browser tests | Playwright against the real Docker stack |

The browser uses same-origin `/api` routes. Vite proxies `/api` in development and
Nginx proxies it in production. API types are generated deterministically from the
FastAPI OpenAPI document and CI rejects contract drift.

## Authentication transition

OIDC bearer tokens and `X-Development-Subject` remain only while the two frontends
coexist. Issues #30–#36 introduce local accounts, server-side sessions,
administration and legacy identity mapping. Issue #55 removes both old
authentication paths after all identities are mapped or an administrator explicitly
accepts the loss of login access.

React never stores passwords, bearer tokens, session cookies or CSRF tokens in local
storage. The server owns sessions and sends the `hfp_session` cookie as HttpOnly,
SameSite=Lax and Path=/. React obtains session and CSRF state through the
authentication API and supplies `X-CSRF-Token` on cookie-authenticated mutations.

Global account roles and household membership roles are separate. A global
administrator has no access to household financial data without membership.

## Frontend directory contract

Issue #27 establishes these boundaries:

```text
frontend/
├── e2e/                  # Playwright tests and fixtures
├── public/               # Untransformed static files
├── src/
│   ├── api/              # Generated types, client and query keys
│   ├── app/              # Providers, router, shell and startup
│   ├── components/       # Shared presentation components
│   ├── features/         # Domain routes, forms, queries and tests
│   ├── test/             # Shared Vitest and MSW setup
│   └── utils/            # Country-neutral formatting and pure helpers
├── nginx/                # Production SPA and API proxy configuration
└── package.json
```

Features may import from `api`, `components` and `utils`. Shared folders do not
import from features. Features do not reach into another feature's internals;
deliberately shared behaviour has a public entry point. Generated files are never
edited by hand.

## Routes

| Route | Purpose | Owner |
| --- | --- | --- |
| `/` | Household overview and next actions | #53 |
| `/households` | Create, select and restore a household | #38 |
| `/households/$householdId/memberships` | Household access | #38 |
| `/people` | Household people | #40 |
| `/people/$personId/finances` | Income, tax and cash-flow inputs | #41, #42 |
| `/cash-flow` | Household-calculated cash flow | #42 |
| `/properties` | Property list and creation | #43 |
| `/properties/$propertyId` | Position, value and history | #43 |
| `/properties/$propertyId/ownership` | Dated ownership | #44 |
| `/properties/$propertyId/rental` | Rental details and cash flow | #44 |
| `/properties/$propertyId/loans` | Loans and responsibility | #45 |
| `/loans/$loanId/analysis` | Schedule, targets and refinancing | #46 |
| `/purchases` | Purchase planning and feasibility | #47 |
| `/retirement` | Accounts, contributions and projections | #48, #49 |
| `/timeline` | Events and resolved property state | #50 |
| `/scenarios` | Saved scenarios and comparisons | #51, #52 |
| `/admin/users` | Local account administration | #34 |
| `/admin/legacy-identities` | OIDC identity mapping | #36 |
| `/settings` | Health, account and reference information | #39 |

Authenticated routes restore the intended location after login. Every new session
revalidates access to restored household, person and property selections.

## State and forms

- FastAPI is the durable source of truth. TanStack Query owns fetched state and
  invalidation after mutations.
- The URL owns navigable context. Local storage may contain only the most recently
  selected household, person and property IDs.
- Form state stays in React Hook Form. Zod gives immediate feedback, while FastAPI
  remains authoritative and its validation errors are displayed.
- Dates and money cross the API exactly as generated contracts define them.
- Empty, loading, validation, unauthorised and server-error states are explicit.
  Errors expose the request ID for log correlation without exposing internals.

## Advanced mode

Ordinary workflows use labelled controls from shared or provider-defined field
metadata. Raw provider settings, baseline JSON, event JSON, specialist
tax-jurisdiction overrides and atypical repayment responsibility are hidden behind
a clearly labelled **Advanced** control.

Advanced mode is progressive disclosure, not a duplicated form. Toggling it must
not discard entered values. JSON is validated before submission, and invalid
advanced input cannot silently fall back to a default.

## Completion and release gates

Every issue includes proportionate backend tests where APIs change, React
unit/component tests and a focused manual review script. MSW supplies deterministic
fixtures; Playwright verifies critical flows against Docker.

Before cutover:

1. The [API parity matrix](react-v2-api-parity.md) is complete.
2. Issue #54 passes browser, accessibility, coverage, Lighthouse and bundle gates.
3. Legacy identities are mapped or loss of login access is explicitly accepted.
4. `appsmith-quality` is removed from the `develop` ruleset immediately before
   issue #56 and from `main` immediately before the release PR.
5. Fresh install, backed-up v1 upgrade, mapping and rollback rehearsals pass.
6. Issue #57 updates versions and release documentation before tagging `v2.0.0`.

The Appsmith volume is never deleted automatically. The v1.0.0 tag and Git history
remain the recovery source after Appsmith leaves the active tree.
