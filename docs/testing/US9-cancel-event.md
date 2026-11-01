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
| 1 | `event_cancellations` and `cancellation_status`; cancelled events may lack final fields (D93). Migration `20261112_1200_us9_cancellations` | `backend/tests/event/test_cancellation_schema.py` (TC-US9-01 to 07) |
| 2 | Endpoints, releases, notices | Not built yet |
| 3 | Organiser's and coordinator's screens | Not built yet |

## Decisions for this story

- **One table for requests and direct cancels.** An organiser's request is `pending` until the coordinator decides it. A coordinator's direct cancel (AC 3) is one `approved` row, requested and decided by them at the same moment. Both answer AC 8 the same way.
- **One pending request, and one approved cancellation, per event** (partial unique indexes). A rejected request doesn't stop the organiser asking again.
- **A rejection needs a reason** (the story owner's choice, 1 Nov), as US17's does: the organiser is told why their event goes ahead.
- **Cancellable from Approved, Planning, Confirmed and Preparation, until the start.** Approved is included because nothing moves an event on to Planning (D53), as US18 found (D86). An Approved event may have no date or capacity yet, so a cancelled event no longer needs its final fields (D93, `DECISION-PENDING`).
- **Tech support assignments are kept** (the story owner's choice, 1 Nov). D81 already frees a cancelled event's staff for overlapping events, and the assignment log stays as it was. They are notified (AC 6).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US9-01 | 8 | Migrations applied | Inspect the schema; store a request | `event_cancellations` with RLS on, statuses `pending`, `approved`, `rejected`; a new row is `pending` with no decision |
| TC-US9-02 | 1 | An event with a pending request | Store a second pending one; or a new one after a rejection | Refused (`event_cancellations_one_pending`); allowed |
| TC-US9-03 | 4 | An event with an approved cancellation | Store a second approved one | Refused (`event_cancellations_one_approved`) |
| TC-US9-04 | 1, 3 | | Store a blank reason | Refused (`event_cancellations_reason_not_blank`) |
| TC-US9-05 | 8 | | Approved without a decider or time; pending with a time; a time without a decider | Each refused (`event_cancellations_decided_consistent`) |
| TC-US9-06 | 2 | | Rejected without a reason or with a blank one; approved with one | Each refused (`event_cancellations_rejection_reason_only_when_rejected`) |
| TC-US9-07 | 1 | An Approved event with no date or capacity; a Planning event | Cancel the first; clear the second's start | Allowed (D93); still refused (`events_final_fields_required`) |

## Results

| Date | Suite | Result |
| --- | --- | --- |
| 1 Nov | Backend (`pytest`), PR 1 | 1404 passed, including TC-US9-01 to 07; the migration upgrades, downgrades and upgrades again on a local database |
