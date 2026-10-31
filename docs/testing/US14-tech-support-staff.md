# US14 — Assign Technical Support Staff to an event (SCRUM-17): test cases

**Story:** As an Event Coordinator, I want to assign qualified Technical Support Staff to an event that requires on-site technical assistance, so that the event has dedicated technical personnel available during its delivery.

**Source of truth:** the acceptance criteria in Jira SCRUM-17 and its subtasks SCRUM-133 to SCRUM-135, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Only events with approved technical support requests can have Technical Support Staff assigned.
2. The coordinator sees internal Technical Support Staff filtered by availability: not already on an overlapping event during the event's delivery window.
3. One or more available staff can be assigned.
4. Each assigned staff member gets an automated notification with the event details, venue location and technical requirements.
5. Staff can be reassigned or unassigned before the event starts.
6. Every assignment and reassignment is logged with who did it, the staff assigned, and when.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-133 | `tech_staff_assignments` (the assignments and their log); a second seeded Tech support user; the reseed clears the demo event's assignments | `backend/tests/equipment/test_tech_staff_schema.py` |
| 2 | SCRUM-134 | `GET` / `POST /api/v1/events/{id}/tech-staff`, `DELETE /api/v1/events/{id}/tech-staff/{staff_user_id}`; the notification | backend `pytest`; the routes in US16b's role matrix (TC-US16B-14) |
| 3 | SCRUM-135 | **Technical support** on the coordinator's Equipment screen | Vitest; `e2e/tests/equipment.spec.ts` |

## Decisions for this story

Decided by the acting PO, Matthew, on 31 Oct (team channel).

- **D79, one table is the assignments and their log:** a row per assignment, active until unassigned (who and when); reassigning is unassign then assign, so both are logged.
- **D80, eligible (AC 1):** at least one approved equipment line (US26), and the event in `planning` or `confirmed`. That's what an "approved technical support request" is.
- **D81, delivery window (AC 2):** the event's own start and end, with no venue setup or turnaround; back-to-back events don't overlap.
- **D82, the notification (AC 4):** the event's approved equipment lines and its `equipment_needs`; the venue as attendees see it (D70).
- **D83, where:** on the coordinator's existing Equipment screen.

TC-US14-04 isn't used: it was merged into 03 when the cases were drafted.

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US14-01 | 6 | A database at the previous head | `alembic upgrade head` | `tech_staff_assignments` exists with its columns, RLS on and its indexes; one Alembic head | SCRUM-133 |
| TC-US14-02 | 3, 6 | An event and a Tech support user | An assignment is saved with an unknown event or staff member; with only one of the unassign columns set; or a second active assignment of the same person to the same event; then the first is unassigned and the person assigned again | Refused on a foreign key, the named CHECK, and the partial unique index; after the unassign, the new assignment saves | SCRUM-133 |
| TC-US14-03 | — | The seed; assignments on Equipment Request Demo and on another event | The seed runs (twice) | The second Tech support user exists with a full name; the second run changes nothing; the demo event's assignments are gone and the other event's remain | SCRUM-133 |
| TC-US14-05 | 1, 2 | A confirmed event with an approved equipment line; active Tech support users | Its coordinator lists the event's Tech support staff | `eligible` true; every active Tech support user available; none assigned | SCRUM-134 |
| TC-US14-06 | 1 | An event with only pending or rejected lines; an approved line on an event not in planning or confirmed | The coordinator lists; then assigns | `eligible` false; assigning is `409 NO_APPROVED_TECH_REQUEST` and saves nothing | SCRUM-134 |
| TC-US14-07 | 2 | A Tech support user assigned to another event that overlaps; others assigned to a back-to-back event, one on another day, and one since unassigned | The coordinator lists, and assigns the busy one | The busy one isn't available and assigning them is `409 STAFF_UNAVAILABLE`; the others are available | SCRUM-134 |
| TC-US14-08 | 3 | Two available Tech support users; then one available and one busy | The coordinator assigns both in one request | `201`, both assigned with who and when; in the second case `409 STAFF_UNAVAILABLE` and nothing saved | SCRUM-134 |
| TC-US14-09 | 4 | An eligible event with an approved primary venue, approved lines and `equipment_needs`; another with no primary venue | Staff are assigned | Each is notified with the event's name and times, the venue location (the primary venue's, else the event's own) and the technical requirements; a notifier failure doesn't undo the assignment | SCRUM-134 |
| TC-US14-10 | 5 | An assigned staff member before the event starts; an event that has started | The coordinator unassigns, then assigns someone else; and on the started event, assigns or unassigns | `204` and the person is available again, then the new one is assigned (a reassignment); on the started event `409 EVENT_STARTED` for both | SCRUM-134 |
| TC-US14-11 | 6 | An assignment, an unassignment and a new assignment on one event | The coordinator lists | The log has each, newest first, with the staff member, who did it and when | SCRUM-134 |
| TC-US14-12 | 3 | A user who isn't Tech support, an inactive one, an unknown id; someone already assigned here; someone not assigned | The coordinator assigns them, or unassigns the last | `422 INVALID_STAFF`; `409 ALREADY_ASSIGNED`; unassigning someone not assigned is `409 NOT_ASSIGNED` | SCRUM-134 |
| TC-US14-13 | 2 | One Tech support user; two coordinators, each with an eligible event, the events overlapping | Both assign that person at the same moment | One `201`, the other `409 STAFF_UNAVAILABLE`: a real two-connection race, as TC-US27-11 | SCRUM-134 |
| TC-US14-14 | — | Other roles; a coordinator not assigned to the event; no identity; an unknown event | They list, assign or unassign | `403 FORBIDDEN`; `404 NOT_FOUND`; `401 UNAUTHENTICATED`; `404 NOT_FOUND` | SCRUM-134 |
| TC-US14-15 | 1, 2, 3 | An event that isn't eligible; an eligible one with two available staff; a mocked `STAFF_UNAVAILABLE` | The coordinator opens each on Equipment, ticks both and presses Assign | The first says it needs an approved equipment request; on the second both show as assigned; the refusal shows on the section | SCRUM-135 |
| TC-US14-16 | 5, 6 | An assigned staff member; a mocked `EVENT_STARTED` | The coordinator presses Unassign | The person moves back to available and the log shows the assign and the unassign; the "already started" refusal is shown | SCRUM-135 |
| TC-US14-17 | 1, 3, 5, 6 | Acting as the coordinator, a line is added to the demo event; acting as Tech support, it's approved | The coordinator assigns Terry Ong; then unassigns him | Terry shows as assigned, then available again; the log shows both, with the coordinator and the time. Rerun after a reseed, as for TC-US26-17 | SCRUM-135 |

## Run log

| Date | Subtask | What ran | Result |
| --- | --- | --- | --- |
| 31 Oct | SCRUM-133 | `pytest` (local Postgres): `tests/equipment/test_tech_staff_schema.py`, then the full backend suite; `alembic downgrade -1` and `upgrade head`; the seed | Tests written first: they failed on collection (no `TechStaffAssignment`). After the change: 11 items for TC-US14-01 to 03 pass. TC-US16A's seeded-login count changed from 12 to 13 for the second Tech support user. Whole backend suite 1198 passed; the migration round-trips and the seed runs. Built on SCRUM-118's branch (#102), so its migration chains after `20261106_1200_scrum118_grants` |
| 31 Oct | SCRUM-134 | `pytest` (local Postgres): `tests/equipment/test_tech_staff_api.py` and `tests/user/test_role_scope.py`, then the full backend suite | Tests written first: the new file failed on collection (no `tech_staff_service`) and TC-US16B-14 failed on the three unknown routes. After the change: 28 items for TC-US14-05 to 14 pass, and the three routes pass the role matrix. TC-US14-13 fails with the staff row's lock taken out (`[201, 201]`) and passes with it, including three reruns. Whole backend suite 1232 passed. No migration |
| 31 Oct | SCRUM-135 | Vitest (`npm test`), `npm run lint`, `npm run build`; E2E on chromium against a local API (`AUTH_DEV_HEADERS=true`) after a reseed | Tests written first: the five new cases in `equipment.integration.test.tsx` failed (no section). After the change: they pass, as TC-US14-15 and 16; whole Vitest suite 419 passed; lint and build clean. TC-US14-17 passes in `e2e/tests/equipment.spec.ts`, and the whole E2E suite (40 run, the Supabase login and sign-up tests skipped) passes after a reseed. It first used Projector screen, which TC-US26-16's `Projector` row also matched by name, so it uses Webcam |
