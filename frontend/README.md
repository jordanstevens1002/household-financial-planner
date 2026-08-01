# React frontend

This directory contains the React v2 application. During the parallel migration it
runs on <http://localhost:3000>, while Appsmith remains available on
<http://localhost:8080>.

The React application currently provides local authentication, password recovery
and global user administration. Financial workflows are added only through their
tested migration issues; continue using Appsmith for workflows that have not
reached parity.

## Docker

From the repository root:

```bash
docker compose up --build frontend
```

Open <http://localhost:3000>. The container health endpoint is
<http://localhost:3000/health>.

## Local Node development

Node 24 and npm 11 are required. The Node major is recorded in `.nvmrc` and the
complete dependency graph is committed in `package-lock.json`.

```bash
npm ci
npm run dev
```

Vite prints the development URL, normally <http://localhost:5173>.
Requests under `/api` are proxied to `http://127.0.0.1:8000` by default. Set
`VITE_API_PROXY_TARGET` when the API is available elsewhere.

Run all foundation checks with:

```bash
npm audit
npm run contracts:check
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium firefox
npm run e2e
```

Run only the browser you are actively checking with `npm run e2e -- --project
chromium` or `npm run e2e -- --project firefox`.

The production image builds the static application and serves it through Nginx with
SPA history fallback and a same-origin proxy to the Docker `api` service.

## API contracts

`openapi.json` is exported deterministically from FastAPI and
`src/api/schema.d.ts` is generated from it. Both files are committed but must never
be edited manually. From the repository root, regenerate them with:

```bash
docker compose run --rm api python scripts/export_openapi.py - > frontend/openapi.json
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD/frontend:/app" -w /app node:24-alpine npm run generate:api
```

The CI drift checks are authoritative. The request client sends cookies only through
the browser's `include` mode, supports in-memory CSRF values for mutations, and
normalises API failures with their `X-Request-ID`.
