# US4 — Approve or reject a venue booking request (SCRUM-8): test cases

**Story:** As a Venue Staff member, I want to approve or reject a venue booking request so that only venues that are actually available get committed to an event.

**Source of truth:** the acceptance criteria in Jira SCRUM-8, as updated on 12 Oct 2026 (customer clarification sessions 1 and 2). If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Venue Staff can see the event's timing and venue requirements in the request.
2. Approving reserves the venue for the event.
3. Approval is refused if the venue is already booked, tentatively held or blocked for any part of the window, setup and turnaround included. The request stays unresolved or is rejected. No override.
4. Venue Staff can reject the request.
5. A rejection may give a reason and/or suggest another venue or arrangement.
6. The Event Coordinator is notified of the approval or rejection.
7. The request is approved or rejected as a whole; no partial approval.
8. After a rejection the event stays in (or returns to) Planning, so the Coordinator can request another venue.

**Delivery:** one PR (SCRUM-8): migration, endpoints, screens and E2E as separate commits.

## Test cases

| ID | AC | Check | Type |
| --- | --- | --- | --- |
| TC-US4-01 | 1 | The pending list gives each request's event, venue, start and end, attendance, layout, required facilities and accessibility, and special requirements; the decision fields are null | Auto pytest; frontend unit |
| TC-US4-02 | 2 | `POST …/approve` by Venue Staff: `200`, status `approved`, `decided_at` and `decided_by_user_id` set; it leaves the pending list; a new request for that window is `409 VENUE_UNAVAILABLE`; the event's status doesn't change. An empty or missing body both work | Auto pytest; frontend unit + integration |
| TC-US4-03 | 3 | Approval is `409 VENUE_UNAVAILABLE` with the clashing window, and the booking stays `requested` with nothing notified, when the booking's stored occupied window (US13) overlaps a venue block ("unavailable" if it overlaps the window itself, "Too close to a venue closure …" with `buffers: true` if only the buffers) or, for rows older than the exclusion constraint, another live booking ("already booked" or "Too close to a booking …"). The stored window counts, not the venue's buffers now. Gaps exactly equal to the buffers are fine, as is a block at another venue; with 0/0 buffers touching windows are fine. An inactive venue is `409 VENUE_UNAVAILABLE`. A stored occupied window that now starts before the venue opens or ends after it closes is `409 VENUE_OUTSIDE_HOURS` naming the end that breaches (US13 D32), with the booking left `requested` and nothing notified; hours exactly matching the window are fine. A request whose start is now or past is `409 BOOKING_EXPIRED` and can still be rejected. Attendance above a capacity cut since the request is `409 VENUE_CAPACITY_EXCEEDED`; equal is fine. A body with any field (e.g. `override`) is `422`. The screen explains each refusal on the row and still offers Reject | Auto pytest; frontend unit |
| TC-US4-04 | 4 | `POST …/reject` with no body: `200`, status `rejected`, both notes null; the window is free for a new request; a request whose approval was refused can still be rejected | Auto pytest; frontend unit |
| TC-US4-05 | 5 | A reason and an alternative are trimmed and stored; either alone is fine; blank is null. Any other field is `422`. The database refuses notes on a booking that isn't rejected, and a decision time on one that isn't decided. The coordinator's panel shows both notes | Auto pytest; frontend unit + integration |
| TC-US4-06 | 6 | Approving or rejecting calls `Notifier.venue_booking_decided` once per coordinator: the one who made the request and, if different, the one now assigned to the event, with the decision, event, venue, window and notes. A failing notifier leaves an approval or a rejection in place | Auto pytest |
| TC-US4-07 | 7 | Approving or rejecting a booking that's approved, rejected or withdrawn is `409 BOOKING_NOT_PENDING` with its status and notifies nobody. A decided booking can't be withdrawn. Approve takes no fields, so nothing can be partly approved | Auto pytest; frontend unit |
| TC-US4-08 | 8 | Rejecting leaves an Approved or Planning event's status alone, and its coordinator can request another venue (`201`). Approving a booking whose event has become confirmed, cancelled or completed is `409 EVENT_NOT_BOOKABLE`; it can still be rejected | Auto pytest; frontend unit + integration |
| TC-US4-09 | — | Coordinators (including the requester), Coordinator Leads, organisers, attendees and inactive staff get `403`; no identity `401`; an unknown booking `404` | Auto pytest |
| TC-US4-10 | 1, 2, 6 | In the browser, a coordinator requests a venue for **Venue Booking Demo**; acting as Venue staff, Approve on the pending row says the venue is reserved and the row goes; the coordinator sees it Approved | Auto Playwright |
| TC-US4-11 | 4, 5, 8 | In the browser, Venue staff reject a request with a reason and an alternative; the coordinator sees Rejected with both notes, and Request venue is still offered | Auto Playwright |

Backend: `backend/tests/venue/test_booking_decision_api.py`. Frontend: `PendingBookings.test.tsx`, `EventVenueBookings.test.tsx`, `venueBooking.integration.test.tsx` in `frontend/src/features/venue/`. E2E: `e2e/tests/venue-booking-decision.spec.ts`.

## Decisions to confirm with the team

- **D38 (`DECISION-PENDING`): which window approval checks.** Since US13 (#71) merged: the booking's stored occupied window (setup before, turnaround after), against other live bookings' occupied windows and venue blocks. The booking half is a backstop (the exclusion constraint already keeps them apart); blocks are only checked by the service, so a block added since the request is caught here. A buffer-only clash says "Too close to …" (`buffers: true`).
- **`BOOKING_EXPIRED` (new, PR #73 review):** a request whose start has passed can't be approved, only rejected, until US25 (SCRUM-93) expires pending requests.
- **D39: an inactive venue can't be approved** (`409 VENUE_UNAVAILABLE`). The ticket doesn't say; a deactivated venue isn't "actually available" (the story's goal).
- **D40: who hears the decision.** The coordinator who made the request, and the event's assigned coordinator if that's someone else now (after a reassignment, US10e), once each if active. Log-only, like the other notices.
- **AC 8 "returns to Planning".** No event status changes on a decision: approve and reject leave an Approved or Planning event where it is. Nothing moves an event out of Planning when a venue is booked yet, so there's nothing to return from. Revisit when an event can move past Planning on a confirmed venue.
- **Holds (US25) don't exist yet**, so "tentatively held" is a Requested booking (D21).
