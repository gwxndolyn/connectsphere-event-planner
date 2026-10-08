# ConnectSphere — Development Spec (Sprint 1 + Sprint 2)
 
**Source of truth:** Jira project `SCRUM` (SPM ConnectSphere) — https://smu-team-kk38iw8n.atlassian.net
**Generated:** 2026-09-19 from Jira issues SCRUM-2, SCRUM-5, SCRUM-6 and their subtasks.
**Updated:** 2026-09-30 for Sprint 2 — US1 Submit Event Request (SCRUM-20) and the Epic 1 groundwork it laid.
**Stack:** FastAPI (Python) backend · Supabase (Postgres) · React/Vite frontend. Sprint 1 screens are still mockups on `mockEvents.ts`; the Event requests screens (US1) call the real API.
 
---
 
## 0. How to use this document
 
This is a **test-case-driven** spec. Every behaviour below traces back to an acceptance criterion written by the team in Jira. Work in this order:
 
1. Read §2 (data model) and §3 (API contracts) — they are proposals, not gospel; if you deviate, say so explicitly.
2. For each story, write the tests in §4 **first**, as failing tests. Test IDs (`TC-US3-01`, `TC-US1-01`, …) are stable references — use them as test function names, e.g. `def test_tc_us3_01_lists_only_confirmed_registration_open_events():`.
3. Implement until the tests pass.
4. Check §5 — the subtask-to-test mapping is the definition of done for each Jira ticket.
5. §6 lists real ambiguities in the acceptance criteria. **Do not silently invent an answer.** Use the stated Sprint 1 default and leave a `# DECISION-PENDING: <id>` comment at the code site.
Anything not in §4 is out of scope for Sprint 1. See §7.
 
**New to the project, or coming back after a break? Start at §1a.** It covers where things stand, how to get everything running, the rules we've learned the hard way, where the code already departs from §2/§3, and the questions still waiting on an answer. Per-ticket status isn't there: Jira and the PR list own that.
 
---
 
## 1. Sprint 1 scope
 
Sprint 1 is the whole of **Epic 3: Event Registration** (SCRUM-22), minus one story.
 
| Jira | Story | Owner | Status |
|---|---|---|---|
| SCRUM-2 | US3 — Register for an Event | Matthew | To Do |
| SCRUM-5 | US11 — View attendee's upcoming registered events | Nicholas | To Do |
| SCRUM-6 | US7 — Withdraw from an Event Registration | Calvin | To Do |
 
`SCRUM-10` (US6 — Join a Waiting List) is in Epic 3 but **not in Sprint 1**. Sprint 1 touches the waitlist only where US3 and US7 force it to: offering a full-event attendee a waitlist place, and passing a freed place to the next person. Build the minimum that satisfies those two, and no waitlist management UI.
 
Everything in Epic 1 (Event Management) and Epic 2 (Venue & Resources) is out of scope — including event creation, approval and venue booking. Sprint 1 therefore **cannot create a confirmed event through the product**, which is why SCRUM-23 (seeded mock events) exists.

### Sprint 2 scope (27 Sep – 11 Oct)

| Jira | Story | Owner (Jira) | Points |
|---|---|---|---|
| SCRUM-20 | US1 — Submit Event Request (Epic 1) | Chloe | 8 |
| SCRUM-10 | US6 — Join a Waiting List (Epic 3) | Gwendolyn | 3 |
| SCRUM-11 | US8 — Request Clarification (Epic 1) | Nicholas | 5 |
| SCRUM-13 | US10 — Assign a Coordinator (Epic 1) | Matthew | 5 |

US1, US8 and US10 move the same event request through one status lifecycle, so SCRUM-40 laid shared groundwork for all three (statuses, request fields, `users` with roles, the `X-User-Id` stub) — see §2 and §3. Status per ticket lives in Jira, not here.
 
---
 
## 1a. Start here
 
Read this before writing code. It holds what the rest of the document can't: how to get the thing running, the rules we've had to learn, where the code knowingly departs from the contract, and what's still undecided.
 
**Per-ticket status does not live here.** Jira owns ticket state; git and the PR list own what merged. Duplicating either goes stale within hours — it already did once, when two of us edited this section on separate branches and produced a file that contradicted itself. Hence: **edit this section only in the PR that changes the code it describes**, and at sprint boundaries for the two summaries below.
 
### Where things stand — mid Sprint 2 (30 Sep)
 
All three Sprint 1 stories have working backends, tested against a real Postgres. **US1 (SCRUM-20) is the first feature built end to end**: schema, API and React screens, with the screens calling the real API. **The Sprint 1 screens still run on `mockEvents.ts`**; wiring them is the top open item (see "What's next" below).
 
| Story | Backend | Mockup | Test cases |
|---|---|---|---|
| SCRUM-2 — register for an event | Done | Done | TC-US3 15/15 |
| SCRUM-5 — view my upcoming events | Done | Done | TC-US11 11/11 |
| SCRUM-6 — withdraw from a registration | Done | Done | TC-US7 15/15 |
| SCRUM-20 — submit event request (US1) | Done | **Real screens, wired to API** | TC-US1 16/16 + 1 E2E |
| SCRUM-11 — request clarification (US8a) | Done: storage (SCRUM-54) + send endpoint (SCRUM-53) | Not started (SCRUM-57) | TC-US8 14/14 |
 
Every endpoint in §3 exists, plus `POST /registrations/{id}/decline` (deviation 3 below). Identity is two stubs: `X-Attendee-Id` for the Sprint 1 routes and `X-User-Id` (role-aware) for the event-request routes. The database is the tables in §2 plus `attendees` and `users`. Backend suite: 110 tests; E2E: 2 tests (health check, US1 journey). **Supabase may lag `main`**: the SCRUM-40 and SCRUM-54 migrations (`20260930_1200_us1_request_schema`, `20261008_1200_us8_clarifications`) must be applied there by the named person — check with `alembic current`.
 
### Get it running
 
```bash
docker compose up -d postgres          # tests and local work need this
 
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # 3.12 exactly; see Environment below
pip install -e ".[dev]"
cp .env.example .env                   # keep DATABASE_URL on localhost
alembic upgrade head                   # create the tables — the seed fails without this
pytest                                 # whole suite, seconds (tests build their own DB)
 
python -m app.seed                     # seven events, attendees, the organiser and a coordinator
uvicorn app.main:app --reload          # http://localhost:8000/docs
 
cd ../frontend
cp .env.example .env                   # REQUIRED: holds VITE_DEV_USER_ID (the seeded organiser)
npm install && npm run dev             # http://localhost:5173 — restart after editing .env
 
cd ../e2e && npm ci && npx playwright install chromium
npm test                               # backend must be running; don't also run npm run dev
```

**Windows (PowerShell):** activate with `.venv\Scripts\activate`; copy with `Copy-Item .env.example .env`. Create `.env` files by copying or in VS Code, not with `echo >` — PowerShell writes UTF-16, which Vite can't read.
 
`/docs` is the quickest way to see the Sprint 1 product work: withdraw a seeded registration from the full event and watch the seat pass to the next person in the queue. The seed script prints the `X-Attendee-Id` and registration ids you need, plus `VITE_DEV_USER_ID` (organiser `6c200a77-b7cc-5fb1-9d51-81a0abeba24b`, deterministic). For US1, open **Event requests** in the app, or call the event-request endpoints in `/docs` with that id in `X-User-Id`. For US8, act as the seeded coordinator (`2aac679a-f014-5437-b43a-d150447a6336`, also deterministic).
 
### When something looks broken
 
- **Every database test errors at once** → Postgres isn't running.
- **`relation … does not exist` against Supabase** → an unapplied migration, not a bug. Compare `alembic current` there with `alembic heads` here.
- **Passes locally, fails in CI** → check Python is 3.12, and see the lockfile note under Environment.
- **The page says "backend unreachable"** → the API isn't running, or your origin isn't in `CORS_ORIGINS`.
- **Event requests says "Set VITE_DEV_USER_ID…"** → `frontend/.env` doesn't exist (only `.env.example` does). Copy it and restart `npm run dev`.
- **CORS errors even on `/api/events/health`** → something else is answering on port 8000 (open the health URL directly; "no Route matched" means another app), or a terminal still has a leftover `CORS_ORIGINS`. Close all terminals and start fresh.
- **`401` on `/api/v1/me/event-requests`** → the organiser isn't in the database uvicorn is using. Run `alembic upgrade head` and `python -m app.seed`; check no terminal has a leftover `DATABASE_URL` (`echo $env:DATABASE_URL`).
- **`python -m app.seed` fails with `relation … does not exist`** → you skipped `alembic upgrade head`.
- **Ports 5173 / 8000 are taken by another project** → stop it, or for E2E set `E2E_FRONTEND_PORT` (and matching `VITE_API_BASE_URL` / `CORS_ORIGINS`).
- **A PR check fails instantly** → the title needs a `feat:` / `fix:` / `chore:` prefix.
- **A PR check hangs** → E2E waits on the backend's health endpoint; read the "Backend log" step.
 
### Rules that keep us out of trouble
 
- **One shared Supabase.** Branch work points `DATABASE_URL` at local Docker Postgres. Only `main` is applied to Supabase, by one named person, right after the merge. Running `alembic upgrade head` from a branch changes the schema for the whole team before review.
- **Every schema change is a migration in the repo.** Nothing is created by clicking in the Supabase dashboard, or the next person's `alembic upgrade` fails on a table that already exists.
- **One migration head.** If two branches each add a migration, Alembic ends up with two heads on merge. Rebase on `main` and regenerate rather than merging heads.
- **Tests never touch Supabase.** They build a separate `connectsphere_test` database from the migrations and refuse to run against a non-local host. Keep that guard.
- **Deviating from §2/§3 is allowed; doing it silently is not.** Add a `# DECISION-PENDING: <id>` at the code site and a line under "Deviations awaiting a decision" below.
- **New screens call the real API** (changed in Sprint 2 — the Sprint 1 "mockups stay mockups" rule is retired; *needs team confirmation*). Build through `frontend/src/api/client.ts`, with TypeScript types that match the API's snake_case names. Don't add new mock data.
- **Two identity headers, one per route family.** Sprint 1 routes take `X-Attendee-Id` (`get_current_attendee`); event-request routes take `X-User-Id` (`get_current_user` / `require_user_roles`). Every attendee has a `users` row with the **same id** and role `attendee`, so one id works in both. Both stubs go when Supabase Auth lands (§9).
- **Another person's record is `404 NOT_FOUND`, never `403`.** Applies to drafts as well as registrations (TC-US7-02, TC-US1-13).
- **Schema changes go in the first PR of a story, alone.** US1 split into schema → API → screens PRs; the API and screen PRs added no migration. Keeps one Alembic head and a reviewable migration.
- **E2E runs against a migrated, seeded database.** `e2e.yml` runs `alembic upgrade head` and `python -m app.seed` before starting the backend. A new E2E test needing data should get it from the seed, not by assuming an empty database.
 
### Deviations awaiting a decision
 
Each is implemented and defensible; each departs from the contract in §2/§3 and needs the team to either bless it or change the code.
 
| # | Deviation | Where |
|---|---|---|
| 1 | `attendees` table isn't in §2 at all. §2 references `attendees(id)` without defining it, so SCRUM-24 added the minimal version (`id`, `email`, `created_at`) | `app/user/models.py` |
| 2 | Withdrawing an `offered` registration returns `409 REGISTRATION_NOT_ACTIVE`, a code not in §3's table. Releasing an offer is a decline, not a withdrawal | `app/registration/service.py` |
| 3 | `POST /registrations/{id}/decline` isn't in §3's endpoint list. TC-US7-11 needs declining to be distinct from letting the window lapse | `app/registration/router.py` |
| 4 | `expire-offer` doesn't check that `offer_expires_at` has passed, and isn't restricted to the offer holder — it stands in for a system job | `app/registration/service.py` |
| 5 | Offer-release responses say *whether* the seat was passed on, never to whom, because TC-X-04 forbids revealing another attendee | `app/registration/schemas.py` |
| 6 | `POST /events/{id}/waitlist` doesn't require `X-Attendee-Id`, against §3's "every endpoint depends on it". Its contract is body-only (`{"email": ...}`), matching D3's email-only case | `app/registration/router.py` |
| 7 | Event requests live on the `events` table (nullable fields + a status-based CHECK), not a separate `event_requests` table, so the whole lifecycle is one row | `app/event/models.py`, SCRUM-40 migration |
| 8 | `expected_attendees = 0` is rejected even when saving a draft (`422 INVALID_EVENT_REQUEST`), because the DB CHECK forbids it | `app/event/request_service.py` |
| 9 | New error code `INVALID_EVENT_REQUEST` (422, with `fields`) for present-but-invalid values — past/duplicate dates, start ≥ end, attendees < 1 — distinct from `MISSING_REQUIRED_FIELD` | `app/event/request_service.py` |
| 10 | The form auto-adds a date left in the date picker on Save/Submit; "Add date" is only needed for extra dates. Found in manual testing | `frontend/src/features/eventRequest/` |
| 11 | New error code `INVALID_CLARIFICATION` (422, `fields: ["sections"]` plus the unknown `sections`) for an unknown or repeated section; an empty section list or blank comment is `MISSING_REQUIRED_FIELD` | `app/event/clarification_service.py` |
| 12 | New error code `CLARIFICATION_NOT_ALLOWED` (409, with the request's current `status`) when a coordinator asks for clarification outside `submitted`/`under_review` | `app/event/clarification_service.py` |
 
### Open decisions still unanswered
 
§6 defines D1–D6 and a Sprint 1 default for each. All six are coded to their defaults and marked in the code; **none has been confirmed by the team**. D7 is new and not in §6. D8–D12 came from US1 and D13–D14 from US8; all are marked `DECISION-PENDING` in the code.
 
| id | Question | What we assumed |
|---|---|---|
| D1 | How long is a waitlist offer valid? | 24 hours, one constant `WAITLIST_OFFER_WINDOW` |
| D2 | What expires an offer? | A manual endpoint. No scheduler this sprint |
| D3 | Is a waitlisted person an attendee or just an email? | Store both; `attendee_id` when we have one |
| D4 | Are "cancel" and "withdraw" the same action? | Yes, one action |
| D5 | Does withdrawal notify by email or on screen? | On screen only |
| D6 | May a waitlisted person leave the queue? | Yes, via the same withdraw endpoint |
| D7 | Must you be identified to join a waitlist? | No — email is enough. Settle with D3 |
| D8 | What are the event category options? | Free text, non-empty, max 100 chars |
| D9 | What timezone are preferred times in? | Asia/Singapore local time (`time` without zone); converted when a request becomes an event |
| D10 | What's the request reference format? | `ER-<year>-<6-digit sequence>`, e.g. `ER-2026-000123`, from `event_request_reference_seq`; one formatter function |
| D11 | Who can read a submitted request? | Owner, coordinators and operations managers, **only while in a request status** (submitted → rejected). Other organisers 404. Drafts owner-only |
| D12 | How are users identified before Supabase Auth? | `X-User-Id` header stub, alongside `X-Attendee-Id` |
| D13 | Which sections can a clarification request tag? | SCRUM-11 only gives examples (attendance, layout, equipment). Assumed seven, grouping the US1 fields: `details`, `schedule`, `attendance`, `layout`, `accessibility`, `equipment`, `registration`. One list in `CLARIFICATION_SECTIONS`, mirrored by the migration's CHECK |
| D14 | Which coordinator may ask for clarification? | Any active coordinator. US10 (SCRUM-13) assigns a coordinator to a request; tighten this to the assigned one then |
 
### Environment
 
- **Supabase can lag `main`.** Check before blaming the code: `alembic current` against Supabase versus `alembic heads` in the repo. A missing table usually means an unapplied migration, not a bug.
- **Row Level Security is on for every application table, with no policies** (migration `5733a3c705f7`). RLS on plus no policies means Supabase's anon and authenticated roles can read nothing; the backend is unaffected because it connects as the tables' owner, and owners bypass RLS. Keep the Data API disabled anyway — belt and braces. **Adding a table means enabling RLS on it in the same migration.** Policies come with Supabase Auth (§9), when the browser needs its own access.
- **Backend tests need Postgres running**: `docker compose up -d postgres`. Without it every database test errors on connection, which looks alarming and isn't.
- **Python 3.12**, pinned in `backend/.python-version` and matched by CI. A 3.13 virtualenv can pass locally and fail in CI.
- **No dependency lock on the backend.** `pyproject.toml` uses open ranges, so two machines can resolve different versions. The frontend has `package-lock.json`; the backend has nothing equivalent. Suspect this when something works for one person only.
- **Frontend and API don't share vocabulary yet — for the Sprint 1 screens.** The mockup says `title`, `format`, `startsAt`; §3 says `name`, `delivery_mode`, `start_at`. The US1 screens already use the API's names (`frontend/src/features/eventRequest/`). Generating TypeScript types from `/openapi.json` would turn a rename into a build error instead of a runtime one.
- **Env files are per machine and git-ignored.** Both `backend/.env` and `frontend/.env` must exist; after pulling a change to either `.env.example`, compare and copy the new lines across.
- **The seed refuses a non-local database** unless run with `--yes`. Only the named Supabase person should ever pass it.
 
### What's next in Sprint 2
 
1. **Wire the Sprint 1 screens** (event list, register, my events, withdraw). Every endpoint exists, and US1 built the plumbing: `api/client.ts` sends an identity header and turns 404/409/422 into structured errors. Swap `useEventRegistry`'s functions for `apiClient` calls, send `X-Attendee-Id` (the seed prints an attendee id), handle the §3 codes (`EVENT_FULL`, `ALREADY_REGISTERED`, `REGISTRATION_CLOSED`, `MISSING_REQUIRED_FIELD`), and add loading/error states. **No Jira ticket yet — create one.** Do it **before US6's frontend**: the join-waitlist prompt hangs off the register screen's real `EVENT_FULL` response.
2. **US6 (SCRUM-10).** Backend mostly exists from Sprint 1. Still missing: honour `waitlist_enabled` (column added in SCRUM-40, default `false` — the seed's waitlist events may need it set to `true`), and **an accept-offer endpoint** (offers can only be declined or expire today). Settle D3/D6/D7.
3. **US8 (SCRUM-11) and US10 (SCRUM-13)** build on the US1 request: statuses, `users`/roles and `X-User-Id` exist. The seed has a **coordinator** since SCRUM-54; US10 still needs to seed an **operations manager**. US8a's backend is done: `POST /api/v1/event-requests/{id}/clarifications` (§3) stores the question and sets `awaiting_clarification` in one transaction (`clarification_service.send_request`). SCRUM-55 hooks the organiser notification into `send_request`; SCRUM-77 adds the reply as a `response` row for the same round and sets `under_review`, which lets the next round through the guard; SCRUM-56 refines what's allowed for later rounds. Nothing yet moves a request to `under_review` or `approved` — agree who does. US10 moving an event to `planning` will hide it from staff under D11; widen that rule in US10 if the coordinator needs to keep reading it.
4. **One end-to-end test** that registers, views and withdraws against the live backend, once item 1 is done. The E2E job already migrates and seeds.
5. **Then Supabase Auth** (§9), replacing both header stubs — after the wiring, so a failure can only be in one half. It brings RLS policies with it.
6. **Smaller, worth doing:** fix the root README (missing `alembic upgrade head`, the frontend `.env` copy, a CI section naming a `ci.yml` that doesn't exist, TODO team list); lock the backend's dependencies; review the Dependabot PRs; make the notification log visible under uvicorn; delete merged branches; turn on branch protection for `main`.

---

## 2. Data model (Supabase / Postgres)
 
Sprint 1 owns `registrations`, `registration_answers`, `attendance_log` and the seed data. `events` and `venues` are placeholders standing in for Epic 1 and Epic 2 output — keep the columns other epics will need, but do not build write paths for them.
 
### `events` — seeded only this sprint (SCRUM-23)
 
```sql
create type event_status as enum ('draft', 'submitted', 'confirmed', 'cancelled');
create type delivery_mode as enum ('in_person', 'online');
 
create table events (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null,
  status              event_status not null default 'draft',
  registration_enabled boolean not null default false,
  registration_opens_at  timestamptz,
  registration_closes_at timestamptz,
  start_at            timestamptz not null,
  end_at              timestamptz not null,
  capacity            integer not null check (capacity >= 0),
  delivery_mode       delivery_mode not null,
  venue_name          text,        -- in_person only
  room_number         text,        -- in_person only
  join_link           text,        -- online only
  created_at          timestamptz not null default now()
);
```
 
`registration_enabled` and the open/close window are **two separate gates**. The AC lists them as separate bullets ("events that are confirmed and have registration enabled" / "only register while registration is open"), so keep them separate — an event can have registration enabled but not yet open.
 
### `events` — Sprint 2 additions for event requests (SCRUM-40)

An event request **is** an `events` row in an early status (deviation 7). Migration `20260930_1200_us1_request_schema`:

```sql
-- full lifecycle; Sprint 1 values kept
-- draft → submitted → under_review ⇄ awaiting_clarification → approved | rejected
--       → planning → confirmed → cancelled | completed
alter type event_status add value 'under_review' after 'submitted';  -- + awaiting_clarification,
                                                                      --   approved, rejected, planning, completed
alter table events
  add column waitlist_enabled       boolean not null default false,   -- for US6
  add column event_category         text,          -- D8
  add column purpose                text,
  add column preferred_dates        date[],        -- sorted on submit
  add column preferred_start_time   time,          -- Asia/Singapore local, D9
  add column preferred_end_time     time,
  add column expected_attendees     integer,       -- check (expected_attendees >= 1)
  add column room_layout_preference text,
  add column accessibility_needs    text,
  add column equipment_needs        text,
  add column registration_required  boolean,       -- null = not decided (distinct from false)
  add column created_by_user_id     uuid references users(id),
  add column submitted_by_user_id   uuid references users(id),
  add column submitted_at           timestamptz,
  add column request_reference      text unique;   -- D10, set only on submit
create sequence event_request_reference_seq;
```

- `name`, `start_at`, `end_at`, `capacity` and `delivery_mode` became **nullable**, guarded by the CHECK `events_final_fields_required`: they may be null only while status is `draft`, `submitted`, `under_review`, `awaiting_clarification`, `approved` or `rejected`. `planning` onwards must have them.
- All request fields are nullable so drafts can be partial (AC3). Mandatory-field checks happen at submit, in the service, not in the schema.
- Downgrade refuses if it would discard lifecycle, request or user data.

### `users` — role-aware identity (SCRUM-40)

```sql
create type user_role as enum ('organiser', 'coordinator', 'operations_manager', 'attendee');

create table users (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  role        user_role not null default 'attendee',
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);
alter table users enable row level security;
-- attendees.id references users.id: every attendee has a users row with the same id, role 'attendee'
```

Existing attendees were backfilled. Anything that creates an attendee (the seed's `upsert_attendee`, the test factory `make_attendee`) must create the `users` row first.

### `event_request_clarifications` — US8 clarification thread (SCRUM-54)

AC (SCRUM-11): "The Coordinator can select which section(s) of the request the clarification concerns … and add a comment." 8c and 8d add the organiser's reply and further rounds, so it's one thread table, not a column on `events`.

```sql
create type clarification_kind as enum ('request', 'response');

create table event_request_clarifications (
  id             uuid primary key default gen_random_uuid(),
  event_id       uuid not null references events(id),
  round          integer not null check (round >= 1),
  kind           clarification_kind not null,   -- request = coordinator's question, response = organiser's reply
  sections       text[],                        -- request: ≥ 1 of D13's sections; response: null
  comment        text not null check (btrim(comment) <> ''),
  author_user_id uuid not null references users(id),
  created_at     timestamptz not null default now(),
  unique (event_id, round, kind)                -- one question and at most one reply per round
);
alter table event_request_clarifications enable row level security;
```

- `clarification_service.add_request` validates, stores sections in D13's order, and numbers the round (`max(round) + 1`). It **doesn't check the event's status or commit**: `send_request` (SCRUM-53) locks the event, guards the status, calls it and moves the request to `awaiting_clarification` in the same transaction. Whether a new round is allowed (8d) is that guard's job too.
- `clarification_service.list_thread` returns the thread oldest round first, each question before its reply (SCRUM-58).
- Downgrade refuses if any message exists.

### `registrations` — the core table (SCRUM-24)
 
```sql
create type registration_status as enum (
  'confirmed',   -- holds a seat
  'waitlisted',  -- queued, holds no seat
  'offered',     -- a freed seat is held for this person until offer_expires_at
  'withdrawn',   -- attendee withdrew
  'declined',    -- declined or let an offer lapse
  'expired'
);
 
create table registrations (
  id              uuid primary key default gen_random_uuid(),
  event_id        uuid not null references events(id),
  attendee_id     uuid references attendees(id),   -- null only for email-only waitlist entries, see §6 D3
  attendee_email  text not null,
  status          registration_status not null,
  registered_at   timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  withdrawn_at    timestamptz,
  waitlist_joined_at timestamptz,   -- ordering key for the waitlist, NOT a stored position
  offer_expires_at   timestamptz,
  created_at      timestamptz not null default now()
);
 
-- "Cannot register twice for the same event" — enforced in the DB, not only in app code.
create unique index registrations_one_active_per_attendee
  on registrations (event_id, attendee_id)
  where status in ('confirmed', 'waitlisted', 'offered');
```
 
Two rules that fall out of this and must hold everywhere:
 
- **Waitlist position is derived, never stored.** Position = rank by `waitlist_joined_at` ascending among `status = 'waitlisted'` rows for that event. Storing an integer means renumbering every row on every withdrawal and it will drift.
- **Seat occupancy** = `count(status = 'confirmed') + count(status = 'offered' AND offer_expires_at > now())`. An outstanding offer holds a seat — SCRUM-6's AC requires it ("the place remains reserved for that person during the window"). `seats_remaining = events.capacity - occupancy`, computed, never a column that can go stale.
### `registration_answers` — per-event required info
 
AC: "Provides the registration information required for that event." The required fields differ per event, so they cannot be columns.
 
```sql
create table event_registration_fields (
  id        uuid primary key default gen_random_uuid(),
  event_id  uuid not null references events(id),
  field_key text not null,
  label     text not null,
  field_type text not null check (field_type in ('text','email','select','number')),
  options   jsonb,
  required  boolean not null default true,
  sort_order integer not null default 0,
  unique (event_id, field_key)
);
 
create table registration_answers (
  registration_id uuid not null references registrations(id) on delete cascade,
  field_key       text not null,
  value           text,
  primary key (registration_id, field_key)
);
```
 
### `attendance_log` — audit trail (SCRUM-39)
 
AC: "Has the withdrawal recorded with a timestamp for the event's attendance history."
 
```sql
create table attendance_log (
  id              bigserial primary key,
  registration_id uuid not null references registrations(id),
  event_id        uuid not null references events(id),
  attendee_id     uuid,
  action          text not null,  -- registered | waitlisted | withdrawn | offered | offer_expired | declined
  occurred_at     timestamptz not null default now(),
  note            text
);
```
 
Append-only. Never update or delete a row here — a withdrawal must leave both the `registrations.withdrawn_at` timestamp and a permanent log row.
 
### Concurrency
 
Registration and withdrawal both read seat occupancy and then write. Two attendees registering for the last seat at the same moment must not both get it. Take a row lock on the event for the duration of the transaction:
 
```sql
select capacity from events where id = :event_id for update;
```
 
`TC-US3-10` tests exactly this.
 
---
 
## 3. API contracts (FastAPI)
 
Prefix everything `/api/v1`. Return Pydantic models, not raw dicts.
 
**Identity (Sprint 1):** Supabase Auth is not wired up yet. Read the caller from an `X-Attendee-Id` header and resolve it in a single `get_current_attendee()` dependency. Every endpoint depends on it. When auth lands, one function changes. Do not scatter attendee lookups through route bodies.
 
### `GET /events/available` — SCRUM-25
 
Returns events an attendee may register for right now: `status = 'confirmed'` AND `registration_enabled = true` AND `now()` within `[registration_opens_at, registration_closes_at)` AND `end_at > now()`.
 
```json
{
  "events": [{
    "id": "uuid", "name": "Tech Talk: Agile at Scale",
    "start_at": "2026-10-02T14:00:00+08:00", "end_at": "2026-10-02T16:00:00+08:00",
    "delivery_mode": "in_person", "venue_name": "SMU SCIS Seminar Room 2-1",
    "capacity": 40, "seats_remaining": 3, "is_full": false,
    "already_registered": false,
    "registration_fields": [
      {"field_key": "dietary", "label": "Dietary requirements", "field_type": "text", "required": false}
    ]
  }]
}
```
 
`already_registered` is computed for the calling attendee so the mockup can grey out the button.
 
### `POST /events/{event_id}/registrations` — SCRUM-26, SCRUM-27
 
Body: `{"answers": {"dietary": "vegetarian"}}`
 
| Outcome | Status | Body |
|---|---|---|
| Registered | `201` | `{"registration_id", "status": "confirmed", "event": {"name", "start_at", "end_at", "venue_name" or "join_link"}}` |
| Event full → waitlist offered | `409` | `{"code": "EVENT_FULL", "waitlist_available": true, "message": "..."}` |
| Already registered | `409` | `{"code": "ALREADY_REGISTERED"}` |
| Not confirmed / registration disabled | `403` | `{"code": "REGISTRATION_NOT_ENABLED"}` |
| Outside registration window | `403` | `{"code": "REGISTRATION_CLOSED"}` |
| Missing required answer | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["dietary"]}` |
 
The success body must carry **date, time and venue** — the AC names all three ("Receives a confirmation, along with the event's date, time and venue"). For an online event, `join_link` stands in for venue.
 
The full-event case is a **409, not a silent waitlist join.** The AC says the attendee is *offered* a waitlist place, which means they must accept. Joining is a second, explicit call:
 
### `POST /events/{event_id}/waitlist` — SCRUM-27
 
Body: `{"email": "calvin.ng.2024@smu.edu.sg"}` → `201 {"registration_id", "status": "waitlisted", "position": 4}`
 
### `GET /me/registrations` — SCRUM-30, SCRUM-31
 
```json
{
  "confirmed": [{
    "registration_id": "uuid", "event_name": "Tech Talk: Agile at Scale",
    "date": "2026-10-02", "start_time": "14:00", "end_time": "16:00",
    "venue_name": "SMU SCIS Seminar Room 2-1", "joining_info": "Room 2-1",
    "delivery_mode": "in_person"
  }],
  "waitlisted": [{ "...": "same fields", "waitlist_position": 4 }]
}
```
 
Sorting, filtering and section order are all server-side — the mockup must not re-sort. See `TC-US11-04` through `TC-US11-07`.
 
### `POST /registrations/{registration_id}/withdraw` — SCRUM-34, SCRUM-35, SCRUM-36, SCRUM-39
 
| Outcome | Status | Body |
|---|---|---|
| Withdrawn | `200` | `{"status": "withdrawn", "withdrawn_at", "event_name", "seats_remaining": 4}` |
| Not the caller's registration | `404` | `{"code": "NOT_FOUND"}` — 404 not 403, don't leak other attendees' records |
| Event already started | `403` | `{"code": "EVENT_STARTED"}` |
| Already withdrawn | `409` | `{"code": "ALREADY_WITHDRAWN"}` |
 
A withdrawal is **one transaction**: flip status → write `withdrawn_at` → append `attendance_log` → either create an offer for the head of the waitlist or leave the seat free. If the offer notification fails to send, the transaction still commits; log the failure, don't roll back the withdrawal.
 
### `POST /registrations/{registration_id}/expire-offer` — SCRUM-37 (**Sprint 1 stub**)
 
Manual trigger standing in for a scheduled job, exactly as the ticket says ("stub manual 'expire offer' for Sprint 1, pending team decision"). Expires the offer, appends to `attendance_log`, and offers the seat to the next waitlisted person. No scheduler, no background worker this sprint. Mark it clearly:
 
```python
# DECISION-PENDING: D2 — manual stub for SCRUM-37. Replace with a scheduled
# sweep once the team agrees on the offer window length.
```
 
---
 
### Event requests — SCRUM-41 to SCRUM-44 (US1)

Router: `app/event/request_router.py`; logic: `app/event/request_service.py`. **Identity:** `X-User-Id`, resolved by `get_current_user` (unknown or missing → `401 UNAUTHENTICATED`, inactive → `403 FORBIDDEN`); write routes also need role `organiser` (`require_user_roles`, wrong role → `403 FORBIDDEN`).

| Method & path | Purpose |
|---|---|
| `POST /api/v1/event-requests` | Create a draft from partial data → `201` |
| `GET /api/v1/me/event-requests` | Caller's requests, newest first → `{"event_requests": [...]}` |
| `GET /api/v1/event-requests/{id}` | Read one (owner; staff per D11) |
| `PATCH /api/v1/event-requests/{id}` | Update a draft; only fields sent are changed |
| `POST /api/v1/event-requests/{id}/submit` | Validate and submit |

Write body (every field optional; unknown fields rejected): `name`, `event_category`, `purpose`, `preferred_dates` (ISO dates), `preferred_start_time`, `preferred_end_time` (`HH:MM`), `expected_attendees`, `room_layout_preference`, `accessibility_needs`, `equipment_needs`, `registration_required`. The response echoes them plus `id`, `status`, `created_by_user_id`, `submitted_by_user_id`, `submitted_at`, `request_reference`, `created_at`.

Mandatory at submit: `name`, `event_category`, `purpose`, `preferred_dates` (≥ 1), `preferred_start_time`, `preferred_end_time`, `expected_attendees`.

| Outcome | Status | Body |
|---|---|---|
| Submitted | `200` | status `submitted`, `request_reference` like `ER-2026-000001`, submitter + `submitted_at` set, dates sorted |
| Mandatory field missing | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` — status stays `draft` |
| Value present but invalid (past or duplicate date, start ≥ end, attendees < 1) | `422` | `{"code": "INVALID_EVENT_REQUEST", "fields": [...]}` |
| Edit or re-submit after submission | `409` | `{"code": "EVENT_REQUEST_LOCKED"}` |
| Someone else's draft, or not visible under D11 | `404` | `{"code": "NOT_FOUND"}` |

Submit and edit lock the row (`SELECT … FOR UPDATE`), so two simultaneous submits can't both succeed or burn two references.

### `POST /api/v1/event-requests/{id}/clarifications` — SCRUM-53 (US8a)

Role `coordinator` only (D14). Body: `{"sections": ["attendance", "layout"], "comment": "..."}` — sections from D13. Logic: `clarification_service.send_request`, which locks the request row.

| Outcome | Status | Body |
|---|---|---|
| Sent | `201` | `{"clarification": {"id", "event_id", "round", "kind": "request", "sections", "comment", "author_user_id", "created_at"}, "status": "awaiting_clarification"}` |
| No sections / blank comment | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Unknown or repeated section | `422` | `{"code": "INVALID_CLARIFICATION", "fields": ["sections"], "sections": [...]}` |
| Request not `submitted` or `under_review` | `409` | `{"code": "CLARIFICATION_NOT_ALLOWED", "status": "<current>"}` (deviation 12) |
| Draft, an event past the request stage, or unknown id | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

Nothing is stored and the status doesn't change on any error.

---

## 4. Test cases
 
These are the acceptance criteria restated as executable checks. Each one maps to a bullet the team wrote in Jira. Write them all before writing implementation code.
 
### SCRUM-2 / US3 — Register for an Event
 
> *As an Attendee, I want to register for a confirmed event so that I have a reservation and receive the event's details.*
 
| ID | Given | When | Then |
|---|---|---|---|
| TC-US3-01 | Events exist in every status | `GET /events/available` | Only `confirmed` + `registration_enabled` + within window + not ended are returned |
| TC-US3-02 | Event is `confirmed` but `registration_enabled = false` | Attendee registers | `403 REGISTRATION_NOT_ENABLED`; no registration row created |
| TC-US3-03 | Event is `draft` / `submitted` / `cancelled` | Attendee registers | `403`; no row created |
| TC-US3-04 | `now()` is before `registration_opens_at` | Attendee registers | `403 REGISTRATION_CLOSED` |
| TC-US3-05 | `now()` is after `registration_closes_at` | Attendee registers | `403 REGISTRATION_CLOSED` |
| TC-US3-06 | Event has a required field `dietary`; body omits it | Attendee registers | `422 MISSING_REQUIRED_FIELD` listing `dietary`; no row created |
| TC-US3-07 | Valid open event with seats, all required answers supplied | Attendee registers | `201`, row `status = 'confirmed'`, answers persisted, response contains event **date, start time, end time and venue name** |
| TC-US3-08 | Online event | Attendee registers | Confirmation carries `join_link` in place of venue |
| TC-US3-09 | Attendee already holds a `confirmed` registration for this event | Registers again | `409 ALREADY_REGISTERED`; still exactly one active row (DB unique index holds even if the guard is bypassed) |
| TC-US3-10 | Capacity 1, 0 taken, two attendees register **concurrently** | Both calls run | Exactly one `201`, one `409 EVENT_FULL`; `occupancy` never exceeds capacity |
| TC-US3-11 | Capacity fully taken by confirmed registrations | Attendee registers | `409 EVENT_FULL` with `waitlist_available: true`; **no** registration row created yet |
| TC-US3-12 | Attendee received `EVENT_FULL` | `POST /events/{id}/waitlist` with their email | `201`, row `status = 'waitlisted'`, `waitlist_joined_at` set, position returned |
| TC-US3-13 | Three attendees join the waitlist in order A, B, C | Each queries position | A = 1, B = 2, C = 3, derived from `waitlist_joined_at` |
| TC-US3-14 | Capacity 5, 4 confirmed, 1 unexpired `offered` | Attendee registers | `409 EVENT_FULL` — an outstanding offer holds its seat |
| TC-US3-15 | Attendee previously `withdrawn` from this event | Registers again | `201` — the partial unique index permits it; withdrawal is not a ban |
 
### SCRUM-5 / US11 — View upcoming registered events
 
> *As an Attendee, I want to see the events I am registered for, so that I know when and where to attend.*
 
| ID | Given | When | Then |
|---|---|---|---|
| TC-US11-01 | Attendee A and Attendee B both have registrations | A calls `GET /me/registrations` | Only A's registrations appear; none of B's, in either section |
| TC-US11-02 | Confirmed registration for an in-person event | A loads the view | Entry shows event name, date, start time, end time, venue name, **and room number** as joining info |
| TC-US11-03 | Confirmed registration for an online event | A loads the view | Joining info is the **join link**, not a room number |
| TC-US11-04 | Three upcoming events on different dates | A loads the view | Ordered by `start_at` ascending, soonest first |
| TC-US11-05 | Two events with identical `start_at`, names "Zumba" and "Archery" | A loads the view | "Archery" before "Zumba" — alphabetical tiebreak |
| TC-US11-06 | A has both confirmed and waitlisted registrations | A loads the view | Two separately headed sections; **Confirmed first**, Waitlisted second |
| TC-US11-07 | A is 3rd on a waitlist | A loads the view | That entry shows position `3` |
| TC-US11-08 | A withdraws from an event, then reloads | A loads the view | The event is absent |
| TC-US11-09 | An event's `end_at` is in the past | A loads the view | The event is absent — filter on `end_at`, **not** `start_at`; an in-progress event still shows |
| TC-US11-10 | A has no upcoming registrations | A loads the view | Empty-state message, not an empty array rendered as a blank page |
| TC-US11-11 | A has confirmed registrations but nothing waitlisted | A loads the view | Waitlisted section is omitted or shows its own empty state — it must not break the Confirmed section |
 
### SCRUM-6 / US7 — Withdraw from a registration
 
> *As an Attendee, I want to withdraw my registration from an event I can no longer attend so that my place can be released to someone on the waiting list.*
 
| ID | Given | When | Then |
|---|---|---|---|
| TC-US7-01 | A holds a confirmed registration, event starts tomorrow | A withdraws | `200`, status `withdrawn`, confirmation body returned |
| TC-US7-02 | A passes B's `registration_id` | A withdraws | `404 NOT_FOUND`; B's registration untouched |
| TC-US7-03 | Event `start_at` is in the past | A withdraws | `403 EVENT_STARTED`; registration unchanged |
| TC-US7-04 | Event starts in 1 minute | A withdraws | `200` — the cutoff is `start_at`, inclusive of everything before it |
| TC-US7-05 | A already withdrew | A withdraws again | `409 ALREADY_WITHDRAWN`; no duplicate `attendance_log` row |
| TC-US7-06 | Capacity 10, 10 confirmed, **empty** waitlist | A withdraws | `seats_remaining` becomes 1; **no offer created**; no notification sent |
| TC-US7-07 | Capacity 10, 10 confirmed, waitlist B → C | A withdraws | B's row becomes `offered` with `offer_expires_at` set; C stays `waitlisted` at position 1; `seats_remaining` stays 0 — the seat is held, not free |
| TC-US7-08 | Same as above | Immediately after A's withdrawal | B is notified (assert the notification call, don't send real mail in tests) |
| TC-US7-09 | B holds an unexpired offer | C tries to claim the seat | Refused — the seat is not available until B's window lapses or B declines |
| TC-US7-10 | B's offer window lapses (`POST /expire-offer`) | Offer expires | B → `expired`; C → `offered`; `attendance_log` records both |
| TC-US7-11 | B declines the offer | B declines | B → `declined`; C → `offered` immediately, without waiting for a window |
| TC-US7-12 | Any successful withdrawal | A withdraws | `registrations.withdrawn_at` set **and** an `attendance_log` row with `action = 'withdrawn'` and `occurred_at` |
| TC-US7-13 | A withdraws, then checks the event listing | `GET /events/available` | `seats_remaining` reflects the withdrawal on the very next read — no cache, no delayed job |
| TC-US7-14 | A is `waitlisted`, not confirmed | A withdraws | `200`; A leaves the queue; everyone behind A moves up one position; no seat is freed |
| TC-US7-15 | Notification send raises an exception | A withdraws | Withdrawal still commits; failure is logged; response is still `200` |
 
### SCRUM-20 / US1 — Submit Event Request

> *As an Event Organiser, I want to submit an event request with my initial event requirements so that I can have planning start without manually creating a request by email.*

Backend: `tests/event/test_event_requests.py` (01–15), `tests/event/test_event_request_schema.py` (16). E2E: `e2e/tests/event-request.spec.ts`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US1-01 | Organiser | Creates a request with only some fields | `201`, status `draft` |
| TC-US1-02 | Owner's draft | Lists, reads and patches it | Changes persist; still `draft` |
| TC-US1-03 | Optional requirements, `registration_required = false` | Save and read back | Round-trips; `false` stays distinct from unset |
| TC-US1-04 | Draft with every mandatory field | Submit | `200`, status `submitted` |
| TC-US1-05 | Draft missing mandatory fields | Submit | `422 MISSING_REQUIRED_FIELD` listing each; status stays `draft` |
| TC-US1-06 | Past or duplicate preferred date | Submit | `422 INVALID_EVENT_REQUEST`; valid dates come back sorted |
| TC-US1-07 | One time missing, or start ≥ end | Submit | `422` naming the time field |
| TC-US1-08 | `expected_attendees = 0` | Save or submit | `422` (deviation 8) |
| TC-US1-09 | Valid draft | Submit | `submitted_by_user_id` and `submitted_at` recorded |
| TC-US1-10 | Two valid drafts | Submit both | Different references in `ER-<year>-<6 digits>` format |
| TC-US1-11 | Draft / submitted request | Read / submit again | Draft has no reference; re-submit `409 EVENT_REQUEST_LOCKED`, reference unchanged |
| TC-US1-12 | Submitted request | Owner patches it | `409 EVENT_REQUEST_LOCKED`; data unchanged |
| TC-US1-13 | Another organiser's draft | Read, patch or submit | `404 NOT_FOUND` |
| TC-US1-14 | Coordinator / ops manager | Read a draft; read a submitted request; read a confirmed event | `404`; `200`; `404` |
| TC-US1-15 | Missing/unknown `X-User-Id`, inactive user, wrong role | Call the routes | `401`, `403`, `403`; Sprint 1 `X-Attendee-Id` tests unchanged |
| TC-US1-16 | Migrated schema | Inspect / insert | Lifecycle values, columns, defaults, user backfill + FK, RLS on `users`; a `confirmed` event with null `start_at` is rejected; `expected_attendees` must be ≥ 1 |

The E2E test drives the browser: save a draft → submit with a field missing → see it flagged → complete it (leaving a date unadded in the picker) → submit → see the reference.

### SCRUM-11 / US8a — Send a clarification request

> *As an Event Coordinator, I want to send a clarification request back to the Event Organiser on specific parts of their submission, so that ambiguous requirements are called out before planning proceeds.*

Backend: `tests/event/test_event_request_clarifications.py` (01–08, storage, SCRUM-54) and `tests/event/test_event_request_clarification_api.py` (09–14, endpoint, SCRUM-53).

| ID | Given | When | Then |
|---|---|---|---|
| TC-US8-01 | Migrated schema | Inspect | Table, columns, `(event_id, round, kind)` unique, RLS on |
| TC-US8-02 | Submitted request, coordinator | Add a request tagging `equipment`, `attendance` | Round 1, sections stored in D13 order, comment trimmed, author and time recorded |
| TC-US8-03 | — | No sections, blank comment | `422 MISSING_REQUIRED_FIELD`, `fields: ["sections", "comment"]` |
| TC-US8-04 | — | Unknown or repeated section | `422 INVALID_CLARIFICATION` (deviation 11); nothing stored |
| TC-US8-05 | A request with one round | Add another; add one on a different request | Rounds 2 and 1 |
| TC-US8-06 | Round 1 question + reply, round 2 question | List the thread | Ordered by round, question before reply |
| TC-US8-07 | — | Insert directly with no/unknown sections, blank comment, a reply with sections, or a second question in a round | Database rejects each |
| TC-US8-08 | — | Run the seed | An active `coordinator` user exists |
| TC-US8-09 | `submitted` or `under_review` request | Coordinator sends | `201`, round 1, status `awaiting_clarification` (AC 2, 3) |
| TC-US8-10 | Clarification sent | Owner reads the request | Status `awaiting_clarification`; one message stored |
| TC-US8-11 | `awaiting_clarification`, `approved` or `rejected` request | Coordinator sends | `409 CLARIFICATION_NOT_ALLOWED`; status unchanged, nothing stored (AC 2) |
| TC-US8-12 | Draft, confirmed event, unknown id | Coordinator sends | `404 NOT_FOUND` |
| TC-US8-13 | No identity, organiser, ops manager, attendee, inactive coordinator | Send | `401`, then `403` for each; status unchanged |
| TC-US8-14 | Submitted request | Send with missing or unknown sections | `422`; status stays `submitted`, nothing stored |

### Cross-cutting
 
| ID | Check |
|---|---|
| TC-X-01 | All timestamps are `timestamptz`, stored UTC, serialised with offset. Team and events are Asia/Singapore (UTC+8) — a naive `datetime` anywhere is a bug |
| TC-X-02 | `seats_remaining` is computed on read. No test may depend on a stored counter column |
| TC-X-03 | Every state change writes exactly one `attendance_log` row |
| TC-X-04 | No endpoint returns another attendee's email, name or registration |
 
---
 
## 5. Subtask → definition of done
 
Each Jira subtask is done when its tests pass. The subtasks have no descriptions in Jira; this table is the working interpretation — correct it if the team meant otherwise.
 
### SCRUM-2 (US3)
 
| Subtask | Work | Done when |
|---|---|---|
| SCRUM-23 | Seed mock confirmed events with `registration_enabled` | Seed script produces: a confirmed+open event with seats, one with `registration_enabled = false`, one before its window, one after, one at full capacity, one online, one already ended. Idempotent — safe to re-run |
| SCRUM-24 | `registrations` schema + migration | Tables and the partial unique index exist in Supabase; TC-US3-09 passes at the DB level |
| SCRUM-25 | `GET /events/available` | TC-US3-01 |
| SCRUM-26 | `POST .../registrations` guards | TC-US3-02 … TC-US3-10, TC-US3-15 |
| SCRUM-27 | Waitlist branch | TC-US3-11, 12, 13, 14 |
| SCRUM-28 | Frontend: available-events list | **Mockup only** — static list matching the `GET /events/available` shape, with full/open/closed states visible |
| SCRUM-29 | Frontend: registration form + confirmation | **Mockup only** — form driven by `registration_fields`, confirmation screen showing date, time, venue |
 
### SCRUM-5 (US11)
 
| Subtask | Work | Done when |
|---|---|---|
| SCRUM-30 | Query by attendee, split confirmed/waitlisted | TC-US11-01, 06, 07, 08, 09 |
| SCRUM-31 | Sort ascending by start | TC-US11-04, 05 |
| SCRUM-32 | Frontend: "My Registrations" | **Mockup only** — two headed sections, waitlist position shown, empty state (TC-US11-10) drawn |
| SCRUM-33 | Frontend: "Discovery" view | **Mockup only** — reuses the SCRUM-28 list component; do not build a second one |
 
### SCRUM-6 (US7)
 
| Subtask | Work | Done when |
|---|---|---|
| SCRUM-34 | Withdraw endpoint + guards | TC-US7-01 … 05, 14 |
| SCRUM-35 | Capacity release | TC-US7-06, 13 |
| SCRUM-36 | Waitlist offer trigger | TC-US7-07, 08, 09 |
| SCRUM-37 | Offer expiry / decline (**stub**) | TC-US7-10, 11 via the manual endpoint. Leave `# DECISION-PENDING: D2` |
| SCRUM-38 | Frontend: withdraw action | **Mockup only** — withdraw button, confirm dialog, post-withdrawal confirmation |
| SCRUM-39 | Record withdrawal | TC-US7-12, TC-X-03 |
 
### SCRUM-20 (US1)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-40 | Schema + groundwork migration | TC-US1-16; one Alembic head; Sprint 1 tests unchanged | #27 |
| SCRUM-41 | Save-draft endpoint | TC-US1-01, 02, 03, 08 | #28 |
| SCRUM-42 | Submit + missing-field list | TC-US1-04, 05, 06, 07 | #28 |
| SCRUM-43 | Draft → Submitted + edit lock | TC-US1-11, 12 | #28 |
| SCRUM-44 | Reference + submitter/timestamp | TC-US1-09, 10 | #28 |
| SCRUM-45 | Frontend form + draft save | **Real API** — E2E journey | #29 |
| SCRUM-46 | Missing-field indicators | Inline from the 422 `fields` list — E2E journey | #29 |
| SCRUM-47 | Confirmation with reference | E2E journey | #29 |

Access and identity (TC-US1-13, 14, 15) span SCRUM-41–44.

### SCRUM-11 (US8a)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-54 | Thread table, `clarification_service`, seeded coordinator | TC-US8-01 to 08; one Alembic head | #34 |
| SCRUM-53 | Endpoint + guard + Submitted/Under Review → Awaiting Clarification | TC-US8-09 to 14 (AC 2, 3) | |
| SCRUM-57 | Coordinator section selector + comment UI | | |

**Build order** (dependencies are real — SCRUM-23 and SCRUM-24 unblock everything):
 
```
SCRUM-23 ─┐
SCRUM-24 ─┴─► SCRUM-25 ─► SCRUM-26 ─► SCRUM-27 ─► SCRUM-30 ─► SCRUM-31
                                   └─► SCRUM-34 ─► SCRUM-35 ─► SCRUM-36 ─► SCRUM-37 ─► SCRUM-39
Mockups (28, 29, 32, 33, 38) can proceed in parallel once the contracts in §3 are agreed.
```
 
---
 
## 6. Open decisions — do not guess
 
These are genuine gaps in the acceptance criteria, not oversights in this document. Use the Sprint 1 default, mark the code, and raise them at standup.
 
**D1 — How long is the waitlist offer window?**
SCRUM-6 says "a fixed window to accept" and names no duration. *Sprint 1 default:* 24 hours, as a single module-level constant `WAITLIST_OFFER_WINDOW = timedelta(hours=24)`. One constant, one edit when the team decides.
 
**D2 — What expires an offer?**
SCRUM-37 says the expiry handling is itself "pending team decision". *Sprint 1 default:* the manual `POST /expire-offer` endpoint. No scheduler.
 
**D3 — Is a waitlisted person an attendee or just an email?**
Real inconsistency between two stories: SCRUM-2 says the attendee is "offered to be put on a waitlist **using their email**", implying email is enough; SCRUM-5 says a waitlisted entry appears in that attendee's "My Events" with a position, which requires an `attendee_id`. *Sprint 1 default:* store both — `attendee_id` when the caller is authenticated, `attendee_email` always. Flag it; the team should pick one.
 
**D4 — "Cancels a registration" vs "withdraws".**
SCRUM-5 says "Given an Attendee cancels a registration"; SCRUM-6 calls the same action "withdraw". Treated as one action throughout. Confirm nobody meant an organiser-side cancellation.
 
**D5 — Does a withdrawn attendee get a confirmation email, or just an on-screen message?**
SCRUM-6 says "Sees a confirmation once the withdrawal is processed" — "sees" reads as on-screen. *Sprint 1 default:* response body only, no email.
 
**D6 — Can a waitlisted person leave the waitlist?**
Not stated anywhere. TC-US7-14 assumes yes, via the same withdraw endpoint. Cheap to build, easy to remove.
 
---
 
## 7. Out of scope for Sprint 1
 
Say so and stop if the work drifts into any of these:
 
- Creating, approving, editing or cancelling events (Epic 1 — SCRUM-19)
- Venue search, booking, equipment, setup buffers, staff assignment (Epic 2 — SCRUM-21)
- Standalone "Join a Waiting List" flow (SCRUM-10, Epic 3 but a later sprint)
- Supabase Auth / real login — `X-Attendee-Id` stub only
- Real email delivery — assert on a notification interface, log instead of send
- A working frontend. **Mockups only.** Do not wire React to FastAPI this sprint. *(Sprint 2: retired — see §1a Rules.)*
- Payments, check-in, attendance marking, feedback — nowhere in the backlog
---
 
## 8. Conventions
 
- **Tests:** `pytest` + `httpx.AsyncClient`. Name tests after their IDs. Use a transactional fixture that rolls back per test; never test against seeded production-ish data you also mutate.
- **Time:** freeze it (`freezegun` or an injected `now()` provider). TC-US3-04, TC-US3-05, TC-US7-03 and TC-US7-04 are unreliable otherwise.
- **Structure:** routes stay thin. Guard logic and state transitions live in a service layer so they can be tested without HTTP.
- **Errors:** every 4xx returns a machine-readable `code`, exactly as spelled in §3. The mockup keys off `code`, not off message text.
- **Migrations:** every schema change is a migration file in the repo. No changes made only in the Supabase dashboard.
- **Branches and PRs:** one branch per PR, named `feat(SCRUM-<n>)Title-Case-Words` (ranges allowed: `feat(SCRUM-41-44)…`), started from an up-to-date `main`. Commits and PR titles: `feat(SCRUM-<n>): lowercase summary` — CI checks the PR title's type prefix, not the branch name. Every PR is reviewed before merge.
- **Keep this file current:** every PR updates this document for what it changed (status row, rules, schema/API, deviations) before it merges, so everyone's Claude matches `main` after a pull.
---
 
## 9. Supabase Auth — plan for a later sprint
 
Out of scope for Sprint 1 (§7); written down so the `X-Attendee-Id` stub can be replaced without re-deciding any of it. Sequence it **after** the API wiring: wiring against the stub proves the endpoints, then only the identity mechanism changes. Doing both at once means a failure could be in either half.
 
Supabase Auth supplies **identity only**. FastAPI stays the only thing that touches the database, so no service or router changes — §3 already promises the change lands in one place:
 
> "When auth lands, one function changes. Do not scatter attendee lookups through route bodies."
 
That function is `get_current_attendee` in `app/user/dependencies.py`.
 
### Dashboard
 
Enable a provider under **Authentication → Providers**. Email/password is simplest; Google fits SMU accounts. With Google, **restrict the domain in our own code** — check the `email` claim ends in `@smu.edu.sg`; Supabase won't enforce it.
 
Keys come from **Project Settings → API**. Current naming: **publishable** (`sb_publishable_…`, safe in the frontend) and **secret** (`sb_secret_…`, backend only, probably not needed). The old `anon` / `service_role` keys still work but are deprecated by the end of 2026.
 
### Frontend
 
`@supabase/supabase-js`, created with `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`. Every request in `api/client.ts` carries `Authorization: Bearer <session.access_token>` in place of `X-Attendee-Id`. Read the session per request — tokens last an hour and supabase-js refreshes them, which a value cached at startup would miss. `VITE_*` values are compiled into the bundle and readable by anyone: the publishable key only.
 
### Backend
 
Supabase signs access tokens with **asymmetric keys** (RS256/ES256), so the backend holds no secret. Public keys come from:
 
```
https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
```
 
Verify with `pyjwt[crypto]` and a cached `PyJWKClient`, checking `audience="authenticated"` and `issuer=<url>/auth/v1`. The claims we need are `sub` (stable Supabase user id) and `email`.
 
### Linking to `attendees`
 
Our rows have their own UUIDs, and seeded ones come from `uuid5`, so no Supabase user sits behind them. Add a column rather than repurposing the primary key:
 
```sql
alter table attendees add column auth_user_id uuid unique;
```
 
`get_current_attendee` then: verify token → look up by `auth_user_id` → else **look up by email and link it** → else create. Matching on email first keeps the seeded demo accounts working the moment the real person signs in, instead of creating duplicates.
 
### Consequences to keep in mind
 
- **Tests must not reach the network.** Keep the dependency overridable, or inject the verifier so tests supply claims directly. The existing suite should need nothing beyond the fixture.
- **RLS is already on, but policy-less — that becomes a blocker here.** Today nothing can read these tables except the owner, which is fine while FastAPI is the only client. The moment the browser holds a publishable key, it needs policies keyed on `auth.uid()`, and those policies are the only thing stopping one student reading another's registrations. Write them alongside the auth work, not after it.
- **CORS already allows `Authorization`** (`allow_headers=["*"]`). Cookie-based sessions would instead need `allow_credentials=True` and specific origins.
 
Sources: [Supabase JWTs](https://supabase.com/docs/guides/auth/jwts), [API keys](https://supabase.com/docs/guides/api/api-keys).
 
---
 
## Traceability
 
| Test IDs | Jira | Acceptance criterion |
|---|---|---|
| TC-US3-01, 02, 03 | SCRUM-2 | View available events; confirmed + registration enabled only |
| TC-US3-04, 05 | SCRUM-2 | Register only while registration is open |
| TC-US3-06 | SCRUM-2 | Provides required registration information |
| TC-US3-07, 08 | SCRUM-2 | Confirmation with date, time, venue |
| TC-US3-09, 10, 15 | SCRUM-2 | Cannot register twice |
| TC-US3-11 … 14 | SCRUM-2 | Waitlist offer when capacity full |
| TC-US11-01 | SCRUM-5 | Only own registrations |
| TC-US11-02, 03 | SCRUM-5 | Name, date, times, venue, joining info |
| TC-US11-04, 05 | SCRUM-5 | Ascending by start; alphabetical tiebreak |
| TC-US11-06, 07, 11 | SCRUM-5 | Separate sections, Confirmed first, position shown |
| TC-US11-08, 09 | SCRUM-5 | Cancelled and past events drop off |
| TC-US11-10 | SCRUM-5 | Empty state |
| TC-US7-01 … 05, 14 | SCRUM-6 | Withdraw only own, only before start; confirmation |
| TC-US7-06 | SCRUM-6 | No waitlist → capacity returned, no offer |
| TC-US7-07 … 11 | SCRUM-6 | Offer to next person, held during window |
| TC-US7-12 | SCRUM-6 | Withdrawal recorded with timestamp |
| TC-US7-13 | SCRUM-6 | Capacity updated immediately |
 
| TC-US1-01, 02, 03 | SCRUM-20 | Enter details and optional requirements; save as draft and return later |
| TC-US1-04 … 08 | SCRUM-20 | Mandatory fields; cannot submit until complete; shown what's missing; stays Draft |
| TC-US1-09 | SCRUM-20 | Submission recorded with submitter and timestamp |
| TC-US1-10, 11 | SCRUM-20 | Confirmation with a reference to track the request |
| TC-US1-11, 12 | SCRUM-20 | Draft → Submitted; no direct edits after submission |
| TC-US1-13, 14, 15 | SCRUM-20 | (Access rules — D11, D12) |
| TC-US1-16 | SCRUM-40 | Schema groundwork for Epic 1 |
