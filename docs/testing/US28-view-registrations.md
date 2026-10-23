# US28 — View registrations for my events (SCRUM-96): test cases

**Story:** As an Event Organiser or Event Coordinator, I want to see who has registered for an event I manage so that I can plan for actual attendance.

**Source of truth:** the acceptance criteria in Jira SCRUM-96.

**Delivery:** one PR. It adds `GET /api/v1/me/managed-events` (the events whose registrations the caller may view), `GET /api/v1/events/{id}/registrations`, a **Registrations** view in the header for the Organiser and Coordinator roles, and seeds the organiser as the owner of the seeded events. No schema change.

**Tests:**

- Backend: `backend/tests/registration/test_event_registrations.py` (TC-US28-01 to 15)
- Frontend: `frontend/src/features/eventRegistrations/eventRegistrations.integration.test.tsx` (the real `App` against the MSW fake backend). The fake doesn't apply the access or filter rules: it returns what a test seeds (`seedManagedEvent`), so integration tests check what the screen sends and shows, and AC 1, 4 and 5 are proven by the backend and E2E tests
- E2E: `e2e/tests/event-registrations.spec.ts` (TC-US28-16, 17), read-only against the seeded Intro to Supabase: Live Coding

## Acceptance criteria

1. Can view registrations only for events they own or are assigned to; for any other event the registrations aren't shown
2. Sees totals for confirmed, waitlisted and offered, and the remaining capacity
3. Sees a list of registrants with name/email, status, registration time, waitlist position and answers to the registration questions
4. Can filter by status
5. Doesn't see withdrawn or declined entries by default, and can show them with a "Show all" toggle

## Decisions

- **D30: who manages an event?** An Organiser manages the events they created (`created_by_user_id`). Any active Coordinator manages every event for now. US10a (SCRUM-13) added `events.coordinator_id`; narrowing `_manages` in `app/registration/roster_service.py` to the assigned coordinator is a follow-up
- Only events past the request stage (`planning`, `confirmed`, `cancelled`, `completed`) have registrations to show. A request is `404`, which also keeps coordinators out of drafts (D11)
- `expired` offers are hidden by default with withdrawn and declined, since none of them holds or waits for a place
- A status filter decides on its own: `?status=withdrawn` shows withdrawn rows without `show_all`

## Test cases

| ID | AC | Check | Type |
| --- | --- | --- | --- |
| TC-US28-01 | 1 | The organiser who created the event gets its registrations | Auto pytest |
| TC-US28-02 | 1 | Another organiser gets `404 NOT_FOUND`, never `403` | Auto pytest |
| TC-US28-03 | 1 | A coordinator gets any event's registrations (D30) | Auto pytest |
| TC-US28-04 | 1 | An attendee or operations manager is `403 FORBIDDEN`; no identity is `401` | Auto pytest |
| TC-US28-05 | 1 | A draft, submitted or approved request, or an unknown id, is `404` for its owner and for coordinators | Auto pytest |
| TC-US28-06 | 2 | Totals count confirmed, waitlisted and offered; places left is capacity minus confirmed and live offers | Auto pytest |
| TC-US28-07 | 3 | Each row has name (or null), email, status, registration time, waitlist position and answers keyed by question; the questions come in order | Auto pytest |
| TC-US28-08 | 3 | Confirmed first, then offered, then the waitlist in queue order with positions 1, 2 | Auto pytest |
| TC-US28-09 | 2, 4 | One or more `status` values narrow the list; totals stay those of the whole event | Auto pytest |
| TC-US28-10 | 5 | Withdrawn, declined and expired are hidden by default, shown with `show_all=true`, and shown when asked for by status | Auto pytest |
| TC-US28-11 | 3 | An email-only waitlist entry (D3) shows its email with no name | Auto pytest |
| TC-US28-12 | 4 | An unknown status is `422` | Auto pytest |
| TC-US28-13 | 1 | Managed events are the organiser's own events past the request stage, soonest first | Auto pytest |
| TC-US28-14 | 1 | A coordinator's managed events are every event past the request stage; an attendee is `403` | Auto pytest |
| TC-US28-15 | 1 | The seeded organiser owns the seeded events | Auto pytest |
| TC-US28-16 | 1, 2, 3 | As the organiser, the seeded online event shows Confirmed 1, Waitlisted 0, Places left 199 and Calvin's confirmed row | E2E |
| TC-US28-17 | 4, 5 | As a coordinator, filtering to Waitlisted empties the list but not the totals; Show all brings Calvin back | E2E |
