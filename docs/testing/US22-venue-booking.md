# US22 — Submit a venue booking request (SCRUM-89): test cases

**Story:** As an Event Coordinator, I want to request a venue for an event I manage so that Venue Staff can review whether it can be committed.

**Source of truth:** the acceptance criteria in Jira SCRUM-89, as updated on 12 Oct 2026, and its subtasks, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Submit a booking request only for an event assigned to you that is Approved or in Planning.
2. The request holds the event, venue, start and end time, expected attendance, room layout and any special requirements.
3. Refused if expected attendance exceeds the venue's capacity, or the occupied window overlaps an approved booking, unexpired hold or unavailability period, even by one second. Warned, but can still submit, if a required facility, accessibility feature or room layout is missing.
4. The request is created as Requested and shows in Venue Staff's pending list.
5. A pending request can be withdrawn.
6. Venue Staff are notified of the new request.
7. Two coordinators requesting overlapping windows at the same venue at the same moment: only the first succeeds; the second gets a conflict error.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | Backend schema | `venue_bookings` table, the overlap guard, `has_approved_future_bookings` filled in | `backend/tests/venue/test_booking_schema.py` |
| 2 | Backend endpoints | Create, withdraw and list bookings; validation; Venue Staff notification; the inactive-venue read gap from US20 | `backend/tests/venue/test_booking_api.py` |
| 3 | Frontend | "Request venue" from an event, the coordinator's booking list, Venue Staff's pending list | lint, build, `e2e/tests/venue-booking.spec.ts` |

## Test cases

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US22-01 | 2 | `venue_bookings` has the agreed columns (event, venue, requester, `starts_at`, `ends_at`, expected attendance, room layout, required facility and accessibility tags, special requirements, status, timestamps), named CHECKs (`ends_at > starts_at`, attendance ≥ 1, layout and tags from D18's lists) and RLS on. It has no buffer columns (TC-US20-07's booking half) | Auto pytest | 1 |
| TC-US22-02 | 3, 7 | The database refuses a second Requested or Approved booking whose window overlaps another at the same venue, even by one second. Back-to-back (one ends exactly when the next starts) is allowed. Withdrawn and rejected bookings don't block. Another venue at the same time is fine | Auto pytest | 1 |
| TC-US22-03 | US20 AC 2 | `has_approved_future_bookings` is true for an Approved booking ending after now, and false for Requested, past, withdrawn or rejected ones. TC-US20-02's buffer lock now triggers without forcing it | Auto pytest | 1 |
| TC-US22-04 | 1, 2, 4 | A coordinator requests a venue for an Approved event: `201`, status `requested`, every field read back | Auto pytest | 2 |
| TC-US22-05 | 1 | Planning events can be booked too. Any other status (draft, submitted, under review, awaiting clarification, rejected, confirmed, cancelled, completed) is `409 EVENT_NOT_BOOKABLE` with the current status | Auto pytest | 2 |
| TC-US22-06 | 1 | Organisers, attendees and Venue Staff get `403 FORBIDDEN`. Until US10a adds assignment, any coordinator may book (D20); after it, only the assigned coordinator | Auto pytest | 2 |
| TC-US22-07 | 2 | Missing fields are `422 MISSING_REQUIRED_FIELD` listing them. Start at or after end, a start in the past, or a layout or tag outside D18's lists is `422 INVALID_BOOKING` naming the field | Auto pytest | 2 |
| TC-US22-08 | 3 | Expected attendance above the venue's capacity is `422 VENUE_CAPACITY_EXCEEDED` naming the capacity; nothing is saved. Attendance equal to capacity is accepted | Auto pytest | 2 |
| TC-US22-09 | 3 | A window overlapping a Requested or Approved booking at that venue is `409 VENUE_UNAVAILABLE` with the conflicting window; a one-second overlap is refused; back-to-back is accepted | Auto pytest | 2 |
| TC-US22-10 | 3 | A venue missing a required facility, accessibility feature or the chosen layout still saves (`201`), with a `warnings` list naming each missing item. A venue that has them all has no warnings | Auto pytest | 2 |
| TC-US22-11 | 3 | An inactive venue can't be requested: `404 NOT_FOUND`, as for any venue the coordinator can't see | Auto pytest | 2 |
| TC-US22-12 | 4 | Venue Staff's pending list shows the new request with its event and venue; the coordinator sees it in the event's booking list | Auto pytest | 2 |
| TC-US22-13 | 5 | Withdrawing a Requested booking makes it `withdrawn` and frees the window, so the same window can then be requested. Withdrawing an Approved, rejected or withdrawn booking is `409 BOOKING_NOT_PENDING`. Another coordinator can't withdraw it | Auto pytest | 2 |
| TC-US22-14 | 6 | A successful request notifies Venue Staff once, with the event, venue and window. A refused request notifies nobody | Auto pytest | 2 |
| TC-US22-15 | 7 | Two overlapping requests for the same venue sent at the same moment in separate sessions: one gets `201`, the other `409 VENUE_UNAVAILABLE` | Auto pytest | 2 |
| TC-US22-16 | US20 gap | A coordinator whose event has a booking at a venue that was later deactivated can still read that venue. Other non-staff still get `404` | Auto pytest | 2 |
| TC-US22-17 | US20 AC 7 | A booking body with `setup_minutes` or `turnaround_minutes` is `422` (unknown field): a booking can't override the venue's buffers | Auto pytest | 2 |
| TC-US22-18 | — | No identity is `401 UNAUTHENTICATED`; an unknown event, venue or booking id is `404 NOT_FOUND` | Auto pytest | 2 |
| TC-US22-19 | 1, 2, 4 | In the browser, a coordinator opens an approved event, chooses Request venue, picks a venue and times and submits; the booking shows as Requested. Acting as Venue staff, it appears in the pending list | Auto Playwright | 3 |
| TC-US22-20 | 3 | In the browser, attendance above capacity shows the API's error on the attendance field; a missing layout shows a warning and the request can still be sent | Auto Playwright | 3 |
| TC-US22-21 | 5 | In the browser, the coordinator withdraws a pending request and it shows as Withdrawn | Auto Playwright | 3 |

## Decisions to confirm with the team

- **D20 (`DECISION-PENDING`): who may book before US10a.** Events have no assigned coordinator until US10a (SCRUM-13) adds one, so any coordinator may request a venue for an Approved or Planning event. US10a narrows it to the assigned coordinator in one place.
- **Nothing sets Approved yet.** US17 (SCRUM-84) approves requests, so tests and the seed put events straight into `approved`.
- **Pending requests block the window too.** AC 3 lists approved bookings, holds and unavailability; AC 7 (first come, first served) only works if a Requested booking also blocks. So Requested and Approved both block, enforced by a Postgres exclusion constraint (`btree_gist`) on the venue and the time range, which also covers AC 7's race.
- **Plain start to end for now.** Jira says to check the plain window until US13 (SCRUM-16) adds setup and turnaround buffers to the overlap rule.
- **Holds and unavailability come later.** Neither table exists. US25 (SCRUM-93, holds) and US23a (SCRUM-90, unavailability) add them and extend TC-US22-09.
- **Required facilities and accessibility are tags on the request**, from D18's lists, because the event's own `equipment_needs` and `accessibility_needs` are free text and can't be matched against a venue.
- **New error codes:** `EVENT_NOT_BOOKABLE` (409), `INVALID_BOOKING` (422), `VENUE_CAPACITY_EXCEEDED` (422), `VENUE_UNAVAILABLE` (409), `BOOKING_NOT_PENDING` (409). Each is recorded as a deviation in §1a by the PR that adds it.
