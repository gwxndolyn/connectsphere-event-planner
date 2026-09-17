# ConnectSphere Event Planner — E2E

Playwright end-to-end tests against the full stack (frontend + backend).

## Setup

```bash
npm install
npx playwright install --with-deps chromium
```

## Run

Make sure the backend is running (`uvicorn app.main:app` from `backend/`) — Playwright
starts the frontend dev server automatically.

```bash
npm test
```

Set `E2E_BASE_URL` to point at a different frontend host, or `CI=true` to run headless
against an already-running server.
