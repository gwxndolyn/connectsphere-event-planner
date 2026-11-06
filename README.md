# ConnectSphere Event Planner

A university scrum project for planning campus events: event requests, venue booking,
equipment reservation, attendee registration, and notifications.

**Git repository:** <https://github.com/gwxndolyn/connectsphere-event-planner> (IS212 G8T4)

Monorepo layout:

- [`backend/`](backend/) — FastAPI (Python 3.12+) REST API
- [`frontend/`](frontend/) — React 19 (Vite, TypeScript) SPA
- [`e2e/`](e2e/) — Playwright end-to-end tests
- [`docs/`](docs/) — [C4 model as built](docs/c4/README.md), [requirements → tests traceability](docs/testing/TRACEABILITY.md), per-story test evidence in [`docs/testing/`](docs/testing/)

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
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Health check: `GET /api/events/health`.

## Running the frontend

```bash
cd frontend
cp .env.example .env
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

# with coverage (what CI runs)
cd backend && pytest --cov=app --cov-report=term-missing
cd frontend && npm run test:coverage

# end-to-end (Playwright): backend running on :8000 against a seeded database
cd e2e && npm ci && npx playwright install chromium && npm test
```

## CI

GitHub Actions runs on every pull request: `backend-ci.yml` (pytest with coverage), `frontend-ci.yml`
(oxlint, Vitest with coverage, typecheck and build), `e2e.yml` (Playwright against a migrated, seeded
backend), `lint-markdown.yml` and `pr-title-check.yml`. What each suite covers, how to add a
test and what to do when one fails: [`docs/testing/README.md`](docs/testing/README.md).

## Demo walkthrough (end-to-end workflow)

After `python -m app.seed`, run the frontend in dev mode (`VITE_DEV_AUTH=true`) and use the **Acting as**
switch in the header to change role:

1. **Organiser**: Event requests → new request → *Save draft* → complete it (tick "attendee registration
   required") → *Submit*.
2. **Coordinator Lead**: assign a coordinator from the Unassigned queue (workload shown).
3. **Coordinator**: open the request → ask for clarification or *Approve*; then *Request venue* (search
   filters by date, time, attendance, location, accessibility, facilities) and add equipment lines.
4. **Venue Staff**: approve or reject pending bookings with a reason (conflicts and setup/turnaround
   buffers are checked); mark a venue unavailable to see affected bookings flagged.
5. **Tech Support**: check equipment availability → approve → reserve; assign support staff.
6. **Safety Officer**: approve the safety review (or request changes).
7. **Coordinator**: readiness list all ✓ → *Confirm event* → *Start preparation* → after it ends,
   *Mark as completed*. Confirming opens registration if the organiser asked for it.
8. **Attendee**: Events board → register → My Events → withdraw.

Every step lands in the relevant people's **Notifications**.

## Demo logins

These accounts are created by `python -m app.seed` (`SEEDED_LOGIN_EMAILS` in
[`backend/app/seed.py`](backend/app/seed.py)). They are demo accounts only, and they all share one password.

| Role | Name | Email (username) |
| --- | --- | --- |
| Event Organiser | Olivia Organiser | `event.organiser@smu.edu.sg` |
| Event Coordinator | Casey Tan | `event.coordinator@smu.edu.sg` |
| Coordinator Lead | Lena Lim | `lead.one@smu.edu.sg` |
| Coordinator Lead | Leo Lee | `lead.two@smu.edu.sg` |
| Venue Staff | Vera Goh | `venue.staff@smu.edu.sg` |
| Technical Support | Terry Ong | `tech.support@smu.edu.sg` |
| Technical Support | Priya Nair | `tech.support2@smu.edu.sg` |
| Safety Officer | Sam Koh | `safety.officer@smu.edu.sg` |
| Coordinator + Venue Staff (two roles) | Morgan Lau | `multi.role@smu.edu.sg` |
| Attendee | Arjun Rao | `arjun.rao.2024@smu.edu.sg` |
| Attendee | Calvin Ng | `calvin.ng.2024@smu.edu.sg` |
| Attendee | Mei Tan | `mei.tan.2024@smu.edu.sg` |
| Attendee | Sofia Lim | `sofia.lim.2024@smu.edu.sg` |

Password for all accounts: is212connectSphere

The multi.role user switches role with the **Role** menu in the header.

## Team Members

| Member | Sprint roles (PO / SM rotate each sprint) |
| --- | --- |
| Calvin Ng | SM Sprint 2; developer Sprint 4 |
| Chloe Goh | PO Sprint 1, SM Sprint 4 |
| Gwendolyn Leong | SM Sprint 1, PO Sprint 4; repository owner |
| Matthew Leong | PO Sprint 2, SM Sprint 3; developer Sprint 4 |
| Nicholas Lo | PO Sprint 3; developer Sprint 4 |

**Sprint 4:** Gwendolyn Leong (PO), Chloe Goh (SM); Calvin Ng, Matthew Leong and Nicholas Lo are developers.

## Product Backlog / Board Link

- Jira project `SCRUM`: <https://smu-team-kk38iw8n.atlassian.net> (exported in the submission's folder 1)
- Development spec (data model, API contracts, test cases, decisions): [`claude_instructions.md`](claude_instructions.md)
