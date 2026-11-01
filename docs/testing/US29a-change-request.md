# US29a — Request a change to a submitted event (SCRUM-97): test cases

**Story:** As an Event Organiser, I want to request changes to my event after it's been submitted so that ConnectSphere can adjust the arrangements.

**Source of truth:** the acceptance criteria in Jira SCRUM-97. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The Organiser requests changes to date, time, expected attendance, venue or equipment requirements or other details, for their own event, once it's Submitted or later (not Cancelled, Completed or Rejected).
2. They see each requested field with its current and proposed value before submitting.
3. A reason is required.
4. The change request is Pending; the event's current values don't change.
5. The assigned coordinator is notified.
6. They can see the status of their change requests.

**Delivery:** one PR. The Jira subtasks (table, create endpoint, form, notifier, tests) are its commits.

| Work | Tests |
| --- | --- |
| `event_change_requests.reason` (migration `20261109_1200_us29a_change_reqs`), on US12's table | `backend/tests/event/test_change_requests.py` (TC-US29A-12, 18) |
| `POST /api/v1/event-requests/{id}/change-requests`, `GET /api/v1/me/change-requests`; `Notifier.change_requested` | `backend/tests/event/test_change_requests.py` (TC-US29A-01 to 17) |
| **Change requests** on the organiser's request: form, review, status list | `frontend/src/features/changeRequest/changeRequest.integration.test.tsx` (TC-US29A-19 to 23); `e2e/tests/change-request.spec.ts` (TC-US29A-24) |

## Decisions for this story

- **One table for both kinds of change request.** US12's `event_change_requests` gains a `reason`, and its `pending_approval` status is AC 4's "Pending". US29b reviews organisers' requests and coordinators' US12 edits in one place. An organiser sees only the requests they made.
- **Which fields, by stage** (D87, `DECISION-PENDING`; the story owner's choice, 1 Nov): from Submitted to Approved, the preferred dates, start time and end time; from Planning on, the event's own start and end. At every stage: name, category, purpose, expected attendance, room layout, accessibility needs and equipment needs. "Venue requirements" are the room layout and accessibility needs; the venue itself is booked by the coordinator (US22). Capacity and delivery mode are the coordinator's, not the organiser's.
- **Who is notified** (D88, `DECISION-PENDING`; the story owner's choice, 1 Nov): the assigned coordinator. A Submitted event has none yet (D27), so every active Coordinator Lead hears instead, as when a request joins the queue (D28). Log-only, like the other notices.
- **Draft:** `404`, as it's still the organiser's to edit directly.
- **Unchanged values aren't listed**, and a request whose every value matches the event is refused (`NO_CHANGES`).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US29A-01 | 1 | The organiser's event, Submitted, Under Review, Awaiting Clarification, Approved, Planning or Confirmed | They request a change | `201`, Pending |
| TC-US29A-02 | 1 | Rejected, Cancelled, Completed | They request a change | `409 CHANGE_NOT_ALLOWED` with `status`; nothing stored |
| TC-US29A-03 | 1 | A draft, another organiser's event, an unknown id | They request a change | `404 NOT_FOUND` |
| TC-US29A-04 | 1 | A Submitted event | Change preferred date, times, room layout, equipment | Each listed, in form order |
| TC-US29A-05 | 1 | A Planning event | Change the end; change a preferred time | End accepted; the preference refused "at this stage" (D87) |
| TC-US29A-06 | 2 | A Submitted event | Change attendance, resend the purpose unchanged | Only attendance listed, with current and proposed value |
| TC-US29A-07 | 2 | A Submitted event | Propose only current values | `422 NO_CHANGES`; nothing stored |
| TC-US29A-08 | 3 | A Submitted event | No reason, a blank one, no changes, neither | `422 MISSING_REQUIRED_FIELD` naming `reason` and/or `changes` |
| TC-US29A-09 | 3 | A Submitted event | A 1,001-character reason | `422 INVALID_CHANGE_REQUEST` on `reason` |
| TC-US29A-10 | 2 | A Submitted event | Attendance 0 or "lots", a blank name, a past or malformed date, end before start, `capacity`, `status` | `422 INVALID_CHANGE_REQUEST` naming the field; nothing stored |
| TC-US29A-11 | 4 | A Submitted event | Request a change | Pending with the reason and requester; the event keeps its values and status |
| TC-US29A-12 | 3 | The schema | Insert a blank reason | Refused by `event_change_requests_reason_not_blank` |
| TC-US29A-13 | 5 | An event with a coordinator | Request a change | `change_requested` to the coordinator: event, organiser, fields, reason |
| TC-US29A-14 | 5 | A Submitted event (no coordinator) | Request a change | Every active Lead is told, marked as to a Lead (D88) |
| TC-US29A-15 | 5 | The notice fails | Request a change | `201`; the request is kept |
| TC-US29A-16 | 6 | Requests on two events, and another organiser's | List theirs, then for one event | Theirs only, newest first, with status and reference |
| TC-US29A-17 | 6 | A coordinator's US12 edit on the organiser's event | List theirs | Not listed |
| TC-US29A-18 | — | The migrations | — | One head |
| TC-US29A-19 | 1 | Frontend: a Submitted and a Rejected request | Open each | Request a change offered, then not, with the reason |
| TC-US29A-20 | 2, 3 | Frontend | Change attendance, Review without a reason, then with one | The reason is marked; then a table shows Expected attendees 40 → 60; nothing sent yet |
| TC-US29A-21 | 4, 6 | Frontend | Add equipment needs, a reason, Review, Send | Only that field and the reason sent; listed as Pending; the request unchanged |
| TC-US29A-22 | 6 | Frontend: an earlier rejected change request | Open the request | Listed with Rejected and its fields |
| TC-US29A-23 | 2 | Frontend: the API refuses the date | Send | "Nothing was sent."; Preferred date marked with the API's message |
| TC-US29A-24 | 1–4, 6 | E2E: the organiser submits a request | Request a change, Review without then with a reason, Send, reopen | Reason required; the preview shows current and proposed values; Pending, listed again on reopening |

## Evidence

From the running app (local Postgres, seeded, acting as the seeded organiser Olivia Organiser), 1 Nov 2026, branch `feat(SCRUM-97)Request-Change-To-Submitted-Event`. Attach these to SCRUM-97.

| AC | Evidence | Shows |
| --- | --- | --- |
| 1 | [01-ac1-submitted-request-change-offered.png](screenshots/US29a/01-ac1-submitted-request-change-offered.png) | A just-submitted request (ER-2026-000009) offers **Request a change** |
| 1 | [02-ac1-change-form-date-time-attendance-equipment.png](screenshots/US29a/02-ac1-change-form-date-time-attendance-equipment.png) | The form: preferred date and times, attendance, layout, accessibility, equipment and other details |
| 3 | [03-ac3-reason-required.png](screenshots/US29a/03-ac3-reason-required.png) | Review without a reason: "Give a reason for the change." on the reason field |
| 2 | [04-ac2-current-and-proposed-before-sending.png](screenshots/US29a/04-ac2-current-and-proposed-before-sending.png) | Before sending: each changed field with its current and proposed value, and the reason |
| 4, 6 | [05-ac4-ac6-pending-event-unchanged.png](screenshots/US29a/05-ac4-ac6-pending-event-unchanged.png) | Sent: "Your event keeps its current details"; the request listed as **Pending** |
| 6 | [06-ac6-status-on-reopening.png](screenshots/US29a/06-ac6-status-on-reopening.png) | Reopening the request shows the change request and its status |
| 5 | [07-ac5-notification-log.txt](screenshots/US29a/07-ac5-notification-log.txt) | The backend's notice log: the assigned coordinator (Venue Booking Demo), and both Leads for the unassigned request (D88). Notices are log-only (spec §7) |

## Run log

1 Nov 2026, this branch, local Postgres 16:

- Backend: `pytest` — 1315 passed (TC-US29A-01 to 18 in `tests/event/test_change_requests.py`).
- Frontend: `npm run lint`, `npm run build`, `npm test` — 432 passed (TC-US29A-19 to 23).
- E2E: `npx playwright test --project=chromium` — 44 passed, 1 failed: `change-request.spec.ts` passes; the failure is TC-US5-11 (`equipment.spec.ts`), which fails the same way on `main` (found 31 Oct) and isn't touched here. The `login` project needs Supabase secrets and wasn't run.
