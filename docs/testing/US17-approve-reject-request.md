# US17 — Approve or reject an event request (SCRUM-84): test cases

**Story:** As an Event Coordinator, I want to approve or reject an event request I am reviewing so that the Organiser knows whether planning will go ahead.

**Source of truth:** the acceptance criteria in Jira SCRUM-84.

**Delivery:** one PR, the migration in its own first commit. It adds the decision columns on `events` (`decided_at`, `decided_by_user_id`, `rejection_reason`) with two CHECKs, `POST /api/v1/event-requests/{id}/approve` and `/reject`, `Notifier.request_decided`, Approve and Reject on the coordinator's review screen, and the outcome on both the coordinator's and the organiser's view of the request.

**Tests:**

- Backend: `backend/tests/event/test_event_request_decisions.py` (TC-US17-01 to 15)
- Frontend: `frontend/src/features/eventRequest/requestDecision.integration.test.tsx` (the real `App` against the MSW fake backend: what the screens offer, send and show)
- E2E: `e2e/tests/event-request-decision.spec.ts` (TC-US17-16, 17). Each test submits its own uniquely named request, which the seeded Lead assigns to the seeded coordinator, Casey Tan

## Acceptance criteria

1. Can approve or reject only requests assigned to them that are Under Review (not while Awaiting Clarification)
2. Moves an approved request to Approved, and a rejected request to Rejected
3. Must give a reason when rejecting; the reason is stored with the request
4. Causes the Organiser to be notified of the outcome, including the reason for a rejection
5. Has the decision recorded with their identity and a timestamp, and the Organiser can see the outcome and reason on their request
6. Who tries to approve or reject a request that's already Approved, Rejected or Cancelled sees an error, and the request doesn't change

## Decisions

- **D53: what deciding does.** Approve → Approved, reject → Rejected; neither moves the request on to Planning, which no AC times. Only the assigned coordinator (D48), only from Under Review, never on a request they created (D51). A rejection's reason is required, trimmed and up to 1,000 characters; an approval takes none
- **Order of checks:** not yours, unassigned, a draft or unknown → `404`; you created it → `403 SELF_DECISION_NOT_ALLOWED`; reject without a reason → `422`; not Under Review → `409 REQUEST_NOT_DECIDABLE` with the status. On any refusal nothing changes and nobody is notified
- **Not backfilled:** events approved or rejected before US17 (the seed, tests) have no recorded decision, so their outcome isn't shown

## Test cases

| ID | AC | Check | Type |
| --- | --- | --- | --- |
| TC-US17-01 | 1, 2, 5 | The assigned coordinator approves a request under review: `approved`, `decided_by` is their name, `decided_at` is now, no reason | Auto pytest |
| TC-US17-02 | 2, 3, 5 | Rejecting stores the trimmed reason, the decider and the time | Auto pytest |
| TC-US17-03 | 3 | A missing, null or blank reason is `422 MISSING_REQUIRED_FIELD` on `reason`; nothing changes and nobody is told | Auto pytest |
| TC-US17-04 | 1 | Another coordinator's request, or an unassigned one, is `404` for both actions, unchanged | Auto pytest |
| TC-US17-05 | 1 | Awaiting Clarification is `409 REQUEST_NOT_DECIDABLE`, unchanged | Auto pytest |
| TC-US17-06 | 6 | Approved, Rejected and Cancelled are `409 REQUEST_NOT_DECIDABLE` with the status, unchanged | Auto pytest |
| TC-US17-07 | 1 | A draft or unknown id is `404` | Auto pytest |
| TC-US17-08 | 1 | An organiser, Lead, Venue Staff or attendee is `403 FORBIDDEN`; no identity is `401` | Auto pytest |
| TC-US17-09 | 1 | A user holding Organiser and Coordinator can't decide a request they created: `403 SELF_DECISION_NOT_ALLOWED` (D51) | Auto pytest |
| TC-US17-10 | 4 | The organiser is told the outcome, with the reason on a rejection and none on an approval | Auto pytest |
| TC-US17-11 | 4 | A refused decision tells no one | Auto pytest |
| TC-US17-12 | 4 | A failed notice doesn't undo the decision | Auto pytest |
| TC-US17-13 | 5 | The organiser's `GET /event-requests/{id}` and `GET /me/event-requests` show the outcome, reason, decider and time | Auto pytest |
| TC-US17-14 | 3 | An unknown body field or a reason over 1,000 characters is `422`, unchanged | Auto pytest |
| TC-US17-15 | 3 | The database refuses a reason on a request that isn't rejected, and a decider who created the request | Auto pytest |
| TC-US17-16 | 1, 2, 5 | Submit, assign Casey, Casey approves; Casey and the organiser see "Approved by Casey Tan" | E2E |
| TC-US17-17 | 3, 5 | Rejecting without a reason is refused on screen; with one, Casey and the organiser see the reason | E2E |
