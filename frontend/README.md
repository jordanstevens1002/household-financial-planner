# React frontend

This directory contains the React v2 application. During the parallel migration it
runs on <http://localhost:3000>, while Appsmith remains available on
<http://localhost:8080>.

The current screen is intentionally a foundation preview. Financial workflows are
added only through their tested migration issues; continue using Appsmith for
workflows that have not reached parity.

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

Run all foundation checks with:

```bash
npm audit
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run e2e
```

The production image builds the static application and serves it through Nginx with
SPA history fallback. Same-origin API proxying and generated FastAPI contracts are
introduced by the next migration issue.
