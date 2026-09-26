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
- Node 20+
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
# backend (pytest)
cd backend && pytest

# frontend build/typecheck
cd frontend && npm run build

# end-to-end (Playwright)
cd e2e && npm install && npm test
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs the backend (pytest), frontend
(TypeScript build/lint) and Playwright E2E suite on every push and pull request.

## Team Members

- _TODO: add team member names and roles_

## Product Backlog / Board Link

- _TODO: link to Scrum board (e.g. Jira/Trello/GitHub Projects)_
