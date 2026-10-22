# ConnectSphere Event Planner

A university scrum project for planning campus events: event requests, venue booking,
equipment reservation, attendee registration, and notifications.

Monorepo layout:

- [`backend/`](backend/) — FastAPI (Python 3.12+) REST API
- [`frontend/`](frontend/) — React 19 (Vite, TypeScript) SPA
- [`e2e/`](e2e/) — Playwright end-to-end tests
- [`docs/`](docs/) — C4 architecture diagrams and ER diagrams

## Prerequisites

- Python 3.12 (pinned in `backend/.python-version`; CI runs the same)
- Node 22+
- PostgreSQL 16 (or Docker, via `docker-compose.yml`)

## Running Postgres

```bash
docker compose up -d postgres
```

## Running the backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Health check: `GET /api/events/health`.

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`.

## Running tests

```bash
# backend (pytest): needs Postgres running
cd backend && pytest

# frontend unit + integration (Vitest): Node 22+, no backend needed
cd frontend && npm test

# end-to-end (Playwright): backend running on :8000 against a seeded database
cd e2e && npm ci && npx playwright install chromium && npm test
```

## CI

GitHub Actions runs on every pull request: `backend-ci.yml` (pytest), `frontend-ci.yml`
(oxlint, Vitest, typecheck and build), `e2e.yml` (Playwright against a migrated, seeded
backend), `lint-markdown.yml` and `pr-title-check.yml`. What each suite covers, how to add a
test and what to do when one fails: [`docs/testing/README.md`](docs/testing/README.md).

## Team Members

- _TODO: add team member names and roles_

## Product Backlog / Board Link

- _TODO: link to Scrum board (e.g. Jira/Trello/GitHub Projects)_
