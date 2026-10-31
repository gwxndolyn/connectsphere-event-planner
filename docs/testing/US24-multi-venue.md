# US24 — Book multiple venues for one event (SCRUM-92): test cases

**Story:** As an Event Coordinator, I want to request more than one venue for the same event so that larger events, such as a conference with breakout rooms, can use several spaces at once.

**Source of truth:** the acceptance criteria in Jira SCRUM-92 (changed 13 Oct). If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Several venue bookings for one event, each with its own venue, window and purpose; each window within the event's schedule.
2. Each venue checked independently for suitability, availability, setup and turnaround, and conflicts, for its own window.
3. Expected attendees allocated to each venue; no allocation exceeds the venue's capacity.
4. Exactly one primary venue. Attendees see only it; the Organiser sees every venue with its status, any unavailability and the next action.
5. One booking can be changed or cancelled without affecting the others; the others go only when the whole event is cancelled.
6. A rejected booking keeps the event in Planning, and approved venues stay attached.
7. Each booking's own approval and preparation status; the event's venues are arranged only when every required booking is approved.

**Decisions:** D65 (the event's schedule), D66 (purpose), D67 (allocations), D68 (primary), D69 (change = withdraw and request again), D70 (attendees' venue; `venue_name` / `room_number`), D71 (the Organiser's view), D72 ("venues arranged"), D73 (preparation status). Deviation 53. D65 follows customer clarification CS3-22, D67 CS3-24, D68 and D70 CS3-25, and D73 CS3-49. All in `claude_instructions.md` §1a, `DECISION-PENDING`. AC 5's "the others go only when the event is cancelled" is US9's (SCRUM-12), as D60 records.

**Delivery:** three PRs.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-127 | Migration `20261103_1200_us24_multi_venue` (`purpose`, `is_primary`, `preparation_status`, `venue_bookings_one_primary_per_event`, backfills); the seed's primary bookings and Multi-Venue Conference Demo | `backend/tests/venue/test_multi_venue_schema.py` |
| 2 | (to create) | Create with purpose, schedule check and first-is-primary; make primary; withdraw from Approved; the Organiser's read; `venues_arranged`; Venue staff set preparation status; attendee endpoints from the primary venue; attendee E2E text | pytest; `attendee-registration.spec.ts`, `events-board.spec.ts` |
| 3 | (to create) | Coordinator's and Organiser's venue screens; Venue staff's preparation control | Vitest; `e2e/tests/multi-venue.spec.ts` |

## Test cases

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US24-01 | 7 | `purpose`, `is_primary` and `preparation_status` are NOT NULL, with the purpose and preparation CHECKs, `preparation_status` defaulting to `not_started`, and the partial unique index; the upgrade gives existing bookings "Main venue" and `not_started` and makes each event's first live booking (by when it was made) primary, none for an event with nothing live; downgrade removes them all and upgrade restores them, keeping bookings whose values are the defaults; downgrade refuses (`RuntimeError`) while a booking has its own purpose or a preparation status past `not_started` | Auto pytest | 1 |
| TC-US24-02 | 4 | A second live (requested or approved) primary for the same event is refused by `venue_bookings_one_primary_per_event`; a withdrawn or rejected primary doesn't block a new one; each event has its own, and non-primary bookings sit beside it | Auto pytest | 1 |
| TC-US24-03 | 1, 7 | A blank, untrimmed or over-100-character purpose is refused by `venue_bookings_purpose_valid`; 1 and 100 characters are accepted. An unknown preparation status is refused by `venue_bookings_preparation_status_known`; `not_started`, `in_progress` and `ready` are accepted, and a new booking is `not_started` | Auto pytest | 1 |
| TC-US24-04 | — | Each in-person seeded event names its venue (no default, so none is assumed); the seed gives each in-person event with a seeded venue one approved primary booking there, over its own times, within capacity; online events and the one with no seeded venue have none; US2's slot bookings are primary; Multi-Venue Conference Demo has an approved primary main hall (preparation `in_progress`), a requested breakout and a rejected one (with a reason) on its preferred day; every other seeded booking is `not_started`; reseeding puts the primary back on the main hall; the seed's summary counts every booking it owns (11) | Auto pytest | 1 |
| TC-US24-05 | 1 | Two bookings for one event at two venues, each with its own window and purpose → both `201` | Auto pytest | 2 |
| TC-US24-06 | 1 | A window outside the schedule (wrong day, before the start, after the end; `start_at`/`end_at` and `preferred_*` cases) → `422 INVALID_BOOKING` on the field; setup before the start is fine | Auto pytest | 2 |
| TC-US24-07 | 1 | A missing or blank purpose → `MISSING_REQUIRED_FIELD` / `INVALID_BOOKING` | Auto pytest | 2 |
| TC-US24-08 | 2 | The same event: one booking refused for a clash, another accepted; outside hours judged per booking | Auto pytest | 2 |
| TC-US24-09 | 3 | An allocation over the venue's capacity → `VENUE_CAPACITY_EXCEEDED`; the sum may exceed expected attendance | Auto pytest | 2 |
| TC-US24-10 | 4 | The first booking becomes primary; later ones don't | Auto pytest | 2 |
| TC-US24-11 | 4 | Make primary moves the flag atomically; refused on a withdrawn or rejected booking (`409`), for another coordinator (`404`) and for Venue staff (`403`) | Auto pytest | 2 |
| TC-US24-12 | 4 | Withdrawing or rejecting the primary leaves none; `next_action` `choose_primary`; not arranged | Auto pytest | 2 |
| TC-US24-13 | 4 | Attendee endpoints (available, register, My events) show the approved primary's name and location; a non-primary venue never; the legacy columns without one | Auto pytest | 2 |
| TC-US24-14 | 4 | The Organiser reads every booking with status, primary, unavailability and next action; another organiser `404`; an attendee `403` | Auto pytest | 2 |
| TC-US24-15 | 4 | `unavailability`: a rejection's reason and alternative; an inactive venue | Auto pytest | 2 |
| TC-US24-16 | 5 | Withdraw an Approved booking: the window is freed, Venue staff are told, and the others' status, windows and primary are unchanged; requesting again works | Auto pytest | 2 |
| TC-US24-17 | 6 | Reject one of two: the event stays `approved` / `planning`; the approved booking stays approved and primary | Auto pytest | 2 |
| TC-US24-18 | 3, 7 | `venues_arranged`: false with a Requested booking, no primary or no bookings; false when the live bookings' allocations add up to less than the event's expected attendance, true at exactly it or more (D67, CS3-24); true when every live one is Approved with one primary and enough allocated; true for an online event; no booking is refused for a shortfall; preparation status doesn't change it | Auto pytest | 2 |
| TC-US24-19 | 4 | E2E (updated): the events board and My events show the seeded events' primary venue; the board's venue search matches it | Auto E2E | 2 |
| TC-US24-20 | 1, 3 | Booking form: purpose required; allocation field; the schedule shown; field errors from `INVALID_BOOKING` | Auto Vitest | 3 |
| TC-US24-21 | 3, 4, 7 | Coordinator panel: each booking's venue, purpose, window, allocation, status, preparation status and a Primary badge; total allocation against expected, with any shortfall (D67); "Venues arranged" or what's missing | Auto Vitest | 3 |
| TC-US24-22 | 4 | Make primary moves the badge; "Choose a primary venue" with none | Auto Vitest | 3 |
| TC-US24-23 | 5 | Withdraw an Approved booking with a confirm dialog, then request again; the others unchanged | Auto Vitest | 3 |
| TC-US24-24 | 4 | Organiser's view: every venue with status, unavailability and next action; read-only | Auto Vitest | 3 |
| TC-US24-25 | 4 | The MSW mock follows the API's rules (primary, the Organiser's read, schedule) | Auto Vitest | 3 |
| TC-US24-26 | 1, 4, 7 | E2E: the coordinator adds a breakout room to Multi-Venue Conference Demo, sees it pending and not arranged, and withdraws it (rerunnable) | Auto E2E | 3 |
| TC-US24-27 | 4 | E2E: the Organiser sees the demo event's venues with statuses and next action | Auto E2E | 3 |
| TC-US24-28 | 7 | Venue staff set an approved booking's preparation status (`not_started`, `in_progress`, `ready`; D73, CS3-49); an unknown value `422`; a requested, rejected or withdrawn booking `409`; a coordinator, Lead or Organiser `403`; an unknown booking `404`; the event's other bookings unchanged; the coordinator's and Organiser's reads show it | Auto pytest | 2 |
| TC-US24-29 | 7 | Venue staff's control sets an approved booking's preparation status and shows the API's refusal; the coordinator's panel and the Organiser's view show each booking's preparation status, read-only | Auto Vitest | 3 |

## Results

**PR 1 (SCRUM-127), 31 Oct:** TC-US24-01 to 04 pass (33 pytest items, `test_multi_venue_schema.py`). Written first and run before the migration and seed existed (with only `MULTI_VENUE_EVENT = None` stubbed so the file imports): all 19 failed (the 20th, the seed summary's count, was added after review, 31 Oct). Three existing tests changed with the seed and schema: TC-US22-01 (the agreed columns and CHECKs gain `purpose`, `is_primary` and `venue_bookings_purpose_valid`), TC-US2-12 (counts US2's two slot bookings, not every seeded booking) and TC-US10A-04 (the demo event is a fourth assigned seeded event).

**PR 1, customer clarifications (31 Oct):** D73 now tracks preparation per venue (CS3-49), so the migration adds `preparation_status` and deviation 54 is gone; D67 makes the allocations cover the expected attendance for "arranged" (CS3-24; PRs 2 and 3). Changed or added first and run before the column existed: TC-US24-01's three checks, TC-US24-03's eight preparation cases and TC-US24-04's two seed checks failed, with TC-US22-01's agreed columns (14 in all). Now 28 pytest items pass; whole backend suite: 1052 passed.

**PR 1 review (Calvin, #96), 31 Oct:** `EventSpec.venue_slug` has no default, and each in-person seeded event names its venue (the same bookings as before); the downgrade refuses while a booking has its own purpose or preparation progress, as US26's and US5's do; and, with #94 merged, the migration follows `20261102_1200_us5_check_outcome`. Added first and run before the fixes: the three refusal cases and the named-venue check failed; the defaults round-trip already passed. Now 33 pytest items pass; whole backend suite after merging `main`: 1086 passed.
