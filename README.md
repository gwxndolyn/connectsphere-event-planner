# ConnectSphere Event Planner

A university scrum project for planning campus events: event requests, venue booking,
equipment reservation, attendee registration, and notifications.

Monorepo layout:

- [`backend/`](backend/) — Spring Boot (Java 17, Maven) REST API
- [`frontend/`](frontend/) — React (Vite, JavaScript) SPA
- [`docs/`](docs/) — C4 architecture diagrams and ER diagrams

## Prerequisites

- Java 17
- Node 20+
- Maven

## Running the backend

```bash
cd backend
mvn spring-boot:run
```

Runs on `http://localhost:8080`. Health check: `GET /api/events/health`.

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`.

## Running tests

```bash
# backend
cd backend && mvn test

# frontend
cd frontend && npm test
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) builds and tests both the backend (Maven)
and frontend (npm) on every push and pull request.

## Team Members

- _TODO: add team member names and roles_

## Product Backlog / Board Link

- _TODO: link to Scrum board (e.g. Jira/Trello/GitHub Projects)_
