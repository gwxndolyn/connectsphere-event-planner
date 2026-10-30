# US5 — Check equipment availability (SCRUM-9): test cases

**Story:** As a Technical Support Staff member, I want to check whether requested equipment is available for an event's date and time so that I can confirm whether the technical requirements can be met.

**Source of truth:** the acceptance criteria in Jira SCRUM-9 and its subtasks SCRUM-124 to SCRUM-126, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. View, for the requested type and quantity, how much is available for the required date and time.
2. Equipment reserved for another event in that period is excluded.
3. Equipment damaged, being repaired or otherwise unavailable is excluded.
4. Shown whether the available quantity is sufficient, or short and by how much.
5. A check only: no reservation is created or changed.
6. Based only on quantity, condition and reservations for the event's own times; no venue setup or turnaround.
7. Each item's storage location is shown for reference; it never blocks anything.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-124 | `equipment_types` stock, out-of-service count and storage location; `equipment_reservations` (schema only); seeded stock | `backend/tests/equipment/test_equipment_stock_schema.py` |
| 2 | SCRUM-125 | `POST /api/v1/equipment-lines/{line_id}/availability-check` for Tech Support; the latest outcome recorded on the line (migration `20261102_1200_us5_check_outcome`) | `backend/tests/equipment/test_equipment_availability.py`; the route in US16b's role matrix (`tests/user/test_role_scope.py`, TC-US16B-14) |
| 3 | SCRUM-126 | **Check availability** on Tech support's equipment queue; each line's last recorded check | `frontend/src/features/equipment/equipment.integration.test.tsx` (fake backend: `setAvailability` in `src/test/server.ts`); `e2e/tests/equipment.spec.ts` |

## Decisions for this story

- **Stock is per type** (D62, `DECISION-PENDING`): a total and one out-of-service count, following the 12 Oct customer clarification (as D41). Damaged, under repair and otherwise unavailable are one count, since AC 3 treats them alike.
- **Only the seed records stock** (D63, `DECISION-PENDING`): no AC asks for a screen to edit it.
- **`equipment_reservations` is created here**, ahead of US27 (SCRUM-95), because AC 2 subtracts other events' reservations. US27 adds reserving, release and the link to the approved line in its own migration.
- **The latest outcome is recorded on the line** (D64, SCRUM-125; decided by the acting PO on 30 Oct) _(changed 30 Oct; first read as "not stored")_: sufficient, shortfall, who and when, in four columns on `equipment_request_lines`. A newer check replaces it; editing the line's quantity or type clears it; every line read-back shows it as `availability_check`. It never reserves (AC 5) and doesn't block a review. The columns are a second migration in SCRUM-125's PR, because SCRUM-124's (#93) had already merged.
- **TC-US5-06 uses two venues** _(changed 30 Oct)_: at one venue, `venue_bookings_no_overlap` refuses the second booking when the 30-minute turnaround clashes, so the case as first written couldn't exist. Buffers only matter for equipment when the events are at different venues, so the earlier event is at another venue and its turnaround runs into the line's event; the check still ignores it.
- **Back-to-back events don't overlap** (SCRUM-125), as for venues (D21).

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US5-01 | Schema | A database at the previous head | `alembic upgrade head` | `equipment_types` has the three new columns with their defaults; `equipment_reservations` exists with RLS on; one Alembic head | SCRUM-124 |
| TC-US5-02 | 3, 7 | A catalogue entry; a reservation | Saved with a negative stock, out-of-service below 0 or above the stock, or a blank location; a reservation with quantity 0 or negative, or an unknown event or type | The database rejects it on a named CHECK or foreign key | SCRUM-124 |
| TC-US5-03 | Seed | The seed | Runs (twice) | Every catalogue type has a stock and a storage location, some have units out of service; the second run changes nothing | SCRUM-124 |
| TC-US5-04 | 1, 2, 3, 4, 7 | A type with stock 10, 2 out of service and 3 reserved by another overlapping event; a line for 4 of it | Tech Support checks the line | `200`: total 10, out of service 2, reserved elsewhere 3, available 5, sufficient, shortfall 0, with the storage location and the event's window | SCRUM-125 |
| TC-US5-05 | 2 | Reservations of the type on an event that partly overlaps, one that is back-to-back, one on another day, one on the line's own event, and one of another type | Tech Support checks the line | Only the partly overlapping event's reservation is subtracted | SCRUM-125 |
| TC-US5-06 | 6 | Another event, at a different venue with a 30-minute turnaround, ending 10 minutes before this one starts (so its turnaround runs into this event), holding a reservation of the type | Tech Support checks the line | That reservation isn't subtracted; the window is the event's own start and end | SCRUM-125 |
| TC-US5-07 | 4 | A line asking for more than is available; a type whose out-of-service and reserved units exceed its stock | Tech Support checks each | Not sufficient, with the shortfall (requested − available); available is 0, never negative | SCRUM-125 |
| TC-US5-08 | 5 | A pending line | Tech Support checks it twice; then again after another event reserves some | Same answer the first two times; the line records the latest outcome (sufficient, shortfall, who, when), shown as `availability_check` in the queue (null before any check), and the third check replaces it. No reservation is created; the line's status, quantity and review are unchanged _(changed 30 Oct, D64)_ | SCRUM-125 |
| TC-US5-09 | 7 | A type with no storage location | Tech Support checks a line of it | Answered as usual with the location empty; location never changes the result | SCRUM-125 |
| TC-US5-10 | — | Other roles; no identity; an unknown line | They check a line | `403 FORBIDDEN`; `401 UNAUTHENTICATED`; `404 NOT_FOUND`; nothing is recorded | SCRUM-125 |
| TC-US5-11 | 1, 4, 7 | Acting as the coordinator, a line is added to the demo event; then acting as Tech support | Opens the queue and presses **Check availability** on that line; repeats for a line asking for more than the seeded stock | The first shows available against requested, Sufficient and the storage location; the second shows Short by the right number | SCRUM-126 |
| TC-US5-12 | 2, 3, 5 | A mocked availability result; a mocked API error | The row is checked | Stock, out of service, reserved for other events and available are shown; the error shows on that row only; the line's status and Approve / Reject stay as they were | SCRUM-126 |
| TC-US5-13 | 5 | A line with a recorded check | The coordinator edits its quantity, or its type; or only its notes | The recorded check is cleared after a quantity or type edit, and kept after a notes-only edit _(added 30 Oct, D64)_ | SCRUM-125 |
| TC-US5-14 | Schema | A database at the previous head; a request line | `alembic upgrade head`; a check is saved without its time or checker, or with a shortfall that contradicts sufficient | One Alembic head; the line is refused on `equipment_request_lines_availability_check_consistent` _(added 30 Oct, D64)_ | SCRUM-125 |
| TC-US5-15 | 5 | A line with a recorded check and one never checked; then a line just checked | Tech support opens the queue; then approves the checked line | The first shows its last check (Sufficient or Short by N, and when), the second none; the approval goes through with no "changed since you loaded it" warning (D64) _(added 30 Oct)_ | SCRUM-126 |

## Run log

| Date | Subtask | What ran | Result |
| --- | --- | --- | --- |
| 30 Oct | SCRUM-124 | `pytest` (local Postgres): `tests/equipment/test_equipment_stock_schema.py`, then the full backend suite; `alembic downgrade -1` and `upgrade head` | Tests written first: they failed on collection (no `EquipmentReservation`). After the change: 13 items for TC-US5-01 to 03 pass; whole backend suite 1024 passed. Two existing tests needed loosening for the new columns and head: TC-US26-01 (`equipment_types` has _at least_ its own columns) and TC-US16B-29 (one head that contains D51's migration). The migration round-trips |
| 30 Oct | SCRUM-125 | `pytest` (local Postgres): `tests/equipment/test_equipment_availability.py`, then the full backend suite | Tests written first: all 15 failed with `404` (no route). After the endpoint: 15 items for TC-US5-04 to 10 pass. TC-US16B-14's route matrix needed the new route (Tech Support only). TC-US5-06 changed to two venues (above), in Jira too. Whole backend suite 1040 passed |
| 30 Oct | SCRUM-125, recorded outcome | Failing tests first: TC-US5-08 rewritten and TC-US5-13, 14 added, TC-US5-04 to 10 moved to `POST …/availability-check`; all 25 failed (no route, no columns). Then the migration, the recorded check, the edit clearing it and `availability_check` on every line | 25 items for TC-US5-04 to 10, 13 and 14 pass; TC-US26-01 loosened for the line's new columns; whole backend suite 1050 passed; the migration round-trips |
| 30 Oct | SCRUM-126 | Vitest (lint, build, unit and integration), then Playwright against the local API on a reseeded database | Failing tests first: the 4 integration tests for TC-US5-12 and 15 failed (no button), the 14 existing ones passed. TC-US5-11 (E2E) was written after the screen, so it was run once against the old queue screen to confirm it fails (no Check availability button), then on the new one. After the screen: lint and build clean, Vitest 335 passed, E2E (chromium) 34 passed including TC-US5-11 |
