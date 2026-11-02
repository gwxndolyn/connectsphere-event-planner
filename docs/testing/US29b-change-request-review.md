# US29b — Review an event change request (SCRUM-98): test cases

**Story:** As an Event Coordinator, I want to review the changes requested to an event so that its arrangements stay right.

**Source of truth:** the acceptance criteria in Jira SCRUM-98. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The Event Coordinator sees pending change requests for events assigned to them, with current and proposed values.
2. They can approve (the values are applied to the event) or reject with a reason.
3. On approving a significant change (date/time, duration, expected attendance, layout, venue or equipment), the event moves back to Planning and the affected venue bookings, equipment reservations and registrations are flagged for review; nothing is reset or deleted automatically.
4. The Organiser is notified of the decision.
5. The decision and applied changes are recorded in the event history.
6. If the event already had safety approval, a new safety review (US30a) is needed before it can be confirmed again.

**Delivery:** three PRs.

| PR | Work | Tests |
| --- | --- | --- |
| 1, SCRUM-141 | Decision columns on `event_change_requests`, `event_audit_entries.action`, `event_review_flags` (migration `20261115_1200_us29b_decisions`); seeded **Change Request Demo** | `backend/tests/event/test_change_request_decision_schema.py` (TC-US29B-01 to 07) |
| 2, SCRUM-142 | List, approve and reject change requests; list and clear review flags; readiness and safety queue; notices | `backend/tests/event/test_change_request_decisions.py`, `backend/tests/event/test_review_flags.py` (TC-US29B-08 to 25) |
| 3, SCRUM-143 | The coordinator's review panel, flags in the readiness list, the safety notice, the organiser's outcome | `frontend/src/features/changeRequest/changeRequestReview.integration.test.tsx` (TC-US29B-26 to 32); `e2e/tests/change-request-review.spec.ts` (TC-US29B-33) |

## Decisions for this story

All six are **the story owner's defaults, asked of the acting PO (Matthew) on 1 Nov**, and marked `DECISION-PENDING` in the code. They'll be updated when he answers.

- **D102, who decides** (settles D89): the event's assigned coordinator decides an Organiser's request. A coordinator's own US12 critical edit goes to any active Coordinator Lead (D51), through the API only: there is no Lead screen in this story, and a follow-up ticket adds it.
- **D103, significant:** schedule, attendance, layout, venue (accessibility, delivery mode) or equipment; not name, category, purpose or join link.
- **D104, flags:** one row per affected live booking, reserved equipment line, and one for the event's registrations; one open flag per item. The coordinator clears each with an optional note. Open flags block confirming. Nothing on the item changes.
- **D105, statuses:** Confirmed goes back to Planning (its confirmation cleared); Approved and Planning stay; request-stage events just take the values; approving is refused in Preparation, Cancelled, Completed and Rejected. Registration closes until the event is confirmed again.
- **D106, safety** (amends D92): a significant change clears an existing safety approval; the earlier review row stays. The event returns to the Safety Officer's queue once its flags are cleared.
- **D107, stale requests:** if the event changed since the request was made, approving is refused with `409 CHANGE_REQUEST_STALE`; it can still be rejected.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US29B-01 | 2, 5 | A migrated database | A pending request is written with `decided_at`, or an approved one without it or without `decided_by_user_id` | `event_change_requests_decision_consistent` refuses it; a whole decision is accepted |
| TC-US29B-02 | 2 | A migrated database | A rejected request with no or a blank reason, or an approved one with a reason | `…_rejection_reason_only_when_rejected` / `…_not_blank` refuse it |
| TC-US29B-03 | 2 | A request made by user A | It's marked decided by user A | `event_change_requests_decider_not_requester` refuses it (D51) |
| TC-US29B-04 | 3 | An event with an approved booking and an approved line | A flag with an unknown kind, no target, two targets or no fields; a second open flag on the same booking, line or registrations | The named CHECK or unique index refuses it; once the first is cleared, the booking can be flagged again |
| TC-US29B-05 | 3 | A flag | Cleared with no `cleared_by_user_id`; a note without clearing; a blank note | `…_clearance_consistent` / `…_note_only_when_cleared` refuse it |
| TC-US29B-06 | 5 | Entries before US29b, one tied to a change request | Upgrading; writing an unknown action; downgrading with a decided request, a flag or an `applied` entry | `saved` / `requested`; `event_audit_entries_action_known` refuses; the downgrade refuses each, and round-trips cleanly when there are none |
| TC-US29B-07 | all | A seeded database where Change Request Demo was approved back to Planning, flagged and reviewed again, with flags on the other demos' rows | `python -m app.seed` again | Confirmed, safety-approved with exactly one approved review by the seeded Safety officer at `safety_approved_at`, one pending request, no flags or history; booking and reservation intact; the other demos reset without a foreign-key error |
| TC-US29B-08 | 1 | Coordinator C on E1 with a pending Organiser request; another coordinator's E2 with one | C lists change requests | Only E1's, with each field's current and proposed value, the reason and whether it's significant |
| TC-US29B-09 | 1 | A pending request on E1 | The Organiser, an attendee, Venue staff or another coordinator reads, approves or rejects it | `403` (wrong role) or `404 NOT_FOUND` |
| TC-US29B-10 | 2, 4, 5 | A non-significant request on a Confirmed, safety-approved event; a preferred-date request on a Submitted one | C approves | Values applied, status kept, no flags, safety approval kept, `applied` and `decided` entries, the Organiser notified |
| TC-US29B-11 | 3 | A Confirmed event with an approved and a withdrawn booking, a reserved and an unreserved line, two registrations | C approves a start and end change | Planning, confirmation cleared; the approved booking, the reserved line and registrations flagged; nothing else flagged; nothing changed or deleted |
| TC-US29B-12 | 6 | A safety-approved Confirmed event | A significant change is approved | Approval cleared, state `pending`, earlier review kept, confirm `409 EVENT_NOT_READY`; in the safety queue only once flags are cleared |
| TC-US29B-13 | 6 | A safety-approved event; a never-reviewed one | A non-significant change; a significant one | Approval kept; no safety field changed |
| TC-US29B-14 | 2, 4, 5 | A pending request | C rejects with no reason, 1,001 characters, a reason | `422 MISSING_REQUIRED_FIELD`; `422 INVALID_CHANGE_DECISION`; rejected, event unchanged, `decided` entry, Organiser notified with the reason |
| TC-US29B-15 | 2 | An approved request | C approves or rejects it again | `409 CHANGE_REQUEST_NOT_PENDING` with `status` |
| TC-US29B-16 | 2 | A pending request, two sessions at a barrier | One approves and one rejects at once; then two approve at once | One `200`, one `409 CHANGE_REQUEST_NOT_PENDING`; one decision, one effect, one set of entries, one notice |
| TC-US29B-17 | 2 | Two pending requests changing attendance from 50 | Both approved at once | One applies; the other `409 CHANGE_REQUEST_STALE` naming `expected_attendees` |
| TC-US29B-18 | 2 | A request whose field was since saved through US12; a preferred-date request on an event now in Planning | C approves | `409 CHANGE_REQUEST_STALE`, `changed` / `not_at_this_stage`; rejecting works |
| TC-US29B-19 | 2 | A request on a Preparation, Cancelled or Completed event | C approves; C rejects | `409 CHANGE_NOT_ALLOWED`; rejected |
| TC-US29B-20 | 1 | C's own pending US12 edit | C approves; a Lead approves; the Lead tries an Organiser request | `403 SELF_DECISION_NOT_ALLOWED`; applied; `404` |
| TC-US29B-21 | 5 | An approved significant change on a safety-approved Confirmed event | C reads History | `safety_approval_cleared`, `confirmation_cleared`, `status_changed`, each `applied`, `decided`, all tied to the request |
| TC-US29B-22 | 3 | Open flags | C clears one with a note; again; reads readiness; confirms; another coordinator clears | Cleared; `409 FLAG_ALREADY_CLEARED`; readiness item outstanding; `409 EVENT_NOT_READY`; `404` |
| TC-US29B-23 | 4 | An approved and a rejected request | The Organiser lists their requests | Each status and `decided_at`, and the rejection's reason |
| TC-US29B-24 | 4 | A notifier that fails | C approves | The decision stands and the failure is logged |
| TC-US29B-25 | 3 | A booking with an open flag | A second significant change is approved | Still one open flag, with both changes' fields |
| TC-US29B-26 | 1 | Two pending requests on the coordinator's events | They open Event requests | "Change requests to review (2)", each with event, requester, date and Significant where it applies |
| TC-US29B-27 | 1, 3, 6 | A significant request on a safety-approved Confirmed event | They open Review | Current and proposed values, the reason, and a notice of the move to Planning, the flags and the safety review |
| TC-US29B-28 | 2, 3 | That panel | They approve | Approved and Planning; Review after change lists each flag with Mark reviewed; Confirm disabled until all are reviewed |
| TC-US29B-29 | 2 | A pending request | Reject with no reason; with a reason | An inline error; Rejected with the reason |
| TC-US29B-30 | 2 | The API answers stale or not pending | They approve | The message names the fields or says it was decided; the list reloads |
| TC-US29B-31 | 6 | An approved significant change on a safety-approved event | The review screen loads | "A new safety review is needed" and why; Safety check outstanding |
| TC-US29B-32 | 4 | Decided requests | The Organiser opens Change requests | Approved or Rejected, the date and any reason |
| TC-US29B-33 | 1–6 | A fresh seed | The Organiser requests a later start on Change Request Demo; the coordinator reviews and approves it | The coordinator sees Planning, the flags and the safety notice; the Organiser sees Approved and the new times |

## Run log

1 Nov 2026, branch `feat(SCRUM-141)Change-Request-Decision-Schema` on `main` `b321e6d`, local Postgres 16:

- TC-US29B-01 to 07 written first and run failing: missing columns, missing table, unknown revision, no `CHANGE_REQUEST_EVENT`.
- Backend: `pytest`: 1453 passed (TC-US29B-01 to 07, and two seed inventories updated for the new demo: TC-US10A-04's assigned events and TC-US24-04's booking count, now 14).
- Migration: `alembic upgrade head`, `downgrade -1`, `upgrade head` on local Docker; `python -m app.seed` twice.

After merging `origin/main` (#115, US9 cancellations schema, SCRUM-12), 1 Nov 2026: the migration is renamed `20261113_1200_us29b_decisions` and follows `20261112_1200_us9_cancellations` (one head); US29b's decisions are renumbered D99 to D104, since US9 took D98.

- Migration: local database rebuilt (it had run the old revision id), then `alembic upgrade head`, `downgrade -1`, `upgrade head`; `python -m app.seed`.
- Backend: `pytest`: 1480 passed (main's 1472 plus TC-US29B-01 to 07's 8).

After merging `origin/main` (#116, US30b request changes after a safety review, SCRUM-100), 1 Nov 2026: the migration is renamed `20261114_1200_us29b_decisions` and follows `20261113_1200_us30b_changes` (one head); US29b's decisions are renumbered D100 to D105, since US30b took D99. Deviation 64 is now US30b's, so US29b's API and screen deviations will be 68 and 69 (65 and 67 went to US9 in #117 and #119, 66 to US15 in #118).

- Migration: local database downgraded to `20261112_1200_us9_cancellations` before the rename, then `alembic upgrade head`; `python -m app.seed --yes`.
- Backend: `pytest`: 1503 passed (main's 1495 plus TC-US29B-01 to 07's 8). Frontend: Vitest 460 passed.

After merging `origin/main` (421ff52, SCRUM-99 row level security for `safety_reviews`), 1 Nov 2026: the migration keeps its name and is re-chained after `20261114_1200_us30a_rls` (one head).

- Migration: local database downgraded to `20261113_1200_us30b_changes` first, then `alembic upgrade head`; `python -m app.seed --yes`.
- Backend: `pytest`: 1504 passed (main's 1496, with TC-SEC-05, plus TC-US29B-01 to 07's 8).

- Merged origin/main (#117): decisions renumbered D102–D107; backend 1555 collected; `pytest backend/tests/event backend/tests/user`: 616 passed, 1 failed (TC-US9-33: US9's cancellation rejects pending change requests without the decision fields US29b's CHECKs require).
- Calvin's review: renamed to `20261115_1200_us29b_decisions`; held edits log `requested`, with a CHECK; backend 1555 (1554 passed, 1 failed: TC-US9-33, as above).
- #117 clash fixed: cancelling decides the change requests it rejects (`decided_at`, the canceller, "The event was cancelled."); the migration backfills older ones from the approved cancellation; `event_change_requests_decider_not_requester` covers approvals only; backend 1557 passed.
- Merged origin/main (#118): deviations 67 and 68; backend 1585.
- Merged origin/main (#119): deviations 68 and 69; backend 1587.

SCRUM-142 (PR 2), 1 Nov 2026, branch `feat(SCRUM-142)Change-Request-Decision-API`, local Postgres 16:

- TC-US29B-08 to 25 written first in `tests/event/test_change_request_decisions.py` and `test_review_flags.py`; both failed to collect (no `app.event.change_decision_service`).
- Races 16 and 17 run on two committed connections held at a barrier before the event lock, as TC-US27-11.
- Backend: `pytest`: 1625 passed (1587, plus 30 new tests and 8 role-matrix cases for the six routes).
- Local check: approving Change Request Demo's seeded request moved it to Planning, flagged its booking and projector, cleared its safety approval (state `pending`, review kept), and left readiness waiting on the safety check and the flags; the demo was reseeded afterwards.

Calvin's #125 review, note 1, 1 Nov 2026: who decides and who clears are checked again on the locked event. Three tests on two committed connections, reassigning the event just before the lock, failed first (the old coordinator's approve, reject and clear all succeeded) and pass now: `pytest`: 1628 passed.

SCRUM-143 (PR 3), 1 Nov 2026, branch `feat(SCRUM-143)Change-Request-Review-Screen` (from SCRUM-142's), local Postgres 16:

- TC-US29B-26 to 32 written first in `frontend/src/features/changeRequest/changeRequestReview.integration.test.tsx` (12 failed: no fake routes, no screens), and TC-US29B-33 in `e2e/tests/change-request-review.spec.ts` (failed: no Change requests to review on the coordinator's screen).
- TC-US29B-33 asks for expected attendance and equipment needs, fields the seeded start-and-end request doesn't touch, so that request stays pending and not stale; equipment is there for the projector flag (attendance flags bookings and registrations only, D104).
- Frontend: `npm run lint` clean, `tsc -b` clean, `npm run build` passes; Vitest 486 passed (45 files).
- E2E, freshly seeded, backend without `--reload`: 53 passed, 10 skipped (the login and sign-up cases without their secrets), 63 in all; reseeded afterwards.
- Seed fix: a reseed now resets Change Request Demo's equipment needs, so TC-US29B-33 reruns. It also resets room layout and accessibility needs, the other organiser-requestable fields (D90) the seed left alone; TC-US29B-07 sets them, with attendance 30 and "Two projectors", before the reseed and failed first on them.
- Merged origin/main (#123, #129, US25): deviation 69 renumbered 71; counts Backend 1678 passed, Vitest 493 passed (46 files), E2E 64 (54 passed, 10 skipped; freshly seeded, backend without `--reload`, reseeded afterwards).
