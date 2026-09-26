# ConnectSphere — Sprint 1 Development Spec
 
**Source of truth:** Jira project `SCRUM` (SPM ConnectSphere) — https://smu-team-kk38iw8n.atlassian.net
**Generated:** 2026-09-19 from Jira issues SCRUM-2, SCRUM-5, SCRUM-6 and their subtasks.
**Stack:** FastAPI (Python) backend · Supabase (Postgres) · frontend is a **static UI mockup only** this sprint.
 
---
 
## 0. How to use this document
 
This is a **test-case-driven** spec. Every behaviour below traces back to an acceptance criterion written by the team in Jira. Work in this order:
 
1. Read §2 (data model) and §3 (API contracts) — they are proposals, not gospel; if you deviate, say so explicitly.
2. For each story, write the tests in §4 **first**, as failing tests. Test IDs (`TC-US3-01`, …) are stable references — use them as test function names, e.g. `def test_tc_us3_01_lists_only_confirmed_registration_open_events():`.
3. Implement until the tests pass.
4. Check §5 — the subtask-to-test mapping is the definition of done for each Jira ticket.
5. §6 lists real ambiguities in the acceptance criteria. **Do not silently invent an answer.** Use the stated Sprint 1 default and leave a `# DECISION-PENDING: <id>` comment at the code site.
Anything not in §4 is out of scope for Sprint 1. See §7.
 
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
 
---
 
## 1a. Progress — updated 26 Sep 2026
 
Read this with §5; the subtask tables below are still the definition of done. This section records what is actually built. Update it when something merges.
 
### Merged to `main`
 
| Ticket | What landed | Where |
|---|---|---|
| SCRUM-24 | `registrations`, `attendees`, `attendance_log` and the §2 `events` schema, with the partial unique index | PR #13 |
| SCRUM-28, 29, 32, 33 | Frontend mockups: events board, event card, registration dialog, confirmation ticket, My Events | PRs #11, and SCRUM-5 branch |
| — | CI: split workflows, Dependabot, markdown lint, PR title check | PRs #1, #12 |
| — | E2E fix: `wait-on` probed with HEAD against a GET-only route and hung until the 6-hour limit; now `http-get://` with timeouts. `health.spec.ts` also asserts the backend's real response | PR #14 |
| — | CORS middleware, so the frontend origin can call the API at all | — |
 
`attendees` is **not in §2**. The spec references `attendees(id)` without defining the table, so SCRUM-24 added the minimal version (`id`, `email`, `created_at`). Revisit when Supabase Auth lands.
 
### Open branches, awaiting review
 
| Branch | Ticket | Contents |
|---|---|---|
| `feat(SCRUM-6)Withdrawal-from-an-Event-Registration` | SCRUM-34, 36, 37, 39 | The whole withdrawal backend and 30 tests |
| `feat(SCRUM-23)-seed-mock-events` | SCRUM-23 | `python -m app.seed`, idempotent |
| `chore(backend)pin-python-and-restore-env-example` | — | Pins Python 3.12, restores `.env.example` |
 
### SCRUM-6 (Calvin) — backend complete
 
Endpoints, all under `/api/v1/registrations/{id}`:
 
| Endpoint | Does | Ticket |
|---|---|---|
| `POST .../withdraw` | Flips to `withdrawn`, stamps `withdrawn_at`, logs it, and passes a freed confirmed seat to the head of the waitlist | SCRUM-34, 35, 39 |
| `POST .../expire-offer` | Ends an outstanding offer (`expired`) and offers the seat on. Manual stub, no scheduler | SCRUM-37 |
| `POST .../decline` | The offer holder turns the seat down (`declined`); it moves on immediately | SCRUM-37 |
 
Supporting pieces: `core/exceptions.py` (machine-readable `code`), `core/clock.py` (injectable `now`), `user/dependencies.py` (`X-Attendee-Id` stub), `notification/service.py` (a `Notifier` protocol, logged not sent).
 
| Subtask | State |
|---|---|
| SCRUM-34 endpoint + guards | Done |
| SCRUM-35 capacity release | Done — TC-US7-13 can't be *observed* until `GET /events/available` (SCRUM-25) exists |
| SCRUM-36 waitlist offer trigger | Done |
| SCRUM-37 offer expiry / decline | Done, as the manual stub the ticket asks for |
| SCRUM-39 record the withdrawal | Done |
| SCRUM-38 frontend withdraw | Partly — My Events has "Cancel registration" and "Leave waitlist" buttons, but no confirm dialog and no post-withdrawal confirmation |
 
**TC-US7 coverage: 14 of 15**, in 30 backend tests. Only **TC-US7-13** is outstanding, and it is blocked on SCRUM-25.
 
The waitlist is FIFO but **derived**: the head is the oldest `waitlist_joined_at`, with `id` breaking ties, locked `FOR UPDATE` alongside the event. No position is ever stored.
 
### Deviations to confirm at standup
 
1. Withdrawing an `offered` registration returns `409 REGISTRATION_NOT_ACTIVE`, a code **not in the §3 table**. Releasing an offer is a decline, not a withdrawal.
2. `POST .../decline` is **not in §3's endpoint list**. TC-US7-11 needs declining to be distinct from letting the window lapse.
3. `expire-offer` deliberately does **not** check that `offer_expires_at` has passed, and isn't restricted to the offer holder — it stands in for a system job (`DECISION-PENDING: D2`).
4. Offer-release responses say *whether* the seat was passed on, never to whom (TC-X-04).
 
Open decisions in play: **D1** (24h window, one constant), **D2** (what expires an offer), **D5** (on-screen confirmation only), **D6** (a waitlisted person may leave — implemented, TC-US7-14).
 
### Next steps
 
1. **Review and merge the three open branches**, schema-adjacent ones first.
2. **SCRUM-38 — finish the mockup**: confirm dialog before withdrawing, post-withdrawal confirmation. Mockup-only; §7 still forbids wiring React to FastAPI.
3. **Seed Supabase** with `python -m app.seed --yes` once SCRUM-23 merges — the tables are still empty, which blocks manual testing for everyone.
4. **TC-US7-13 stays blocked** until SCRUM-25 exists.
5. **Notification logging**: `LoggingNotifier` writes to its own logger, which uvicorn's default config doesn't display, so an offer is invisible in the server log during a demo.
 
### Environment notes
 
- **Supabase is migrated** to revision `dcc645f2c595`; all four tables exist, all **empty** until the seed script merges and runs.
- **RLS is off on all four tables.** Safe only while the Data API stays disabled. Enable RLS before anyone turns that API back on.
- **Backend tests need a local Postgres**: `docker compose up -d postgres`. They build a separate `connectsphere_test` database from the migrations and refuse to run against Supabase.
- **Python 3.12** — pinned in `backend/.python-version`, matching CI. A 3.13 virtualenv can pass locally and fail in CI.
- **No dependency lock on the backend.** `pyproject.toml` uses open ranges (`fastapi>=0.115`), so two machines can resolve different versions. The frontend has `package-lock.json`; the backend has nothing equivalent.
 
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
- A working frontend. **Mockups only.** Do not wire React to FastAPI this sprint.
- Payments, check-in, attendance marking, feedback — nowhere in the backlog
---
 
## 8. Conventions
 
- **Tests:** `pytest` + `httpx.AsyncClient`. Name tests after their IDs. Use a transactional fixture that rolls back per test; never test against seeded production-ish data you also mutate.
- **Time:** freeze it (`freezegun` or an injected `now()` provider). TC-US3-04, TC-US3-05, TC-US7-03 and TC-US7-04 are unreliable otherwise.
- **Structure:** routes stay thin. Guard logic and state transitions live in a service layer so they can be tested without HTTP.
- **Errors:** every 4xx returns a machine-readable `code`, exactly as spelled in §3. The mockup keys off `code`, not off message text.
- **Migrations:** every schema change is a migration file in the repo. No changes made only in the Supabase dashboard.
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
 