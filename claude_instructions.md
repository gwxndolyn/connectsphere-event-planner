# ConnectSphere — Development Spec (Sprint 1–3)
 
**Source of truth:** Jira project `SCRUM` (SPM ConnectSphere) — https://smu-team-kk38iw8n.atlassian.net
**Generated:** 2026-09-19 from Jira issues SCRUM-2, SCRUM-5, SCRUM-6 and their subtasks.
**Updated:** 2026-10-11 — end of Sprint 2; Sprint 3 scope added.
**Stack:** FastAPI (Python) backend · Supabase (Postgres) · React/Vite frontend. Every screen calls the real API: the Sprint 1 attendee screens since SCRUM-79, the Event requests screens since US1.
 
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

| Jira | Story | Owner (Jira) | Points | Status |
|---|---|---|---|---|
| SCRUM-20 | US1 — Submit Event Request | Chloe | 8 | Done |
| SCRUM-10 | US6a — Join a waiting list for a full event | Gwendolyn | 3 | Done |
| SCRUM-72 | US6b — Take up an available place after a withdrawal | Gwendolyn | 3 | Done |
| SCRUM-11 | US8a — Send a clarification request on specific sections | Nicholas | 5 | Done |
| SCRUM-73 | US8b — Notify Organiser of a clarification request | Nicholas | 2 | Done |
| SCRUM-74 | US8c — See the Organiser's response and resume review | Nicholas | 5 | Done |
| SCRUM-75 | US8d — Send additional rounds of clarification | Nicholas | 2 | Done |
| | **Total** | | **28** | |

US10a–d (SCRUM-13, 67, 68, 69) did not start and moved to Sprint 3.

US1, US8 and US10 move the same event request through one status lifecycle, so SCRUM-40 laid shared groundwork for all three (statuses, request fields, `users` with roles, the `X-User-Id` stub) — see §2 and §3. Status per ticket lives in Jira, not here.

### Sprint 3 scope (11 – 25 Oct)

| Jira | Story | Owner | Points |
|---|---|---|---|
| SCRUM-81 | US16a — Log in and log out | Calvin | 3 |
| SCRUM-82 | US16b — Role-based access | Calvin | 3 |
| SCRUM-94 | US26 — Record and review an equipment request | Calvin | 3 |
| SCRUM-9 | US5 — Check equipment availability | Calvin | 3 |
| SCRUM-13 | US10a — Assign a Coordinator to an eligible event (Coordinator Lead) | Matthew | 3 |
| SCRUM-67 | US10b — See Coordinator workload when assigning | Matthew | 2 |
| SCRUM-68 | US10c — Notify Coordinator and Organiser of an assignment | Matthew | 2 |
| SCRUM-69 | US10d — View an event's Coordinator assignment history | Matthew | 3 |
| SCRUM-86 | US19 — Event Coordinator Lead's queue and oversight view | Matthew | 3 |
| SCRUM-83 | US10e — Reassign an event to another coordinator | Nic | 3 |
| SCRUM-84 | US17 — Approve or reject an event request | Nic | 3 |
| SCRUM-96 | US28 — View registrations for my events | Nic | 3 |
| SCRUM-87 | US20 — Manage the venue catalogue | Chloe | 5 |
| SCRUM-89 | US22 — Submit a venue booking request | Chloe | 3 |
| SCRUM-16 | US13 — Venue setup and turnaround buffer scheduling | Chloe | 5 |
| SCRUM-7 | US2 — Search for suitable venues | Gwendolyn | 8 |
| SCRUM-8 | US4 — Approve or reject a venue booking request | Gwendolyn | 5 |
| | **Total** | | **60** |

### Customer changes (Week 7)

| CR | Change | Stories |
|---|---|---|
| CR-01 | Setup and turnaround time configured per venue; conflicts are flagged, not removed | US13 (SCRUM-16) |
| CR-02 | A venue can become unavailable | US23a/b (SCRUM-90, 91) |
| CR-03 | One event can use multiple venues | US24 (SCRUM-92) |
| CR-04 | Venue holds expire | US25 (SCRUM-93); affects D2 |
| CR-05 | An Event Coordinator Lead assigns and reassigns events from an unassigned queue | US10a–e, US19 |
| CR-06 | A Safety Officer checks events | US30a/b (SCRUM-99, 100) |

US23a/b, US24, US25 and US30a/b are in Sprint 4 in Jira.
 
---
 
## 1a. Start here
 
Read this before writing code. It holds what the rest of the document can't: how to get the thing running, the rules we've had to learn, where the code knowingly departs from the contract, and what's still undecided.
 
**Per-ticket status does not live here.** Jira owns ticket state; git and the PR list own what merged. Duplicating either goes stale within hours — it already did once, when two of us edited this section on separate branches and produced a file that contradicted itself. Hence: **edit this section only in the PR that changes the code it describes**, and at sprint boundaries for the two summaries below.
 
### Where things stand — end of Sprint 2 (11 Oct)
 
All three Sprint 1 stories have working backends, tested against a real Postgres. **US1 (SCRUM-20) is the first feature built end to end**: schema, API and React screens, with the screens calling the real API. **The Sprint 1 attendee screens call the real API since SCRUM-79** (`mockEvents.ts` and the localStorage registry are gone).
 
| Story | Backend | Mockup | Test cases |
|---|---|---|---|
| SCRUM-2 — register for an event | Done | **Real screens, wired to API** (SCRUM-79) | TC-US3 15/15 + E2E |
| SCRUM-5 — view my upcoming events | Done | **Real screens, wired to API** (SCRUM-79) | TC-US11 11/11 + E2E |
| SCRUM-6 — withdraw from a registration | Done | **Real screens, wired to API** (SCRUM-79) | TC-US7 15/15 + E2E |
| SCRUM-20 — submit event request (US1) | Done | **Real screens, wired to API** | TC-US1 16/16 + 1 E2E |
| SCRUM-11 — request clarification (US8a) | Done: storage (SCRUM-54), send endpoint (SCRUM-53), review queue (SCRUM-57) | **Real screens, wired to API** (SCRUM-57) | TC-US8 16/16 + 1 E2E |
| SCRUM-10 — join a waitlist (US6a) | Done: availability rule (SCRUM-48) + join refusals (SCRUM-49) | Attendee screens wired (SCRUM-79); join prompt + position confirmation done (SCRUM-52) | TC-US6A 10/10 + E2E |
| SCRUM-72 — take up a place (US6b) | Done: offer notice (SCRUM-50) + accept (SCRUM-51) | **Real screens, wired to API**: Place available + Accept place (SCRUM-76) | TC-US6B 10/10 + 1 E2E |
| SCRUM-74 — organiser responds (US8c) | Done: response endpoint + thread read (SCRUM-77) | **Real screens, wired to API**: response form (SCRUM-78), thread view (SCRUM-58) | TC-US8-17 to 24 + E2E |
| SCRUM-75 — more clarification rounds (US8d) | Done: rounds guard pinned as D15 (SCRUM-56) | No change needed | TC-US8-31 to 35 |
| SCRUM-13 — assign a Coordinator (US10a) | Done: schema + seed, unassigned queue, coordinator picker and assign endpoints, Lead notified on submit (log-only, D28) | **Real screens, wired to API**: Lead's unassigned queue, coordinator picker and confirm, **Coordinator Lead** in Acting as, the organiser sees "Unassigned" or the coordinator's name | TC-US10A-01 to 31 |
| SCRUM-68 — notify Coordinator and Organiser of an assignment (US10c) | Done: `Notifier.assignment_made`, called after a successful assign (log-only) | No change needed | TC-US10C-01 to 07 |
| SCRUM-67 — see Coordinator workload when assigning (US10b) | Done: `GET /api/v1/coordinators` gives each entry a `planning_count` (D30) | **Real screens, wired to API**: the picker shows each coordinator's name and "N events planning" | TC-US10B-01 to 06 (backend), 07 to 09 (frontend) + the E2E picker check |
| SCRUM-86 — Lead's queue and oversight view (US19) | Done: `GET /api/v1/event-requests/assigned` (the active events this Lead assigned, filter by `coordinator_id` and `status`, soonest event date first; Lead only; D44). No new table: the Lead's scope is the assigner on an event's latest `coordinator_assignments` record | **Real screens, wired to API**: the Lead's page has **Unassigned** and **Assigned** tabs, coordinator and status filters, and a read-only request view from either tab (deviation 40) | TC-US19-01 to 11 (backend), 12 to 18 (frontend) + the E2E assign journey checks the tab, filter and view |
| SCRUM-69 — assignment history (US10d) | Done: `coordinator_assignments` table (SCRUM-63), written in the assign transaction; `GET /api/v1/event-requests/{id}/assignment-history`, Lead only, newest first (SCRUM-64) | **Real screens, wired to API**: the Lead's queue page lists Assigned requests, each with History, and Coordinator assigned offers View assignment history (SCRUM-66; deviation 35) | TC-US10D-01 to 10 and 15 (backend), 11 to 14 (frontend) + the E2E assign journey checks the history |
| SCRUM-87 — venue catalogue (US20) | Done: schema + seed (PR 1, #53); endpoints, Venue Staff stub (D19), validation, buffer-lock stub (PR 2) | **Real screens, wired to API**: Venues list with filters, staff create/edit form (PR 2) | TC-US20-01 to 19 (07's booking half is TC-US22-01) + 2 E2E; see `docs/testing/US20-venue-catalogue.md` |
| SCRUM-89 — request a venue booking (US22) | Schema (PR 1, SCRUM-111): `venue_bookings`, the no-overlap exclusion constraint, the real buffer-lock query. Endpoints (PR 2, SCRUM-112): create with warnings, withdraw, Venue Staff's pending list, an event's bookings, the Venue Staff notice, the inactive-venue read for booked coordinators | **Real screens, wired to API** (PR 3, SCRUM-113): Request venue and the event's bookings with Withdraw on an Approved request in the coordinator's review queue; Venue staff's pending list on Venues (deviation 32) | TC-US22-01 to 21 + 3 E2E; see `docs/testing/US22-venue-booking.md` |
| SCRUM-7 — search for suitable venues (US2) | Done: `GET /api/v1/venues/available` (hides live US22 bookings and `venue_blocks`), `venue_blocks` table, seeded slot | **Real screen, wired to API**: search form on Venues for Coordinator and Venue staff | TC-US2-01 to 16 (12 pytest + 4 E2E) + frontend unit and integration; see `docs/testing/US2-venue-search.md` |
| SCRUM-8 — approve or reject a venue booking request (US4) | Done: decision columns + CHECKs (migration `20261025_1300_us4_decisions`), `POST /api/v1/venue-bookings/{id}/approve` and `/reject`, buffered conflict check on approve (D38), refusals for a passed start (`BOOKING_EXPIRED`) and for attendance over a since-reduced capacity, `Notifier.venue_booking_decided` (log-only) | **Real screens, wired to API**: Approve and Reject (with optional reason and alternative) on Venue staff's pending list; the coordinator's bookings show the decision and notes | TC-US4-01 to 11 (63 pytest + 2 E2E) + frontend unit and integration; see `docs/testing/US4-booking-decision.md` |
| SCRUM-16 — setup and turnaround buffers (US13) | Schema (PR 1, SCRUM-114): each booking stores its occupied window, `venue_bookings_no_overlap` covers it, bookings get a `VB-` reference; US2 search's booking check reads the stored window. API (PR 2, SCRUM-115): the reusable rule US4 calls (`app/venue/availability.py`), opening hours (`VENUE_OUTSIDE_HOURS`), the overlap in `VENUE_UNAVAILABLE`, Venue Staff's evaluation endpoint, the buffer-edit recompute (`VENUE_BUFFERS_CONFLICT`), US2 search with each venue's own buffers and hours. Screens (PR 3, SCRUM-116): the booking form previews the window the chosen venue's setup and turnaround occupy, with its hours; `VENUE_OUTSIDE_HOURS` shows on the time field that breaches and `VENUE_UNAVAILABLE` names the overlap period (never the other booking's reference, D35); the event's bookings panel and Venue staff's pending list show each booking's `VB-` reference and occupied window; each pending row shows its evaluation (conflicts with the overlap and the clashing reference, an hours breach, or none), fetched again after a refused approval. Approve is still offered on a row with conflicts: the API refuses it with the reason (US4 AC 3) | Done | TC-US13-01 to 19 (`docs/testing/US13-buffers.md`) |
| SCRUM-81 — sign up, log in, log out (US16a) | Schema (SCRUM-101), token check (SCRUM-102), sign-up profile endpoint (SCRUM-103), seeded Supabase logins (SCRUM-104) and `GET /api/v1/me` (SCRUM-105) done | **Login page, logout, session** (SCRUM-105); **sign-up page and first-login profile** (SCRUM-106, #75) | TC-US16A-01 to 51, all in `docs/testing/US16a-sign-up-log-in.md`. Logged-in E2E (32, 33, 35, 36, 38, 39) skips without `E2E_SEED_PASSWORD`, and sign-up E2E (40, 41, 43, 45, 50) without `SUPABASE_URL` and `SUPABASE_SECRET_KEY`, so neither runs in CI until the secrets are added (§9 Next steps); both run locally, all pass (run log in the test doc) |
| SCRUM-94 — equipment requests (US26) | Schema + seed + `tech_support` role done (SCRUM-108); endpoints done (SCRUM-109): the catalogue, a coordinator's lines on their assigned planning or confirmed event, Tech Support's queue and review, the coordinator's notice; seeds **Equipment Request Demo**; `GET /api/v1/me/equipment-events` for the screen's event picker, and a reseed empties the demo event's equipment (SCRUM-110) | **Real screens, wired to API** (SCRUM-110): **Equipment** for the coordinator (pick an event, add, edit and remove pending lines, see decisions and notes) and as Tech support's only screen (the pending queue, Approve or Reject with a note); **Acting as** gains Tech support (deviation 42) | TC-US26-01 to 20, all in `docs/testing/US26-equipment-requests.md`; 16 and 17 are E2E |
| SCRUM-82 — role-based access (US16b) | Planned 25 Oct: SCRUM-119 (roles become a list, `venue_staff` and `safety_officer`, checks on held roles, seed) and SCRUM-120 (coordinators scoped to assigned events, refusals per role); decisions D45 to D50 | SCRUM-121 (role switcher) | TC-US16B-01 to 23 in Jira and `docs/testing/US16b-role-based-access.md`; nothing built yet. Carries over to Sprint 4 |
 
Every endpoint in §3 exists, plus `POST /registrations/{id}/decline` (deviation 3 below) and `POST /registrations/{id}/accept` (deviation 13). Identity is a Supabase access token (`Authorization: Bearer`, SCRUM-102), plus two dev stubs when `AUTH_DEV_HEADERS=true`: `X-Attendee-Id` for the Sprint 1 routes and `X-User-Id` (role-aware) for the event-request, venue and equipment routes. The frontend logs in with Supabase (SCRUM-105) and shows each role only its own screens (attendees: the events board and My events; organiser, coordinator, Lead: Event requests and Venues, and the coordinator Equipment too; venue staff: Venues; Tech support: Equipment); with `VITE_DEV_AUTH=true` it skips login, sends the stubs and shows every screen. The database is the tables in §2 plus `attendees` and `users`. Backend suite: 807 tests; frontend suite (Vitest): 292 tests, 209 unit + 83 integration; E2E: 41 tests (US16a login: 9, the five logged-in ones skip without `E2E_SEED_PASSWORD`; US16a sign-up: 3, skip without `SUPABASE_URL` and `SUPABASE_SECRET_KEY`; US10a journey: organiser submits, Lead assigns, reads the history entry, finds it on the Assigned tab, filters and opens it, organiser sees the coordinator; health check, US1 journey, US8 clarification journey: ask, answer, read the thread, attendee journey: list, register, My events, withdraw; waitlist journey: leave, rejoin, see position; offer journey: freed place offered, accepted; US20 venue list and search; US20 venue staff journey: add with a field error, edit, deactivate; US1 draft round-trip: save, reload, reopen, edit, submit; events board: only open events listed, Open/Full tabs, search by title and venue, online event's join link; Acting as switch remembered across a reload; US2 venue search: seeded slot drops booked and blocked venues, filters and hours, no-match criteria and a marked bad time, organisers not offered search; US22 venue booking: request then Venue staff's pending list, capacity error and layout warning, withdraw; US4 booking decision: approve, and reject with a reason and an alternative; US26 equipment: a coordinator adds a line, fixes the quantity, edits it and removes another, and Tech support approves one with a note that the coordinator then sees; US13 buffers: the form previews the occupied window, a window past closing is refused on the end time, setup inside a seeded booking's turnaround is refused with the overlap and the touching time is accepted, with Venue staff seeing its reference, occupied window and no conflicts). **Supabase may lag `main`.** The Supabase owner applies each merged migration there right after the merge: Calvin, with Matthew covering when Calvin is away. The routine: check `alembic current` against Supabase versus `alembic heads` in the repo; run `alembic upgrade head` (never one named revision); reseed with `--yes` if the merge changed the seed (it empties Equipment Request Demo's equipment lines, and says so first); then open Supabase's Security Advisor and fix anything new it flags. The Data API stays off (§1a Environment). If a migration fails on permissions for an extension, enable it under Database → Extensions and rerun. Log: **25 Oct**, at `20261026_1200_us10d_history` (`main`'s head then): seven migrations applied, reseeded, all 10 seeded logins linked; the Data API was found on and turned off (SCRUM-117).
 
### Get it running
 
```bash
docker compose up -d postgres          # tests and local work need this
 
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # 3.12 exactly; see Environment below
pip install -e ".[dev]"
cp .env.example .env                   # keep DATABASE_URL on localhost and AUTH_DEV_HEADERS=true
alembic upgrade head                   # create the tables — the seed fails without this
pytest                                 # whole suite, seconds (tests build their own DB)
 
python -m app.seed                     # events, attendees, the organiser, a coordinator, two Coordinator Leads, venue staff, Tech Support,
                                       # six venues and the equipment catalogue;
                                       # with SUPABASE_SECRET_KEY + SEED_AUTH_PASSWORD set, also their Supabase logins
uvicorn app.main:app --reload          # http://localhost:8000/docs
 
cd ../frontend
cp .env.example .env                   # REQUIRED: VITE_DEV_USER_ID (organiser), VITE_DEV_COORDINATOR_ID, VITE_DEV_LEAD_ID, VITE_DEV_VENUE_STAFF_ID, VITE_DEV_TECH_SUPPORT_ID, VITE_DEV_ATTENDEE_ID (Calvin), VITE_DEV_AUTH=true
                                       # (backend/tests/test_dev_ids.py checks the ids match the seeded users);
                                       # plus VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY for the login page
npm install && npm run dev             # http://localhost:5173 — restart after editing .env
npm test                               # Vitest unit + integration tests; no backend needed
 
cd ../e2e && npm ci && npx playwright install chromium
npm test                               # backend must be running; don't also run npm run dev. Reseed first (python -m app.seed) on a reused database
                                       # login.spec.ts runs on a second frontend (port 5174, VITE_DEV_AUTH unset); its logged-in
                                       # cases need E2E_SEED_PASSWORD (the seeded logins' password) and SUPABASE_URL in backend/.env.
                                       # sign-up.spec.ts runs there too and needs SUPABASE_URL, SUPABASE_SECRET_KEY and E2E_SIGNUP_INBOX
                                       # (an inbox you control that accepts plus-addressing) in the environment
```

**Day to day: two terminals, left open.** `uvicorn` and `npm run dev` each keep their terminal busy until stopped, so they can't run one after the other in the same terminal. Docker's Postgres runs in the background on its own.

```bash
# Terminal 1: the API on http://localhost:8000
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload   # or .venv/bin/uvicorn without activating
# Terminal 2: the app on http://localhost:5173
cd frontend && npm run dev
```

Stop either with **Ctrl + C**. If a port is still taken by a server you can't find: `lsof -ti tcp:8000 | xargs kill` (or `tcp:5173`). Restart `npm run dev` after editing `frontend/.env`, and `uvicorn` after editing `backend/.env`: both read them only at start.

**`backend/.env` points at local Docker for day-to-day work.** Keep the Supabase `DATABASE_URL` line commented out (`#DATABASE_URL=…pooler.supabase.com…`) and the local one active (`DATABASE_URL=postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere`). Swap them only to apply `main`'s migrations to Supabase, then swap back.

**Windows (PowerShell):** activate with `.venv\Scripts\activate`; copy with `Copy-Item .env.example .env`. Create `.env` files by copying or in VS Code, not with `echo >` — PowerShell writes UTF-16, which Vite can't read.
 
`/docs` is the quickest way to see the Sprint 1 product work: withdraw a seeded registration from the full event and watch the seat pass to the next person in the queue. The seed script prints the `X-Attendee-Id` and registration ids you need, plus `VITE_DEV_USER_ID` (organiser `6c200a77-b7cc-5fb1-9d51-81a0abeba24b`, deterministic). For US1, open **Event requests** in the app, or call the event-request endpoints in `/docs` with that id in `X-User-Id`. For US8, switch **Acting as** in the header to **Coordinator** and open **Event requests** for the review queue; in `/docs` use the seeded coordinator's id (`2aac679a-f014-5437-b43a-d150447a6336`, also deterministic).
 
### When something looks broken
 
- **Every database test errors at once** → Postgres isn't running.
- **`relation … does not exist` against Supabase** → an unapplied migration, not a bug. Compare `alembic current` there with `alembic heads` here.
- **Passes locally, fails in CI** → check Python is 3.12, and see the lockfile note under Environment.
- **The page says "backend unreachable"** → the API isn't running (it needs its own terminal, see "Day to day"), or your origin isn't in `CORS_ORIGINS`. Check with `curl localhost:8000/api/events/health` (should print "event service is up") or `lsof -i tcp:8000` (should list Python). Nothing there: start `uvicorn` and keep that terminal open. If `uvicorn` exits straight away, read its last lines.
- **`relation … does not exist` locally, or the data isn't what the seed made** → `backend/.env`'s active `DATABASE_URL` points at Supabase, which can lag `main`. Comment that line out and use the local one (see "Day to day"), then `alembic upgrade head` and `python -m app.seed`.
- **Sign-up says "Check your email" but nothing arrives** → look in Spam and the Promotions tab first. Then Supabase → Logs → Auth for an SMTP error (`535` is a wrong Gmail app password), and Authentication → Rate Limits for the hourly email limit.
- **The confirmation link opens a page that can't be reached** → Supabase's Site URL isn't the app, or the app isn't running. It should be `http://localhost:5173` with `http://localhost:5173/**` and `http://localhost:5174/**` as redirect URLs (§9 Dashboard), and `npm run dev` must be running.
- **Event requests says "Set VITE_DEV_USER_ID…"** → `frontend/.env` doesn't exist (only `.env.example` does). Copy it and restart `npm run dev`.
- **The app shows a Log in page locally** → `frontend/.env` predates SCRUM-105, so `VITE_DEV_AUTH` is missing and login is required. Add `VITE_DEV_AUTH=true` for dev mode (Acting as), or log in with a seeded account. Restart `npm run dev`.
- **The login page says "Login isn't set up"** → add `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` (Project Settings → API Keys, `sb_publishable_…`) to `frontend/.env` and restart `npm run dev`.
- **The review queue says "Set VITE_DEV_COORDINATOR_ID…"** → your `frontend/.env` predates SCRUM-57. Copy that line from `.env.example` and restart `npm run dev`.
- **Equipment, acting as Tech support, says "Set the dev user id…"** → your `frontend/.env` predates SCRUM-110. Copy `VITE_DEV_TECH_SUPPORT_ID` from `.env.example` (the seeded Tech Support user); Vite restarts itself when `.env` changes.
- **The events board or My events says "Set VITE_DEV_ATTENDEE_ID…"** → your `frontend/.env` predates SCRUM-79. Copy that line from `.env.example` (seeded attendee Calvin, `83565d3f-e757-5c0e-8c6e-8dadb298ce18`) and restart `npm run dev`.
- **The attendee E2E fails at its first step (Tech Talk not "You're registered")** → it ran before against this database and left Calvin withdrawn. Run `python -m app.seed`, then rerun.
- **`python -m app.seed` fails on `registrations_one_active_per_attendee`** → fixed in SCRUM-79: the seed now withdraws any other active row for a seeded (event, attendee) pair, such as one made by withdrawing and registering again in the app, before resetting its own row. If you still see it, your `backend` predates that change.
- **CORS errors even on `/api/events/health`** → something else is answering on port 8000 (open the health URL directly; "no Route matched" means another app), or a terminal still has a leftover `CORS_ORIGINS`. Close all terminals and start fresh.
- **Event requests says "Set VITE_DEV_LEAD_ID…" when acting as Coordinator Lead** → your `frontend/.env` predates SCRUM-13. Copy `VITE_DEV_LEAD_ID` from `.env.example` (seeded Lead one, `78c61ada-12c1-543f-8838-d559f1ece279`), run `python -m app.seed` if that user is missing, and restart `npm run dev`.
- **Venues says "Set the dev user id…" when acting as Venue staff** → your `frontend/.env` predates SCRUM-87 PR 2. Copy `VITE_DEV_VENUE_STAFF_ID` from `.env.example` (seeded venue staff, `4e8d2398-4b1e-5e59-900e-4ddb311a243f`), run `python -m app.seed` if that user is missing, and restart `npm run dev`.
- **Every screen gets `401` after pulling SCRUM-102** → your `backend/.env` predates it, so the header stubs are off. Add `AUTH_DEV_HEADERS=true` (and `SUPABASE_URL`) from `.env.example` and restart uvicorn.
- **Every login token gets `500 AUTH_NOT_CONFIGURED`** → `SUPABASE_URL` isn't set in `backend/.env`. **`503 AUTH_UNAVAILABLE`** → the backend can't reach Supabase's public keys: check the network, then the URL. The uvicorn log says which (refusals are logged with their reason, never the token).
- **Every login token gets `401` on macOS** → read the uvicorn log for the reason. The key fetch uses certifi's CA bundle because python.org's macOS Python ships without one; if you replaced that, run its "Install Certificates.command".
- **`401` on `/api/v1/me/event-requests`** → the organiser isn't in the database uvicorn is using. Run `alembic upgrade head` and `python -m app.seed`; check no terminal has a leftover `DATABASE_URL` (`echo $env:DATABASE_URL`).
- **`python -m app.seed` fails with `relation … does not exist`** → you skipped `alembic upgrade head`.
- **An E2E test fails locally but passes in CI, around seeded events** (e.g. Design Sprint Bootcamp not showing "waitlist open") → the seed changed since you last ran it; your local rows are stale. Run `python -m app.seed` again — CI always seeds fresh.
- **Ports 5173 / 8000 are taken by another project** → stop it, or for E2E set `E2E_FRONTEND_PORT` (and matching `VITE_API_BASE_URL` / `CORS_ORIGINS`).
- **A PR check fails instantly** → the title needs a `feat:` / `fix:` / `chore:` prefix.
- **A PR check hangs** → E2E waits on the backend's health endpoint; read the "Backend log" step.
 
### Rules that keep us out of trouble
 
- **One shared Supabase.** Branch work points `DATABASE_URL` at local Docker Postgres. Only `main` is applied to Supabase, by the Supabase owner (Calvin; Matthew when Calvin is away), right after the merge, following the routine in "Supabase may lag `main`" above. Running `alembic upgrade head` from a branch changes the schema for the whole team before review.
- **Every schema change is a migration in the repo.** Nothing is created by clicking in the Supabase dashboard, or the next person's `alembic upgrade` fails on a table that already exists.
- **One migration head.** If two branches each add a migration, Alembic ends up with two heads on merge. Rebase on `main` and regenerate rather than merging heads.
- **Tests never touch Supabase.** They build a separate `connectsphere_test` database from the migrations and refuse to run against a non-local host. Keep that guard.
- **Deviating from §2/§3 is allowed; doing it silently is not.** Add a `# DECISION-PENDING: <id>` at the code site and a line under "Deviations awaiting a decision" below.
- **New screens call the real API** (changed in Sprint 2 — the Sprint 1 "mockups stay mockups" rule is retired; *needs team confirmation*). Build through `frontend/src/api/client.ts`, with TypeScript types that match the API's snake_case names. Don't add new mock data.
- **Two identity headers, one per route family.** Sprint 1 routes take `X-Attendee-Id` (`get_current_attendee`); event-request and venue routes take `X-User-Id` (`get_current_user` / `require_user_roles`). Every attendee has a `users` row with the **same id** and role `attendee`, so one id works in both. In the frontend, `apiClient` sends `X-User-Id` by default and `X-Attendee-Id` (from `VITE_DEV_ATTENDEE_ID`) when a call passes `identity` `"attendee"`, as every call in `features/registration/api.ts` does (SCRUM-79). Since SCRUM-102 both stubs work **only when `AUTH_DEV_HEADERS=true`** (local dev, tests via `conftest.py`, CI E2E); otherwise only `Authorization: Bearer <Supabase token>` identifies the caller. A token that fails verification is `401`, never a fallback to a stub.
- **New roles arrive with US16b (SCRUM-82):** `venue_staff`, `tech_support`, `safety_officer`. `coordinator_lead` was added early by US10a's migration (`20261022_1300_us10a_coordinator`) because SCRUM-13 needs it first, so SCRUM-82 must not add it again. Until then the enum is `organiser`, `coordinator`, `coordinator_lead`, `operations_manager`, `attendee`, and `operations_manager` stands in for Venue Staff on the venue routes (D19). Exception: `tech_support` arrived early with SCRUM-108 (US26) under the planned name, so US26's review routes check a real role (deviation 34); US16b keeps it and adds the rest.
- **Another person's record is `404 NOT_FOUND`, never `403`.** Applies to drafts as well as registrations (TC-US7-02, TC-US1-13).
- **Schema changes go in the first PR of a story, alone.** US1 split into schema → API → screens PRs; the API and screen PRs added no migration. Keeps one Alembic head and a reviewable migration.
- **E2E specs share one seeded database and run in parallel.** `attendee-registration.spec.ts` is the only spec that changes seeded registrations (serial within itself); others either only read seeded rows that it never touches (`events-board.spec.ts`, `venue-search.spec.ts`) or create their own uniquely named rows (`event-request*.spec.ts`, `clarification-request.spec.ts`, `venue-catalogue.spec.ts`, `venue-booking*.spec.ts`). Keep a new spec in one of those two kinds, or it will flake against the attendee journeys.
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
| 13 | `POST /registrations/{id}/accept` (US6b) isn't in §3's original list, and adds `409 OFFER_EXPIRED` for an offer past `offer_expires_at` that the manual expiry (D2) hasn't swept yet — accepting it could overbook, since a lapsed offer no longer holds its seat | `app/registration/service.py` |
| 14 | New error code `NO_OPEN_CLARIFICATION` (409, with the request's current `status`) when the organiser answers outside `awaiting_clarification`, including a second answer to the same round | `app/event/clarification_service.py` |
| 15 | `GET /me/registrations` has a third section, `offered`, not in §3's original shape: live offers with `offer_expires_at`, so the attendee sees the place on screen (D5). It's additive; the notifier also now receives the `registration_id` to accept with | `app/registration/service.py`, `app/notification/service.py` |
| 16 | US6a (SCRUM-48, 49): `EVENT_FULL`'s `waitlist_available` can now be `false` (message "This event is full."), and `POST /events/{id}/waitlist` has two new 409 codes: `WAITLIST_NOT_ENABLED` (the event's waitlist is off; checked first) and `SEATS_AVAILABLE` (places remain, so register instead) | `app/registration/service.py` |
| 17 | SCRUM-79 dropped what the mock showed but the API doesn't return: event category (label, icon, coloured thumb), description, the attendee name/email inputs and the name on the ticket (identity is `X-Attendee-Id`). The "Waitlist only" tab and card label are now **Full**, since `/events/available` doesn't say whether a waitlist exists. The ticket's confirmation code is a **booking reference** derived from `registration_id` (first 8 hex characters, uppercased); the API has no code. Times show in Asia/Singapore. A waitlisted event's card says "You're on the waitlist (#position)" and its dialog "You're on the waitlist for this event. Find it under My events.", matched through the new `event_id` on `GET /me/registrations` rows (additive backend change, TC-US11-12); confirmed events keep "You're registered". SCRUM-52: a full event that takes a waitlist says **"Full · waitlist open"** on its card (plain "Full" otherwise), and its dialog asks for an **email** to join, since the frontend has no attendee profile and the join route takes only an email (D7) | `frontend/src/features/registration/`, `app/registration/schemas.py` |
| 18 | `GET /events/available` gains `waitlist_available` per event (SCRUM-52, additive): `registration_service.waitlist_available`, the same rule and name as `EVENT_FULL`'s flag, so the board offers "Join the waitlist" up front instead of after a failed register (TC-US6A-10) | `app/event/service.py`, `app/event/schemas.py` |
| 19 | New error codes for tokens (SCRUM-102): `PROFILE_REQUIRED` (403), a valid Supabase token with no `users` row, so signed up and confirmed but no profile yet (TC-US16A-12; §9 first said such a caller is created as an attendee; the first login creates the profile instead, SCRUM-103); `AUTH_UNAVAILABLE` (503), Supabase's keys unreachable, so the frontend doesn't log everyone out (TC-US16A-46); `AUTH_NOT_CONFIGURED` (500), `SUPABASE_URL` unset (TC-US16A-47) | `app/user/dependencies.py`, `app/user/auth.py` |
| 20 | First login links an unlinked row by email **only for an active Organiser or Attendee, and only when the token says the email is verified** (SCRUM-102, TC-US16A-06; PR #55 review). Supabase "Confirm email" is **on**, so a token only exists for an email its owner confirmed (US16a AC 6 changed 16 Oct). Staff rows are never linked by email; the seed links them (SCRUM-104) | `app/user/dependencies.py` |
| 21 | New error code `INVALID_VENUE` (422, with `fields` and `errors`: a message per field) for present-but-invalid venue values: capacity ≤ 0, closing not after opening, negative buffers, blank name or location, a tag outside D18's lists (on a write or a list filter). A missing or nulled required field is `MISSING_REQUIRED_FIELD` (SCRUM-87, AC 4) | `app/venue/service.py` |
| 22 | New error code `VENUE_BUFFERS_LOCKED` (409, with `fields` and `message`) when an edit changes `setup_minutes` or `turnaround_minutes` while the venue has approved future bookings (AC 2). Since US22 PR 1 (SCRUM-111), `has_approved_future_bookings` queries `venue_bookings`: an Approved booking at the venue ending after now, including one under way. Since US4 (SCRUM-8), approving a booking makes it reachable in the product | `app/venue/service.py` |
| 23 | New error codes for `POST /api/v1/auth/profile` (SCRUM-103): `INVALID_ROLE` (422), a role other than `organiser` or `attendee` (US16a AC 7); `EMAIL_ALREADY_REGISTERED` (409), any `users` row already has this account's id or email, seeded staff included, also returned when a simultaneous call wins the race. Numbered 23 because #60 (US20) takes 21 and 22 | `app/user/service.py` |
| 24 | New error code `EVENT_NOT_BOOKABLE` (409, with the event's current `status`) when a venue is requested for an event that isn't `approved` or `planning` (US22 AC 1). A **draft** is `404 NOT_FOUND` instead, because it's owner-only (D11) and a 409 would reveal it exists | `app/venue/booking_service.py` |
| 25 | New error code `INVALID_BOOKING` (422, with `fields` and `errors`, a message per field, every field at once, like `INVALID_VENUE`) for present-but-invalid booking values: a time without a timezone offset, end not after start, a start in the past, attendance < 1, a layout or tag outside D18's lists. Missing fields are `MISSING_REQUIRED_FIELD` | `app/venue/booking_service.py` |
| 26 | New error code `VENUE_CAPACITY_EXCEEDED` (422, with `fields: ["expected_attendees"]`, the venue's `capacity` and a `message`) when expected attendance is above capacity (AC 3). Equal to capacity is accepted | `app/venue/booking_service.py` |
| 27 | New error code `VENUE_UNAVAILABLE` (409, with `conflict: {starts_at, ends_at}` of the clashing booking or venue block, ISO 8601 in UTC, and a `message`) when the window overlaps a Requested or Approved booking or a `venue_blocks` row at that venue, even by one second; back-to-back is allowed (AC 3, AC 7; D21, D22). A booking is reported before a block; the message says "already booked" for one and "unavailable" for the other. A request the database refuses in a race gets the same answer: the exclusion constraint once the winner commits, or, if the two inserts deadlock, one retry and then this. Two deadlocks in a row answer it without `conflict`. **Since US13 PR 2** the clash is on occupied windows (D22), `conflict` also carries `kind` (`booking` or `block`), `occupied` (the clashing booking's window with its buffers) and `overlap` (the exact shared period, AC 4), and the body carries the request's own `occupied` window; `starts_at`/`ends_at` stay the clashing booking's or block's own times. No reference (D35) | `app/venue/booking_service.py` |
| 28 | New error code `BOOKING_NOT_PENDING` (409, with the booking's current `status`) when withdrawing a booking that isn't `requested` (AC 5) | `app/venue/booking_service.py` |
| 29 | `POST /api/v1/venue-bookings` returns `warnings` (`[{field, item, message}]`) for each required facility or accessibility feature the venue lacks, and for a layout it doesn't offer; the request still saves (AC 3). Warnings aren't stored. And `GET /api/v1/venues/{id}` now shows an **inactive** venue to the coordinator assigned to an event with a live (Requested or Approved) booking there (D20, since US10a), closing US20's gap; everyone else still gets `404`, and the venue still leaves their list | `app/venue/booking_service.py`, `app/venue/service.py` |
| 30 | `venue_blocks` (US2, SCRUM-7) is in no earlier §: AC 5's "blocked" venue has no event behind it, so it can't be a `venue_bookings` row (event and requester required). Minimal: `venue_id`, `starts_at`, `ends_at`, `note`. Blocks may overlap each other and bookings. US23a (SCRUM-90, CR-02) adds Venue Staff's screens for it. Numbered 30 because US22 PR 2 takes 24 to 29 | `app/venue/models.py`, migration `20261022_1200_us2_venue_blocks` |
| 31 | New error code `INVALID_VENUE_SEARCH` (422, with `fields` and `errors`) on `GET /api/v1/venues/available` for a past date, end not after start, attendance below 1 or not a whole number, or an unknown tag. `attendees` is read as text so `1.5` is this error on `attendees`, not FastAPI's generic 422. Missing criteria are `MISSING_REQUIRED_FIELD` | `app/venue/service.py` |
| 32 | US22's screens (SCRUM-113). **Where:** Request venue and the event's bookings appear on an **Approved** request opened from the coordinator's review queue, the only place a coordinator sees an Approved event; a **Planning** event can't be reached in the app, because D11 hides it from coordinators. **Still open after #68 (US10a):** AC 1 allows Planning events too, but US10a didn't widen D11, so a Planning event is still out of reach; once D11 covers it, the panel should show there too. **Who:** only the event's assigned coordinator may book it (D20, since US10a). The review queue still lists every Approved request to every coordinator, so on an **unassigned** one the panel says no coordinator is assigned yet, and on one assigned to someone else (the API answers `404`) it names that coordinator; neither shows Request venue. Venue staff see the pending list at the top of Venues. **How:** date and times are Singapore wall-clock, sent as ISO 8601 with `+08:00` (D9); the form starts from the request's first preferred date, times and attendance; before sending it lists what the chosen venue lacks of the required facilities, accessibility and layout but never blocks (AC 3), and after booking it shows the API's `warnings`. The layout field is labelled **Layout**, not Room layout, because the review screen already has a Room layout section checkbox. Withdraw asks first (PR #69 review), like the registration WithdrawDialog: the dialog says the window is released to any coordinator at once, and nothing is sent until **Withdraw request**; a refusal (e.g. `BOOKING_NOT_PENDING`) is explained in the dialog while the list reloads behind it. A withdrawn window can be requested again | `frontend/src/features/venue/EventVenueBookings.tsx`, `VenueBookingForm.tsx`, `PendingBookings.tsx` |
| 33 | US4 (SCRUM-8) adds `POST /api/v1/venue-bookings/{id}/approve` and `/reject` (Venue Staff, D19), not in §3 before. `BOOKING_NOT_PENDING` (409) for a booking that isn't `requested`. On approve only: `VENUE_UNAVAILABLE` (409, with `conflict` and `message`) for a clash of the stored occupied window with another live booking or a block, or an inactive venue (D38, D39), plus `buffers: true` when the clash is only with the setup and turnaround, whose message reads "Too close to a booking (or a venue closure) … to fit the venue's setup and turnaround" rather than "already booked"; `VENUE_CAPACITY_EXCEEDED` (409, with `capacity`) when the venue's capacity was cut below the attendance after the request; `EVENT_NOT_BOOKABLE` (409) when the event has left Approved/Planning; and the **new code `BOOKING_EXPIRED`** (409, with `message`) once the request's start has passed, since pending requests don't expire until US25. Each refusal leaves the request pending, to be rejected (PR #73 review). Reject notes are at most 1,000 characters each. Approve takes no body fields and reject only `reason` and `alternative_suggestion`; anything else is FastAPI's `422`, which is how "no override" (AC 3) and "no partial approval" (AC 7) are enforced. Bookings gain `decided_at`, `decided_by_user_id`, `rejection_reason`, `alternative_suggestion` in every response | `app/venue/booking_service.py`, `app/venue/booking_router.py` |
| 34 | `tech_support` added to `user_role` by SCRUM-108 (US26) ahead of US16b (SCRUM-82), using the name §1a already planned, so Tech Support's routes check a real role instead of a stand-in (D19 already makes `operations_manager` mean two jobs). The seed adds `tech.support@smu.edu.sg`. Postgres can't drop an enum value, so the US26 downgrade leaves it | `migrations/versions/20261025_1200_us26_equipment.py`, `app/user/models.py` |
| 35 | US10d's screen (SCRUM-66). The Lead reaches an event's history with **History** on a row of the Assigned tab (US19, SCRUM-86) or **View assignment history** after assigning. Because the Assigned tab lists Planning and Confirmed events too (D44), the Lead's own events are no longer cut off at `rejected` as D11 does for the review queue | `frontend/src/features/eventRequest/AssignmentQueuePage.tsx` |
| 36 | New error code `INVALID_EQUIPMENT_LINE` (422, with `fields` and `errors`) when a line's type is missing or not in the catalogue, or its quantity is missing, not a whole number or below 1 (US26 AC 4, TC-US26-07). One code for missing and invalid, since a line has only two checked fields. The type and quantity are read unchecked, so `1.5` or `"two"` is this error on `quantity`, not FastAPI's generic 422 | `app/equipment/service.py` |
| 37 | New error code `LINE_NOT_PENDING` (409, with the line's current `status`) when a coordinator edits or removes, or Tech Support reviews, a line that is already approved or rejected (AC 2, 3) | `app/equipment/service.py` |
| 38 | New error code `EVENT_NOT_ELIGIBLE` (409, with the event's current `status`) when a line is added to an event that isn't `planning` or `confirmed` (SCRUM-109, TC-US26-10). A draft is `404`, as for venue bookings (D11). Only adding checks the event's status; editing and removing a pending line don't | `app/equipment/service.py` |
| 39 | New error code `DUPLICATE_EQUIPMENT_TYPE` (409, with `fields: ["equipment_type_id"]` and a `message`) when adding a line, or changing a line's type, would give the event a second pending or approved line of that type (D41, TC-US26-19). Checked first; two requests at the same moment are settled by `equipment_request_lines_one_live_per_type`, and the loser gets the same answer | `app/equipment/service.py` |
| 40 | US19's screens (SCRUM-86). **Tabs:** Unassigned (the existing queue, still first and shared by all Leads) and Assigned. **Read-only view** (AC 4): **View** on a row opens the request's fields from the list row, with no editing and no approve, reject or confirm action (those belong to other roles). On an unassigned request it offers **Assign a coordinator**; on an assigned one it offers **Assignment history**. **Reassign is not offered yet**: reassigning is US10e (SCRUM-83), which should add its button to this view. **Supervisory scope** (AC 6): no separate column or table; a Lead's scope is the events they assigned, read from `coordinator_assignments` (D44), so any number of Leads works and none is hard-coded. A broader scope would need a decision | `frontend/src/features/eventRequest/AssignmentQueuePage.tsx`, `LeadRequestDetail.tsx` |
| 41 | New endpoint `GET /api/v1/me/equipment-events` (SCRUM-110, TC-US26-20): `{"events": [{id, name, start_at, status}]}`, the caller's own assigned events in `planning` or `confirmed`, using SCRUM-109's eligibility rule (`ELIGIBLE_STATUSES`): those not over yet first, soonest first, then ended ones, most recent first (PR #78 review). Ended ones stay listed because the API still takes lines for them (the rule is status only); only the order keeps last month's event off the top. Coordinator only. US26's screen needs it to pick an event, and no other route lists a coordinator's planning or confirmed events: D11 hides them from the event-request routes | `app/equipment/service.py`, `app/equipment/router.py` |
| 42 | US26's screens (SCRUM-110). **Where:** a new **Equipment** screen in the header: the coordinator's (after Event requests and Venues) and Tech support's only screen, so a logged-in Tech Support user no longer sees "no screens yet". In dev mode, **Acting as** gains Tech support (`VITE_DEV_TECH_SUPPORT_ID`); other roles opening Equipment, and Tech support opening Event requests, are told it isn't their role's. **Coordinator:** pick an event (deviation 41), see its lines with status and Tech support's note, add a line (type from the catalogue, quantity, notes), and edit or remove a pending one. The quantity and type are sent as typed, so the API's `INVALID_EQUIPMENT_LINE` and `DUPLICATE_EQUIPMENT_TYPE` show beside their field; the screen doesn't repeat the rules. Remove asks first, like Withdraw on a venue request (PR #69 review). **Tech support:** the pending queue, oldest first, each with its event, date, quantity and notes, a note box, and **Approve** / **Reject** (the note is optional, D43); a decided line leaves the queue, and a refused review (e.g. `LINE_NOT_PENDING`) is explained and the queue reloads. **Stale lines (PR #78 review):** approval is always the line's current quantity (AC 6) and the coordinator can edit a pending line after the queue loaded, so Approve and Reject first reload the queue; if the line changed (`updated_at`) or left it, nothing is sent and the screen shows it as it is now. A change in the moment between that check and the review isn't caught; closing it would need the review to carry the version it saw | `frontend/src/features/equipment/` |
| 43 | New error code `VENUE_OUTSIDE_HOURS` (422, with `fields` naming the end that breaches, `opens_at`, `closes_at`, the request's `occupied` window and a `message`) when a booking request's occupied window starts before the venue opens or ends after it closes, or crosses midnight (US13 AC 5, D32). Checked before overlaps. Approval (US4) refuses the same way with `409` instead, on the booking's stored occupied window: it has no body to be wrong, and like US4's capacity re-check it's the booking's state now that stands in the way | `app/venue/booking_service.py`, `app/venue/availability.py` |
| 44 | New error code `VENUE_BUFFERS_CONFLICT` (409, with `fields`, `bookings`: each clashing Requested booking's `reference`, times, recomputed `occupied` window and `reason`, and a `message`) when a venue's buffer edit would make its live future Requested bookings overlap or run outside hours (US13, D31). Nothing is saved | `app/venue/service.py` |

### Open decisions still unanswered

§6 defines D1–D6 and a Sprint 1 default for each. All six are coded to their defaults and marked in the code; **none has been confirmed by the team**. D7 is new and not in §6. D8–D12 came from US1 and D13–D15 from US8 and D16–D17 from US6a; D18–D19 from US20; D20–D24 from US22; D25–D26 from US2; D27–D28 from US10a; D30 from SCRUM-67; D31–D37 from US13 (the story owner's choices, awaiting the team); D41 and D43 from US26; D42 from US10d; D44 from US19; D45–D50 from US16b (the story owner's decisions of 25 Oct, reasoning in §9 "US16b role-based access: decisions"; D47 still needs the PO); all are marked `DECISION-PENDING` in the code (D20 from US22 PR 2, where its check lives), **except D21, which the team has decided** (no longer marked).
 
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
| D11 | Who can read a submitted request? | Owner, coordinators, Event Coordinator Leads (`coordinator_lead`, since US10a) and `operations_manager` (the Venue Staff stand-in, D19), **only while in a request status** (submitted → rejected). Other organisers 404. Drafts owner-only **Planned (US16b, SCRUM-120): coordinators narrowed to their assigned requests (D48).** |
| D12 | How are users identified before Supabase Auth? | `X-User-Id` header stub, alongside `X-Attendee-Id`. The frontend's **Acting as** switch (header) sends the seeded organiser's or coordinator's id from `frontend/.env`; the choice is kept in `localStorage`. Since SCRUM-102 the stubs are dev-only, behind `AUTH_DEV_HEADERS` (default off) |
| D13 | Which sections can a clarification request tag? | SCRUM-11 only gives examples (attendance, layout, equipment). Assumed seven, grouping the US1 fields: `details`, `schedule`, `attendance`, `layout`, `accessibility`, `equipment`, `registration`. One list in `CLARIFICATION_SECTIONS`, mirrored by the migration's CHECK |
| D14 | Which coordinator may ask for clarification? | Any active coordinator. US10a (SCRUM-13) assigns a coordinator to a request, using US16b's (SCRUM-82) roles; tighten this to the assigned one then. SCRUM-13 PR 2 assigns but did not tighten it (the ticket doesn't ask), so a follow-up must decide **Planned (US16b, SCRUM-120): retired, only the assigned coordinator (D48).** |
| D15 | When may a coordinator send another clarification round? | From `submitted` or `under_review`, no limit; the new round is `max(round) + 1`. `awaiting_clarification`, `approved`, `rejected` → `409 CLARIFICATION_NOT_ALLOWED`. `awaiting_clarification` is blocked on purpose: the organiser's reply answers the latest open round, so a second open question would never get its own answer. Past the request stage (`planning` → `completed`) and drafts stay `404` under D11. `CLARIFIABLE_STATUSES` in `clarification_service.py`. **Differs from SCRUM-75 AC 1, which allows another round while Awaiting Clarification. Confirm with the team.** |
| D16 | Does joining a waitlist need registration to be open? | Yes. US6a AC 1's "reached its registration capacity" presumes it, so `join_waitlist` applies register's gates (`_check_registration_open`): `403 REGISTRATION_NOT_ENABLED` unless confirmed with registration enabled, `403 REGISTRATION_CLOSED` outside the window |
| D17 | What happens to people already queued if an event's waitlist is switched off? | They keep their place and still get offers: `offer_freed_seat` ignores `waitlist_enabled`, because US6a only governs joining |
| D18 | Which tags can a venue's facilities, accessibility features and room layouts use? | SCRUM-87 only gives examples. Assumed fixed lists, so US2's filters and the venue form agree on spelling. Facilities: `projector`, `screen`, `sound_system`, `microphone`, `stage`, `wifi`, `whiteboard`, `video_conferencing`, `power_outlets`. Accessibility: `wheelchair`, `lift`, `accessible_toilet`, `hearing_loop`, `step_free_entrance`. Layouts: `theatre`, `classroom`, `banquet`, `boardroom`, `u_shape`, `cabaret`, `standing`. Constants in `app/venue/models.py`, mirrored by the migration's CHECKs |
| D19 | Who stands in for Venue Staff before US16b adds the role? | `operations_manager`, one constant `VENUE_STAFF_ROLES` in `app/venue/service.py`; US16b changes it to `venue_staff`. The seed adds `venue.staff@smu.edu.sg` with that role, and **Acting as → Venue staff** sends its id. `operations_manager` stays a Venue Staff stand-in only: US10a (SCRUM-13) gave the Coordinator Lead its own `coordinator_lead` role and seeded two Leads, so the roles are already split. The venue staff user can read the event-request queue (D11). A Lead can no longer create, edit or deactivate venues, and gets `403` on the venue write routes. US22's booking notices go to Venue Staff (`operations_manager`) only, so Leads don't get them **Planned (US16b, SCRUM-119): retired, `venue_staff` replaces it (D49).** |
| D20 | Who may request a venue for an event, and see its bookings? | **Since US10a (SCRUM-13): only the coordinator assigned to the event** (`events.coordinator_id`), as AC 1 says, for an Approved or Planning event: `may_book` (`app/venue/booking_service.py`). A coordinator not assigned to it, and anyone on an **unassigned** event, is refused as before: `404 NOT_FOUND` on create and on the event's booking list. Venue Staff still read any event's bookings. The inactive-venue read (`_has_live_booking_by`, `app/venue/service.py`) widened from "requested the booking" to "assigned to its event", whoever made the request. Before US10a any coordinator could book. **Still to confirm:** withdrawing stays with the coordinator who made the request, even if the event is later reassigned. **US26 (SCRUM-109) uses the same rule for equipment lines** (`may_manage`, `app/equipment/service.py`): only the event's assigned coordinator lists, adds, edits and removes them, whoever added the line; anyone else gets `404`. This replaces the ticket's earlier interim "any active coordinator, as D14", which assumed coordinators weren't assigned yet |
| D21 | Does a pending (Requested) booking block the window? | **Decided by the team:** yes, Requested and Approved both block. Based on the sessions 1–2 clarification behind AC 7: "any overlap is prevented; first come, first served". AC 3 names only approved bookings, but first come, first served needs a pending request to hold the window too. `LIVE_BOOKING_STATUSES` (`app/venue/models.py`) and the exclusion constraint `venue_bookings_no_overlap` enforce it, which also settles AC 7's race |
| D22 | What window does the overlap check use? | **Since US13 PR 1 (SCRUM-114), the occupied window** `[starts_at − setup, ends_at + turnaround)`, from the venue's buffers when the booking is made, stored on the booking (`occupied_starts_at`, `occupied_ends_at`) because an exclusion constraint can't read `venues`. Windows that only touch don't clash. Since PR 2 (SCRUM-115) the stored windows are recomputed when buffers change (D31) and the occupied window must fit the opening hours (D32). Before US13 it was the plain `[starts_at, ends_at)`. Unavailability is US2's `venue_blocks` (deviation 30): a request overlapping a block is refused by the same rule. Bookings are kept apart by the exclusion constraint, but blocks only by the service's check (`_block_conflicts` in `app/venue/availability.py`, against the booking's occupied window; blocks have no buffers of their own), so a block added while a request is in flight isn't seen; US23a (SCRUM-90), which adds the block screens, should lock the venue row `FOR UPDATE` so requests (which read it `FOR SHARE`) wait. Holds (US25, SCRUM-93) don't exist yet and extend the check when they land |
| D23 | How does a request say which facilities and accessibility it needs? | D18 tag lists on the booking (`required_facilities`, `required_accessibility_features`), because the event's `equipment_needs` and `accessibility_needs` are free text and can't be matched against a venue |
| D24 | How do events reach Approved before US17? | They don't in the product. US17 (SCRUM-84) approves requests; tests and the seed put events straight into `approved` |
| D25 | Who may search for available venues (US2)? | `coordinator`, plus `operations_manager` (standing in for Venue Staff, D19); the Coordinator Lead, organisers and attendees `403`. One constant, `VENUE_SEARCH_ROLES` in `app/venue/service.py`. US16b should give it `venue_staff`, and decide whether the Lead may search |
| D26 | Does venue search apply setup and turnaround buffers around bookings? | **Partly since US13 PR 1:** an existing booking takes up its stored occupied window (its venue's buffers), the range the exclusion constraint's GiST index holds, so a venue whose booking's setup or turnaround overlaps the searched time is left out. **Since US13 PR 2 (SCRUM-115)** the searched venue's own buffers apply too: a venue is offered only if the window they make it occupy for that time, `[start − setup, end + turnaround)`, is free of live bookings' stored windows and of blocks, and inside its opening hours (confirmed by the story owner). Built per venue in the one query; each `EXISTS` carries `OFFSET 0` so Postgres keeps it a per-venue subplan on the GiST indexes (TC-US2-08). Blocks have no buffers of their own |
| D27 | What status does assigning a coordinator leave the request in? | `under_review`, not `planning` as SCRUM-61's wording says. AC 3 assigns only from `submitted`; AC 10 needs assigned requests to stay at the request stage; approval (US17, SCRUM-84) is what leads to `planning`, which D11 hides from coordinators. Assigning is also what moves a request from Submitted to Under Review, which nothing did before. `assignment_service.assign` |
| D28 | Which Leads are told when a request joins the unassigned queue (SCRUM-13 AC 11)? | Every active user with role `coordinator_lead`, once each, since there can be more than one Lead (SCRUM-82 AC 7). No active Lead logs a warning and the request is still queued. This is not SCRUM-68, which tells the coordinator and organiser about an assignment |
| D29 | What "event date" does the assignment notice carry (SCRUM-68 AC 1, 2)? | The request's `preferred_dates`: a request has no confirmed date (`start_at`) until much later, and the Coordinator and Organiser are told at assignment. Revisit if the team wants the notice to wait for a confirmed date. Recipients are the assigned Coordinator and the submitting Organiser only; other Leads are not told (the ticket leaves that optional). Log-only, like the other notices |
| D30 | What does the picker's workload count (SCRUM-67 AC 1, 2) count? | Events the coordinator owns in `under_review`, `awaiting_clarification`, `approved` or `planning`, 0 when none. Counting only `planning` is what the ticket words say, but an assignment leaves the request `under_review` (D27), so that count would not rise after assigning (AC 3) until approval moves it to `planning` (SCRUM-84). `rejected`, `confirmed`, `cancelled` and `completed` events are not counted. Field name `planning_count` keeps the ticket's wording. `WORKLOAD_STATUSES` in `assignment_service.py`. Raise with the PO alongside D27 |
| D31 | What happens to Requested bookings' stored occupied windows when a venue's buffers change (US13)? | The story owner's choice (24 Oct): recompute them in the same transaction as the venue edit, and refuse the edit with `409 VENUE_BUFFERS_CONFLICT` if any would then clash or run outside hours (built in PR 2: `_recompute_windows` in `app/venue/service.py`). AC 6's lock (`VENUE_BUFFERS_LOCKED`) is checked first and still covers approved future bookings. Live future Requested bookings are recomputed (ends after now); past ones keep their windows. The new windows are written in two steps (PR #79 review): each is first shrunk to its booking's own times and flushed, then widened, because `venue_bookings_no_overlap` is checked row by row and a new window can clash with another booking's old one (e.g. 0/30 to 30/0 between touching bookings). An hours edit alone recomputes nothing (D37) |
| D32 | When does US13 AC 5 (occupied window inside opening hours) apply? | At request time too (`422 VENUE_OUTSIDE_HOURS`, checked before overlaps), and again at approval: US4's approve calls `evaluate_booking`, which checks the booking's stored occupied window against the hours now (`409 VENUE_OUTSIDE_HOURS`, deviation 43), since hours can change. Compared as instants on the booking's Singapore day, so a window crossing midnight is outside them |
| D33 | What is a booking's reference (US13 AC 4)? | `VB-<year>-<6 digits>`, the year it was made in Singapore, from `next_venue_booking_reference()`, the column's default, so every insert gets one. Not the event's `ER-` reference, which an approved seeded event may not have. Existing bookings were numbered in the order they were made |
| D34 | What if the buffers make existing live bookings overlap? | The US13 migration refuses and names each pair; a person withdraws or rejects one of each, then reruns. CR-01 says such bookings are identified, not removed, and an exclusion constraint can't be added `NOT VALID` |
| D35 | What does a coordinator see when a request clashes (US13 AC 4)? | The overlap period and the kind of clash (`conflict.kind`, `conflict.occupied`, `conflict.overlap` in `VENUE_UNAVAILABLE`), but not the other booking's reference, which AC 4 gives to Venue Staff through the evaluation (D36) |
| D36 | How does AC 4 reach Venue Staff before US4 (approval) exists? | `GET /api/v1/venue-bookings/{id}/evaluation` (Venue Staff only, PR 2): each conflict with its overlap and reference, and any hours breach; PR 3 shows it on the pending list |
| D37 | Does US13 build US20's deferred flag-and-notify on hours or capacity edits? | No. US13 AC 5 at approval covers hours; capacity is US22's create check |
| D38 | Which window does approving a booking check (US4 AC 3)? | **Since US13 (#71) merged, the booking's stored occupied window** (`occupied_starts_at`, `occupied_ends_at`: setup before, turnaround after, D22), against every other live (Requested or Approved) booking's occupied window and any venue block. `venue_bookings_no_overlap` already keeps live bookings' occupied windows apart, so for bookings this is a backstop for older rows; the block half is the real check, since blocks are only ever checked by the service (D22) and one may have been added since the request. A clash that's only in the buffers carries `buffers: true` and a "Too close to …" message. The venue row is locked `FOR UPDATE` so an edit or a new request waits for the decision. Approval calls US13's `evaluate_booking` (`app/venue/availability.py`), which also refuses a stored window outside the opening hours now (D32); `_approval_unavailable` in `booking_service.py` keeps this PR's response shape for a clash (the first conflict, bookings before blocks). US4's own `_find_approval_conflict` and `_find_block` are gone. Before #71 this PR widened the window itself from the venue's current buffers (PR #73 review); that stopgap is gone |
| D39 | Can a booking at a venue that was deactivated after the request be approved? | No: `409 VENUE_UNAVAILABLE` ("This venue is inactive…"). It can still be rejected. The ticket doesn't say; the story's goal is that only actually available venues are committed |
| D40 | Who is told about an approval or rejection (US4 AC 6)? | The coordinator who made the request and, if different, the event's currently assigned coordinator, once each, if active. The organiser is not told. Log-only (`Notifier.venue_booking_decided`); a failure is logged and the decision stands |
| D41 | Can an event have two pending or approved equipment lines for the same type (US26)? | No: one live line per type per event (`equipment_request_lines_one_live_per_type`, unique on event and type where `status <> 'rejected'`). The 12 Oct customer clarification lets the team track equipment by type, and splitting one need across lines would get round AC 6 (no partial fulfilment). A rejected type can be requested again. Gap for the PO: more of a type that's already approved needs a new decision, since AC 2 only edits pending lines. `DECISION-PENDING` | `migrations/versions/20261025_1200_us26_equipment.py` |
| D42 | Who sees an Assignment History, and what about assignments made before the table existed (SCRUM-69)? | The Coordinator Lead only (`403` for every other role, `401` without identity), the same gate as assigning (AC 3). Any non-draft event, whatever its status: a draft `404`s like an unknown id. An event with no records returns an empty list. **No backfill:** events assigned before `20261026_1200_us10d_history` start with an empty history, because who assigned them was never stored and a guessed name would defeat an accountable record. Entries are ordered by `created_at` (the database clock at the assign transaction) descending, then `id` |
| D43 | Must Tech Support's review carry a note (US26 AC 3)? | No: the note is optional for both approval and rejection, and a blank one is stored as null. AC 3 says lines are marked "with a note" but doesn't make it mandatory, and no test case refuses a missing note. If the PO wants it required (for example on rejection, so the coordinator knows why), add a 422 and a test case. `EquipmentService.review` in `app/equipment/service.py`, `DECISION-PENDING` |
| D44 | What is on a Lead's Assigned tab (SCRUM-86 AC 2)? | Events that have a coordinator, are **active** (`under_review`, `awaiting_clarification`, `approved`, `planning`, `confirmed`; not draft, rejected, cancelled or completed) and whose **latest** assignment record names this Lead as the assigner, so a later reassignment by another Lead moves the event to theirs (US10e). Each row has `event_date`: the start date in Singapore time once the event has one, else the first preferred date, else null. Sorted soonest first, undated last. `status` outside the active set is `422 INVALID_STATUS_FILTER`. Events assigned before `20261026_1200_us10d_history` have no record, so they appear for no Lead |
| D45 | How does a user hold more than one role (US16b AC 1)? | A `roles` list column on `users` (Postgres array of `user_role`, at least one, no repeats), replacing `users.role`. Not a `user_roles` table. Decided 25 Oct; reasoning in §9 |
| D46 | Does the API check the role a user is *using* or every role they *hold* (US16b AC 2, 3)? | Every role they hold. The current role is a frontend choice (the switcher), not sent to the API. Decided 25 Oct; reasoning in §9 |
| D47 | What is an Organiser's "organisation" (US16b AC 4)? | The organiser themselves: another organiser's request is `404`, today's owner-only rule (D11). No organisation model. Decided 25 Oct by the story owner; **`DECISION-PENDING` for the PO**; reasoning in §9 |
| D48 | Which coordinator may see and act on a request (US16b AC 5)? | Only its assigned coordinator, for the review queue, the request's details, its clarification thread and sending a clarification; anyone else `404`. Retires D14 and narrows D11 for coordinators; matches D20 (venues) and equipment. Decided 25 Oct; reasoning in §9 |
| D49 | What happens to `operations_manager`, D19's stand-in for Venue Staff? | Its users become `venue_staff` and nothing checks `operations_manager` any more; the value stays in `user_role` because Postgres can't drop an enum value. Retires D19. Decided 25 Oct; reasoning in §9 |
| D50 | Which seeded user holds two roles (US16b subtasks: "one user with two roles")? | `multi.role@smu.edu.sg`, Coordinator and Venue staff. Decided 25 Oct; reasoning in §9 |
 
### Environment
 
- **Supabase can lag `main`.** Check before blaming the code: `alembic current` against Supabase versus `alembic heads` in the repo. A missing table usually means an unapplied migration, not a bug.
- **Row Level Security is on for every application table, with no policies** (migration `5733a3c705f7`). RLS on plus no policies means Supabase's anon and authenticated roles can read nothing; the backend is unaffected because it connects as the tables' owner, and owners bypass RLS. Keep the Data API disabled anyway — belt and braces. **It was found enabled on 25 Oct** and turned off (SCRUM-117): the publishable key could read and write `alembic_version`, the one `public` table without RLS, and call `next_venue_booking_reference()`. SCRUM-118 adds a second layer (RLS on `alembic_version`, no `anon`/`authenticated` grants on functions and sequences), so turning it back on doesn't reopen that. **Adding a table means enabling RLS on it in the same migration.** Policies are needed only if the Data API is ever enabled (§9).
- **Backend tests need Postgres running**: `docker compose up -d postgres`. Without it every database test errors on connection, which looks alarming and isn't.
- **Python 3.12**, pinned in `backend/.python-version` and matched by CI. A 3.13 virtualenv can pass locally and fail in CI.
- **Node 22+ for the frontend and E2E.** Vitest 5, jsdom 30 and MSW 3 refuse Node 20. The root `.nvmrc` says 22 (run `nvm use`), both Node CI jobs read it, and `engines` with `engine-strict` in `frontend/` and `e2e/` make `npm ci` fail on Node 20 with a clear message. **Teammates: install Node 22, then `npm ci` in `frontend/` and `e2e/`.**
- **No dependency lock on the backend.** `pyproject.toml` uses open ranges, so two machines can resolve different versions. The frontend has `package-lock.json`; the backend has nothing equivalent. Suspect this when something works for one person only.
- **Frontend and API don't share vocabulary yet — for the Sprint 1 screens.** The mockup says `title`, `format`, `startsAt`; §3 says `name`, `delivery_mode`, `start_at`. The US1 screens already use the API's names (`frontend/src/features/eventRequest/`). Generating TypeScript types from `/openapi.json` would turn a rename into a build error instead of a runtime one.
- **Env files are per machine and git-ignored.** Both `backend/.env` and `frontend/.env` must exist; after pulling a change to either `.env.example`, compare and copy the new lines across.
- **The seed refuses a non-local database** unless run with `--yes`. Only the named Supabase person should ever pass it.
 
### What's next in Sprint 3
 
1. **US16a, then US16b** — Supabase Auth per §9. Log in first, then role checks on the routes.
2. **US20's venue catalogue is in** (schema PR 1, API and screens PR 2). US2 builds search on `GET /api/v1/venues`. US22 adds bookings: PR 1 (SCRUM-111) added `venue_bookings` and filled in `has_approved_future_bookings`; PR 2 (SCRUM-112) added the endpoints and closed US20's inactive-venue read gap; PR 3 (SCRUM-113) added the screens and seeds **Venue Booking Demo**, an approved event to book (D24). Coordinators can only reach Approved events (the review queue); **US10a must widen D11** so a coordinator can open a Planning event and book it. US4 (SCRUM-8) added approve and reject on Venue staff's pending list; its approval check uses US13's stored occupied windows (D38). US13 adds the flag-and-notify step for capacity or hours edits that PR 2 deferred.
3. **US10a before US10e and US17.** US10a's schema PR added the Lead role and seeded two Leads; the queue/assign API is in and the screens too (assigning moves the request to `under_review`, D27). US10b to d and US19 are in. US10e must write a `reassignment` row to `coordinator_assignments` (`AssignmentKind.REASSIGNMENT`) in the same transaction as the change; its button goes in US19's read-only request view (deviation 40).
4. **Waitlist gap (D3):** an email-only waitlist entry can't accept an offer, because there's no attendee to match. Settle D3/D6/D7 before US16a links logins to users.
5. **Smaller, worth doing:** fix the root README (missing `alembic upgrade head`, the frontend `.env` copy, TODO team list; its CI section is fixed); lock the backend's dependencies; review the Dependabot PRs; make the notification log visible under uvicorn; delete merged branches; turn on branch protection for `main`.

---

## 2. Data model (Supabase / Postgres)
 
Sprint 1 owns `registrations`, `registration_answers`, `attendance_log` and the seed data. `events` is a placeholder standing in for Epic 1 output — keep the columns other epics will need, but do not build write paths for it. `venues` is real since SCRUM-87 (US20).
 
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
  add column waitlist_enabled       boolean not null default false,   -- US6a: offered only when full and true
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

### `coordinator_assignments` — Assignment History (SCRUM-69, US10d)

Migration `20261026_1200_us10d_history`:

```sql
create type assignment_kind as enum ('assignment', 'reassignment');
create table coordinator_assignments (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  assigned_by_user_id uuid not null references users(id),   -- the Lead
  coordinator_id uuid not null references users(id),
  kind assignment_kind not null,
  created_at timestamptz not null default now()
);
create index ix_coordinator_assignments_event_id on coordinator_assignments (event_id);
alter table coordinator_assignments enable row level security;
```

- Append-only: one row per assignment, written in the same transaction as the change to `events.coordinator_id`, so a refused or rolled-back assignment leaves none (AC 1).
- US10a only ever writes `assignment`. `reassignment` is there for US10e (SCRUM-83) so its rows need no further migration.
- Downgrade drops the table and the enum type, and refuses (like US22 and US26) while any row exists, because it would discard an accountability record.

### `events.coordinator_id` — coordinator assignment (SCRUM-13, US10a)

Migration `20261022_1300_us10a_coordinator`:

```sql
alter type user_role add value 'coordinator_lead' after 'coordinator';
alter table events add column coordinator_id uuid references users(id);  -- null = unassigned
create index ix_events_coordinator_id on events (coordinator_id);
```

- `coordinator_id` is null until the Event Coordinator Lead assigns someone; submitting a request never sets it (AC 1). No event had a coordinator before this column, so AC 9 (existing assignments kept) holds trivially.
- The schema doesn't check that the user is an active coordinator: the assign service does (AC 4), because the role lives on `users`.
- Downgrade drops the column and index but not the `coordinator_lead` enum value (Postgres can't drop one).
- The seed adds two active Leads (`lead.one@smu.edu.sg`, `lead.two@smu.edu.sg`, named Lena Lim and Leo Lee; ids printed by `python -m app.seed`) and gives the seeded organiser and coordinator full names (Olivia Organiser, Casey Tan), satisfying SCRUM-82 AC 7 early. Their supervisory scope is SCRUM-82's.

### `users` — role-aware identity (SCRUM-40)

```sql
create type user_role as enum ('organiser', 'coordinator', 'operations_manager', 'attendee');
-- later: 'coordinator_lead' added after 'coordinator' by US10a (see events.coordinator_id above)

create table users (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  role        user_role not null default 'attendee',
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);
alter table users enable row level security;
-- attendees.id references users.id: every attendee has a users row with the same id, role 'attendee'

-- US16a (SCRUM-101), migration 20261015_1200_us16a_auth_link
alter table users
  add column auth_user_id uuid,        -- Supabase Auth user id (token `sub`); null until first login or sign-up
  add constraint users_auth_user_id_key unique (auth_user_id),
  add column full_name    text;        -- asked at sign-up (AC 6); null for seeded users
```

Existing attendees were backfilled. Anything that creates an attendee (the seed's `upsert_attendee`, the test factory `make_attendee`) must create the `users` row first. The US16a downgrade refuses while any user is linked or named.

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

### `venues` — US20 venue catalogue (SCRUM-87)

The columns are the "Venue fields" table agreed with US2 in SCRUM-87. Migration `20261013_1200_us20_venues`:

```sql
create table venues (
  id                     uuid primary key default gen_random_uuid(),
  name                   text not null,       -- check btrim(name) <> ''
  location               text not null,       -- check btrim(location) <> ''
  capacity               integer not null,    -- check capacity > 0
  facilities             text[] not null default '{}',  -- check <@ the D18 list
  accessibility_features text[] not null default '{}',  -- check <@ the D18 list
  room_layouts           text[] not null default '{}',  -- check <@ the D18 list
  opens_at               time not null,
  closes_at              time not null,       -- check closes_at > opens_at
  setup_minutes          integer not null default 0,    -- check >= 0; 0 is valid
  turnaround_minutes     integer not null default 0,    -- check >= 0; 0 is valid
  is_active              boolean not null default true
);
alter table venues enable row level security;
```

- One venue hosts one event at a time; there's no rooms table. Setup and turnaround belong to the venue only, and a booking can't override them (AC 7).
- Each CHECK is named (`venues_capacity_positive`, `venues_hours_valid`, …) so PR 2's API can name the field in its error (AC 4). Hours can't cross midnight.
- Tags come from D18's fixed lists. The database doesn't reject a duplicate tag, so PR 2's API trims and de-duplicates.
- Events keep their free-text `venue_name` and `room_number` until US22's booking links an event to a venue.
- The seed adds six venues with varied capacity, tags and buffers: one with 0/0 buffers, and one inactive (`SOE Seminar Room B1-1`, which no seeded event uses).
- Downgrade refuses if any venue exists.
- PR 2 added the API (§3, Venues) and screens with no migration. Writes need Venue Staff, which is `operations_manager` until US16b (D19). Buffer edits are refused while the venue has approved future bookings; since US22 PR 1 that reads `venue_bookings` (below). Test cases and the PR split: `docs/testing/US20-venue-catalogue.md`.

### `venue_bookings` — US22 venue booking requests (SCRUM-89)

A coordinator's request to hold a venue for an event. PR 1 (SCRUM-111), migration `20261021_1200_us22_bookings`:

```sql
create extension if not exists btree_gist;
create type venue_booking_status as enum ('requested', 'approved', 'rejected', 'withdrawn');

create table venue_bookings (
  id                              uuid primary key default gen_random_uuid(),
  event_id                        uuid not null references events(id),
  venue_id                        uuid not null references venues(id),
  requested_by_user_id            uuid not null references users(id),
  starts_at                       timestamptz not null,
  ends_at                         timestamptz not null,   -- check ends_at > starts_at
  expected_attendees              integer not null,       -- check >= 1
  room_layout                     text not null,          -- one of D18's layouts
  required_facilities             text[] not null default '{}',  -- <@ D18's facilities (D23)
  required_accessibility_features text[] not null default '{}',  -- <@ D18's accessibility features (D23)
  special_requirements            text,
  status                          venue_booking_status not null default 'requested',
  created_at                      timestamptz not null default now(),
  updated_at                      timestamptz not null default now(),  -- the model stamps now() on every ORM update
  withdrawn_at                    timestamptz,            -- set by PR 2's withdraw; check (status = 'withdrawn') = (withdrawn_at is not null)
  constraint venue_bookings_no_overlap exclude using gist (
    venue_id with =, tstzrange(starts_at, ends_at, '[)') with &&
  ) where (status in ('requested', 'approved'))         -- D21, D22
);
alter table venue_bookings enable row level security;
```

- **No two live bookings at one venue overlap, even by one second** (AC 3). `'[)'` excludes the end, so back-to-back is allowed. Withdrawn and rejected bookings don't block. The constraint also settles **AC 7's race**: a concurrent second insert waits for the first to commit, then fails. PR 2 turns that failure into `409 VENUE_UNAVAILABLE`.
- Requested blocks as well as Approved (D21); the window is plain start to end until US13 adds buffers (D22). `LIVE_BOOKING_STATUSES` in `app/venue/models.py` mirrors the constraint's predicate.
- **No buffer columns**: setup and turnaround stay on `venues` (US20 AC 7, TC-US22-01).
- Each CHECK is named (`venue_bookings_window_valid`, `venue_bookings_room_layout_known`, …) so PR 2's API can name the field.
- **`venue_bookings_withdrawn_consistent`:** a booking has `withdrawn_at` exactly when its status is `withdrawn`, in both directions and on update too, so a withdraw can't forget the time and no other status carries one (PR #64 review).
- **`updated_at`** is set by the model (`onupdate=func.now()`, PR #64 review), not by a trigger: an ORM update stamps it unless the code sets it itself, as withdraw does with the request clock. A raw SQL `UPDATE` doesn't. `now()` is the transaction's start time, so two changes in one transaction share it.
- The layout and tag CHECKs repeat D18's lists, so they now live in **three places**: `app/venue/models.py` and the US20 and US22 migrations, each with a comment naming the other two. Changing a list means a new migration that replaces both migrations' CHECKs, plus `frontend/src/features/venue/tags.ts`.
- `has_approved_future_bookings(db, venue_id, now)` in `app/venue/service.py` is true for an Approved booking at the venue with `ends_at > now`, so one under way still locks the buffers.
- `create extension if not exists btree_gist` needs permission to create extensions. Supabase ships it, but if the migration fails there on permissions, enable `btree_gist` under Database → Extensions and rerun `alembic upgrade head`. On the shared project it's installed (in `public`).
- Downgrade refuses if any booking exists; it leaves `btree_gist` installed.
- **US4 (SCRUM-8), migration `20261025_1300_us4_decisions`:** `decided_at timestamptz`, `decided_by_user_id uuid references users(id)`, `rejection_reason text`, `alternative_suggestion text`, all nullable. `venue_bookings_decided_consistent`: a booking has `decided_at` exactly when it's `approved` or `rejected`. `venue_bookings_rejection_notes_only_when_rejected`: the two notes are null unless `rejected`. The upgrade backfills `decided_at = updated_at` for bookings already decided (`decided_by_user_id` stays null for them: unknown). Downgrade refuses if any decider or note would be lost. Tests and the seed that build an approved or rejected booking must set `decided_at` (`make_venue_booking` does).

**US13 PR 1 (SCRUM-114), migration `20261024_1200_us13_buffers` (revises US26's `20261025_1200_us26_equipment`): the occupied window and the reference.** A database that ran US13 straight on US10a, before it was moved after US26, records US13 as current without US26 having run: fix it with `alembic downgrade -1`, `alembic stamp 20261022_1300_us10a_coordinator`, then `alembic upgrade head`.

```sql
alter table venue_bookings
  add column occupied_starts_at timestamptz not null,  -- starts_at - venue.setup_minutes
  add column occupied_ends_at   timestamptz not null,  -- ends_at + venue.turnaround_minutes
  add constraint venue_bookings_occupied_covers_window
    check (occupied_starts_at <= starts_at and occupied_ends_at >= ends_at),
  add column reference text not null unique default next_venue_booking_reference();  -- VB-2026-000123 (D33)
-- venue_bookings_no_overlap is re-created on the occupied window:
--   exclude using gist (venue_id with =, tstzrange(occupied_starts_at, occupied_ends_at, '[)') with &&)
--   where (status in ('requested', 'approved'))
create sequence venue_booking_reference_seq;  -- behind next_venue_booking_reference()
```

- **The guard covers the occupied window** (US13 AC 2, 3). An exclusion constraint can only use the row's own columns, not `venues.setup_minutes`, so each booking stores the window its venue's buffers produce. `occupied_window(venue, starts_at, ends_at)` in `app/venue/models.py` is the one place that works it out: create, the seed, the factories and (PR 2) buffer edits all call it. The migration's backfill does the same in SQL.
- **The windows are stored when the booking is made.** US20's lock refuses buffer edits only while approved future bookings exist, so a Requested booking can outlive a buffer change. PR 2 recomputes them (D31); until then they keep the buffers they were made with.
- **The upgrade refuses existing overlaps (D34):** if the backfilled windows of two live bookings at one venue overlap, it stops, naming both, before re-creating the guard. **Before applying to Supabase, check** that `alembic upgrade head` there doesn't refuse; if it does, withdraw or reject one of each pair named, then rerun. Applied there on 25 Oct (SCRUM-117) without a refusal: Supabase had no bookings yet.
- **Reference (D33):** `next_venue_booking_reference()` is the column default, so every insert gets one, the year it was made in Singapore. Existing bookings were numbered in the order they were made. The unique constraint is `venue_bookings_reference_key`.
- **US2 search's booking check reads the stored window** (`_occupied_slot()` in `app/venue/service.py`), the range the guard's GiST index holds, so TC-US2-08's index check still holds and an existing booking's buffers keep a venue out (D26).
- **Downgrade** restores the plain-window guard and drops the two columns, the reference, its function and its sequence. It doesn't refuse: the plain window is inside the occupied one, so the old guard holds for every row.
- **US4 (SCRUM-8), migration `20261025_1300_us4_decisions`:** `decided_at timestamptz`, `decided_by_user_id uuid references users(id)`, `rejection_reason text`, `alternative_suggestion text`, all nullable. `venue_bookings_decided_consistent`: a booking has `decided_at` exactly when it's `approved` or `rejected`. `venue_bookings_rejection_notes_only_when_rejected`: the two notes are null unless `rejected`. The upgrade backfills `decided_at = updated_at` for bookings already decided (`decided_by_user_id` stays null for them: unknown). Downgrade refuses if any decider or note would be lost. Tests and the seed that build an approved or rejected booking must set `decided_at` (`make_venue_booking` does).
- **US2's search leaves out a venue with a live booking** (`LIVE_BOOKING_STATUSES`: requested, AC 5's "tentatively held"; approved, "booked") overlapping the requested window.

### `venue_blocks` — closures venue search leaves out (SCRUM-7, US2)

AC 5: search must not show venues "blocked for the requested date and time". A block has no event or requester, so it isn't a `venue_bookings` row (deviation 30). Migration `20261022_1200_us2_venue_blocks`, after US22's:

```sql
create table venue_blocks (
  id          uuid primary key default gen_random_uuid(),
  venue_id    uuid not null references venues(id),
  starts_at   timestamptz not null,
  ends_at     timestamptz not null,      -- check ends_at > starts_at (venue_blocks_window_valid)
  note        text,                      -- e.g. "Closed for AV maintenance"
  created_at  timestamptz not null default now()
);
create index venue_blocks_venue_window on venue_blocks (venue_id, starts_at, ends_at);
alter table venue_blocks enable row level security;
```

- Half-open like bookings: a block ending at 10:00 doesn't clash with a search from 10:00. A multi-day block hides the venue on every day inside it.
- Blocks may overlap each other and bookings; only bookings are kept apart. No buffer columns (US20 AC 7).
- Nothing creates blocks in the product yet: US23a (SCRUM-90, CR-02) adds Venue Staff's screens. The seed adds one.
- The seed's US2 slot: five days ahead, 10:00–12:00 Singapore time, SCIS Seminar Room 2-1 has a `requested` booking, Mochtar Riady Auditorium an `approved` one (each for a seeded approved event, requested by the seeded coordinator, D24), and SMU Connexion Studio 3-2 a block (`VENUE_BOOKINGS`, `VENUE_BLOCKS` in `app/seed.py`). The approved booking means **the auditorium's buffers are locked** (deviation 22).
- Downgrade refuses if any block exists.

### `equipment_types` and `equipment_request_lines` — US26 equipment requests (SCRUM-108)

Migration `20261025_1200_us26_equipment`:

```sql
alter type user_role add value if not exists 'tech_support';   -- deviation 34

create table equipment_types (           -- the catalogue (AC 4); stock, condition, location come with US5
  id         uuid primary key default gen_random_uuid(),
  name       text not null unique check (btrim(name) <> ''),
  created_at timestamptz not null default now()
);
create unique index equipment_types_name_lower_unique on equipment_types (lower(btrim(name)));  -- `Projector` = ` projector`

create type equipment_line_status as enum ('pending', 'approved', 'rejected');
create table equipment_request_lines (
  id                   uuid primary key default gen_random_uuid(),
  event_id             uuid not null references events(id),
  equipment_type_id    uuid not null references equipment_types(id),
  quantity             integer not null check (quantity > 0),   -- equipment_request_lines_quantity_positive
  notes                text,
  status               equipment_line_status not null default 'pending',
  review_note          text,
  requested_by_user_id uuid not null references users(id),
  reviewed_by_user_id  uuid references users(id),
  reviewed_at          timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  -- equipment_request_lines_reviewed_consistent: pending = no reviewer and no time; reviewed = both
  check ((status = 'pending' and reviewed_at is null and reviewed_by_user_id is null)
      or (status <> 'pending' and reviewed_at is not null and reviewed_by_user_id is not null)),
  -- equipment_request_lines_note_only_when_reviewed
  check (review_note is null or status <> 'pending')
);
create index ix_equipment_request_lines_event_id on equipment_request_lines (event_id);
create index ix_equipment_request_lines_pending on equipment_request_lines (created_at) where status = 'pending';
create unique index equipment_request_lines_one_live_per_type            -- D41
  on equipment_request_lines (event_id, equipment_type_id) where status <> 'rejected';
-- RLS on for both tables
```

- Approval is always for the full requested quantity (AC 6), so there's no approved-quantity column.
- **One live line per type per event (D41, `DECISION-PENDING`):** a second pending or approved line for the same type is refused; the coordinator changes the quantity instead (AC 2). A rejected line doesn't count, so the type can be requested again. The API answers it with `409 DUPLICATE_EQUIPMENT_TYPE` (deviation 39).
- The seed adds eight equipment types (`EQUIPMENT_TYPES` in `app/seed.py`) and the Tech Support user (SCRUM-108), and **Equipment Request Demo** (SCRUM-109, `EQUIPMENT_EVENT`): a confirmed event owned by the seeded organiser and assigned to the seeded coordinator (`VITE_DEV_COORDINATOR_ID`), with registration off so it stays off the events board. No other seeded event is both eligible and assigned. **A reseed empties its equipment lines** (SCRUM-110), approved ones included: an approved line can't be removed and D41 allows one live line per type, so E2E reruns (TC-US26-17) would otherwise use up the types. Other events' lines are untouched, and a non-local reseed says so before anything is deleted, both when it refuses without `--yes` and when it runs with it (PR #78 review). The API is in §3 (SCRUM-109) and the screens are deviation 42 (SCRUM-110). Test cases and the PR split: `docs/testing/US26-equipment-requests.md`.
- Downgrade refuses while any request line exists.

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
 
**Identity (Sprint 1):** Supabase Auth is not wired up yet. Read the caller from an `X-Attendee-Id` header and resolve it in a single `get_current_attendee()` dependency. Every endpoint depends on it. When auth lands, one function changes. Do not scatter attendee lookups through route bodies. The frontend sends it from `VITE_DEV_ATTENDEE_ID` (seeded attendee Calvin) on the attendee routes: available events, register, withdraw, `GET /me/registrations` (SCRUM-79).

**Identity (since SCRUM-102):** `get_current_attendee` and `get_current_user` accept `Authorization: Bearer <Supabase access token>` (§9). The `X-Attendee-Id` / `X-User-Id` stubs above still work, but only when `AUTH_DEV_HEADERS=true`. Errors: no or bad token `401 UNAUTHENTICATED`; valid token with no profile `403 PROFILE_REQUIRED`; inactive user `403 FORBIDDEN`; Supabase's keys unreachable `503 AUTH_UNAVAILABLE`; `SUPABASE_URL` unset `500 AUTH_NOT_CONFIGURED` (deviation 19). Tokens get 10 seconds of clock-drift leeway.
 
### `GET /events/available` — SCRUM-25
 
Returns events an attendee may register for right now: `status = 'confirmed'` AND `registration_enabled = true` AND `now()` within `[registration_opens_at, registration_closes_at)` AND `end_at > now()`.
 
```json
{
  "events": [{
    "id": "uuid", "name": "Tech Talk: Agile at Scale",
    "start_at": "2026-10-02T14:00:00+08:00", "end_at": "2026-10-02T16:00:00+08:00",
    "delivery_mode": "in_person", "venue_name": "SMU SCIS Seminar Room 2-1",
    "capacity": 40, "seats_remaining": 3, "is_full": false, "waitlist_available": false,
    "already_registered": false,
    "registration_fields": [
      {"field_key": "dietary", "label": "Dietary requirements", "field_type": "text", "required": false}
    ]
  }]
}
```
 
`already_registered` is computed for the calling attendee so the mockup can grey out the button. `waitlist_available` (SCRUM-52, deviation 18) is SCRUM-48's rule: full **and** `waitlist_enabled`. The board offers "Join the waitlist" only where it's true.
 
### `POST /events/{event_id}/registrations` — SCRUM-26, SCRUM-27
 
Body: `{"answers": {"dietary": "vegetarian"}}`
 
| Outcome | Status | Body |
|---|---|---|
| Registered | `201` | `{"registration_id", "status": "confirmed", "event": {"name", "start_at", "end_at", "venue_name" or "join_link"}}` |
| Event full | `409` | `{"code": "EVENT_FULL", "waitlist_available": true \| false, "message": "..."}`. `true` only when `waitlist_enabled` (US6a, SCRUM-48) |
| Already registered | `409` | `{"code": "ALREADY_REGISTERED"}` |
| Not confirmed / registration disabled | `403` | `{"code": "REGISTRATION_NOT_ENABLED"}` |
| Outside registration window | `403` | `{"code": "REGISTRATION_CLOSED"}` |
| Missing required answer | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["dietary"]}` |
 
The success body must carry **date, time and venue** — the AC names all three ("Receives a confirmation, along with the event's date, time and venue"). For an online event, `join_link` stands in for venue.
 
The full-event case is a **409, not a silent waitlist join.** The AC says the attendee is *offered* a waitlist place, which means they must accept. Joining is a second, explicit call:
 
### `POST /events/{event_id}/waitlist` — SCRUM-27, SCRUM-49 (US6a)
 
Body: `{"email": "calvin.ng.2024@smu.edu.sg"}` → `201 {"registration_id", "status": "waitlisted", "position": 4}`

Joinable only when `registration_service.waitlist_available` holds: no seats left (an unexpired offer holds its seat) **and** `waitlist_enabled`. Checked in this order:

| Outcome | Status | Body |
|---|---|---|
| Joined | `201` | as above; `position` is the confirmation (US6a AC 3) |
| Unknown event | `404` | `{"code": "NOT_FOUND"}` |
| Not confirmed / registration disabled | `403` | `{"code": "REGISTRATION_NOT_ENABLED"}` (D16) |
| Outside registration window | `403` | `{"code": "REGISTRATION_CLOSED"}` (D16) |
| Email already has an active row | `409` | `{"code": "ALREADY_REGISTERED"}` |
| Event's waitlist is off | `409` | `{"code": "WAITLIST_NOT_ENABLED"}` (deviation 16) |
| Places remain | `409` | `{"code": "SEATS_AVAILABLE"}` (deviation 16) |

No registration row and no `attendance_log` row on any refusal.

The board's join form (SCRUM-52) calls this with the email the attendee types and **no identity header** (`apiClient` identity `"none"`).
 
### `GET /me/registrations` — SCRUM-30, SCRUM-31
 
```json
{
  "confirmed": [{
    "registration_id": "uuid", "event_id": "uuid", "event_name": "Tech Talk: Agile at Scale",
    "date": "2026-10-02", "start_time": "14:00", "end_time": "16:00",
    "venue_name": "SMU SCIS Seminar Room 2-1", "joining_info": "Room 2-1",
    "delivery_mode": "in_person"
  }],
  "waitlisted": [{ "...": "same fields", "waitlist_position": 4 }],
  "offered": [{ "...": "same fields", "offer_expires_at": "2026-10-02T01:00:00Z" }]
}
```

`offered` (SCRUM-50, deviation 15) lists places held for the attendee after someone withdrew, until `offer_expires_at`; accept with `POST /registrations/{registration_id}/accept`. A lapsed offer isn't listed, since it can no longer be accepted.
 
Sorting, filtering and section order are all server-side — the mockup must not re-sort. See `TC-US11-04` through `TC-US11-07`.

`event_id` (SCRUM-79, additive) is the row's event, the same id as `GET /events/available`. The events board uses it to tell a waitlisted event from a confirmed one, since `already_registered` is true for both (TC-US11-12).
 
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

### `POST /registrations/{registration_id}/accept` — SCRUM-51 (US6b)

The offer holder takes up the seat: `offered` → `confirmed`, `offer_expires_at` cleared, an `attendance_log` row with `action = 'registered'` and note `accepted waitlist offer`. Locks the event and the registration like decline does. Identity: `X-Attendee-Id`.

| Outcome | Status | Body |
|---|---|---|
| Accepted | `200` | Same as a registration: `{"registration_id", "status": "confirmed", "event": {"name", "start_at", "end_at", "venue_name" or "join_link"}}` |
| Not holding an offer (waitlisted, confirmed, declined, withdrawn…) | `409` | `{"code": "NO_ACTIVE_OFFER"}` — status unchanged (US6b AC 3) |
| Offer past `offer_expires_at` | `409` | `{"code": "OFFER_EXPIRED"}` (deviation 13) |
| Event already started | `403` | `{"code": "EVENT_STARTED"}` |
| Someone else's registration, or unknown id | `404` | `{"code": "NOT_FOUND"}` |
 
---
 
### Event requests — SCRUM-41 to SCRUM-44 (US1)

Router: `app/event/request_router.py`; logic: `app/event/request_service.py`. **Identity:** `X-User-Id`, resolved by `get_current_user` (unknown or missing → `401 UNAUTHENTICATED`, inactive → `403 FORBIDDEN`); write routes also need role `organiser` (`require_user_roles`, wrong role → `403 FORBIDDEN`).

| Method & path | Purpose |
|---|---|
| `POST /api/v1/event-requests` | Create a draft from partial data → `201` |
| `GET /api/v1/me/event-requests` | Caller's requests, newest first → `{"event_requests": [...]}` |
| `GET /api/v1/event-requests` | Staff review queue: every request from `submitted` to `rejected`, oldest submission first. Coordinator, Coordinator Lead or operations manager only (SCRUM-57) |
| `GET /api/v1/event-requests/unassigned` | The Lead's queue: `submitted` requests with no coordinator, oldest first, each with `organiser` (`id`, `name`, `email`) → `{"event_requests": [...]}`. Coordinator Lead only (SCRUM-13) |
| `GET /api/v1/coordinators` | Picker: active users with role `coordinator`, `{"coordinators": [{id, name, email, planning_count}]}`; `planning_count` is how many events they are currently planning, 0 when none (SCRUM-67, D30). Lead only |
| `POST /api/v1/event-requests/{id}/assignment` | Body `{"coordinator_id": "<uuid>"}`; sets the coordinator and moves the request to `under_review` (D27). Lead only |
| `GET /api/v1/event-requests/assigned` | The Lead's Assigned tab: `{"event_requests": [...]}`, each an event request plus `event_date`. Optional `coordinator_id` and `status` filters (SCRUM-86, D44). A real status outside the active set (e.g. `draft`) is `422 INVALID_STATUS_FILTER`; a value that isn't a status at all (`?status=foo`) gets FastAPI's generic `422`. Lead only |
| `GET /api/v1/event-requests/{id}/assignment-history` | `{"assignments": [{id, kind, assigned_by, coordinator, created_at}]}`, newest first; `kind` is `assignment` or `reassignment`, and `assigned_by` and `coordinator` are `{id, name, email}` (SCRUM-69, D42). Lead only; `404` for a draft or unknown id |
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

**Coordinator (SCRUM-13).** Every request body now carries `coordinator`: `null` while unassigned (screens say "Unassigned"), else `{"id", "name"}`. `name` is the user's full name. A user with no full name yet shows their email instead, so give every real coordinator one; the seeded coordinator (Casey Tan) and Leads (Lena Lim, Leo Lee) have names. Submitting never assigns. Assignment outcomes (`assignment_service.assign`, row locked):

| Outcome | Status | Body |
|---|---|---|
| Assigned | `200` | the request, `status` `under_review`, `coordinator` set |
| Target is unknown, inactive, not a `coordinator` (this includes any Lead), or the caller themselves | `422` | `{"code": "INVALID_COORDINATOR", "reason": "unknown_user" \| "inactive" \| "not_a_coordinator" \| "self_assignment"}`; nothing changes |
| Request isn't `submitted`, or already has a coordinator (reassigning is SCRUM-83) | `409` | `{"code": "ASSIGNMENT_NOT_ALLOWED", "status": "<current>"}` |
| Draft, past-stage event or unknown id | `404` | `{"code": "NOT_FOUND"}` (D11) |
| Not the Lead / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

The Lead gate is the `coordinator_lead` role, marked `DECISION-PENDING` until SCRUM-82 owns role checks. Leads may also read submitted requests (D11) and the review queue. A returned request keeps its `coordinator_id` through the organiser's reply, so it never rejoins the queue (AC 10).

**Lead notification (AC 11, D28).** After `POST /api/v1/event-requests/{id}/submit` commits, `event_request_service` calls `Notifier.request_queued` once for each active Coordinator Lead, with `email`, `request_reference`, `event_name`, `organiser_name` (the organiser's display name) and `preferred_dates`. Like the clarification notice it runs after the commit and is best effort: a notifier error is logged and never undoes the submit, and one Lead's failure doesn't stop the next. No active Lead logs a warning. `LoggingNotifier` only logs it for now.

**Assignment notices (SCRUM-68, D29).** After `POST /api/v1/event-requests/{id}/assignment` commits, `assignment_service` calls `Notifier.assignment_made` twice: once for the assigned coordinator (`recipient="coordinator"`) and once for the organiser who created the request (`recipient="organiser"`). Each carries `email`, `request_reference`, `event_name`, `coordinator_name` (display name) and `event_dates` (the preferred dates). Nothing is sent when the assignment is refused (`422`, `409`, `404`, `403`, `401`). Best effort after the commit: a notifier error is logged and never undoes the assignment, and one recipient failing doesn't stop the other. A missing organiser or email logs a warning and still notifies the coordinator; missing request details (no reference or name) log a warning and the notices still go out, with "no reference yet" and "Untitled event request" in their place. **Reassignment's notices (SCRUM-68's last AC) arrive with SCRUM-83**, which should reuse `assignment_made` and add the previous coordinator as a recipient.

### `POST /api/v1/event-requests/{id}/clarifications` — SCRUM-53 (US8a)

Role `coordinator` only (D14). Body: `{"sections": ["attendance", "layout"], "comment": "..."}` — sections from D13. Logic: `clarification_service.send_request`, which locks the request row. After the clarification and status commit, the service calls the log-only notifier with the organiser email, request reference, event name, round, sections and comment. A missing owner/email or incomplete request details logs a warning and skips notification; notifier exceptions are logged and never undo the committed clarification.

| Outcome | Status | Body |
|---|---|---|
| Sent | `201` | `{"clarification": {"id", "event_id", "round", "kind": "request", "sections", "comment", "author_user_id", "created_at"}, "status": "awaiting_clarification"}` |
| No sections / blank comment | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Unknown or repeated section | `422` | `{"code": "INVALID_CLARIFICATION", "fields": ["sections"], "sections": [...]}` |
| Request `awaiting_clarification`, `approved` or `rejected` | `409` | `{"code": "CLARIFICATION_NOT_ALLOWED", "status": "<current>"}` (deviation 12, D15) |
| Draft, an event past the request stage (`planning`, `confirmed`, `cancelled`, `completed`), or unknown id | `404` | `{"code": "NOT_FOUND"}` (D11) |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

Allowed from `submitted` or `under_review` only, with no limit on rounds (D15, SCRUM-75 AC 1): each send is round `max(round) + 1`, so after the organiser's reply (`under_review`) the coordinator can ask again. While a round is open (`awaiting_clarification`) another question is refused, because the reply answers the latest open round. 409 means the request is visible but past asking; 404 means staff can't see it at all (D11).

Nothing is stored, the status doesn't change and no notification is sent on any error.

### `POST /api/v1/event-requests/{id}/clarifications/response` — SCRUM-77 (US8c)

Role `organiser`, and only the request's owner. Body: `{"comment": "..."}`. Logic: `clarification_service.send_response`, which locks the request row and stores the reply as a `response` for the open (latest) round.

| Outcome | Status | Body |
|---|---|---|
| Answered | `201` | `{"clarification": {…, "kind": "response", "round", "sections": null, "comment", "author_user_id", "created_at"}, "status": "under_review"}` |
| Blank comment | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["comment"]}` |
| Request not `awaiting_clarification` (incl. answered already) | `409` | `{"code": "NO_OPEN_CLARIFICATION", "status": "<current>"}` (deviation 14) |
| Another organiser's request, or unknown id | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### `GET /api/v1/event-requests/{id}/clarifications` — SCRUM-77 (US8c)

The whole thread, `{"clarifications": [...]}`, oldest round first and each question before its reply (AC 1, 3). Readable by whoever may read the request (owner, or staff per D11); anyone else gets `404 NOT_FOUND`.

### Venues — SCRUM-87 (US20)

Router: `app/venue/router.py`; logic: `app/venue/service.py`. **Identity:** `X-User-Id` or a token via `get_current_user`; writes also need Venue Staff (`require_user_roles(*VENUE_STAFF_ROLES)`, `operations_manager` until US16b, D19).

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/venues` | anyone signed in | `{"venues": [...]}` by name. Query: `q` (part of the name, any case), `min_capacity`, `facilities` and `accessibility` (repeatable; the venue must have all of them), `active` (staff only: `true`/`false`, all when left out). Non-staff always get active venues only |
| `GET /api/v1/venues/available` | coordinator, operations manager (D25) | US2 search, below |
| `GET /api/v1/venues/{id}` | anyone signed in | One venue; an inactive venue is `404` to non-staff |
| `POST /api/v1/venues` | Venue Staff | Create → `201`, active |
| `PATCH /api/v1/venues/{id}` | Venue Staff | Change only the fields sent; works on inactive venues too; row locked `FOR UPDATE` |
| `POST /api/v1/venues/{id}/deactivate` · `/reactivate` | Venue Staff | `200`, idempotent; bookings are kept (AC 3) |

Write body (unknown fields rejected): `name`, `location`, `capacity`, `facilities`, `accessibility_features`, `room_layouts`, `opens_at`, `closes_at` (`HH:MM`), `setup_minutes`, `turnaround_minutes`. Required on create: `name`, `location`, `capacity`, `opens_at`, `closes_at`; tags default to `[]` and buffers to `0`. Responses carry those plus `id` and `is_active`. Tags are trimmed, de-duplicated and stored in D18's order. Every check runs on the venue as it would be after the edit, so a new `opens_at` is checked against the stored `closes_at`.

| Outcome | Status | Body |
|---|---|---|
| Required field missing (create) or sent as `null` (edit) | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Value present but invalid; unknown tag in a body or filter | `422` | `{"code": "INVALID_VENUE", "fields": [...], "errors": {"capacity": "Capacity must be greater than 0."}}` (deviation 21) |
| Buffer change while approved future bookings exist | `409` | `{"code": "VENUE_BUFFERS_LOCKED", "fields": [...], "message": "Setup and turnaround can't change while this venue has approved future bookings."}` (deviation 22). Resending the stored value isn't a change |
| Buffer change that would make Requested future bookings overlap or run outside hours (US13, D31) | `409` | `{"code": "VENUE_BUFFERS_CONFLICT", "fields": [...], "bookings": [{"reference", "starts_at", "ends_at", "occupied", "reason": "overlap" \| "hours"}], "message": "..."}` (deviation 44). Nothing is saved. Otherwise the edit recomputes their stored occupied windows |
| Unknown id; inactive venue read by non-staff | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; not Venue Staff or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### `GET /api/v1/venues/available` — SCRUM-7 (US2)

Logic: `venue_service.find_available`, one query. Query: `date` (`YYYY-MM-DD`), `start_time`, `end_time` (`HH:MM`, Singapore wall-clock, D9), `attendees` (all four required); `location` (part of the venue's location, any case; blank is no filter), `facilities` and `accessibility` (repeatable; the venue must have all of them). Returns active venues with `capacity >= attendees` whose **occupied window** for the searched time (`[start − setup, end + turnaround)`, each venue's own buffers, US13) fits inside its opening hours and overlaps no live booking's stored occupied window (`requested` or `approved`) and no block, smallest first, then by name:

```json
{
  "venues": [{ "...": "VenueOut, as GET /api/v1/venues" }],
  "criteria": {"date": "2026-10-27", "start_time": "10:00:00", "end_time": "12:00:00", "attendees": 20,
               "location": null, "facilities": [], "accessibility": []}
}
```

`criteria` is what was applied (tags in D18's order, location trimmed), so the screen can show it with the results and beside "No matching venues" (AC 7). An empty result is `200`.

| Outcome | Status | Body |
|---|---|---|
| Criteria missing | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}`, every missing one |
| Past date, end not after start, attendance below 1 or not a whole number, unknown tag | `422` | `{"code": "INVALID_VENUE_SEARCH", "fields": [...], "errors": {...}}` (deviation 31) |
| Organiser, attendee, inactive user / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

Not built until bookings exist: AC 2's flag-and-notify step for capacity or hours edits (flag affected future bookings for review, notify Venue Staff and the assigned coordinators). Flagging lands in US13 (SCRUM-16); the booking link is US22's (SCRUM-89, below). **US20's inactive-venue gap is closed (US22 PR 2):** an inactive venue is still `404` to non-staff, except to the coordinator assigned to an event with a live booking there (deviation 29, D20).

### Venue bookings — SCRUM-89 (US22)

Router: `app/venue/booking_router.py`; logic: `app/venue/booking_service.py`; table: §2 `venue_bookings`. **Identity:** `X-User-Id` or a token via `get_current_user`, then a role check.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/v1/venue-bookings` | Coordinator | Request a venue → `201`, status `requested`, with `warnings`. Notifies every active Venue Staff member once |
| `POST /api/v1/venue-bookings/{id}/withdraw` | The coordinator who made the request | → `200`, status `withdrawn`, `withdrawn_at` set; the window is free again |
| `GET /api/v1/venue-bookings/pending` | Venue Staff (D19) | `{"bookings": [...]}`: Requested bookings, oldest first |
| `POST /api/v1/venue-bookings/{id}/approve` | Venue Staff | US4: no body (or `{}`); → `200`, status `approved`, `decided_at`/`decided_by_user_id` set; the venue is reserved. Refused on a buffered clash (D38). Notifies the coordinator(s) (D40) |
| `POST /api/v1/venue-bookings/{id}/reject` | Venue Staff | US4: optional `reason`, `alternative_suggestion` (trimmed; blank → null); → `200`, status `rejected`; the window is free again; the event's status doesn't change (AC 8). Notifies the coordinator(s) |
| `GET /api/v1/events/{event_id}/venue-bookings` | The event's assigned coordinator (D20) and Venue Staff | `{"bookings": [...]}`: the event's bookings in every status, soonest first |
| `GET /api/v1/venue-bookings/{id}/evaluation` | Venue Staff (D19, D36) | US13 AC 4: `{booking_id, reference, occupied, conflicts: [{kind, reference, note, starts_at, ends_at, occupied, overlap}], outside_hours: {opens_at, closes_at, fields} \| null, clear}`, the booking as it would occupy its venue now (current buffers and hours). `404` for an unknown id |

Body (unknown fields rejected, so no `setup_minutes` or `turnaround_minutes`: US20 AC 7): `event_id`, `venue_id`, `starts_at`, `ends_at` (ISO 8601 **with** an offset), `expected_attendees`, `room_layout` all required; `required_facilities` and `required_accessibility_features` (D18 tags, D23; default `[]`, trimmed, de-duplicated, D18's order) and `special_requirements` (blank → null) optional. A booking reads back with every column (including US4's decision fields) except the two ids, which become `event: {id, name, request_reference, status}` and `venue: {id, name, location, capacity}`; since US13 they also carry `reference` (D33), `occupied_starts_at` and `occupied_ends_at`. Create adds `warnings`.

Create checks, in order; each refusal saves nothing and notifies nobody:

| Outcome | Status | Body |
|---|---|---|
| Required field missing | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Value present but invalid | `422` | `{"code": "INVALID_BOOKING", "fields": [...], "errors": {...}}` (deviation 25) |
| Unknown or draft event, or one the coordinator may not book (D20); unknown or inactive venue | `404` | `{"code": "NOT_FOUND"}` |
| Event not `approved` or `planning` | `409` | `{"code": "EVENT_NOT_BOOKABLE", "status": "..."}` (deviation 24) |
| Attendance above capacity | `422` | `{"code": "VENUE_CAPACITY_EXCEEDED", "fields": ["expected_attendees"], "capacity": 40, "message": "..."}` (deviation 26) |
| Occupied window outside the venue's opening hours (US13 AC 5, D32) | `422` | `{"code": "VENUE_OUTSIDE_HOURS", "fields": ["starts_at" and/or "ends_at"], "opens_at": "08:00:00", "closes_at": "20:00:00", "occupied": {...}, "message": "..."}` (deviation 43) |
| Occupied window overlaps a live booking's or a venue block (US13 AC 3) | `409` | `{"code": "VENUE_UNAVAILABLE", "conflict": {"kind": "booking", "starts_at": "...", "ends_at": "...", "occupied": {...}, "overlap": {...}}, "occupied": {...}, "message": "..."}` (deviation 27) |
| Withdraw, approve or reject a booking that isn't `requested` | `409` | `{"code": "BOOKING_NOT_PENDING", "status": "..."}` (deviations 28, 33) |
| Approve: the stored occupied window (US13) overlaps another live booking's or a block, or the venue is inactive | `409` | `{"code": "VENUE_UNAVAILABLE", ...}` as on create, plus `"buffers": true` and a "Too close to …" message for a buffer-only clash; the booking stays `requested` (D38, D39) |
| Approve: the stored occupied window starts before the venue opens or ends after it closes, as the hours are now | `409` | `{"code": "VENUE_OUTSIDE_HOURS", "fields": [...], "opens_at": ..., "closes_at": ..., "occupied": {...}, "message": ...}` as on create but `409`, checked before clashes; the booking stays `requested` (D32, deviation 43) |
| Approve: the request's start has passed | `409` | `{"code": "BOOKING_EXPIRED", "message": "..."}`; it can still be rejected (deviation 33) |
| Approve: attendance above the venue's capacity, cut since the request | `409` | `{"code": "VENUE_CAPACITY_EXCEEDED", "capacity": 25, "message": "..."}` |
| Approve: the event is no longer `approved` or `planning` | `409` | `{"code": "EVENT_NOT_BOOKABLE", "status": "..."}` |
| Approve with any body field; reject with a field other than the two notes, or a note over 1,000 characters | `422` | FastAPI's unknown-field error: no override, no partial approval (US4 AC 3, 7) |
| Withdraw someone else's or an unknown booking; list an unknown or draft event | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

- **AC 7's race:** the service checks for a conflict first, so it can name the window, and the exclusion constraint settles a simultaneous pair. Two overlapping inserts can deadlock in the exclusion index; Postgres aborts one, and the service runs that request once more, which then sees the winner (TC-US22-15).
- The event and venue rows are read `FOR SHARE`, so a concurrent status change or venue edit waits for the request, and two requests don't block each other.
- The notice (`Notifier.venue_booking_requested`) goes out after the commit; a failure is logged and the booking stands. An unnamed approved event is named by its request reference.
- **The reusable rule (US13, for US4):** `evaluate_window(db, venue, starts_at, ends_at, *, exclude_booking_id=None)` and `evaluate_booking(db, booking)` in `app/venue/availability.py` return `Evaluation(occupied, conflicts, outside_hours)`, with `clear` true when nothing stands in the way. `evaluate_window` builds the occupied window from the venue's current buffers; `evaluate_booking` uses the booking's stored one (the range `venue_bookings_no_overlap` guards), which buffer edits keep current (D31). Each `Conflict` has `kind`, `window`, `occupied`, `overlap`, `reference` (bookings) and `note` (blocks), bookings first then blocks, by start. Live bookings count (D21); holds are a `TODO(US25)` stub. US4's approval calls `evaluate_booking` and refuses unless `clear` (AC 3, 5): hours first (`409 VENUE_OUTSIDE_HOURS`), then the first conflict (`409 VENUE_UNAVAILABLE`); there's no override.
- **Not built:** checking the window against the event's own dates (no AC asks); holds (US25, D22); a database guard between blocks and bookings (D22); requesting a venue from search results (only from the event for now).

### Equipment requests — SCRUM-94 (US26)

Router: `app/equipment/router.py`; logic: `app/equipment/service.py`; tables: §2 `equipment_types` and `equipment_request_lines` (SCRUM-108). **Identity:** `X-User-Id` or a token via `get_current_user`, then a role check. Endpoints added by SCRUM-109.

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/equipment-types` | Anyone signed in | `{"equipment_types": [{id, name}]}`: the catalogue, by name (AC 4) |
| `GET /api/v1/me/equipment-events` | Coordinator | `{"events": [{id, name, start_at, status}]}`: the caller's own assigned events in `planning` or `confirmed`, for the screen's picker: not over yet first, soonest first, then ended ones, most recent first (SCRUM-110, deviation 41) |
| `GET /api/v1/events/{event_id}/equipment-lines` | The event's assigned coordinator (D20) | `{"lines": [...]}`: the event's lines in every status, oldest first |
| `POST /api/v1/events/{event_id}/equipment-lines` | The event's assigned coordinator (D20) | Add a line → `201`, status `pending`, `requested_by_user_id` the caller (AC 1) |
| `PATCH /api/v1/equipment-lines/{id}` | The event's assigned coordinator (D20) | Edit a pending line; only the fields sent change (AC 2) → `200` |
| `DELETE /api/v1/equipment-lines/{id}` | The event's assigned coordinator (D20) | Remove a pending line → `204` (AC 2) |
| `GET /api/v1/equipment-lines?status=pending` | Tech Support (`tech_support`, deviation 34) | `{"lines": [...]}`: pending lines from every event, oldest first (AC 3). `status` defaults to and only accepts `pending` |
| `POST /api/v1/equipment-lines/{id}/review` | Tech Support | `{"decision": "approved" \| "rejected", "note": "..."}` → `200`; saves the status, note, reviewer and time, then notifies the coordinator who asked (AC 3, 5) |

Line body (unknown fields rejected, so a coordinator can't send `status` or review fields): `equipment_type_id` and `quantity` (a whole number, at least 1) required on add; `notes` optional (trimmed, blank → null). Review body (unknown fields rejected): `decision` required; `note` optional for both decisions (D43; trimmed, blank → null). **There's no quantity in a review:** approval is always the full requested quantity (AC 6), so sending one is a `422` (TC-US26-13). A line reads back as `{id, event: {id, name, start_at}, equipment_type: {id, name}, quantity, notes, status, review_note, requested_by_user_id, reviewed_by_user_id, reviewed_at, created_at, updated_at}`.

| Outcome | Status | Body |
|---|---|---|
| Unknown or draft event, or one the coordinator doesn't manage (D20); unknown line, or one on such an event | `404` | `{"code": "NOT_FOUND"}` |
| Add to an event not `planning` or `confirmed` | `409` | `{"code": "EVENT_NOT_ELIGIBLE", "status": "..."}` (deviation 38) |
| Type missing or not in the catalogue; quantity missing, not a whole number or below 1 | `422` | `{"code": "INVALID_EQUIPMENT_LINE", "fields": [...], "errors": {...}}` (deviation 36) |
| A second pending or approved line of the type on the event (add, or edit to that type) | `409` | `{"code": "DUPLICATE_EQUIPMENT_TYPE", "fields": ["equipment_type_id"], "message": "..."}` (deviation 39, D41) |
| Edit, remove or review a line that is `approved` or `rejected` | `409` | `{"code": "LINE_NOT_PENDING", "status": "..."}` (deviation 37) |
| Unknown field (e.g. `status` on a line, `quantity` on a review); a decision other than `approved` or `rejected` | `422` | FastAPI's validation body |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

- **Locking:** the event row is read `FOR SHARE` when a line is added, so a concurrent status change waits. Edits, removals and reviews lock the line `FOR UPDATE`, so a second review, or an edit racing a review, waits and then gets `LINE_NOT_PENDING`.
- **The notice** (`Notifier.equipment_line_reviewed`: email, line id, event name, equipment type, quantity, decision, note) goes to the coordinator who requested the line, even if the event has since been reassigned (TC-US26-14). It's sent after the commit; a failure is logged and the review stands. A refused review notifies nobody.
- **Not built:** checking availability or stock (AC 6 is Tech Support's judgement until US5, SCRUM-9); asking for more of a type that's already approved (D41's gap); re-checking the event's status when a pending line is edited or removed (deviation 38). The coordinator's list of eligible events came with SCRUM-110 (deviation 41).

### `GET /api/v1/me` — SCRUM-105 (US16a)

Who is logged in, so the login page can show the role's home screen (AC 2). Same identity as any role route (`get_current_user`: a token, or `X-User-Id` with dev headers on). `200 {"id", "email", "full_name", "role"}` (`MeOut`); `full_name` is null until a name is set, unlike `POST /auth/profile`'s `ProfileOut`, where it is always present. No profile yet: `403 PROFILE_REQUIRED`; deactivated: `403 FORBIDDEN`; no identity: `401 UNAUTHENTICATED`.

### `POST /api/v1/auth/profile` — SCRUM-103 (US16a)

Called on a confirmed user's **first login**, after the token check answered `403 PROFILE_REQUIRED`. **Token only**: the dev header stubs never apply (`get_token_claims`). Body: `{"full_name": "...", "role": "organiser" | "attendee"}` (lowercase; `"Organiser"` is `INVALID_ROLE`), unknown fields rejected. The token's email must be verified (`user_metadata.email_verified`), as for #55's linking. `auth_user_id` and `email` come from the token, never the body. An `attendee` also gets its `attendees` row with the same id.

| Outcome | Status | Body |
|---|---|---|
| Created | `201` | `{"id", "email", "full_name", "role"}`, so the frontend knows which home screen to show |
| `full_name` and/or `role` missing or blank | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Role not `organiser` or `attendee` | `422` | `{"code": "INVALID_ROLE"}` (deviation 23) |
| A `users` row already has this account or email (seeded staff included), or a simultaneous call won (checked again after the database refuses the insert; any other integrity error is re-raised) | `409` | `{"code": "EMAIL_ALREADY_REGISTERED"}` (deviation 23) |
| `email` or `auth_user_id` in the body | `422` | FastAPI's unknown-field error |
| No token, an invalid one, or one whose email isn't verified | `401` | `{"code": "UNAUTHENTICATED"}` (and `503`/`500` as for any token, deviation 19) |

Open for SCRUM-105: a retry after a lost `201` gets `409` today (TC-US16A-23), which the login page can't tell from someone else's address. Decide there whether the same account should get its existing profile back instead.

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
| TC-US11-12 | A is confirmed, waitlisted and offered on three events | A loads the view | Every row carries its event's `event_id` (SCRUM-79) |
 
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

### SCRUM-11 / US8a, SCRUM-74 / US8c and SCRUM-75 / US8d — Clarification requests, responses and rounds

> *As an Event Coordinator, I want to send a clarification request back to the Event Organiser on specific parts of their submission, so that ambiguous requirements are called out before planning proceeds.*

Backend: `tests/event/test_event_request_clarifications.py` (01–08, storage, SCRUM-54) and `tests/event/test_event_request_clarification_api.py` (09–14, endpoint, SCRUM-53; 15–16, review queue, SCRUM-57) and `tests/event/test_event_request_clarification_response.py` (17–24, organiser response and thread, SCRUM-77; 31–32, repeated rounds, SCRUM-56). Also `test_event_request_clarification_api.py` 25–30 (notification, SCRUM-55) and 33–35 (rounds guard, SCRUM-56). E2E: `e2e/tests/clarification-request.spec.ts`.

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
| TC-US8-15 | Requests across statuses, plus a draft and a confirmed event | Coordinator lists the review queue | Only request-stage statuses, oldest submission first |
| TC-US8-16 | — | Coordinator, ops manager, organiser, no identity list the queue | `200`, `200`, `403`, `401` |
| TC-US8-17 | Request awaiting clarification | Owner answers | `201`, `response` in round 1, comment trimmed; status `under_review` (8c AC 1, 2) |
| TC-US8-18 | Answered round | Coordinator, owner, ops manager read the thread | Question, then answer (8c AC 1, 3) |
| TC-US8-19 | `submitted`, `under_review`, `approved`, `rejected` | Owner answers | `409 NO_OPEN_CLARIFICATION`; nothing stored |
| TC-US8-20 | Already answered | Owner answers again | `409`; still one answer |
| TC-US8-21 | Open clarification | Other organiser, coordinator, no identity, unknown id | `404`, `403`, `401`, `404`; nothing stored |
| TC-US8-22 | Open clarification | Owner sends a blank answer | `422 MISSING_REQUIRED_FIELD`; still `awaiting_clarification` |
| TC-US8-23 | Answered round | Coordinator asks again | `201`, round 2, `awaiting_clarification` |
| TC-US8-24 | Open clarification | Other organiser, attendee, no identity read the thread | `404`, `404`, `401` |
| TC-US8-25 | Eligible submitted/under-review request with an organiser | Coordinator sends | Notifier called once with organiser email, request reference, event name, round, canonical sections and trimmed comment (AC 1, 2) |
| TC-US8-26 | Request in a blocked status | Coordinator sends; response is `409` | No notification (AC 3) |
| TC-US8-27 | Draft, past-stage event or unknown id | Coordinator sends; response is `404` | No notification (AC 3) |
| TC-US8-28 | Submitted request, invalid clarification body | Coordinator sends; response is `422` | No notification (AC 3) |
| TC-US8-29 | Valid clarification; notifier raises | Coordinator sends | `201`; clarification and `awaiting_clarification` remain committed; exception logged (AC 1, 3) |
| TC-US8-30 | Valid clarification with no owner or no organiser email | Coordinator sends | `201`; warning logged; no notification; clarification and status remain committed (AC 1, 3) |
| TC-US8-31 | Submitted request | Question → reply → question → reply → question | Each `201`; questions are rounds 1, 2, 3; replies answer rounds 1 and 2; ends `awaiting_clarification` (8d AC 1) |
| TC-US8-32 | After TC-US8-31's flow | Read the thread | All five messages, round order, question before reply in each round (8d AC 3) |
| TC-US8-33 | Round 1 open (`awaiting_clarification`) | Coordinator sends again | `409 CLARIFICATION_NOT_ALLOWED`; no new row, status unchanged, no notification (8d AC 1/2, D15) |
| TC-US8-34 | `approved` or `rejected` request | Coordinator sends | `409 CLARIFICATION_NOT_ALLOWED`; no new row, status unchanged, no notification (8d AC 2) |
| TC-US8-35 | `planning`, `confirmed`, `cancelled` or `completed` event | Coordinator sends | `404 NOT_FOUND`; no new row, status unchanged, no notification (8d AC 2, D11) |

The E2E test drives the browser: organiser submits a request → switch to coordinator → open it from the queue → send with nothing chosen and see both inputs flagged → tick Attendance and Room layout, comment, send → see the confirmation → switch back to organiser, see `awaiting clarification`, open the request and see the question → send a blank response and see it flagged → answer → see `under review` → switch to coordinator and see `under review` in the queue (SCRUM-78) → open it and see round 1's question with the answer beneath it (SCRUM-58).

### SCRUM-10 / US6a — Join a waiting list for a full event

ACs: (1) the waitlist is offered only when the event is full and supports one; (2) not when places remain or it isn't supported; (3) after joining, the attendee is confirmed with their position.

E2E (SCRUM-79): `e2e/tests/attendee-registration.spec.ts`, as seeded attendee Calvin: the board lists Tech Talk ("You're registered") and Design Sprint Bootcamp ("Full") → My events, withdraw Tech Talk → register for it again and see the confirmation with a booking reference → it shows under Confirmed → withdraw again. It leaves Calvin withdrawn, so reseed before rerunning on the same database. Reseeding is safe after any app use: the seed withdraws other active rows for its (event, attendee) pairs first (`tests/registration/test_seed_reseed.py`).

E2E (SCRUM-52), second test in the same file, run serially with the first: Calvin leaves the Design Sprint Bootcamp waitlist from My events → the card says "Full · waitlist open" → its dialog offers "Join the waitlist" and no "Reserve my seat" (AC 1) → an empty email is blocked → with his email he joins and sees "You're #2 in the queue" (AC 3) → the card says "You're on the waitlist (#2)" → Tech Talk, with places left, offers no waitlist (AC 2) → My events lists him at position 2. It ends as it started, so it reruns without a reseed. The full-without-waitlist case isn't in the seed; TC-US6A-10 covers it.

Backend: `tests/registration/test_waitlist_rules.py` (SCRUM-48, 49). `make_event` defaults to `waitlist_enabled=True`, like `registration_enabled=True`, so the US3/US7/US6B waitlist tests keep their meaning; these tests pass `False` where they need it.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US6A-01 | Full event, waitlist enabled | Attendee registers | `409 EVENT_FULL`, `waitlist_available: true`, "You may join the waitlist" (AC 1) |
| TC-US6A-02 | Full event, waitlist disabled | Attendee registers | `409 EVENT_FULL`, `waitlist_available: false`, "This event is full." (AC 2) |
| TC-US6A-03 | Full (one seat held by an unexpired offer), enabled | Join | `201 waitlisted`, position 1, `waitlisted` log row (AC 1, 3) |
| TC-US6A-04 | Places remain, enabled | Join | `409 SEATS_AVAILABLE` (AC 2) |
| TC-US6A-05 | Waitlist disabled, full or with places | Join | `409 WAITLIST_NOT_ENABLED` (AC 2) |
| TC-US6A-06 | Each refusal from 04, 05 | Join | No registration row, no attendance log (AC 2) |
| TC-US6A-07 | Full, enabled | Two emails join a minute apart | Positions 1 and 2 (AC 3) |
| TC-US6A-08 | Full, enabled, but cancelled / registration disabled / not open / closed | Join | `403 REGISTRATION_NOT_ENABLED` / `REGISTRATION_CLOSED`; nothing stored (D16) |
| TC-US6A-09 | — | Run the seed | Only Design Sprint Bootcamp has `waitlist_enabled` |
| TC-US6A-10 | Full + enabled, full + disabled, places left + enabled | `GET /events/available` | `waitlist_available` true, false, false (SCRUM-52; AC 1, 2) |

### SCRUM-72 / US6b — Take up an available place after a withdrawal

> *As a waiting-listed Attendee, I want to be told when a place becomes available and be able to take it up, so that I get to attend the event I was waiting for.*

Backend: `tests/registration/test_accept_offer.py` (01–07 accept, SCRUM-51; 08–10 offer notice, SCRUM-50). E2E: the third test in `e2e/tests/attendee-registration.spec.ts` (SCRUM-76) has Sofia leave the Bootcamp queue and Mei withdraw through the API, then Calvin sees **Place available**, accepts, and finds the event under Confirmed; it leaves Calvin with a Bootcamp seat, so reseed before a local rerun. TC-US7-08's notification now also carries the `registration_id`, and TC-US11-10's empty response includes `"offered": []`. IDs are `TC-US6B-…` so they can't collide with US6a's tests, written in parallel. AC 1 (notify the next person) is the Sprint 1 offer flow, TC-US7-07, 08.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US6B-01 | B holds an offer on a full event, C queued behind | B accepts | `200`, B `confirmed`, confirmation has the event; seats unchanged; C still first in the queue; logged (AC 2) |
| TC-US6B-02 | C is waitlisted with no offer | C accepts | `409 NO_ACTIVE_OFFER`; C stays `waitlisted` (AC 3) |
| TC-US6B-03 | Confirmed, declined or withdrawn registration | Accept | `409 NO_ACTIVE_OFFER`; unchanged |
| TC-US6B-04 | B's offer | C tries to accept it | `404 NOT_FOUND`; B still `offered` |
| TC-US6B-05 | B's offer has passed `offer_expires_at` | B accepts | `409 OFFER_EXPIRED`; unchanged |
| TC-US6B-06 | B accepted | B lists `GET /me/registrations` | B under `confirmed`, not `waitlisted` |
| TC-US6B-07 | B's offer | No identity; event already started | `401`; `403 EVENT_STARTED` |
| TC-US6B-08 | Full event, C queued | A withdraws, C lists `GET /me/registrations` | C's row moves from `waitlisted` to `offered`, with `offer_expires_at` (AC 1) |
| TC-US6B-09 | Same | A withdraws; C accepts with the id from the notification | Notification goes to C with the `registration_id`; accept `200 confirmed` (AC 1, 2) |
| TC-US6B-10 | B's offer has lapsed | B lists `GET /me/registrations` | Not under `offered` (or `waitlisted`) |

### SCRUM-13 / US10a — Assign a Coordinator to an eligible event

| ID | Given | When | Then |
|---|---|---|---|
| TC-US10A-01 to 04 | — | Schema and seed | `coordinator_lead` role, nullable `events.coordinator_id` with FK and index, new events unassigned, two seeded Leads (PR 1) |
| TC-US10A-05 | Organiser submits | Read the response, then the Lead's queue | `coordinator` null; request is in the queue (AC 1, 8) |
| TC-US10A-06 | Two submitted requests | Lead reads the queue | Oldest first; name, organiser, preferred dates, expected attendance, status present (AC 2) |
| TC-US10A-07 | Draft, `under_review`, and assigned requests | Lead reads the queue | None of them listed |
| TC-US10A-08 | Submitted, unassigned request | Lead assigns an active coordinator | `200`, `under_review`, coordinator set; request leaves the queue (AC 3, 5, D27) |
| TC-US10A-09 | Assigned request | Organiser lists their requests | Coordinator's name, not email (AC 8) |
| TC-US10A-10, 11 | Inactive coordinator, organiser, attendee, a Lead, unknown id | Lead assigns | `422 INVALID_COORDINATOR` with the reason; nothing changes (AC 4) |
| TC-US10A-12 | — | Lead assigns themselves | `422`, `self_assignment` (AC 7) |
| TC-US10A-13 | Organiser, coordinator, ops manager, attendee, no identity | Assign, list queue, list picker | `403` each; `401` without identity (AC 6) |
| TC-US10A-14 | Active and inactive coordinators, an organiser | Lead opens the picker | Only the active coordinator |
| TC-US10A-15, 16 | `under_review`, `awaiting_clarification`, `approved`, or already assigned | Lead assigns | `409 ASSIGNMENT_NOT_ALLOWED`; nothing changes |
| TC-US10A-17 | Draft, `planning`, `confirmed`, unknown id | Lead assigns | `404` |
| TC-US10A-18 | Queued request | Lead reads it | `200` (D11) |
| TC-US10A-19 | Assigned request, clarification asked and answered | Organiser replies | `under_review`, same coordinator, not in the queue (AC 10) |
| TC-US10A-20 | `under_review` request with a coordinator already set | Organiser and Lead read | Coordinator kept; not queued (AC 9) |
| TC-US10A-21 | Submitted, draft and already-assigned requests | Lead opens Event requests | Only the unassigned submitted one, with organiser, dates, attendance, status; Assign, pick, Confirm, then it leaves the queue (frontend) |
| TC-US10A-22 | Backend refuses the pick (`INVALID_COORDINATOR`) | Lead confirms | The reason is shown; the request stays queued (frontend) |
| TC-US10A-23 | Another Lead assigned it first | Lead confirms | `ASSIGNMENT_NOT_ALLOWED` message; the request drops from the queue (frontend) |
| TC-US10A-24 | Submitted request | Coordinator, then organiser, open Event requests | No Assign button (AC 6, frontend) |
| TC-US10A-25 | An unassigned and an assigned request | Organiser opens Event requests | "Coordinator: Unassigned" and "Coordinator: <name>" (AC 8, frontend) |
| TC-US10A-26 | Seeded Lead and coordinator | E2E: organiser submits, Lead assigns from the queue, organiser sees the coordinator, coordinator has no Assign | The whole journey (AC 1, 2, 5, 6, 8) |
| TC-US10A-27 | Two active Leads; organiser submits | Submit | Each Lead notified once with the request name, organiser name and preferred dates (AC 11) |
| TC-US10A-28 | An inactive Lead, a coordinator and an ops manager | Submit | Only the active Lead is notified |
| TC-US10A-29 | Notifier raises | Submit | `200`, status `submitted`, still queued; every Lead was still tried; error logged (AC 11) |
| TC-US10A-30 | No active Lead | Submit | `200`; warning logged; nothing sent |
| TC-US10A-31 | Draft missing required fields | Submit refused, then a good submit | No notification for the refusal; one for the good submit |

### SCRUM-68 / US10c — Notify Coordinator and Organiser of an assignment

| ID | Given | When | Then |
|---|---|---|---|
| TC-US10C-01 | Submitted request | Lead assigns a coordinator | The coordinator is told: request reference, event name, coordinator's name, event dates (AC 1) |
| TC-US10C-02 | Same | Same | The organiser is told the same three details; exactly two notices, none to the Lead (AC 2) |
| TC-US10C-03 | Coordinator with no full name | Assign | The notices name them by email (D29, same fallback as AC 8) |
| TC-US10C-04 | Inactive or unknown pick, the Lead themselves, already assigned, a draft, an organiser caller, no identity | Assign | `422`, `409`, `404`, `403`, `401`; no notice (AC 3) |
| TC-US10C-05 | Notifier raises | Assign | `200`, `under_review`, coordinator kept; both notices still tried; error logged |
| TC-US10C-06 | Request with no owner | Assign | `200`; warning logged; the coordinator is still told |
| TC-US10C-07 | Request with no reference or name | Assign | `200`; warning logged; both notices still sent, with stand-in labels |

### SCRUM-86 / US19 — Event Coordinator Lead's queue and oversight view

| ID | Given | When | Then |
|---|---|---|---|
| TC-US19-01 | A request the Lead assigned | Lead reads the Assigned list | Name, status, coordinator `{id, name}` and `event_date` (first preferred date) (AC 2) |
| TC-US19-02 | A confirmed event starting 01:00 Singapore time on the 5th | Lead reads the list | `event_date` is the 5th |
| TC-US19-03 | One event in each status | Lead reads the list | Only under review, awaiting clarification, approved, planning and confirmed |
| TC-US19-04 | Two Leads each assigned an event | Each reads the list | Each sees only their own (AC 6) |
| TC-US19-05 | Another Lead later reassigns the event | Both read | It moves to the later Lead |
| TC-US19-06 | Events for two coordinators and statuses | Filter by coordinator, by status, by both, by an unknown coordinator | Only matches; empty when none (AC 3) |
| TC-US19-07 | — | Filter by `status=rejected` | `422 INVALID_STATUS_FILTER` |
| TC-US19-08 | Dated and undated events | Lead reads the list | Soonest first, undated last |
| TC-US19-09 | Organiser, coordinator, ops manager, attendee, no identity | Read the list | `403` each; `401` without identity (AC 5) |
| TC-US19-10 | One unassigned request, two Leads | Both read the queue, one assigns | Both saw it; after, neither does and it is on the assigner's list only (AC 1, 6) |
| TC-US19-11 | Assigned event | Lead posts approve, reject, confirm | `404` or `405`: no such route (AC 4) |
| TC-US19-12 | Unassigned and assigned requests | Frontend: Lead opens Event requests | Unassigned tab selected, with only the unassigned one; Assigned tab with only the assigned one |
| TC-US19-13 | An approved assigned event | Frontend: Assigned tab | Name, "Coordinator: Casey Tan", status, "Event date: …" (AC 2) |
| TC-US19-14 | Events assigned by this Lead and by another | Frontend: Assigned tab | Only this Lead's (AC 6) |
| TC-US19-15 | Two coordinators and statuses | Frontend: choose a coordinator, then a status | Request carries the filter, the list narrows, the coordinator list stays whole, and an empty result says so (AC 3) |
| TC-US19-16 | Unassigned and assigned requests | Frontend: View each | Read-only fields; Assign a coordinator only on the unassigned one, Assignment history only on the assigned one; no approve, reject or confirm (AC 4) |
| TC-US19-17 | Lead assigns from the queue | Frontend: opens the Assigned tab | The request is there |
| TC-US19-18 | Coordinator, organiser | Frontend: open Event requests; call the list directly | No tabs; `403` (AC 5) |

### SCRUM-69 / US10d — View an event's Coordinator assignment history

| ID | Given | When | Then |
|---|---|---|---|
| TC-US10D-01 | — | Schema | `coordinator_assignments` with the six columns, all not null, and foreign keys to `events` and `users` (SCRUM-63) |
| TC-US10D-02 | Submitted request | Lead assigns | One record: event, assigning Lead, coordinator, kind `assignment`, a timestamp (AC 1) |
| TC-US10D-03 | Self, organiser or inactive coordinator picked | Lead assigns | `422`; no record |
| TC-US10D-04 | Already-assigned request | Lead assigns again | `409`; still one record |
| TC-US10D-05 | One assignment | Lead reads the history | Kind, Lead and coordinator as `{id, name, email}`, and the time (AC 3) |
| TC-US10D-06 | An assignment and a later reassignment | Lead reads the history | Newest first, the reassignment marked (AC 2, 3) |
| TC-US10D-07, 08 | No records; another event with records | Lead reads the history | `{"assignments": []}`, never another event's rows |
| TC-US10D-09 | Organiser, coordinator, ops manager, attendee, no identity | Read the history | `403` each; `401` without identity (AC 3) |
| TC-US10D-10 | Draft, unknown id | Lead reads the history | `404` |
| TC-US10D-11 | Submitted request | Frontend: Lead assigns, then View assignment history | One entry: Assignment, "Lena Lead assigned Casey Tan", the date (SCRUM-66) |
| TC-US10D-12 | Assigned request with a reassignment | Frontend: Lead opens its History from Assigned requests | Two entries, newest first, the first marked Reassignment |
| TC-US10D-13 | Assigned request, no records | Frontend: Lead opens History | "No assignments have been recorded for this event." |
| TC-US10D-14 | Coordinator, then organiser | Frontend: open Event requests | No History action |
| TC-US10D-15 | — | Schema | Row-level security is enabled on `coordinator_assignments` |

### SCRUM-67 / US10b — See Coordinator workload when assigning

| ID | Given | When | Then |
|---|---|---|---|
| TC-US10B-01 | A coordinator with no events | Lead opens the picker | The entry has their name and `planning_count` 0 (AC 1, 2) |
| TC-US10B-02 | One coordinator with an event in each status | Lead opens the picker | Counts `under_review`, `awaiting_clarification`, `approved`, `planning` only; not `rejected`, `confirmed`, `cancelled`, `completed` (D30) |
| TC-US10B-03 | Coordinators owning 1, 2 and 0 events | Lead opens the picker | Each count is their own |
| TC-US10B-04 | A coordinator with events, and a queued request | Lead assigns, then reopens the picker | The count is one higher (AC 3) |
| TC-US10B-05 | A refused assignment | Reopen the picker | Every count is unchanged |
| TC-US10B-06 | An inactive coordinator and other roles | Lead, a coordinator, no identity open the picker | Inactive and other roles not listed; `403`, `401` |
| TC-US10B-07 | A coordinator with no events | Frontend: Lead opens Assign | Entry shows "0 events planning" |
| TC-US10B-08 | Two counted events, two not counted, two queued requests | Frontend: assign one, then open Assign on the other | "2 events planning", then "3 events planning" |
| TC-US10B-09 | One counted event | Frontend: Lead opens Assign | "1 event planning", singular |

### SCRUM-8 / US4 — Approve or reject a venue booking request

Test cases TC-US4-01 to 11 in full: `docs/testing/US4-booking-decision.md`. Backend `tests/venue/test_booking_decision_api.py`; E2E `e2e/tests/venue-booking-decision.spec.ts` (TC-US4-10, 11).

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

### SCRUM-10 (US6a)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-48 | `waitlist_available` helper (full and `waitlist_enabled`); `EVENT_FULL` uses it; seed enables the bootcamp's waitlist | TC-US6A-01, 02, 09 (AC 1, 2) | #43 |
| SCRUM-49 | `POST /events/{id}/waitlist` refuses with `WAITLIST_NOT_ENABLED` / `SEATS_AVAILABLE`, takes register's gates (D16), keeps the position confirmation | TC-US6A-03 to 08 (AC 1–3); no migration | #43 |
| SCRUM-79 | Attendee screens (board, register, My events, withdraw) call the API via `X-Attendee-Id`; mock removed; `event_id` on My Registrations rows so the board shows waitlist status; reseed withdraws app-made duplicates of seeded registrations | `npm run build` + `lint`; attendee E2E journey; TC-US11-12; `test_seed_reseed.py` | #45 |
| SCRUM-52 | Join-waitlist prompt (email field) on a full event with a waitlist; position confirmation; "Full · waitlist open" card; `waitlist_available` on `/events/available` | TC-US6A-10; waitlist E2E journey (AC 1–3) | #46 |

### SCRUM-72 (US6b)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-51 | Accept an offer: `offered` → `confirmed` | TC-US6B-01 to 07 (AC 2, 3) | #37 |
| SCRUM-50 | Notify the next waitlisted attendee on a vacancy: on-screen `offered` section + id in the notice | TC-US6B-08 to 10, TC-US7-07, 08 (AC 1) | #39 |
| SCRUM-76 | Offer + "Accept place" on the attendee's screen | E2E: offer journey (AC 1, 2 in the browser) | #51 |

### SCRUM-74 (US8c)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-77 | Organiser response endpoint + thread read | TC-US8-17 to 24 (AC 1, 2) | #38 |
| SCRUM-78 | Organiser response form | E2E journey (answer step) | #40 |
| SCRUM-58 | Thread view (question + answer) | AC 1, 3 — E2E journey (thread step) | #50 |

### SCRUM-75 (US8d)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-56 | Rounds guard pinned as D15: ask again from `under_review` with no limit; 409 while a round is open or once decided; 404 past the request stage | TC-US8-31 to 35 (AC 1–3); no migration, no frontend | #42 |

### SCRUM-11 (US8a)

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-54 | Thread table, `clarification_service`, seeded coordinator | TC-US8-01 to 08; one Alembic head | #34 |
| SCRUM-53 | Endpoint + guard + Submitted/Under Review → Awaiting Clarification | TC-US8-09 to 14 (AC 2, 3) | #35 |
| SCRUM-57 | Coordinator section selector + comment UI, review queue, **Acting as** switch | TC-US8-15, 16; E2E journey | #36 |
| SCRUM-55 | Log-only organiser clarification notification after commit | TC-US8-25 to 30 (AC 1–3); no migration | #41 |

### SCRUM-87 (US20)

Test cases in full: `docs/testing/US20-venue-catalogue.md`.

| PR | Work | Done when | PR # |
|---|---|---|---|
| PR 1 | `venues` table, named CHECKs, D18 tag lists, six seeded venues | TC-US20-01, 04 (DB), 07 (DB), 08, 09; one Alembic head | #53 |
| PR 2 | Venue endpoints, Venue Staff stub (D19), `INVALID_VENUE` / `VENUE_BUFFERS_LOCKED`, buffer-lock stub, seeded venue staff, Venues screens | TC-US20-01 to 06, 10 to 18 (`tests/venue/test_venue_api.py`); E2E TC-US20-05, 19 (`e2e/tests/venue-catalogue.spec.ts`); no migration | #60 |

### SCRUM-89 (US22)

Test cases in full: `docs/testing/US22-venue-booking.md`.

| PR | Subtask | Work | Done when | PR # |
|---|---|---|---|---|
| PR 1 | SCRUM-111 | `venue_bookings` table, named CHECKs, `venue_bookings_no_overlap` exclusion constraint (`btree_gist`), real `has_approved_future_bookings` | TC-US22-01 to 03 (`tests/venue/test_booking_schema.py`); one Alembic head | |
| PR 2 | SCRUM-112 | Create, withdraw and list endpoints; D20 access check; `EVENT_NOT_BOOKABLE`, `INVALID_BOOKING`, `VENUE_CAPACITY_EXCEEDED`, `VENUE_UNAVAILABLE`, `BOOKING_NOT_PENDING`; facility warnings; `Notifier.venue_booking_requested`; inactive-venue read for booked coordinators | TC-US22-04 to 18 (`tests/venue/test_booking_api.py`); no migration | |
| PR 3 | SCRUM-113 | Request venue from an Approved request in the review queue, the event's bookings with Withdraw, Venue Staff's pending list on Venues; seeded Venue Booking Demo; `server.ts` booking handlers | TC-US22-19 to 21 (`e2e/tests/venue-booking.spec.ts`); unit + integration tests in `frontend/src/features/venue/`; lint + build; no migration | |

### SCRUM-8 (US4)

Test cases in full: `docs/testing/US4-booking-decision.md`. No subtasks in Jira; one PR, schema, API, screens and E2E as separate commits (an exception to "schema changes go in the first PR of a story, alone", agreed for this story).

| Work | Done when |
|---|---|
| Decision columns, CHECKs, backfill (`20261025_1300_us4_decisions`) | TC-US4-05 (DB); TC-US22-01's column and CHECK lists updated; one Alembic head |
| Approve and reject endpoints, buffered conflict check, coordinator notice | TC-US4-01 to 09 (`tests/venue/test_booking_decision_api.py`) |
| Approve / Reject on the pending list, reject dialog, decision notes on the coordinator's panel | Frontend unit + integration; TC-US4-10, 11 (E2E); lint + build |

### SCRUM-16 (US13)

Test cases in full: `docs/testing/US13-buffers.md`.

| PR | Subtask | Work | Done when | PR # |
|---|---|---|---|---|
| PR 1 | SCRUM-114 | Migration `20261024_1200_us13_buffers`: stored occupied window, `venue_bookings_occupied_covers_window`, `venue_bookings_no_overlap` on the occupied window, `VB-` reference; `occupied_window()`; create, the seed and the factories fill them; US2 search's booking check on the stored window; US22 and US2 plain-rule tests on 0/0 venues | TC-US13-01 to 05 (`tests/venue/test_buffer_schema.py`); one Alembic head; whole E2E suite on a reseeded database | |
| PR 2 | SCRUM-115 | `evaluate_window` and `evaluate_booking` for US4; `VENUE_OUTSIDE_HOURS`; overlap and reference in `VENUE_UNAVAILABLE`; staff evaluation endpoint; buffer-edit recompute and `VENUE_BUFFERS_CONFLICT`; US2 search with the searched venue's buffers and hours; E2E time fixes (TC-US22-21, TC-US2-14); after US4 (#73) merged, its approval calls `evaluate_booking` on the stored window (adds `409 VENUE_OUTSIDE_HOURS` at approval) | TC-US13-06 to 15 (`tests/venue/test_buffer_api.py`); no migration | |
| PR 3 | SCRUM-116 | Occupied-window preview on the booking form; `VENUE_OUTSIDE_HOURS` on the time fields and the overlap period for `VENUE_UNAVAILABLE` (also `VENUE_OUTSIDE_HOURS` at approval); reference and occupied window on the bookings panel and pending list; each pending row's evaluation (`bookingApi.evaluation`); the fake server's evaluation route and `setEvaluation` | TC-US13-16 to 19 (Vitest, `e2e/tests/venue-buffers.spec.ts`); lint + build; whole E2E suite on a reseeded database, and the new spec again without a reseed; no migration | |

### SCRUM-7 (US2)

Test cases in full: `docs/testing/US2-venue-search.md`. No subtasks in Jira; one PR, rebased on US22 PR 1 (#64).

| Work | Done when |
|---|---|
| `venue_blocks` table + seeded slot | TC-US2-11, 12; one Alembic head |
| `GET /api/v1/venues/available` | TC-US2-01 to 10 (AC 1–8) |
| Search form on Venues (Coordinator, Venue staff) | Frontend unit + integration; TC-US2-13 to 16 (E2E); lint + build |

### SCRUM-81 (US16a)

Test cases in full: `docs/testing/US16a-sign-up-log-in.md`, mirroring the subtasks in Jira.

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-101 | `users.auth_user_id` (unique) + `users.full_name`; downgrade refuses while any user is linked or named | TC-US16A-01 to 04; one Alembic head | #54 |
| SCRUM-102 | Verify the Supabase token in `get_current_user` / `get_current_attendee` (`app/user/auth.py`); header stubs only when `AUTH_DEV_HEADERS=true`; email linking for active Organiser and Attendee rows with a verified email only; 503/500 for key outages and missing config; startup warning while the stubs are on | TC-US16A-05 to 17, 46 to 49 (`tests/user/test_token_identity.py`) | #55 |
| SCRUM-103 | `POST /api/v1/auth/profile` (`app/user/router.py`, `service.py`, `schemas.py`; `get_token_claims` in `dependencies.py`): Organiser or Attendee only; any existing email refused; returns `{id, email, full_name, role}` | TC-US16A-18 to 26 (`tests/user/test_profile.py`) | #61 |
| SCRUM-104 | Seed Supabase Auth logins for the seeded users via the Admin API (`app/user/supabase_admin.py`, `seed_auth_logins` in `app/seed.py`); skipped without `SUPABASE_SECRET_KEY` / `SEED_AUTH_PASSWORD` | TC-US16A-27 to 31 (`tests/user/test_seed_auth_logins.py`) | #56 |
| SCRUM-105 | Login page (`frontend/src/auth/`), logout, session; Bearer token per request; **Acting as** only with `VITE_DEV_AUTH=true`; last screen remembered for refresh; `GET /api/v1/me` for the role | TC-US16A-32 to 39, 51 (`tests/user/test_me.py`, `e2e/tests/login.spec.ts`); lint + build | #62 |
| SCRUM-106 | Sign-up page (`frontend/src/auth/SignUpPage.tsx`, `signUp.ts`) linked from the login page; first login creates the profile from sign-up's metadata (`App.tsx`) | TC-US16A-40 to 45, 50 (`signUp.test.ts`, `SignUpPage.test.tsx`, `signUp.integration.test.ts`, `e2e/tests/sign-up.spec.ts`); lint + build | #75 |

### SCRUM-94 (US26)

Test cases in full: `docs/testing/US26-equipment-requests.md`, mirroring the subtasks in Jira.

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-108 | `equipment_types` (seeded) + `equipment_request_lines`; `tech_support` role and a seeded Tech Support user | TC-US26-01 to 05, 18 (`tests/equipment/test_equipment_schema.py`); one Alembic head | #63 |
| SCRUM-109 | Catalogue; the assigned coordinator adds, edits and removes pending lines on a planning or confirmed event; Tech Support's queue and approve/reject with an optional note (D43); coordinator notified (`Notifier.equipment_line_reviewed`); `INVALID_EQUIPMENT_LINE`, `LINE_NOT_PENDING`, `EVENT_NOT_ELIGIBLE`, `DUPLICATE_EQUIPMENT_TYPE`; seeded Equipment Request Demo | TC-US26-06 to 15, 19 (`tests/equipment/test_equipment_api.py`), seed (`tests/equipment/test_equipment_seed.py`); no migration | |
| SCRUM-110 | Equipment screen for coordinators and the Tech Support queue; **Acting as** gains Tech support; `GET /api/v1/me/equipment-events` (deviation 41); reseed empties the demo event's lines | TC-US26-16, 17 (`e2e/tests/equipment.spec.ts`), TC-US26-20 (`tests/equipment/test_equipment_api.py`, `test_equipment_seed.py`); unit and integration tests in `frontend/src/features/equipment/`; lint + build | |

### SCRUM-82 (US16b)

Test cases in full: `docs/testing/US16b-role-based-access.md`, mirroring the subtasks in Jira. Decisions D45 to D50 (§9).

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-119 | `users.roles` replaces `users.role`; `venue_staff` and `safety_officer`; checks on held roles; `/me` returns `roles`; `operations_manager` retired (D49); seed one user per role and `multi.role@smu.edu.sg` (D50) | TC-US16B-01 to 08; one Alembic head | |
| SCRUM-120 | Coordinators scoped to assigned events for the queue, details, thread and clarifications (D48); organiser scope tested (D47); attendee, role-matrix and Lead checks; clarification E2E gains the assign step | TC-US16B-09 to 16 | |
| SCRUM-121 | Role switcher and navigation per current role (D46); Safety officer's "no screens yet"; **Acting as** gains Venue staff and Safety officer | TC-US16B-17 to 23; lint + build; E2E | |

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
- Assignment notices to the Coordinator and Organiser (SCRUM-68, D29) use it too, after the assignment commits, log-only
- Lead notification on submit (SCRUM-13 AC 11, D28) uses it too, after the submit commits, log-only like the rest
- Clarification-request notification (SCRUM-55) uses that interface after commit; missing recipient data logs a warning and skips notification, and notifier failures do not undo the clarification
- A working frontend. **Mockups only.** Do not wire React to FastAPI this sprint. *(Sprint 2: retired — see §1a Rules.)*
- Payments, check-in, attendance marking, feedback — nowhere in the backlog
---
 
## 8. Conventions
 
- **Tests:** `pytest` + `httpx.AsyncClient`. Name tests after their IDs. Use a transactional fixture that rolls back per test; never test against seeded production-ish data you also mutate.
- **Testing guide:** `docs/testing/README.md` covers all four suites, what each CI workflow runs, the frontend test helpers, the E2E shared-seed rule and what to do when a test fails. Keep it current when a suite or workflow changes.
- **Frontend tests:** Vitest + Testing Library in jsdom, `*.test.ts(x)` next to the file under test; shared fixtures in `frontend/src/test/`. `vite.config.ts` fixes the `VITE_*` values (`VITE_API_BASE_URL=http://api.test`, `VITE_DEV_AUTH=true` for SCRUM-105's dev mode), so tests never read `frontend/.env`. Query by role and label, as the E2E specs do; cite the TC ID or AC a test checks in its name. Formatters are asserted in Asia/Singapore, so the suite must pass under any `TZ`. **Integration tests** (`*.integration.test.tsx`) render the real `App` against `frontend/src/test/server.ts`, an MSW in-memory fake of the §3 routes that checks identity headers and keeps state per test (`seedEvent`, `seedRegistration`, `seedRequest`, `seedVenue`, `nextSearchResult`, `callsTo`). Unmocked requests fail the test (`onUnhandledFrame: "error"`, MSW 3's name for the old `onUnhandledRequest`). **When a §3 contract changes, change the fake too**: it doesn't call FastAPI, so only the E2E suite catches drift between the two. Keep business rules out of the fake: venue search returns what a test queues (`nextSearchResult`) rather than re-deciding which venues fit.
- **Time:** freeze it (`freezegun` or an injected `now()` provider). TC-US3-04, TC-US3-05, TC-US7-03 and TC-US7-04 are unreliable otherwise.
- **Structure:** routes stay thin. Guard logic and state transitions live in a service layer so they can be tested without HTTP.
- **Errors:** every 4xx returns a machine-readable `code`, exactly as spelled in §3. The mockup keys off `code`, not off message text.
- **Migrations:** every schema change is a migration file in the repo. No changes made only in the Supabase dashboard.
- **Branches and PRs:** one branch per PR, named `feat(SCRUM-<n>)Title-Case-Words` (ranges allowed: `feat(SCRUM-41-44)…`), started from an up-to-date `main`. Commits and PR titles: `feat(SCRUM-<n>): lowercase summary` — CI checks the PR title's type prefix, not the branch name. Every PR is reviewed before merge.
- **Keep this file current:** every PR updates this document for what it changed (status row, rules, schema/API, deviations) before it merges, so everyone's Claude matches `main` after a pull.
---
 
## 9. Supabase Auth — Sprint 3 (US16a SCRUM-81, US16b SCRUM-82)
 
Scheduled for Sprint 3. The API wiring it waited for is done (SCRUM-79), so only the identity mechanism changes.
 
Supabase Auth supplies **identity only**. FastAPI stays the only thing that touches the database, so no service or router changes — §3 already promises the change lands in one place:
 
> "When auth lands, one function changes. Do not scatter attendee lookups through route bodies."
 
That's one token check in `app/user/dependencies.py`; `get_current_user` and `get_current_attendee` both build on it.
 
### Dashboard
 
Enable a provider under **Authentication → Providers**. **Email/password is the chosen provider (US16a).** Google stays optional; if added, **restrict the domain in our own code** — check the `email` claim ends in `@smu.edu.sg`; Supabase won't enforce it.
 
**Settings made in the shared project (24 Oct, SCRUM-106).** Anyone changing them tells the team; they apply to everyone:

| Setting | Where | Value |
|---|---|---|
| Confirm email | Authentication → Sign In / Providers → Email | **On** (PR #55 review) |
| Minimum password length | Same page | Keep Supabase's default of 6: the sign-up page checks the same (TC-US16A-44) |
| Custom SMTP | Authentication → Emails → SMTP Settings | **On**: Gmail, `smtp.gmail.com` port 587, the team account `connectsphereis212@gmail.com` with a Gmail app password, sender name "ConnectSphere". The app password lives only in the dashboard; ask Calvin. Supabase's built-in sender is for testing only (a few emails an hour) |
| Site URL | Authentication → URL Configuration | `http://localhost:5173`, so confirmation links open the app. **Change it to the deployed address when there is one** |
| Redirect URLs | Same page | `http://localhost:5173/**` and `http://localhost:5174/**` (the E2E login frontend) |
| Email rate limit | Authentication → Rate Limits | Check it before heavy testing: each sign-up E2E run sends 2 confirmation emails (to the team inbox, plus-addressed) |

Keys come from **Project Settings → API**. Current naming: **publishable** (`sb_publishable_…`, safe in the frontend) and **secret** (`sb_secret_…`, backend only, probably not needed). The old `anon` / `service_role` keys still work but are deprecated by the end of 2026.
 
### Frontend
 
`@supabase/supabase-js`, created with `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`. Every request in `api/client.ts` carries `Authorization: Bearer <session.access_token>` in place of **both `X-User-Id` and `X-Attendee-Id`**. The **Acting as** toggle and `apiClient`'s `identity` option become dev-only. Read the session per request — tokens last an hour and supabase-js refreshes them, which a value cached at startup would miss. `VITE_*` values are compiled into the bundle and readable by anyone: the publishable key only.

**Done in SCRUM-105:** `frontend/src/auth/supabase.ts` holds the client; `LoginPage.tsx` shows one message for any wrong email or password (AC 3), and its own message for an unconfirmed email, too many attempts (429) or no connection (`auth/messages.ts`). A failed `GET /api/v1/me` says which: no profile, deactivated, login unavailable (500/503) or backend unreachable. Log out ends the session in this browser only (`scope: "local"`). Not logged in and `VITE_DEV_AUTH` unset, every screen is the login page; with `VITE_DEV_AUTH=true` the app runs as before (Acting as, dev stubs) unless someone logs in. After a login the app reads `GET /api/v1/me` and opens the role's home: organiser → Event requests, coordinator → review queue, Coordinator Lead → unassigned queue, operations manager (Venue staff stand-in, D19) → Venues, attendee → events board. Each role gets only its own screens (`frontend/src/auth/screens.ts`); a role the frontend doesn't know yet gets a message and Log out, not a broken page. The last screen is kept in `localStorage` (`connectsphere.view`), so a refresh returns to it.

**Done in SCRUM-106:** `frontend/src/auth/SignUpPage.tsx` (reached from **Create an account** on the login page): name, email, password and Organiser or Attendee only (AC 6, 7), with field errors before anything is sent. It calls `supabase.auth.signUp` with `full_name` and `role` in the user metadata and `emailRedirectTo` set to the app's own origin, then shows "Check your email to confirm your account" with nobody logged in. An email that already has an account is refused (TC-US16A-43): with "Confirm email" on, Supabase answers it with a user that has no identities instead of an error, and the page reads that as "already registered". **That tells anyone whether an address has an account**, seeded staff included. Supabase's own answer is designed to hide it; showing the same "Check your email" for both would too, but TC-43 asks for a refusal, so it's a product call for the PO (PR #75 review). The first login after confirming gets `403 PROFILE_REQUIRED` from `GET /api/v1/me`. `App.tsx` then calls `POST /api/v1/auth/profile` with the saved name and role (`completeProfile` in `auth/signUp.ts`), and opens the role's home screen. If that answers `409 EMAIL_ALREADY_REGISTERED`, `completeProfile` reads `/me` again first: the confirmation link's tab, a retry or React StrictMode's double effect may have created this account's own profile already. Only if `/me` still has no profile does the 409 stand. Logging in before confirming says "Confirm your email first" (`email_not_confirmed`, from SCRUM-105), not "Email or password is incorrect". Metadata can never make anyone staff: only `organiser` or `attendee` is read, and the backend refuses any other role anyway. A profile refused because the email already belongs to one (`409 EMAIL_ALREADY_REGISTERED`) gets its own message.

### Next steps for the team after SCRUM-106

Not in SCRUM-106; each needs a decision or a ticket:

1. **Before any real user signs up: point Supabase at the deployed app.** The shared project's Site URL is `http://localhost:5173`, so every confirmation link opens localhost until it's changed. Set the Site URL and redirect URLs to the deployed address, and add it to `CORS_ORIGINS`.
2. **E2E in CI, on a separate Supabase project.** Today the login and sign-up E2E skip in CI. Don't fix that by putting the **shared** project's `SUPABASE_SECRET_KEY` in GitHub secrets: it's the admin key for the real staff logins and users, and any collaborator's PR could print it from a test or workflow. Instead, create a **CI-only Supabase project** (seeded by CI, with no real users), and have a repo admin (Gwendolyn) add *its* `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `E2E_SEED_PASSWORD` and `E2E_SIGNUP_INBOX` under Settings → Secrets and variables → Actions. `.github/workflows/e2e.yml` then passes them to the backend, the login frontend and Playwright (`${{ secrets.NAME }}`), and runs the seed with them. Agree it as a team first (PR #75 review).
3. **Resend confirmation email**: a button on the "Check your email" state (`supabase.auth.resend({ type: "signup", email })`), for anyone who loses the first email (PR #75 review).
4. **Password reset screen**: "Forgot password?" on the login page (`supabase.auth.resetPasswordForEmail`, redirecting to a "set a new password" page that calls `updateUser`). US16a has no AC for it, so it needs a ticket.
5. **Email change screen**: `supabase.auth.updateUser({ email })` sends a confirmation to the new address. The `users` row's `email` must then follow, which the backend doesn't do yet. Needs a ticket and a backend decision.
6. **"Already registered" on sign-up** (TC-US16A-43) reveals whether an address has an account: the PO decides whether to keep it or show "Check your email" for both (see "Done in SCRUM-106").
 
### Backend
 
Supabase signs access tokens with **asymmetric keys** (RS256/ES256), so the backend holds no secret. Public keys come from:
 
```
https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
```
 
Verify with `pyjwt[crypto]` and a cached `PyJWKClient`, checking `audience="authenticated"` and `issuer=<url>/auth/v1`. The claims we need are `sub` (stable Supabase user id) and `email`. One token check resolves the `users` row; `get_current_user` and `get_current_attendee` both build on it, and the role comes from `users.role`.
 
### Linking to `users`
 
Our rows have their own UUIDs, and seeded ones come from `uuid5`, so no Supabase user sits behind them. A column links them rather than repurposing the primary key. **Done in SCRUM-101** (migration `20261015_1200_us16a_auth_link`; full DDL in §2):
 
```sql
alter table users
  add column auth_user_id uuid,
  add constraint users_auth_user_id_key unique (auth_user_id),
  add column full_name    text;
```

There's deliberately no foreign key to `auth.users(id)`: the test database has no `auth` schema, and a FK would block deleting a user in Supabase.
 
Every attendee has a `users` row with the same id, so linking `users` covers attendees too. The token check (SCRUM-102, `app/user/dependencies.py`): verify token → look up by `auth_user_id` → else **look up an unlinked, active Organiser or Attendee by email (ignoring case, row locked) and link it, if the token says the email is verified** → else `403 PROFILE_REQUIRED`, and the first login after confirming the email creates the profile with `POST /api/v1/auth/profile` (SCRUM-103, §3). Matching on email keeps the seeded demo accounts working the moment the real person signs in, instead of creating duplicates. Staff rows are never linked by email (deviation 20); the seed links them (SCRUM-104).

**"Confirm email" is on** in the Supabase dashboard (Authentication → Sign In / Providers → Email), decided in the PR #55 review: sign-up sends a confirmation link, and no session exists until it's clicked, so nobody can log in as an email they don't own. Supabase's built-in email service is rate-limited and meant for testing; real sign-ups need a custom SMTP provider.

The key fetch is built on the first token, not at startup, and uses certifi's CA bundle: python.org's macOS Python has none, which would fail every login. Supabase unreachable is `503 AUTH_UNAVAILABLE` and `SUPABASE_URL` unset is `500 AUTH_NOT_CONFIGURED`, so neither looks like a bad token. The backend logs a warning at startup while `AUTH_DEV_HEADERS` is on.
 
### Consequences to keep in mind
 
- **Tests must not reach the network.** Keep the dependency overridable, or inject the verifier so tests supply claims directly. The existing suite should need nothing beyond the fixture.
- RLS stays on with no policies. The browser only calls Supabase Auth and the Data API stays disabled, so the publishable key reads no tables. Policies are needed only if the Data API is ever enabled; until then FastAPI's role checks (US16b) are the access control. New tables still enable RLS in their migration.
- **CORS already allows `Authorization`** (`allow_headers=["*"]`). Cookie-based sessions would instead need `allow_credentials=True` and specific origins.
 
### Seeded logins (SCRUM-104)

Staff can't sign up (US16a AC 7), so `python -m app.seed` creates a confirmed Supabase login for each seeded user (`SEEDED_LOGIN_EMAILS`: the organiser, the coordinator, venue staff, the two Coordinator Leads and the four demo attendees) through the Admin API, then links each row by `auth_user_id`. It needs `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (`sb_secret_…`) and `SEED_AUTH_PASSWORD` in `backend/.env`; without them it prints that logins were skipped and seeds everything else as before. Every login it creates carries `app_metadata.seeded_by = "app.seed"`. An account that already exists is found by email and reused, password unchanged, **only if it has that mark and a confirmed email**; anyone can sign up with an unused staff address first, so any other account is refused and nothing is linked (PR #56 review). A row already linked to a different account is never re-pointed. Every login is fetched and checked before any row is linked, so a failure (an Admin API refusal, a timeout or a malformed reply) names the email and links nothing, and `python -m app.seed` exits 1. The key and password are `SecretStr` in `Settings`; the password must be at least 12 characters. Demo accounts only: they share one password. The nine logins were created on Supabase on 24 Oct (for the SCRUM-105 login E2E) and marked the same day.

Sources: [Supabase JWTs](https://supabase.com/docs/guides/auth/jwts), [API keys](https://supabase.com/docs/guides/api/api-keys).
 
---
 
### US16b role-based access: decisions (25 Oct)

SCRUM-82 had no subtasks or test cases. Before any code, the story owner (Calvin) checked each AC against the code and took six decisions, recorded as D45 to D50. They shape the three subtasks: SCRUM-119 (backend, roles as a list), SCRUM-120 (backend, scope and refusals) and SCRUM-121 (frontend, role switcher). Test cases TC-US16B-01 to 23 are in Jira and `docs/testing/US16b-role-based-access.md`.

**Where the code stood:** every user had exactly one role (`users.role`); `venue_staff` and `safety_officer` didn't exist, and `operations_manager` stood in for Venue Staff (D19) in 31 files. Staff routes already refused other roles (`403`), venue booking and equipment were already scoped to the assigned coordinator (D20), and attendees already couldn't reach any staff route. Two gaps went beyond the role list: any coordinator could read every submitted request and send it a clarification (D11, D14), and AC 4 speaks of "organisations", which the data model doesn't have.

| # | Decision | Logic and reasoning | Alternative considered, and why not | Consequence |
|---|---|---|---|---|
| D45 | **Roles are a list column on `users`** (`roles user_role[]`, at least one, no repeats), replacing `users.role` | AC 1 changed "exactly one role" to "one or more". A list keeps one row per user, so every check stays a membership test (`role in user.roles`) and queries use `= ANY(roles)`. Named CHECKs enforce "at least one" and "no repeats" in the database. The role set is small and fixed by the customer | A `user_roles` join table: more normalised, but every role check becomes a join or an extra query, and nothing needs per-role metadata (dates, scopes) yet. If it ever does, the list migrates cleanly to a table | One migration in SCRUM-119 rewrites every `user.role` check; `/me` returns `roles`. The downgrade refuses while anyone holds two roles |
| D46 | **The API authorises by every role a user holds**; the current role lives only in the frontend | AC 3 says a user is refused for a role they *don't hold*, not one they aren't currently using. Holding is the security boundary, and the switcher (AC 2) is about what the user sees. Keeping the API stateless about the current role means no header to forge or forget, and every existing route works unchanged | Sending an active-role header and refusing everything else: stricter than AC 3 asks, adds a header to every call and a new way to be refused, and a user could still switch it freely, so it adds no real protection | SCRUM-119 changes `require_user_roles` to "holds any of"; SCRUM-121 builds the switcher and filters navigation by the current role |
| D47 | **An organiser's "organisation" is the organiser themselves**: another organiser's request is `404` | No AC, field or sign-up step defines an organisation; the only data is who created a request. Owner-only already gives AC 4's outcome: "another organisation's request behaves as if it doesn't exist" (D11 returns `404`). So the AC is met without inventing a model nobody specified | An `organisations` table with members: sign-up would have to ask for one, and requests would belong to it. No AC asks for that, and it would change US1 and US16a. Raise it with the PO if organisations really share requests | Tested as AC 4 in SCRUM-120 (TC-US16B-12). **To confirm with the PO** at the sprint review |
| D48 | **Coordinators see and act only on requests assigned to them**: the review queue, a request's details and thread, and sending a clarification; anyone else `404` | AC 5: "An Event Coordinator can only manage events assigned to them." Since US10a, every request a coordinator should work on is assigned by a Lead first, so the assignment is the right boundary. D14 itself said to tighten to the assigned coordinator once assignment existed. It also matches D20 (venues) and equipment, so there's one rule for coordinators everywhere. `404` rather than `403` follows D11: a request you can't see behaves as if it doesn't exist | Leaving D11 and D14 as they were: every coordinator could keep reading and clarifying every submitted request, which contradicts AC 5 | SCRUM-120 retires D14 and narrows D11 for coordinators; Leads keep their view. The clarification E2E journey gains a Lead-assign step, since a coordinator no longer sees a request straight after it's submitted |
| D49 | **`operations_manager` is retired**: its users become `venue_staff`; nothing checks it any more | It was only ever a stand-in until US16b added the real role (D19), and keeping it would make "Venue Staff" mean two values. Postgres can't drop an enum value, so it stays in `user_role`, unused | Keeping both, with `operations_manager` meaning Venue Staff: two names for one job and checks that must list both | SCRUM-119 migrates the users, `VENUE_STAFF_ROLES` becomes `venue_staff`, and the seed and **Acting as** follow |
| D50 | **The two-role seed user is `multi.role@smu.edu.sg`, Coordinator and Venue staff** | US16b's subtask note asks for "one user with two roles". Both roles have their own screens (Event requests; Venues with the pending list), so switching visibly changes navigation in the E2E check (TC-US16B-23). They're also a realistic pairing: a coordinator who also helps run venues | Organiser and Attendee: both can be self-signed, so it says little about staff, and attendee screens use a different identity path. Pairings with Tech support or Safety officer: one side has few or no screens yet | The seed adds the user with a Supabase login; the login E2E uses it |

These are the story owner's decisions; D47 also needs the PO's confirmation. Each is marked `DECISION-PENDING` in the code when its subtask lands, like the other open decisions.

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
| TC-US8-02 … 04, 14 † | SCRUM-11 | AC 1: select the section(s) the clarification concerns and add a comment |
| TC-US8-09, 11 | SCRUM-11 | AC 2: first request only while Submitted or Under Review |
| TC-US8-09, 10 † | SCRUM-11 | AC 3: once sent, status becomes Awaiting Clarification |
| TC-US8-01, 05 … 08 † | SCRUM-11 | (Storage groundwork — SCRUM-54) |
| TC-US8-12, 13, 15, 16 † | SCRUM-11 | (Access rules and review queue — D11, D14) |
| TC-US8-25, 29, 30 | SCRUM-73 | AC 1: Organiser notified with the Coordinator's comment |
| TC-US8-25 | SCRUM-73 | AC 2: notification identifies the request and section(s) |
| TC-US8-26 … 28 | SCRUM-73 | AC 3: no notification if the request isn't sent |
| TC-US8-17, 18 | SCRUM-74 | AC 1: response appended to the thread, question still above it |
| TC-US8-17 | SCRUM-74 | AC 2: status back to Under Review on response |
| TC-US8-18 + E2E thread step | SCRUM-74 | AC 3: Coordinator views the full thread |
| TC-US8-19 … 22, 24 † | SCRUM-74 | (Only an open round can be answered; access — deviation 14, D11) |
| TC-US8-23, 31, 33 | SCRUM-75 | AC 1: further rounds, no limit (D15 refuses while a round is open, against AC 1's "Awaiting Clarification") |
| TC-US8-33 … 35 | SCRUM-75 | AC 2: none once Approved, Rejected or later |
| TC-US8-32 | SCRUM-75 | AC 3: rounds kept in order, earlier ones visible |
| TC-US6A-01, 03, 10 | SCRUM-10 | AC 1: offered only when full and waitlists are supported |
| TC-US6A-02, 04 … 06, 10 | SCRUM-10 | AC 2: not offered with places left or no waitlist |
| TC-US6A-03, 07 | SCRUM-10 | AC 3: added to the waitlist, position confirmed |
| TC-US6A-08, 09 | SCRUM-10 | (Registration gates — D16; seed) |
| TC-US6B-08, 09 | SCRUM-72 | AC 1: next waitlisted Attendee notified a place is available |
| TC-US6B-01, 06 †, 09 | SCRUM-72 | AC 2: accept the place; waiting-listed → registered |
| TC-US6B-02, 03 † | SCRUM-72 | AC 3: no offer, no place; status stays waiting-listed |
| TC-US6B-04, 05, 07, 10 † | SCRUM-72 | (Ownership, expiry, start cutoff — deviations 13, 15) |
| TC-US11-12 | SCRUM-5 | (Rows carry `event_id` for the events board — SCRUM-79) |
| `tests/registration/test_seed_reseed.py` (3 tests, no TC ID) | SCRUM-79 | (Reseeding works after app use) |

| TC-US2-01, 13 | SCRUM-7 | AC 1: search by date, start and end time, expected attendance |
| TC-US2-02, 14 | SCRUM-7 | AC 2: filter by location, accessibility and facilities |
| TC-US2-03, 13 | SCRUM-7 | AC 3: capacity, facilities and accessibility on each result |
| TC-US2-04, 13 | SCRUM-7 | AC 4: capacity at least the expected attendance |
| TC-US2-05, 11, 12, 13 | SCRUM-7 | AC 5: not booked (approved), tentatively held (requested) or blocked for the time |
| TC-US2-06, 14 | SCRUM-7 | AC 6: inside operating hours |
| TC-US2-07, 15 | SCRUM-7 | AC 7: "no matching venues" with the criteria applied |
| TC-US2-08, 13 | SCRUM-7 | AC 8: results within 3 seconds |
| TC-US2-09, 10, 16 | SCRUM-7 | (Input validation and who may search — D25, deviation 31) |

† §4 doesn't tag an AC for these IDs; they're mapped by what the test checks.
