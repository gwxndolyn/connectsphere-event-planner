# ConnectSphere Event Planner — Frontend

React 19 + Vite (JavaScript).

## Prerequisites

- Node 20+

## Setup

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL if the backend isn't on localhost:8080
```

## Run the app

```bash
npm run dev
```

Opens on `http://localhost:5173`. The home page calls the backend's
`/api/events/health` endpoint (see `src/features/event/EventHealthCheck.jsx`)
to confirm the frontend/backend connection is working.

## Build

```bash
npm run build
```

## Lint

```bash
npm run lint
```

## Folder layout

- `src/features/<domain>/` — feature-scoped components, one folder per backend domain
  (event, venue, equipment, registration, notification)
- `src/components/` — shared UI components
- `src/api/` — API client (`client.js` wraps `fetch`, base URL from `VITE_API_BASE_URL`)
