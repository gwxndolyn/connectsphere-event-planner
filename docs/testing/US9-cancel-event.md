# US9 — Cancel an event (SCRUM-12): test cases

**Story:** As an Event Organiser, I want to request cancellation of my event so that ConnectSphere stops holding resources for an event that will no longer take place.

**Source of truth:** the acceptance criteria in Jira SCRUM-12. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The Organiser requests cancellation of their event, with a reason, from approval until its start. Before approval a request is rejected (US17), not cancelled.
2. The assigned Coordinator approves or rejects the request; the Organiser is told the decision.
3. The Coordinator can cancel directly, with a reason.
4. A cancelled event's status is Cancelled, and that can't be undone.
5. Cancelling releases every venue booking (all venues of a multi-venue event), any tentative holds and any reserved equipment.
6. Cancelling notifies the Organiser, the Venue staff and Technical support staff involved, and every registered and wait-listed attendee, with the event name and the reason.
7. Cancelling an event that has started or is Completed is refused with an explanation, and nothing changes.
8. The cancellation records who requested it, who approved it, when, and why.

**Delivery:** three PRs, as US1 and US24 did: the schema alone first (§1a rule), then the API, then the screens.

| PR | Work | Tests |
| --- | --- | --- |
| 1 | `event_cancellations` and `cancellation_status`; a cancelled event may lack its date and capacity, not its name (D98), and the Planning-onwards lists leave such an event out. Migration `20261112_1200_us9_cancellations` | `backend/tests/event/test_cancellation_schema.py` (TC-US9-01 to 08), `test_cancelled_event_reads.py` (TC-US9-08, every read route) |
| 2 | Endpoints, releases, notices | Not built yet |
| 3 | Organiser's and coordinator's screens | Not built yet |

## Decisions for this story

- **One table for requests and direct cancels.** An organiser's request is `pending` until the coordinator decides it. A coordinator's direct cancel (AC 3) is one `approved` row, requested and decided by them at the same moment. Both answer AC 8 the same way.
- **One open row per event** (`event_cancellations_one_open`, on pending and approved): one waiting request, or the cancellation itself. So there's no second request while one waits, none after the event is cancelled, and cancelling must decide a waiting request. A rejected request doesn't stop the organiser asking again.
- **Where the record shows** (AC 8): `GET /api/v1/event-requests/{id}/cancellations` (PR 2) answers the organiser and the assigned coordinator at any status, a dateless cancelled event included. On screen (PR 3): the organiser's own request, which they can open at any status; for the coordinator, PR 2 lets the assigned coordinator open a cancelled request too, since the request routes stop at Rejected (D11) and the Planning-onwards routes leave out an event cancelled before it had a date.
- **A rejection needs a reason** (the story owner's choice, 1 Nov), as US17's does: the organiser is told why their event goes ahead.
- **Cancellable from Approved, Planning, Confirmed and Preparation, until the start.** Approved is included because nothing moves an event on to Planning (D53), as US18 found (D86). An Approved event may have no date or capacity yet, so a cancelled event no longer needs its date, capacity or delivery mode, though it keeps its name for the notices (D98, `DECISION-PENDING`). The coordinator's Events list and the managed-events list are for events from Planning on, so they leave out one cancelled before it had a date.
- **Tech support assignments are kept** (the story owner's choice, 1 Nov). D81 already frees a cancelled event's staff for overlapping events, and the assignment log stays as it was. They are notified (AC 6).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US9-01 | 8 | Migrations applied | Inspect the schema; store a request | `event_cancellations` with RLS on, statuses `pending`, `approved`, `rejected`; a new row is `pending` with no decision |
| TC-US9-02 | 1 | An event with a pending request | Store a second pending one; or a new one after a rejection | Refused (`event_cancellations_one_open`); allowed |
| TC-US9-03 | 4 | An approved cancellation; a pending request | Store a second approved one, or a new request; approve beside the pending one | Each refused (`event_cancellations_one_open`) |
| TC-US9-04 | 1, 3 | | Store a blank reason; a reason or rejection reason of 1,001 characters | Refused (`event_cancellations_reason_not_blank`, `…_rejection_reason_only_when_rejected`); 1,000 is allowed |
| TC-US9-05 | 8 | | Approved without a decider or time; pending with a time; a time without a decider; decided before it was asked. `direct` but pending or rejected; self-approved but not `direct`; an organiser's request approved by the coordinator marked `direct` | Each refused (`event_cancellations_decided_consistent`, `event_cancellations_direct_consistent`) |
| TC-US9-06 | 2 | | Rejected without a reason or with a blank one; approved with one | Each refused (`event_cancellations_rejection_reason_only_when_rejected`) |
| TC-US9-07 | 1 | An Approved event with no date or capacity; one with no name; a Planning event | Cancel the first two; clear the third's start | Allowed (D98); refused; refused (`events_final_fields_required`) |
| TC-US9-08 | 1 | An event cancelled while Approved, with no date, capacity or delivery mode, a released venue, an approved equipment line, a Tech support assignment and its cancellation | Its coordinator lists and opens their Events; its organiser lists managed events and opens its registrations; **every GET route, as every role** (the eight roles' users) | Left out of both lists, `404` when opened; no route answers `5xx` for anyone (Matt's review of #115) |

## Results

| Date | Suite | Result |
| --- | --- | --- |
| 1 Nov | Backend (`pytest`), PR 1 | 1411 passed, including TC-US9-01 to 08; the migration upgrades, downgrades and upgrades again on a local database. Without the list fix TC-US9-08 fails with a `ValidationError` (the `500`) |
| 1 Nov | Backend (`pytest`), PR 1 after merging `main` (#114, US30a) | 1454 passed; the migration now follows `20261110_1200_us30a_safety` and upgrades, downgrades and upgrades again |
| 1 Nov | Backend (`pytest`), PR 1 after Matt's review | 1460 passed: `direct` and the reason caps (TC-US9-04, 05), and every GET route as every role on a dateless cancelled event (TC-US9-08), which fails with a `ValidationError` without the list fix |
| 1 Nov | Backend (`pytest`), PR 1 after merging `main` (#113, US15) | 1472 passed; the migration now follows `20261111_1200_us15_sessions`; D93 renumbered to D98 (#113 took D93 to D97); the read-route sweep (TC-US9-08) covers US15's agenda routes too |
