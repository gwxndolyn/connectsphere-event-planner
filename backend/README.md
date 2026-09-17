# ConnectSphere Event Planner — Backend

FastAPI (Python 3.12+) REST API, backed by PostgreSQL 16.

## Prerequisites

- Python 3.12+
- PostgreSQL 16 (running locally, or via the `docker-compose.yml` in the repo root)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # adjust DATABASE_URL if needed
```

## Run the app

```bash
uvicorn app.main:app --reload
```

The app starts on `http://localhost:8000`. Health check:

```bash
curl http://localhost:8000/api/events/health
```

Interactive API docs: `http://localhost:8000/docs`.

## Run tests

```bash
pytest
```

## Package layout

Feature-based packages under `app/`:

- `event` — event request, review, status management
- `venue` — venue catalogue, booking, conflict detection
- `equipment` — equipment catalogue, reservation
- `registration` — attendee registration, waitlist
- `notification` — cross-cutting notification service
- `user` — auth, roles
- `core` — shared config, database session, exceptions
