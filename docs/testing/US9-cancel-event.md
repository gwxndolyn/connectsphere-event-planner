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
| 1 | `event_cancellations` and `cancellation_status`; a cancelled event may lack its date and capacity, not its name (D93), and the Planning-onwards lists leave such an event out. Migration `20261112_1200_us9_cancellations` | `backend/tests/event/test_cancellation_schema.py` (TC-US9-01 to 08) |
| 2 | Ask, approve, reject and cancel; reading the record; releasing venues and equipment; the notices; no waitlist offers on a cancelled event | `backend/tests/event/test_cancellations.py` (TC-US9-09 to 23), `test_cancellation_race.py` (TC-US9-24); `backend/tests/user/test_role_scope.py` (the routes' roles and D51) |
| 3 | Organiser's and coordinator's screens | Not built yet |

## Decisions for this story

- **One table for requests and direct cancels.** An organiser's request is `pending` until the coordinator decides it. A coordinator's direct cancel (AC 3) is one `approved` row, requested and decided by them at the same moment. Both answer AC 8 the same way.
- **One open row per event** (`event_cancellations_one_open`, on pending and approved): one waiting request, or the cancellation itself. So there's no second request while one waits, none after the event is cancelled, and cancelling must decide a waiting request. A rejected request doesn't stop the organiser asking again.
- **A rejection needs a reason** (the story owner's choice, 1 Nov), as US17's does: the organiser is told why their event goes ahead.
- **Cancellable from Approved, Planning, Confirmed and Preparation, until the start.** Approved is included because nothing moves an event on to Planning (D53), as US18 found (D86). An Approved event may have no date or capacity yet, so a cancelled event no longer needs its date, capacity or delivery mode, though it keeps its name for the notices (D93, `DECISION-PENDING`). The coordinator's Events list and the managed-events list are for events from Planning on, so they leave out one cancelled before it had a date.
- **Venue staff told** (D94, `DECISION-PENDING`): Venue staff aren't assigned to events, so every active Venue staff member hears, and only when an approved venue was released, as for a withdrawn approved booking (D69).
- **When an Approved event starts** (D95, `DECISION-PENDING`): it has no `start_at` yet, so AC 7 uses its earliest live venue booking, else its last preferred date at its preferred start time, by when it has surely started.
- **A waiting request blocks a direct cancel** (`CANCELLATION_PENDING`): the coordinator decides the organiser's request instead, so the record keeps who asked (AC 8).
- **Registrations stay as they are.** Everyone registered, offered or waiting is told (AC 6); a cancelled event offers no freed place, and an offer made before the cancel can't be accepted (`EVENT_CANCELLED`).
- **Tech support assignments are kept** (the story owner's choice, 1 Nov). D81 already frees a cancelled event's staff for overlapping events, and the assignment log stays as it was. They are notified (AC 6).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US9-01 | 8 | Migrations applied | Inspect the schema; store a request | `event_cancellations` with RLS on, statuses `pending`, `approved`, `rejected`; a new row is `pending` with no decision |
| TC-US9-02 | 1 | An event with a pending request | Store a second pending one; or a new one after a rejection | Refused (`event_cancellations_one_open`); allowed |
| TC-US9-03 | 4 | An approved cancellation; a pending request | Store a second approved one, or a new request; approve beside the pending one | Each refused (`event_cancellations_one_open`) |
| TC-US9-04 | 1, 3 | | Store a blank reason | Refused (`event_cancellations_reason_not_blank`) |
| TC-US9-05 | 8 | | Approved without a decider or time; pending with a time; a time without a decider; decided before it was asked | Each refused (`event_cancellations_decided_consistent`) |
| TC-US9-06 | 2 | | Rejected without a reason or with a blank one; approved with one | Each refused (`event_cancellations_rejection_reason_only_when_rejected`) |
| TC-US9-07 | 1 | An Approved event with no date or capacity; one with no name; a Planning event | Cancel the first two; clear the third's start | Allowed (D93); refused; refused (`events_final_fields_required`) |
| TC-US9-08 | 1 | An event cancelled while Approved, with no date | Its coordinator lists and opens their Events; its organiser lists managed events and opens its registrations | Left out of both lists, `404` when opened; never a `500` |
| TC-US9-09 | 1, 2 | The organiser's event, Approved, Planning, Confirmed or Preparation | They ask, with a padded reason | `201`, pending, the reason trimmed; the event unchanged; the coordinator told |
| TC-US9-10 | 1, 4, 7 | Submitted, Under Review, Awaiting Clarification, Rejected, Cancelled, Completed | They ask | `409 CANCELLATION_NOT_ALLOWED` with `status`; nothing stored or told |
| TC-US9-11 | 1 | A draft, another organiser's event, an unknown id | They ask | `404 NOT_FOUND` |
| TC-US9-12 | 1 | | No reason, a blank one, over 1,000 characters; an unknown field | `422 MISSING_REQUIRED_FIELD` / `INVALID_CANCELLATION` on `reason`; `422`; nothing stored |
| TC-US9-13 | 1 | A request waiting | They ask again | `409 CANCELLATION_PENDING` with its id |
| TC-US9-14 | 2, 4 | A waiting request | The coordinator approves | `200`; approved, with decider and time; the event Cancelled; the organiser told, with the reason |
| TC-US9-15 | 2 | A waiting request | Reject without a reason; with one | `422`; `200`, rejected with the reason, the event still Planning, the organiser told why, nobody told of a cancel; the organiser can ask again |
| TC-US9-16 | 2 | A request | Another coordinator, an unknown id; decide twice | `404`; `409 CANCELLATION_NOT_PENDING` |
| TC-US9-17 | 3 | The coordinator's event; one with a request waiting | Cancel with a reason; without; by another coordinator; beside the waiting request | `200`, approved, `direct`, them as requester and decider; `422`; `404`; `409 CANCELLATION_PENDING` |
| TC-US9-18 | 5 | Approved, requested and rejected bookings at three venues; a reservation; another event's; a Tech support assignment | Cancel; a refused cancel | The two live bookings withdrawn (the approved one keeps its decision), the rejected one untouched; the event's reservation deleted, the other kept; the assignment kept. A refused cancel changes nothing |
| TC-US9-19 | 6 | Organiser, active and inactive Venue staff, an approved booking, an assigned, an unassigned and a deactivated Tech support member, registered, wait-listed, offered, lapsed-offer and withdrawn attendees | Cancel; with only a requested booking; with the notifier failing | One notice each to the organiser, the active Venue staff, the active assigned Tech support member and the three attendees holding or awaiting a place, with the name and reason; no Venue staff when no approved venue was released; the cancel stands |
| TC-US9-20 | 7 | An event that has started; a request approved after the start; Approved events: one with a later preferred date ahead, one with every date passed, one whose venue booking has started | Ask, cancel, approve | `409 EVENT_STARTED`, nothing changes and the request stays pending; the first Approved one may be cancelled, the other two are `EVENT_STARTED` (D95) |
| TC-US9-21 | 4 | A cancelled event | Cancel again, ask | `409 CANCELLATION_NOT_ALLOWED`, `status: cancelled` |
| TC-US9-22 | 8 | A rejected request and a newer waiting one | The organiser and the coordinator read; another organiser and coordinator | Both newest first; `404` |
| TC-US9-23 | 6 | An offer made before the cancel; a full event with a queue | The attendee accepts; a registered attendee withdraws after the cancel | `409 EVENT_CANCELLED`, the offer unchanged; no place offered, nobody told |
| TC-US9-24 | 5 | A requested booking, committed | Venue staff approve it (locking the booking, then pausing) while the coordinator cancels the event, on two connections | Both succeed in turn: the booking is approved, then withdrawn with its decision kept; the event Cancelled. Locking the event first deadlocked (`DeadlockDetected`) |

## Results

| Date | Suite | Result |
| --- | --- | --- |
| 1 Nov | Backend (`pytest`), PR 1 | 1411 passed, including TC-US9-01 to 08; the migration upgrades, downgrades and upgrades again on a local database. Without the list fix TC-US9-08 fails with a `ValidationError` (the `500`) |
| 1 Nov | Backend (`pytest`), PR 1 after merging `main` (#114, US30a) | 1454 passed; the migration now follows `20261110_1200_us30a_safety` and upgrades, downgrades and upgrades again |
| 1 Nov | Backend (`pytest`), PR 2 | 1498 passed, including TC-US9-09 to 24 and the new routes in `test_role_scope.py`; TC-US9-24 fails with `DeadlockDetected` without the lock order |
