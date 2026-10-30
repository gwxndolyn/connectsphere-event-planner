# US21 — View venue availability calendar (SCRUM-88): test cases

**Story:** As an Event Coordinator or Venue Staff member, I want to see a venue's bookings and unavailable periods on a calendar so that I know when it can be requested.

**Source of truth:** the acceptance criteria in Jira SCRUM-88. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Choose a venue and see a week or month calendar of its approved bookings, tentative holds and unavailability periods, labelled "Booking", "Hold" or "Unavailable".
2. Setup and turnaround buffers are shown as part of each booking's occupied time.
3. Opening a booking shows the event name and status (internal users only).
4. Expired holds and cancelled bookings are not shown.
5. Only internal users; Organisers and Attendees can't access the calendar.

**Decisions:** D56 (who: Coordinator, Lead, Venue staff), D57 (Requested bookings shown, marked pending), D58 (event name and status for all; the `VB-` reference only for Venue staff, Leads and the event's coordinator), D59 (no holds until US25), D60 (withdrawn and rejected bookings left out; a cancelled event's live bookings shown with the event cancelled, the acting PO's decision of 30 Oct), D61 (range, timezone, hours; inactive venues for Venue staff, Leads and the booked event's coordinator). Deviations 50 and 51. All in `claude_instructions.md` §1a.

**Delivery:** two PRs, no migration.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-122 | `GET /api/v1/venues/{venue_id}/calendar?from=&to=` | `backend/tests/venue/test_calendar.py`; the route in US16b's role matrix (`tests/user/test_role_scope.py`, TC-US16B-14) |
| 2 | SCRUM-123 | The calendar on Venues: venue picker, week and month views, item details | lint, build, unit and integration tests, `e2e/tests/venue-calendar.spec.ts` |

## Test cases

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US21-01 | 1, 2 | An approved booking 10:00–12:00 at a venue with 30/15 buffers is one `booking` item labelled "Booking", with its own times and occupied 09:30–12:15; the response echoes the range and the venue's hours and buffers | Auto pytest | 1 |
| TC-US21-02 | 1 | A Requested booking is shown, `status: requested` (D57) | Auto pytest | 1 |
| TC-US21-03 | 1 | A venue block is a `block` item labelled "Unavailable" with its note; its occupied window is its own times | Auto pytest | 1 |
| TC-US21-04 | 4 | Withdrawn and rejected bookings are left out (D60) | Auto pytest | 1 |
| TC-US21-05 | 4 | An approved booking for a cancelled event is shown with the event's status `cancelled` (D60) | Auto pytest | 1 |
| TC-US21-06 | 2 | A booking whose own times are outside the range but whose turnaround or setup runs into it is included (D61) | Auto pytest | 1 |
| TC-US21-07 | 1 | Bookings and blocks outside the range, and another venue's, are left out | Auto pytest | 1 |
| TC-US21-08 | 1, 3 | Items are in occupied-start order, bookings before blocks at the same start; each booking carries its event's name (null with the request reference when unnamed) and status | Auto pytest | 1 |
| TC-US21-09 | 3 | The booking's reference reaches Venue staff, a Lead and the event's coordinator, and is null for another coordinator, who still sees the event's name and the booking's status (D58) | Auto pytest | 1 |
| TC-US21-10 | 5 | Organiser, attendee, Tech support and Safety officer get `403 FORBIDDEN`; no identity `401` (D56) | Auto pytest | 1 |
| TC-US21-11 | 5 | A user holding Organiser and Coordinator gets `200` (D46) | Auto pytest | 1 |
| TC-US21-12 | — | An inactive venue: `200` for Venue staff, a Lead and a coordinator whose event is booked there; `404` for another coordinator (`GET /venues/{id}`'s rule, D61). The Lead also gets `200` on `GET /venues/{id}` | Auto pytest | 1 |
| TC-US21-13 | — | An unknown venue is `404 NOT_FOUND` | Auto pytest | 1 |
| TC-US21-14 | — | A missing or badly formatted `from` or `to` (anything but exactly `YYYY-MM-DD`, e.g. `12-10-2026` or `2026-W42-1`), `to` before `from`, or more than 42 days is `422 INVALID_DATE_RANGE` naming the field; 42 days and a single day are accepted (deviation 51) | Auto pytest | 1 |
| TC-US21-15 | 1 | `calendarGrid`: a week is Monday to Sunday; a month is the full weeks covering it; the API range matches | Auto Vitest | 2 |
| TC-US21-16 | 5 | The calendar is shown on Venues for the Coordinator, Lead and Venue staff roles, not the Organiser | Auto Vitest | 2 |
| TC-US21-17 | 2 | Week view: a booking labelled "Booking" spans its occupied window, with setup and turnaround segments named | Auto Vitest | 2 |
| TC-US21-18 | 1 | Week view: a Requested booking reads "Booking (requested)"; a block "Unavailable" with its note | Auto Vitest | 2 |
| TC-US21-19 | — | Week view: hours outside the venue's opening hours are shaded "Closed" (D61) | Auto Vitest | 2 |
| TC-US21-20 | 3 | Opening an item shows the event's name and status, the booking's status and times; the reference only when the API gives one; a cancelled event's booking shows the event as cancelled (D60) | Auto Vitest | 2 |
| TC-US21-21 | 1 | Month view, Previous / Today / Next and Week ↔ Month each request the right range | Auto Vitest | 2 |
| TC-US21-22 | — | `403`, `404`, `422 INVALID_DATE_RANGE` and a network failure are shown in an alert; no venue chosen, loading and nothing booked each say so | Auto Vitest | 2 |
| TC-US21-23 | 1, 3 | E2E: Venue staff open the week of US2's seeded slot and see SCIS Seminar Room 2-1's seeded booking, labelled, with its setup and turnaround, and SMU Connexion Studio 3-2's seeded block, "Unavailable" with its note (the seed puts them at two venues); the booking opens with event name, status and reference | Auto E2E | 2 |
| TC-US21-24 | 3 | E2E: a coordinator sees the same items, without the reference on a booking for an event not theirs | Auto E2E | 2 |

## Results

**PR 1 (SCRUM-122), 28 Oct:** TC-US21-01 to 14 pass (25 pytest items, `test_calendar.py`), plus the route's TC-US16B-14 matrix row. Written first and run before the endpoint existed: all 25 failed (`404`, no route). Whole backend suite: 1010 passed.

**PR 1 review (Calvin, #92), 30 Oct:** TC-US21-05 now expects a cancelled event's booking shown (D60, the acting PO's decision), TC-US21-12 adds a Lead on an inactive venue, and TC-US21-14 adds `2026-W42-1`. Changed first and run before the fix: all three failed (the booking was left out, the Lead got `404`, `2026-W42-1` was accepted). Now 26 pytest items pass; whole backend suite: 1011 passed.

**PR 2 (SCRUM-123), 30 Oct:** TC-US21-15 to 24 pass: 33 Vitest tests (`calendarGrid.test.ts` 13 and `VenueCalendar.test.tsx` 13, unit; `venueCalendar.integration.test.tsx` 7, against the fake backend's calendar route) and 2 E2E (`e2e/tests/venue-calendar.spec.ts`). Written first and run against stubs (`calendarGrid` throwing, `VenueCalendar` rendering nothing): 32 failed; the one that passed is TC-US21-16's organiser case, which checks the calendar is absent. The E2E spec was first run after the build, with the screen taken off Venues: both failed (no Availability calendar), then passed with it. Whole frontend suite: 364 passed; lint and build clean. Whole E2E suite: 38 passed, 10 skipped (the logged-in and sign-up tests, without `E2E_SEED_PASSWORD` and Supabase keys).
