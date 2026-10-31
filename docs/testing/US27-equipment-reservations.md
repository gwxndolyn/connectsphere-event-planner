# US27 — Reserve equipment for an event (SCRUM-95): test cases

**Story:** As a Technical Support Staff member, I want to reserve available equipment for an event so that it's committed to that event and not double-allocated.

**Source of truth:** the acceptance criteria in Jira SCRUM-95 and its subtasks SCRUM-130 to SCRUM-132, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Reserve a quantity of a type for an approved equipment request, for the event's own date and time (no venue setup or turnaround).
2. Not more than the available quantity for that period (US5's availability check).
3. A reservation reduces the available quantity for overlapping events.
4. The reservation is linked to its event, and released if the event is cancelled.
5. A reservation can be released, returning the quantity to availability.
6. The full approved quantity or nothing; no partial reservations.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-130 | Each reservation fulfils one approved line (`request_line_id`, composite foreign key) and records who reserved it; the reseed removes the demo event's reservations | `backend/tests/equipment/test_equipment_reservation_schema.py` |
| 2 | SCRUM-131 | Reserve and release (`POST` / `DELETE /api/v1/equipment-lines/{id}/reservation`) with row locking; `?status=approved`; `reservation` on every line | backend `pytest`; the routes in US16b's role matrix (TC-US16B-14) |
| 3 | SCRUM-132 | **Approved: to reserve** on Tech support's Equipment screen; "Reserved" on the coordinator's lines | Vitest; `e2e/tests/equipment.spec.ts` |

## Decisions for this story

All approved 31 Oct, in `claude_instructions.md` §1a.

- **D74, releasing deletes the reservation:** no history, and US5's sum of reservations stays as it is.
- **D75, a cancelled event's reservations count as released** until US9 (SCRUM-12) builds cancellation: they stop counting in US5's check and when reserving, and the line reads as released. US9 deletes them when it cancels an event; Nic was asked on SCRUM-12.
- **D76, only `planning` or `confirmed` events** can have equipment reserved, as for adding US26's lines.

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US27-01 | Schema | A database at the previous head | `alembic upgrade head` | `equipment_reservations` has `request_line_id` (unique) and `reserved_by_user_id`, both not null; one Alembic head | SCRUM-130 |
| TC-US27-02 | 1 | An approved line and its reservation | A reservation is saved with a different event or type from its line's; or a second one for the same line | Refused on the composite foreign key; refused on the unique line | SCRUM-130 |
| TC-US27-03 | — | A reservation | Saved with an unknown line or user | Refused on a foreign key | SCRUM-130 |
| TC-US27-04 | — | Reservations on Equipment Request Demo's lines and on another event's line | The seed runs | The demo event's reservations and lines are gone; the other event's reservation and line remain | SCRUM-130 |
| TC-US27-05 | 1, 6 | An approved line for 4 of a type with enough stock | Tech Support reserves it | `201`: a reservation for 4, linked to the line's event and type, with who and when | SCRUM-131 |
| TC-US27-06 | 6 | An approved line | The reserve request sends a quantity | `422`: only the full quantity can be reserved | SCRUM-131 |
| TC-US27-07 | 2, 6 | An approved line for more than is available (out of service and other overlapping reservations) | Tech Support reserves it | `409 INSUFFICIENT_EQUIPMENT` with available, requested and shortfall; nothing saved | SCRUM-131 |
| TC-US27-08 | 1, 2 | Available exactly equal to the quantity; another event back-to-back holding a reservation; another at a venue whose turnaround runs into this event | Tech Support reserves | Reserved in each case: the boundary fits, back-to-back doesn't overlap, venue setup and turnaround aren't added | SCRUM-131 |
| TC-US27-09 | 3 | A reservation on one event | US5's check runs for an overlapping event's line, and for a non-overlapping one | The overlapping one's `reserved_elsewhere` includes it; the other's doesn't | SCRUM-131 |
| TC-US27-10 | 1 | A pending line; a rejected line; a reserved line; an approved line on an event that isn't planning or confirmed | Tech Support reserves | `409 LINE_NOT_APPROVED`; `409 LINE_NOT_APPROVED`; `409 ALREADY_RESERVED`; `409 EVENT_NOT_ELIGIBLE`; nothing saved | SCRUM-131 |
| TC-US27-11 | 2 | Two approved lines on overlapping events, with stock for only one | Both are reserved at the same moment | One `201`, the other `409 INSUFFICIENT_EQUIPMENT` | SCRUM-131 |
| TC-US27-12 | 5 | A reserved line; an approved line never reserved | Tech Support releases each | `204` and the units are available again, then the line can be reserved again; `409 NOT_RESERVED` | SCRUM-131 |
| TC-US27-13 | 4 | A reservation whose event is then cancelled | US5's check runs for an overlapping line, another line is reserved, and the line is read | The cancelled event's units aren't counted in either, and the line's `reservation` reads as released because the event was cancelled | SCRUM-131 |
| TC-US27-14 | 4 | A reserved approved line | Tech Support lists `?status=approved`; the coordinator lists the event's lines | Both show its `reservation` with quantity, who and when; a line not reserved shows null | SCRUM-131 |
| TC-US27-15 | — | Other roles; no identity; an unknown line | They reserve or release | `403 FORBIDDEN`; `401 UNAUTHENTICATED`; `404 NOT_FOUND` | SCRUM-131 |
| TC-US27-16 | 1, 2, 5, 6 | Approved lines in the fake backend, one reserved; a mocked `INSUFFICIENT_EQUIPMENT` | Tech support opens Equipment, reserves a line, releases the reserved one, then reserves a line that's short | Approved lines are listed with their state; Reserve sends no quantity and the row reads Reserved; Release makes it unreserved; the short one reads "Short by N: can't reserve" on that row only | SCRUM-132 |
| TC-US27-17 | 4 | A reserved approved line; a line released because its event was cancelled | The coordinator opens the event's equipment; Tech support views the approved list | The coordinator sees "Reserved"; the cancelled event's line reads as released, with no Release button | SCRUM-132 |
| TC-US27-18 | 1, 4, 5 | Acting as the coordinator, a line is added to the demo event; acting as Tech support, it's approved | Tech support reserves it; the coordinator opens the event; Tech support releases it | Reserved in Tech support's list; the coordinator sees Reserved; after release it's unreserved. Rerun after a reseed, as for TC-US26-17 | SCRUM-132 |

## Run log

| Date | Subtask | What ran | Result |
| --- | --- | --- | --- |
| 31 Oct | SCRUM-130 | `pytest` (local Postgres): `tests/equipment/test_equipment_reservation_schema.py`, then the full backend suite; `alembic downgrade -1` and `upgrade head`; the seed | Tests written first: all 9 failed (no columns, no migration). After the change: 9 items for TC-US27-01 to 04 pass. Three US5 tests changed, since a reservation now needs a line: their helpers reserve through an approved line (`test_equipment_stock_schema.py`, `test_equipment_availability.py`), TC-US5-05's own-event case reserves the checked line itself (D41 allows no second live line of the type), and TC-US5-01 checks the reservation table has _at least_ its own columns. Whole backend suite 1095 passed; the migration round-trips and the seed runs |
| 31 Oct | SCRUM-131 | `pytest` (local Postgres): `tests/equipment/test_equipment_reservation_api.py`, then the full backend suite | Tests written first: all 21 failed (no routes). After the endpoints: 21 items for TC-US27-05 to 15 pass, and TC-US16B-14's matrix has both routes (Tech Support only). TC-US27-11 is a real race (two sessions on separate connections, as TC-US22-15): run with the type's lock taken out it fails with both reserving (`[201, 201]`), and passes with it. Whole backend suite 1118 passed |
