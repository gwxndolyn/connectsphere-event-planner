# Testing and CI

How ConnectSphere is tested, what runs in CI, and how to add a test. Per-story test cases live beside this file (`US2-venue-search.md`, `US4-booking-decision.md`, `US12-edit-event.md`, `US13-buffers.md`, `US16a-sign-up-log-in.md`, `US17-approve-reject-request.md`, `US16b-role-based-access.md`, `US20-venue-catalogue.md`, `US22-venue-booking.md`, `US28-view-registrations.md`); the Sprint 1 and 2 cases are in `claude_instructions.md` §4.
How ConnectSphere is tested, what runs in CI, and how to add a test. Per-story test cases live beside this file (`US2-venue-search.md`, `US4-booking-decision.md`, `US5-equipment-availability.md`, `US13-buffers.md`, `US14-tech-support-staff.md`, `US16a-sign-up-log-in.md`, `US17-approve-reject-request.md`, `US16b-role-based-access.md`, `US20-venue-catalogue.md`, `US21-venue-calendar.md`, `US22-venue-booking.md`, `US24-multi-venue.md`, `US27-equipment-reservations.md`, `US28-view-registrations.md`); the Sprint 1 and 2 cases are in `claude_instructions.md` §4.

## The four suites

| Suite | Where | Tool | Talks to | What it proves |
| --- | --- | --- | --- | --- |
| Backend | `backend/tests/` | pytest + httpx | A real Postgres (`connectsphere_test`, rebuilt from the migrations every run) | Every API contract, rule and error code in §3; the schema, constraints and seed |
| Frontend unit | `frontend/src/**/*.test.ts(x)` | Vitest + Testing Library, jsdom | Nothing: `fetch` and callbacks are mocked | Helpers (API client, mappers, formatters) and each component on its own |
| Frontend integration | `frontend/src/**/*.integration.test.tsx` | Vitest + Testing Library + MSW | `frontend/src/test/server.ts`, an in-memory fake of the API | Whole flows through the real `App`: screens, hooks and the API client together |
| E2E | `e2e/tests/*.spec.ts` | Playwright, Chromium | The real FastAPI backend on a migrated, seeded Postgres, and the Vite dev server | User journeys in a browser, end to end |

Test IDs (`TC-US2-05`, `TC-US7-14`, …) name the backend tests and appear in frontend and E2E test titles, so `grep TC-US2-05` finds every test for that case.

## Run them locally

```bash
# Backend: needs Postgres
docker compose up -d postgres
cd backend && pytest

# Frontend unit + integration: no backend needed. Node 22+.
cd frontend && npm test            # once
cd frontend && npm run test:watch  # re-runs on save

# E2E: backend running on :8000 against a seeded database; Playwright starts the frontend
cd backend && alembic upgrade head && python -m app.seed && uvicorn app.main:app --port 8000
cd e2e && npm test
```

Reseed (`python -m app.seed`) before rerunning E2E on the same database: `attendee-registration.spec.ts` leaves Calvin's registrations changed, and `equipment.spec.ts` leaves an approved equipment line on Equipment Request Demo, which can't be removed (a reseed empties that event's equipment).

## What CI runs

Every workflow is in `.github/workflows/`. A PR needs all of them green.

| Workflow | Trigger | Steps |
| --- | --- | --- |
| `backend-ci.yml` | Every push and PR | Python 3.12, Postgres 16 service, `pip install -e ".[dev]"`, `pytest` |
| `frontend-ci.yml` | Every push and PR | Node 22, `npm ci`, `npm run lint` (oxlint), `npm test` (Vitest unit + integration), `npm run build` (`tsc -b` + Vite) |
| `e2e.yml` | PRs, pushes to `main`, manual | Postgres 16, `alembic upgrade head`, `python -m app.seed`, uvicorn on :8000, Node 22, Playwright Chromium, `npm test`. Uploads the Playwright report on failure |
| `lint-markdown.yml` | Every push and PR | markdownlint over `**/*.md` (`claude_instructions.md` is ignored) |
| `pr-title-check.yml` | PR opened or edited | Title is `type(scope): subject`, type one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` |

**Versions:** Python 3.12 (`backend/.python-version`) and Node 22 (`.nvmrc`, which both Node jobs read). Vitest 5, jsdom 30 and MSW 3 refuse Node 20, so `frontend/` and `e2e/` set `engines` with `engine-strict`: on Node 20, `npm ci` stops with an engine error. Run `nvm use` at the repo root, then `npm ci`.

## Frontend tests in detail

**Config** is the `test` block in `frontend/vite.config.ts`:

- jsdom environment; `src/test/setup.ts` adds jest-dom matchers and clears the DOM and `localStorage` after each test.
- Fixed `VITE_*` values (`VITE_API_BASE_URL=http://api.test`, ids `organiser-id`, `coordinator-id`, `lead-id`, `venue-staff-id`, `attendee-id`), so a developer's `frontend/.env` never changes a result. `VITE_DEV_AUTH=true` keeps SCRUM-105's dev mode on: without it, `App` shows the login page and `apiClient` sends no identity headers, and the integration tests fail.
- `testTimeout: 15000`, because integration tests type through whole forms and CI runners are slower than a laptop.
- `restoreMocks` and `unstubGlobals`, so a mocked `fetch` never leaks into the next test.

**Shared helpers** in `frontend/src/test/`:

- `fixtures.ts`: `makeEvent`, `makeRegistration`, `makeRegistry` for unit tests.
- `server.ts`: the MSW fake backend. Call `startMockBackend()` at the top of an integration file. It starts the server, empties its in-memory database after each test, and **fails the test on any request it has no handler for** (`onUnhandledFrame: "error"`). Seed state with `seedEvent`, `seedRegistration`, `seedRequest`, `seedClarification`, `seedVenue`, `seedBooking`, `nextSearchResult`; check what the screens sent with `callsTo(method, path)`, which records each call's URL, headers and body. Override one route for an error case with `server.use(http.get(...))`.

**The fake backend copies the API's contracts, not its business rules.** It checks identity headers, returns §3's codes and keeps simple state (register, withdraw, submit), but it isn't FastAPI. **When a §3 contract changes, change `server.ts` in the same PR**, or the integration tests keep passing against the old behaviour; the E2E suite is the only one that catches the two drifting apart. Leave real rules to the backend tests: venue search's fake returns whatever a test queues with `nextSearchResult`, so its integration tests check what the screen sends and shows, not which venues fit.

**Writing a test:**

- Put it next to the file under test. Name it `*.test.ts(x)` for a unit test, or `*.integration.test.tsx` when it renders `App` against the fake backend.
- Query the way a user finds things: `getByRole`, `getByLabelText`, then text. Avoid class names and test ids.
- Drive the UI with `userEvent`, not `fireEvent`.
- Put the TC ID or AC in the test's name when it checks one.
- Times show in Asia/Singapore. Assert the Singapore value, and the suite passes under any `TZ` (try `TZ=America/New_York npm test`).

## E2E tests in detail

Config: `e2e/playwright.config.ts`. It starts the frontend with `npm run dev --prefix ../frontend` (reusing a running one locally, not in CI), runs files in parallel, and retries twice in CI only.

**Specs share one seeded database and run in parallel**, so each spec must be one of two kinds:

1. **Changes seeded rows**: only `attendee-registration.spec.ts`, which runs its own tests serially.
2. **Reads seeded rows it never changes, or creates its own uniquely named rows**: every other spec. New rows get a unique name (`E2E Project Room ${Date.now()}`). Read-only specs assert on named items, never on a count, since another spec may add rows mid-run (see `venue-search.spec.ts`).

A spec that changes seeded data used by another spec will flake. If a journey needs new data, add it to `app/seed.py`.

The seed data E2E relies on: Calvin (`VITE_DEV_ATTENDEE_ID`) confirmed for Tech Talk and the online Supabase talk, and second in the full Design Sprint Bootcamp's queue; the organiser, coordinator and venue staff users; six venues, one inactive; and, five days ahead at 10:00–12:00, a requested and an approved US22 booking and a venue block; and **Venue Booking Demo**, an approved event assigned to the dev coordinator with no seeded booking, which only `venue-booking.spec.ts` and `venue-booking-decision.spec.ts` book. The first withdraws what it books, on windows 60 to 360 days ahead; the second approves or rejects what it books, which can't be undone, so it uses a day 400 to 20,400 days ahead that changes every second.

## When a test fails

- **Every backend test errors at once:** Postgres isn't running.
- **Vitest says "Failed to start forks worker" or times out with no tests run,** or Vite reports an "Invalid package config": OneDrive has evicted `node_modules` to the cloud (this repo lives in OneDrive). Run `rm -rf node_modules && npm ci`. Setting the project folder to **Always keep on this device** stops it happening.
- **An integration test fails with an unhandled request:** the screen called a route `server.ts` doesn't have. Add a handler for it, following the real contract.
- **E2E passes in CI but fails locally around seeded data:** your local rows are stale. Reseed.
- **The E2E job hangs:** it's waiting for the backend's health check; read the "Backend log" step.
