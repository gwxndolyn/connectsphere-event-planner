# US12 — Edit event details during planning (SCRUM-15): test cases

**Story:** As an Event Coordinator, I want to edit non-critical event details during planning, so that the record stays accurate as arrangements evolve.

**Source of truth:** the acceptance criteria in Jira SCRUM-15. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. A Planning event's Edit action is enabled; Confirmed, Cancelled or Completed, it's disabled.
2. Changing only non-critical fields saves them at once; the event stays in Planning and no change request is made.
3. Changing a critical field keeps the event's previous values, creates a Pending Approval change request listing each changed field with its old and new value, and tells the Coordinator it's awaiting approval.
4. A save refused by validation (a required field cleared, end before start, attendance not a positive integer) writes nothing to the event or the audit log, and the message names the field.
5. Every successful save writes an audit entry per field: user id, field, previous value, new value, timestamp. History shows them newest first.

**Delivery:** one PR (no subtasks in Jira), the migration in its own first commit.

| Work | Tests |
| --- | --- |
| `event_change_requests`, `event_audit_entries` (migration `20261108_1200_us12_event_edits`) | `backend/tests/event/test_event_edits.py` (TC-US12-19) |
| `GET /api/v1/me/coordinated-events`, `GET` / `PATCH /api/v1/events/{id}`, `GET /api/v1/events/{id}/history`; seeded **Event Planning Demo** | `backend/tests/event/test_event_edits.py` (TC-US12-01 to 18, 20) |
| **Events** screen for the coordinator: list, details, Edit, changes awaiting approval, History | `frontend/src/features/eventEdit/eventEdit.integration.test.tsx` (TC-US12-21 to 25); `e2e/tests/event-edit.spec.ts` (TC-US12-20 to 23) |

## Decisions for this story

- **Critical fields** (D83, `DECISION-PENDING`; chosen by the story owner on 30 Oct): start time, end time, capacity, expected attendance and delivery mode. Non-critical: name, category, purpose, room layout, accessibility needs, equipment needs, join link. The venue isn't edited here; it's booked through US22.
- **A save mixing both kinds goes for approval whole** (D84, `DECISION-PENDING`; chosen by the story owner on 30 Oct), so "the event record keeps its previous values" (AC 3) holds for every field in it.
- **A critical save is a successful save**, so AC 5 logs it too, each entry tied to its change request and shown as Pending approval in History (D85, `DECISION-PENDING`). **Nobody approves change requests yet**: the ticket doesn't say who does. That is the next story's.
- **Who:** only the event's assigned coordinator (D48), for events past the request stage (`planning` onwards). Anyone else, an unassigned event, a request still at the request stage, or an unknown id is `404`. Other roles `403`.
- **Sending a field at its current value changes nothing and logs nothing**; the screen sends only the fields that differ from what it loaded.
- **A seeded event to try it on:** **Event Planning Demo**, Planning, assigned to the seeded coordinator, registration off. A reseed puts its details back and clears its history and change requests.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US12-01 | 1 | A planning event assigned to the coordinator | They open it | `editable: true`, no pending change requests |
| TC-US12-02 | 1 | A confirmed, cancelled or completed event | They open it, then save | `editable: false`; the save is `409 EVENT_NOT_EDITABLE` with `status`; nothing written |
| TC-US12-03 | 1 | Their planning and confirmed events, and another coordinator's | They list their events | Only theirs, soonest first, each with `editable` |
| TC-US12-04 | — | Another coordinator, an unassigned event, an unknown id | Open, history, save | `404 NOT_FOUND` |
| TC-US12-05 | — | An approved request assigned to them | They open it here | `404`: the request routes own it (D11) |
| TC-US12-06 | 2 | A planning event | Save purpose and equipment needs | `200 saved`; the event has the new values and stays planning; no change request |
| TC-US12-07 | 2 | A room layout | Save it blank | Cleared to null |
| TC-US12-08 | 2 | A planning event | Save the current values | "Nothing changed"; no audit entry, no change request |
| TC-US12-09 | 3 | A planning event | Save new start, end and capacity | `202 pending_approval`; the change request lists each field's old and new value; the event keeps its values and lists the request; the message names the fields |
| TC-US12-10 | 3 | A planning event | Save purpose and expected attendance | The whole edit goes for approval (D84); the event keeps both |
| TC-US12-11 | 3 | A planning event | Save each critical field alone | Each goes for approval |
| TC-US12-12 | 4 | A planning event | Clear a required field; capacity 0; attendance −5, 1.5, "lots", true; an unknown mode; a time without offset; a 101-character category | `422 INVALID_EVENT_EDIT` naming the field with a message; nothing written, not even a valid field sent alongside |
| TC-US12-13 | 4 | A planning event | End before start; start after end | Refused on the field that was moved; nothing written |
| TC-US12-14 | 4 | Two invalid fields | Save | Both named, in form order |
| TC-US12-15 | — | A planning event | Send `status` or `venue_name` | `422`; unchanged |
| TC-US12-16 | 5 | A planning event | Save two changed fields and one unchanged | One audit entry per changed field: user, field, previous, new, time |
| TC-US12-17 | 5 | A planning event | Save a critical field | Its audit entry points at the change request (D85) |
| TC-US12-18 | 5 | Two saves five minutes apart | Read History | Newest first; who, the change request's status |
| TC-US12-19 | — | The migration | Insert a change request with no changes | Refused by its CHECK; RLS on both tables |
| TC-US12-20 | — | A seeded database | Seed, edit, reseed | Event Planning Demo, planning, assigned to the seeded coordinator; a reseed resets it. **E2E:** Edit enabled on it and disabled on a confirmed event |
| TC-US12-21 | 1 | Frontend | Open a planning and a confirmed event | Edit enabled, then disabled with the reason. **E2E:** a non-critical save shows at once and survives a reload |
| TC-US12-22 | 2 | Frontend | Save equipment needs | "Your changes are saved."; only that field sent; shown at once. **E2E:** a capacity change waits for approval |
| TC-US12-23 | 3 | Frontend | Change capacity | "awaiting approval"; details keep 80; "Capacity: 80 → 100" pending. **E2E:** end before start refused on End time; History newest first |
| TC-US12-24 | 4 | Frontend | The API refuses the end time | "Nothing was saved."; End time marked with the API's message; form stays open |
| TC-US12-25 | 5 | Frontend | Two saves, then History | Rows newest first with who (name and id), previous and new values |

## Evidence

Screenshots from the running app (local Postgres, seeded, acting as the seeded coordinator Casey Tan), taken 30 Oct 2026 on branch `feat(SCRUM-15)Edit-Event-Details-During-Planning`. Attach these to SCRUM-15.

| AC | Screenshot | Shows |
| --- | --- | --- |
| — | [01-coordinator-events-list.png](screenshots/US12/01-coordinator-events-list.png) | The coordinator's **Events**: their planning and confirmed events |
| 1 | [02-ac1-planning-edit-enabled.png](screenshots/US12/02-ac1-planning-edit-enabled.png) | Event Planning Demo, Planning: **Edit** enabled |
| 1 | [03-ac1-confirmed-edit-disabled.png](screenshots/US12/03-ac1-confirmed-edit-disabled.png) | A Confirmed event: **Edit** disabled, "Only events in planning can be edited" |
| 2 | [04-ac2-editing-non-critical-fields.png](screenshots/US12/04-ac2-editing-non-critical-fields.png) | Editing room layout and equipment needs |
| 2 | [05-ac2-saved-immediately-still-planning.png](screenshots/US12/05-ac2-saved-immediately-still-planning.png) | "Your changes are saved."; new values shown, still Planning, nothing awaiting approval |
| 3 | [06-ac3-critical-change-awaiting-approval.png](screenshots/US12/06-ac3-critical-change-awaiting-approval.png) | End time and capacity changed: "awaiting approval"; the event keeps 80 and its times; the change request lists each field old → new, Pending approval |
| 4 | [07-ac4-required-field-cleared.png](screenshots/US12/07-ac4-required-field-cleared.png) | Event name cleared: "Nothing was saved", "Event name is required." |
| 4 | [08-ac4-end-before-start.png](screenshots/US12/08-ac4-end-before-start.png) | End before start: "End time must be after the start time." |
| 4 | [09-ac4-attendance-not-positive.png](screenshots/US12/09-ac4-attendance-not-positive.png) | Attendance 0: "Expected attendance must be a whole number of at least 1." |
| 5 | [10-ac5-history-newest-first.png](screenshots/US12/10-ac5-history-newest-first.png) | History, newest first: when, who (name and user id), field, previous and new value; the refused saves left no entries |

## Run log

30 Oct 2026, this branch, local Postgres 16:

- Backend: `pytest` — 1025 passed (TC-US12-01 to 20 in `tests/event/test_event_edits.py`, 37 tests).
- Frontend: `npm run lint`, `npm run build`, `npm test` — 337 passed (TC-US12-21 to 25).
- E2E: `npx playwright test --project=chromium` — 37 passed, `event-edit.spec.ts` 4/4. The `login` project needs Supabase secrets and wasn't run.
