# US26 — Record and review an equipment request (SCRUM-94): test cases

**Story:** As an Event Coordinator, I want to record the equipment an event needs so that Technical Support Staff can review and arrange it.

**Source of truth:** the acceptance criteria in Jira SCRUM-94 and its subtasks SCRUM-108 to SCRUM-110, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The Event Coordinator adds equipment lines to an event they manage: type, quantity and technical notes.
2. The Coordinator edits or removes lines while the request is pending.
3. Technical Support Staff see pending requests and mark each line approved or rejected with a note.
4. Quantity is a positive whole number, and the type exists in the equipment catalogue.
5. The Coordinator is notified when lines are approved or rejected.
6. A line is approved only for its full quantity, or rejected. No partial fulfilment.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-108 | `equipment_types` (seeded) + `equipment_request_lines`; `tech_support` role and a seeded Tech Support user (schema only) | `backend/tests/equipment/test_equipment_schema.py` |
| 2 | SCRUM-109 | Coordinator and Tech Support endpoints; review; coordinator notified | to be added |
| 3 | SCRUM-110 | Equipment screen and Tech Support queue | to be added (lint, build, Playwright) |

## Decisions for this story

- **`tech_support` is added now** (SCRUM-108), under the name the spec planned for US16b (SCRUM-82), so Tech Support's routes check a real role (deviation 33). US16b adds the other new roles.
- **Any active coordinator** may manage an event's equipment until US10 assigns coordinators (`DECISION-PENDING`, as D14).
- **Only events in `planning` or `confirmed`** accept equipment lines (SCRUM-109).
- **No availability check yet:** whether the full quantity is available (AC 6) is Tech Support's judgement until US5 (SCRUM-9) adds stock and condition. Approval is always for the full requested quantity.

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US26-01 | Schema | A database at the previous head | `alembic upgrade head` | Both tables exist with their columns, RLS is on, `user_role` includes `tech_support`; one Alembic head | SCRUM-108 |
| TC-US26-02 | 4 | A request line | Saved with quantity 0 or negative | The database rejects it on a named CHECK | SCRUM-108 |
| TC-US26-03 | 4 | A request line | Saved with an unknown equipment type or event | The database rejects it (foreign key) | SCRUM-108 |
| TC-US26-04 | 3 | A new request line | Saved without a status | It is `pending`; only `pending`, `approved` and `rejected` are allowed | SCRUM-108 |
| TC-US26-05 | Seed | The seed | Runs (twice) | The equipment catalogue and the Tech Support user exist; the second run adds nothing | SCRUM-108 |
| TC-US26-06 | 1 | A coordinator and a confirmed event | Adds a line with type, quantity and notes | `201`; the line is `pending` and records who asked | SCRUM-109 |
| TC-US26-07 | 4 | A coordinator | Quantity is 0, negative or not a whole number; or the type is unknown | `422 INVALID_EQUIPMENT_LINE` naming the field; nothing saved | SCRUM-109 |
| TC-US26-08 | 2 | A pending line | The coordinator edits it, or removes it | The change is saved, or the line is gone | SCRUM-109 |
| TC-US26-09 | 2 | An approved or rejected line | The coordinator edits or removes it | `409 LINE_NOT_PENDING`; unchanged | SCRUM-109 |
| TC-US26-10 | 1 | An event not in `planning` or `confirmed`; an unknown event | A line is added | `409 EVENT_NOT_ELIGIBLE`; `404 NOT_FOUND` | SCRUM-109 |
| TC-US26-11 | 3 | Pending, approved and rejected lines | Tech Support opens the queue | Only pending lines, with their event and equipment type | SCRUM-109 |
| TC-US26-12 | 3 | A pending line | Tech Support approves or rejects it with a note | Status, note, reviewer and time saved; a second review is `409 LINE_NOT_PENDING` | SCRUM-109 |
| TC-US26-13 | 6 | A pending line | Tech Support approves it and sends a quantity | `422`: approval is always the full requested quantity | SCRUM-109 |
| TC-US26-14 | 5 | A line is approved or rejected | The review is saved | The requesting coordinator is notified with the event, type, quantity, decision and note; a notifier failure doesn't undo the review | SCRUM-109 |
| TC-US26-15 | 1, 3 | Other roles; no identity | They add, edit, remove, open the queue or review | `403 FORBIDDEN` for the wrong role; `401 UNAUTHENTICATED` without an identity | SCRUM-109 |
| TC-US26-16 | 1, 2, 4 | Acting as the coordinator | Opens Equipment, picks a seeded event, adds a line with quantity 0, fixes it, edits it, adds and removes another | The quantity error shows on the field; the line appears as Pending; edits show; the removed line is gone | SCRUM-110 |
| TC-US26-17 | 3, 5 | A pending line | Acting as Tech support, approves it with a note; then acting as the coordinator, opens the event | Tech Support's queue no longer lists it; the coordinator sees it as Approved with the note | SCRUM-110 |
