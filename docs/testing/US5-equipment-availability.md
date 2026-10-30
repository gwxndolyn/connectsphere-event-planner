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
| 2 | SCRUM-125 | `GET /api/v1/equipment-lines/{line_id}/availability` for Tech Support | backend `pytest` |
| 3 | SCRUM-126 | **Check availability** on Tech support's equipment queue | Vitest; `e2e/tests/` |

## Decisions for this story

- **Stock is per type** (D62, `DECISION-PENDING`): a total and one out-of-service count, following the 12 Oct customer clarification (as D41). Damaged, under repair and otherwise unavailable are one count, since AC 3 treats them alike.
- **Only the seed records stock** (D63, `DECISION-PENDING`): no AC asks for a screen to edit it.
- **`equipment_reservations` is created here**, ahead of US27 (SCRUM-95), because AC 2 subtracts other events' reservations. US27 adds reserving, release and the link to the approved line in its own migration.
- **"Records the outcome" is read as shown, not stored** (SCRUM-125, `DECISION-PENDING`): storing each check would add a table no AC reads.
- **Back-to-back events don't overlap** (SCRUM-125), as for venues (D21).

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US5-01 | Schema | A database at the previous head | `alembic upgrade head` | `equipment_types` has the three new columns with their defaults; `equipment_reservations` exists with RLS on; one Alembic head | SCRUM-124 |
| TC-US5-02 | 3, 7 | A catalogue entry; a reservation | Saved with a negative stock, out-of-service below 0 or above the stock, or a blank location; a reservation with quantity 0 or negative, or an unknown event or type | The database rejects it on a named CHECK or foreign key | SCRUM-124 |
| TC-US5-03 | Seed | The seed | Runs (twice) | Every catalogue type has a stock and a storage location, some have units out of service; the second run changes nothing | SCRUM-124 |
| TC-US5-04 | 1, 2, 3, 4, 7 | A type with stock 10, 2 out of service and 3 reserved by another overlapping event; a line for 4 of it | Tech Support checks the line | `200`: total 10, out of service 2, reserved elsewhere 3, available 5, sufficient, shortfall 0, with the storage location and the event's window | SCRUM-125 |
| TC-US5-05 | 2 | Reservations of the type on an event that partly overlaps, one that is back-to-back, one on another day, one on the line's own event, and one of another type | Tech Support checks the line | Only the partly overlapping event's reservation is subtracted | SCRUM-125 |
| TC-US5-06 | 6 | Another event at the same venue ending 10 minutes before this one starts, with a 30-minute venue turnaround, holding a reservation of the type | Tech Support checks the line | That reservation isn't subtracted; the window is the event's own start and end | SCRUM-125 |
| TC-US5-07 | 4 | A line asking for more than is available; a type whose out-of-service and reserved units exceed its stock | Tech Support checks each | Not sufficient, with the shortfall (requested − available); available is 0, never negative | SCRUM-125 |
| TC-US5-08 | 5 | A pending line | Tech Support checks it twice | Same answer both times; no reservation is created and the line is unchanged | SCRUM-125 |
| TC-US5-09 | 7 | A type with no storage location | Tech Support checks a line of it | Answered as usual with the location empty; location never changes the result | SCRUM-125 |
| TC-US5-10 | — | Other roles; no identity; an unknown line | They check a line | `403 FORBIDDEN`; `401 UNAUTHENTICATED`; `404 NOT_FOUND` | SCRUM-125 |
| TC-US5-11 | 1, 4, 7 | Acting as the coordinator, a line is added to the demo event; then acting as Tech support | Opens the queue and presses **Check availability** on that line; repeats for a line asking for more than the seeded stock | The first shows available against requested, Sufficient and the storage location; the second shows Short by the right number | SCRUM-126 |
| TC-US5-12 | 2, 3, 5 | A mocked availability result; a mocked API error | The row is checked | Stock, out of service, reserved for other events and available are shown; the error shows on that row only; the line's status and Approve / Reject stay as they were | SCRUM-126 |

## Run log

| Date | Subtask | What ran | Result |
| --- | --- | --- | --- |
| 30 Oct | SCRUM-124 | `pytest` (local Postgres): `tests/equipment/test_equipment_stock_schema.py`, then the full backend suite; `alembic downgrade -1` and `upgrade head` | Tests written first: they failed on collection (no `EquipmentReservation`). After the change: 13 items for TC-US5-01 to 03 pass; whole backend suite 1024 passed. Two existing tests needed loosening for the new columns and head: TC-US26-01 (`equipment_types` has *at least* its own columns) and TC-US16B-29 (one head that contains D51's migration). The migration round-trips |
