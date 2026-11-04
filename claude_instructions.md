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
| SCRUM-82 | US16b — Role-based access | Calvin | 3 (**carried over to Sprint 4**: planned on 25 Oct as SCRUM-119 to 121, nothing built in Sprint 3; see §1a) |
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
| CR-04 | Venue holds expire | US25 (SCRUM-93); affects D2. Holds should lapse on read like waitlist offers (§1a rule "Lapse on read", SCRUM-137) |
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
| SCRUM-6 — withdraw from a registration | Done. Bug SCRUM-137: a lapsed offer expires on the next read or change of its event's registrations and the place passes to the next person, or back to capacity (D1, D2 settled) | **Real screens, wired to API** (SCRUM-79); since SCRUM-137 My events shows a lapsed offer muted, under Offer expired | TC-US7 24/24 + E2E |
| SCRUM-20 — submit event request (US1) | Done | **Real screens, wired to API** | TC-US1 16/16 + 1 E2E |
| SCRUM-11 — request clarification (US8a) | Done: storage (SCRUM-54), send endpoint (SCRUM-53), review queue (SCRUM-57) | **Real screens, wired to API** (SCRUM-57) | TC-US8 16/16 + 1 E2E |
| SCRUM-10 — join a waitlist (US6a) | Done: availability rule (SCRUM-48) + join refusals (SCRUM-49). Bug SCRUM-136: joining takes the logged-in attendee (`get_current_attendee`, `401` without a login) and no body, so every new place has an attendee and can accept an offer; an attendee's email-only place from before is linked to them when they try to join (D3, D7 settled) | Attendee screens wired (SCRUM-79); join prompt + position confirmation done (SCRUM-52); since SCRUM-136 joining is one button, with no email typed | TC-US6A 15/15 + E2E |
| SCRUM-72 — take up a place (US6b) | Done: offer notice (SCRUM-50) + accept (SCRUM-51) | **Real screens, wired to API**: Place available + Accept place (SCRUM-76) | TC-US6B 10/10 + 1 E2E |
| SCRUM-74 — organiser responds (US8c) | Done: response endpoint + thread read (SCRUM-77) | **Real screens, wired to API**: response form (SCRUM-78), thread view (SCRUM-58) | TC-US8-17 to 24 + E2E |
| SCRUM-75 — more clarification rounds (US8d) | Done: rounds guard pinned as D15 (SCRUM-56) | No change needed | TC-US8-31 to 35 |
| SCRUM-13 — assign a Coordinator (US10a) | Done: schema + seed, unassigned queue, coordinator picker and assign endpoints, Lead notified on submit (log-only, D28) | **Real screens, wired to API**: Lead's unassigned queue, coordinator picker and confirm, **Coordinator Lead** in Acting as, the organiser sees "Unassigned" or the coordinator's name | TC-US10A-01 to 32; evidence per AC in `docs/testing/US10-coordinator-assignment.md` |
| SCRUM-68 — notify Coordinator and Organiser of an assignment (US10c) | Done: `Notifier.assignment_made`, called after a successful assign (log-only) | No change needed | TC-US10C-01 to 07; evidence per AC in `docs/testing/US10-coordinator-assignment.md` |
| SCRUM-67 — see Coordinator workload when assigning (US10b) | Done: `GET /api/v1/coordinators` gives each entry a `planning_count` (D30) | **Real screens, wired to API**: the picker shows each coordinator's name and "N events planning" | TC-US10B-01 to 06 (backend), 07 to 09 (frontend) + the E2E picker check; evidence per AC in `docs/testing/US10-coordinator-assignment.md` |
| SCRUM-86 — Lead's queue and oversight view (US19) | Done: `GET /api/v1/event-requests/assigned` (the active events this Lead assigned, filter by `coordinator_id` and `status`, soonest event date first; Lead only; D44). No new table: the Lead's scope is the assigner on an event's latest `coordinator_assignments` record | **Real screens, wired to API**: the Lead's page has **Unassigned** and **Assigned** tabs, coordinator and status filters, and a read-only request view from either tab (deviation 40) | TC-US19-01 to 11 (backend), 12 to 18 (frontend) + the E2E assign journey checks the tab, filter and view |
| SCRUM-69 — assignment history (US10d) | Done: `coordinator_assignments` table (SCRUM-63), written in the assign transaction; `GET /api/v1/event-requests/{id}/assignment-history`, Lead only, newest first (SCRUM-64) | **Real screens, wired to API**: the Lead's queue page lists Assigned requests, each with History, and Coordinator assigned offers View assignment history (SCRUM-66; deviation 35). Each entry says which it was: "Lena Lim assigned Casey Tan", or "Lena Lim reassigned the event to Dana Lim" (since 1 Nov) | TC-US10D-01 to 10 and 15 (backend), 11 to 14 (frontend) + the E2E assign journey checks the history; evidence per AC in `docs/testing/US10-coordinator-assignment.md` |
| SCRUM-84 — approve or reject an event request (US17) | Done: decision columns + CHECKs (migration `20261029_1200_us17_decisions`, for the Supabase owner to apply after merge), `POST /api/v1/event-requests/{id}/approve` and `/reject` for the assigned coordinator (D48, D51, D53), `Notifier.request_decided` to the organiser (log-only); every request body carries `decided_at`, `decided_by`, `rejection_reason` | **Real screens, wired to API**: Approve / Reject with a required reason on the coordinator's review screen (own assigned, Under Review requests only); the outcome on both screens | TC-US17-01 to 17 (15 pytest + 2 E2E) + frontend integration; see `docs/testing/US17-approve-reject-request.md` |
| SCRUM-83 — reassign an event (US10e) | Done: `POST /api/v1/event-requests/{id}/reassignment` (Lead only; a different active coordinator and a reason; active events only; history row `reassignment` with the reason in the same transaction), `POST /api/v1/event-requests/{id}/transfer-request` (the event's coordinator asks, every active Lead is told, nothing moves), `Notifier.event_reassigned` to the organiser and both coordinators, migration `20261030_1200_us10e_reassign` (`reason` column); the previous coordinator loses the event's request, thread and send-clarification access (D54) and the new one gains the venue withdraw (D20) | **Real screens, wired to API**: **Reassign to another coordinator** in the Lead's request view (current coordinator not offered, reason required), the history shows each reassignment's reason. **Request a transfer** for the event's coordinator since SCRUM-146 (below; deviation 48) | TC-US10E-01 to 24 (backend), 25 to 28 (frontend) |
| SCRUM-85 — confirm an event (US18) | Done: `GET /api/v1/event-requests/{id}/readiness`, `POST …/confirmation` and `POST …/preparation` (the assigned coordinator only, D48); an event is confirmed once its venues are arranged (US24's rule, D72), its equipment lines are approved and reserved, technical support is assigned where it was requested and the Safety Officer has approved (D86); the event takes its date and capacity from its approved bookings; the organiser gets `Notifier.event_confirmed`; new status `preparation` after `confirmed` (registration stays open through it); a coordinator now opens their own event in Planning, Confirmed and Preparation (widens D11); migration `20261109_1200_us18_confirm`; seeds **Confirmation Demo**. **Not built:** the Safety Officer's approval (US30a, SCRUM-99), so only the seeded demo and tests are ready to confirm until it lands, and the Venue staff and Technical support preparation updates the AC unlocks in Preparation | **Real screens, wired to API**: on a request the coordinator opens from their review queue, a Readiness list (each venue booking, equipment, technical support, safety check, complete or outstanding), **Confirm event** (disabled until ready), **Check again**, then **Start preparation** (deviation 59) | TC-US18-01 to 29 and 38 to 43 (backend), 30 (E2E) and 31 to 37, 44 (frontend); all pass |
| SCRUM-99 — operational safety review (US30a) | Done: `safety_reviews` (migration `20261110_1200_us30a_safety`, plus `events.safety_review_requested_at`; RLS on since `20261114_1200_us30a_rls`, a fix: the first migration left it off); the Safety officer's queue, review and decision `GET /api/v1/safety-reviews`, `GET …/{event_id}`, `POST …/{event_id}` (seven checklist items, comments, internal notes; approve sets `safety_approved_at`, which is what lets US18 confirm; reject leaves the event where it is); `GET /event-requests/{id}/safety-reviews` for the organiser, coordinator and Lead (no internal notes) and `POST …/safety-review-request` for the coordinator to send a rejected arrangement back; `Notifier.safety_review_decided` to the coordinator; Preparation refuses an event without an approved review (`SAFETY_NOT_APPROVED`); seeds **Safety Review Demo**. **Not built:** a change log of attendance, venue, access and equipment edits (deviation 62). Requesting changes is US30b (SCRUM-100, below) | **Real screens, wired to API**: the Safety officer's **Safety reviews** screen (queue, event details, venues, equipment, earlier reviews, the checklist, comments and internal notes, **Approve** and **Reject safety arrangement**); the organiser's request view and the coordinator's review screen show the **Safety review** outcome, and the coordinator's has **Send for another review** | TC-US30A-01 to 31 (backend), 40 and 41 (frontend, E2E) and 42 to 47 (frontend); all pass |
| SCRUM-100 — request changes after a safety review (US30b) | Done: a third review outcome, `changes_requested` (migration `20261113_1200_us30b_changes`, after US23a's `20261116_1200_us23a_blocks`: `safety_reviews.areas`, the outcome and a CHECK that it carries comments and at least one area); `POST /api/v1/safety-reviews/{event_id}` takes `outcome: "changes_requested"` with `comments` and `areas` (`venue`, `layout`, `equipment`, `accessibility`, `other`); the event keeps its status and nothing is reset (deviation 64); the coordinator is told by `Notifier.safety_changes_requested` (comments, areas, flagged items); the coordinator marks the changes done with the existing `POST …/safety-review-request`, which puts the event back in the Safety Officer's queue to be reviewed again, with the earlier review kept in its history (D99). **Not built:** a change log of what the coordinator changed (deviation 62) | **Real screens, wired to API**: **Request changes** and the **Areas affected** tick boxes on the Safety Officer's review; the organiser's and coordinator's **Safety review** panel shows the areas and comments, and the coordinator's has **Mark changes done** | TC-US30B-01 to 19 (backend), 30 (E2E) and 31 to 37, and TC-US30A-50 (frontend); all pass |
| SCRUM-107 — view my notifications (US31) | Done: `notifications` (migration `20261116_1200_us31_notifications`: one row per recipient, with the sentence written when the notice was raised, no foreign keys, D116); the app's notifier is now `RecordingNotifier` over the logging one, so **every** `Notifier` method also keeps a row for its recipient (the 23 in `app/notification/service.py`, including the cancellation notices); `GET /api/v1/me/notifications` (newest first, `unread_only`, `limit` up to 100, with `unread_count` and `can_open`), `GET …/unread-count`, `POST …/{id}/read` and `POST …/read-all`, open to every signed-in role. **Not built:** email, push or real-time delivery (the count refreshes every 30 seconds), settings to mute a kind, notifications from before this change (not backfilled), and a link for roles with no screen for the event (deviation 74) | **Real screens, wired to API**: **Notifications** on every role's header with the unread count, and a screen listing the user's own (event, what happened, when, unread marked), **Mark as read**, **Mark all as read**, and **Open request** where the user may open it | TC-US31-01 to 11 and 20 to 33 (backend), 40 to 57 (frontend), 60 (E2E); all pass |
| SCRUM-87 — venue catalogue (US20) | Done: schema + seed (PR 1, #53); endpoints, Venue Staff stub (D19), validation, buffer-lock stub (PR 2) | **Real screens, wired to API**: Venues list with filters, staff create/edit form (PR 2) | TC-US20-01 to 19 (07's booking half is TC-US22-01) + 2 E2E; see `docs/testing/US20-venue-catalogue.md` |
| SCRUM-89 — request a venue booking (US22) | Schema (PR 1, SCRUM-111): `venue_bookings`, the no-overlap exclusion constraint, the real buffer-lock query. Endpoints (PR 2, SCRUM-112): create with warnings, withdraw, Venue Staff's pending list, an event's bookings, the Venue Staff notice, the inactive-venue read for booked coordinators | **Real screens, wired to API** (PR 3, SCRUM-113): Request venue and the event's bookings with Withdraw on an Approved request in the coordinator's review queue; Venue staff's pending list on Venues (deviation 32) | TC-US22-01 to 21 + 3 E2E; see `docs/testing/US22-venue-booking.md` |
| SCRUM-7 — search for suitable venues (US2) | Done: `GET /api/v1/venues/available` (hides live US22 bookings and `venue_blocks`), `venue_blocks` table, seeded slot | **Real screen, wired to API**: search form on Venues for Coordinator and Venue staff | TC-US2-01 to 16 (12 pytest + 4 E2E) + frontend unit and integration; see `docs/testing/US2-venue-search.md` |
| SCRUM-8 — approve or reject a venue booking request (US4) | Done: decision columns + CHECKs (migration `20261025_1300_us4_decisions`), `POST /api/v1/venue-bookings/{id}/approve` and `/reject`, buffered conflict check on approve (D38), refusals for a passed start (`BOOKING_EXPIRED`) and for attendance over a since-reduced capacity, `Notifier.venue_booking_decided` (log-only) | **Real screens, wired to API**: Approve and Reject (with optional reason and alternative) on Venue staff's pending list; the coordinator's bookings show the decision and notes | TC-US4-01 to 11 (63 pytest + 2 E2E) + frontend unit and integration; see `docs/testing/US4-booking-decision.md` |
| SCRUM-16 — setup and turnaround buffers (US13) | Schema (PR 1, SCRUM-114): each booking stores its occupied window, `venue_bookings_no_overlap` covers it, bookings get a `VB-` reference; US2 search's booking check reads the stored window. API (PR 2, SCRUM-115): the reusable rule US4 calls (`app/venue/availability.py`), opening hours (`VENUE_OUTSIDE_HOURS`), the overlap in `VENUE_UNAVAILABLE`, Venue Staff's evaluation endpoint, the buffer-edit recompute (`VENUE_BUFFERS_CONFLICT`), US2 search with each venue's own buffers and hours. Screens (PR 3, SCRUM-116): the booking form previews the window the chosen venue's setup and turnaround occupy, with its hours; `VENUE_OUTSIDE_HOURS` shows on the time field that breaches (editing either time clears both fields' errors, since moving the other end can fix it; PR #83 review) and `VENUE_UNAVAILABLE` names the overlap period (never the other booking's reference, D35); the event's bookings panel and Venue staff's pending list show each booking's `VB-` reference and occupied window; each pending row shows its evaluation (conflicts with the overlap and the clashing reference, an hours breach, or none), fetched again after a refused approval. Approve is still offered on a row with conflicts: the API refuses it with the reason (US4 AC 3). **Known cost:** the pending list fetches one evaluation per row (N+1 requests); if the queue grows, add a batch evaluation endpoint or include each evaluation in `GET /venue-bookings/pending` | Done | TC-US13-01 to 19 (`docs/testing/US13-buffers.md`) |
| SCRUM-88 — venue availability calendar (US21) | API (PR 1, SCRUM-122): `GET /api/v1/venues/{id}/calendar?from=&to=` for Coordinators, Leads and Venue staff (D56): the venue's live bookings (Requested too, D57) with their stored occupied windows, and its blocks, over Singapore days, at most 42 (D61); each booking with its event's name and status, and its `VB-` reference only for Venue staff, Leads and the event's coordinator (D58); withdrawn and rejected bookings left out, a cancelled event's live ones shown with the event `cancelled` (D60); an inactive venue for Venue staff, Leads and a coordinator whose event is booked there (D61); no holds until US25 (D59); `422 INVALID_DATE_RANGE` (deviation 51). No migration. Screens (PR 2, SCRUM-123): an Availability calendar on Venues for the Coordinator, Lead and Venue staff roles, not the Organiser (D56): choose a venue (Venue staff also see inactive ones), Week or Month, Previous / Today / Next, all in Singapore days. The week view draws each booking over its occupied window with its setup and turnaround parts named, a Requested one dashed and labelled "Booking (requested)" (D57), blocks as "Unavailable" with their note, and the hours outside opening shaded "Closed" (D61); the month view lists the same as chips per day. Opening an item shows the event's name and status (a cancelled event's too, D60), the booking's status, its times and occupied window, and the `VB-` reference only when the API gives it (D58); no link into the request. No calendar library (`calendarGrid.ts`); holds aren't drawn until US25 (D59) | Done | TC-US21-01 to 24 pass (`docs/testing/US21-venue-calendar.md`) |
| SCRUM-92 — book multiple venues for one event (US24) | Schema + seed (PR 1, SCRUM-127): migration `20261103_1200_us24_multi_venue` gives each booking a `purpose` (D66; existing ones "Main venue") and `is_primary`, with `venue_bookings_one_primary_per_event` allowing one live primary per event (D68; the upgrade makes each event's first live booking primary), and a `preparation_status` (`not_started`, `in_progress`, `ready`; D73, CS3-49), existing bookings `not_started`. The seed gives each in-person event with a seeded venue an approved primary booking over its own times (D65, D70), makes US2's slot bookings primary, and adds **Multi-Venue Conference Demo** (approved, assigned to the dev coordinator): an approved primary main hall that Venue staff are preparing (`in_progress`), a requested breakout and a rejected one; a reseed deletes any other booking on it, such as the Breakout C each E2E run adds and withdraws (SCRUM-129), and a non-local reseed says so first. Decisions D65 to D73, deviation 53 Endpoints (PR 2, SCRUM-128): every request has a purpose (D66, now required: the column lost its default) and a window within the event's schedule (D65); the event's first live booking is its primary venue and `make-primary` moves it (D68); `withdraw` takes an Approved booking too, which keeps its decision (D77) and tells Venue staff (D69); Venue staff set an approved booking's preparation status (D73); `GET /events/{id}/venue-bookings` adds the event's Organiser from approved on (D71), each booking's `unavailability` and `next_action`, and the event's `venues_arranged` (D67, D72), `primary_booking_id`, `allocated_attendees`, `expected_attendees` and `next_action`; attendees see the approved primary venue's name and location, with the board's search matching both (D70). The booking form gained a Purpose field so the UI keeps working. Screens (PR 3, SCRUM-129): the booking form shows the event's schedule (D65: its own start and end once set, else its preferred dates and times) and asks for each venue's allocated attendees with its capacity; the coordinator's panel shows each venue's purpose, allocation, status, preparation and Primary badge, the allocation against expected attendance, "Venues arranged" or what's missing, Make primary and "Choose a primary venue", and withdraws an approved venue after a confirm; the Organiser's request detail has a read-only Venues section (D71); Venue staff set an approved booking's preparation in the availability calendar's details (D78), which shows it read-only to others. The Organiser's view reads a rejection reason that already ends in `.`, `!` or `?` without adding a second full stop. The request read gained `start_at`/`end_at` and the calendar's bookings `preparation_status` (deviation 55) | Done | TC-US24-01 to 29 pass (`docs/testing/US24-multi-venue.md`) |
| SCRUM-81 — sign up, log in, log out (US16a) | Schema (SCRUM-101), token check (SCRUM-102), sign-up profile endpoint (SCRUM-103), seeded Supabase logins (SCRUM-104) and `GET /api/v1/me` (SCRUM-105) done | **Login page, logout, session** (SCRUM-105); **sign-up page and first-login profile** (SCRUM-106, #75) | TC-US16A-01 to 51, all in `docs/testing/US16a-sign-up-log-in.md`. Logged-in E2E (32, 33, 35, 36, 38, 39) skips without `E2E_SEED_PASSWORD`, and sign-up E2E (40, 41, 43, 45, 50) without `SUPABASE_URL` and `SUPABASE_SECRET_KEY`, so neither runs in CI until the secrets are added (§9 Next steps); both run locally, all pass (run log in the test doc) |
| SCRUM-94 — equipment requests (US26) | Schema + seed + `tech_support` role done (SCRUM-108); endpoints done (SCRUM-109): the catalogue, a coordinator's lines on their assigned planning or confirmed event, Tech Support's queue and review, the coordinator's notice; seeds **Equipment Request Demo**; `GET /api/v1/me/equipment-events` for the screen's event picker, and a reseed empties the demo event's equipment (SCRUM-110) | **Real screens, wired to API** (SCRUM-110): **Equipment** for the coordinator (pick an event, add, edit and remove pending lines, see decisions and notes) and as Tech support's only screen (the pending queue, Approve or Reject with a note); **Acting as** gains Tech support (deviation 42) | TC-US26-01 to 20, all in `docs/testing/US26-equipment-requests.md`; 16 and 17 are E2E |
| SCRUM-9 — check equipment availability (US5) | Schema + seed (PR 1, SCRUM-124): `equipment_types` gains `total_quantity`, `out_of_service_quantity` and `storage_location` (D62); `equipment_reservations`, read by US5 and written by US27; the seed stocks the catalogue (D63). Migration `20261101_1200_us5_equipment`, for the Supabase owner to apply after merge. API (PR 2, SCRUM-125): `POST /api/v1/equipment-lines/{id}/availability-check` for Tech Support: stock less out of service less other events' overlapping reservations, by the events' own times, with sufficient or the shortfall and the storage location; the latest outcome is recorded on the line and cleared when its quantity or type is edited (D64, deviation 52; migration `20261102_1200_us5_check_outcome`, for the Supabase owner to apply after merge) | **Real screen, wired to API** (PR 3, SCRUM-126): **Check availability** on each line of Tech support's queue shows available against requested, Sufficient or Short by N, the stock, out-of-service and reserved counts and the storage location; each line shows its last recorded check (D64); after a check the queue reloads, so Approve and Reject's change check (PR #78) isn't tripped by it | TC-US5-01 to 15 pass; 11 is E2E (`docs/testing/US5-equipment-availability.md`) |
| SCRUM-95 — reserve equipment (US27) | Schema (PR 1, SCRUM-130): each `equipment_reservations` row fulfils one approved line (`request_line_id`, unique, with a composite foreign key so its event and type are the line's) and records `reserved_by_user_id` (migration `20261104_1200_us27_reservations`, for the Supabase owner to apply after merge); the reseed removes Equipment Request Demo's reservations with its lines. API (PR 2, SCRUM-131): `POST` / `DELETE /api/v1/equipment-lines/{id}/reservation` for Tech Support, the approved line's full quantity if US5's count says it's available, the type's row locked so two can't take the last units; Tech Support's list takes `?status=approved`; every line carries `reservation`; a cancelled event's reservations count as released (D75); deviation 54 | **Real screen, wired to API** (PR 3, SCRUM-132): **Approved: to reserve** under Tech support's review queue lists approved lines with Reserve (no quantity: the full one) and Release; a refusal for want of stock says "Short by N: can't reserve" on its row; a cancelled event's reservation reads as released, with no Release (D75); the list reloads when the queue approves a line; the coordinator's lines show "Reserved" | TC-US27-01 to 18 pass; 18 is E2E (`docs/testing/US27-equipment-reservations.md`) |
| SCRUM-17 — assign Tech support staff (US14) | Schema (PR 1, SCRUM-133): `tech_staff_assignments`, one row per assignment, active until unassigned, so the rows are also the log of who assigned and unassigned whom, and when (D79); a second seeded Tech support user (Priya Nair); a reseed clears Equipment Request Demo's assignments. Migration `20261107_1200_us14_tech_staff`, for the Supabase owner to apply after merge. API (PR 2, SCRUM-134): `GET` / `POST /api/v1/events/{id}/tech-staff` and `DELETE /api/v1/events/{id}/tech-staff/{staff_user_id}` for the event's coordinator: whether it's eligible (D80), who's assigned, who's available (not on an overlapping event, D81) and the log, newest first; assigning is all or none, each staff member's row locked so nobody is on two overlapping events, and each is notified with the event, its venue and the technical requirements (`Notifier.tech_staff_assigned`, D82); nothing changes once the event has started; deviation 56 | **Real screen, wired to API** (PR 3, SCRUM-135): **Technical support** on the coordinator's Equipment screen, under the picked event's equipment (D83). Until the event has an approved equipment request it says "Needs an approved equipment request first"; then the coordinator ticks available staff and presses Assign, or Unassigns someone, and the log underneath lists every assign and unassign with who and when. The API's refusals (someone just booked elsewhere, the event already started) show on the section, which then reloads | TC-US14-01 to 03 and 05 to 17 pass; 17 is E2E (`docs/testing/US14-tech-support-staff.md`) |
| SCRUM-18 — multi-session agenda (US15) | Schema (PR 1, SCRUM-138): `event_sessions`, one row per agenda item (title, type, speaker, times), with named CHECKs (the speaker is required unless it's a break, D96) and an exclusion constraint so one event's sessions never overlap (one track, D95); a seeded **Agenda Demo** in `planning`, owned by the seeded organiser, whose sessions a reseed clears. Migration `20261111_1200_us15_sessions`, for the Supabase owner to apply after merge. API (PR 2, SCRUM-139): `GET` / `POST /api/v1/event-requests/{id}/sessions`, `PATCH` / `DELETE /api/v1/event-sessions/{id}`; the request's own Organiser changes the agenda while it's `draft` or `planning` (D93), within the event's window (D94), one track (D95), and anyone who can read the request lists it, in chronological order (D97) | Done (PR 3, SCRUM-140): an **Agenda** section on the organiser's request (D97): below a saved draft's details, on the clarification view and on the confirmation view. Sessions in chronological order, each with its date, times, title, type and speaker; **Add session**, **Edit** and **Delete** while the request is `draft` or `planning`, read-only otherwise (D93). The API's field errors show on their fields, an overlap names the clashing session, and a session the event's times have moved away from is marked "Outside the event's times" (`outside_window`, D94). Not on the coordinator's or Lead's review screens (D97 names the organiser's) | TC-US15-01 to 15 pass (`docs/testing/US15-event-agenda.md`) |
| SCRUM-82 — role-based access (US16b) | Planned 25 Oct, **all three subtasks in Sprint 4; none landed in Sprint 3**; decisions D45 to D51. **SCRUM-119 done:** `users.roles` (a list, at least one, no repeats) replaces `users.role` (migration `20261027_1200_us16b_roles`); `venue_staff` replaces `operations_manager` (D49) and `safety_officer` is added; every role check reads every held role (D46); `/me` and sign-up return `roles` and, until SCRUM-121, `role`; the seed adds `safety.officer@smu.edu.sg` and `multi.role@smu.edu.sg` (D50) and gives every seeded user a full name. **SCRUM-120 done:** a coordinator's review queue, request details, thread and clarifications cover only the requests assigned to them now (D48); Venue Staff read no event requests, and attendees and Venue Staff get `403` on a request's details and thread; no one decides a record they created (D51: `403 SELF_DECISION_NOT_ALLOWED` on bookings, equipment lines and assignment, `422 INVALID_COORDINATOR` `created_the_request`, CHECKs in migration `20261031_1200_us16b_d51_checks`; one check, `refuse_self_decision`, shared with SCRUM-84's request decisions); the Lead reassigns a deactivated coordinator's request (TC-US16B-31, with SCRUM-83's reassignment, which also follows D51) | **SCRUM-121 done:** a user holding more than one role gets a **Role** switcher in the header; navigation and the home screen follow the current role, which is remembered per user across a refresh (deviation 49). The frontend reads `roles` from `/me`, which no longer sends `role`. A Safety officer gets "no screens yet" with Log out; **Acting as** gains Safety officer. A request the user made, or for an event they coordinate, shows `SELF_DECISION_NOT_ALLOWED` on its row in Venue staff's pending list and Tech support's queue. SCRUM-120 changed no screen (the clarification E2E gained a Lead-assign step) | TC-US16B-01 to 32 in Jira and `docs/testing/US16b-role-based-access.md`; 01 to 32 all pass (SCRUM-119 to 121) |
| SCRUM-96 — view registrations for my events (US28) | Done: `GET /api/v1/me/managed-events`, `GET /api/v1/events/{id}/registrations` (totals, registrants, answers, status filter, Show all; D52: the creating Organiser and the **assigned** Coordinator). The seeded organiser owns the seeded events, so they also list under its Event requests as `confirmed`; the seeded coordinator is assigned Intro to Supabase: Live Coding | **Real screen, wired to API**: **Registrations** in the header for Organiser and Coordinator | TC-US28-01 to 17 (15 pytest + 2 E2E) + frontend integration; see `docs/testing/US28-view-registrations.md` |
| SCRUM-15 — edit event details during planning (US12) | Done: `event_change_requests` and `event_audit_entries` (migration `20261108_1200_us12_event_edits`, for the Supabase owner to apply after merge); `GET /api/v1/me/coordinated-events`, `GET` and `PATCH /api/v1/events/{id}`, `GET /api/v1/events/{id}/history`, for the event's assigned coordinator only (D48). Non-critical fields save at once; a critical one (D87) holds the whole edit (D88) in a Pending Approval change request; every successful save is logged per field, a critical one tied to its request (D89). **No one approves change requests yet** (D89). Seeds **Event Planning Demo** (planning, the seeded coordinator's, 10:00 to 12:00 SGT 21 days ahead whatever the seed's clock time, so TC-US12-23's end before the start is the same on every run); a reseed resets it | **Real screen, wired to API**: **Events** in the coordinator's header (deviation 58): their events from planning on, Edit enabled only in Planning, the edit form with errors on their fields, changes awaiting approval, and History newest first | TC-US12-01 to 26 (40 pytest + 6 frontend + 4 E2E); see `docs/testing/US12-edit-event.md`, with a screenshot per AC |
| SCRUM-97 — request a change to a submitted event (US29a) | Done: `event_change_requests.reason` (migration `20261110_1200_us29a_change_reqs`, for the Supabase owner to apply after merge) on US12's table; `POST /api/v1/event-requests/{id}/change-requests` for the event's own Organiser from Submitted on, not Rejected, Cancelled or Completed; fields by stage (D90); a reason required; the event keeps its values and the request is `pending_approval`; `GET /api/v1/me/change-requests`; `Notifier.change_requested` to the assigned coordinator, or every active Lead while unassigned (D91, log-only). **No one reviews them yet**: US29b | **Real screens, wired to API**: **Change requests** on the organiser's submitted request (deviation 61): Request a change, a review step with each field's current and proposed value and the reason, and the event's requests with their status | TC-US29A-01 to 24 (`docs/testing/US29a-change-request.md`, with evidence per AC) |
| SCRUM-12 — cancel an event (US9) | Schema (PR 1): `event_cancellations`, one row per organiser request (pending, then approved or rejected by the assigned coordinator) or direct coordinator cancel (approved), with who asked, why and when and who decided and when (AC 8); one pending or approved row per event; a rejection needs a reason. A `cancelled` event needs only its name of the final fields (D98); the coordinator's Events list and the managed-events list leave out one cancelled before it had a date. Migration `20261112_1200_us9_cancellations`, for the Supabase owner to apply after merge. API (PR 2): the organiser asks with a reason, the assigned coordinator approves or rejects (a reason required) or cancels directly (D48, D51); cancelling is refused before approval, once over or once the event has started (D101); the assigned coordinator keeps a cancelled event in their review queue and can open it (widens D11); the event's pending change requests are rejected and its pending equipment lines leave Tech support's queue and can't be reviewed; a request with no active coordinator goes to the Leads; Leads read the record; cancelling withdraws every live venue booking and deletes the equipment reservations in one transaction (locking bookings before the event, as approve does; reserve now waits on the event), and tells the organiser, Venue staff when an approved venue is released (D100), assigned active Tech support staff and every registered, offered and wait-listed attendee; a cancelled event offers no freed place and refuses an earlier offer (`EVENT_CANCELLED`); deviation 65. **Not built:** releasing holds (US25) | **Real screens, wired to API** (PR 3): a **Cancellation** panel on the organiser's opened request from Approved on (**Request cancellation** with a reason, then "Waiting for decision") and on the coordinator's review screen for their assigned event (**Approve cancellation** / **Reject cancellation** with a reason when a request waits; otherwise **Cancel event**, a reason, then a confirm step saying it can't be undone); both show the record (who asked, why, when, who decided) and "This event is cancelled." (deviation 67). Seeds **Cancellation Demo** (planning, the seeded coordinator's); a reseed puts it back, and drops the approved cancellation of any seeded event it un-cancels; the panel offers nothing if the history can't be loaded | TC-US9-01 to 35 pass (`docs/testing/US9-cancel-event.md`) |
| SCRUM-98 — review an event change request (US29b) | Schema (PR 1, SCRUM-141): each `event_change_requests` row records its decision (`decided_at`, `decided_by_user_id`, `rejection_reason`, with named CHECKs: a decision is whole, only a rejection has a reason, and no one decides a request they made, D51); `event_audit_entries.action` says what each History entry is (`saved`, `requested`, `applied`, `decided`, `status_changed`, `confirmation_cleared`, `safety_approval_cleared`; existing entries tied to a request backfilled as `requested`); `event_review_flags`, one row per arrangement an approved significant change may have overtaken (a live venue booking, an equipment line that holds a reservation, or the event's registrations as one flag), one open flag per item, cleared by the coordinator with an optional note, nothing on the item changed (D104). Seeds **Change Request Demo** (confirmed, safety-approved with an approved review by the seeded Safety officer, an approved booking, a reserved projector, Terry Ong assigned, and the seeded organiser's pending request to start an hour later); a reseed puts it back. Migration `20261115_1200_us29b_decisions`, for the Supabase owner to apply after merge. D102 to D107 were decided on 3 Nov. API (PR 2, SCRUM-142): the coordinator's, and for a coordinator's own US12 edit a Lead's, list of change requests with each field's current and proposed value, approve and reject (D102); a significant approval on an Approved, Planning or Confirmed event flags its live bookings, reservations and registrations, moves Confirmed back to Planning and clears the safety approval (D103 to D106); a request the event has outgrown is refused as stale (D107); the coordinator lists and clears flags, and open ones hold back confirming and the safety review; the requester (and the organiser for an approved US12 edit) is told after the commit (deviation 68) | **Real screens, wired to API** (PR 3, SCRUM-143): **Change requests to review** on the coordinator's Event requests screen; on the event's review screen a **Change requests** panel with each field's current and proposed value, the reason and, for a significant one, what approving does, then **Approve** (with a confirm step) or **Reject** with a required reason; refusals (stale, already decided, not allowed) say why; **Review after change** under the readiness list with **Mark reviewed** and an optional note, resolved flags shown as resolved, Confirm disabled while one is open; "A new safety review is needed" on the safety outcome; the Safety officer told an event with open flags can't be reviewed yet; the organiser's change requests show Approved or Rejected, the date and why; History reads each new action (deviation 71). the change-request list sends the acting role as `acting_as` (Calvin's #127 review). **Lead screen** (SCRUM-144): **Coordinator edits to approve** on the Lead's Event requests screen, opening the same panel for a coordinator's own US12 edit (D102), listed with `acting_as=coordinator_lead` | TC-US29B-01 to 42 pass (`docs/testing/US29b-change-request-review.md`) |
| SCRUM-93 — tentative venue holds (US25) | Schema (PR 1, #123): `held` and `expired` booking statuses, the hold columns, the overlap guard covering holds (`BLOCKING_STATUSES`), and the availability check, US2's search and the buffer-edit recompute with it; a hold never the primary venue (D111); migration `20261115_1200_us25_holds`, for the Supabase owner to apply after merge. API (PR 2): Venue staff place a hold up to 14 days ahead (D108) for an Approved or Planning event they pick from `GET /venue-holds/events` (D112); the coordinator confirms it into a request, which Venue staff must approve before its expiry (AC 5), or declines it (withdraw, D110); holds lapse on read with a warning in their last 24 hours (D109); the calendar shows them; cancelling an event releases them (US9); `Notifier.venue_held`; deviation 70. Seeds **Venue Hold Demo** (Approved, the seeded coordinator's), whose bookings and holds a reseed clears | **Real screens, wired to API** (PR 2): **Hold a venue** on Venues for Venue staff (pick the event, then the request form with an expiry date and time); on the coordinator's event, a held venue shows until when it's held and how long is left, with **Confirm hold** and **Decline hold** (which asks first, as Withdraw does), and a confirmed one the time Venue staff must approve it by; the calendar draws holds (dotted) with "Held until" in their details | TC-US25-01 to 24 pass (`docs/testing/US25-venue-holds.md`) |
| SCRUM-90 — mark a venue unavailable and flag affected bookings (US23a) | Schema (PR 1): each `venue_blocks` row has a `reason` (maintenance, equipment failure, renovation, safety, other; blocks made before US23a read `other`, the seeded one `maintenance`) and `created_by_user_id`; a booking or hold a block overlaps is marked "Needs rearrangement" by `venue_bookings.rearrangement_block_id` and `rearrangement_flagged_at`, keeping its status (D113); migration `20261116_1200_us23a_blocks`, for the Supabase owner to apply after merge. API (PR 2): `POST /api/v1/venues/{id}/blocks` for Venue staff records a period with a reason (AC 1, 2), marks every booking and hold whose occupied window it overlaps (D113), and tells each affected event's coordinator and organiser once (`Notifier.venue_unavailable`, D114); a marked booking reads `unavailability.kind: "venue_unavailable"` with the period, its next action is the coordinator's, it doesn't count as arranged, and a marked hold can't be confirmed; requests and approvals in the period are refused as before (AC 5); calendar blocks carry their reason (AC 6); deviation 73. Seeds **Venue Unavailability Demo** (Approved, the seeded coordinator's), whose bookings and the periods that marked only them a reseed deletes | **Real screens, wired to API** (PR 2): **Mark a venue unavailable** on Venues for Venue staff (venue, start, end, reason, optional note; an end before the start is refused on the end date before sending), then which bookings now need rearrangement; on the coordinator's event a **Needs rearrangement** badge with the period, reason and note, Withdraw still offered and a marked hold's Confirm hidden; the Organiser reads the same with "The coordinator will arrange a replacement"; the calendar's block details show the reason | TC-US23A-01 to 20 pass (`docs/testing/US23a-venue-unavailability.md`) |
| SCRUM-91 — find a replacement venue for an affected booking (US23b) | Schema (PR 1): booking status `replaced` with `replaced_at` (D117; a replaced booking no longer holds its window); a replacement request names the booking it replaces (`replaces_booking_id`, at most one live replacement each); the coordinator's restore request on a marked booking (`restore_requested_at`, `restore_requested_by_user_id`, D118), and Venue staff's last decline of one (`restore_declined_at`, `restore_declined_by_user_id`, `restore_decline_reason`); a venue block can be ended early (`ended_early_at`, `ended_early_by_user_id`, `scheduled_ends_at`; ended before it began, it is left empty and overlaps nothing). Migration `20261117_1200_us23b_replacement`, for the Supabase owner to apply after merge. API (PR 2): marking a venue unavailable moves an affected Confirmed or Preparation event back to Planning, clearing its confirmation, with History entries (AC 1); `POST /venue-bookings` takes `replaces_booking_id` (AC 3); approving the replacement makes the original `replaced` and moves the primary across, and attendees hear only if the primary venue or its times changed (AC 4, 7, D117); `POST /venues/{id}/blocks/{block_id}/end`, `POST /venue-bookings/{id}/restore`, `GET /venue-bookings/restore-requests` and `POST /venue-bookings/{id}/restore/confirm` and `/decline` (AC 5, D118) | **Find a replacement** on a booking that needs rearrangement opens the request form prefilled from it and lists only the venues the search finds free then (AC 2), **Search again**; Replaced, Replaces and the replacement's status on the rows; **Ask to restore** once the period ended early; Venue staff's **Requests to restore a booking** on Venues and **End early** in the calendar's block details | TC-US23B-01 to 20 pass (`docs/testing/US23b-replacement-venue.md`) |
| SCRUM-145 — cleanup: E2E flake, header overflow, dev-mode 403, setup | No change | Fixes, no new feature: every spec that waits for **Requests to review** matches it exactly through `reviewQueueHeading()` in `e2e/tests/helpers.ts`, so a parallel test's **Change requests to review (N)** no longer matches it; above 640px the header wraps its links onto a second row instead of widening the page (dev mode's eight links plus Acting as made it ~1767px wide at 1280px), the 390px phone layout unchanged; **Event requests** shows "Event requests aren't part of the X role" for every role without that screen (Venue staff, Tech support, Safety officer, Attendee), where the Safety officer used to fall through to the organiser's screen and its `403`; `frontend/.env.example` leaves `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` blank (a placeholder URL crashes the app on load); the root README adds `alembic upgrade head`, `python -m app.seed` and the frontend's `cp .env.example .env`; sibling panels keyed by the event id now use distinct keys | 3 frontend (Safety officer on Event requests, no request sent; an approved request's Agenda and Cancellation panels without a duplicate-key warning; `supabase.test.ts`: blank Supabase values give a null client without throwing) + 3 E2E (`health.spec.ts`: no sideways scroll at 800px, 1280px and 1440px) |
| SCRUM-146 — ask the Lead for a transfer (US10e AC 6) | No change: SCRUM-83's `POST /api/v1/event-requests/{id}/transfer-request` (`202`, every active Lead told, nothing moves) | **Real screens, wired to API**: **Request a transfer** (`TransferRequest.tsx`) for the event's assigned coordinator only, while it's Under review, Awaiting clarification, Approved, Planning, Confirmed or Preparation (the statuses a Lead can reassign in): on their review screen in Event requests, and on an event opened from their **Events** screen. A required reason (up to 1,000 characters), **Send** (disabled while sending) and **Cancel**; then "Transfer requested. The Coordinator Leads have been told." A blank reason is marked on the field (before sending, or the API's `422`), a `409 REASSIGNMENT_NOT_ALLOWED` names the event's status. The Lead reads the request in Notifications (US31) and reassigns from the request view as before; nothing records the request beyond that notice (deviation 48) | TC-US10E-29 to 33 (frontend) and 34 (E2E) pass |
 
Every endpoint in §3 exists, plus `POST /registrations/{id}/decline` (deviation 3 below) and `POST /registrations/{id}/accept` (deviation 13). Identity is a Supabase access token (`Authorization: Bearer`, SCRUM-102), plus two dev stubs when `AUTH_DEV_HEADERS=true`: `X-Attendee-Id` for the Sprint 1 routes and `X-User-Id` (role-aware) for the event-request, venue and equipment routes. The frontend logs in with Supabase (SCRUM-105) and shows each role only its own screens (attendees: the events board and My events; organiser, coordinator, Lead: Event requests and Venues, and the coordinator Equipment too; venue staff: Venues; Tech support: Equipment); a user holding several roles sees one role's screens at a time and switches with **Role** (SCRUM-121); with `VITE_DEV_AUTH=true` it skips login, sends the stubs and shows every screen. The database is the tables in §2 plus `attendees` and `users`. Backend suite: 1873 tests; frontend suite (Vitest): 552 tests; E2E: 71 tests (no sideways scroll at 800px, 1280px and 1440px, SCRUM-145; US10e transfer request: the coordinator asks to transfer Event Planning Demo and the Lead finds the notice, SCRUM-146; US16a and US16b login: 10, the six logged-in ones skip without `E2E_SEED_PASSWORD`, one of them `multi.role` switching to Venue staff; US16a sign-up: 3, skip without `SUPABASE_URL` and `SUPABASE_SECRET_KEY`; US10a journey: organiser submits, Lead assigns, reads the history entry, finds it on the Assigned tab, filters and opens it, organiser sees the coordinator; health check, US1 journey, US8 clarification journey: the coordinator doesn't see the new request until a Lead assigns it, then ask, answer, read the thread, attendee journey: list, register, My events, withdraw; waitlist journey: leave, rejoin, see position; offer journey: freed place offered, accepted; US20 venue list and search; US20 venue staff journey: add with a field error, edit, deactivate; US1 draft round-trip: save, reload, reopen, edit, submit; events board: only open events listed, Open/Full tabs, search by title and venue, online event's join link; Acting as switch remembered across a reload; US2 venue search: seeded slot drops booked and blocked venues, filters and hours, no-match criteria and a marked bad time, organisers not offered search; US22 venue booking: request then Venue staff's pending list, capacity error and layout warning, withdraw; US4 booking decision: approve, and reject with a reason and an alternative; US26 equipment: a coordinator adds a line, fixes the quantity, edits it and removes another, and Tech support approves one with a note that the coordinator then sees; US13 buffers: the form previews the occupied window, a window past closing is refused on the end time, setup inside a seeded booking's turnaround is refused with the overlap and the touching time is accepted, with Venue staff seeing its reference, occupied window and no conflicts; US28 registrations: the organiser's totals and registrants for the seeded online event, status filter and Show all; US17 decisions: the assigned coordinator approves, or rejects with a reason, and the organiser sees the outcome; US21 venue calendar: Venue staff see the seeded booking and block, labelled, and the booking's reference, a coordinator the same booking without it; US24 venues: the coordinator adds a breakout room to the multi-venue demo, sees it pending and the venues not arranged, and withdraws it, and the Organiser reads the event's venues with their status, unavailability and next action; US27 equipment reservations: Tech support reserves an approved line, the coordinator sees it Reserved, then Tech support releases it; US14 Tech support staff: once Tech support approves the demo event's line, the coordinator assigns Terry Ong, then unassigns him, and the log shows both; US12 event edits: Edit is enabled for the planning event and a confirmed one isn't listed as editable, a non-critical change saves at once and the event stays in planning, a critical change waits for approval and the event keeps its capacity, and an end before the start is refused on the end time, with History listing saves newest first; US29b change requests: the organiser asks Change Request Demo for more attendees and a second projector, the coordinator approves it from Change requests to review and sees the event back in Planning, its booking and projector flagged and a new safety review needed, the seeded request still pending, and the organiser sees it Approved (reseed before a rerun); US25 holds: Venue staff hold a venue for Venue Hold Demo, the coordinator confirms it, then withdraws it; US23a unavailability: the coordinator requests a venue for Venue Unavailability Demo, Venue staff mark it unavailable over the request for maintenance and see it listed, the coordinator sees it needs rearrangement with the reason and note, then withdraws it; US23b replacement: the coordinator requests a venue for Replacement Venue Demo and Venue staff approve it, then mark it unavailable, the coordinator finds a replacement from the notice with the booking's time and attendance, Venue staff approve it, and the original reads Replaced, then the replacement is withdrawn). **Supabase may lag `main`.** The Supabase owner applies each merged migration there right after the merge: Calvin, with Matthew covering when Calvin is away. The routine: check `alembic current` against Supabase versus `alembic heads` in the repo; run `alembic upgrade head` (never one named revision); reseed with `--yes` if the merge changed the seed (it empties Equipment Request Demo's equipment lines and deletes Multi-Venue Conference Demo's app-made bookings and Agenda Demo's sessions, and puts Change Request Demo back, deleting its change requests' decisions, history and review flags, and deletes Venue Hold Demo's bookings and Venue Unavailability Demo's and Replacement Venue Demo's bookings with the periods that marked only them, and says so first); then open Supabase's Security Advisor and fix anything new it flags. The Data API stays off (§1a Environment). If a migration fails on permissions for an extension, enable it under Database → Extensions and rerun. Log: **25 Oct**, at `20261026_1200_us10d_history` (`main`'s head then): seven migrations applied, reseeded, all 10 seeded logins linked; the Data API was found on and turned off (SCRUM-117). **25 Oct**, after #87 (SCRUM-119): `20261027_1200_us16b_roles` applied and reseeded; the venue staff user became `venue_staff`, and all 12 seeded logins (now with the Safety officer and `multi.role`) are named and linked.
 
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
cp .env.example .env                   # REQUIRED: VITE_DEV_USER_ID (organiser), VITE_DEV_COORDINATOR_ID, VITE_DEV_LEAD_ID, VITE_DEV_VENUE_STAFF_ID, VITE_DEV_TECH_SUPPORT_ID, VITE_DEV_SAFETY_OFFICER_ID, VITE_DEV_ATTENDEE_ID (Calvin), VITE_DEV_AUTH=true
                                       # (backend/tests/test_dev_ids.py checks the ids match the seeded users);
                                       # plus VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY for the login page (blank in dev mode:
                                       # a placeholder URL crashes the app on load)
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
- **A screen says "The request could not be completed. Check the backend connection and try again." but `curl localhost:8000/api/events/health` works** → usually a `500` from an unapplied migration (the browser reports it as a network failure because the error response carries no CORS header). Run `alembic upgrade head` in `backend/` and read the uvicorn terminal for the traceback. After SCRUM-83 this shows up as every assign, history and Assigned-tab call failing until `20261030_1200_us10e_reassign` is applied.
- **`alembic` says `Can't locate revision identified by '20261027_1200_us10e_reassign'`** → your local database ran SCRUM-83's migration while it was still chained straight after `20261026_1200_us10d_history`, so it never ran `20261027_1200_us16b_roles` or `20261029_1200_us17_decisions` (which now come first), and the file was renamed to `20261030_1200_us10e_reassign`. **Don't re-stamp it** with `UPDATE alembic_version`: that makes Alembic believe those two ran, and the app then fails with `column users.roles does not exist` (the screens only say "The request could not be completed"). Rebuild the local database instead: `pg_dump` it if you want a copy, then in `psql` run `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, and in `backend/` run `alembic upgrade head` and `python -m app.seed`. A database that was already past `us17_decisions` when it ran SCRUM-83 can be re-stamped safely; check that `\d users` has a `roles` column first. A fresh database needs nothing.
- **The notice lines (`coordinator assigned`, `event reassigned`, `transfer requested`…) never appear in the uvicorn terminal** → the app configures no logging, so INFO is hidden. Start uvicorn with a `--log-config` JSON that routes the root and `app` loggers to the console at INFO (§1a Next steps lists making this visible by default).
- **Reassigning needs a second coordinator, and the seed has only Casey Tan** → add one to your local database, for example `insert into users (email, full_name, role, is_active) values ('dana.lim@smu.edu.sg', 'Dana Lim', 'coordinator', true);`. The Lead's picker then offers her. Seeded events have no assignment history (D44), so only an event the Lead assigns in the app appears on the Assigned tab; the API reassigns any assigned event regardless.
- **Sign-up says "Check your email" but nothing arrives** → look in Spam and the Promotions tab first. Then Supabase → Logs → Auth for an SMTP error (`535` is a wrong Gmail app password), and Authentication → Rate Limits for the hourly email limit.
- **The confirmation link opens a page that can't be reached** → Supabase's Site URL isn't the app, or the app isn't running. It should be `http://localhost:5173` with `http://localhost:5173/**` and `http://localhost:5174/**` as redirect URLs (§9 Dashboard), and `npm run dev` must be running.
- **Event requests says "Set VITE_DEV_USER_ID…"** → `frontend/.env` doesn't exist (only `.env.example` does). Copy it and restart `npm run dev`.
- **The app shows a Log in page locally** → `frontend/.env` predates SCRUM-105, so `VITE_DEV_AUTH` is missing and login is required. Add `VITE_DEV_AUTH=true` for dev mode (Acting as), or log in with a seeded account. Restart `npm run dev`.
- **The login page says "Login isn't set up"** → add `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` (Project Settings → API Keys, `sb_publishable_…`) to `frontend/.env` and restart `npm run dev`.
- **The review queue says "Set VITE_DEV_COORDINATOR_ID…"** → your `frontend/.env` predates SCRUM-57. Copy that line from `.env.example` and restart `npm run dev`.
- **Equipment, acting as Tech support, says "Set the dev user id…"** → your `frontend/.env` predates SCRUM-110. Copy `VITE_DEV_TECH_SUPPORT_ID` from `.env.example` (the seeded Tech Support user); Vite restarts itself when `.env` changes.
- **Acting as Safety officer gets `401`s, or Safety reviews says "Set VITE_DEV_SAFETY_OFFICER_ID"** → your `frontend/.env` predates SCRUM-121. Copy `VITE_DEV_SAFETY_OFFICER_ID` from `.env.example` (the seeded Safety officer, SCRUM-119) and restart the frontend. The E2E for US30a needs it too.
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
- **A user holds one or more roles (US16b, SCRUM-119).** `users.roles` is a list; check it with `user.holds(UserRole.X, ...)` in Python and `User.roles.any(UserRole.X)` in a query, never by comparing a single role, so a two-role user passes every check either role allows (D46). `require_user_roles` already does this. The roles are `organiser`, `coordinator`, `coordinator_lead`, `attendee`, `tech_support`, `venue_staff` and `safety_officer`; `UserRole` lists them in the database type's order, which is the order `/me` returns them in. `operations_manager` is retired (D49): it stays in the database type because Postgres can't drop a value, but `UserRole` doesn't have it, so the app can't give it out. A test user with two roles is `make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)`.
- **Another person's record is `404 NOT_FOUND`, never `403`.** Applies to drafts as well as registrations (TC-US7-02, TC-US1-13).
- **Schema changes go in the first PR of a story, alone.** US1 split into schema → API → screens PRs; the API and screen PRs added no migration. Keeps one Alembic head and a reviewable migration.
- **E2E heading locators use `exact: true` when another screen's heading can contain the same words** (SCRUM-145): `getByRole("heading", { name: "Requests to review" })` also matches **Change requests to review (N)** once a parallel test leaves a change request. For the review queue, use `reviewQueueHeading()` from `e2e/tests/helpers.ts`.
- E2E steps must not depend on the seed's clock time, and must not assert a time string against History, whose When column shows the save's own timestamp; check by field name instead.
- **E2E specs share one seeded database and run in parallel.** `attendee-registration.spec.ts` is the only spec that changes seeded registrations (serial within itself); others either only read seeded rows that it never touches (`events-board.spec.ts`, `venue-search.spec.ts`, `event-registrations.spec.ts`, which reads Intro to Supabase: Live Coding) or create their own uniquely named rows (`event-request*.spec.ts`, `clarification-request.spec.ts`, `venue-catalogue.spec.ts`, `venue-booking*.spec.ts`). A spec may also change a seeded row that only it uses and the seed resets, as `equipment.spec.ts` (Equipment Request Demo) and `event-edit.spec.ts` (Event Planning Demo, serial within itself) do. `change-request.spec.ts` creates its own uniquely named request. `event-cancellation.spec.ts` cancels the seeded Cancellation Demo, which only it uses and the seed puts back in Planning (reseed before a local rerun). Keep a new spec in one of those two kinds, or it will flake against the attendee journeys. `venue-hold.spec.ts` holds a venue for the seeded Venue Hold Demo, which only it uses, on a day 400 to 700 days ahead, then withdraws it; the seed clears the event's bookings. `venue-unavailability.spec.ts` requests a venue for the seeded Venue Unavailability Demo, which only it uses, on a day 800 to 1100 days ahead, marks it unavailable and withdraws it; the seed deletes the event's bookings and the periods that marked only them. `transfer-request.spec.ts` (SCRUM-146) asks to transfer Event Planning Demo, which changes nothing on it, and finds the Lead's notice by a reason unique to the run, so it can share the event with `event-edit.spec.ts`.
- **Lapse on read (D2, SCRUM-137). `venue-replacement.spec.ts` does the same for the seeded Replacement Venue Demo, which only it uses, on a day 1100 to 1400 days ahead, replaces the venue and withdraws the replacement; the seed clears it the same way.** Nothing time-limited waits for a scheduler: it lapses when it's next read or changed. Each kind has one helper, which every read and change of that kind calls before its own work; for waitlist offers it's `registration_service.expire_lapsed_offers(db, event_ids, now, notifier)`. The helper does a cheap check without a lock (usually nothing has lapsed, so no lock and no write), then takes each parent row it found **in id order, in its own transaction**: lock it, re-check under the lock (another request may have got there first), apply the change, commit. One lock at a time in a fixed order, so concurrent reads can't deadlock; committing before the caller's work, so a refusal that follows can't roll the change back. A lapsed offer's place goes to the next person only while the event hasn't started. US25 (SCRUM-93) tentative holds should copy this. Tests: TC-US7-16 to 24, with a real two-session race in TC-US7-19.
- **Known lock-order inversion: event → bookings versus booking → event.** US18 confirm (`confirmation_service.confirm`) and US29b's change decision (SCRUM-142) lock the event `FOR UPDATE` and then its bookings; US4's booking approve (`booking_service.approve`) locks the booking and then its event `FOR SHARE`. If a confirm or change decision meets a Venue staff approval on the same event at the same moment, Postgres detects the deadlock and aborts one of them (a `500` for that caller, who can try again); nothing is half-written. Left as it is deliberately (no retry, decided 1 Nov for SCRUM-141): it needs two people acting on one event within milliseconds. If it shows up, make booking approve lock the event first.
- **E2E runs against a migrated, seeded database.** `e2e.yml` runs `alembic upgrade head` and `python -m app.seed` before starting the backend. A new E2E test needing data should get it from the seed, not by assuming an empty database.
 
### Deviations awaiting a decision
 
Each is implemented and defensible; each departs from the contract in §2/§3 and needs the team to either bless it or change the code.
 
| # | Deviation | Where |
|---|---|---|
| 1 | `attendees` table isn't in §2 at all. §2 references `attendees(id)` without defining it, so SCRUM-24 added the minimal version (`id`, `email`, `created_at`) | `app/user/models.py` |
| 2 | Withdrawing an `offered` registration returns `409 REGISTRATION_NOT_ACTIVE`, a code not in §3's table. Releasing an offer is a decline, not a withdrawal | `app/registration/service.py` |
| 3 | `POST /registrations/{id}/decline` isn't in §3's endpoint list. TC-US7-11 needs declining to be distinct from letting the window lapse | `app/registration/router.py` |
| 4 | `expire-offer` doesn't check that `offer_expires_at` has passed, and isn't restricted to the offer holder. Since SCRUM-137 it's a test helper only: offers expire on read (D2) | `app/registration/service.py` |
| 5 | Offer-release responses say *whether* the seat was passed on, never to whom, because TC-X-04 forbids revealing another attendee | `app/registration/schemas.py` |
| 6 | **Resolved by SCRUM-136.** `POST /events/{id}/waitlist` used to need no identity and take a body-only `{"email": ...}`, against §3's "every endpoint depends on it". It now depends on `get_current_attendee` like `register` and takes no body (D3, D7) | `app/registration/router.py` |
| 7 | Event requests live on the `events` table (nullable fields + a status-based CHECK), not a separate `event_requests` table, so the whole lifecycle is one row | `app/event/models.py`, SCRUM-40 migration |
| 8 | `expected_attendees = 0` is rejected even when saving a draft (`422 INVALID_EVENT_REQUEST`), because the DB CHECK forbids it | `app/event/request_service.py` |
| 9 | New error code `INVALID_EVENT_REQUEST` (422, with `fields`) for present-but-invalid values — past/duplicate dates, start ≥ end, attendees < 1 — distinct from `MISSING_REQUIRED_FIELD` | `app/event/request_service.py` |
| 10 | The form auto-adds a date left in the date picker on Save/Submit; "Add date" is only needed for extra dates. Found in manual testing | `frontend/src/features/eventRequest/` |
| 11 | New error code `INVALID_CLARIFICATION` (422, `fields: ["sections"]` plus the unknown `sections`) for an unknown or repeated section; an empty section list or blank comment is `MISSING_REQUIRED_FIELD` | `app/event/clarification_service.py` |
| 12 | New error code `CLARIFICATION_NOT_ALLOWED` (409, with the request's current `status`) when a coordinator asks for clarification outside `submitted`/`under_review` | `app/event/clarification_service.py` |
| 13 | `POST /registrations/{id}/accept` (US6b) isn't in §3's original list, and adds `409 OFFER_EXPIRED` for an offer past `offer_expires_at`, or already expired — accepting it could overbook, since a lapsed offer no longer holds its seat. Since SCRUM-137 decline answers `409 OFFER_EXPIRED` for a lapsed offer too, rather than declining it; in both the place has already moved on (D2) | `app/registration/service.py` |
| 14 | New error code `NO_OPEN_CLARIFICATION` (409, with the request's current `status`) when the organiser answers outside `awaiting_clarification`, including a second answer to the same round | `app/event/clarification_service.py` |
| 15 | `GET /me/registrations` has a third section, `offered`, not in §3's original shape: live offers with `offer_expires_at`, so the attendee sees the place on screen (D5). It's additive; the notifier also now receives the `registration_id` to accept with. SCRUM-137 adds a fourth, `expired`: offers that lapsed on events still to come, with `offer_expires_at` (when the offer ended), unless the attendee has an active row on the event again | `app/registration/service.py`, `app/notification/service.py`, `app/equipment/service.py` (reserve reads the event FOR SHARE) |
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
| 28 | New error code `BOOKING_NOT_PENDING` (409, with the booking's current `status`) when withdrawing a booking that isn't `requested` (AC 5). Since US24 PR 2 (SCRUM-128) withdraw refuses with `BOOKING_NOT_LIVE` instead, as an approved booking can be withdrawn too (deviation 53); approve and reject keep `BOOKING_NOT_PENDING` (deviation 33) | `app/venue/booking_service.py` |
| 29 | `POST /api/v1/venue-bookings` returns `warnings` (`[{field, item, message}]`) for each required facility or accessibility feature the venue lacks, and for a layout it doesn't offer; the request still saves (AC 3). Warnings aren't stored. And `GET /api/v1/venues/{id}` now shows an **inactive** venue to the coordinator assigned to an event with a live (Requested or Approved) booking there (D20, since US10a), closing US20's gap; everyone else still gets `404`, and the venue still leaves their list | `app/venue/booking_service.py`, `app/venue/service.py` |
| 30 | `venue_blocks` (US2, SCRUM-7) is in no earlier §: AC 5's "blocked" venue has no event behind it, so it can't be a `venue_bookings` row (event and requester required). Minimal: `venue_id`, `starts_at`, `ends_at`, `note`. Blocks may overlap each other and bookings. US23a (SCRUM-90, CR-02) adds Venue Staff's screens for it. Numbered 30 because US22 PR 2 takes 24 to 29 | `app/venue/models.py`, migration `20261022_1200_us2_venue_blocks` |
| 31 | New error code `INVALID_VENUE_SEARCH` (422, with `fields` and `errors`) on `GET /api/v1/venues/available` for a past date, end not after start, attendance below 1 or not a whole number, or an unknown tag. `attendees` is read as text so `1.5` is this error on `attendees`, not FastAPI's generic 422. Missing criteria are `MISSING_REQUIRED_FIELD` | `app/venue/service.py` |
| 32 | US22's screens (SCRUM-113). **Where:** Request venue and the event's bookings appear on an **Approved** request opened from the coordinator's review queue, the only place a coordinator sees an Approved event; a **Planning** event can't be reached in the app, because D11 hides it from coordinators. **Still open after #68 (US10a):** AC 1 allows Planning events too, but US10a didn't widen D11, so a Planning event is still out of reach; once D11 covers it, the panel should show there too. **Who:** only the event's assigned coordinator may book it (D20, since US10a). The review queue still lists every Approved request to every coordinator, so on an **unassigned** one the panel says no coordinator is assigned yet, and on one assigned to someone else (the API answers `404`) it names that coordinator; neither shows Request venue. Venue staff see the pending list at the top of Venues. **How:** date and times are Singapore wall-clock, sent as ISO 8601 with `+08:00` (D9); the form starts from the request's first preferred date, times and attendance; before sending it lists what the chosen venue lacks of the required facilities, accessibility and layout but never blocks (AC 3), and after booking it shows the API's `warnings`. The layout field is labelled **Layout**, not Room layout, because the review screen already has a Room layout section checkbox. Withdraw asks first (PR #69 review), like the registration WithdrawDialog: the dialog says the window is released to any coordinator at once, and nothing is sent until **Withdraw request**; a refusal (e.g. `BOOKING_NOT_PENDING`) is explained in the dialog while the list reloads behind it. A withdrawn window can be requested again | `frontend/src/features/venue/EventVenueBookings.tsx`, `VenueBookingForm.tsx`, `PendingBookings.tsx` **Closed by SCRUM-85:** the assigned coordinator now opens a Planning event from their review queue (D11 widened), where Request venue shows (an approved or planning event) beside the readiness list |
| 33 | US4 (SCRUM-8) adds `POST /api/v1/venue-bookings/{id}/approve` and `/reject` (Venue Staff, D19), not in §3 before. `BOOKING_NOT_PENDING` (409) for a booking that isn't `requested`. On approve only: `VENUE_UNAVAILABLE` (409, with `conflict` and `message`) for a clash of the stored occupied window with another live booking or a block, or an inactive venue (D38, D39), plus `buffers: true` when the clash is only with the setup and turnaround, whose message reads "Too close to a booking (or a venue closure) … to fit the venue's setup and turnaround" rather than "already booked"; `VENUE_CAPACITY_EXCEEDED` (409, with `capacity`) when the venue's capacity was cut below the attendance after the request; `EVENT_NOT_BOOKABLE` (409) when the event has left Approved/Planning; and the **new code `BOOKING_EXPIRED`** (409, with `message`) once the request's start has passed, since pending requests don't expire until US25. Each refusal leaves the request pending, to be rejected (PR #73 review). Reject notes are at most 1,000 characters each. Approve takes no body fields and reject only `reason` and `alternative_suggestion`; anything else is FastAPI's `422`, which is how "no override" (AC 3) and "no partial approval" (AC 7) are enforced. Bookings gain `decided_at`, `decided_by_user_id`, `rejection_reason`, `alternative_suggestion` in every response | `app/venue/booking_service.py`, `app/venue/booking_router.py` |
| 34 | `tech_support` added to `user_role` by SCRUM-108 (US26) ahead of US16b (SCRUM-82), using the name §1a already planned, so Tech Support's routes check a real role instead of a stand-in (D19 already makes `operations_manager` mean two jobs). The seed adds `tech.support@smu.edu.sg`. Postgres can't drop an enum value, so the US26 downgrade leaves it | `migrations/versions/20261025_1200_us26_equipment.py`, `app/user/models.py` |
| 35 | US10d's screen (SCRUM-66). The Lead reaches an event's history with **History** on a row of the Assigned tab (US19, SCRUM-86) or **View assignment history** after assigning. Because the Assigned tab lists Planning and Confirmed events too (D44), the Lead's own events are no longer cut off at `rejected` as D11 does for the review queue | `frontend/src/features/eventRequest/AssignmentQueuePage.tsx` |
| 36 | New error code `INVALID_EQUIPMENT_LINE` (422, with `fields` and `errors`) when a line's type is missing or not in the catalogue, or its quantity is missing, not a whole number or below 1 (US26 AC 4, TC-US26-07). One code for missing and invalid, since a line has only two checked fields. The type and quantity are read unchecked, so `1.5` or `"two"` is this error on `quantity`, not FastAPI's generic 422 | `app/equipment/service.py` |
| 37 | New error code `LINE_NOT_PENDING` (409, with the line's current `status`) when a coordinator edits or removes, or Tech Support reviews, a line that is already approved or rejected (AC 2, 3) | `app/equipment/service.py` |
| 38 | New error code `EVENT_NOT_ELIGIBLE` (409, with the event's current `status`) when a line is added to an event that isn't `planning` or `confirmed` (SCRUM-109, TC-US26-10). A draft is `404`, as for venue bookings (D11). Only adding checks the event's status; editing and removing a pending line don't | `app/equipment/service.py` |
| 39 | New error code `DUPLICATE_EQUIPMENT_TYPE` (409, with `fields: ["equipment_type_id"]` and a `message`) when adding a line, or changing a line's type, would give the event a second pending or approved line of that type (D41, TC-US26-19). Checked first; two requests at the same moment are settled by `equipment_request_lines_one_live_per_type`, and the loser gets the same answer | `app/equipment/service.py` |
| 40 | US19's screens (SCRUM-86). **Tabs:** Unassigned (the existing queue, still first and shared by all Leads) and Assigned. **Read-only view** (AC 4): **View** on a row opens the request's fields from the list row, with no editing and no approve, reject or confirm action (those belong to other roles). On an unassigned request it offers **Assign a coordinator**; on an assigned one it offers **Assignment history**. **Reassign** (SCRUM-83) is offered on an active event that has a coordinator. **Supervisory scope** (AC 6): no separate column or table; a Lead's scope is the events they assigned, read from `coordinator_assignments` (D44), so any number of Leads works and none is hard-coded. A broader scope would need a decision | `frontend/src/features/eventRequest/AssignmentQueuePage.tsx`, `LeadRequestDetail.tsx` |
| 41 | New endpoint `GET /api/v1/me/equipment-events` (SCRUM-110, TC-US26-20): `{"events": [{id, name, start_at, status}]}`, the caller's own assigned events in `planning` or `confirmed`, using SCRUM-109's eligibility rule (`ELIGIBLE_STATUSES`): those not over yet first, soonest first, then ended ones, most recent first (PR #78 review). Ended ones stay listed because the API still takes lines for them (the rule is status only); only the order keeps last month's event off the top. Coordinator only. US26's screen needs it to pick an event, and no other route lists a coordinator's planning or confirmed events: D11 hides them from the event-request routes | `app/equipment/service.py`, `app/equipment/router.py` |
| 42 | US26's screens (SCRUM-110). **Where:** a new **Equipment** screen in the header: the coordinator's (after Event requests and Venues) and Tech support's only screen, so a logged-in Tech Support user no longer sees "no screens yet". In dev mode, **Acting as** gains Tech support (`VITE_DEV_TECH_SUPPORT_ID`); other roles opening Equipment, and Tech support opening Event requests, are told it isn't their role's. **Coordinator:** pick an event (deviation 41), see its lines with status and Tech support's note, add a line (type from the catalogue, quantity, notes), and edit or remove a pending one. The quantity and type are sent as typed, so the API's `INVALID_EQUIPMENT_LINE` and `DUPLICATE_EQUIPMENT_TYPE` show beside their field; the screen doesn't repeat the rules. Remove asks first, like Withdraw on a venue request (PR #69 review). **Tech support:** the pending queue, oldest first, each with its event, date, quantity and notes, a note box, and **Approve** / **Reject** (the note is optional, D43); a decided line leaves the queue, and a refused review (e.g. `LINE_NOT_PENDING`) is explained and the queue reloads. **Stale lines (PR #78 review):** approval is always the line's current quantity (AC 6) and the coordinator can edit a pending line after the queue loaded, so Approve and Reject first reload the queue; if the line changed (`updated_at`) or left it, nothing is sent and the screen shows it as it is now. A change in the moment between that check and the review isn't caught; closing it would need the review to carry the version it saw | `frontend/src/features/equipment/` |
| 43 | New error code `VENUE_OUTSIDE_HOURS` (422, with `fields` naming the end that breaches, `opens_at`, `closes_at`, the request's `occupied` window and a `message`) when a booking request's occupied window starts before the venue opens or ends after it closes, or crosses midnight (US13 AC 5, D32). Checked before overlaps. Approval (US4) refuses the same way with `409` instead, on the booking's stored occupied window: it has no body to be wrong, and like US4's capacity re-check it's the booking's state now that stands in the way | `app/venue/booking_service.py`, `app/venue/availability.py` |
| 44 | New error code `VENUE_BUFFERS_CONFLICT` (409, with `fields`, `bookings`: each clashing Requested booking's `reference`, times, recomputed `occupied` window and `reason`, and a `message`) when a venue's buffer edit would make its live future Requested bookings overlap or run outside hours (US13, D31). Nothing is saved | `app/venue/service.py` |
| 45 | `SELF_DECISION_NOT_ALLOWED` (403, the code deviation 47 also uses for event requests) when someone decides a record they're tied to (D51, SCRUM-120): approving or rejecting a venue booking they requested or whose event they now coordinate, reviewing an equipment line on the same terms, or a Lead assigning or reassigning (SCRUM-83) a request they created. Checked before whether the record is still pending, so the refusal doesn't depend on its state. Assigning a request to its creator adds a reason to the existing code instead: `422 INVALID_COORDINATOR`, `reason: created_the_request`, like the picker's other refusals. All four decision paths, SCRUM-84's included, call one check, `refuse_self_decision` (`app/event/self_decision.py`), and a test fails on any approve, reject, review or assignment route it doesn't try (PR #88 review) | `app/event/self_decision.py`, `app/venue/booking_service.py`, `app/equipment/service.py`, `app/event/assignment_service.py`, `app/event/decision_service.py` |
| 46 | Who reads event requests (US16b, SCRUM-120). The review queue (`GET /api/v1/event-requests`) is Coordinator and Lead only, and a request's details and clarification thread are Organiser, Coordinator and Lead only: Venue Staff, Tech support, the Safety officer and attendees get `403` (AC 3), where before any signed-in user reached the service and got `404`, and Venue Staff read everything (D11, D19's leftover). Venue Staff's access was dropped on 25 Oct (D55) because, through it, a Coordinator who is also Venue staff would see every request, defeating D48; their pending list already names each booking's event. TC-US16B-14's matrix lists every route with the roles allowed, and fails on a new route that isn't in it (PR #88 review) | `app/event/request_router.py` |
| 47 | New error codes for deciding an event request (SCRUM-84): `REQUEST_NOT_DECIDABLE` (409, with the request's `status`) outside Under Review (AC 1, 6); `SELF_DECISION_NOT_ALLOWED` (403) when the coordinator created the request (D51, the code #88 uses for bookings and equipment). Numbered 47 because #88 takes 45 and 46 | `app/event/decision_service.py` |
| 48 | US10e (SCRUM-83). **Transfer request (AC 6):** `POST /api/v1/event-requests/{id}/transfer-request` (`{"reason"}`, `202`) exists, but there is no table: it only tells every active Lead (`Notifier.transfer_requested`, kept as a notification since US31). Since SCRUM-146 the event's assigned coordinator asks with **Request a transfer** on their review screen and their Events screen; nothing records the request beyond the notice, so neither screen says one is already waiting. **New notifier method** `event_reassigned` rather than reusing `assignment_made` as US10c's note suggested, because the previous coordinator's notice must say who it moved from and why. **New error codes:** `REASSIGNMENT_NOT_ALLOWED` (409, with `status`) and `INVALID_COORDINATOR` gains `reason: "same_coordinator"` (422). **`reason`** is on `AssignmentRecordOut` (null for an assignment) | `app/event/assignment_service.py`, `app/event/request_router.py`, `app/notification/service.py` |
| 49 | US16b's screens (SCRUM-121). **Role switcher:** shown next to Log out only to a logged-in user with more than one role that has screens; it lists those roles, in `/me`'s order. Switching opens the new role's home screen. The choice is stored per user (`connectsphere.role` in `localStorage`, with the user's id), so a refresh keeps it, a role no longer held or another user's choice falls back to the first held role, and the API never hears of it (D46). **Roles without screens** (the Safety officer's) aren't offered, so nobody can switch into a dead end; a user with no role that has screens gets "Your account's role doesn't have any screens yet" and Log out. **Your own requests (D51):** Approve and Reject stay on every row of Venue staff's pending list and Tech support's queue; when the API answers `SELF_DECISION_NOT_ALLOWED`, the row says another Venue staff member (or Tech support user) must decide it and stays. Rejecting a booking from the dialog closes the dialog and shows the message on the row. **Test mock:** `frontend/src/test/server.ts` follows SCRUM-120: a coordinator sees only assigned requests, other roles without a reading role get `403` on request details and threads, and decisions refuse the requester and the event's coordinator. With D48, a coordinator never reaches another coordinator's approved event, so the venue panel's "Only <name>… can request a venue" message is no longer reachable from the app; it's left in place | `frontend/src/auth/currentRole.ts`, `frontend/src/App.tsx`, `frontend/src/components/SiteHeader.tsx`, `frontend/src/features/venue/PendingBookings.tsx`, `frontend/src/features/equipment/EquipmentQueue.tsx` |
| 50 | The venue calendar (US21, SCRUM-122) shows **Requested** bookings as well as approved ones, though AC 1 names only approved bookings: a pending request blocks the window too (D21), and the story's goal is knowing when a venue can be requested. Each says which (`booking.status`) so the screen marks it pending (D57) | `app/venue/calendar_service.py` |
| 51 | New endpoint `GET /api/v1/venues/{id}/calendar` (US21, SCRUM-122; §3) and new error code `INVALID_DATE_RANGE` (422, with `fields` naming `from` and/or `to`, and a `message`) for a missing or badly formatted date (not exactly `YYYY-MM-DD`: `20261012` and `2026-W42-1` are refused too), `to` before `from`, or more than 42 days. `from` and `to` are read as strings so a bad one names its field, as US2 search does for `attendees` | `app/venue/router.py`, `app/venue/calendar_service.py` |
| 52 | New endpoint `POST /api/v1/equipment-lines/{id}/availability-check` (US5, SCRUM-125; §3), Tech Support only: a request line's type and quantity against stock, out of service and other events' overlapping reservations, recorded on the line (D64). Every line read-back gains `availability_check`, and editing a line's quantity or type clears it. No new error codes | `app/equipment/router.py`, `app/equipment/service.py`, `app/equipment/schemas.py` |
| 53 | US24 (SCRUM-92) adds `venue_bookings.purpose`, `is_primary` and `preparation_status` and the partial unique index `venue_bookings_one_primary_per_event` (PR 1, SCRUM-127; §2); PR 2 adds `POST /api/v1/venue-bookings/{id}/make-primary`, an endpoint for Venue staff to set an approved booking's `preparation_status` (D73), lets `withdraw` take an Approved booking, opens `GET /api/v1/events/{id}/venue-bookings` to the Organiser and adds `venues_arranged`, `primary_booking_id`, `allocated_attendees`, `expected_attendees`, `next_action` and, per booking, `purpose`, `is_primary`, `preparation_status`, `unavailability` and `next_action` to it (D68, D69, D71, D72, D73). PR 2 (SCRUM-128) also adds two error codes, `BOOKING_NOT_LIVE` (409, with `status`: making a withdrawn or rejected booking primary, or withdrawing one, which answered `BOOKING_NOT_PENDING` before; #100 review) and `BOOKING_NOT_APPROVED` (409, with `status`: preparing a booking that isn't approved), and `venue_location` to `GET /events/available` (the primary venue's location, else `room_number`; D70) | `migrations/versions/20261103_1200_us24_multi_venue.py`, `migrations/versions/20261105_1200_us24_bookings_api.py`, `app/venue/booking_service.py`, `app/venue/primary.py` |
| 54 | US27 (SCRUM-131; §3): new endpoints `POST` and `DELETE /api/v1/equipment-lines/{id}/reservation` (Tech Support), and `GET /api/v1/equipment-lines` takes `status=approved` as well as `pending`. New error codes: `LINE_NOT_APPROVED` (409, with `status`), `ALREADY_RESERVED` (409), `INSUFFICIENT_EQUIPMENT` (409, with `available`, `requested`, `shortfall`), `NOT_RESERVED` (409); `EVENT_NOT_ELIGIBLE` is reused (D76). Every line read-back gains `reservation` | `app/equipment/router.py`, `app/equipment/service.py`, `app/equipment/schemas.py` |
| 55 | US24 PR 3 (SCRUM-129) adds two read fields: `preparation_status` on each booking of `GET /api/v1/venues/{id}/calendar` (D78), and `start_at` / `end_at` on the event request read (`EventRequestOut`; null until the event is planned), which the booking form shows as the event's schedule (D65) | `app/venue/schemas.py`, `app/venue/calendar_service.py`, `app/event/request_schemas.py` |
| 56 | US14 (SCRUM-134; §3): new endpoints `GET` and `POST /api/v1/events/{id}/tech-staff` and `DELETE /api/v1/events/{id}/tech-staff/{staff_user_id}` (the event's coordinator). New error codes: `NO_APPROVED_TECH_REQUEST` (409, D80), `EVENT_STARTED` (409), `INVALID_STAFF` (422), `ALREADY_ASSIGNED` (409) and `STAFF_UNAVAILABLE` (409), each of the last three with the `staff_user_ids` concerned, and `NOT_ASSIGNED` (409). New notification `Notifier.tech_staff_assigned` (D82) | `app/equipment/router.py`, `app/equipment/tech_staff_service.py`, `app/equipment/schemas.py`, `app/notification/service.py` |
| 57 | US12 (SCRUM-15) adds routes on `/api/v1/events/{id}` for an event past the request stage (`planning` onwards), alongside the Sprint 1 `/api/v1/events/available`, which is registered first so `available` isn't read as an id: `GET` (details, `editable`, and `pending_change_requests`), `PATCH` (the edit, `200` when saved and `202` when a change request was made, both `{outcome, message, event, change_request}`), `GET .../history` (`{entries: [{id, field, previous_value, new_value, user, created_at, change_request_id, change_request_status}]}`), and `GET /api/v1/me/coordinated-events`. New error codes: `EVENT_NOT_EDITABLE` (409, with `status`) outside Planning (AC 1), and `INVALID_EVENT_EDIT` (422, with `fields` and `errors`, a message per field, all at once) for a cleared required field, end not after start, a count below 1 or not a whole number, an unknown delivery mode, a time without its offset (D9), or a category over 100 characters (AC 4). Unknown fields (`status`, `venue_name`) are FastAPI's 422 | `app/event/edit_router.py`, `app/event/edit_service.py` |
| 58 | US12's screen (SCRUM-15). **Where:** a new **Events** screen in the coordinator's header, after Event requests, because the review queue stops at the request stage (D11) and a coordinator had no screen for an event in planning. Other roles opening it are told it isn't theirs. **Edit** is shown on every event and disabled outside Planning, with the reason (AC 1). The form sends only the fields that differ from what it loaded, so an untouched critical field never sends an edit for approval; times are Singapore wall-clock, sent with `+08:00` (D9). The form says up front which fields need approval. A refused save keeps the form open with each field's message; editing the date or either time clears both time errors, as on the booking form (PR #83 review). **History** is a tab: when, who (name and user id, AC 5), field, previous and new value, and Pending approval on a critical edit's rows | `frontend/src/features/eventEdit/` |
| 59 | US18 (SCRUM-85). **Safety:** `events.safety_approved_at` and `safety_approved_by_user_id` are what US30a (SCRUM-99) sets on approval; until it lands nobody can approve, so only the seeded Confirmation Demo (and tests) can be confirmed. **Confirmable from Approved as well as Planning** (D86). **Online events** need no venue (D72); every other event needs its venues arranged, and a request has no delivery mode, so it counts as in person (D86). **Technical support** is the US14 assignment (D80): once an event has an approved equipment line, at least one active Tech support staff member must be assigned; with none requested nothing is needed. **Equipment** must be approved and reserved (US27). **Confirming fills the event's date and capacity** from its approved bookings, because the database requires them past the request stage (`events_final_fields_required`); it doesn't write `venue_name`, which attendees now read from the primary booking (D70). **Preparation:** the status and Start preparation exist; the Venue staff and Technical support preparation updates the AC unlocks there don't exist yet, so nothing is gated. **Registration** now stays open through Preparation (`registration_service._check_registration_open`, the events board). **New error codes:** `CONFIRMATION_NOT_ALLOWED` (409, with `status`), `EVENT_NOT_READY` (409, with `outstanding` and `items`), `PREPARATION_NOT_ALLOWED` (409, with `status`). **Reading:** a coordinator reads their own event in `planning`, `confirmed` and `preparation` through the event-request routes (widens D11); a Lead still reads request-stage events only there. The screen's **Check again** exists because the venue panel and readiness list don't refresh each other | `app/event/confirmation_service.py`, `app/event/request_service.py`, `frontend/src/features/eventRequest/EventConfirmation.tsx` |
| 60 | US29a (SCRUM-97; §3): new endpoints `POST /api/v1/event-requests/{id}/change-requests` (`{changes: {field: proposed value}, reason}`, `201`) and `GET /api/v1/me/change-requests` (`event_id` optional). New error codes: `CHANGE_NOT_ALLOWED` (409, with `status`) for a Rejected, Cancelled or Completed event; `INVALID_CHANGE_REQUEST` (422, with `fields` and `errors`) for a field not open at the event's stage (D90) or an invalid proposed value, or a reason over 1,000 characters; `NO_CHANGES` (422) when every proposed value is the current one. A missing reason or no changes is `MISSING_REQUIRED_FIELD`. Organisers' requests share US12's `event_change_requests` and its `pending_approval` (AC 4's "Pending"); an organiser lists only the requests they made | `app/event/change_request_service.py`, `app/event/request_router.py` |
| 61 | US29a's screen (SCRUM-97). **Where:** a **Change requests** panel on the organiser's opened request, on the confirmation view (Submitted onwards) and below the clarification answer (Awaiting Clarification), because those are the views a submitted request opens to. **Request a change** shows only while changes can be requested. The form starts from the event's values and shows the stage's fields (D90); it sends only what differs, so an untouched field is never part of a request, and a request's other preferred dates are kept. **Review change** first checks a reason is given and something changed, then shows each field's current and proposed value and the reason before **Send change request** (AC 2, 3). A refusal goes back to the form with each field's message. The list shows each request's fields, reason and status (Pending, Approved, Rejected) | `frontend/src/features/changeRequest/` |
| 62 | US30a (SCRUM-99). **No status step:** the ticket suggests one (`awaiting_safety_check`); none was added. The safety state is derived from the reviews, `safety_approved_at` and `safety_review_requested_at` (D92), so a rejected event stays `approved` or `planning`. **Change history:** the Safety Officer sees the event's earlier reviews as the relevant history; US12 (SCRUM-15) is built but keeps no log of attendance, venue, layout, access or equipment edits, so there is none to show. **Approval can't carry a flagged item:** an approval with any checklist item marked `issue` is `422 CHECKLIST_HAS_ISSUES`; a rejection may have none. **Internal notes** reach only the Safety Officer's own routes: the coordinator, organiser and Lead never get them (AC 7); the organiser and coordinator do see the reviewer's name. **Only the details a review needs** (AC 9): a separate review view, not the request, with no organiser, submission or contact details, and it opens only an event that is in the queue or has been reviewed. **D51** applies: no review of an event the officer created or coordinates (`403 SELF_DECISION_NOT_ALLOWED`). **The queue is every event that meets AC 1**, so older seeded events with an approved booking (Faculty Town Hall) appear beside the demo. **New error codes:** `SAFETY_REVIEW_NOT_ALLOWED` (409, with `reason` and `status`), `INVALID_SAFETY_REVIEW` (422), `CHECKLIST_HAS_ISSUES` (422), `SAFETY_NOT_APPROVED` (409). The Lead reads the outcome only at the request stage, as D11 allows. **Screen:** the Safety officer's only screen is Safety reviews | `app/safety/`, `app/event/confirmation_service.py`, `frontend/src/features/safety/`, `frontend/src/features/eventRequest/SafetyOutcome.tsx` |
| 63 | US9 (SCRUM-12) PR 1 (§2): a new table `event_cancellations` and type `cancellation_status`, not in the contract before; and `events_final_fields_required` now lets a `cancelled` event go without its date, capacity and delivery mode (not its name), so an Approved event without them can be cancelled (D98); `GET /api/v1/me/coordinated-events`, `GET /api/v1/events/{id}`, `GET /api/v1/me/managed-events` and `GET /api/v1/events/{id}/registrations` leave such an event out (`404` when opened) | `app/event/models.py`, `app/event/edit_service.py`, `app/registration/roster_service.py`, migration `20261112_1200_us9_cancellations` |
| 64 | US30b (SCRUM-100). **The event's status doesn't move:** the ticket says the event "stays in (or returns to) Planning", but nothing moves an approved request to Planning (D53) and an approval is final (D92), so a request for changes leaves an `approved` or `planning` event where it is and marks the areas on the review instead. **Nothing is reset:** the venue booking, equipment lines and technical support are not touched; the readiness list says what the Safety Officer asked for ("The Safety Officer asked for changes to Venue, Layout: …"), and the coordinator decides what to change. **"Marks the changes done" is the send-back US30a already has:** `POST /api/v1/event-requests/{id}/safety-review-request` serves a rejection and a request for changes alike (its `reason` values keep their names), and the screen labels the button **Mark changes done** for the latter. **The checklist is still answered in full** (all seven items, `issue` allowed), because the ticket doesn't say it is optional. **"Other" has no free text of its own:** the comments carry it. **Only before confirming:** changes are requested while the event is `approved` or `planning` and not yet safety-approved, like a rejection. New state `changes_requested` beside `pending`, `approved` and `rejected`. **Screens:** **Request changes** button and **Areas affected** tick boxes on the Safety officer's review | `app/safety/`, `app/event/confirmation_service.py`, `frontend/src/features/safety/`, `frontend/src/features/eventRequest/SafetyOutcome.tsx` |
| 65 | US9 (SCRUM-12) PR 2 (§3): new endpoints `POST /api/v1/event-requests/{id}/cancellation-requests`, `POST /api/v1/event-requests/{id}/cancel`, `GET /api/v1/event-requests/{id}/cancellations`, and `POST /api/v1/event-cancellations/{id}/approve` and `/reject` (decided by the request's own id, as venue bookings are). New error codes: `CANCELLATION_NOT_ALLOWED` (409, with `status`), `CANCELLATION_PENDING` (409, with `cancellation_id`), `CANCELLATION_NOT_PENDING` (409, with `status`), `INVALID_CANCELLATION` (422), and `EVENT_CANCELLED` (409) on accepting a waitlist offer for a cancelled event; `EVENT_STARTED` (409, with `starts_at`) as US14's. New notices `cancellation_requested`, `cancellation_rejected` and `event_cancelled` (log-only) | `app/event/cancellation_service.py`, `app/event/request_router.py`, `app/registration/service.py`, `app/notification/service.py`, `app/equipment/service.py` (reserve reads the event FOR SHARE) |
| 66 | US15 (SCRUM-139; §3): new endpoints `GET` and `POST /api/v1/event-requests/{id}/sessions` (`201`) and `PATCH` and `DELETE /api/v1/event-sessions/{id}` (`200`, `204`). New error codes: `INVALID_SESSION` (422, with `fields` and `errors`) for every invalid field at once, a missing one included (one code rather than `MISSING_REQUIRED_FIELD` as well, so the form marks them together), and a time outside the event's window (D94); `SESSION_OVERLAP` (409, with the clashing `session`: `id`, `title`, `starts_at`, `ends_at`); `AGENDA_NOT_EDITABLE` (409, with `status`) outside `draft` and `planning` (D93). Each listed session carries `outside_window`, true when the event's window has since moved away from it (D94), for the Agenda's marker (SCRUM-140) |
| 67 | US9's screens (SCRUM-12). **Where:** a **Cancellation** panel on the organiser's opened request (the confirmation view, Approved onwards, and afterwards for the record) and on the coordinator's review screen for their assigned event, below Confirmation, since those are where each already works the event. The coordinator's direct cancel takes a reason and then a separate confirm step naming what's released and who's told, because it can't be undone (AC 4); approving an organiser's request has the same confirm step, since it releases the same things and can't be undone either (PR #119 review). The confirm text says the organiser, everyone registered or waiting, and any venue or technical support staff involved are told. The approved badge reads **Cancelled**. A seeded **Cancellation Demo** for the E2E; a reseed puts it back. `venue-buffers.spec.ts` now looks up its form's **Cancel** button exactly, since **Cancel event** shares the screen | `frontend/src/features/cancellation/`, `EventRequestsPage.tsx`, `ClarificationReviewPage.tsx`, `backend/app/seed.py`, `e2e/tests/event-cancellation.spec.ts` |
| 68 | US29b (SCRUM-142; §3): new endpoints `GET /api/v1/change-requests`, `GET /api/v1/change-requests/{id}`, `POST /api/v1/change-requests/{id}/approve` and `/reject` (the event's coordinator, or a Lead for a coordinator's own US12 edit, D102), `GET /api/v1/events/{id}/review-flags` and `POST /api/v1/review-flags/{id}/clear` (the event's coordinator). New error codes: `CHANGE_REQUEST_NOT_PENDING` (409, with `status`), `CHANGE_REQUEST_STALE` (409, with `fields` and `message`, D107), `INVALID_CHANGE_DECISION` (422), `FLAG_ALREADY_CLEARED` (409), `INVALID_REVIEW_FLAG` (422); `CHANGE_NOT_ALLOWED` is reused for approving late (D105), and `SAFETY_REVIEW_NOT_ALLOWED` gains `reason: "review_flags_open"` (D106). Additive reads: `decided_at` and `rejection_reason` on the organiser's change requests, `action` on History entries, a `review_flags` readiness item. New notifications `Notifier.change_request_decided` and `Notifier.arrangement_flagged` (log-only). A resolved flag is derived on read, never written (D104). The list later gained an optional `acting_as` (`coordinator` or `coordinator_lead`, SCRUM-143, Calvin's #127 review) for a user holding both roles | `app/event/change_decision_service.py`, `app/event/change_decision_router.py`, `app/event/review_flag_service.py`, `app/safety/service.py`, `app/event/confirmation_service.py` |
| 69 | US25 (SCRUM-93) PR 1 (§2): `venue_booking_status` gains `held` and `expired`, `venue_bookings` gains `hold_expires_at`, `held_by_user_id`, `hold_warned_at` and `expired_at`, and the overlap guard covers held rows. Numbered 69 because US29b (SCRUM-142) took 68 | `app/venue/models.py`, `app/venue/availability.py`, `app/venue/service.py`, migration `20261115_1200_us25_holds` |
| 70 | US25 (SCRUM-93) PR 2 (§3): new endpoints `POST /api/v1/venue-holds`, `GET /api/v1/venue-holds/events` and `POST /api/v1/venue-bookings/{id}/confirm`; `withdraw` takes a held booking; a booking read gains `hold_expires_at`, `held_by_user_id`, `expired_at` and `next_action: coordinator_to_confirm`; calendar items gain `kind: "hold"` and `booking.hold_expires_at`; `GET /venue-bookings/pending`, `GET /events/{id}/venue-bookings`, the calendar and search take the clock and notifier to sweep lapsed holds. New error codes `INVALID_HOLD` (422) and `HOLD_NOT_HELD` (409). Screens: **Hold a venue** on Venues for Venue staff, reusing the request form with an expiry; Confirm and Decline on the coordinator's event; holds on the calendar | `app/venue/hold_service.py`, `app/venue/booking_service.py`, `app/venue/booking_router.py`, `app/venue/router.py`, `app/venue/calendar_service.py`, `frontend/src/features/venue/` |
| 71 | US29b's screens (SCRUM-143). Numbered 71 because US25 took 69 and 70. **Where:** on the coordinator's Event requests screen, a **Change requests to review (N)** section above the review queue (event, requester, date, **Significant**; hidden when none waits), whose **Review** opens the event's review screen at a **Change requests** panel, placed between the venue bookings and the safety review, next to the arrangements it affects; that screen opens every status a request can be decided in. **Review after change** (the flags) sits under the readiness list, where confirming is decided. **Steps:** Approve takes a second click (**Approve change**); Reject asks for the reason first (**Reject change**), checked on screen before anything is sent; no modal dialogs. **Wording:** the significant notice reads "What approving does: moves this event back to Planning · flags 1 venue booking and 1 equipment reservation for review · needs a new safety review", built from the API's `impact`; the safety notice, "A new safety review is needed", shows only when the state is pending, the latest review is an approval and the event has no `safety_approved_at`, and can't say which change cleared it (the flags and History do); History rows carry Applied, Approved change or Rejected change, Moved to Planning, Confirmation cleared and Safety approval cleared. **The Lead (SCRUM-144, D102), extending this deviation:** on the Lead's Event requests screen (the assignment queue a Lead lands on), a **Coordinator edits to approve (N)** section above the Unassigned and Assigned tabs, on both (event, the coordinator who asked, date, **Significant**; hidden when none waits; listed with `acting_as=coordinator_lead`, so a user holding both roles sees only the Lead's list (the API's list, unfiltered on screen)). **Review** opens a **Coordinator edit** screen built from the change request alone (`GET /api/v1/change-requests/{id}`, which takes no `acting_as`: event name and status, then the same table and Approve / Reject as the coordinator's panel; one already decided reads "Already approved/rejected by … on …" with any reason; after a decision the header shows the status it left), never the event, which only its assigned coordinator may read past the request stage (`_can_read`); rows read "Casey Tan asked … (a critical edit)"; after a decision the request closes, its outcome stays and the list reloads. The Lead sees no review flags or readiness list (flags are the coordinator's, §3); the coordinator works through them on their review screen | `frontend/src/features/changeRequest/`, `frontend/src/features/eventRequest/ClarificationReviewPage.tsx`, `EventConfirmation.tsx`, `SafetyOutcome.tsx`, `frontend/src/features/eventEdit/EventsPage.tsx`, `frontend/src/features/eventRequest/AssignmentQueuePage.tsx` (SCRUM-144) |
| 72 | US23a (SCRUM-90) PR 1 (§2): `venue_blocks` gains `reason` (with `venue_blocks_reason_known`) and `created_by_user_id`; `venue_bookings` gains `rearrangement_block_id` and `rearrangement_flagged_at` (D113), not the `needs_rearrangement` booking status Jira's subtask names | `app/venue/models.py`, migration `20261116_1200_us23a_blocks` |
| 73 | US23a (SCRUM-90) PR 2 (§3): new endpoint `POST /api/v1/venues/{id}/blocks` (Venue staff) and error code `INVALID_BLOCK` (422, with `fields` and `errors`); a booking read's `unavailability` gains `kind: "venue_unavailable"` with `block` and `flagged_at`, and its `next_action` is `coordinator_to_rebook` for a marked hold too; confirming a marked hold is `409 VENUE_UNAVAILABLE`; calendar items gain `reason`; new notifier method `Notifier.venue_unavailable`; `Conflict` carries a block's `reason` | `app/venue/router.py`, `app/venue/block_service.py`, `app/venue/booking_service.py`, `app/venue/schemas.py`, `app/notification/service.py` |
| 74 | US31 (SCRUM-107). **Notices are kept by the notifier, not by each story:** the 23 `Notifier` methods are unchanged, so no story's call sites or tests changed; `RecordingNotifier` logs through `LoggingNotifier`, then writes a row for the recipient (D116). **The recipient is found by email** (case-insensitive), because that is all the notifier is given; an address no user holds is logged and skipped. **The event is found from what the notice carries** (its id, request reference, booking, equipment line or registration); one that can't be found is kept without an event, with no link. **"Open" is the request, for who may read it:** `can_open` is the request routes' own rule (D11, D47, D48): the organiser their own, the assigned coordinator theirs, a Lead at the request stage. Everyone else (attendees, Venue staff, Tech support, Safety officers) gets the notice with no link, because they have no screen for the event. The organiser and coordinator open the request itself; a Lead lands on Event requests. **Wording is fixed when the notice is raised** (plain English, times in Singapore time with "SGT", as everywhere else, TC-X-01), so changing the text later doesn't change old ones. **No history before this change** and **no email**. **The count polls every 30 seconds**, and on every screen change; a real-time push is out of scope. **"Cancellation" notices** (US9) are kept like the rest. **Screen:** **Notifications** is every role's last screen | `app/notification/`, `frontend/src/features/notifications/`, `frontend/src/components/SiteHeader.tsx` |
| 75 | US23b (SCRUM-91) PR 1 (§2): `venue_booking_status` gains `replaced`, added with `ADD VALUE` and compared as text in its CHECK, not by rebuilding the type (D117); `venue_bookings` gains `replaced_at`, `replaces_booking_id` (with `venue_bookings_one_live_replacement`), `restore_requested_at`, `restore_requested_by_user_id`, `restore_declined_at`, `restore_declined_by_user_id` and `restore_decline_reason` (D118); `venue_blocks` gains `ended_early_at`, `ended_early_by_user_id` and `scheduled_ends_at`, and `venue_blocks_window_valid` allows an empty block once ended early | `app/venue/models.py`, migration `20261117_1200_us23b_replacement` |
| 76 | US23b (SCRUM-91) PR 2 (§3): `POST /venue-bookings` takes `replaces_booking_id`; new endpoints `POST /api/v1/venues/{id}/blocks/{block_id}/end`, `POST /api/v1/venue-bookings/{id}/restore`, `GET /api/v1/venue-bookings/restore-requests`, `POST /api/v1/venue-bookings/{id}/restore/confirm` and `/restore/decline`; a booking read gains `replaces_booking_id`, `replacement_booking_id`, `replaced_at`, `restore_requested_at`, `restore_requested_by_user_id`, `restore_declined_at`, `restore_decline_reason` and `next_action: venue_staff_to_restore`; a block summary, a block response and a calendar block gain `ended_early_at` (and `scheduled_ends_at`, or `block_id` on the calendar); `POST /venues/{id}/blocks` now moves an affected Confirmed or Preparation event to Planning. New error codes `BOOKING_NOT_REPLACEABLE`, `REPLACEMENT_EXISTS`, `RESTORE_ALREADY_REQUESTED`, `RESTORE_NOT_REQUESTED` (409) and `BLOCK_ENDED` (409). Notifier gains `venue_restore_requested`, `venue_restore_decided`, `venue_changed` and `venue_period_ended`, each kept by US31's recorder | `app/venue/booking_service.py`, `app/venue/block_service.py`, `app/venue/booking_router.py`, `app/venue/router.py`, `app/notification/service.py`, `frontend/src/features/venue/` |

### Open decisions still unanswered

§6 defines D1–D6 and a Sprint 1 default for each. All six were coded to their defaults and marked in the code; D1, D2 and D3 are now settled (below), and **D4 to D6 have not been confirmed by the team**. D7 is new and not in §6. D8–D12 came from US1 and D13–D15 from US8 and D16–D17 from US6a; D18–D19 from US20; D20–D24 from US22; D25–D26 from US2; D27–D28 from US10a; D30 from SCRUM-67; D31–D37 from US13 (the story owner's choices, awaiting the team); D41 and D43 from US26; D42 from US10d; D44 from US19; D45–D51 from US16b (the story owner's decisions of 25 Oct, reasoning in §9 "US16b role-based access: decisions"; D47 and D51 decided by the acting PO, Matthew, on 25 Oct; D55 from SCRUM-120, asked of him on #88); D52 from US28; D53 from US17; D54 from US10e (SCRUM-83); D56–D61 from US21 (SCRUM-88; D56 to D58 the story owner's choices of 26 Oct, D60 decided by the acting PO, Matthew, on 30 Oct); D62–D64 from US5 (SCRUM-9; D64 decided by the acting PO, Matthew, on 30 Oct); D74–D76 from US27 (SCRUM-95; approved 31 Oct, so not marked in the code); D65–D73 from US24 (SCRUM-92; the story owner's defaults of 31 Oct, approved with review changes, with D67 and D73 following customer clarifications CS3-24 and CS3-49; D65, D66, D68, D70 and D73 are marked in PR 1's code, D67, D69, D71 and D72 in PR 2's; D77 from US24 PR 2 (SCRUM-128) and D78 from PR 3 (SCRUM-129), the story owner's choices of 31 Oct); D79 to D83 from US14 (SCRUM-17, decided by the acting PO on 31 Oct); D86 from US18 (SCRUM-85); D87 to D89 from US12 (SCRUM-15); D90 and D91 from US29a (SCRUM-97); D93 to D97 from US15 (SCRUM-18, decided by the acting PO on 1 Nov); D98, D100 and D101 from US9 (SCRUM-12); D99 from US30b (SCRUM-100); D102 to D107 from US29b (SCRUM-98); D108 to D112 from US25 (SCRUM-93); all are marked `DECISION-PENDING` in the code (D20 from US22 PR 2, where its check lives), **except D21, which the team has decided** (no longer marked), **and D47 and D51, decided by the acting PO on 25 Oct, and D60 and D64, on 30 Oct, and D74 to D76, approved on 31 Oct, and D79 to D83, decided by the acting PO on 31 Oct, and D93 to D97, on 1 Nov, and D3 and D7, decided via the SCRUM-136 bug fix, and D1 and D2, via the SCRUM-137 bug fix, 31 Oct, and D102 to D107, decided on 3 Nov**.
 
| id | Question | What we assumed |
|---|---|---|
| D1 | How long is a waitlist offer valid? | **Decided via the SCRUM-137 bug fix, 31 Oct:** 24 hours, one constant `WAITLIST_OFFER_WINDOW` |
| D2 | What expires an offer? | **Decided via the SCRUM-137 bug fix, 31 Oct:** expiry on read. Every read or change of an event's registrations (events board, My events, register, join waitlist, withdraw, accept, decline, the organiser's registrations list) first expires its lapsed offers and passes each place to the next person, notified with a new window, or back to capacity (`expire_lapsed_offers`, §1a "Lapse on read"). `POST /expire-offer` stays, for tests |
| D3 | Is a waitlisted person an attendee or just an email? | **Decided via the SCRUM-136 bug fix, 31 Oct:** an attendee. Joining a waitlist requires login, and every new entry stores the attendee's `attendee_id` and their own email. Email-only rows made before stay as they are; one is linked to its attendee, matching the email in any letter case, when they try to join (TC-US6A-15) |
| D4 | Are "cancel" and "withdraw" the same action? | Yes, one action |
| D5 | Does withdrawal notify by email or on screen? | On screen only |
| D6 | May a waitlisted person leave the queue? | Yes, via the same withdraw endpoint |
| D7 | Must you be identified to join a waitlist? | **Decided via the SCRUM-136 bug fix, 31 Oct:** yes. `POST /events/{id}/waitlist` depends on `get_current_attendee` and takes no body; no login is `401 UNAUTHENTICATED` |
| D8 | What are the event category options? | Free text, non-empty, max 100 chars |
| D9 | What timezone are preferred times in? | Asia/Singapore local time (`time` without zone); converted when a request becomes an event |
| D10 | What's the request reference format? | `ER-<year>-<6-digit sequence>`, e.g. `ER-2026-000123`, from `event_request_reference_seq`; one formatter function |
| D11 | Who can read a submitted request? | The owner, Event Coordinator Leads (`coordinator_lead`, since US10a) and **since SCRUM-120 only the request's assigned coordinator** (D48), **only while in a request status** (submitted → rejected). Other organisers and other coordinators 404. Drafts owner-only. Venue Staff (and `operations_manager` before them, D19) read every submitted request until SCRUM-120; now they, like other roles without a reading role, get `403` (deviation 46) **Widened by SCRUM-85 (D86):** the assigned coordinator also reads their own event in `planning`, `confirmed` and `preparation`, and these join their review queue; a Lead and everyone else still stop at `rejected` |
| D12 | How are users identified before Supabase Auth? | `X-User-Id` header stub, alongside `X-Attendee-Id`. The frontend's **Acting as** switch (header) sends the seeded organiser's or coordinator's id from `frontend/.env`; the choice is kept in `localStorage`. Since SCRUM-102 the stubs are dev-only, behind `AUTH_DEV_HEADERS` (default off) |
| D13 | Which sections can a clarification request tag? | SCRUM-11 only gives examples (attendance, layout, equipment). Assumed seven, grouping the US1 fields: `details`, `schedule`, `attendance`, `layout`, `accessibility`, `equipment`, `registration`. One list in `CLARIFICATION_SECTIONS`, mirrored by the migration's CHECK |
| D14 | Which coordinator may ask for clarification? | Any active coordinator. US10a (SCRUM-13) assigns a coordinator to a request, using US16b's (SCRUM-82) roles; tighten this to the assigned one then. SCRUM-13 PR 2 assigns but did not tighten it (the ticket doesn't ask), so a follow-up must decide. **Retired by SCRUM-120: only the assigned coordinator (D48).** |
| D15 | When may a coordinator send another clarification round? | From `submitted` or `under_review`, no limit; the new round is `max(round) + 1`. `awaiting_clarification`, `approved`, `rejected` → `409 CLARIFICATION_NOT_ALLOWED`. `awaiting_clarification` is blocked on purpose: the organiser's reply answers the latest open round, so a second open question would never get its own answer. Past the request stage (`planning` → `completed`) and drafts stay `404` under D11. `CLARIFIABLE_STATUSES` in `clarification_service.py`. **Differs from SCRUM-75 AC 1, which allows another round while Awaiting Clarification. Confirm with the team.** |
| D16 | Does joining a waitlist need registration to be open? | Yes. US6a AC 1's "reached its registration capacity" presumes it, so `join_waitlist` applies register's gates (`_check_registration_open`): `403 REGISTRATION_NOT_ENABLED` unless confirmed with registration enabled, `403 REGISTRATION_CLOSED` outside the window |
| D17 | What happens to people already queued if an event's waitlist is switched off? | They keep their place and still get offers: `offer_freed_seat` ignores `waitlist_enabled`, because US6a only governs joining |
| D18 | Which tags can a venue's facilities, accessibility features and room layouts use? | SCRUM-87 only gives examples. Assumed fixed lists, so US2's filters and the venue form agree on spelling. Facilities: `projector`, `screen`, `sound_system`, `microphone`, `stage`, `wifi`, `whiteboard`, `video_conferencing`, `power_outlets`. Accessibility: `wheelchair`, `lift`, `accessible_toilet`, `hearing_loop`, `step_free_entrance`. Layouts: `theatre`, `classroom`, `banquet`, `boardroom`, `u_shape`, `cabaret`, `standing`. Constants in `app/venue/models.py`, mirrored by the migration's CHECKs |
| D19 | Who stands in for Venue Staff before US16b adds the role? | `operations_manager`, one constant `VENUE_STAFF_ROLES` in `app/venue/service.py`; US16b changes it to `venue_staff`. The seed adds `venue.staff@smu.edu.sg` with that role, and **Acting as → Venue staff** sends its id. `operations_manager` stays a Venue Staff stand-in only: US10a (SCRUM-13) gave the Coordinator Lead its own `coordinator_lead` role and seeded two Leads, so the roles are already split. The venue staff user can read the event-request queue (D11). A Lead can no longer create, edit or deactivate venues, and gets `403` on the venue write routes. US22's booking notices go to Venue Staff (`operations_manager`) only, so Leads don't get them. **Retired by SCRUM-119 (D49):** `VENUE_STAFF_ROLES` is `(venue_staff,)`, the migration moved the seeded venue staff user to `venue_staff`, and **Acting as → Venue staff** now sends a real `venue_staff` user. No longer marked in the code |
| D20 | Who may request a venue for an event, and see its bookings? | **Since US10a (SCRUM-13): only the coordinator assigned to the event** (`events.coordinator_id`), as AC 1 says, for an Approved or Planning event: `may_book` (`app/venue/booking_service.py`). A coordinator not assigned to it, and anyone on an **unassigned** event, is refused as before: `404 NOT_FOUND` on create and on the event's booking list. Venue Staff still read any event's bookings. The inactive-venue read (`_has_live_booking_by`, `app/venue/service.py`) widened from "requested the booking" to "assigned to its event", whoever made the request. Before US10a any coordinator could book. **Still to confirm:** withdrawing stays with the coordinator who made the request, even if the event is later reassigned. **US26 (SCRUM-109) uses the same rule for equipment lines** (`may_manage`, `app/equipment/service.py`): only the event's assigned coordinator lists, adds, edits and removes them, whoever added the line; anyone else gets `404`. This replaces the ticket's earlier interim "any active coordinator, as D14", which assumed coordinators weren't assigned yet |
| D21 | Does a pending (Requested) booking block the window? | **Decided by the team:** yes, Requested and Approved both block. Based on the sessions 1–2 clarification behind AC 7: "any overlap is prevented; first come, first served". AC 3 names only approved bookings, but first come, first served needs a pending request to hold the window too. `LIVE_BOOKING_STATUSES` (`app/venue/models.py`) and the exclusion constraint `venue_bookings_no_overlap` enforce it, which also settles AC 7's race |
| D22 | What window does the overlap check use? | **Since US13 PR 1 (SCRUM-114), the occupied window** `[starts_at − setup, ends_at + turnaround)`, from the venue's buffers when the booking is made, stored on the booking (`occupied_starts_at`, `occupied_ends_at`) because an exclusion constraint can't read `venues`. Windows that only touch don't clash. Since PR 2 (SCRUM-115) the stored windows are recomputed when buffers change (D31) and the occupied window must fit the opening hours (D32). Before US13 it was the plain `[starts_at, ends_at)`. Unavailability is US2's `venue_blocks` (deviation 30): a request overlapping a block is refused by the same rule. Bookings are kept apart by the exclusion constraint, but blocks only by the service's check (`block_conflicts` in `app/venue/availability.py`, against the booking's occupied window; blocks have no buffers of their own), so a block added while a request is in flight isn't seen; US23a (SCRUM-90), which adds the block screens, should lock the venue row `FOR UPDATE` so requests (which read it `FOR SHARE`) wait. Holds (US25, SCRUM-93) don't exist yet and extend the check when they land |
| D23 | How does a request say which facilities and accessibility it needs? | D18 tag lists on the booking (`required_facilities`, `required_accessibility_features`), because the event's `equipment_needs` and `accessibility_needs` are free text and can't be matched against a venue |
| D24 | How do events reach Approved? | Since US17 (SCRUM-84), the assigned coordinator approves a request under review (D53). Tests and the seed still put events straight into `approved` and later statuses, with no recorded decision |
| D25 | Who may search for available venues (US2)? | `coordinator` and `venue_staff` (`operations_manager`, D19's stand-in, until SCRUM-119); the Coordinator Lead, organisers and attendees `403`. One constant, `VENUE_SEARCH_ROLES` in `app/venue/service.py`. Still open: whether the Lead may search |
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
| D45 | How does a user hold more than one role (US16b AC 1)? | A `roles` list column on `users` (Postgres array of `user_role`, at least one, no repeats), replacing `users.role`. Not a `user_roles` table. Decided 25 Oct; reasoning in §9. **Built in SCRUM-119** |
| D46 | Does the API check the role a user is *using* or every role they *hold* (US16b AC 2, 3)? | Every role they hold. The current role is a frontend choice (the switcher), not sent to the API. Decided 25 Oct; reasoning in §9. **Built in SCRUM-119** (`require_user_roles` and every other check use `User.holds`) **and SCRUM-121** (the switcher, deviation 49) |
| D47 | What is an Organiser's "organisation" (US16b AC 4)? | The organiser themselves: each organiser sees only the requests they created, and another organiser's request is `404`, today's owner-only rule (D11). **Decided by the acting PO (Matthew) on 25 Oct: colleagues at one organisation must not see or work on each other's requests, and there's no organisations model, now or later.** Reasoning in §9 |
| D48 | Which coordinator may see and act on a request (US16b AC 5)? | Only its assigned coordinator, for the review queue, the request's details, its clarification thread and sending a clarification; anyone else `404`. No coordinator can clarify an unassigned request. On reassignment (SCRUM-83) the thread follows the request: the new coordinator reads and continues it, the previous one loses access. Retires D14 and narrows D11 for coordinators; matches D20 (venues) and equipment. Decided 25 Oct; reasoning in §9. **Built in SCRUM-120** (`is_assigned_coordinator` in `app/event/request_service.py`); a Lead still reads every request and sees the whole queue |
| D49 | What happens to `operations_manager`, D19's stand-in for Venue Staff? | Its users become `venue_staff` and nothing checks `operations_manager` any more; the value stays in `user_role` because Postgres can't drop an enum value. Retires D19. Decided 25 Oct; reasoning in §9. **Built in SCRUM-119** |
| D50 | Which seeded user holds two roles (US16b subtasks: "one user with two roles")? | `multi.role@smu.edu.sg` (Morgan Lau), Coordinator and Venue staff. Decided 25 Oct; reasoning in §9. **Seeded by SCRUM-119**, with a Supabase login |
| D51 | Can one person decide a request they made (US16b, with D46)? | No, anywhere in the application: **no one decides a record they created**, whatever roles they hold. Venue bookings: approving or rejecting is refused if the decider requested the booking or is the event's current coordinator. Equipment lines: the same for reviewing. Assignment and reassignment: a Lead can't assign or reassign a request they created, and a request can't be (re)assigned to its creator. Event requests (US17, SCRUM-84) inherit it. `403 SELF_DECISION_NOT_ALLOWED` (assigning to the creator is `422 INVALID_COORDINATOR`, `reason: created_the_request`); database CHECKs on bookings and equipment lines. **Decided by the acting PO (Matthew) on 25 Oct.** Reasoning in §9. **Built in SCRUM-120** for bookings, equipment lines, assignment and SCRUM-83's reassignment (deviation 45), and by SCRUM-84 (#90) for event requests (deviation 47); all four call `refuse_self_decision` |
| D52 | Who manages an event, for viewing its registrations (US28)? | The Organiser who created it (`created_by_user_id`) and the event's **assigned** Coordinator (`coordinator_id`, US10a), whichever of those roles the user holds (D46). Only events past the request stage (`planning` onwards); anyone else's or an unassigned event is `404`. `_manages` in `app/registration/roster_service.py` |
| D53 | What does deciding an event request do (US17)? | Approve → `approved`, reject → `rejected`; neither moves the request on to `planning` (D27 says approval leads there, but no AC says when, so it's left to the planning story). Only the assigned coordinator (D48), only from `under_review`, never on a request they created (D51). A rejection's reason is required, trimmed, up to 1,000 characters, and stored; an approval takes none. `app/event/decision_service.py` |
| D54 | What does "the previous coordinator can no longer see or manage it" (SCRUM-83 AC 3) cover while coordinators can read every submitted request (D11)? | **A coordinator no longer sees an event that has a *different* coordinator**: `GET /event-requests/{id}` and its clarification thread are `404`, the review queue (`GET /event-requests`) leaves it out, and sending a clarification is `404`. This is the part of D48 (SCRUM-120) that reassignment needs, so SCRUM-83 lands it first; **it does not go as far as D48 on unassigned requests**, which stay visible to every coordinator as before (D48 would hide them), so SCRUM-120 should tighten that and can reuse the checks in `request_service._can_read`, `list_for_review` and `clarification_service.send_request`. Venue bookings and equipment lines were already limited to the assigned coordinator (D20). **Venue withdraw changes with it:** a pending booking is now withdrawn by the coordinator assigned to its event, not the one who made it, so the new coordinator can manage pending requests. The requester still gets the decision notice (D40). Leads are unaffected (a user who holds both Coordinator and Lead keeps the Lead's view) **Tightened by SCRUM-120 (#88, D48):** a coordinator now sees only requests assigned to them, unassigned ones included, through one check, `is_assigned_coordinator`; this PR's `_is_other_coordinators_event` and the extra clarification check were folded into it |
| D55 | Do Venue Staff read event requests (US16b, with D48)? | No. The review queue, a request's details and its thread are for Organisers (their own), Coordinators (their assigned ones) and Leads; Venue Staff get `403` (deviation 46). Their access was D19's leftover (`operations_manager` once read the queue), and through it `multi.role` (Coordinator and Venue staff) would see every request, defeating D48. Their pending list already names each booking's event, so nothing they do needs a request. **The story owner's decision, 25 Oct, while building SCRUM-120; asked of the acting PO on #88.** Reasoning in §9. `Reviewer` and `Reader` in `app/event/request_router.py`, `DECISION-PENDING` |
| D56 | Who may open a venue's availability calendar (US21 AC 5)? | Coordinator, Coordinator Lead and Venue staff, on any role held (D46): `CALENDAR_ROLES` in `app/venue/service.py`. AC 5 only rules out Organisers and Attendees; the story names Coordinators and Venue Staff, and the Lead oversees coordinators' events. Tech support and the Safety officer get `403` until a story needs them. The story owner's choice, 26 Oct |
| D57 | Does the calendar show Requested bookings (US21 AC 1 names approved ones)? | Yes, each with its `status`, so the screen marks it pending: a Requested booking blocks the window (D21), and a coordinator shouldn't pick a time that looks free and get `VENUE_UNAVAILABLE`. Deviation 50. The story owner's choice, 26 Oct |
| D58 | What does a calendar booking show (US21 AC 3)? | To every calendar user: the event's name (or its request reference when unnamed) and status, the booking's status, its own times and its occupied window. The booking's `VB-` reference only to Venue staff, Leads and the event's assigned coordinator, null to other coordinators, as a coordinator's `VENUE_UNAVAILABLE` never names another booking (D35). No event id or link into the request, which D48 keeps to its own coordinator. `REFERENCE_ROLES` in `app/venue/calendar_service.py`. The story owner's choice, 26 Oct |
| D59 | What is a "Hold" on the calendar before US25 (SCRUM-93)? | Nothing yet: `kind: "hold"` and the label "Hold" are reserved and none are returned (`_hold_items`, `TODO(US25)`). When holds land they join the calendar and an expired one is left out (AC 4) **Since US25 PR 2 (SCRUM-93)** holds are listed and drawn, kind `hold`, label "Hold", with their expiry; an expired one isn't. |
| D60 | What is a "cancelled booking" (US21 AC 4)? | Bookings aren't cancelled: they are withdrawn or rejected, and only live ones (`LIVE_BOOKING_STATUSES`) are shown. A live booking whose **event** is `cancelled` **is shown**, with the event's status `cancelled`, because it still blocks the window (the exclusion constraint and `evaluate_window` don't look at the event). **Decided by the acting PO, Matthew, on 30 Oct** (via Calvin's review of #92). Whether cancelling an event withdraws its bookings is US9's (SCRUM-12) **Since US9 PR 2 (SCRUM-12)** cancelling withdraws them, so a cancelled event's bookings leave the calendar. |
| D61 | What range does the calendar take, and how are hours shown? | `from` and `to`, Singapore days (D9), both included, at most 42 (a month view's six weeks), so the window is `[from 00:00, to + 1 day 00:00)` SGT. An item is in range if its **occupied** window overlaps it, so a booking whose setup starts the evening before still shows. Sorted by occupied start, bookings before blocks at the same start. The venue's opening hours and buffers come back with it for the screen to shade "Closed"; hours aren't items, and "Unavailable" is only ever a block. An inactive venue follows `GET /venues/{id}`: Venue staff, Coordinator Leads (who oversee every coordinator's events; Calvin's review of #92) and a coordinator whose event is booked there (`venue_service.visible`). The venue list (`GET /venues`) still shows inactive venues only to Venue staff, so the calendar's venue picker (SCRUM-123) lists only active venues for Leads; showing them inactive ones too needs `GET /venues` to include them for Leads, a backend follow-up (#95 review) |
| D62 | How is equipment stock counted (US5 AC 3)? | Per type, not per unit: `equipment_types.total_quantity` owned and `out_of_service_quantity` damaged, under repair or otherwise unavailable, as one count since AC 3 treats them alike. Follows the 12 Oct customer clarification that equipment is tracked by type (as D41). `equipment_types_stock_in_range` keeps `0 <= out_of_service <= total`. The story owner's choice, 29 Oct; to confirm with the acting PO on the SCRUM-124 PR |
| D63 | Who records equipment stock (US5)? | Only the seed (`EQUIPMENT_STOCK` in `app/seed.py`) for now: no AC asks for a screen to edit it, so none is built. A later story can add one. The story owner's choice, 29 Oct; to confirm with the acting PO on the SCRUM-124 PR |
| D64 | Is US5's check stored (AC 5: "records the outcome … as a check only")? | Yes, the latest check only, on the line: `availability_checked_at`, `availability_checked_by_user_id`, `availability_sufficient`, `availability_shortfall` (migration `20261102_1200_us5_check_outcome`; `equipment_request_lines_availability_check_consistent` keeps them whole and consistent). A newer check replaces it; editing the line's quantity or type clears it, since it no longer applies. It never reserves ("a check only") and doesn't block a review. First read as "not stored" (29 Oct), then changed to this by the story owner. **Decided by the acting PO, Matthew, on 30 Oct** (in the team channel) |
| D65 | What is "the event's overall schedule" a booking's window must fall within (US24 AC 1)? | `[start_at, end_at]` once those are set; before that (an Approved request has no `start_at`), a day in `preferred_dates` between `preferred_start_time` and `preferred_end_time`, Singapore time. Only the booking's own window must fit; setup and turnaround may fall outside. Existing bookings aren't re-checked. Checked from PR 2 as `422 INVALID_BOOKING` on `starts_at` / `ends_at`. Customer clarification CS3-22; the story owner's default, 31 Oct |
| D66 | Must each booking have a purpose, and in what form (US24 AC 1)? | Yes: free text, trimmed, 1 to 100 characters (`venue_bookings_purpose_valid`), e.g. "Main hall", "Breakout A". Existing bookings became "Main venue". Required by the API since PR 2 (`MISSING_REQUIRED_FIELD`; blank or over 100 characters `INVALID_BOOKING`), and the column no longer has a default; the booking form has a Purpose field. The story owner's default, 31 Oct |
| D67 | Must the venues' allocations add up to the event's expected attendance (US24 AC 3)? | Yes, for "arranged" (CS3-24: "allocations must account for the expected attendees"): the live bookings' `expected_attendees` must add up to at least the event's `expected_attendees`, or `venues_arranged` is false (D72). A booking is never refused for it: each allocation must only be at most its venue's capacity (`VENUE_CAPACITY_EXCEEDED`, as since US22), and the coordinator's screen shows the total against expected, with any shortfall. Rooms used in turn still fit, since the sum may exceed the expected attendance. Customer clarification CS3-24; built in PRs 2 and 3 |
| D68 | How is the primary venue chosen and kept (US24 AC 4)? | `is_primary`, at most one **live** primary per event (`venue_bookings_one_primary_per_event`, partial on requested and approved). From PR 2 the event's first live booking becomes primary and Make primary moves it. A withdrawn or rejected primary isn't replaced automatically: the event has none, the screen asks for one, and it isn't arranged (D72). The migration made each event's first live booking, by when it was made, primary. A Requested booking can be primary (the first booking is, and the coordinator may designate one, CS3-25); attendees see only an **approved** primary (D70), so until Venue staff approve it they see the event's own `venue_name` / `room_number` (TC-US24-11; #100 review). Customer clarifications CS3-25 (the coordinator designates the primary) and CS3-23 (after a rejection, the coordinator arranges a replacement); the story owner's default, 31 Oct |
| D69 | How is one booking changed or cancelled (US24 AC 5)? | Withdraw it, then request again if needed, for Requested and Approved bookings alike: from PR 2 `withdraw` also accepts an Approved booking (frees the window, tells Venue staff). No edit route. The event's other bookings are never touched. Withdrawing every booking when the event is cancelled is US9's (SCRUM-12, D60). The story owner's default, 31 Oct, after review **Done in US9 PR 2 (SCRUM-12).** |
| D70 | Where do attendees' venue details come from once an event has several venues (US24 AC 4)? | From PR 2, the event's **approved primary** booking: `venue_name` is the venue's name, an in-person event's `joining_info` its location; the API field names don't change. With no approved primary, the event's own `venue_name` / `room_number` (which nothing writes; only the seed set them). No data migration of those columns, since free text can't be matched to a venue, window and allocation; the seed gives its in-person events primary bookings (`EventSpec.venue_slug`). A follow-up technical task drops the columns once every event has a primary booking. Customer clarification CS3-25; the story owner's default, 31 Oct |
| D71 | What does the Organiser see of an event's venues (US24 AC 4)? | From PR 2, read access to `GET /api/v1/events/{id}/venue-bookings` for the event's creator, from `approved` on: every booking with venue, purpose, window, allocation, status, primary flag and reference; `unavailability` (a rejection's reason and alternative, or an inactive venue); `next_action` (`venue_staff_to_decide`, `coordinator_to_rebook`, `none`, and `choose_primary` for the event when it has none). Read-only. The story owner's default, 31 Oct, after review |
| D72 | Which bookings are "required", and when are an event's venues "arranged" (US24 AC 7)? | Every live booking is required (no optional flag). Arranged: an online event, or one with at least one live booking, every live booking Approved, exactly one of them primary, and their allocations adding up to at least the event's expected attendance (D67). Preparation (D73) doesn't count. Withdrawn and rejected bookings don't count. `venues_arranged()` from PR 2, for US18 (SCRUM-85) to use. The story owner's default, 31 Oct |
| D73 | How is a venue booking's preparation tracked (US24 AC 7)? | Per venue (CS3-49: "venue preparation progress is tracked per venue"): `venue_bookings.preparation_status`, `not_started`, `in_progress` or `ready` (`venue_bookings_preparation_status_known`; not null, default `not_started`, existing bookings backfilled `not_started`). Venue staff set it on an **approved** booking: an endpoint in PR 2, a control on their screens in PR 3. The coordinator and the Organiser see it beside each booking's approval status. It isn't part of "arranged" (D72), which AC 7 ties to approval. The seed's demo main hall is `in_progress`. Customer clarification CS3-49 |
| D74 | What does releasing a reservation do (US27 AC 5)? | Deletes it: no history is kept. It's the simplest option, and US5's sum of reservations stays as it is; keeping a history would need a `released_at` column that the check skips. So `equipment_reservations` has no release columns (SCRUM-130). Approved 31 Oct |
| D75 | How is a reservation "released if the event is cancelled" (US27 AC 4) when nothing cancels an event yet? | Until US9 (SCRUM-12) builds cancellation, a reservation whose event is `cancelled` stops counting, in US5's check and when reserving, and its line reads as released (`released_because_event_cancelled`, SCRUM-131). When US9 cancels an event it deletes the event's reservations in the same transaction (Nic asked on SCRUM-12, 31 Oct). Approved 31 Oct **Done in US9 PR 2 (SCRUM-12):** cancelling deletes the event's reservations in the same transaction (TC-US9-18). |
| D76 | Which events can have equipment reserved (US27)? | `planning` or `confirmed`, as for adding US26's lines (TC-US26-10); anything else is `409 EVENT_NOT_ELIGIBLE` (SCRUM-131). Approved 31 Oct |
| D77 | What happens to an approved booking's decision when it's withdrawn (US24 AC 5, D69)? | It's kept: `decided_at` and `decided_by_user_id` stay, so the record shows who approved it before it was withdrawn. `venue_bookings_decided_consistent` was relaxed to match (migration `20261105_1200_us24_bookings_api`): approved and rejected bookings need a decision time, a requested one has none, a withdrawn one may have either. The downgrade refuses while a withdrawn booking has a decision. The story owner's choice, 31 Oct |
| D78 | Where do Venue staff set a booking's preparation status (US24 AC 7, D73)? | In the availability calendar (US21): opening an approved booking's details gives Venue staff a Preparation control (Not started, In progress, Ready) that calls `POST /api/v1/venue-bookings/{id}/preparation`; coordinators and Leads see the status read-only there, and the coordinator's panel and the Organiser's view show it too. No other screen lists Venue staff the approved bookings, so the calendar's bookings now carry `preparation_status` (deviation 55). The story owner's choice, 31 Oct |
| D79 | How are Tech support staff assignments, and their log, kept (US14 AC 3, 5, 6)? | One table, `tech_staff_assignments`: a row per assignment, active until it has an unassign stamp (who and when, set together), at most one active row per person per event. The rows are the log, so nothing is ever deleted, and reassigning is an unassign then an assign, so both are logged (SCRUM-133). **Decided by the acting PO, Matthew, on 31 Oct** (team channel), with US14's other readings, which SCRUM-134 and 135 record |
| D80 | What is an "approved technical support request" (US14 AC 1)? | At least one **approved equipment line** (US26) on the event, and the event in `planning` or `confirmed`; no new kind of request. Otherwise the list says `eligible: false` with nobody available, and assigning is `409 NO_APPROVED_TECH_REQUEST` (SCRUM-134). **Decided by the acting PO, Matthew, on 31 Oct** (team channel) |
| D81 | What is the event's delivery window, for overlapping events (US14 AC 2)? | The event's own `start_at` to `end_at`, with no venue setup or turnaround, as for equipment (US5 AC 6); back-to-back events don't overlap. Only active assignments count (SCRUM-134), and none on a cancelled event: as for equipment (D75), its staff are free for overlapping events (decided by the acting PO, Matthew, on 1 Nov, on #105's question). Nothing cancels an event yet (US9). **Decided by the acting PO, Matthew, on 31 Oct** (team channel) US9 (SCRUM-12) keeps the assignments when it cancels (the story owner's choice), relying on this. |
| D82 | What does the assignment notification say (US14 AC 4)? | The event's name and times; the venue attendees see (D70: the approved primary venue's name and location, else the event's own `venue_name` and `room_number`); and the technical requirements, the event's approved equipment lines (quantity and type) plus its `equipment_needs` (SCRUM-134). **Decided by the acting PO, Matthew, on 31 Oct** (team channel) |
| D83 | Where does the coordinator assign Tech support staff (US14)? | On their existing Equipment screen (US26), in a **Technical support** section under the picked event's equipment, rather than a new screen (SCRUM-135). **Decided by the acting PO, Matthew, on 31 Oct** (team channel) |
| D86 | What can be confirmed, and what is "ready" (US18)? | **Status:** `approved` or `planning` (AC 5 refuses Cancelled, Rejected and already Confirmed; anything earlier or later is `CONFIRMATION_NOT_ALLOWED` too). Planning alone, as the lifecycle says, would make confirming unreachable, because D53 leaves approval at `approved` and nothing moves an event to `planning`. **Ready:** the **venues are arranged** as D72 defines it (an online event, or every live booking approved, exactly one primary, allocations holding the expected attendance), shown as one item per live booking plus the primary and allocation items; **every equipment line that isn't rejected is approved and reserved** (none requested is fine); **technical support** is assigned (at least one active `tech_staff_assignments` row) when the event has an approved equipment line (D80), otherwise not needed; **the Safety Officer's approval** is recorded. Rejected and withdrawn bookings and rejected lines are ignored. **Effect:** `confirmed`, `confirmed_at` and `confirmed_by_user_id` set, the event's `start_at`, `end_at`, `capacity` (expected attendance) and `delivery_mode` (in person) filled from its approved bookings where empty, and the organiser told. There is no override. The bookings and lines are locked with the event so a Venue staff decision can't land mid-confirm. `app/event/confirmation_service.py`. **Confirm with the team** |
| D87 | Which event fields are critical (US12 AC 3)? | Start time, end time, capacity, expected attendance and delivery mode: the schedule, the event's size and its format, which other people (attendees, venue, equipment) plan around. Everything else editable is non-critical: name, category, purpose, room layout, accessibility needs, equipment needs, join link. The venue isn't edited here; US22 books it. **The story owner's choice, 30 Oct; the ticket doesn't list them.** `CRITICAL_FIELDS` in `app/event/edit_service.py`, `DECISION-PENDING` |
| D88 | What happens to a save that changes both critical and non-critical fields? | The whole edit goes for approval: the change request lists every changed field, and the event keeps every previous value (AC 3 read literally). Saving the non-critical half straight away was the other option. **The story owner's choice, 30 Oct.** `app/event/edit_service.py`, `DECISION-PENDING` |
| D89 | Who approves an event change request, and is a critical save logged? | A save with a critical field (D87) creates a change request, and the event keeps its values until it's decided. It's decided per D102: the event's assigned coordinator, or a Coordinator Lead for a coordinator's own edit (SCRUM-142, SCRUM-144). The save is a successful save, so AC 5 logs it field by field, tied to its request (`change_request_id`) and shown as Pending approval in History until it's decided; from SCRUM-141 the decision is stored on the request and History entries carry an `action`. `app/event/edit_service.py`. **Settled by D102, 3 Nov.** |
| D90 | Which fields may an Organiser ask to change (US29a AC 1)? | By stage. Submitted to Approved: the preferred dates, start time and end time. Planning onwards: the event's own `start_at` and `end_at` (+08:00, D9), since preferences no longer place it. At every stage: name, category, purpose, expected attendance, room layout, accessibility needs, equipment needs. AC 1's "venue requirements" are the room layout and accessibility needs; the venue itself is booked by the coordinator (US22). Capacity and delivery mode are the coordinator's (US12, D87). **The story owner's choice, 1 Nov.** `app/event/change_request_service.py`, `DECISION-PENDING` |
| D91 | Who is told about an Organiser's change request when no coordinator is assigned (US29a AC 5)? | Every active Coordinator Lead, as when a request joins the queue (D28): a Submitted event has no coordinator until a Lead assigns one (D27), and someone must hear. The assigned coordinator otherwise. **The story owner's choice, 1 Nov.** `app/event/change_request_service.py`, `DECISION-PENDING` |
| D92 | How is an event's safety state held, and when is it in the Safety Officer's queue (US30a)? | **State:** `approved` when `events.safety_approved_at` is set; `rejected` when the latest `safety_reviews` row is a rejection the coordinator hasn't sent back; otherwise `pending` (never reviewed, or sent back). Sending back is `events.safety_review_requested_at`, at or after the rejection. **Queue:** `approved` or `planning` events, not yet approved, `pending`, whose venues are arranged (US24's rule, D72) and whose requested equipment is approved and reserved (the same checks as US18's readiness, without technical support, which the coordinator arranges for confirming). **A rejection** records the review and changes nothing else: the event keeps its status, the coordinator is told, and the readiness list's safety item shows the comments. **An approval** sets `safety_approved_at` and `safety_approved_by_user_id`, so US18 can confirm; it is final (nothing revokes it), so an approval still stands if the coordinator adds or swaps a venue afterwards; that is left for US30b. Each review is a row and none is deleted (AC 6). `app/safety/state.py`, `app/safety/service.py`. **Confirm with the team** **Amended by D106** (US29b, SCRUM-98): approving a significant change clears the approval. |
| D93 | Who edits an event's agenda, and when (US15 AC 1)? | The request's own Organiser, while it's `draft` or `planning`; in every other status (`awaiting_clarification` included) it's read-only. Anyone who can read the request (D11) can read its agenda (SCRUM-139). **Decided by the acting PO, Matthew, on 1 Nov** (team channel) |
| D94 | What is the "confirmed event date/time window" a session must fall within (US15 AC 3)? | A `planning` event's `[start_at, end_at]`. A draft has no confirmed times, so D65's window: one of its `preferred_dates`, between `preferred_start_time` and `preferred_end_time`, Singapore time; a draft without them can't take sessions yet. Changing the event's dates doesn't re-check existing sessions (as D65), so the Agenda marks any outside the current window (SCRUM-139, 140). **Decided by the acting PO, Matthew, on 1 Nov** (team channel) |
| D95 | What is a "single-track room schedule" (US15 AC 4)? | Each event is one track: no two of its sessions overlap, by the `event_sessions_no_overlap` exclusion constraint; back-to-back is allowed (SCRUM-138). A track per room, tying a session to one of the event's US24 venue bookings, is a likely follow-up story. **Decided by the acting PO, Matthew, on 1 Nov** (team channel) |
| D96 | What does a session define (US15 AC 2)? | Title, start, end, speaker and type: `presentation`, `workshop`, `panel`, `break` (the AC's examples) or `other` (opening remarks, Q&A). The speaker is required unless it's a break (SCRUM-138). **Decided by the acting PO, Matthew, on 1 Nov** (team channel) |
| D97 | Where is the agenda shown (US15 AC 5)? | On the request's details in the Organiser's existing Event requests screen, the "event overview page", in chronological order (start, then end, then title); not a new screen (SCRUM-140). **Decided by the acting PO, Matthew, on 1 Nov** (team channel) |
| D98 | Can an event be cancelled before it has a date (US9 AC 1)? | Yes: AC 1 allows cancelling once the event is approved, and an Approved event has no date, capacity or delivery mode of its own until US18 takes them from its bookings (D86). So a `cancelled` event needs only its name (AC 6's notices name the event); the lists for events past the request stage (US12's Events, US28's managed events) leave out one cancelled before it had a date. Refusing to cancel an Approved event until it's planned was the other option, but nothing moves an event to Planning (D53). **The story owner's default, 1 Nov**; needs the team's blessing |
| D99 | What does "request changes" do, and who says the changes are done (US30b)? | **Outcome:** a review with `outcome = changes_requested`, `comments` and at least one of `venue`, `layout`, `equipment`, `accessibility`, `other` in `areas` (both required, in the API and a CHECK). It records the review and changes nothing else: the event keeps its status, `safety_approved_at` stays unset, and the venue booking, equipment and technical support stay as they were (the ticket's 13 Oct change: no automatic reset). **State:** `changes_requested` while it is the latest review and `safety_review_requested_at` isn't at or after it; the coordinator's **Mark changes done** (the US30a send-back) sets that, and the event is then `pending` and back in the queue marked sent back. The Safety Officer reviews again, and every earlier review stays in the history (AC 6 of US30a). **Decided** by the acting PO on 1 Nov 2026, in the PR review: an `approved` or `planning` event stays where it is, with the areas marked on the review, as the 13 Oct clarification says (the event stays put until all approvals are done, and nothing is reset); it fits D53 and D92. **Not covered:** nothing checks that the areas were actually changed, since there is no change log (deviation 62). `app/safety/state.py`, `app/safety/service.py` |
| D100 | Which Venue staff are told of a cancellation (US9 AC 6's "assigned Venue Staff")? | Venue staff aren't assigned to events, so every active Venue staff member hears, and only when cancelling released an approved booking, as when an approved booking is withdrawn (D69); a request they hadn't decided just leaves their queue. Telling only whoever decided each booking was the other option. **The story owner's default, 1 Nov** |
| D101 | When does an Approved event start, for refusing a cancellation once it has (US9 AC 7)? | Its own `start_at` once it has one. An Approved request has none (D86), so its earliest **approved** venue booking, which places it (a pending one may never be approved and doesn't expire until US25, so a stale one would refuse a cancel, PR #117 review); with no booking, its **last** preferred date at its preferred start time, Singapore time (D9), since it may be on any of them and has surely started by the last. With neither, it's never "started". The first preferred date was the other option, but it would refuse a cancel for an event booked on a later one (PR review). **The story owner's default, 1 Nov** |
| D102 | Who decides an event change request (US29b AC 1; settles D89)? | The event's **assigned coordinator** decides an Organiser's request (US29a). A coordinator's own US12 critical edit can't be decided by them (D51), so **any active Coordinator Lead** decides it, on the Lead's Event requests screen under **Coordinator edits to approve** (SCRUM-144, extending deviation 71). An unassigned event's requests wait until a Lead assigns it; Leads don't decide Organiser requests. `event_change_requests_decider_not_requester` (SCRUM-141); the routes in SCRUM-142. No one approves their own request (D51); cancelling an event rejects all its pending requests, the coordinator's own included, decided by whoever cancelled it (US9). Built in SCRUM-142. **Decided 3 Nov.** |
| D103 | What is a "significant" change (US29b AC 3)? | Any change to the schedule (`start_at`, `end_at`, the preferred dates and times), attendance (`expected_attendees`, `capacity`), layout (`room_layout_preference`), venue (`accessibility_needs`, `delivery_mode`) or equipment (`equipment_needs`). Name, category, purpose and join link aren't. One significant field makes the request significant. Tech support staff and agenda sessions aren't flagged (the AC doesn't name them). SCRUM-142. Built in SCRUM-142. **Decided 3 Nov.** |
| D104 | What does "flagged for review" store, who sees it, and how is it cleared (US29b AC 3)? | One `event_review_flags` row per affected item: each live venue booking, each equipment line holding a reservation, and one flag for the event's registrations if any are active; schedule changes flag all three, attendance bookings and registrations, layout and accessibility bookings, delivery mode bookings and registrations, equipment needs reservations. One open flag per item; a later change adds its fields. Nothing on the item changes. The event's coordinator sees them and clears each (Mark reviewed, optional note); a flag whose booking was withdrawn or rejected, or whose reservation was released, reads as resolved. Open flags block confirming (a readiness item). Venue staff and Tech support get a log-only notice. Table in SCRUM-141. Built in SCRUM-142. **Decided 3 Nov.** |
| D105 | Which statuses go back to Planning, and what happens to a confirmed event (US29b AC 3)? | A significant change moves a **Confirmed** event back to Planning and clears `confirmed_at` and `confirmed_by_user_id` (in History); Approved stays Approved and Planning stays Planning (both confirmable, D86), with flags; the request stage just takes the values. Approving is refused (`409 CHANGE_NOT_ALLOWED`) in Preparation, Cancelled, Completed and Rejected, where a request can still be rejected. Registration closes until the event is confirmed again (the gate reads status); existing registrations are kept untouched and attendees aren't told. SCRUM-142. Built in SCRUM-142. **Decided 3 Nov.** |
| D106 | How does a significant change use the safety state (US29b AC 6; amends D92)? | Approving a significant change on an event with `safety_approved_at` set clears it and `safety_approved_by_user_id` (in History); the earlier approval stays in `safety_reviews`. `safety_state` then reads `pending`, so US18 can't confirm and Preparation is refused until a new review approves it. The event re-enters the Safety Officer's queue once it has no open review flags. A non-significant change keeps the approval. A cleared approval also ends any `changes_requested` state (US30b, D99): the latest review is the approval, so the event reads `pending`, not `changes_requested`, until it is reviewed again, even if an earlier review asked for changes. SCRUM-142. Built in SCRUM-142. **Decided 3 Nov.** |
| D107 | What if the event changed after the request was made (US29b)? | Approving re-checks every field: if the event's value no longer matches the request's `old_value`, the field isn't open at the event's stage any more (D90), or the proposed value no longer passes US29a's checks, approval is refused with `409 CHANGE_REQUEST_STALE` naming the fields, and nothing is applied. The request can still be rejected with a reason. Two pending requests on one field resolve this way too. SCRUM-142. Built in SCRUM-142. **Decided 3 Nov.** |
| D108 | How long can a tentative hold last, and can it be extended (US25)? | Any expiry from now up to 14 days ahead; no extension. To keep a venue longer, the coordinator confirms it into a request, or Venue staff place a new hold once it lapses. A longer or open-ended hold could block a venue for weeks by mistake. **The story owner's choice, 1 Nov** |
| D109 | When does a hold expire, and when is the 24-hour warning sent (US25 AC 3, 4)? | On read, as waitlist offers (D2): a hold lapses on the next read or change of its venue's bookings, with the same helper pattern (§1a "Lapse on read"). The warning goes once (`hold_warned_at`) on the first read inside the last 24 hours, or at once for a hold placed with less than 24 hours left; it can arrive late if nobody looks. A scheduled job was the other option, but the project has none. **The story owner's choice, 1 Nov** **If nothing reads the hold in its last 24 hours there's no warning at all:** the next read finds it lapsed, and the coordinator hears only that it expired (TC-US25-14). |
| D110 | What releases a hold "when the booking is updated" (US25 AC 7)? | The coordinator declining it (for example after choosing another venue), the event being cancelled (US9) and confirming it into a request. Releasing it whenever the event's other bookings change was the other option, but it could drop a hold the coordinator still wants. Rejection can't apply: holds exist only from Approved on. **The story owner's choice, 1 Nov** |
| D111 | What is a hold, in the data (US25)? | A `venue_bookings` row with status `held`, so the existing overlap guard keeps other requests out of its window (AC 2). It blocks but is no booking anywhere else (AC 6): `BLOCKING_STATUSES` for the guard, search and the availability check; `LIVE_BOOKING_STATUSES` for the event's venues, readiness and the primary venue, which a hold can't be. While held, the requester is the Venue staff member who placed it; confirming makes the coordinator the requester, so Venue staff can approve it (D51). A separate holds table was the other option, but the guard can't span two tables. **The story owner's default, 1 Nov** |
| D112 | How do Venue staff pick the event for a hold (US25 AC 1), when they read no event requests (D55)? | `GET /api/v1/venue-holds/events` lists only what a hold needs: each Approved or Planning event's name, reference, status, schedule and expected attendance, by name, and only events with a coordinator, who alone can confirm or decline the hold (D20). Opening Venue staff's access to event requests was the other option, but D55 kept them out. **The story owner's default, 2 Nov** |
| D113 | How is a booking marked "Needs rearrangement" (US23a AC 3)? | By naming the venue block that overlaps it (`venue_bookings.rearrangement_block_id`, with `rearrangement_flagged_at`); its status (requested, approved or held) is untouched. It keeps its window under the overlap guard, so US23b (SCRUM-91) can restore it once the venue is free for the whole occupied window (its AC 5) or mark it replaced (its AC 4), and nothing needs to remember the status it had. A `needs_rearrangement` status, as Jira's subtask names, was the other option: it would lose the original status, take the booking out of the guard, and mean rebuilding the status type and every constraint on it as US25 did. **What reads the marker** (Matt's #131 review), each only for a live booking or hold (`_needs_rearrangement`: `BLOCKING_STATUSES`), so a withdrawn, rejected or expired booking keeps its marker as history but needs nothing: the event's venues (`unavailability.kind: "venue_unavailable"`, `next_action: coordinator_to_rebook`) for the coordinator and the Organiser; `venues_arranged`; US18's readiness list, which names a marked booking as outstanding, so Confirm event is refused (`EVENT_NOT_READY`); confirming a marked hold (`VENUE_UNAVAILABLE`); and Venue staff's approval, refused by the block itself (AC 5). The calendar shows the booking and the block side by side. A Confirmed event can still start Preparation until US23b (SCRUM-91) moves it back to Planning when its venue is marked. **The story owner's choice, 2 Nov** `DECISION-PENDING` |
| D114 | Who is told, and what is "the next action" (US23a AC 4)? | One notice per affected event for its assigned coordinator and one for its organiser (`created_by_user_id`), naming every booking of that event the period hit, so an event with two affected bookings gets one notice each, not two. The coordinator's next action: "Find a replacement venue for the affected booking, or withdraw it." The Organiser's: "Your event's coordinator will arrange a replacement venue. You don't need to do anything yet." An event with no active coordinator or organiser just isn't told that person (logged); its organiser then reads "Your event has no active coordinator yet. A Coordinator Lead assigns one, who then arranges a replacement venue." instead (Matt's #133 review). Attendees are never told here (AC 4). **The story owner's default, 2 Nov** `DECISION-PENDING` |
| D115 | What if a booking is already marked, or the period has started (US23a)? | A booking keeps the first period that marked it, and a later overlapping period neither re-marks it nor notifies again, since its people already know it needs rearranging; the later period's response lists it in `already_affected_bookings`, so Venue staff see it reached it (Matt's #133 review). A booking already over isn't marked. A period may start in the past (equipment can fail mid-day) but must not have ended. Periods can't be edited or deleted yet; nothing in AC 1 to 6 asks for it, and US23b's restore (its AC 5) will need to decide how a period ends early. **The story owner's default, 2 Nov** `DECISION-PENDING` |
| D102 | Who decides an event change request (US29b AC 1; settles D89)? | The event's **assigned coordinator** decides an Organiser's request (US29a). A coordinator's own US12 critical edit can't be decided by them (D51), so **any active Coordinator Lead** decides it, through the API only for now (no Lead screen in US29b; a follow-up ticket adds it). An unassigned event's requests wait until a Lead assigns it; Leads don't decide Organiser requests. `event_change_requests_decider_not_requester` (SCRUM-141); the routes in SCRUM-142. No one approves their own request (D51); cancelling an event rejects all its pending requests, the coordinator's own included, decided by whoever cancelled it (US9). **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D103 | What is a "significant" change (US29b AC 3)? | Any change to the schedule (`start_at`, `end_at`, the preferred dates and times), attendance (`expected_attendees`, `capacity`), layout (`room_layout_preference`), venue (`accessibility_needs`, `delivery_mode`) or equipment (`equipment_needs`). Name, category, purpose and join link aren't. One significant field makes the request significant. Tech support staff and agenda sessions aren't flagged (the AC doesn't name them). SCRUM-142. **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D104 | What does "flagged for review" store, who sees it, and how is it cleared (US29b AC 3)? | One `event_review_flags` row per affected item: each live venue booking, each equipment line holding a reservation, and one flag for the event's registrations if any are active; schedule changes flag all three, attendance bookings and registrations, layout and accessibility bookings, delivery mode bookings and registrations, equipment needs reservations. One open flag per item; a later change adds its fields. Nothing on the item changes. The event's coordinator sees them and clears each (Mark reviewed, optional note); a flag whose booking was withdrawn or rejected, or whose reservation was released, reads as resolved. Open flags block confirming (a readiness item). Venue staff and Tech support get a log-only notice. Table in SCRUM-141. **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D105 | Which statuses go back to Planning, and what happens to a confirmed event (US29b AC 3)? | A significant change moves a **Confirmed** event back to Planning and clears `confirmed_at` and `confirmed_by_user_id` (in History); Approved stays Approved and Planning stays Planning (both confirmable, D86), with flags; the request stage just takes the values. Approving is refused (`409 CHANGE_NOT_ALLOWED`) in Preparation, Cancelled, Completed and Rejected, where a request can still be rejected. Registration closes until the event is confirmed again (the gate reads status); existing registrations are kept untouched and attendees aren't told. SCRUM-142. **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D106 | How does a significant change use the safety state (US29b AC 6; amends D92)? | Approving a significant change on an event with `safety_approved_at` set clears it and `safety_approved_by_user_id` (in History); the earlier approval stays in `safety_reviews`. `safety_state` then reads `pending`, so US18 can't confirm and Preparation is refused until a new review approves it. The event re-enters the Safety Officer's queue once it has no open review flags. A non-significant change keeps the approval. A cleared approval also ends any `changes_requested` state (US30b, D99): the latest review is the approval, so the event reads `pending`, not `changes_requested`, until it is reviewed again, even if an earlier review asked for changes. SCRUM-142. **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D107 | What if the event changed after the request was made (US29b)? | Approving re-checks every field: if the event's value no longer matches the request's `old_value`, the field isn't open at the event's stage any more (D90), or the proposed value no longer passes US29a's checks, approval is refused with `409 CHANGE_REQUEST_STALE` naming the fields, and nothing is applied. The request can still be rejected with a reason. Two pending requests on one field resolve this way too. SCRUM-142. **The story owner's default, asked of the acting PO on 1 Nov.** `DECISION-PENDING` |
| D116 | Where are notifications written, and what do they hold (US31)? | **Written by the notifier**, at the moment a story calls it, so every notice the system already raises is kept without touching the stories (AC 6). Each row holds the user, the kind (the method's name), the event when found, the event name and the sentence, written then. **From its own session, and with no foreign keys:** a waitlist offer is sent inside the withdrawal's transaction, which holds the event's lock, and a foreign key insert waits for it, so the request waited on itself (found by the attendee E2E); the recorder also gives up on a lock after 2 seconds. Users and events are never deleted, so nothing is left dangling. **Best effort:** a failure to record is logged and never undoes what raised the notice, like the log. **Not always after the commit:** most notices are raised after the caller's commit, but a waitlist offer is recorded inside the withdrawal's transaction, so if that transaction rolls back the notification for an offer that never happened stays; accepted, since the offer is rolled back only on an unexpected failure. **Times** are written in Singapore time ("SGT"), as everywhere else (TC-X-01), because the sentence is kept as text. **Decided** by the acting PO on 3 Nov 2026, in the PR review: a notice for an address no user holds is logged and skipped, and a role with no screen for the event gets the notice with no link (D11, D47, D48). **Not decided:** how long notifications are kept. `app/notification/recorder.py` |
| D117 | How is a booking "Replaced" (US23b AC 3, 4)? | A replacement is a new venue request that names the booking it replaces (`replaces_booking_id`) and goes through Venue staff's approval like any other (AC 3). When it is approved, the original's status becomes `replaced` with `replaced_at`: like withdrawn or expired, it no longer holds its window, and it keeps its reference, venue, times, decision and the block that marked it, so the event's history still shows it (AC 4). At most one live replacement per booking, counting every status that holds a window (requested, approved, held: Matt's #134 review), though a replacement is always a request; a rejected or withdrawn one makes way for another (`venue_bookings_one_live_replacement`). **The primary (Chloe's #134 review):** while the original holds the event's primary (`venue_bookings_one_primary_per_event`, D68, not deferrable), the replacement is requested as non-primary; approving it makes the original Replaced first and then the replacement primary, in one transaction, so the event has one primary throughout. Only a booking that needs rearrangement is replaced, so a replaced one always keeps its marker (`venue_bookings_replaced_consistent`). A marker column, as D113 chose for Needs rearrangement, was the other option: every availability check would then need to skip replaced bookings. **What reads the status** (Matt's #134 review): every check on a booking's status names the live set (`BLOCKING_STATUSES` for the overlap guard, search, the availability check, holds, the hold sweep and cancelling; `LIVE_BOOKING_STATUSES` for the primary, `venues_arranged`, US18's readiness, review flags and making primary), so a replaced booking counts as closed everywhere; no check lists the closed statuses instead. On screen, rows use the same live pair, and Replaced has its own label and line. **The story owner's choice, 3 Nov** `DECISION-PENDING` |
| D118 | How does a booking get its venue back (US23b AC 5)? | Venue staff end the block early: `ends_at` moves to when they did (or to its start, if it hadn't begun, leaving an empty block that overlaps nothing), and `scheduled_ends_at` keeps the end it had; search, the availability check and the calendar read `ends_at` as before. Once nothing overlaps the booking's whole occupied window (setup and turnaround included), its coordinator may ask to restore it (`restore_requested_at`, `restore_requested_by_user_id`, only on a marked booking); Venue staff confirm, which checks again and clears the Needs rearrangement marker, or decline, optionally with a reason, which clears the request and records the decline (`restore_declined_at`, `restore_declined_by_user_id`, `restore_decline_reason`) so the coordinator sees it on the event until they ask again (Matt's #134 review). A restore request lives only on a live booking or hold (requested, approved or held); replacing, withdrawing, rejecting, expiring or cancelling it clears the request in the same update (Chloe's #134 review), so PR 2's withdraw, reject, hold sweep and cancellation all clear it. A booking another period still overlaps when one ends early is moved to that period's marker, so it never reads as free while still blocked (Matt's #131 review); the restore checks every period, not only the marker's. Ending a period early tells the coordinator of each booking it alone still marks (`venue_period_ended`), so they know to ask. Whatever closes a booking (replacing, withdrawing, rejecting, a hold's expiry, cancelling) clears its restore request in the same update (`clear_restore_request`). This revisits D115's "no edit or delete". **The story owner's choice, 3 Nov** `DECISION-PENDING` |
| D120 | When can an event be marked Completed (core feature "Event Status Management")? | `POST /api/v1/event-requests/{id}/completion` by the assigned coordinator, only from `preparation` and only once `end_at <= now` (`409 COMPLETION_NOT_ALLOWED` / `409 EVENT_NOT_ENDED`). Completed is terminal. **DECISION-PENDING:** confirm with the customer whether staff or a scheduled job should complete events. |
| D121 | How does an event made in the app open for attendee registration (core feature "Attendee Registration")? | Confirming an event whose request said `registration_required = true` sets `registration_enabled`, opens the window at confirmation and closes it at `start_at`; a window the event already holds is kept. `false`/unset stays closed. **DECISION-PENDING:** confirm the window with the customer. |
| D122 | Are attendees told about their own registration changes (core feature "Notification System")? | Yes: `Notifier.registration_changed` (`registered` / `withdrawn`), after the commit and best effort; recorded in the inbox (US31). |
 
### Environment
 
- **Supabase can lag `main`.** Check before blaming the code: `alembic current` against Supabase versus `alembic heads` in the repo. A missing table usually means an unapplied migration, not a bug.
- **Row Level Security is on for every application table, with no policies** (migration `5733a3c705f7`; TC-SEC-05 fails on any `public` table without it, so a new table's migration must turn it on). `safety_reviews` reached Supabase without it, fixed by `20261114_1200_us30a_rls`. RLS on plus no policies means Supabase's anon and authenticated roles can read nothing; the backend is unaffected because it connects as the tables' owner, and owners bypass RLS. Keep the Data API disabled anyway — belt and braces. **It was found enabled on 25 Oct** and turned off (SCRUM-117): the publishable key could read and write `alembic_version`, the one `public` table without RLS, and call `next_venue_booking_reference()`. SCRUM-118 adds a second layer (migration `20261106_1200_scrum118_grants`), so turning it back on doesn't reopen that: RLS on `alembic_version`; `next_venue_booking_reference()` closed to `PUBLIC`, with a fixed `search_path = public`; and, where the roles exist (Supabase only, not local Docker or CI), no `anon` or `authenticated` privileges on that function or on `attendance_log_id_seq`, `event_request_reference_seq` and `venue_booking_reference_seq`. Tests: TC-SEC-01 to 03 and the `search_path` half of TC-SEC-04 in `backend/tests/core/test_supabase_grants.py`; TC-SEC-04's Security Advisor check is manual, on Supabase, after it's applied. **Adding a table means enabling RLS on it in the same migration; a new function or sequence the app owns needs the same revokes** (SCRUM-118). Policies are needed only if the Data API is ever enabled (§9).
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
3. **US10a before US10e and US17.** US10a's schema PR added the Lead role and seeded two Leads; the queue/assign API is in and the screens too (assigning moves the request to `under_review`, D27). US10b to d and US19 are in. US10e (SCRUM-83) is in: it writes a `reassignment` row in the same transaction as the change, and its button is in US19's request view.
   **US17 (SCRUM-84) is in:** the assigned coordinator approves or rejects a request under review (D53). **US18 (SCRUM-85) is in:** the assigned coordinator confirms a ready event and starts Preparation (D86); **US30a (SCRUM-99) is in:** the Safety Officer reviews and approves, which is what lets an event be confirmed (D92); **US30b (SCRUM-100) is in:** the Safety Officer can request changes instead, and the coordinator marks them done (D99).
4. ~~**Waitlist gap (D3):** an email-only waitlist entry can't accept an offer, because there's no attendee to match.~~ **Resolved by SCRUM-136:** joining requires login, so every new entry has an attendee, and an old email-only entry is linked to its attendee when they try to join (D3, D7 settled; D6 unchanged).
5. **Smaller, worth doing:** fill in the root README's TODO team list and board link; lock the backend's dependencies; review the Dependabot PRs; make the notification log visible under uvicorn; delete merged branches; turn on branch protection for `main`.

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

Migration `20261026_1200_us10d_history` (plus SCRUM-83's `reason`, below):

```sql
create type assignment_kind as enum ('assignment', 'reassignment');
create table coordinator_assignments (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  assigned_by_user_id uuid not null references users(id),   -- the Lead
  coordinator_id uuid not null references users(id),
  kind assignment_kind not null,
  reason text,                                              -- SCRUM-83: required on a reassignment, null on an assignment
  created_at timestamptz not null default now(),
  constraint coordinator_assignments_reassignment_has_reason
    check (kind::text <> 'reassignment' or (reason is not null and btrim(reason) <> ''))
);
create index ix_coordinator_assignments_event_id on coordinator_assignments (event_id);
alter table coordinator_assignments enable row level security;
```

- Append-only: one row per assignment, written in the same transaction as the change to `events.coordinator_id`, so a refused or rolled-back assignment leaves none (AC 1).
- US10a writes `assignment` (no reason); US10e (SCRUM-83) writes `reassignment` with the Lead's reason. Migration `20261030_1200_us10e_reassign` adds the nullable `reason` column and the CHECK, and its downgrade refuses while any reason exists.
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

### `events` — US17 decision (SCRUM-84)

Migration `20261029_1200_us17_decisions`:

```sql
alter table events
  add column decided_at         timestamptz,                -- when the coordinator approved or rejected (AC 5)
  add column decided_by_user_id uuid references users(id),  -- who (AC 5)
  add column rejection_reason   text,                       -- the service requires it on every rejection (AC 3)
  add constraint events_rejection_reason_only_when_rejected
    check (status::text = 'rejected' or rejection_reason is null),
  add constraint events_decider_not_creator  -- D51
    check (decided_by_user_id is null or created_by_user_id is null or decided_by_user_id <> created_by_user_id);
```

Not backfilled: events approved or rejected before US17 (the seed, tests) have no decision. The CHECK compares `status::text`, as `events_final_fields_required` does, because the tests build the schema in one transaction and Postgres refuses a just-added enum value there.

### `events` — US18 confirmation (SCRUM-85)

Migration `20261109_1200_us18_confirm`:

```sql
alter type event_status add value 'preparation' after 'confirmed';  -- after Confirmed (customer session 3)
alter table events
  add column safety_approved_at         timestamptz,                -- the Safety Officer's approval (US30a will write it)
  add column safety_approved_by_user_id uuid references users(id),
  add column confirmed_at               timestamptz,                -- when the coordinator confirmed (AC 3)
  add column confirmed_by_user_id       uuid references users(id),
  add constraint events_safety_approval_consistent                  -- both or neither
    check ((safety_approved_at is null) = (safety_approved_by_user_id is null));
```

Not backfilled: events confirmed before US18 (the seed, tests) have neither. `preparation` can't be dropped from the type once added, so the downgrade keeps it and refuses while any event is in Preparation, confirmed through US18 or safety-approved. `events_final_fields_required` already demands a name, dates, capacity and delivery mode of every event past the request stage, which is why confirming fills them (D86).

### `safety_reviews` — US30a safety reviews (SCRUM-99)

Migration `20261110_1200_us30a_safety`:

```sql
create table safety_reviews (
  id             uuid primary key default gen_random_uuid(),
  event_id       uuid not null references events(id),
  reviewer_id    uuid not null references users(id),
  outcome        text not null,                -- 'approved' | 'rejected'
  checklist      jsonb not null,               -- {item: {"result": "satisfactory" | "issue", "comment": text | null}} for the seven items
  comments       text,                         -- what the coordinator and organiser read
  internal_notes text,                         -- the Safety Officer's own; no other route returns them
  created_at     timestamptz not null default now(),
  constraint safety_reviews_outcome_known check (outcome in ('approved', 'rejected')),
  constraint safety_reviews_rejection_has_comments
    check (outcome <> 'rejected' or (comments is not null and btrim(comments) <> ''))
);
create index ix_safety_reviews_event_id_created_at on safety_reviews (event_id, created_at);
alter table events add column safety_review_requested_at timestamptz;  -- when a rejected arrangement was sent back
alter table safety_reviews enable row level security;  -- migration 20261114_1200_us30a_rls; the first one left it off
```

The seven checklist keys, in order: `attendance_capacity`, `layout`, `emergency_access`, `accessibility`, `equipment_placement`, `crowd_movement`, `venue_restrictions` (`app/safety/models.py`). The API checks them; the database holds the JSON. Rows are never updated or deleted by the app. The downgrade refuses while any review exists.

Migration `20261113_1200_us30b_changes` (US30b, SCRUM-100), after US23a's `20261116_1200_us23a_blocks` and so after the one above:

```sql
alter table safety_reviews add column areas jsonb;   -- 'venue' | 'layout' | 'equipment' | 'accessibility' | 'other', for a request for changes; null otherwise
alter table safety_reviews drop constraint safety_reviews_outcome_known;
alter table safety_reviews add constraint safety_reviews_outcome_known
  check (outcome in ('approved', 'rejected', 'changes_requested'));
alter table safety_reviews add constraint safety_reviews_changes_have_comments_and_areas
  check (outcome <> 'changes_requested'
         or (comments is not null and btrim(comments) <> '' and areas is not null and jsonb_array_length(areas) > 0));
```

`areas` is a real SQL `NULL` for the other outcomes (the column maps with `none_as_null`). The API holds the five area keys (`app/safety/models.py`), in the order the form shows them, each once. The downgrade refuses while any request for changes exists.


### `notifications` — US31 notifications (SCRUM-107)

Migration `20261116_1200_us31_notifications`:

```sql
create table notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,                  -- the recipient; no foreign key (D108)
  kind       text not null,                  -- the Notifier method that raised it, e.g. 'event_confirmed'
  event_id   uuid,                           -- the event it is about, when found; no foreign key (D108)
  event_name text,
  message    text not null,                  -- the sentence the user reads, written when it was raised
  created_at timestamptz not null default now(),
  read_at    timestamptz,                    -- null = unread
  constraint notifications_kind_and_message_not_blank check (btrim(kind) <> '' and btrim(message) <> '')
);
create index ix_notifications_user_id_created_at on notifications (user_id, created_at desc);
create index ix_notifications_unread on notifications (user_id) where read_at is null;
alter table notifications enable row level security;   -- no policies, like every public table
```

Rows are never updated except to set `read_at` (first read kept), and never deleted by the app. The downgrade refuses while any exist.

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
  add column full_name    text;        -- asked at sign-up (AC 6); the seed names every seeded user (SCRUM-119)

-- US16b (SCRUM-119), migration 20261027_1200_us16b_roles: a list of roles replaces `role` (D45)
-- user_role is rebuilt with the same values in the same order, plus 'venue_staff', 'safety_officer'
alter table users add column roles user_role[] not null default '{attendee}';  -- backfilled: [role]
alter table users drop column role;
alter table users add constraint users_roles_not_empty  check (cardinality(roles) > 0);
alter table users add constraint users_roles_no_repeats check (array_has_no_repeats(roles));
```

- **The backfill:** each user's `roles` is their old role as a list of one; `operations_manager` became `venue_staff` (D49). Nobody holds `operations_manager` now, and the app can't give it out.
- **Why the type is rebuilt:** a value added with `ALTER TYPE … ADD VALUE` can't be used until the transaction commits, and the backfill writes `venue_staff` in the same transaction. So the migration creates the full type under a new name, moves the column to it, drops the old type and renames the new one. The values and their order are unchanged, with the two new ones last.
- **Why a function for "no repeats":** a CHECK can't hold a subquery, so `array_has_no_repeats(anyarray)` (SQL, immutable, empty `search_path`) counts the distinct items.
- **Downgrade:** puts `role` back as each user's one role (`venue_staff` → `operations_manager`), and refuses while anyone holds two roles or `safety_officer`, which one role can't keep. `venue_staff` and `safety_officer` stay in the type.

Existing attendees were backfilled. Anything that creates an attendee (the seed's `upsert_attendee`, the test factory `make_attendee`) must create the `users` row first, with `roles` `[attendee]`. The US16a downgrade refuses while any user is linked or named.

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

### `event_change_requests` and `event_audit_entries` — US12 event edits (SCRUM-15)

Migration `20261108_1200_us12_event_edits`:

```sql
create type change_request_status as enum ('pending_approval', 'approved', 'rejected');
create table event_change_requests (           -- AC 3: a critical edit, held; the event keeps its values
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  requested_by_user_id uuid not null references users(id),
  status change_request_status not null default 'pending_approval',
  changes jsonb not null,                       -- [{"field", "old_value", "new_value"}, ...], at least one
  reason text,                                  -- US29a (SCRUM-97): the organiser's reason; null on a US12 edit
  created_at timestamptz not null default now(),
  constraint event_change_requests_reason_not_blank check (reason is null or btrim(reason) <> ''),
  constraint event_change_requests_changes_not_empty
    check (jsonb_typeof(changes) = 'array' and jsonb_array_length(changes) >= 1)
);
create table event_audit_entries (              -- AC 5: one row per field of every successful save
  id uuid primary key default gen_random_uuid(),
  seq bigint generated always as identity,      -- orders the rows of one save
  event_id uuid not null references events(id),
  user_id uuid not null references users(id),
  field_name text not null,
  previous_value jsonb,                         -- the API's JSON form; null = empty
  new_value jsonb,
  change_request_id uuid references event_change_requests(id),  -- set on a critical edit (D89)
  created_at timestamptz not null default now()
);
-- indexed on event_id; RLS on both
```

- Append-only: the service writes both in the edit's transaction and never updates an audit row. A refused save writes neither (AC 4).
- Only `pending_approval` was written until US29b (SCRUM-98), which records each decision on the request (below).
- **US29a (SCRUM-97)** adds `reason` (migration `20261110_1200_us29a_change_reqs`): an organiser's request carries one, required by the service; a coordinator's US12 edit has none. Its downgrade refuses while any reason exists.
- Downgrade drops both and the type, and refuses while any row exists.

### `event_cancellations` — US9 cancel an event (SCRUM-12)

Migration `20261112_1200_us9_cancellations`:

```sql
create type cancellation_status as enum ('pending', 'approved', 'rejected');
create table event_cancellations (              -- AC 8: who asked, why, when; who decided, when
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  requested_by_user_id uuid not null references users(id),
  reason text not null,                         -- AC 1, 3: required, not blank, at most 1,000 characters
  status cancellation_status not null default 'pending',
  requested_at timestamptz not null default now(),
  decided_by_user_id uuid references users(id),
  decided_at timestamptz,
  rejection_reason text,                        -- the coordinator's, when rejecting; required then and only then
  direct boolean not null default false,        -- AC 3: the coordinator cancelled it themselves
  constraint event_cancellations_reason_not_blank check (btrim(reason) <> '' and char_length(reason) <= 1000),
  constraint event_cancellations_decided_consistent
    check ((status = 'pending') = (decided_at is null) and (decided_at is null) = (decided_by_user_id is null)
           and (decided_at is null or decided_at >= requested_at)),
  constraint event_cancellations_rejection_reason_only_when_rejected
    check ((status = 'rejected') = (rejection_reason is not null)
           and (rejection_reason is null or (btrim(rejection_reason) <> '' and char_length(rejection_reason) <= 1000))),
  constraint event_cancellations_direct_consistent
    check ((not direct or status = 'approved')
           and (decided_by_user_id is null or direct = (decided_by_user_id = requested_by_user_id)))
);
create unique index event_cancellations_one_open on event_cancellations (event_id)
  where status in ('pending', 'approved');     -- one waiting request, or the cancellation itself
-- indexed on event_id; RLS on
```

- An organiser's request is `pending` until the assigned coordinator approves or rejects it (AC 1, 2). A coordinator's direct cancel (AC 3) is one `approved`, `direct` row with the coordinator as requester and decider, at the same instant. `direct` is true exactly when the decider is the requester, so a request decided by someone else (D51) is never direct.
- `requested_at` defaults to the database clock for hand-written rows; the service always sets it from the same injected clock as `decided_at`, so `decided_at >= requested_at` holds under a frozen test clock.
- **Consistency:** nothing in the schema ties an `approved` row to `events.status = 'cancelled'`; the service changes both in one transaction (PR 2), and PR 2's tests check every cancelled event has exactly one approved row. The seed has no cancelled events.
- **One open row per event:** no second request while one waits, none after the event is cancelled (AC 4), and cancelling must decide a waiting request rather than leave it open beside the cancellation.
- The same migration lets a `cancelled` event go without its date, capacity and delivery mode, but not its name (`events_final_fields_required`), because an Approved event can be cancelled before it has them (D98). The coordinator's Events list and the managed-events list (US12, US28) leave such an event out, and opening it there is `404`: it never reached Planning.
- Downgrade refuses while any row exists, or while a cancelled event lacks its final fields.

### Change request decisions and `event_review_flags` — US29b (SCRUM-98, PR 1 SCRUM-141)

Migration `20261115_1200_us29b_decisions` (the name `…_us29b_change_decisions` is over Alembic's 32-character version limit):

```sql
alter table event_change_requests
  add column decided_at         timestamptz,                -- AC 2, 5: when it was approved or rejected
  add column decided_by_user_id uuid references users(id),  -- who (D102)
  add column rejection_reason   text,                       -- AC 2: the service requires it on every rejection
  add constraint event_change_requests_decision_consistent
    check ((status::text = 'pending_approval') = (decided_at is null) and (decided_at is null) = (decided_by_user_id is null)),
  add constraint event_change_requests_rejection_reason_only_when_rejected
    check ((status::text = 'rejected') = (rejection_reason is not null)),
  add constraint event_change_requests_rejection_reason_not_blank
    check (rejection_reason is null or btrim(rejection_reason) <> ''),
  add constraint event_change_requests_decider_not_requester    -- D51, D102: approvals only (US9 cancels reject)
    check (status::text <> 'approved' or decided_by_user_id <> requested_by_user_id);
-- before the CHECKs: a cancelled event's rejected requests with no decision (US9, #117) take the approved
-- cancellation's decided_at and decided_by_user_id, with the reason 'The event was cancelled.'
create index ix_event_change_requests_pending on event_change_requests (event_id) where status = 'pending_approval';

alter table event_audit_entries
  add column action text not null default 'saved',          -- AC 5: what each History entry is
  add constraint event_audit_entries_action_known check (action in ('saved', 'requested', 'applied', 'decided',
    'status_changed', 'confirmation_cleared', 'safety_approval_cleared'));
-- backfill: entries tied to a change request are 'requested' (a critical save still waiting, D89)

create table event_review_flags (                           -- AC 3, D104
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id),
  change_request_id uuid not null references event_change_requests(id),  -- the change that raised it
  kind text not null,                                       -- 'venue_booking' | 'equipment_reservation' | 'registrations'
  venue_booking_id uuid references venue_bookings(id),
  equipment_request_line_id uuid references equipment_request_lines(id), -- the line: releasing deletes a reservation (D74)
  fields text[] not null,                                   -- the changed fields that affected it
  raised_at timestamptz not null default now(),
  cleared_at timestamptz, cleared_by_user_id uuid references users(id), cleared_note text,
  constraint event_review_flags_kind_known check (kind in ('venue_booking', 'equipment_reservation', 'registrations')),
  constraint event_review_flags_target_matches_kind check ((venue_booking_id is not null) = (kind = 'venue_booking')
    and (equipment_request_line_id is not null) = (kind = 'equipment_reservation')),
  constraint event_review_flags_fields_not_empty check (cardinality(fields) > 0),
  constraint event_review_flags_clearance_consistent check ((cleared_at is null) = (cleared_by_user_id is null)),
  constraint event_review_flags_note_only_when_cleared
    check (cleared_note is null or (cleared_at is not null and btrim(cleared_note) <> ''))
);
-- one open flag per item: unique partial indexes event_review_flags_one_open_per_booking, _one_open_per_line,
-- _one_open_registrations (event_id, kind = 'registrations'); ix_event_review_flags_event_id; RLS on
```

- **Decisions:** written only by SCRUM-142's service; the CHECKs back it up. `rejection_reason` follows US17's name on `events`.
- **History:** a US12 critical save writes `requested` entries when it's made. US12's held edits now write `requested` (Calvin's #121 review), enforced by `event_audit_entries_request_entry_not_saved`; approving any request writes `applied` entries for what changed and a `decided` entry, plus `status_changed`, `confirmation_cleared` and `safety_approval_cleared` when a significant change has those effects (D105, D106). A rejection writes only `decided`.
- **Flags** never change the booking, line, reservation or registrations they point at. Each is the coordinator's to clear (D104).
- **Seed:** Change Request Demo (`CHANGE_REQUEST_EVENT`), confirmed and safety-approved (with the approved `safety_reviews` row behind it, by the seeded Safety officer, at `safety_approved_at`), with an approved primary booking, a reserved projector, Terry Ong assigned and one pending organiser request; a reseed deletes its flags, history and other requests and resets the rest. The other demos' resets delete their events' flags first, since flags point at the bookings, lines and change requests they delete.
- **Downgrade** refuses while any flag, decided request, or History entry other than `saved` / `requested` exists.

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
- Events keep their free-text `venue_name` and `room_number`; since US24 PR 2 (D70) attendees see an event's approved primary venue instead, and these are the fallback.
- The seed adds six venues with varied capacity, tags and buffers: one with 0/0 buffers, and one inactive (`SOE Seminar Room B1-1`, which no seeded event uses).
- Downgrade refuses if any venue exists.
- PR 2 added the API (§3, Venues) and screens with no migration. Writes need Venue Staff (`venue_staff` since SCRUM-119; `operations_manager` before, D19). Buffer edits are refused while the venue has approved future bookings; since US22 PR 1 that reads `venue_bookings` (below). Test cases and the PR split: `docs/testing/US20-venue-catalogue.md`.

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
- **US16b (SCRUM-120), migration `20261031_1200_us16b_d51_checks`:** `venue_bookings_decider_not_requester` (`decided_by_user_id <> requested_by_user_id`; a pending booking has no decider, and null passes): nobody decides a booking they requested (D51). The other half of D51, the event's current coordinator, spans tables, so `booking_service` checks it. Downgrade drops the CHECK.
- **US24 (SCRUM-127), migration `20261103_1200_us24_multi_venue`:** `purpose text not null default 'Main venue'` with `venue_bookings_purpose_valid` (`purpose = btrim(purpose) AND char_length(purpose) BETWEEN 1 AND 100`, D66), and `is_primary boolean not null default false` with the unique index `venue_bookings_one_primary_per_event` on `(event_id) WHERE is_primary AND status IN ('requested', 'approved')` (D68). The upgrade makes each event's first live booking, by `created_at`, primary. `preparation_status text not null default 'not_started'` with `venue_bookings_preparation_status_known` (`not_started`, `in_progress`, `ready`; D73, CS3-49); existing bookings are `not_started`. Downgrade drops the index, the three columns and both CHECKs, and refuses (`RuntimeError`, as US26's and US5's do) while any booking has a purpose other than "Main venue" or a preparation status other than `not_started`, which would be lost; the primary flag the upgrade works out again (#96 review). Since #94 merged, the migration follows `20261102_1200_us5_check_outcome`.
- **US24 PR 2 (SCRUM-128), migration `20261105_1200_us24_bookings_api`:** drops `purpose`'s default, now that the API asks for it (D66), and relaxes `venue_bookings_decided_consistent` to `(status NOT IN ('approved', 'rejected') OR decided_at IS NOT NULL) AND (status <> 'requested' OR decided_at IS NULL)`, so a withdrawn booking keeps its decision (D77). Downgrade refuses while a withdrawn booking has one, then restores the strict CHECK and the default. Since #98 merged, the migration follows US27's `20261104_1200_us27_reservations`. Existing bookings keep their `expected_attendees` as their allocation (D67).

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
- **US25 (SCRUM-93), migration `20261115_1200_us25_holds`:** `venue_booking_status` gains `held` and `expired` (the type is rebuilt, as US16b's roles were, because a value added with `ADD VALUE` can't be used until the transaction commits); `hold_expires_at timestamptz`, `held_by_user_id uuid references users(id)`, `hold_warned_at timestamptz`, `expired_at timestamptz`, all null except on a hold. `venue_bookings_no_overlap` now covers `status in ('requested', 'approved', 'held')` (`BLOCKING_STATUSES`; AC 2), while `LIVE_BOOKING_STATUSES` and the one-primary index keep requested and approved (AC 6: a hold isn't one of the event's venues). A partial index `ix_venue_bookings_hold_expires_at` (where `hold_expires_at is not null`) keeps the lapse-on-read sweep's check for due holds cheap (PR #123 review). New CHECKs: `venue_bookings_hold_consistent` (an expiry exactly when someone placed it, on every held or expired row; a warning only before the expiry; while held, the requester is whoever placed it), `venue_bookings_expired_consistent` (and never before the expiry), `venue_bookings_hold_not_primary`; `venue_bookings_decided_consistent` also keeps held and expired rows undecided. A confirmed hold keeps its expiry and who placed it (AC 5). The app's copies of the guard's rule use `BLOCKING_STATUSES` too, so they agree with it: the availability check (`_booking_conflicts`, which names the hold a request clashes with), US2's search (a held venue isn't free, AC 5's "tentatively held") and the buffer-edit recompute (a future hold is re-measured like a request). The 14-day cap (D108) is the service's, in PR 2. Downgrade refuses while any row has a hold, and rebuilds the old type (D108 to D111).

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
- Since US23a (SCRUM-90) PR 2, Venue staff create them with `POST /api/v1/venues/{id}/blocks` (§3, "Venue unavailability"); there is no edit or delete yet; since US23b (SCRUM-91) they can be ended early (D118). The seed adds one.
- **US23a (SCRUM-90) PR 1, migration `20261116_1200_us23a_blocks`:** `reason text not null` with `venue_blocks_reason_known` (`maintenance`, `equipment_failure`, `renovation`, `safety`, `other`: AC 1's list, `VenueBlockReason` in `app/venue/models.py`, which names the migration's copy); existing blocks are backfilled `other`, then the default is dropped so every new block names one. `created_by_user_id uuid references users(id)`, null for blocks made before US23a. `note` stays, for detail beyond the reason. On `venue_bookings`, `rearrangement_block_id uuid references venue_blocks(id)` and `rearrangement_flagged_at timestamptz` mark a booking or hold a block overlaps as **Needs rearrangement** (AC 3, D113), set together (`venue_bookings_rearrangement_consistent`), with a partial index `ix_venue_bookings_rearrangement_block_id` for a block's affected bookings. The status is untouched: the booking keeps its window and its place under the overlap guard, so US23b (SCRUM-91) can replace it or restore it. PR 2's `block_service.create` sets the marker. Downgrade refuses while any booking is marked or any block has another reason or a recorder.
- **US23b (SCRUM-91) PR 1, migration `20261117_1200_us23b_replacement`:** `venue_booking_status` gains `replaced` (`ALTER TYPE ... ADD VALUE`, as US10a did; the new CHECK compares `status::text`, so the value needn't be committed first, and downgrade leaves the value in the type, unused). On `venue_bookings`: `replaced_at timestamptz` (`venue_bookings_replaced_consistent`: set exactly when replaced, and a replaced booking keeps its marker; D117), `replaces_booking_id uuid references venue_bookings(id)` (not itself, `venue_bookings_replaces_another`; at most one requested, approved or held replacement per booking, the partial unique index `venue_bookings_one_live_replacement`), and `restore_requested_at timestamptz` with `restore_requested_by_user_id uuid references users(id)`, set together and only on a live (requested, approved or held) booking marked as needing rearrangement (`venue_bookings_restore_consistent`; D118), and Venue staff's last decline, `restore_declined_at` with `restore_declined_by_user_id uuid references users(id)` and an optional `restore_decline_reason text`, set together and the reason only with a decline (`venue_bookings_restore_decline_consistent`). `BLOCKING_STATUSES` and `LIVE_BOOKING_STATUSES` are unchanged, so a replaced booking holds no window. On `venue_blocks`: `ended_early_at`, `ended_early_by_user_id uuid references users(id)` and `scheduled_ends_at`, set together with `scheduled_ends_at` after the new `ends_at` (`venue_blocks_ended_early_consistent`); `venue_blocks_window_valid` now also allows `ends_at = starts_at` once ended early, an empty range that overlaps nothing. Downgrade refuses while any booking is replaced, replaces another, or has a restore request or decline, or any block was ended early.
- The seed's US2 slot: five days ahead, 10:00–12:00 Singapore time, SCIS Seminar Room 2-1 has a `requested` booking, Mochtar Riady Auditorium an `approved` one (each for a seeded approved event, requested by the seeded coordinator, D24), and SMU Connexion Studio 3-2 a block (`VENUE_BOOKINGS`, `VENUE_BLOCKS` in `app/seed.py`). The approved booking means **the auditorium's buffers are locked** (deviation 22).
- Downgrade refuses if any block exists.

### `equipment_types` and `equipment_request_lines` — US26 equipment requests (SCRUM-108)

Migration `20261025_1200_us26_equipment`:

```sql
alter type user_role add value if not exists 'tech_support';   -- deviation 34

create table equipment_types (           -- the catalogue (AC 4); US5 adds its stock (below)
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
  check (review_note is null or status <> 'pending'),
  -- equipment_request_lines_reviewer_not_requester (US16b D51, migration 20261031_1200_us16b_d51_checks)
  check (reviewed_by_user_id <> requested_by_user_id)
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

### Equipment stock and `equipment_reservations` — US5 equipment availability (SCRUM-124)

Migration `20261101_1200_us5_equipment` (for the Supabase owner to apply after merge):

```sql
alter table equipment_types
  add column total_quantity          integer not null default 0,   -- owned (D62)
  add column out_of_service_quantity integer not null default 0,   -- damaged, under repair, otherwise unavailable (AC 3, D62)
  add column storage_location        text,                         -- for reference only (AC 7)
  -- equipment_types_stock_in_range: one check, so a negative stock is always refused under this name
  add constraint equipment_types_stock_in_range
    check (out_of_service_quantity >= 0 and out_of_service_quantity <= total_quantity),
  add constraint equipment_types_storage_location_not_blank check (btrim(storage_location) <> '');

create table equipment_reservations (    -- US27 reserves (SCRUM-95); US5 only reads it (AC 2)
  id                uuid primary key default gen_random_uuid(),
  event_id          uuid not null references events(id),
  equipment_type_id uuid not null references equipment_types(id),
  quantity          integer not null check (quantity > 0),   -- equipment_reservations_quantity_positive
  created_at        timestamptz not null default now()
);
create index ix_equipment_reservations_equipment_type_id on equipment_reservations (equipment_type_id);
-- RLS on
```

- **The reservations table comes before US27** because US5's check (SCRUM-125) subtracts other events' reservations (AC 2), which needs somewhere to read them from. Nothing writes it yet. US27 (SCRUM-95) adds the link to the approved line, who reserved and release, in its own migration.
- **Stock is per type (D62) and only the seed records it (D63):** `EQUIPMENT_STOCK` in `app/seed.py` gives each of the eight types a stock, a storage location and, for some, units out of service, small enough that a large request on Equipment Request Demo comes out short (TC-US5-11). A reseed puts the seeded values back. Types added another way own nothing until stock is recorded.
- Downgrade refuses while any reservation exists. Test cases and the PR split: `docs/testing/US5-equipment-availability.md`.

### `equipment_request_lines` — US5's recorded check (SCRUM-125)

Migration `20261102_1200_us5_check_outcome` (for the Supabase owner to apply after merge):

```sql
alter table equipment_request_lines
  add column availability_checked_at         timestamptz,
  add column availability_checked_by_user_id uuid references users(id),
  add column availability_sufficient         boolean,
  add column availability_shortfall          integer,
  -- equipment_request_lines_availability_check_consistent: none, or all four with sufficient = short by 0
  add constraint equipment_request_lines_availability_check_consistent check (
    (availability_checked_at is null and availability_checked_by_user_id is null
       and availability_sufficient is null and availability_shortfall is null)
    or (availability_checked_at is not null and availability_checked_by_user_id is not null
       and availability_sufficient is not null and availability_shortfall is not null  -- a NULL would pass (PR #94 review)
       and ((availability_sufficient and availability_shortfall = 0)
         or (not availability_sufficient and availability_shortfall > 0))));
```

- The latest check only (D64): a newer check replaces it, and editing the line's quantity or type clears it.

### `equipment_reservations` — US27 reserve equipment (SCRUM-130)

Migration `20261104_1200_us27_reservations` (for the Supabase owner to apply after merge; it refuses to run, and to downgrade, while the table has rows):

```sql
alter table equipment_reservations
  add column request_line_id     uuid not null,                     -- the approved line it fulfils (AC 1, 6)
  add column reserved_by_user_id uuid not null references users(id),
  add constraint equipment_reservations_request_line_id_key unique (request_line_id);   -- one per line
alter table equipment_request_lines
  add constraint equipment_request_lines_id_event_type_key unique (id, event_id, equipment_type_id);
alter table equipment_reservations                                  -- its event and type are its line's
  add constraint equipment_reservations_line_fkey foreign key (request_line_id, event_id, equipment_type_id)
    references equipment_request_lines (id, event_id, equipment_type_id);
```

- **Releasing deletes the reservation (D74),** so there are no release columns. The event's times come from the event (AC 1: no venue setup or turnaround). Reserving and releasing are SCRUM-131.
- **The reseed** removes Equipment Request Demo's reservations before its lines, which they point at. Test cases and the PR split: `docs/testing/US27-equipment-reservations.md`.

### `tech_staff_assignments` — US14 assign Tech support staff (SCRUM-133)

Migration `20261107_1200_us14_tech_staff` (for the Supabase owner to apply after merge; the downgrade refuses while the table has rows, which are the log):

```sql
create table tech_staff_assignments (     -- one per assignment; the rows are the log (AC 6, D79)
  id                    uuid primary key default gen_random_uuid(),
  event_id              uuid not null references events(id),
  staff_user_id         uuid not null references users(id),     -- a Tech support user (checked by SCRUM-134)
  assigned_by_user_id   uuid not null references users(id),
  assigned_at           timestamptz not null default now(),
  unassigned_by_user_id uuid references users(id),
  unassigned_at         timestamptz,
  -- tech_staff_assignments_unassigned_consistent: an unassign is both who and when
  check ((unassigned_at is null) = (unassigned_by_user_id is null))
);
create unique index tech_staff_assignments_one_active                   -- one active per person per event
  on tech_staff_assignments (event_id, staff_user_id) where unassigned_at is null;
create index ix_tech_staff_assignments_active_staff                     -- SCRUM-134's availability check
  on tech_staff_assignments (staff_user_id) where unassigned_at is null;
-- RLS on
```

- **The seed** adds a second Tech support user, Priya Nair (`tech.support2@smu.edu.sg`, with a Supabase login), so a coordinator can assign one or more (AC 3), and a reseed clears Equipment Request Demo's assignments with its equipment lines (TC-US14-17 reruns). Its non-local warning names only the equipment lines, as before. Test cases and the PR split: `docs/testing/US14-tech-support-staff.md`.

### `event_sessions` — US15 multi-session agenda (SCRUM-138)

Migration `20261111_1200_us15_sessions` (for the Supabase owner to apply after merge; the downgrade refuses while the table has rows):

```sql
create type event_session_type as enum ('presentation', 'workshop', 'panel', 'break', 'other');  -- D96

create table event_sessions (             -- one per agenda item (AC 2)
  id           uuid primary key default gen_random_uuid(),
  event_id     uuid not null references events(id),
  title        text not null,              -- event_sessions_title_not_blank: btrim(title) <> ''
  session_type event_session_type not null,
  speaker_name text,                       -- event_sessions_speaker_required: unless it's a break (D96)
  starts_at    timestamptz not null,
  ends_at      timestamptz not null,       -- event_sessions_window_valid: ends_at > starts_at
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
-- One track per event (AC 4, D95): '[)', so back-to-back is allowed. Its GiST index also serves lookups by event.
alter table event_sessions add constraint event_sessions_no_overlap
  exclude using gist (event_id with =, tstzrange(starts_at, ends_at, '[)') with &&);
-- RLS on
```

- **The window (AC 3, D94)** is the API's to check (SCRUM-139): a draft's comes from its preferred dates and times, which a table constraint can't read.
- **The seed** adds **Agenda Demo**, a `planning` event owned by the seeded organiser, 09:00 to 17:00 Singapore time 21 days ahead, with registration off. A reseed deletes its sessions (TC-US15-15 reruns), and the non-local warning says so. Test cases and the PR split: `docs/testing/US15-event-agenda.md`.

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
  attendee_id     uuid references attendees(id),   -- null only for email-only waitlist entries made before SCRUM-136, see §6 D3
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

Since US24 PR 2 (D70), `venue_name` and `venue_location` are the event's **approved primary** venue's name and location (`app/venue/primary.py`), else its own `venue_name` and `room_number`; both null for an online event. The registration confirmation's `venue_name` and My events' `venue_name` and in-person `joining_info` follow the same rule. The board's search matches the title, `venue_name` and `venue_location` (TC-US24-19).
 
```json
{
  "events": [{
    "id": "uuid", "name": "Tech Talk: Agile at Scale",
    "start_at": "2026-10-02T14:00:00+08:00", "end_at": "2026-10-02T16:00:00+08:00",
    "delivery_mode": "in_person", "venue_name": "SCIS Seminar Room 2-1",
    "venue_location": "School of Computing and Information Systems, Level 2",
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
 
The logged-in attendee joins (`get_current_attendee`, like `register`; SCRUM-136, D7). No body → `201 {"registration_id", "status": "waitlisted", "position": 4}`. The row stores the attendee's `attendee_id` and their own email; a body sent by an old client is ignored.

Joinable only when `registration_service.waitlist_available` holds: no seats left (an unexpired offer holds its seat) **and** `waitlist_enabled`. Checked in this order:

| Outcome | Status | Body |
|---|---|---|
| No login | `401` | `{"code": "UNAUTHENTICATED"}`, before the event is looked up |
| Joined | `201` | as above; `position` is the confirmation (US6a AC 3) |
| Unknown event | `404` | `{"code": "NOT_FOUND"}` |
| Not confirmed / registration disabled | `403` | `{"code": "REGISTRATION_NOT_ENABLED"}` (D16) |
| Outside registration window | `403` | `{"code": "REGISTRATION_CLOSED"}` (D16) |
| The attendee already has an active row | `409` | `{"code": "ALREADY_REGISTERED"}`. An email-only row with their email (from before SCRUM-136) is first linked to them, so it can accept an offer |
| Event's waitlist is off | `409` | `{"code": "WAITLIST_NOT_ENABLED"}` (deviation 16) |
| Places remain | `409` | `{"code": "SEATS_AVAILABLE"}` (deviation 16) |

No registration row and no `attendance_log` row on any refusal.

The board's join button (SCRUM-52) calls this with the attendee's identity, as register does (`apiClient` identity `"attendee"`); nothing is typed (SCRUM-136).
 
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
  "offered": [{ "...": "same fields", "offer_expires_at": "2026-10-02T01:00:00Z" }],
  "expired": [{ "...": "same fields", "offer_expires_at": "2026-10-01T01:00:00Z" }]
}
```

`offered` (SCRUM-50, deviation 15) lists places held for the attendee after someone withdrew, until `offer_expires_at`; accept with `POST /registrations/{registration_id}/accept`. A lapsed offer isn't listed, since it can no longer be accepted.

`expired` (SCRUM-137, additive) lists the attendee's offers that lapsed, on events that haven't ended, with `offer_expires_at` as when the offer ended; an event where the attendee has an active row again is left out. My events shows them muted, under **Offer expired**, with nothing to press (TC-US7-22). Reading this list first expires lapsed offers on the attendee's events (D2).
 
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
 
### `POST /registrations/{registration_id}/expire-offer` — SCRUM-37 (test-only)

A forced expiry, kept for tests: it expires the offer whatever the time, appends to `attendance_log`, and offers the seat to the next waitlisted person (deviation 4).

**Real expiry is on read (D2, SCRUM-137).** Every read or change of an event's registrations, `GET /events/available`, `GET /me/registrations`, register, join waitlist, withdraw, accept, decline and the organiser's `GET /events/{event_id}/registrations`, first calls `expire_lapsed_offers`. Each offer past `offer_expires_at` becomes `expired` with an `offer_expired` log row, and its place goes to the head of the waitlist (`offered`, a new 24-hour window, notified) or back to capacity. Once the event has started the offer still expires but the place goes to no one. It commits on its own, before the endpoint's work, so a newcomer's `EVENT_FULL` or a holder's `OFFER_EXPIRED` doesn't undo it; see §1a "Lapse on read". Declining a lapsed offer answers `409 {"code": "OFFER_EXPIRED"}` (deviation 13). There's no scheduler and no background worker.

### `POST /registrations/{registration_id}/accept` — SCRUM-51 (US6b)

The offer holder takes up the seat: `offered` → `confirmed`, `offer_expires_at` cleared, an `attendance_log` row with `action = 'registered'` and note `accepted waitlist offer`. Locks the event and the registration like decline does. Identity: `X-Attendee-Id`.

| Outcome | Status | Body |
|---|---|---|
| Accepted | `200` | Same as a registration: `{"registration_id", "status": "confirmed", "event": {"name", "start_at", "end_at", "venue_name" or "join_link"}}` |
| Not holding an offer (waitlisted, confirmed, declined, withdrawn…) | `409` | `{"code": "NO_ACTIVE_OFFER"}` — status unchanged (US6b AC 3) |
| Offer past `offer_expires_at`, or already expired | `409` | `{"code": "OFFER_EXPIRED"}` (deviation 13); the place has already passed on (TC-US7-17) |
| Event already started | `403` | `{"code": "EVENT_STARTED"}` |
| Someone else's registration, or unknown id | `404` | `{"code": "NOT_FOUND"}` |
 
---
 
### Event requests — SCRUM-41 to SCRUM-44 (US1)

Router: `app/event/request_router.py`; logic: `app/event/request_service.py`. **Identity:** `X-User-Id`, resolved by `get_current_user` (unknown or missing → `401 UNAUTHENTICATED`, inactive → `403 FORBIDDEN`); write routes also need role `organiser` (`require_user_roles`, wrong role → `403 FORBIDDEN`).

| Method & path | Purpose |
|---|---|
| `POST /api/v1/event-requests` | Create a draft from partial data → `201` |
| `GET /api/v1/me/event-requests` | Caller's requests, newest first → `{"event_requests": [...]}` |
| `GET /api/v1/event-requests` | Review queue: requests from `submitted` to `rejected`, oldest submission first: every one for a Lead, only those assigned to them for a coordinator (D48). Coordinator or Coordinator Lead only (SCRUM-57; Venue Staff `403` since SCRUM-120, deviation 46) |
| `GET /api/v1/event-requests/unassigned` | The Lead's queue: `submitted` requests with no coordinator, oldest first, each with `organiser` (`id`, `name`, `email`) → `{"event_requests": [...]}`. Coordinator Lead only (SCRUM-13) |
| `GET /api/v1/coordinators` | Picker: active users with role `coordinator`, `{"coordinators": [{id, name, email, planning_count}]}`; `planning_count` is how many events they are currently planning, 0 when none (SCRUM-67, D30). Lead only |
| `POST /api/v1/event-requests/{id}/assignment` | Body `{"coordinator_id": "<uuid>"}`; sets the coordinator and moves the request to `under_review` (D27). Lead only |
| `GET /api/v1/event-requests/assigned` | The Lead's Assigned tab: `{"event_requests": [...]}`, each an event request plus `event_date`. Optional `coordinator_id` and `status` filters (SCRUM-86, D44). A real status outside the active set (e.g. `draft`) is `422 INVALID_STATUS_FILTER`; a value that isn't a status at all (`?status=foo`) gets FastAPI's generic `422`. Lead only |
| `GET /api/v1/event-requests/{id}/assignment-history` | `{"assignments": [{id, kind, assigned_by, coordinator, created_at}]}`, newest first; `kind` is `assignment` or `reassignment`, and `assigned_by` and `coordinator` are `{id, name, email}`; `reason` is the Lead's reason on a reassignment, else `null` (SCRUM-69, D42, SCRUM-83). Lead only; `404` for a draft or unknown id |
| `GET /api/v1/event-requests/{id}` | Read one: the owner, a Lead, or its assigned coordinator (D11, D48). Organiser, Coordinator or Lead only; other roles `403` (deviation 46). Since US24 PR 3 it includes `start_at` and `end_at`, null until the event is planned (deviation 55) |
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
| Target is unknown, inactive, not a `coordinator` (this includes any Lead), the caller themselves, or the request's creator (D51) | `422` | `{"code": "INVALID_COORDINATOR", "reason": "unknown_user" \| "inactive" \| "not_a_coordinator" \| "self_assignment" \| "created_the_request"}`; nothing changes |
| The Lead created the request (D51) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (deviation 45); nothing changes |
| Request isn't `submitted`, or already has a coordinator (reassigning is `POST …/reassignment`, SCRUM-83) | `409` | `{"code": "ASSIGNMENT_NOT_ALLOWED", "status": "<current>"}` |
| Draft, past-stage event or unknown id | `404` | `{"code": "NOT_FOUND"}` (D11) |
| Not the Lead / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

The Lead gate is the `coordinator_lead` role (any held role counts, D46). Leads may also read every submitted request (D11) and the whole review queue. A returned request keeps its `coordinator_id` through the organiser's reply, so it never rejoins the queue (AC 10).

**Lead notification (AC 11, D28).** After `POST /api/v1/event-requests/{id}/submit` commits, `event_request_service` calls `Notifier.request_queued` once for each active Coordinator Lead, with `email`, `request_reference`, `event_name`, `organiser_name` (the organiser's display name) and `preferred_dates`. Like the clarification notice it runs after the commit and is best effort: a notifier error is logged and never undoes the submit, and one Lead's failure doesn't stop the next. No active Lead logs a warning. `LoggingNotifier` only logs it for now.

**Assignment notices (SCRUM-68, D29).** After `POST /api/v1/event-requests/{id}/assignment` commits, `assignment_service` calls `Notifier.assignment_made` twice: once for the assigned coordinator (`recipient="coordinator"`) and once for the organiser who created the request (`recipient="organiser"`). Each carries `email`, `request_reference`, `event_name`, `coordinator_name` (display name) and `event_dates` (the preferred dates). Nothing is sent when the assignment is refused (`422`, `409`, `404`, `403`, `401`). Best effort after the commit: a notifier error is logged and never undoes the assignment, and one recipient failing doesn't stop the other. A missing organiser or email logs a warning and still notifies the coordinator; missing request details (no reference or name) log a warning and the notices still go out, with "no reference yet" and "Untitled event request" in their place. Reassignment's notices are below (SCRUM-83).

**Reassign — `POST /api/v1/event-requests/{id}/reassignment` (SCRUM-83, US10e).** Body `{"coordinator_id", "reason"}`, Lead only. `assignment_service.reassign` locks the event, sets `events.coordinator_id` and writes a `reassignment` history row (with the trimmed reason) in one transaction; the status does not change. Everything linked is keyed by the event (clarification thread, venue bookings, equipment lines, history), so it moves with that one column (D20, D54).

| Outcome | Status | Body |
|---|---|---|
| Reassigned | `200` | the request, `coordinator` now the new one |
| Event has no coordinator, or is `submitted`, `rejected`, `cancelled` or `completed` | `409` | `{"code": "REASSIGNMENT_NOT_ALLOWED", "status": "<current>"}` |
| Same coordinator as now | `422` | `{"code": "INVALID_COORDINATOR", "reason": "same_coordinator"}` |
| Unknown, inactive, not a coordinator, the Lead, or the request's creator (D51, SCRUM-120) | `422` | `INVALID_COORDINATOR` with the reason, as for assign (`created_the_request` for the creator) |
| The Lead created the request (D51, SCRUM-120) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (deviation 45), checked before the status |
| Blank or missing reason | `422` | `MISSING_REQUIRED_FIELD` with `fields: ["reason"]` (a reason over 1000 characters is the framework's `422`) |
| Draft or unknown id | `404` | `NOT_FOUND` |
| Not the Lead (a coordinator included) / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

A refusal changes nothing and notifies no one. **Notices:** after the commit `Notifier.event_reassigned` is called once each for `new_coordinator`, `previous_coordinator` and `organiser`, with `email`, `request_reference`, `event_name`, `previous_coordinator_name`, `new_coordinator_name`, `event_dates` (the preferred dates) and `reason`. Best effort like the assignment notices; no copy goes to the Lead.

**Transfer request — `POST /api/v1/event-requests/{id}/transfer-request` (SCRUM-83 AC 6).** Body `{"reason"}`, coordinator only, `202 {"status": "requested"}`. Nothing moves; `Notifier.transfer_requested` goes to every active Lead with the reason. `404` unless the caller is the event's coordinator, `409 REASSIGNMENT_NOT_ALLOWED` on a finished event, `422` on a blank reason (deviation 48). Screen: **Request a transfer** (SCRUM-146).

### Approve or reject an event request — SCRUM-84 (US17)

`POST /api/v1/event-requests/{id}/approve` (no body) and `POST /api/v1/event-requests/{id}/reject` with `{"reason": "..."}` (unknown fields rejected). Role `coordinator`; logic `app/event/decision_service.py`, which locks the row. Success is `200` with the request, now carrying `decided_at`, `decided_by` (`{"id", "name"}`) and `rejection_reason`; every request body has these three, null until decided (AC 5).

| Outcome | Status | Body |
|---|---|---|
| Not the caller's assigned request, unassigned, a draft, or unknown id | `404` | `{"code": "NOT_FOUND"}` (D48) |
| The caller created the request | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (D51, deviation 47) |
| Reject with no reason, or a blank one | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}` (AC 3) |
| Reason over 1,000 characters, or an unknown field | `422` | FastAPI's validation body |
| Not `under_review` (Submitted, Awaiting Clarification, Approved, Rejected, Cancelled…) | `409` | `{"code": "REQUEST_NOT_DECIDABLE", "status": "<current>"}` (AC 1, 6, deviation 47) |
| Not a coordinator, or inactive / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

Checked in that order; on any refusal nothing changes and nobody is told. After the commit, `Notifier.request_decided` tells the organiser who created the request (`email`, `request_reference`, `event_name`, `decision`, `reason`) (AC 4). Best effort like the other notices: a failure is logged and never undoes the decision.

### Confirm an event — SCRUM-85 (US18)

Role `coordinator`, the event's assigned coordinator only (D48); logic `app/event/confirmation_service.py`.

| Route | Does |
|---|---|
| `GET /api/v1/event-requests/{id}/readiness` | `{"ready": bool, "items": [{kind, name, complete, detail}]}`: one item per live venue booking (`kind: "venue"`, named for the venue), then `equipment`, then `safety` (AC 2). For `approved`, `planning`, `confirmed` and `preparation` events |
| `POST /api/v1/event-requests/{id}/confirmation` | No body (nothing overrides an incomplete arrangement, AC 5). `200` the request with `status: "confirmed"` and `confirmed_at` |
| `POST /api/v1/event-requests/{id}/preparation` | No body. A `confirmed` event becomes `preparation` (AC 6). `200` the request |
| `POST /api/v1/event-requests/{id}/completion` | No body. A `preparation` event whose `end_at` has passed becomes `completed` (D120). `409 COMPLETION_NOT_ALLOWED` from any other status, `409 EVENT_NOT_ENDED` before `end_at`. `200` the request |

| Outcome | Status | Body |
|---|---|---|
| Not the caller's assigned event, unassigned, a draft or unknown id | `404` | `{"code": "NOT_FOUND"}` (D48) |
| Confirm on anything but `approved` or `planning` (Cancelled, Rejected, Confirmed, Preparation, Completed, any request-stage status); readiness before approval | `409` | `{"code": "CONFIRMATION_NOT_ALLOWED", "status": "<current>"}` (AC 5) |
| An arrangement is outstanding | `409` | `{"code": "EVENT_NOT_READY", "outstanding": [items], "items": [items]}` (AC 1, 2): nothing changes and nobody is told |
| Preparation on anything but `confirmed` | `409` | `{"code": "PREPARATION_NOT_ALLOWED", "status": "<current>"}` |
| Not a coordinator, or inactive / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

"Ready" is D86's rule, with items of `kind` `venue` (one per live booking, then `Primary venue` and `Attendance allocated` when those fail), `equipment`, `technical_support` and `safety`. Confirming locks the event, its bookings and its equipment lines, checks readiness, then sets `confirmed`, `confirmed_at` and `confirmed_by_user_id`, and fills the event's `start_at` (earliest approved booking), `end_at` (latest), `capacity` and `delivery_mode` where they are empty. After the commit, `Notifier.event_confirmed` tells the organiser who created the request (`email`, `request_reference`, `event_name`, `starts_at`, `ends_at`, `venues`, the primary venue first, AC 4); best effort like the other notices, a failure is logged and never undoes it. Registration is a separate gate (spec §2): a confirmed or Preparation event with `registration_enabled` opens to attendees (AC 3).

### Safety reviews — SCRUM-99 (US30a), SCRUM-100 (US30b)

Logic `app/safety/service.py`; state rule D92, request for changes D99.

| Route | Role | Does |
|---|---|---|
| `GET /api/v1/safety-reviews` | `safety_officer` | The queue (AC 1: arranged venues, equipment approved and reserved, no decision yet): `{"events": [{event_id, name, request_reference, expected_attendees, venues, starts_at, resent}]}`, oldest submission first |
| `GET /api/v1/safety-reviews/{event_id}` | `safety_officer` | What to review (AC 2, 9): `event` (name, reference, status, attendance, layout, accessibility and equipment needs only), `state`, `venues` (the approved bookings with the venue's capacity, facilities and accessibility), `equipment`, the `checklist` items, the `change_areas` a request for changes can mark, and `history` (earlier reviews with internal notes). `404` unless the event is in the queue or has been reviewed |
| `POST /api/v1/safety-reviews/{event_id}` | `safety_officer` | `{"outcome": "approved" \| "rejected" \| "changes_requested", "checklist": {key: {"result", "comment"}}, "comments", "internal_notes", "areas"}`. `201` the review with internal notes. Every checklist item is answered; a rejection or a request for changes needs `comments`; a request for changes needs `areas` (at least one of `venue`, `layout`, `equipment`, `accessibility`, `other`) and no other outcome may send them; an approval can have no `issue` item (unknown fields rejected) |
| `GET /api/v1/event-requests/{id}/safety-reviews` | organiser, coordinator, Lead (D11, D48) | `{"state": "pending" \| "approved" \| "rejected" \| "changes_requested", "reviews": [...]}` newest first, with outcome, checklist, comments and `areas`, **no internal notes** (AC 7) |
| `POST /api/v1/event-requests/{id}/safety-review-request` | `coordinator` | The assigned coordinator sends a rejected arrangement back, or marks requested changes done, for another review (US30a AC 4, US30b AC 4); `200` the same body |

| Outcome | Status | Body |
|---|---|---|
| Draft or unknown event, an event not assigned to the coordinator | `404` | `{"code": "NOT_FOUND"}` |
| The reviewer created or coordinates the event | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (D51) |
| Not `approved` or `planning`; already approved; rejected or changes requested and not yet sent back; an arrangement outstanding | `409` | `{"code": "SAFETY_REVIEW_NOT_ALLOWED", "reason": "status" \| "already_approved" \| "awaiting_revision" \| "arrangements_incomplete", "status": "<current>"}` |
| Sending back when nothing was rejected or changes requested, already sent back, or approved | `409` | the same code, `reason` `not_rejected`, `already_requested` or `already_approved` |
| Missing outcome, checklist item, comments on a rejection or request for changes, or areas on a request for changes | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["outcome", "checklist.<key>", "comments", "areas"]}` |
| A checklist key that isn't one of the seven; an area that isn't one of the five, or areas on an outcome other than a request for changes | `422` | `{"code": "INVALID_SAFETY_REVIEW", "fields": ["checklist"] \| ["areas"], "items": [...]}` |
| An approval with an `issue` item | `422` | `{"code": "CHECKLIST_HAS_ISSUES", "fields": ["checklist.<key>"]}` |
| Any other role, or inactive / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

Checked in that order; on a refusal nothing is stored and nobody is told. After the commit `Notifier.safety_review_decided` tells the event's coordinator (`email`, `request_reference`, `event_name`, `outcome`, `comments`, `issues`: the labels of the flagged items), best effort like the other notices. An approval sets `safety_approved_at` and `safety_approved_by_user_id`, which US18's readiness reads; **`POST …/preparation` now returns `409 {"code": "SAFETY_NOT_APPROVED"}` for an event without them**. US18's readiness list says what is outstanding after a rejection: the comments, and to revise and send it back.

A request for changes (US30b) tells the coordinator through `Notifier.safety_changes_requested` (`email`, `request_reference`, `event_name`, `comments`, `areas`: the labels, `issues`), instead of `safety_review_decided`, after the commit and best effort. It stores the review and nothing else: no status, booking, equipment or technical support changes (deviation 64). US18's readiness list says what is outstanding: the areas and the comments, and to make the changes and mark them done.

### Notifications — SCRUM-107 (US31)

Logic `app/notification/inbox_service.py`; what is kept and why, D116. Open to every signed-in role (`get_current_user`), and always the caller's own: someone else's notification is `404`, like one that doesn't exist.

| Route | Does |
|---|---|
| `GET /api/v1/me/notifications?limit=&unread_only=` | `{"notifications": [{id, kind, event_id, event_name, message, created_at, read, can_open}], "unread_count"}`, newest first; `limit` 1 to 100 (default 50, else `422`); `unread_count` counts every unread one, not only the ones listed (AC 2, 3) |
| `GET /api/v1/me/notifications/unread-count` | `{"unread_count"}`, for the link on every screen (AC 3) |
| `POST /api/v1/me/notifications/{id}/read` | `200` the notification, read; reading twice keeps the first time (AC 4); `404` for someone else's or an unknown id |
| `POST /api/v1/me/notifications/read-all` | `{"updated", "unread_count": 0}`: the caller's unread ones only (AC 4) |

`can_open` (AC 5) is true when the notification names an event and the caller may read that request by the request routes' own rule (D11, D47, D48); the notice names the event either way. No identity is `401`, an inactive user `403`.

What each notice says is written by `RecordingNotifier` when the story calls the notifier (`kind` is the method's name): `waitlist_offer`, `clarification_requested`, `venue_booking_requested`, `venue_booking_decided`, `venue_booking_withdrawn`, `request_queued`, `assignment_made`, `event_reassigned`, `transfer_requested`, `equipment_line_reviewed`, `request_decided`, `tech_staff_assigned`, `event_confirmed`, `safety_review_decided`, `safety_changes_requested`, `change_requested`, `cancellation_requested`, `cancellation_rejected`, `event_cancelled`, `change_request_decided`, `arrangement_flagged`, `venue_held`, `venue_unavailable`. A new `Notifier` method must be added to the recorder and to its test table (TC-US31-01 fails until it is), so a notice can't be raised without being kept (AC 6).

### `POST /api/v1/event-requests/{id}/clarifications` — SCRUM-53 (US8a)

Role `coordinator`, and only the request's assigned coordinator (D48, since SCRUM-120; D14 retired). Body: `{"sections": ["attendance", "layout"], "comment": "..."}` — sections from D13. Logic: `clarification_service.send_request`, which locks the request row. After the clarification and status commit, the service calls the log-only notifier with the organiser email, request reference, event name, round, sections and comment. A missing owner/email or incomplete request details logs a warning and skips notification; notifier exceptions are logged and never undo the committed clarification.

| Outcome | Status | Body |
|---|---|---|
| Sent | `201` | `{"clarification": {"id", "event_id", "round", "kind": "request", "sections", "comment", "author_user_id", "created_at"}, "status": "awaiting_clarification"}` |
| No sections / blank comment | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": [...]}` |
| Unknown or repeated section | `422` | `{"code": "INVALID_CLARIFICATION", "fields": ["sections"], "sections": [...]}` |
| Request `awaiting_clarification`, `approved` or `rejected` | `409` | `{"code": "CLARIFICATION_NOT_ALLOWED", "status": "<current>"}` (deviation 12, D15) |
| Draft, an event past the request stage (`planning`, `confirmed`, `cancelled`, `completed`), unknown id, or a request not assigned to this coordinator (an unassigned one included) | `404` | `{"code": "NOT_FOUND"}` (D11, D48) |
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

The whole thread, `{"clarifications": [...]}`, oldest round first and each question before its reply (AC 1, 3). Readable by whoever may read the request: its owner, a Lead, or its assigned coordinator, so after a reassignment the new coordinator reads and continues it and the previous one can't (D48). Another organiser or coordinator gets `404 NOT_FOUND`; any other role `403` (deviation 46).

### Venues — SCRUM-87 (US20)

Router: `app/venue/router.py`; logic: `app/venue/service.py`. **Identity:** `X-User-Id` or a token via `get_current_user`; writes also need Venue Staff (`require_user_roles(*VENUE_STAFF_ROLES)`, `venue_staff` since SCRUM-119, D49).

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/venues` | anyone signed in | `{"venues": [...]}` by name. Query: `q` (part of the name, any case), `min_capacity`, `facilities` and `accessibility` (repeatable; the venue must have all of them), `active` (staff only: `true`/`false`, all when left out). Non-staff always get active venues only |
| `GET /api/v1/venues/available` | coordinator, operations manager (D25) | US2 search, below |
| `GET /api/v1/venues/{id}` | anyone signed in | One venue; an inactive venue is `404` except to Venue Staff, a Coordinator Lead (D61) and a coordinator whose event is booked there |
| `GET /api/v1/venues/{id}/calendar` | Coordinator, Lead, Venue Staff (D56) | US21 availability calendar, below |
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
| Unknown id; inactive venue read by anyone but Venue Staff, a Lead or a coordinator whose event is booked there | `404` | `{"code": "NOT_FOUND"}` |
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

### `GET /api/v1/venues/{id}/calendar` — SCRUM-88 (US21), SCRUM-122

Logic: `calendar_service.calendar` (`app/venue/calendar_service.py`). Query: `from`, `to` (`YYYY-MM-DD`, Singapore days, both included, `to` not before `from`, at most 42 days; D61). Coordinator, Coordinator Lead or Venue Staff (D56); the venue must be one `GET /venues/{id}` would show the caller.

```json
{
  "venue": {"id": "…", "name": "Hall A", "is_active": true, "opens_at": "08:00:00", "closes_at": "20:00:00",
            "setup_minutes": 30, "turnaround_minutes": 15},
  "from": "2026-11-16", "to": "2026-11-22",
  "items": [
    {"kind": "booking", "label": "Booking", "starts_at": "…", "ends_at": "…",
     "occupied": {"starts_at": "…", "ends_at": "…"},
     "booking": {"id": "…", "reference": "VB-2026-000001", "status": "requested",
                 "event": {"name": "Design Review", "request_reference": null, "status": "approved"},
                 "preparation_status": "not_started"},
     "note": null},
    {"kind": "block", "label": "Unavailable", "starts_at": "…", "ends_at": "…",
     "occupied": {"starts_at": "…", "ends_at": "…"}, "booking": null, "note": "Aircon repair"}
  ]
}
```

Items: live bookings (Requested and Approved, D57) whose stored occupied window overlaps the range, a cancelled event's included with the event's `status: "cancelled"` (D60), and venue blocks overlapping it (a block's occupied window is its own times). Sorted by occupied start, bookings before blocks at the same start. `reference` is null unless the caller is Venue Staff, a Lead or the event's coordinator (D58). No holds until US25 (D59).

| Outcome | Status | Body |
|---|---|---|
| `from` or `to` missing or not `YYYY-MM-DD`; `to` before `from`; more than 42 days | `422` | `{"code": "INVALID_DATE_RANGE", "fields": ["from", "to"], "message": "..."}`, `fields` naming only the bad ones (deviation 51) |
| Unknown venue; inactive venue the caller can't see | `404` | `{"code": "NOT_FOUND"}` |
| No identity; not a Coordinator, Lead or Venue Staff | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### Event registrations — SCRUM-96 (US28)

Router: `app/registration/roster_router.py`; logic: `app/registration/roster_service.py`. **Identity:** `X-User-Id` or a token; role `organiser` or `coordinator` (`require_user_roles`), anyone else `403 FORBIDDEN`. Who manages which event is D52: the creating Organiser and the assigned Coordinator, by any role the user holds (D46).

| Method & path | Purpose |
|---|---|
| `GET /api/v1/me/managed-events` | `{"events": [{"id", "name", "start_at", "end_at", "status", "capacity"}]}`, the events the caller manages past the request stage, soonest first |
| `GET /api/v1/events/{id}/registrations` | One event's registrations, below. Query: `status` (repeatable, any registration status) and `show_all` (`true`/`false`, default `false`) |

```json
{
  "event": { "...": "as in managed-events" },
  "totals": {"confirmed": 2, "waitlisted": 1, "offered": 0, "seats_remaining": 0},
  "registration_fields": [{"field_key": "dietary", "label": "Dietary requirements", "field_type": "text", "options": null, "required": false}],
  "registrations": [{
    "registration_id": "uuid", "attendee_name": "Mei Tan", "attendee_email": "mei.tan.2024@smu.edu.sg",
    "status": "confirmed", "registered_at": "2026-10-01T01:00:00Z",
    "waitlist_position": null, "offer_expires_at": null, "answers": {"dietary": "vegetarian"}
  }]
}
```

- `totals` count every registration by status, whatever the filter (AC 2); `seats_remaining` is §2's rule, floored at 0.
- The list: `status` given → only those statuses; else `show_all=true` → every row; else withdrawn, declined and expired are left out (AC 4, 5). Confirmed first, then offered, then the waitlist in queue order, then the inactive rows.
- `attendee_name` is the user's `full_name`: null for seeded users and email-only waitlist entries (D3). `waitlist_position` only on waitlisted rows, `offer_expires_at` only on offered ones. `answers` is keyed by `field_key`; an unanswered question is absent.

| Outcome | Status | Body |
|---|---|---|
| Someone else's event, one not assigned to the coordinator (or unassigned), a request not yet an event (draft → rejected), or unknown id | `404` | `{"code": "NOT_FOUND"}` |
| Unknown `status` value | `422` | FastAPI's validation error |
| Any other role (attendee, Coordinator Lead, Venue Staff, Tech Support, Safety Officer), inactive user / no identity | `403` / `401` | `FORBIDDEN` / `UNAUTHENTICATED` |

### Venue bookings — SCRUM-89 (US22)

Router: `app/venue/booking_router.py`; logic: `app/venue/booking_service.py`; table: §2 `venue_bookings`. **Identity:** `X-User-Id` or a token via `get_current_user`, then a role check.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/v1/venue-bookings` | Coordinator | Request a venue → `201`, status `requested`, with `warnings`. Notifies every active Venue Staff member once |
| `POST /api/v1/venue-bookings/{id}/withdraw` | The event's assigned coordinator | → `200`, status `withdrawn`, `withdrawn_at` set; the window is free again. Since US24 (D69) an **approved** booking too, and a rejected or withdrawn one is `409 BOOKING_NOT_LIVE`: it keeps its decision (D77) and every active Venue Staff member is told (`Notifier.venue_booking_withdrawn`); the event's other bookings are untouched |
| `POST /api/v1/venue-bookings/{id}/make-primary` | The event's assigned coordinator | US24 AC 4 (D68): → `200`, this live booking is the event's primary venue and the previous one isn't; the event row is locked `FOR UPDATE`, as create locks it. Idempotent. `409 BOOKING_NOT_LIVE` for a withdrawn or rejected booking; anyone else's `404` |
| `POST /api/v1/venue-bookings/{id}/preparation` | Venue Staff | US24 AC 7 (D73): `{"preparation_status": "not_started" \| "in_progress" \| "ready"}` → `200`. Unknown or missing value `422 INVALID_BOOKING` naming `preparation_status`; a booking that isn't approved `409 BOOKING_NOT_APPROVED` |
| `GET /api/v1/venue-bookings/pending` | Venue Staff | `{"bookings": [...]}`: Requested bookings, oldest first |
| `POST /api/v1/venue-bookings/{id}/approve` | Venue Staff | US4: no body (or `{}`); → `200`, status `approved`, `decided_at`/`decided_by_user_id` set; the venue is reserved. Refused on a buffered clash (D38). Notifies the coordinator(s) (D40) |
| `POST /api/v1/venue-bookings/{id}/reject` | Venue Staff | US4: optional `reason`, `alternative_suggestion` (trimmed; blank → null); → `200`, status `rejected`; the window is free again; the event's status doesn't change (AC 8). Notifies the coordinator(s) |
| `GET /api/v1/events/{event_id}/venue-bookings` | The event's assigned coordinator (D20), Venue Staff, and since US24 the event's Organiser from `approved` on (D71; another organiser `404`) | `{"bookings": [...], "venues_arranged", "primary_booking_id", "allocated_attendees", "expected_attendees", "next_action"}`: the event's bookings in every status, soonest first, each with `unavailability` (`{kind: "rejected", reason, alternative_suggestion}` or `{kind: "venue_inactive"}`) and `next_action` (`venue_staff_to_decide`, `coordinator_to_rebook`, `none`); `venues_arranged` per D67 and D72 (`venues_arranged()` in `booking_service`, for US18); the event's `next_action` is `choose_primary` when it has live bookings but no primary |
| `GET /api/v1/venue-bookings/{id}/evaluation` | Venue Staff (D19, D36) | US13 AC 4: `{booking_id, reference, occupied, conflicts: [{kind, reference, note, starts_at, ends_at, occupied, overlap}], outside_hours: {opens_at, closes_at, fields} \| null, clear}`, the booking as it would occupy its venue now (current buffers and hours). `404` for an unknown id |

Body (unknown fields rejected, so no `setup_minutes` or `turnaround_minutes`: US20 AC 7): `event_id`, `venue_id`, `starts_at`, `ends_at` (ISO 8601 **with** an offset), `expected_attendees`, `room_layout` and, since US24, `purpose` (trimmed, 1 to 100 characters, D66) all required; the window must fall within the event's schedule (D65: `start_at`–`end_at` once set, else a preferred day between the preferred times; `422 INVALID_BOOKING` on `starts_at`/`ends_at`); `required_facilities` and `required_accessibility_features` (D18 tags, D23; default `[]`, trimmed, de-duplicated, D18's order) and `special_requirements` (blank → null) optional. A booking reads back with every column (including US4's decision fields) except the two ids, which become `event: {id, name, request_reference, status}` and `venue: {id, name, location, capacity}`; since US13 they also carry `reference` (D33), `occupied_starts_at` and `occupied_ends_at`, and since US24 `purpose`, `is_primary`, `preparation_status`, `unavailability` and `next_action`. Create adds `warnings`; the event's first live booking is created primary (D68).

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
| Approve or reject a booking you requested, or one for an event you now coordinate (D51) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (deviation 45); checked before the status, nothing changes |
| Approve or reject a booking that isn't `requested` | `409` | `{"code": "BOOKING_NOT_PENDING", "status": "..."}` (deviation 33) |
| Withdraw a booking that isn't live (rejected or already withdrawn); since US24 an approved one can be withdrawn (D69) | `409` | `{"code": "BOOKING_NOT_LIVE", "status": "..."}` (deviation 53; `BOOKING_NOT_PENDING` before US24, deviation 28) |
| Approve: the stored occupied window (US13) overlaps another live booking's or a block, or the venue is inactive | `409` | `{"code": "VENUE_UNAVAILABLE", ...}` as on create, plus `"buffers": true` and a "Too close to …" message for a buffer-only clash; the booking stays `requested` (D38, D39) |
| Approve: the stored occupied window starts before the venue opens or ends after it closes, as the hours are now | `409` | `{"code": "VENUE_OUTSIDE_HOURS", "fields": [...], "opens_at": ..., "closes_at": ..., "occupied": {...}, "message": ...}` as on create but `409`, checked before clashes; the booking stays `requested` (D32, deviation 43) |
| Approve: the request's start has passed | `409` | `{"code": "BOOKING_EXPIRED", "message": "..."}`; it can still be rejected (deviation 33) |
| Approve: attendance above the venue's capacity, cut since the request | `409` | `{"code": "VENUE_CAPACITY_EXCEEDED", "capacity": 25, "message": "..."}` |
| Approve: the event is no longer `approved` or `planning` | `409` | `{"code": "EVENT_NOT_BOOKABLE", "status": "..."}` |
| Approve with any body field; reject with a field other than the two notes, or a note over 1,000 characters | `422` | FastAPI's unknown-field error: no override, no partial approval (US4 AC 3, 7) |
| Withdraw someone else's or an unknown booking; list an unknown or draft event | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

- **AC 7's race:** the service checks for a conflict first, so it can name the window, and the exclusion constraint settles a simultaneous pair. Two overlapping inserts can deadlock in the exclusion index; Postgres aborts one, and the service runs that request once more, which then sees the winner (TC-US22-15).
- The venue row is read `FOR SHARE` and, since US24, the event row `FOR UPDATE`: two requests for the same event wait for each other, so only one becomes its first, primary booking (D68); requests for different events don't block each other, and a status change or venue edit waits for the request.
- The notice (`Notifier.venue_booking_requested`) goes out after the commit; a failure is logged and the booking stands. An unnamed approved event is named by its request reference.
- **The reusable rule (US13, for US4):** `evaluate_window(db, venue, starts_at, ends_at, *, exclude_booking_id=None)` and `evaluate_booking(db, booking)` in `app/venue/availability.py` return `Evaluation(occupied, conflicts, outside_hours)`, with `clear` true when nothing stands in the way. `evaluate_window` builds the occupied window from the venue's current buffers; `evaluate_booking` uses the booking's stored one (the range `venue_bookings_no_overlap` guards), which buffer edits keep current (D31). Each `Conflict` has `kind`, `window`, `occupied`, `overlap`, `reference` (bookings) and `note` (blocks), bookings first then blocks, by start. Live bookings count (D21); holds are a `TODO(US25)` stub. US4's approval calls `evaluate_booking` and refuses unless `clear` (AC 3, 5): hours first (`409 VENUE_OUTSIDE_HOURS`), then the first conflict (`409 VENUE_UNAVAILABLE`); there's no override.
- **Not built:** holds (US25, D22); a database guard between blocks and bookings (D22); requesting a venue from search results (only from the event for now).

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
| `GET /api/v1/equipment-lines?status=pending` | Tech Support (`tech_support`, deviation 34) | `{"lines": [...]}`: pending lines from every event, oldest first (AC 3). `status` defaults to `pending`; `approved` lists approved lines to reserve (US27, SCRUM-131, deviation 54) |
| `POST /api/v1/equipment-lines/{id}/review` | Tech Support | `{"decision": "approved" \| "rejected", "note": "..."}` → `200`; saves the status, note, reviewer and time, then notifies the coordinator who asked (AC 3, 5) |
| `POST /api/v1/equipment-lines/{id}/availability-check` | Tech Support | US5's availability check, recorded on the line (SCRUM-125), below |
| `POST` / `DELETE /api/v1/equipment-lines/{id}/reservation` | Tech Support | US27's reserve and release (SCRUM-131), below |

Line body (unknown fields rejected, so a coordinator can't send `status` or review fields): `equipment_type_id` and `quantity` (a whole number, at least 1) required on add; `notes` optional (trimmed, blank → null). Review body (unknown fields rejected): `decision` required; `note` optional for both decisions (D43; trimmed, blank → null). **There's no quantity in a review:** approval is always the full requested quantity (AC 6), so sending one is a `422` (TC-US26-13). A line reads back as `{id, event: {id, name, start_at}, equipment_type: {id, name}, quantity, notes, status, review_note, requested_by_user_id, reviewed_by_user_id, reviewed_at, availability_check, reservation, created_at, updated_at}`; `availability_check` is US5's latest check, `{sufficient, shortfall, checked_by_user_id, checked_at}` or null (SCRUM-125, D64); `reservation` is US27's, `{quantity, reserved_by_user_id, reserved_at, released_because_event_cancelled}` or null (SCRUM-131).

| Outcome | Status | Body |
|---|---|---|
| Unknown or draft event, or one the coordinator doesn't manage (D20); unknown line, or one on such an event | `404` | `{"code": "NOT_FOUND"}` |
| Add to an event not `planning` or `confirmed` | `409` | `{"code": "EVENT_NOT_ELIGIBLE", "status": "..."}` (deviation 38) |
| Type missing or not in the catalogue; quantity missing, not a whole number or below 1 | `422` | `{"code": "INVALID_EQUIPMENT_LINE", "fields": [...], "errors": {...}}` (deviation 36) |
| A second pending or approved line of the type on the event (add, or edit to that type) | `409` | `{"code": "DUPLICATE_EQUIPMENT_TYPE", "fields": ["equipment_type_id"], "message": "..."}` (deviation 39, D41) |
| Review a line you requested, or one for an event you now coordinate (D51) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` (deviation 45); checked before the status, nothing changes |
| Edit, remove or review a line that is `approved` or `rejected` | `409` | `{"code": "LINE_NOT_PENDING", "status": "..."}` (deviation 37) |
| Unknown field (e.g. `status` on a line, `quantity` on a review); a decision other than `approved` or `rejected` | `422` | FastAPI's validation body |
| Missing/unknown identity; wrong role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

- **Locking:** the event row is read `FOR SHARE` when a line is added, so a concurrent status change waits. Edits, removals and reviews lock the line `FOR UPDATE`, so a second review, or an edit racing a review, waits and then gets `LINE_NOT_PENDING`.
- **The notice** (`Notifier.equipment_line_reviewed`: email, line id, event name, equipment type, quantity, decision, note) goes to the coordinator who requested the line, even if the event has since been reassigned (TC-US26-14). It's sent after the commit; a failure is logged and the review stands. A refused review notifies nobody.
- **Not built:** refusing an approval when stock is short: US5's check (below) informs Tech Support's judgement but doesn't block a review (US5 AC 5); asking for more of a type that's already approved (D41's gap); re-checking the event's status when a pending line is edited or removed (deviation 38). The coordinator's list of eligible events came with SCRUM-110 (deviation 41).

### `POST /api/v1/equipment-lines/{id}/availability-check` — SCRUM-9 (US5), SCRUM-125

Logic: `equipment_service.check_availability` (`app/equipment/service.py`). Tech Support only (as the queue), any line whatever its status; no body. Tables: §2 equipment stock and `equipment_reservations` (SCRUM-124). Deviation 52.

```json
{
  "line_id": "…",
  "equipment_type": {"id": "…", "name": "Projector", "storage_location": "AV store, Level B1, Administration Building"},
  "window": {"starts_at": "2026-11-16T10:00:00+08:00", "ends_at": "2026-11-16T13:00:00+08:00"},
  "requested": 4, "total": 10, "out_of_service": 2, "reserved_elsewhere": 3,
  "available": 5, "sufficient": true, "shortfall": 0,
  "checked_by_user_id": "…", "checked_at": "2026-11-02T09:00:00+08:00"
}
```

- **Window:** the line's event's own `start_at`–`end_at`; no venue setup or turnaround (AC 6).
- **Reserved elsewhere:** the sum of `equipment_reservations` of the type on *other* events whose own times overlap the window, half-open, so back-to-back events don't overlap (as D21 for venues). The line's own event isn't counted against itself (AC 2). Since US27 (SCRUM-131, D75), a cancelled event's reservations aren't counted either. `_reserved_elsewhere` in `app/equipment/service.py` is shared with reserving.
- **Available** = total − out of service − reserved elsewhere, never below 0 (stock can drop below what's reserved). `sufficient` is available ≥ requested; `shortfall` is requested − available, or 0 (AC 4). `storage_location` is reference only and never changes the result (AC 7).
- **The outcome is recorded on the line (AC 5, D64):** `sufficient`, `shortfall`, who and when, replacing the last check; every line read-back carries it as `availability_check` (null until checked). Editing the line's quantity or type clears it; editing only its notes keeps it. The line is locked `FOR UPDATE`, so a coordinator's edit waits for a check in progress. It never reserves, and it doesn't block a review.

| Outcome | Status | Body |
|---|---|---|
| Unknown line | `404` | `{"code": "NOT_FOUND"}` |
| Missing/unknown identity; not Tech Support or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### `POST` / `DELETE /api/v1/equipment-lines/{id}/reservation` — SCRUM-95 (US27), SCRUM-131

Logic: `equipment_service.reserve` and `release` (`app/equipment/service.py`). Tech Support only. Tables: §2 `equipment_reservations` (SCRUM-130). Deviation 54.

- **Reserve** (`POST`, no fields: an empty body or none; anything sent, a quantity included, is a `422`) → `201` with the line, its `reservation` filled in. Always the line's full quantity (AC 1, 6). The line must be `approved` and not reserved, and its event `planning` or `confirmed` (D76). The quantity must be available for the event's own times by US5's count: stock, less out of service, less other events' overlapping reservations (cancelled events' excluded, D75), no venue setup or turnaround (AC 1, 2).
- **Locking:** the line, then the equipment type's row, `FOR UPDATE`, so two reservations of one type take turns and the second counts the first's units (TC-US27-11, a real two-connection race). A reservation reduces what US5's check shows for overlapping events (AC 3).
- **Release** (`DELETE`) → `204`: the reservation is deleted (D74), the units are available again, and the line can be reserved again (AC 5).
- **A cancelled event (D75):** nothing cancels an event yet (US9, SCRUM-12), so its reservations stop counting and its line's `reservation` reads `released_because_event_cancelled: true`. US9 deletes them when it cancels an event. **Since US9 PR 2 it does:** cancelling deletes them, so this only covers rows from before.

| Outcome | Status | Body |
|---|---|---|
| Unknown line | `404` | `{"code": "NOT_FOUND"}` |
| Reserve a line that isn't approved | `409` | `{"code": "LINE_NOT_APPROVED", "status": "..."}` |
| Reserve for an event not in `planning` or `confirmed` | `409` | `{"code": "EVENT_NOT_ELIGIBLE", "status": "..."}` (D76) |
| Reserve a line already reserved | `409` | `{"code": "ALREADY_RESERVED"}` |
| Not enough available | `409` | `{"code": "INSUFFICIENT_EQUIPMENT", "available": 2, "requested": 4, "shortfall": 2}` |
| Release a line not reserved | `409` | `{"code": "NOT_RESERVED"}` |
| A field sent with reserve | `422` | FastAPI's validation body |
| Missing/unknown identity; not Tech Support or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### Tech support staff — SCRUM-17 (US14), SCRUM-134

Logic: `tech_staff_service` (`app/equipment/tech_staff_service.py`). The event's assigned coordinator only (D20): any other coordinator, or a draft, gets `404`; other roles `403`. Table: §2 `tech_staff_assignments` (SCRUM-133, D79). Deviation 56.

| Method & path | Body | Success |
|---|---|---|
| `GET /api/v1/events/{id}/tech-staff` | — | `200`, below |
| `POST /api/v1/events/{id}/tech-staff` | `{"staff_user_ids": ["..."]}`, one or more | `201`, the same body as `GET` |
| `DELETE /api/v1/events/{id}/tech-staff/{staff_user_id}` | — | `204` |

```json
{
  "eligible": true,
  "assigned": [{"staff": {"id": "...", "name": "Terry Ong"}, "assigned_by": {"id": "...", "name": "..."}, "assigned_at": "..."}],
  "available": [{"id": "...", "name": "Priya Nair"}],
  "log": [{"action": "unassigned", "staff": {"id": "...", "name": "..."}, "by": {"id": "...", "name": "..."}, "at": "..."}]
}
```

- **Eligible (AC 1, D80):** an approved equipment line, and the event in `planning` or `confirmed`. While it isn't, `available` is empty.
- **Available (AC 2, D81):** active Tech support users, by name, who aren't assigned here and aren't actively assigned to another event overlapping this one's own times. A cancelled event's assignments don't count (D81, as D75 for equipment). A `name` is the full name, else the email.
- **Assign (AC 3):** all of them or none. Each staff member's `users` row is locked `FOR UPDATE`, in id order, before the checks, so two coordinators can't put one person on overlapping events (TC-US14-13, a real two-connection race). Repeated ids count once.
- **Notify (AC 4, D82):** after the commit, `Notifier.tech_staff_assigned` once per person: the event's name and times, the venue attendees see, the approved lines (`"2 x Projector"`) and `equipment_needs`. Log-only, like the others; a failure is logged and the assignment stands.
- **Unassign (AC 5, 6):** stamps who and when; the row stays. Reassigning is an unassign, then an assign.
- **Log (AC 6):** every assign and unassign, newest first.

| Outcome | Status | Body |
|---|---|---|
| Unknown event, a draft, or not this coordinator's | `404` | `{"code": "NOT_FOUND"}` |
| Assign without an approved request | `409` | `{"code": "NO_APPROVED_TECH_REQUEST"}` |
| Assign or unassign once the event has started (`now >= start_at`) | `409` | `{"code": "EVENT_STARTED"}` |
| Not an active Tech support user, or unknown | `422` | `{"code": "INVALID_STAFF", "staff_user_ids": ["..."]}` |
| Already assigned to this event | `409` | `{"code": "ALREADY_ASSIGNED", "staff_user_ids": ["..."]}` |
| On an overlapping event | `409` | `{"code": "STAFF_UNAVAILABLE", "staff_user_ids": ["..."]}` |
| Unassign someone not assigned | `409` | `{"code": "NOT_ASSIGNED"}` |
| No ids, or a field that isn't `staff_user_ids` | `422` | FastAPI's validation body |
| Missing/unknown identity; not a coordinator or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### Event edits — SCRUM-15 (US12)

Router: `app/event/edit_router.py`; logic: `app/event/edit_service.py`. **Identity:** `X-User-Id` or a token; role `coordinator`, anyone else `403`. Only the event's assigned coordinator (D48), for an event in `planning`, `confirmed`, `cancelled` or `completed`; anything else is `404 NOT_FOUND`.

| Method & path | Purpose |
|---|---|
| `GET /api/v1/me/coordinated-events` | `{"events": [{id, name, status, editable, start_at, end_at}]}`, soonest first; `editable` is true only in planning (AC 1) |
| `GET /api/v1/events/{id}` | The event's details, `editable`, and `pending_change_requests` |
| `PATCH /api/v1/events/{id}` | Any of `name`, `event_category`, `purpose`, `start_at`, `end_at` (ISO 8601 with offset), `capacity`, `expected_attendees`, `delivery_mode`, `room_layout_preference`, `accessibility_needs`, `equipment_needs`, `join_link`; only those sent change |
| `GET /api/v1/events/{id}/history` | `{"entries": [...]}`, newest first (AC 5) |

```json
{
  "outcome": "pending_approval",
  "message": "Your change to capacity is awaiting approval. The event keeps its current details until then.",
  "event": { "...": "the details, unchanged" },
  "change_request": {"id": "uuid", "status": "pending_approval", "requested_by": {"id": "uuid", "name": "Casey Tan"},
                     "created_at": "...", "changes": [{"field": "capacity", "old_value": 80, "new_value": 120}]}
}
```

| Outcome | Status | Body |
|---|---|---|
| Only non-critical fields changed (AC 2), or nothing changed | `200` | `outcome: "saved"`, `change_request: null` |
| A critical field changed (D87); the whole edit is held (D88) | `202` | `outcome: "pending_approval"`, the change request |
| Not in planning (AC 1) | `409` | `{"code": "EVENT_NOT_EDITABLE", "status": "confirmed"}` |
| A field invalid (AC 4); nothing written | `422` | `{"code": "INVALID_EVENT_EDIT", "fields": ["end_at"], "errors": {"end_at": "End time must be after the start time."}}` |
| Unknown field (`status`, `venue_name`) | `422` | FastAPI's validation error |

### Organiser change requests — SCRUM-97 (US29a)

Router: `app/event/request_router.py`; logic: `app/event/change_request_service.py`. **Identity:** `X-User-Id` or a token; role `organiser`, anyone else `403`. Only the Organiser who created the event; anyone else's event, a draft or an unknown id is `404`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/event-requests/{id}/change-requests` | `{"changes": {"expected_attendees": 50}, "reason": "Two more teams are joining."}`; fields by stage (D90) |
| `GET /api/v1/me/change-requests` | `{"change_requests": [...]}`, the caller's own, newest first; `event_id` narrows to one event |

```json
{"id": "uuid", "event_id": "uuid", "event_name": "Community design workshop", "request_reference": "ER-2026-000123",
 "status": "pending_approval", "reason": "Two more teams are joining.", "created_at": "...",
 "changes": [{"field": "expected_attendees", "old_value": 24, "new_value": 50}]}
```

| Outcome | Status | Body |
|---|---|---|
| Created; the event is unchanged (AC 4); the coordinator, or every Lead while unassigned, is told (D91) | `201` | the request, `status: "pending_approval"` |
| Rejected, Cancelled or Completed (AC 1) | `409` | `{"code": "CHANGE_NOT_ALLOWED", "status": "rejected"}` |
| No reason (AC 3) or no changes | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}` |
| A field not open at this stage, an invalid proposed value, a reason over 1,000 characters | `422` | `{"code": "INVALID_CHANGE_REQUEST", "fields": [...], "errors": {...}}` |
| Every proposed value is the current one | `422` | `{"code": "NO_CHANGES", "message": "..."}` |

### Change request decisions — SCRUM-142 (US29b)

Router: `app/event/change_decision_router.py`; logic: `app/event/change_decision_service.py` and `app/event/review_flag_service.py`. **Identity:** `X-User-Id` or a token; roles `coordinator` and `coordinator_lead` (flags: `coordinator` only), anyone else `403`. **Who decides (D102):** the event's assigned coordinator decides requests on their event that they didn't make; a Lead decides a coordinator's own US12 edit, on the Lead's Event requests screen (SCRUM-144, extending deviation 71). Someone else's request is `404`; deciding your own is `403 SELF_DECISION_NOT_ALLOWED` (D51), checked before whether it's still pending. Who decides (D102) and who clears are checked again on the locked event, so a reassignment at the same moment refuses the old coordinator (Calvin's #125 review).

**For SCRUM-143 (the screen), decided with the story owner on 1 Nov:**
- **Source:** a request is the organiser's (`source: "organiser"`) when its requester created the event, otherwise a coordinator's US12 edit (`"coordinator"`). A previous coordinator's edit, left after a reassignment, goes to the new coordinator.
- **Resolved flags:** a flag whose booking was withdrawn or rejected, or whose reservation was released, reads `resolved: true` and no longer counts as open. It's derived on every read and never written: a clearance names who cleared it, and a withdrawal or release has nobody to name.
- **Who hears a decision:** the requester always (an organiser for US29a, a coordinator for a US12 edit), and the event's organiser too when an approved US12 edit changed their event. Venue staff hear about each flagged booking and Tech support about each flagged reservation. All log-only.
- **History on the request stage:** an approval on a Submitted, Under Review or Awaiting Clarification event is written to History like any other, but `GET /api/v1/events/{id}/history` serves only Planning onwards (US12), so it isn't readable there yet.

| Method & path | Purpose |
|---|---|
| `GET /api/v1/change-requests` | `{"change_requests": [...]}`, oldest first; `status` = `pending_approval` (default), `decided` or `all`; `event_id` narrows to one event; `acting_as` = `coordinator` (only what the user decides as the event's assigned coordinator) or `coordinator_lead` (only a coordinator's own US12 edits, the Lead's), omitted for both (Calvin's #127 review: the frontend sends the Role switcher's role, so a user holding both sees one role's requests at a time; still deviation 68's API, and deciding is unchanged; any other value `422`) |
| `GET /api/v1/change-requests/{id}` | one request, as listed |
| `POST /api/v1/change-requests/{id}/approve` | no body; applies the values (AC 2) and, on a significant change, what D103 to D106 say |
| `POST /api/v1/change-requests/{id}/reject` | `{"reason": "The venue is booked that week."}`; 1 to 1,000 characters; the event is unchanged |
| `GET /api/v1/events/{id}/review-flags` | `{"flags": [...]}`, open first, then newest; the event's coordinator only |
| `POST /api/v1/review-flags/{id}/clear` | `{"note": "Venue staff confirmed the later slot."}` (optional, at most 1,000 characters) |

```json
{"id": "uuid", "event_id": "uuid", "event_name": "Change Request Demo", "request_reference": null, "event_status": "confirmed",
 "source": "organiser", "requested_by": {"id": "uuid", "name": "Olivia Organiser", "email": "..."},
 "reason": "...", "status": "pending_approval", "created_at": "...",
 "changes": [{"field": "start_at", "label": "Start time", "old_value": "...", "new_value": "...", "current_value": "...", "stale": false}],
 "significant": true,
 "impact": {"status_after": "planning", "venue_bookings": 1, "equipment_reservations": 1, "registrations": 0, "safety_review_required": true},
 "decided_at": null, "decided_by": null, "rejection_reason": null}
```

`impact` is null once decided. A non-significant request's is the current status and zeros; at the request stage a significant one only takes its values, so everything but `status_after` is null (D105). A decision returns `{"change_request", "event" (the event request read), "status_change": {"from": "confirmed", "to": "planning"} | null, "flags": [...], "safety_review_required"}`. A flag is `{"id", "event_id", "kind": "venue_booking" | "equipment_reservation" | "registrations", "target": {"id", "label", "status"} | null, "fields", "change_request_id", "raised_at", "cleared_at", "cleared_by", "cleared_note", "resolved", "open"}`; `target` is null for registrations.

**Approving, in order:** lock the event, then the request (a second decision waits and then gets `409`), refuse Preparation, Cancelled, Completed and Rejected (D105), re-check every field (D107), apply the values, write History (`applied` per field, `decided`). On a significant change (D103) to an Approved, Planning or Confirmed event: lock its live bookings, raise or extend one open flag per affected item (D104), move Confirmed back to Planning clearing `confirmed_at` and `confirmed_by_user_id` (`status_changed`, `confirmation_cleared`), and clear a safety approval (`safety_approval_cleared`; the review row stays, D106). Notices go after the commit; one that fails is logged and the decision stands. **Elsewhere:** US18's readiness gains a `review_flags` item ("Review after change") once the event has had a flag, complete when none is open, so open flags make confirming `409 EVENT_NOT_READY`; the Safety Officer's queue leaves the event out while a flag is open, and reviewing it is `409 SAFETY_REVIEW_NOT_ALLOWED` with `reason: "review_flags_open"` (D106). `GET /api/v1/me/change-requests` gains `decided_at` and `rejection_reason`; History entries gain `action`.

| Outcome | Status | Body |
|---|---|---|
| Approved or rejected | `200` | the decision, as above |
| Not a Coordinator or Lead | `403` | `{"code": "FORBIDDEN"}` |
| Your own request (D51) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` |
| Not one you decide, or unknown | `404` | `{"code": "NOT_FOUND"}` |
| Already decided, or the other side of a race | `409` | `{"code": "CHANGE_REQUEST_NOT_PENDING", "status": "approved"}` |
| Approving after the event changed (D107) | `409` | `{"code": "CHANGE_REQUEST_STALE", "fields": [{"field", "reason": "changed" \| "not_at_this_stage" \| "invalid", "requested_from", "current", "proposed"}], "message": "..."}` |
| Approving in Preparation, Cancelled, Completed, Rejected (D105) | `409` | `{"code": "CHANGE_NOT_ALLOWED", "status": "preparation"}` |
| Rejecting with no reason | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}` |
| A reason over 1,000 characters | `422` | `{"code": "INVALID_CHANGE_DECISION", "fields": ["reason"], "errors": {...}}` |
| Clearing a cleared flag | `409` | `{"code": "FLAG_ALREADY_CLEARED"}` |
| A note over 1,000 characters | `422` | `{"code": "INVALID_REVIEW_FLAG", "fields": ["note"], "errors": {...}}` |

### Event cancellation — SCRUM-12 (US9)

Router: `app/event/request_router.py` (`router` and `cancellations_router`); logic: `app/event/cancellation_service.py`. **Identity:** `X-User-Id` or a token. Asking is the `organiser`'s, for an event they created; cancelling, approving and rejecting are the `coordinator`'s, for the event they're assigned (D48); reading is both, and every Coordinator Lead (who read every submitted request, D48). Anyone else's event or request, a draft or an unknown id is `404`; a role the route doesn't name is `403`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/event-requests/{id}/cancellation-requests` | The organiser asks, `{"reason": "..."}`; `201`, `status: "pending"`; the coordinator is told (AC 1, 2) |
| `POST /api/v1/event-cancellations/{cancellation_id}/approve` | No body. The request is approved and the event cancelled (AC 2, 4, 5) |
| `POST /api/v1/event-cancellations/{cancellation_id}/reject` | `{"reason": "..."}`, required; the event goes ahead and the organiser is told why (AC 2) |
| `POST /api/v1/event-requests/{id}/cancel` | The coordinator cancels directly, `{"reason": "..."}` (AC 3): one `approved`, `direct` row with them as requester and decider |
| `GET /api/v1/event-requests/{id}/cancellations` | `{"cancellations": [...]}`, newest first (AC 8), at any status, a dateless cancelled event included; the organiser, the assigned coordinator and any Lead |

```json
{"id": "uuid", "event_id": "uuid", "event_name": "Design Thinking Lab", "request_reference": "ER-2026-000123",
 "event_status": "cancelled", "status": "approved", "reason": "The keynote speaker can't travel.",
 "requested_by": {"id": "uuid", "name": "Olivia Ong"}, "requested_at": "...",
 "decided_by": {"id": "uuid", "name": "Casey Tan"}, "decided_at": "...", "rejection_reason": null, "direct": false}
```

**Cancelling** (approve or direct), in one transaction: the event becomes `cancelled`; every live venue booking, of every venue, is withdrawn, an approved one keeping its decision (D60, D69, D77); the event's `equipment_reservations` are deleted (D75); Tech support assignments stay, since D81 already frees their staff. **Open work** (Matt's review of #117): the event's pending change requests (US12, US29a) are rejected in the same transaction, so US29b never approves a change to a cancelled event; its equipment lines awaiting Tech support can't be (D51 bars the coordinator as their reviewer), so Tech support's pending queue leaves them out and review refuses them (`409 EVENT_NOT_ELIGIBLE`, `status: cancelled`); safety reviews already take only Approved and Planning events (`SAFETY_REVIEW_NOT_ALLOWED`, reason `status`). Holds wait for US25 (`TODO(US25)`). After the commit, `Notifier.event_cancelled` goes once per address to the organiser, every active Venue staff member if an approved venue was released (D100), the actively assigned, active Tech support staff and every confirmed, offered (unless the offer has lapsed) or wait-listed attendee, each with the event's name and the reason (AC 6). **The assigned coordinator keeps a cancelled event** in their review queue and can open it (`GET /api/v1/event-requests/{id}`), as a rejected one is kept: `COORDINATOR_EVENT_STATUSES` gains `cancelled` (widens D11 again), so an event cancelled before it had a date stays reachable (D98). The approved row and `events.status` change in one transaction, and every cancelled event has exactly one approved row (TC-US9-25). Registrations are left as they are; a cancelled event offers no freed place, and an offer made before can't be accepted (`409 EVENT_CANCELLED`). **Locks:** cancelling takes the event's live bookings, then the event (FOR UPDATE), the order Venue staff's approve takes them in, so the two wait rather than deadlock (TC-US9-24); Tech support's reserve now reads the event FOR SHARE, so it waits for a cancel and then sees it Cancelled.

| Outcome | Status | Body |
|---|---|---|
| Asked; approved, rejected or cancelled | `201`; `200` | the cancellation. The request's notice goes to the assigned coordinator, or every active Lead when they aren't active (as D91), since only the coordinator decides and a Lead must reassign |
| Not Approved, Planning, Confirmed or Preparation (before approval, Rejected, Cancelled, Completed: AC 1, 4, 7) | `409` | `{"code": "CANCELLATION_NOT_ALLOWED", "status": "submitted"}` |
| The event has started (AC 7; an Approved request starts at its earliest approved venue booking, else its last preferred date and time, D101); on approve, the request stays pending | `409` | `{"code": "EVENT_STARTED", "starts_at": "..."}` |
| A request is already waiting (asking again, or cancelling directly beside it) | `409` | `{"code": "CANCELLATION_PENDING", "cancellation_id": "uuid"}` |
| Approving or rejecting a request that's no longer pending | `409` | `{"code": "CANCELLATION_NOT_PENDING", "status": "rejected"}` |
| Deciding a request you made (D51) | `403` | `{"code": "SELF_DECISION_NOT_ALLOWED"}` |
| No reason, or a blank one | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}` |
| A reason over 1,000 characters | `422` | `{"code": "INVALID_CANCELLATION", "fields": ["reason"], "errors": {...}}` |
### Event agenda — SCRUM-18 (US15), SCRUM-139

Router: `app/agenda/router.py`; logic: `app/agenda/service.py`. Table: §2 `event_sessions` (SCRUM-138). Deviation 66. **Identity:** `X-User-Id` or a token. **Listing:** role `organiser`, `coordinator` or `coordinator_lead`, and whoever can read the request (D11, D93): its Organiser always, a Lead or its assigned coordinator once submitted; anyone else `404`. **Changing:** role `organiser`, anyone else `403`; only the request's own Organiser (anyone else's, or an unknown id, is `404`), while it's `draft` or `planning` (D93).

| Method & path | Body | Success |
|---|---|---|
| `GET /api/v1/event-requests/{id}/sessions` | — | `200`, `{"sessions": [...]}` in chronological order: start, then end, then title (D97) |
| `POST /api/v1/event-requests/{id}/sessions` | `{"title", "session_type", "speaker_name", "starts_at", "ends_at"}`, times ISO 8601 with offset | `201`, the session |
| `PATCH /api/v1/event-sessions/{id}` | Any of those; only the fields sent change, and the session is checked whole | `200`, the session |
| `DELETE /api/v1/event-sessions/{id}` | — | `204` |

```json
{"id": "uuid", "event_id": "uuid", "title": "Opening keynote", "session_type": "presentation", "speaker_name": "Dr Tan",
 "starts_at": "2026-10-08T09:00:00+08:00", "ends_at": "2026-10-08T10:00:00+08:00", "outside_window": false}
```

- **Fields (AC 2, D96):** a title; a type, `presentation`, `workshop`, `panel`, `break` or `other`; a speaker unless it's a break (a blank one is `null`); the end after the start. Text is trimmed.
- **The window (AC 3, D94):** a `planning` event's `start_at` to `end_at`; a draft's D65 window, one of its `preferred_dates` between `preferred_start_time` and `preferred_end_time`, Singapore time. A draft without them takes no sessions yet. Moving the event's dates doesn't re-check its sessions, so `outside_window` marks those it left outside.
- **One track (AC 4, D95):** no two of the event's sessions overlap; back-to-back is fine, and an edit doesn't clash with itself. Every change locks the event row `FOR UPDATE` first, so two saves to one agenda take turns and the second is refused by name (TC-US15-12, a real two-connection race); `event_sessions_no_overlap` backs it up.

| Outcome | Status | Body |
|---|---|---|
| Not `draft` or `planning` (AC 1) | `409` | `{"code": "AGENDA_NOT_EDITABLE", "status": "submitted"}` |
| A field missing or invalid, or outside the window; nothing written | `422` | `{"code": "INVALID_SESSION", "fields": ["title", "ends_at"], "errors": {"title": "Give the session a title.", "ends_at": "..."}}` |
| Overlaps another session (AC 4) | `409` | `{"code": "SESSION_OVERLAP", "session": {"id": "uuid", "title": "Opening keynote", "starts_at": "...", "ends_at": "..."}}` |
| Unknown field (`room`) | `422` | FastAPI's validation error |
| Missing/unknown identity; another role or inactive | `401` / `403` | `UNAUTHENTICATED` / `FORBIDDEN` |

### Venue holds — SCRUM-93 (US25)

Routers: `app/venue/booking_router.py` (`holds_router` and `router`); logic: `app/venue/booking_service.py` and `app/venue/hold_service.py`. **Identity:** `X-User-Id` or a token. Placing a hold and listing the events to hold for are **Venue staff**'s; confirming is the event's assigned **coordinator**'s (D20, D48), and declining is `withdraw`. Anyone else's booking or event is `404`; a role the route doesn't name is `403`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/venue-holds` | A booking request's body plus `hold_expires_at` (AC 1); `201` with the booking, `status: "held"`. Checked as a request is: the event Approved or Planning, its schedule (D65), capacity, opening hours, live bookings, holds and blocks; the event's coordinator is told (`Notifier.venue_held`, stage `placed`), and warned at once if it expires within 24 hours |
| `GET /api/v1/venue-holds/events` | `{"events": [...]}`: Approved and Planning events with a coordinator, by name, with their reference, schedule and expected attendance (D112). An unassigned event isn't offered: nobody could confirm or decline its hold |
| `POST /api/v1/venue-bookings/{id}/confirm` | No body. A held venue becomes a request Venue staff approve, before the hold's expiry (AC 5): the coordinator becomes the requester, the first live one is the primary venue (D68), Venue staff are told |
| `POST /api/v1/venue-bookings/{id}/withdraw` | Now also takes a held booking: declining it frees the window (AC 7, D110) |

Every booking read or change sweeps lapsed holds first (`expire_lapsed_holds`, D109, §1a "Lapse on read"): request, place, confirm, decline (withdraw), approve, reject, make primary, the pending list, an event's bookings, the calendar and search, so a stale screen can't decline, reject or make primary a hold that has lapsed. A hold placed with less than 24 hours left is marked warned in the same commit, so the warning goes once. A hold past its expiry, or a confirmed one Venue staff haven't approved by then, becomes `expired` (`expired_at`), frees its window and stops being primary; its coordinator is told (`expired`). A hold in its last 24 hours warns its coordinator once (`expiring`, `hold_warned_at`). A booking read carries `hold_expires_at`, `held_by_user_id` and `expired_at`, and a held one's `next_action` is `coordinator_to_confirm`. The calendar draws a held booking as `kind: "hold"`, label "Hold", with `booking.hold_expires_at`; an expired one isn't listed (AC 6). Cancelling an event (US9) withdraws its holds with its bookings (AC 7).

| Outcome | Status | Body |
|---|---|---|
| Placed; confirmed | `201`; `200` | the booking |
| No expiry, with any other missing field named at once | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["venue_id", "hold_expires_at"]}` |
| An expiry with no offset, not in the future, over 14 days ahead (D108), after the held time starts, or after the venue's setup for it starts | `422` | `{"code": "INVALID_HOLD", "fields": ["hold_expires_at"], "errors": {...}}` |
| Confirming a booking that isn't held (already confirmed, declined or expired) | `409` | `{"code": "HOLD_NOT_HELD", "status": "requested"}` |
| Approving a confirmed hold after its expiry | `409` | `{"code": "BOOKING_NOT_PENDING", "status": "expired"}` |
| Placing a hold on an event with no coordinator, who alone could confirm or decline it (D112) | `409` | `{"code": "EVENT_NOT_BOOKABLE", "status": "approved", "reason": "no_coordinator"}` |
| The event isn't Approved or Planning; the window clashes; outside hours; over capacity | as a request (US22, US13) | |

### Venue unavailability — SCRUM-90 (US23a)

Router: `app/venue/router.py`; logic: `app/venue/block_service.py`, with the read side in `app/venue/booking_service.py`. **Identity:** `X-User-Id` or a token. Recording a period is **Venue staff**'s; any other role is `403`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/venues/{id}/blocks` | `{"starts_at", "ends_at", "reason", "note"?}` (ISO 8601 with an offset; `reason` one of `maintenance`, `equipment_failure`, `renovation`, `safety`, `other`; `note` trimmed, up to 500 characters). `201` with the period (`id`, `venue`, `starts_at`, `ends_at`, `reason`, `note`, `created_by_user_id`, `created_at`) and `affected_bookings` (`id`, `reference`, `status`, `event`, `starts_at`, `ends_at`), by start, plus `already_affected_bookings` in the same shape: the bookings it also overlaps that an earlier period already marked (D115) |

Lapsed holds are swept first (D109), so a hold already past its expiry expires rather than being marked. **Locks (Matt's #133 review):** the overlapping bookings `FOR UPDATE` first, then the venue `FOR UPDATE` (D22), then the bookings read again: the approval's order (booking, event, venue) and a cancel's (TC-US9-24), so a period and an approval at once land in turn (TC-US23A-21; the venue first deadlocked). A request in flight holds the venue `FOR SHARE`, so it either commits first and the second read marks it, or waits and then sees the period. Every `requested`, `approved` or `held` booking at the venue whose **occupied** window (with setup and turnaround) overlaps the period, half-open so touching isn't overlapping, and **hasn't ended** (`occupied_ends_at` after now: a period that began in the past doesn't reach events already over), gets `rearrangement_block_id` and `rearrangement_flagged_at`; its status, window and everything else stay (AC 3, D113). A booking an earlier period already marked keeps that one and isn't announced again, but is listed in `already_affected_bookings` (D115). After the commit, each affected event's assigned coordinator and organiser (`created_by_user_id`) get one `Notifier.venue_unavailable` each, naming the venue, the period, the reason, the event's affected booking references and the next action (D114); attendees aren't told (AC 4). Notices are best effort: a failure is logged and the period stands. An inactive venue can still be marked.

**On the read side:** a marked live booking or hold reads `unavailability: {"kind": "venue_unavailable", "block": {"id", "starts_at", "ends_at", "reason", "note"}, "flagged_at"}` (also on `GET /events/{id}/venue-bookings` for the Organiser, D71), and its `next_action` is `coordinator_to_rebook`, a hold's included. `venues_arranged` is false while any live booking is marked, so US18 can't confirm the event. Confirming a marked hold is `409 VENUE_UNAVAILABLE` (Venue staff couldn't approve it, AC 5). Withdrawing a marked booking works as before. New requests and holds overlapping the period, and approving a marked request, are refused by the availability check that already reads blocks (`409 VENUE_UNAVAILABLE`, AC 5). Calendar items for a block carry `reason` (AC 6).

| Outcome | Status | Body |
|---|---|---|
| Recorded | `201` | the period and its affected bookings |
| Missing fields, every one at once (a blank reason counts) | `422` | `{"code": "MISSING_REQUIRED_FIELD", "fields": ["starts_at", "ends_at", "reason"]}` |
| A time with no offset; an end at or before the start (AC 2); a period already over; an unknown reason; a note over 500 characters | `422` | `{"code": "INVALID_BLOCK", "fields": ["ends_at"], "errors": {"ends_at": "The end must be after the start."}}` |
| No such venue | `404` | `{"code": "NOT_FOUND"}` |
| Not Venue staff | `403` | `{"code": "FORBIDDEN"}` |

### Replacement venue — SCRUM-91 (US23b)

Logic: `app/venue/booking_service.py` (replacements and restores) and `app/venue/block_service.py` (ending a period early, and the move back to Planning); routes in `app/venue/booking_router.py` and `app/venue/router.py`. Built on US23a's marker (D113).

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/v1/venue-bookings` with `replaces_booking_id` | the event's coordinator | AC 3 (D117): a replacement for a booking of the same event that needs rearrangement. Checked and saved like any request (US22, US13), Venue staff hear of it, and it waits for their approval; it isn't primary while the original is live (D68) |
| `POST /api/v1/venues/{id}/blocks/{block_id}/end` | Venue staff | AC 5 (D118): `ends_at` moves to now, or to `starts_at` if the period hadn't begun (an empty period), and `scheduled_ends_at` keeps the end it had. Locks (Chloe's #135 review): the bookings it marks first, by id, then the venue `FOR UPDATE` (D22), then the period, then the bookings read again, as recording a period, an approval and confirming a restore take bookings before the venue (TC-US23B-22). `200` with the period and `affected_bookings`: the live bookings it alone still marks, now free to restore; each one's active coordinator is told after the commit (`venue_period_ended`, Matt's #134 review). A booking another period still overlaps is moved to that period's marker and nobody is told (Matt's #131 review) |
| `POST /api/v1/venue-bookings/{id}/restore` | the event's coordinator | AC 5: ask Venue staff to restore a marked booking. Refused while any block overlaps its whole occupied window, or while a replacement is requested or approved. Every active Venue staff member is told (`venue_restore_requested`); `next_action` becomes `venue_staff_to_restore` |
| `GET /api/v1/venue-bookings/restore-requests` | Venue staff | The requests waiting, oldest first (`{"bookings": [...]}`) |
| `POST /api/v1/venue-bookings/{id}/restore/confirm` | Venue staff, not the one who asked nor the event's coordinator (D51) | The venue `FOR UPDATE` (D22), the window checked again, then the marker and the request cleared; the booking keeps its status, window and primary. The coordinator who asked and the event's coordinator are told (`venue_restore_decided`) |
| `POST /api/v1/venue-bookings/{id}/restore/decline` | Venue staff, as above | Optional `{"reason"}`, up to 1000 characters as a US4 rejection reason (longer is `422`; Chloe's #135 review); the request is cleared and the booking still needs rearrangement; the decline is kept (`restore_declined_at`, `restore_decline_reason` on the booking read) until the coordinator asks again, which clears it; told as above |

**Approving a replacement** (`POST /venue-bookings/{id}/approve`, US4) also, in the same commit, makes the original `replaced` with `replaced_at`, clears any restore request on it, and moves the primary across if the original had it; the original keeps its reference, venue, times, decision and marker (AC 4). **Locks (Chloe's #135 review):** the replacement and its original first, both by id, then the event `FOR SHARE` and the venue, so recording a period at the original's venue (bookings, events, venue) waits rather than deadlocks (TC-US23B-21). If the replacement ends up primary (the original had it, or the coordinator made the pending replacement primary first through US24: Chloe's #135 review) and the venue or times changed, every registered, offered or wait-listed attendee gets `venue_changed` after the commit, best effort (AC 7); nobody else hears more than US4 already tells. A replacement for a booking that was withdrawn or restored meanwhile is just another venue.

**Back to Planning (AC 1):** `POST /venues/{id}/blocks` moves each affected `confirmed` or `preparation` event to `planning`, clearing `confirmed_at` and `confirmed_by_user_id`, with `status_changed` and `confirmation_cleared` History entries by the Venue staff member; an `approved` or `planning` event keeps its status, and the safety approval stands. The events are locked after the bookings and before the venue, the approval's order. Nothing ever cancels the event (AC 6); the coordinator may cancel it through US9.

| Outcome | Status | Body |
|---|---|---|
| `replaces_booking_id` names another event's booking, or none | `422` | `{"code": "INVALID_BOOKING", "fields": ["replaces_booking_id"]}`; a hold naming one is refused the same way |
| The booking doesn't need rearrangement (not marked, or not live) | `409` | `{"code": "BOOKING_NOT_REPLACEABLE", "status", "message"}` |
| A replacement is already requested or approved | `409` | `{"code": "REPLACEMENT_EXISTS", "reference", "message"}`, for a replacement or a restore |
| A block still overlaps the occupied window | `409` | `{"code": "VENUE_UNAVAILABLE", "conflict", "message"}`, for a restore request or confirm |
| Restore already asked for / nothing asked for | `409` | `{"code": "RESTORE_ALREADY_REQUESTED"}` / `{"code": "RESTORE_NOT_REQUESTED", "status"}` |
| The period is already over | `409` | `{"code": "BLOCK_ENDED", "message"}` |
| No such period at that venue; someone else's booking | `404` | `{"code": "NOT_FOUND"}` |

### `GET /api/v1/me` — SCRUM-105 (US16a)

Who is logged in, so the login page can show the role's home screen (AC 2). Same identity as any role route (`get_current_user`: a token, or `X-User-Id` with dev headers on). `200 {"id", "email", "full_name", "roles"}` (`MeOut`): `roles` is every role the user holds, in the role type's order (SCRUM-119, D45). The interim `role` (the first of them) was removed by SCRUM-121 once the frontend read `roles` (PR #86 review); `full_name` is null until a name is set, unlike `POST /auth/profile`'s `ProfileOut`, where it is always present. No profile yet: `403 PROFILE_REQUIRED`; deactivated: `403 FORBIDDEN`; no identity: `401 UNAUTHENTICATED`.

### `POST /api/v1/auth/profile` — SCRUM-103 (US16a)

Called on a confirmed user's **first login**, after the token check answered `403 PROFILE_REQUIRED`. **Token only**: the dev header stubs never apply (`get_token_claims`). Body: `{"full_name": "...", "role": "organiser" | "attendee"}` (lowercase; `"Organiser"` is `INVALID_ROLE`), unknown fields rejected. The token's email must be verified (`user_metadata.email_verified`), as for #55's linking. `auth_user_id` and `email` come from the token, never the body. An `attendee` also gets its `attendees` row with the same id.

| Outcome | Status | Body |
|---|---|---|
| Created | `201` | `{"id", "email", "full_name", "roles"}`, so the frontend knows which home screen to show; `roles` is `["organiser"]` or `["attendee"]` (SCRUM-119; `role` removed by SCRUM-121) |
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
| TC-US3-12 | Attendee received `EVENT_FULL` | `POST /events/{id}/waitlist` as the logged-in attendee (SCRUM-136) | `201`, row `status = 'waitlisted'`, `waitlist_joined_at` set, position returned |
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
| TC-US7-10 | B's offer window lapses (swept on the next read; `POST /expire-offer` in tests) | Offer expires | B → `expired`; C → `offered`; `attendance_log` records both |
| TC-US7-11 | B declines the offer | B declines | B → `declined`; C → `offered` immediately, without waiting for a window |
| TC-US7-12 | Any successful withdrawal | A withdraws | `registrations.withdrawn_at` set **and** an `attendance_log` row with `action = 'withdrawn'` and `occurred_at` |
| TC-US7-13 | A withdraws, then checks the event listing | `GET /events/available` | `seats_remaining` reflects the withdrawal on the very next read — no cache, no delayed job |
| TC-US7-14 | A is `waitlisted`, not confirmed | A withdraws | `200`; A leaves the queue; everyone behind A moves up one position; no seat is freed |
| TC-US7-15 | Notification send raises an exception | A withdraws | Withdrawal still commits; failure is logged; response is still `200` |
| TC-US7-16 | B's offer passed `offer_expires_at`; C waitlisted (capacity 1; for withdraw, capacity 2 with D confirmed) | Any read or change of the event's registrations: board, My events, organiser list, register, join, withdraw (D), accept, decline | B → `expired`, `offer_expired` logged; C → `offered` with a new 24-hour window, notified once. With only live offers, nothing is locked or written (SCRUM-137) |
| TC-US7-17 | B's offer lapsed; C waitlisted | B accepts | `409 OFFER_EXPIRED`, also for an offer already swept; B `expired`, C `offered` and notified: the sweep's commit survives the 409 |
| TC-US7-18 | B's offer lapsed; nobody waiting | Board read | B `expired`; `seats_remaining` 1; no notification |
| TC-US7-19 | Committed rows; B's offer lapsed; C waitlisted | Two sessions sweep at once, meeting at a barrier before the event lock | C offered once: one `offered` row, one notification, one `offer_expired` row |
| TC-US7-20 | Capacity 1; B's offer lapsed; C waitlisted | A newcomer registers | `409 EVENT_FULL` with `waitlist_available`; C `offered`; no row for the newcomer |
| TC-US7-21 | B's offer lapsed; C waitlisted | B declines | `409 OFFER_EXPIRED`; B `expired`, not `declined`; C `offered` |
| TC-US7-22 | B's offer lapsed | B reads My events | B's row is under `expired` with when it ended (a forced early expiry shows the real end), and gone once B rejoins the queue; one row per event, the latest lapsed offer, if B's offers on it lapsed more than once; My events shows it muted under Offer expired |
| TC-US7-23 | B's offer lapsed; the event has started; C waitlisted | Organiser list read | B `expired`; C stays `waitlisted`; no offer, no notification |
| TC-US7-24 | Two events, each with a lapsed offer and a waitlisted person | One board read | Each swept in its own transaction, in id order: lock, commit, lock, commit |
 
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

E2E (SCRUM-52), second test in the same file, run serially with the first: Calvin leaves the Design Sprint Bootcamp waitlist from My events → the card says "Full · waitlist open" → its dialog offers "Join the waitlist" and no "Reserve my seat" (AC 1) → he joins with one click, nothing typed (SCRUM-136), and sees "You're #2 in the queue" (AC 3) → the card says "You're on the waitlist (#2)" → Tech Talk, with places left, offers no waitlist (AC 2) → My events lists him at position 2. It ends as it started, so it reruns without a reseed. The full-without-waitlist case isn't in the seed; TC-US6A-10 covers it.

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
| TC-US6A-11 | Full, enabled; attendee logged in | Joins with no body (no email typed) | `201 waitlisted` with a position; the row's `attendee_id` is theirs and `attendee_email` their own; the `waitlisted` log row carries the attendee (SCRUM-136) |
| TC-US6A-12 | Full, enabled | Joins with no login | `401 UNAUTHENTICATED`; no registration row, no attendance log (SCRUM-136) |
| TC-US6A-13 | Capacity 1 held by A; B joined the waitlist logged in | A withdraws, then B accepts | B's place is `offered`, then `confirmed` (SCRUM-136: the waitlist gap is closed) |
| TC-US6A-14 | Full, enabled; attendee logged in | Joins with an old client's body `{"email": "someone.else@smu.edu.sg"}` | `201`; the place is the logged-in attendee's; nothing is stored for the typed email (SCRUM-136) |
| TC-US6A-15 | An email-only waitlist row from before SCRUM-136 holds the attendee's email, in any letter case (e.g. `Calvin.Ng.2024@smu.edu.sg` for a lowercase login) | They join, logged in; later a seat frees and they accept | `409 ALREADY_REGISTERED`; the old row now has their `attendee_id`, still one row, keeping its place in the queue; the dialog shows the message and refreshes the board, so the card shows their place; it's offered the freed seat and `accept` confirms it (SCRUM-136, PR #106 review) |

### SCRUM-72 / US6b — Take up an available place after a withdrawal

> *As a waiting-listed Attendee, I want to be told when a place becomes available and be able to take it up, so that I get to attend the event I was waiting for.*

Backend: `tests/registration/test_accept_offer.py` (01–07 accept, SCRUM-51; 08–10 offer notice, SCRUM-50). E2E: the third test in `e2e/tests/attendee-registration.spec.ts` (SCRUM-76) has Sofia leave the Bootcamp queue and Mei withdraw through the API, then Calvin sees **Place available**, accepts, and finds the event under Confirmed; it leaves Calvin with a Bootcamp seat, so reseed before a local rerun. TC-US7-08's notification now also carries the `registration_id`, and TC-US11-10's empty response includes `"offered": []`. IDs are `TC-US6B-…` so they can't collide with US6a's tests, written in parallel. AC 1 (notify the next person) is the Sprint 1 offer flow, TC-US7-07, 08.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US6B-01 | B holds an offer on a full event, C queued behind | B accepts | `200`, B `confirmed`, confirmation has the event; seats unchanged; C still first in the queue; logged (AC 2) |
| TC-US6B-02 | C is waitlisted with no offer | C accepts | `409 NO_ACTIVE_OFFER`; C stays `waitlisted` (AC 3) |
| TC-US6B-03 | Confirmed, declined or withdrawn registration | Accept | `409 NO_ACTIVE_OFFER`; unchanged |
| TC-US6B-04 | B's offer | C tries to accept it | `404 NOT_FOUND`; B still `offered` |
| TC-US6B-05 | B's offer has passed `offer_expires_at` | B accepts | `409 OFFER_EXPIRED`; B is `expired` (swept first, SCRUM-137) |
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
| TC-US10A-32 | A request under review; a Lead who isn't a coordinator | Approve, reject, confirm, read readiness, start preparation | `403 FORBIDDEN` each; status unchanged (AC 7, 13 Oct). A user holding both roles acts as a coordinator on their own events (D46) |

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
| TC-US19-11 | Assigned event | Lead posts approve, reject, confirm | approve and reject `403 FORBIDDEN` (US17 gives them to the assigned coordinator only); confirm `404` or `405`: no such route. The event is unchanged (AC 4) |
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

### SCRUM-83 / US10e — Reassign an event to another coordinator

Backend in `backend/tests/event/test_reassignment.py`; frontend in `frontend/src/features/eventRequest/assignment.integration.test.tsx` and, for the transfer request (SCRUM-146), `transferRequest.integration.test.tsx`; E2E in `e2e/tests/transfer-request.spec.ts`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US10E-01 | Event with a coordinator | Lead reassigns with a reason | `200`, new coordinator, status unchanged, one `reassignment` record with the reason, shown in the history |
| TC-US10E-02, 03 | Each active status; rejected, cancelled, completed | Lead reassigns | `200`; `409 REASSIGNMENT_NOT_ALLOWED` and nothing changes (AC 1) |
| TC-US10E-04, 05 | Unassigned request; draft or unknown id | Lead reassigns | `409`; `404` |
| TC-US10E-06 | Same coordinator | Lead reassigns | `422 same_coordinator`; no record, no notice (AC 5) |
| TC-US10E-07 | The Lead, an organiser, an inactive user, an unknown id | Lead reassigns | `422 INVALID_COORDINATOR` (AC 2) |
| TC-US10E-08, 09 | No, empty or blank reason; padded or over-long reason | Lead reassigns | `422`; trimmed and capped (AC 2) |
| TC-US10E-10 | Coordinator (the event's own), organiser, Venue staff, nobody | Reassign | `403`, `403`, `403`, `401`; nothing changes (AC 6) |
| TC-US10E-11 | Reassigned event | Previous and new coordinator read it, the queue, send a clarification | Previous: `404`, absent from the queue, `404`; new: `200`, listed, `201` (AC 3, D54) |
| TC-US10E-12 | Event with a clarification thread | Reassign | The new coordinator reads the thread (AC 4) |
| TC-US10E-13 | Event with a pending venue booking | Reassign | The new coordinator lists and withdraws it; the previous gets `404` (AC 4, D20) |
| TC-US10E-14 | Event with an equipment line | Reassign | The new coordinator lists and removes it; the previous gets `404` (AC 4) |
| TC-US10E-15 | Assign, reassign, reassign back | Lead reads the history | Newest first, each reassignment with its reason (AC 4) |
| TC-US10E-16 | Reassign | — | Notices to the new coordinator, the previous one and the organiser, none to the Lead |
| TC-US10E-17, 18 | Refused; notifier raises | Reassign | No notice; `200`, the move stands, all three tried |
| TC-US10E-19 | — | Insert a `reassignment` row with no reason | The database refuses it |
| TC-US10E-20 | A second Lead reassigns | Both read Assigned | The event moves to the later Lead (US19, D44) |
| TC-US10E-21 to 24 | Event's coordinator | Asks for a transfer | `202`, every active Lead told, nothing moves; reason required; others `404`/`403`; finished event `409` (AC 6) |
| TC-US10E-25 | Assigned event, two coordinators | Frontend: Lead reassigns from the request view | Current coordinator not offered; confirm needs a pick and a reason; success; history shows the reason |
| TC-US10E-26 | Unassigned request | Frontend: Lead opens it | No Reassign action |
| TC-US10E-27 | Backend refuses | Frontend: confirm | The reason is shown and the screen stays |
| TC-US10E-28 | Only one coordinator | Frontend: Reassign | "There are no other active coordinators to assign."; confirm disabled |
| TC-US10E-29 | Assigned coordinator, Under review | Frontend: Request a transfer from the review screen, a padded reason, Send | Send disabled while sending; "Transfer requested. The Coordinator Leads have been told."; the form closes (SCRUM-146) |
| TC-US10E-30 | Planning | Frontend: Send with a blank reason; then the API answers `422 MISSING_REQUIRED_FIELD` | Marked on the field with "Give a reason", nothing sent; the API's refusal marked on the field too |
| TC-US10E-31 | The API answers `409 REASSIGNMENT_NOT_ALLOWED` (`completed`) | Frontend: Send | "A transfer can't be requested while the event is completed."; the reason kept |
| TC-US10E-32 | Cancelled event; an event reassigned to someone else since the queue loaded | Frontend: the coordinator opens it | No Request a transfer |
| TC-US10E-33 | Planning and Completed events on the Events screen | Frontend: open each | Planning offers it and sends the trimmed reason; Completed doesn't |
| TC-US10E-34 | Seeded Event Planning Demo | E2E: the coordinator requests a transfer, then Acting as Coordinator Lead opens Notifications | The confirmation, then an unread "asked to transfer request" notice with the reason |

### SCRUM-85 / US18 — Confirm an event

Backend in `backend/tests/event/test_confirmation.py`; E2E in `e2e/tests/event-confirmation.spec.ts`; frontend in `frontend/src/features/eventRequest/confirmation.integration.test.tsx`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US18-01 | Approved event, every arrangement complete | Coordinator confirms | `200`, `confirmed`, `confirmed_at` and `confirmed_by_user_id` set (AC 3) |
| TC-US18-02, 03 | Two approved bookings; an event with its own date and capacity | Confirm | Date span, capacity (expected attendance) and in-person filled, `venue_name` left alone (D70); existing values kept (D86) |
| TC-US18-04 | Planning event | Confirm | `200` (D86) |
| TC-US18-05 to 07 | A requested booking; no venue; rejected and withdrawn bookings | Confirm | `409 EVENT_NOT_READY` naming the venue; "No venue has been requested yet."; the rejected and withdrawn are ignored (AC 1) |
| TC-US18-08, 09 | A pending equipment line (one approved); none requested | Confirm | `409` naming "1 of 2 equipment lines" and technical support; a rejected line stops blocking, the approved one still needs reserving and staff; no equipment does not block (AC 1) |
| TC-US18-10, 11 | No safety approval; venue, equipment and safety all outstanding | Confirm | `409`; all three listed with the complete ones too (AC 1, 2) |
| TC-US18-12 | One approved and one requested venue | Read readiness | Per venue complete or outstanding, then equipment and safety (AC 2) |
| TC-US18-13 | Cancelled, rejected, confirmed, preparation, completed, under review, awaiting clarification, submitted | Confirm | `409 CONFIRMATION_NOT_ALLOWED`, nothing changes (AC 5) |
| TC-US18-14, 15 | An override body; confirming twice | Confirm | `409`, ignored; the second is `CONFIRMATION_NOT_ALLOWED` (AC 5) |
| TC-US18-16 | Under-review event | Read readiness | `409` |
| TC-US18-17 to 19 | Confirm; refused; notifier raises | — | The organiser told reference, name, start, end and venues; no notice on a refusal; `200`, the confirmation stands, the failure logged (AC 4) |
| TC-US18-20, 21 | Another coordinator, a Lead, an organiser, nobody; unassigned, draft, unknown | Confirm, read | `404`, `403`, `403`, `401`; `404` (D48) |
| TC-US18-22, 23 | Planning, Confirmed, Preparation | The assigned coordinator opens it, its thread and the queue; another coordinator and a Lead | `200` and listed; `404` and absent (D11 widened) |
| TC-US18-24 to 26 | Confirmed event; other statuses; another coordinator | Start preparation | `preparation`; `409 PREPARATION_NOT_ALLOWED`; `404`, `401` (AC 6) |
| TC-US18-27 | Event in Preparation, registration on | Attendee lists the board | It is listed (AC 3) |
| TC-US18-28 | Safety approval with one column set | Insert | The database refuses it |
| TC-US18-29 | Seeded Confirmation Demo | Confirm, reseed, confirm | Ready and confirmable; the reseed puts it back to Approved |
| TC-US18-30 | Seeded Confirmation Demo (E2E) | Coordinator opens it, confirms, starts Preparation | Three complete items; Confirmed, then Preparation |
| TC-US18-31 | Frontend: approved event, all complete | Open it, Confirm event | Three Complete items, the POST sent, "Confirmed" shown |
| TC-US18-32 | Frontend: pending booking and equipment, no safety | Open it | Three Outstanding items with their reasons; Confirm disabled and nothing sent (AC 1, 2, 5) |
| TC-US18-33 | Frontend: safety approved meanwhile | Check again | Confirm enabled |
| TC-US18-34 | Frontend: API says `EVENT_NOT_READY` | Confirm | Alert, and the list is read again |
| TC-US18-35 | Frontend: confirmed event | Start preparation | "Preparation" shown (AC 6) |
| TC-US18-36 | Frontend: planning event | Open it | Request venue and the readiness list both show (D11 widened) |
| TC-US18-37 | Frontend: under-review event | Open it | No readiness list, no readiness call |
| TC-US18-38 | Online event | Confirm | No venue needed (D72); confirms with its own dates |
| TC-US18-39, 40 | Approved bookings with no primary; allocations short of the expected attendance | Confirm | `409` naming "Primary venue"; "Attendance allocated" (US24 D67, D68) |
| TC-US18-41, 42 | An approved, reserved equipment line; staff assigned, then unassigned | Confirm | `409` "No Tech support staff member is assigned yet." until one is active; unassigned staff don't count (D80) |
| TC-US18-43 | Approved, requested, none, no primary, short, online | Read readiness | The venue items agree with `venues_arranged` (D72) |
| TC-US18-44 | Frontend: approved, reserved equipment, no staff | Open it, assign staff, Check again | Technical support outstanding and Confirm disabled; then enabled |

### SCRUM-99 / US30a — Operational safety review

Backend in `backend/tests/safety/test_safety_review.py`; E2E in `e2e/tests/safety-review.spec.ts`; frontend in `frontend/src/features/safety/safetyReview.integration.test.tsx` and `frontend/src/auth/screens.test.ts`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US30A-01 to 04 | Arranged venues, no equipment pending, no decision; one that isn't ready, is decided, or is under review; an approved equipment line, unreserved then reserved; a planning event | Safety officer reads the queue | Only the ready one is listed, with name, reference, venues and start; equipment waiting to be reserved keeps it out, and technical support doesn't; Planning is included (AC 1) |
| TC-US30A-05, 06 | A queued event with an approved equipment line; one not queued and never reviewed, a draft, an unknown id | Open it | Only the review fields, the venues, the equipment and the seven items; `404` (AC 2, 9) |
| TC-US30A-07 | Queued event | Approve | `201` with internal notes; one row with reviewer, outcome, checklist and time; `safety_approved_at` and `_by` set; the status unchanged; the coordinator can now confirm (AC 3, 6) |
| TC-US30A-08 | Approve with an item marked issue | — | `422 CHECKLIST_HAS_ISSUES`; nothing stored |
| TC-US30A-09 | Reject with an issue and comments | — | `201`; the event keeps its status and isn't approved; the coordinator's readiness shows the comments; confirming is `409` (AC 4) |
| TC-US30A-10 to 13 | No, empty or blank comments on a rejection; no outcome or two items missing; an unknown item; the database | Review | `422 MISSING_REQUIRED_FIELD` naming `comments`; naming `outcome` and `checklist.<key>`; `INVALID_SAFETY_REVIEW`; both CHECKs refuse (AC 2, 4) |
| TC-US30A-14 to 18 | Under review, confirmed, preparation, cancelled, rejected; an arrangement outstanding; already approved; rejected not yet sent back; a draft or unknown id | Review | `409` with each `reason`; `404` |
| TC-US30A-19 to 22 | A rejected arrangement | The coordinator sends it back; nothing to send, already sent, approved; another coordinator, organiser, officer; reject, send back, approve | Back in the queue marked `resent`, readiness says "Sent for another safety review."; `409` `not_rejected`, `already_requested`, `already_approved`; `404`, `403`, `403`, `401`; confirmed in the end (AC 4) |
| TC-US30A-23 | Reject, then another officer approves | Read the history | Both reviews kept newest first with reviewer, outcome, comments, time; internal notes only here (AC 6) |
| TC-US30A-24, 25 | Reject; a refused review; a failing notifier | — | The coordinator told outcome, comments and the flagged labels; no notice on a refusal; `201`, the review kept, the failure logged (AC 5) |
| TC-US30A-26, 27 | Rejected event | Organiser and coordinator read the outcome; another organiser or coordinator, an officer, nobody | Outcome and comments, no `internal_notes` anywhere in the body; `404`, `404`, `403`, `401` (AC 7) |
| TC-US30A-28, 29 | Coordinator, organiser, Venue staff, Lead, nobody; an officer who created or coordinates the event | Queue, open, review | `403`, `401`; `403 SELF_DECISION_NOT_ALLOWED` (D51) |
| TC-US30A-30 | A Confirmed event with no approved review | Start preparation | `409 SAFETY_NOT_APPROVED`; allowed once approved (AC 8) |
| TC-US30A-31 | Seeded Safety Review Demo | Review, reseed | It is queued; approving removes it; the reseed forgets its reviews and queues it again |
| TC-US30A-40 | Screens | Safety officer's screens | Safety reviews only; no other role has it |
| TC-US30A-41 | Seeded Safety Review Demo (E2E) | Officer rejects with an issue and internal notes; coordinator reads it and sends it back; officer sees the earlier review with notes and approves; coordinator confirms | Coordinator sees the comments and not the notes, Confirm disabled until approval, then Confirmed |
| TC-US30A-42, 43 | Frontend: ready, not ready, decided events | Officer opens Safety reviews | Only the ready event is listed; "No events are waiting for a safety review." |
| TC-US30A-44 | Frontend: queued event | Open it | Event details, venue, equipment and seven items; nothing about the organiser (AC 2, 9) |
| TC-US30A-45 | Frontend: all items satisfactory | Approve | The POST holds outcome, comments, notes and seven items; "Safety approved"; the event leaves the queue |
| TC-US30A-46 | Frontend: nothing answered; a rejection without comments | Approve, Reject | The alert, the comments field marked, nothing sent |
| TC-US30A-47 | Frontend: an issue and comments | Reject | "Safety arrangement rejected", stays in planning, the issue listed; an API `CHECKLIST_HAS_ISSUES` is explained |
| TC-US30A-48 | Frontend: a rejected event | Organiser and coordinator open it | Outcome, comments and issues, never the internal notes; the coordinator's **Send for another review** posts and the panel says "Sent for another safety review." |
| TC-US30A-49 | An online approved event with no booking, beside a queued in-person one | Safety officer reads the queue | Both are listed; the online one has no venues and no start (D72); the queue doesn't fail (AC 1) |

### SCRUM-100 / US30b — Request changes after a safety review

Backend in `backend/tests/safety/test_safety_review.py` (the US30b section at the end); E2E in `e2e/tests/safety-review.spec.ts` (one journey with US30a's, because the seeded demo is shared); frontend in `frontend/src/features/safety/safetyReview.integration.test.tsx`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US30B-01 | A queued approved event | Safety officer requests changes (venue, layout), with comments | `201`; one `changes_requested` row with the areas in the form's order; the status unchanged; no safety approval; the readiness list says what was asked, and confirming is `409` (AC 1, 2) |
| TC-US30B-02 | A planning event | Request changes | It stays `planning` (AC 2) |
| TC-US30B-03 | No, empty, or blank comments; no or empty areas | Request changes | `422 MISSING_REQUIRED_FIELD` naming `comments`, `areas` or both; nothing stored (AC 1) |
| TC-US30B-04, 05 | An unknown area; areas on an approval or a rejection; a repeated area | Review | `422 INVALID_SAFETY_REVIEW` naming `areas`; the repeated one is kept once, in the form's order |
| TC-US30B-06 | No checklist; a checklist with no issues | Request changes | `422` for the first; `201` for the second (the seven items are still answered) |
| TC-US30B-07 | A `changes_requested` row with no or blank comments, no or empty areas | Insert | The database refuses it |
| TC-US30B-08 | An approved booking and a reserved equipment line | Request changes (venue, equipment) | Nothing is reset: the line, the booking and the readiness of both stay complete (AC 2, the 13 Oct change) |
| TC-US30B-09, 10 | Request changes; a refused request; a failing notifier | — | The coordinator told by `safety_changes_requested` with the comments, the area labels and the flagged items, and not by `safety_review_decided`; no notice on a refusal; `201`, the review kept, the failure logged (AC 3) |
| TC-US30B-11 | Changes requested | Officer lists the queue; reviews again | It's gone; `409 awaiting_revision` (AC 4) |
| TC-US30B-12 | Changes requested | The coordinator marks them done | `200`, `pending`; back in the queue marked sent back; the readiness list says "Sent for another safety review." (AC 4) |
| TC-US30B-13 | Changes requested, marked done | The officer approves | `201`; the history keeps both, newest first, with the areas and the internal notes; the coordinator can confirm (AC 4) |
| TC-US30B-14 | A second request for changes after the first was marked done | Read the outcome | State `changes_requested`; both reviews listed with their areas |
| TC-US30B-15 | Changes requested | Another coordinator, an organiser, the officer, nobody; the assigned coordinator twice | `404`, `403`, `403`, `401`; `200`, then `409 already_requested` |
| TC-US30B-16 | Changes requested | Organiser, coordinator and Lead read the outcome | State, areas and comments; no `internal_notes` anywhere in the body (AC 3) |
| TC-US30B-17 | A coordinator and an organiser; nobody; an officer who coordinates the event | Request changes | `403`; `401`; `403 SELF_DECISION_NOT_ALLOWED` (D51) |
| TC-US30B-18 | Under review, confirmed, preparation, cancelled, rejected | Request changes | `409` reason `status`; nothing stored |
| TC-US30B-19 | Seeded Safety Review Demo | Request changes, reseed | `201`; the reseed forgets it and queues the demo again |
| TC-US30B-30 | Seeded Safety Review Demo (E2E) | Officer rejects; the coordinator sends it back; the officer requests changes (venue, layout); the coordinator sees them and marks them done; the officer sees the earlier review and approves; the coordinator confirms | The coordinator sees the areas and comments, Confirm disabled until approval; the officer's second review shows "Areas to review: Venue, Layout"; then Confirmed |
| TC-US30B-31 | Frontend: queued event | Open it | The five area tick boxes (Venue, Layout, Equipment, Accessibility, Other) and **Request changes** (AC 1) |
| TC-US30B-32 | Frontend: no area, or no comments | Request changes | The alert, the comments field marked, nothing sent (AC 1) |
| TC-US30B-33 | Frontend: layout flagged, venue and equipment ticked, comments | Request changes | The POST holds the outcome, areas, comments and notes; "Changes requested" with the areas; the event leaves the queue (AC 1, 2) |
| TC-US30B-34 | Frontend: a request for changes | Organiser opens the event | The areas, the comments and the flagged item; never the internal notes; no button (AC 3) |
| TC-US30B-35 | Frontend: a request for changes | Coordinator opens the event | The readiness list says what was asked, Confirm is disabled; **Mark changes done** posts and the panel says "Sent for another safety review." (AC 3, 4) |
| TC-US30B-36 | Frontend: changes marked done | Officer opens the event | The earlier review is in the history with its areas and internal notes (AC 4) |
| TC-US30B-37 | Frontend: a planning event | Request changes | "Changes requested", and it says the event stays in planning |
| TC-US30A-50 | Frontend: an Approved event | Reject | "Safety arrangement rejected", and it says the event stays in approved, not planning |

### SCRUM-107 / US31 — View my notifications

Backend in `backend/tests/notification/test_recorder.py` and `test_inbox_api.py`; frontend in `frontend/src/features/notifications/notifications.integration.test.tsx` and `frontend/src/auth/screens.test.ts`; E2E in `e2e/tests/notifications.spec.ts`.

| ID | Given | When | Then |
|---|---|---|---|
| TC-US31-01 | The `Notifier` protocol | List its methods | Every one is in the recorder's test table, so a new notice can't be raised without being kept (AC 6) |
| TC-US31-02 | Each of the 23 `Notifier` methods | Called with the recipient's email | One row for that user: the kind, the event name, the sentence, the event found from its id, reference, booking, equipment line or registration; the call is still logged through the wrapped notifier (AC 2, 6) |
| TC-US31-03 | The same address in another case | A notice | The same person's row |
| TC-US31-04 | An address no user holds | A notice | Nothing kept, a warning logged, the call still logged |
| TC-US31-05 | A reference no event has | A notice | Kept, with no event |
| TC-US31-06, 07 | No session can be opened; a row the database refuses | A notice | Logged, never raised; the session stays usable |
| TC-US31-08 | The app's `get_notifier` | Read it | The recording notifier over the logging one |
| TC-US31-09 | A Lead assigns a request | The coordinator and organiser list their notifications | Each has one, naming the event and what happened, unread; the Lead has none (AC 6) |
| TC-US31-10 | A transaction holding the event's row lock | A notice for that event | Recorded at once, without waiting for the lock |
| TC-US31-11 | An event at 20:00 UTC | A notice naming its time | Written as the next day, 04:00 SGT (Singapore time, TC-X-01) |
| TC-US31-20 | Two of mine, one of someone else's | List | Mine only, newest first, with id, kind, event, event name, sentence, time, read and `can_open` (AC 2) |
| TC-US31-21 | Nothing | List | `200`, empty, `unread_count` 0 |
| TC-US31-22 | Every role, and a two-role user | List | Each their own; no identity `401`; inactive `403` (AC 1, 2) |
| TC-US31-23 | Five, one read | List with `limit=2`; the count route | Two listed; `unread_count` 4 and the count route agrees (AC 3) |
| TC-US31-24, 25 | Read and unread; `limit` 0, 101, abc | `unread_only`; list | Only the unread; `422` |
| TC-US31-26 | Two unread | Mark one read, twice | `200` both times, the first time kept, the count down by one (AC 4) |
| TC-US31-27 | Someone else's; an unknown id; no identity | Mark read | `404`; `404`; `401`; theirs stays unread |
| TC-US31-28 | Mine, read and unread, and someone else's | Mark all read, twice | `updated` 2 then 0; theirs untouched; `401` without identity (AC 4) |
| TC-US31-29 | The organiser, the assigned coordinator, a Lead, another organiser and coordinator, Venue staff; a draft; no event | List | `can_open` true for the first three, false for the rest and for a draft or no event; the notice names the event either way (AC 5) |
| TC-US31-30 | A notification with an event | Mark it read | The answer carries `can_open` too |
| TC-US31-31 | A blank kind or sentence | Insert | The database refuses it |
| TC-US31-32, 33 | A new row; the table | Read it; inspect it | Unread and stamped; no foreign keys (D116) |
| TC-US31-40 | Frontend: three unread, one read; another user's | Open any screen | The header link says "Notifications, 2 unread" with the count, on every screen (AC 1, 3) |
| TC-US31-41 | Frontend: all read | Open | The link shows no count |
| TC-US31-42 | Frontend: Venue staff | Open | Their own count, not Tech support's |
| TC-US31-43, 44 | Frontend: the count can't be read; a new one arrives | Open; change screen | The link stays without an error; the count is read again on the change (AC 3) |
| TC-US31-45 | Frontend: mine, newer and older, and someone else's | Open Notifications | Mine only, newest first, each with event, sentence and time (AC 2) |
| TC-US31-46 | Frontend: one unread, one read | Open | The unread one is marked, with "1 unread" (AC 3) |
| TC-US31-47, 48 | Frontend: none; the list can't be read | Open | "You have no notifications yet." with Mark all disabled; the alert |
| TC-US31-49 | Frontend: two unread | Mark one as read | The mark goes, the link says 1 unread, one POST (AC 4) |
| TC-US31-50 | Frontend: two unread | Mark all as read | The marks and the count go, one POST, the button disables (AC 4) |
| TC-US31-51 | Frontend: the API refuses | Mark as read | The alert; still unread |
| TC-US31-52 | Frontend: one openable, one not, one with no event | Open Notifications | **Open request** on the first only (AC 5) |
| TC-US31-53 | Frontend: the organiser's request | Open request | Their request opens, and the notification is read (AC 4, 5) |
| TC-US31-54, 55 | Frontend: a coordinator's assigned request; a Lead's | Open request | The coordinator's Review request screen; the Lead's Event requests screen (AC 5) |
| TC-US31-56 | Frontend: a request that isn't the organiser's any more | Open request | "This request is no longer available to your account." |
| TC-US31-57 | Every role's screens | List them | Notifications is last (AC 1) |
| TC-US31-60 | Seeded organiser, Lead and coordinator (E2E) | The organiser submits, the Lead reads the notice and assigns, the coordinator and organiser read theirs and open the request, the organiser marks all read | The link shows the unread count; each notice names the event and what happened; Open request shows the request; the count clears (AC 1 to 6) |

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

### SCRUM-15 / US12 — Edit event details during planning

Test cases TC-US12-01 to 25 in full, with a screenshot per AC: `docs/testing/US12-edit-event.md`. Backend `tests/event/test_event_edits.py`; frontend `src/features/eventEdit/eventEdit.integration.test.tsx`; E2E `e2e/tests/event-edit.spec.ts`.

### SCRUM-97 / US29a — Request a change to a submitted event

Test cases TC-US29A-01 to 24 in full, with evidence per AC: `docs/testing/US29a-change-request.md`. Backend `tests/event/test_change_requests.py`; frontend `src/features/changeRequest/changeRequest.integration.test.tsx`; E2E `e2e/tests/change-request.spec.ts`.

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
| SCRUM-37 | Offer expiry / decline | TC-US7-10, 11; since SCRUM-137 expiry is on read (D2), TC-US7-16 to 24, and `POST /expire-offer` is for tests |
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

### SCRUM-83 (US10e)

One PR, no subtasks in Jira.

| Work | Done when |
|---|---|
| Migration `20261030_1200_us10e_reassign`; `reassign` and `request_transfer`; `event_reassigned` and `transfer_requested`; D54 access limits | TC-US10E-01 to 24 (`tests/event/test_reassignment.py`) |
| Reassign screen in the Lead's request view; reason in the history; `server.ts` handler | TC-US10E-25 to 28; lint + build |
| SCRUM-146: Request a transfer for the assigned coordinator (review screen and Events screen); `server.ts` handler | TC-US10E-29 to 34; lint + build |

### SCRUM-85 (US18)

Test cases in full, with screenshots of each acceptance criterion: `docs/testing/US18-confirm-event.md`. One PR. The ticket's subtasks: widen D11, readiness check, confirm endpoint, Preparation status and transition, frontend readiness panel and confirm button, notifier, tests.

| Work | Done when |
|---|---|
| Migration `20261109_1200_us18_confirm`; `preparation` status; widen D11 for the assigned coordinator; registration open through Preparation | TC-US18-22, 23, 27, 28 |
| `confirmation_service` (readiness, confirm, start preparation) and its three routes; `event_confirmed` notifier | TC-US18-01 to 21, 24 to 26 (`tests/event/test_confirmation.py`) |
| Seeded **Confirmation Demo** | TC-US18-29, 30 |
| `EventConfirmation` panel on the review screen; `server.ts` handlers | TC-US18-31 to 37; lint + build |

### SCRUM-99 (US30a)

Test cases in full, with screenshots of each acceptance criterion: `docs/testing/US30a-safety-review.md`.

One PR, on top of SCRUM-85 (it sets the safety columns US18 reads). The ticket's subtasks: `safety_reviews` table and status step, endpoints, Safety Officer queue and checklist form, Organiser view, notifier, tests.

| Work | Done when |
|---|---|
| Migration `20261110_1200_us30a_safety`; `safety_reviews`; derived state (D92), no status step (deviation 62) | TC-US30A-01 to 04, 13, 31 |
| Queue, review view, decision, send back; `safety_review_decided`; the Preparation guard | TC-US30A-05 to 30, 49 (`tests/safety/test_safety_review.py`) |
| Safety officer's screen; `SafetyOutcome` for organiser and coordinator; `server.ts` handlers; seeded Safety Review Demo | TC-US30A-40 to 48; lint + build |

### SCRUM-100 (US30b)

Test cases in full, with screenshots of each acceptance criterion: `docs/testing/US30b-request-changes.md`. One PR, stacked on SCRUM-99 (it extends the review, the state and the send-back).

| Work | Done when |
|---|---|
| Migration `20261113_1200_us30b_changes`; `changes_requested` and `areas`; derived state (D99) | TC-US30B-01 to 08, 19 |
| Request changes, the notice, the queue, marking them done, the history | TC-US30B-09 to 18 (`tests/safety/test_safety_review.py`) |
| Request changes and the areas on the officer's screen; the areas and **Mark changes done** on the outcome panel; `server.ts` handlers | TC-US30B-30 to 37, TC-US30A-50; lint + build |

### SCRUM-107 (US31)

Test cases in full, with screenshots of each acceptance criterion: `docs/testing/US31-view-notifications.md`. One PR. The ticket has no subtasks: migration and model, the recording notifier, the inbox API, the Notifications screen and link, tests.

| Work | Done when |
|---|---|
| Migration `20261116_1200_us31_notifications`; `Notification`; no foreign keys (D116) | TC-US31-31 to 33 |
| `RecordingNotifier` for every `Notifier` method; `get_notifier` | TC-US31-01 to 11 (`tests/notification/test_recorder.py`) |
| `GET`/`POST /api/v1/me/notifications`, `unread-count`, `read`, `read-all`; `can_open` | TC-US31-20 to 30 (`tests/notification/test_inbox_api.py`) |
| Notifications screen; unread count on the link; Open request; `server.ts` routes | TC-US31-40 to 57; TC-US31-60; lint + build |

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

### SCRUM-88 (US21)

Test cases in full: `docs/testing/US21-venue-calendar.md`. Decisions D56 to D61, deviations 50 and 51.

| PR | Subtask | Work | Done when | PR # |
|---|---|---|---|---|
| PR 1 | SCRUM-122 | `GET /api/v1/venues/{id}/calendar`: live bookings with their stored occupied windows, and blocks, over a range of Singapore days; `CALENDAR_ROLES`; the reference rule (D58); `INVALID_DATE_RANGE` (exactly `YYYY-MM-DD`); a cancelled event's live bookings shown (D60, the PO's decision of 30 Oct); `venue_service.visible`, shared with `GET /venues/{id}`, which also lets Leads see inactive venues (D61) | TC-US21-01 to 14 pass; the route is in US16b's role matrix (TC-US16B-14); whole backend suite green | #92 |
| PR 2 | SCRUM-123 | The calendar on Venues for Coordinator, Lead and Venue staff: venue picker, week and month views, buffers and closed hours drawn, item details; `calendarGrid.ts`; `venueApi.calendar`; the fake backend's calendar route and `seedBlock` (`frontend/src/test/server.ts`); `eventName` shared in `bookingApi.ts` | TC-US21-15 to 24 pass; lint and build clean | |

### SCRUM-92 (US24)

Test cases in full: `docs/testing/US24-multi-venue.md`. Decisions D65 to D73, deviation 53. AC 5's "the others go only when the event is cancelled" is US9's (SCRUM-12, D60).

| PR | Subtask | Work | Done when | PR # |
|---|---|---|---|---|
| PR 1 | SCRUM-127 | Migration `20261103_1200_us24_multi_venue`: `purpose`, `is_primary`, `preparation_status`, `venue_bookings_one_primary_per_event`, backfills; seed primary bookings and Multi-Venue Conference Demo | TC-US24-01 to 04 pass; one alembic head; downgrade and upgrade round-trip; whole backend suite green | |
| PR 2 | SCRUM-128 | Create with purpose, schedule check (D65) and first-is-primary; make primary; withdraw from Approved; the Organiser's read; `venues_arranged` (with the allocations covering expected attendance, D67); Venue staff set preparation status (D73); attendee endpoints from the primary venue (D70) and their E2E text; migration `20261105_1200_us24_bookings_api` (D66's default dropped, D77); the booking form's Purpose field | TC-US24-05 to 19 and 28 pass; whole backend and E2E suites green | |
| PR 3 | SCRUM-129 | The booking form's schedule and allocation; the coordinator's venues panel (purpose, allocation, status, preparation, Primary, arrangements, Make primary, withdraw an approved venue); the Organiser's read-only Venues section; Venue staff's preparation control in the calendar (D78); the mock; `preparation_status` on the calendar and `start_at`/`end_at` on the request read (deviation 55) | TC-US24-20 to 27 and 29 pass; lint and build clean | |

### SCRUM-90 (US23a)

Test cases in full: `docs/testing/US23a-venue-unavailability.md`. Decisions D113 to D115, deviations 72 and 73. Two PRs: the schema alone, then the API and screens together (the story owner's choice, 2 Nov). Replacing or restoring an affected booking, and the event's return to Planning, are US23b's (SCRUM-91).

| PR | Work | Done when |
|---|---|---|
| PR 1 | Migration `20261116_1200_us23a_blocks`: block `reason` and `created_by_user_id`; the booking's rearrangement marker; seeded block's reason | TC-US23A-01 to 03; one Alembic head |
| PR 2 | Record a block (Venue staff), mark overlapping bookings and holds, notify each affected event's coordinator and organiser; Needs rearrangement on the event's venues; the reason on the calendar; Venue Unavailability Demo | TC-US23A-04 to 21; frontend lint, tests and build; E2E |

### SCRUM-91 (US23b)

Test cases in full: `docs/testing/US23b-replacement-venue.md`. Decisions D117 and D118, deviations 75 and 76. Two PRs: the schema alone, then the API and screens together (the story owner's choice, 3 Nov). Built on US23a (SCRUM-90).

| PR | Work | Done when |
|---|---|---|
| PR 1 | Migration `20261117_1200_us23b_replacement`: the `replaced` status and `replaced_at`; `replaces_booking_id` with one live replacement each; the restore request; ending a block early | TC-US23B-01 to 04; one Alembic head; downgrade and upgrade round-trip |
| PR 2 | Move an affected Confirmed or Preparation event back to Planning; search and request a replacement from the notice; Replaced once it's approved; end a block early, ask to restore and Venue staff confirm; tell attendees once a replacement changes what they see; Replacement Venue Demo | TC-US23B-05 to 22; frontend lint, tests and build; E2E |

### SCRUM-7 (US2)

Test cases in full: `docs/testing/US2-venue-search.md`. No subtasks in Jira; one PR, rebased on US22 PR 1 (#64).

| Work | Done when |
|---|---|
| `venue_blocks` table + seeded slot | TC-US2-11, 12; one Alembic head |
| `GET /api/v1/venues/available` | TC-US2-01 to 10 (AC 1–8) |
| Search form on Venues (Coordinator, Venue staff) | Frontend unit + integration; TC-US2-13 to 16 (E2E); lint + build |

### SCRUM-96 (US28)

Test cases in full: `docs/testing/US28-view-registrations.md`. No subtasks in Jira; one PR, no schema change.

| Work | Done when |
|---|---|
| Backend list endpoint with access check | TC-US28-01 to 15 |
| Registrations view (Organiser, Coordinator) | Frontend integration; TC-US28-16, 17 (E2E); lint + build |

### SCRUM-84 (US17)

Test cases in full: `docs/testing/US17-approve-reject-request.md`. No subtasks in Jira; one PR, the migration in its own first commit.

| Work | Done when |
|---|---|
| Decision columns + CHECKs | TC-US17-15; one Alembic head |
| Decision endpoint + status guard; `Notifier.request_decided` | TC-US17-01 to 14 |
| Approve / Reject + reason on the review screen; outcome on the organiser's request | Frontend integration; TC-US17-16, 17 (E2E); lint + build |

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

Test cases in full: `docs/testing/US16b-role-based-access.md`, mirroring the subtasks in Jira. Decisions D45 to D51 (§9).

| Subtask | Work | Done when | PR |
|---|---|---|---|
| SCRUM-119 | `users.roles` replaces `users.role`; `venue_staff` and `safety_officer`; checks on held roles; `/me` returns `roles`; `operations_manager` retired (D49); seed one user per role and `multi.role@smu.edu.sg` (D50) | TC-US16B-01 to 08, 24; one Alembic head. `/me` keeps `role` next to `roles` until SCRUM-121 (PR #86 review) | #87 |
| SCRUM-120 | Coordinators scoped to assigned events for the queue, details, thread and clarifications, with the thread following a reassignment (D48); no one decides a record they created, with `SELF_DECISION_NOT_ALLOWED` and CHECKs on bookings and equipment lines (D51, migration); organiser scope tested (D47); attendee, role-matrix and Lead checks; clarification E2E gains the assign step | TC-US16B-09 to 16, 25, 26, 28, 29, 31; one Alembic head | #88 |
| SCRUM-121 | Role switcher and navigation per current role (D46); Safety officer's "no screens yet"; **Acting as** gains Safety officer (Venue staff is already there and now sends a real `venue_staff` user); `/me` drops `role`; `SELF_DECISION_NOT_ALLOWED` shown on the row (D51) | TC-US16B-17 to 23, 27, 30, 32; lint + build; E2E | #91 |

### SCRUM-15 (US12)

Test cases in full: `docs/testing/US12-edit-event.md`. No subtasks in Jira; one PR, the migration in its own first commit.

| Work | Done when |
|---|---|
| Change request and audit tables | TC-US12-19; one Alembic head |
| Coordinated events, details, edit and history endpoints; seeded Event Planning Demo | TC-US12-01 to 18, 20, 26 |
| Events screen: list, Edit, form, changes awaiting approval, History | Frontend integration TC-US12-21 to 25; E2E TC-US12-20 to 23; lint + build |

### SCRUM-97 (US29a)

Test cases in full: `docs/testing/US29a-change-request.md`. One PR; the Jira subtasks are its commits.

| Subtask | Done when |
|---|---|
| `event_change_requests` table (`reason` on US12's) | TC-US29A-12, 18; one Alembic head |
| Create endpoint (and the organiser's list) | TC-US29A-01 to 11, 16, 17 |
| Notifier | TC-US29A-13 to 15 |
| Frontend request form | TC-US29A-19 to 24; lint + build |
| Tests | All of the above |

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
SCRUM-6 says "a fixed window to accept" and names no duration. *Sprint 1 default:* 24 hours, as a single module-level constant `WAITLIST_OFFER_WINDOW = timedelta(hours=24)`. One constant, one edit if it changes. **Decided via the SCRUM-137 bug fix, 31 Oct:** 24 hours.
 
**D2 — What expires an offer?**
SCRUM-37 says the expiry handling is itself "pending team decision". **Decided via the SCRUM-137 bug fix, 31 Oct:** expiry on read. Any read or change of an event's registrations first expires its lapsed offers and passes each place on, in its own locked transaction (`expire_lapsed_offers`; §1a "Lapse on read"; §3 `expire-offer`). `POST /expire-offer` stays, for tests.
 
**D3 — Is a waitlisted person an attendee or just an email?**
Real inconsistency between two stories: SCRUM-2 says the attendee is "offered to be put on a waitlist **using their email**", implying email is enough; SCRUM-5 says a waitlisted entry appears in that attendee's "My Events" with a position, which requires an `attendee_id`. *Sprint 1 default:* store both — `attendee_id` when the caller is authenticated, `attendee_email` always. Flag it; the team should pick one. **Decided via the SCRUM-136 bug fix, 31 Oct:** joining a waitlist requires login, and every new entry has an attendee (with D7); email-only rows made before stay, and one is linked to its attendee when they try to join.
 
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
- The in-app Notifications view (US31, SCRUM-107) keeps every notice the notifier raises and shows it to its recipient; email, push and real-time delivery are still out of scope
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
 
Verify with `pyjwt[crypto]` and a cached `PyJWKClient`, checking `audience="authenticated"` and `issuer=<url>/auth/v1`. The claims we need are `sub` (stable Supabase user id) and `email`. One token check resolves the `users` row; `get_current_user` and `get_current_attendee` both build on it, and the roles come from `users.roles` (`users.role` until SCRUM-119).
 
### Linking to `users`
 
Our rows have their own UUIDs, and seeded ones come from `uuid5`, so no Supabase user sits behind them. A column links them rather than repurposing the primary key. **Done in SCRUM-101** (migration `20261015_1200_us16a_auth_link`; full DDL in §2):
 
```sql
alter table users
  add column auth_user_id uuid,
  add constraint users_auth_user_id_key unique (auth_user_id),
  add column full_name    text;
```

There's deliberately no foreign key to `auth.users(id)`: the test database has no `auth` schema, and a FK would block deleting a user in Supabase.
 
Every attendee has a `users` row with the same id, so linking `users` covers attendees too. The token check (SCRUM-102, `app/user/dependencies.py`): verify token → look up by `auth_user_id` → else **look up an unlinked, active Organiser or Attendee by email (ignoring case, row locked) and link it, if the token says the email is verified** → else `403 PROFILE_REQUIRED`, and the first login after confirming the email creates the profile with `POST /api/v1/auth/profile` (SCRUM-103, §3). Matching on email keeps the seeded demo accounts working the moment the real person signs in, instead of creating duplicates. Staff rows are never linked by email (deviation 20); the seed links them (SCRUM-104). Since SCRUM-119 that means every role the row holds must be Organiser or Attendee: a row that also holds any staff role isn't linked by email (TC-US16B-08), or the email's owner would get that role.

**"Confirm email" is on** in the Supabase dashboard (Authentication → Sign In / Providers → Email), decided in the PR #55 review: sign-up sends a confirmation link, and no session exists until it's clicked, so nobody can log in as an email they don't own. Supabase's built-in email service is rate-limited and meant for testing; real sign-ups need a custom SMTP provider.

The key fetch is built on the first token, not at startup, and uses certifi's CA bundle: python.org's macOS Python has none, which would fail every login. Supabase unreachable is `503 AUTH_UNAVAILABLE` and `SUPABASE_URL` unset is `500 AUTH_NOT_CONFIGURED`, so neither looks like a bad token. The backend logs a warning at startup while `AUTH_DEV_HEADERS` is on.
 
### Consequences to keep in mind
 
- **Tests must not reach the network.** Keep the dependency overridable, or inject the verifier so tests supply claims directly. The existing suite should need nothing beyond the fixture.
- RLS stays on with no policies. The browser only calls Supabase Auth and the Data API stays disabled, so the publishable key reads no tables. Policies are needed only if the Data API is ever enabled; until then FastAPI's role checks (US16b) are the access control. New tables still enable RLS in their migration.
- **CORS already allows `Authorization`** (`allow_headers=["*"]`). Cookie-based sessions would instead need `allow_credentials=True` and specific origins.
 
### Seeded logins (SCRUM-104)

Staff can't sign up (US16a AC 7), so `python -m app.seed` creates a confirmed Supabase login for each seeded user (`SEEDED_LOGIN_EMAILS`: the organiser, the coordinator, venue staff, Tech support, the Safety officer, the two-role user, the two Coordinator Leads and the four demo attendees; 12 since SCRUM-119) through the Admin API, then links each row by `auth_user_id`. It needs `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (`sb_secret_…`) and `SEED_AUTH_PASSWORD` in `backend/.env`; without them it prints that logins were skipped and seeds everything else as before. Every login it creates carries `app_metadata.seeded_by = "app.seed"`. An account that already exists is found by email and reused, password unchanged, **only if it has that mark and a confirmed email**; anyone can sign up with an unused staff address first, so any other account is refused and nothing is linked (PR #56 review). A row already linked to a different account is never re-pointed. Every login is fetched and checked before any row is linked, so a failure (an Admin API refusal, a timeout or a malformed reply) names the email and links nothing, and `python -m app.seed` exits 1. The key and password are `SecretStr` in `Settings`; the password must be at least 12 characters. Demo accounts only: they share one password. The nine logins were created on Supabase on 24 Oct (for the SCRUM-105 login E2E) and marked the same day. SCRUM-119 adds `safety.officer@smu.edu.sg` and `multi.role@smu.edu.sg`. A local seed creates their logins in the shared Supabase Auth project at once, but their `users` rows reach the Supabase database only with the post-merge migration and reseed; until then, signing in as either asks for a profile.

Sources: [Supabase JWTs](https://supabase.com/docs/guides/auth/jwts), [API keys](https://supabase.com/docs/guides/api/api-keys).
 
---
 
### US16b role-based access: decisions (25 Oct)

SCRUM-82 had no subtasks or test cases. Before any code, the story owner (Calvin) checked each AC against the code and took six decisions, recorded as D45 to D50; the PR #86 review added a seventh, D51, and refined D47 and D48. Matthew, as acting PO, decided D47 and D51 on 25 Oct. They shape the three subtasks: SCRUM-119 (backend, roles as a list), SCRUM-120 (backend, scope and refusals) and SCRUM-121 (frontend, role switcher). Test cases TC-US16B-01 to 32 are in Jira and `docs/testing/US16b-role-based-access.md`.

**Where the code stood:** every user had exactly one role (`users.role`); `venue_staff` and `safety_officer` didn't exist, and `operations_manager` stood in for Venue Staff (D19) across the backend, frontend, tests and E2E. Staff routes already refused other roles (`403`), venue booking and equipment were already scoped to the assigned coordinator (D20), and attendees already couldn't reach any staff route. Two gaps went beyond the role list: any coordinator could read every submitted request and send it a clarification (D11, D14), and AC 4 speaks of "organisations", which the data model doesn't have.

| # | Decision | Logic and reasoning | Alternative considered, and why not | Consequence |
|---|---|---|---|---|
| D45 | **Roles are a list column on `users`** (`roles user_role[]`, at least one, no repeats), replacing `users.role` | AC 1 changed "exactly one role" to "one or more". A list keeps one row per user, so every check stays a membership test (`role in user.roles`) and queries use `= ANY(roles)`. Named CHECKs enforce "at least one" and "no repeats" in the database. The role set is small and fixed by the customer | A `user_roles` join table: more normalised, but every role check becomes a join or an extra query, and nothing needs per-role metadata (dates, scopes) yet. If it ever does, the list migrates cleanly to a table | One migration in SCRUM-119 rewrites every `user.role` check; `/me` returns `roles`. The downgrade refuses while anyone holds two roles |
| D46 | **The API authorises by every role a user holds**; the current role lives only in the frontend | AC 3 says a user is refused for a role they *don't hold*, not one they aren't currently using. Holding is the security boundary, and the switcher (AC 2) is about what the user sees. Keeping the API stateless about the current role means no header to forge or forget, and every existing route works unchanged | Sending an active-role header and refusing everything else: stricter than AC 3 asks, adds a header to every call and a new way to be refused, and a user could still switch it freely, so it adds no real protection | SCRUM-119 changes `require_user_roles` to "holds any of"; SCRUM-121 builds the switcher and filters navigation by the current role |
| D47 | **An organiser's "organisation" is the organiser themselves**: another organiser's request is `404` | No AC, field or sign-up step defines an organisation; the only data is who created a request. Owner-only already gives AC 4's outcome: "another organisation's request behaves as if it doesn't exist" (D11 returns `404`). So the AC is met without inventing a model nobody specified | An `organisations` table with members: sign-up would have to ask for one, and requests would belong to it. No AC asks for that, and it would change US1 and US16a. Raise it with the PO if organisations really share requests | Tested as AC 4 in SCRUM-120 (TC-US16B-12). **Decided by the acting PO on 25 Oct:** colleagues at one organisation must not see or work on each other's requests, so owner-only is the rule and no organisations model is planned, now or later |
| D48 | **Coordinators see and act only on requests assigned to them**: the review queue, a request's details and thread, and sending a clarification; anyone else `404` | AC 5: "An Event Coordinator can only manage events assigned to them." Since US10a, every request a coordinator should work on is assigned by a Lead first, so the assignment is the right boundary. D14 itself said to tighten to the assigned coordinator once assignment existed. It also matches D20 (venues) and equipment, so there's one rule for coordinators everywhere. `404` rather than `403` follows D11: a request you can't see behaves as if it doesn't exist | Leaving D11 and D14 as they were: every coordinator could keep reading and clarifying every submitted request, which contradicts AC 5 | SCRUM-120 retires D14 and narrows D11 for coordinators; Leads keep their view. **No coordinator can clarify an unassigned request**, and **on reassignment the thread follows the request** (PR #86 review): access goes by the event's current coordinator, so the new one reads and continues it and the old one loses it, and the organiser's open question isn't stranded (TC-US16B-26; reassigning itself is SCRUM-83). The clarification E2E journey gains a Lead-assign step, since a coordinator no longer sees a request straight after it's submitted |
| D49 | **`operations_manager` is retired**: its users become `venue_staff`; nothing checks it any more | It was only ever a stand-in until US16b added the real role (D19), and keeping it would make "Venue Staff" mean two values. Postgres can't drop an enum value, so it stays in `user_role`, unused | Keeping both, with `operations_manager` meaning Venue Staff: two names for one job and checks that must list both | SCRUM-119 migrates the users, `VENUE_STAFF_ROLES` becomes `venue_staff`, and the seed and **Acting as** follow |
| D50 | **The two-role seed user is `multi.role@smu.edu.sg`, Coordinator and Venue staff** | US16b's subtask note asks for "one user with two roles". Both roles have their own screens (Event requests; Venues with the pending list), so switching visibly changes navigation in the E2E check (TC-US16B-23). They're also a realistic pairing: a coordinator who also helps run venues | Organiser and Attendee: both can be self-signed, so it says little about staff, and attendee screens use a different identity path. Pairings with Tech support or Safety officer: one side has few or no screens yet | The seed adds the user with a Supabase login; the login E2E uses it |
| D51 | **No one decides a record they created**, anywhere in the application, whatever roles they hold. Venue bookings: approve or reject refused if the decider requested it **or is the event's current coordinator**. Equipment lines: the same for reviewing. Assignment: a Lead can't assign a request they created, and a request can't be assigned to its creator. Event requests (US17, SCRUM-84) inherit it | Raised in the PR #86 review and **decided by the acting PO (Matthew) on 25 Oct**, who asked for it to be a rule of the whole application, not only bookings and equipment. Because the API checks every role a user holds (D46), one person holding two roles could otherwise ask and approve: book a venue as Coordinator and approve it as Venue staff, approve their own equipment lines, assign their own request as Lead, or (as Organiser and Coordinator or Lead) approve their own event request once US17 exists. The person asking mustn't be the person deciding. **The event's current coordinator is excluded too:** otherwise, after a reassignment, a new coordinator who is also Venue staff could approve a booking the previous coordinator made for the event they now run. **Assigning a request to its creator is refused**, so nobody coordinates, or clarifies, their own request (D48 then keeps them out of it). | Blocking only the exact requester on bookings and equipment: narrower, but it leaves event requests, assignment and the reassignment case open. Allowing it: rejected by the PO | SCRUM-120: service checks returning `403 SELF_DECISION_NOT_ALLOWED` (a new error code; assigning to the creator is `422 INVALID_COORDINATOR` with `reason: created_the_request`), plus a migration with CHECKs that a booking's decider and an equipment line's reviewer differ from its requester. No seeded or Supabase row breaks them (checked 25 Oct). The event-coordinator and assignment rules span tables, so they're service checks. TC-US16B-25, 28, 29. SCRUM-121 shows the refusal as a readable message on the row (TC-US16B-30) rather than hiding Approve and Reject. SCRUM-84 (Nicholas) has a comment with the rule and a proposed test case |
| D55 | **Venue Staff don't read event requests** (taken while building SCRUM-120, PR #88 review asked for it as its own decision) | AC 3 refuses what a role doesn't need, and Venue Staff's job is venues and bookings: the pending list already names each booking's event. Their read access came only from D19, when `operations_manager` stood in for them and could read the queue (D11). With D46, a user's roles add up, so `multi.role` (Coordinator and Venue staff) would read every request through Venue staff, and D48 would hold only for single-role coordinators | Keeping read access for Venue Staff, perhaps to approved requests only: nothing in US4 or US22 needs it, and D48 would leak through any two-role coordinator | SCRUM-120 makes the queue Coordinator and Lead only, and a request's details and thread Organiser, Coordinator and Lead only; Venue Staff, and other roles without a reading role, get `403` |

These are the story owner's decisions, and the acting PO decided D47 and D51 on 25 Oct (PR #86); D55 (numbered D54 on #88 until #89's D54 landed first) was asked of the acting PO on #88. Each is marked `DECISION-PENDING` in the code when its subtask lands, like the other open decisions.

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
| TC-US7-16 … 24 | SCRUM-137 | A lapsed offer expires on read and passes on, once (D1, D2) |
 
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
| TC-US6A-11 … 15 | SCRUM-136 | (Bug: joining takes the logged-in attendee; D3, D7) |
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
| TC-US28-01 … 05, 13 … 16, 18 | SCRUM-96 | AC 1: only events they own or are assigned to (D52) |
| TC-US28-06, 09, 16 | SCRUM-96 | AC 2: totals for confirmed, waitlisted, offered and remaining capacity |
| TC-US28-07, 08, 11, 16 | SCRUM-96 | AC 3: name/email, status, registration time, waitlist position, answers |
| TC-US28-09, 12, 17 | SCRUM-96 | AC 4: filter by status |
| TC-US28-10, 17 | SCRUM-96 | AC 5: withdrawn and declined hidden unless Show all |
| TC-US17-01, 04, 07, 08, 16 | SCRUM-84 | AC 1: only requests assigned to them, only while Under Review (D48) |
| TC-US17-01, 02, 16, 17 | SCRUM-84 | AC 2: Approved or Rejected |
| TC-US17-02, 03, 14, 17 | SCRUM-84 | AC 3: a reason is required on rejection and stored |
| TC-US17-10 … 12 | SCRUM-84 | AC 4: the organiser is notified, with the reason |
| TC-US17-01, 13, 16, 17 | SCRUM-84 | AC 5: decision recorded with identity and time; the organiser sees outcome and reason |
| TC-US17-05, 06 | SCRUM-84 | AC 6: already Approved, Rejected or Cancelled (and Awaiting Clarification) is refused, unchanged |
| TC-US17-09, 15 | SCRUM-84 | (No self-decision — D51; database CHECKs) |

† §4 doesn't tag an AC for these IDs; they're mapped by what the test checks.
