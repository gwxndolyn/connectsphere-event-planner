# Requirements → tests traceability (Release 1)

Generated from the code by scanning test names (`test_tc_us<story>_<nn>` in pytest) and `TC-US<story>-<nn>`
tags in Vitest and Playwright. Test IDs are the ones in the **Test Cases** tab of the Master Backlog and in
[`claude_instructions.md` §4](../../claude_instructions.md#4-test-cases). Per-story evidence (screenshots, AC by AC)
is in the `US*.md` files in this folder.

Counts are **distinct test IDs** (a parametrised pytest ID counts once). US8a–d share the `TC-US8-nn` series.

## Core feature coverage

| # | Core feature | Stories (Jira) | Backend test IDs (pytest) | Frontend test IDs (Vitest) | E2E specs (Playwright) |
| --- | --- | --- | --- | --- | --- |
| F1 | User Authorisation and Authentication | US16a (SCRUM-81), US16b (SCRUM-82) | 56 | 16 | `clarification-request.spec.ts`, `login.spec.ts`, `sign-up.spec.ts` |
| F2 | Event Request Creation | US1 (SCRUM-20) | 16 | 2 | `event-request-draft.spec.ts` |
| F3 | Draft Event Requests | US1 (SCRUM-20) | 16 | 2 | `event-request-draft.spec.ts` |
| F4 | Event Review and Approval | US8a (SCRUM-11), US8b (SCRUM-73), US8c (SCRUM-74), US8d (SCRUM-75), US17 (SCRUM-84) | 50 | 2 | `event-request-decision.spec.ts` |
| F5 | Coordinator Assignment | US10a (SCRUM-13), US10b (SCRUM-67), US10c (SCRUM-68), US10d (SCRUM-69), US10e (SCRUM-83), US19 (SCRUM-86) | 85 | 29 | `assign-coordinator.spec.ts`, `transfer-request.spec.ts` |
| F6 | Event Status Management | US9 (SCRUM-12), US18 (SCRUM-85), US30a (SCRUM-99), US30b (SCRUM-100) | 123 | 17 | `event-cancellation.spec.ts`, `event-confirmation.spec.ts`, `safety-review.spec.ts` |
| F7 | Event Information Management | US12 (SCRUM-15), US15 (SCRUM-18) | 33 | 7 | `agenda.spec.ts`, `event-edit.spec.ts` |
| F8 | Venue Catalogue | US20 (SCRUM-87) | 17 | 0 | `venue-catalogue.spec.ts` |
| F9 | Venue Availability Calendar | US21 (SCRUM-88), US23a (SCRUM-90) | 28 | 15 | `venue-calendar.spec.ts`, `venue-unavailability.spec.ts` |
| F10 | Venue Search and Filtering | US2 (SCRUM-7), US23b (SCRUM-91) | 27 | 7 | `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts`, `venue-calendar.spec.ts`, `venue-replacement.spec.ts`, `venue-search.spec.ts` |
| F11 | Venue Suitability Checking | US2 (SCRUM-7), US22 (SCRUM-89) | 31 | 4 | `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts`, `venue-calendar.spec.ts`, `venue-search.spec.ts` |
| F12 | Venue Booking Request | US22 (SCRUM-89), US24 (SCRUM-92) | 40 | 12 | `attendee-registration.spec.ts`, `events-board.spec.ts`, `multi-venue.spec.ts`, `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts` |
| F13 | Venue Booking Approval | US4 (SCRUM-8) | 9 | 4 | `venue-booking-decision.spec.ts` |
| F14 | Booking Conflict Detection | US13 (SCRUM-16), US25 (SCRUM-93), US4 (SCRUM-8) | 42 | 13 | `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts`, `venue-hold.spec.ts`, `venue-search.spec.ts` |
| F15 | Equipment Request Management | US26 (SCRUM-94), US14 (SCRUM-17) | 32 | 6 | `equipment.spec.ts` |
| F16 | Equipment Availability Checking | US5 (SCRUM-9) | 12 | 2 | `equipment.spec.ts` |
| F17 | Equipment Reservation | US27 (SCRUM-95) | 15 | 2 | `equipment.spec.ts` |
| F18 | Attendee Registration | US3 (SCRUM-2), US11 (SCRUM-5), US7 (SCRUM-6), US6a (SCRUM-10), US6b (SCRUM-72), US28 (SCRUM-96) | 97 | 16 | `attendee-registration.spec.ts`, `event-registrations.spec.ts`, `events-board.spec.ts` |
| F19 | Event Change Requests | US29a (SCRUM-97), US29b (SCRUM-98), US12 (SCRUM-15) | 65 | 25 | `change-request-review.spec.ts`, `change-request.spec.ts`, `event-edit.spec.ts` |
| F20 | Notification System | US31 (SCRUM-107), US8b (SCRUM-73), US10c (SCRUM-68) | 67 | 20 | `notifications.spec.ts` |

## Per story

| Story | Jira | Backend IDs | Frontend IDs | Backend test files | E2E specs |
| --- | --- | --- | --- | --- | --- |
| US1 | SCRUM-20 | 16 | 2 | `backend/tests/event/test_event_request_schema.py`<br>`backend/tests/event/test_event_requests.py` | `event-request-draft.spec.ts` |
| US2 | SCRUM-7 | 12 | 0 | `backend/tests/venue/test_venue_search.py` | `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts`, `venue-calendar.spec.ts`, `venue-search.spec.ts` |
| US3 | SCRUM-2 | 18 | 4 | `backend/tests/event/test_available_events.py`<br>`backend/tests/registration/test_register.py`<br>`backend/tests/registration/test_registration_notices.py`<br>`backend/tests/registration/test_waitlist_join.py` | `events-board.spec.ts` |
| US4 | SCRUM-8 | 9 | 4 | `backend/tests/venue/test_booking_decision_api.py` | `venue-booking-decision.spec.ts` |
| US5 | SCRUM-9 | 12 | 2 | `backend/tests/equipment/test_equipment_availability.py`<br>`backend/tests/equipment/test_equipment_stock_schema.py` | `equipment.spec.ts` |
| US6a | SCRUM-10 | 15 | 1 | `backend/tests/event/test_available_events.py`<br>`backend/tests/registration/test_waitlist_rules.py` | `attendee-registration.spec.ts` |
| US6b | SCRUM-72 | 10 | 0 | `backend/tests/registration/test_accept_offer.py` | `attendee-registration.spec.ts` |
| US7 | SCRUM-6 | 27 | 5 | `backend/tests/registration/test_offer_expiry_on_read.py`<br>`backend/tests/registration/test_offer_lifecycle.py`<br>`backend/tests/registration/test_registration_notices.py`<br>`backend/tests/registration/test_waitlist_offer.py`<br>`backend/tests/registration/test_withdraw.py` | — |
| US8a | SCRUM-11 | 35 | 2 | `backend/tests/event/test_event_request_clarification_api.py`<br>`backend/tests/event/test_event_request_clarification_response.py`<br>`backend/tests/event/test_event_request_clarifications.py` | — |
| US8b | SCRUM-73 | 35 | 2 | `backend/tests/event/test_event_request_clarification_api.py`<br>`backend/tests/event/test_event_request_clarification_response.py`<br>`backend/tests/event/test_event_request_clarifications.py` | — |
| US8c | SCRUM-74 | 35 | 2 | `backend/tests/event/test_event_request_clarification_api.py`<br>`backend/tests/event/test_event_request_clarification_response.py`<br>`backend/tests/event/test_event_request_clarifications.py` | — |
| US8d | SCRUM-75 | 35 | 2 | `backend/tests/event/test_event_request_clarification_api.py`<br>`backend/tests/event/test_event_request_clarification_response.py`<br>`backend/tests/event/test_event_request_clarifications.py` | — |
| US9 | SCRUM-12 | 29 | 6 | `backend/tests/event/test_cancellation_race.py`<br>`backend/tests/event/test_cancellation_schema.py`<br>`backend/tests/event/test_cancellations.py`<br>`backend/tests/event/test_cancelled_event_reads.py` | `event-cancellation.spec.ts` |
| US10a | SCRUM-13 | 26 | 5 | `backend/tests/event/test_coordinator_assignment_api.py`<br>`backend/tests/event/test_coordinator_assignment_schema.py`<br>`backend/tests/event/test_coordinator_lead_notification.py` | `assign-coordinator.spec.ts` |
| US10b | SCRUM-67 | 6 | 3 | `backend/tests/event/test_coordinator_workload.py` | `assign-coordinator.spec.ts` |
| US10c | SCRUM-68 | 7 | 0 | `backend/tests/event/test_assignment_notifications.py` | — |
| US10d | SCRUM-69 | 11 | 4 | `backend/tests/event/test_assignment_history.py` | `assign-coordinator.spec.ts` |
| US10e | SCRUM-83 | 24 | 10 | `backend/tests/event/test_reassignment.py` | `transfer-request.spec.ts` |
| US11 | SCRUM-5 | 12 | 5 | `backend/tests/registration/test_my_registrations.py` | `events-board.spec.ts` |
| US12 | SCRUM-15 | 21 | 5 | `backend/tests/event/test_event_edits.py` | `event-edit.spec.ts` |
| US13 | SCRUM-16 | 15 | 3 | `backend/tests/venue/test_buffer_api.py`<br>`backend/tests/venue/test_buffer_schema.py` | `venue-booking.spec.ts`, `venue-buffers.spec.ts`, `venue-search.spec.ts` |
| US14 | SCRUM-17 | 13 | 2 | `backend/tests/equipment/test_tech_staff_api.py`<br>`backend/tests/equipment/test_tech_staff_schema.py` | `equipment.spec.ts` |
| US15 | SCRUM-18 | 12 | 2 | `backend/tests/agenda/test_event_sessions_api.py`<br>`backend/tests/agenda/test_event_sessions_schema.py` | `agenda.spec.ts` |
| US16a | SCRUM-81 | 35 | 7 | `backend/tests/user/test_auth_link_schema.py`<br>`backend/tests/user/test_me.py`<br>`backend/tests/user/test_profile.py`<br>`backend/tests/user/test_seed_auth_logins.py`<br>`backend/tests/user/test_token_identity.py` | `login.spec.ts`, `sign-up.spec.ts` |
| US16b | SCRUM-82 | 21 | 9 | `backend/tests/user/test_role_scope.py`<br>`backend/tests/user/test_user_roles.py` | `clarification-request.spec.ts`, `login.spec.ts` |
| US17 | SCRUM-84 | 15 | 0 | `backend/tests/event/test_event_request_decisions.py` | `event-request-decision.spec.ts` |
| US18 | SCRUM-85 | 43 | 2 | `backend/tests/event/test_confirmation.py` | `event-confirmation.spec.ts` |
| US19 | SCRUM-86 | 11 | 7 | `backend/tests/event/test_lead_oversight.py` | `assign-coordinator.spec.ts` |
| US20 | SCRUM-87 | 17 | 0 | `backend/tests/venue/test_venue_api.py`<br>`backend/tests/venue/test_venue_schema.py` | `venue-catalogue.spec.ts` |
| US21 | SCRUM-88 | 14 | 8 | `backend/tests/venue/test_calendar.py` | `venue-calendar.spec.ts` |
| US22 | SCRUM-89 | 19 | 4 | `backend/tests/venue/test_booking_api.py`<br>`backend/tests/venue/test_booking_schema.py`<br>`backend/tests/venue/test_booking_seed.py` | `venue-booking-decision.spec.ts`, `venue-booking.spec.ts` |
| US23a | SCRUM-90 | 14 | 7 | `backend/tests/venue/test_unavailability.py`<br>`backend/tests/venue/test_unavailability_race.py`<br>`backend/tests/venue/test_unavailability_schema.py` | `venue-unavailability.spec.ts` |
| US23b | SCRUM-91 | 15 | 7 | `backend/tests/venue/test_replacement.py`<br>`backend/tests/venue/test_replacement_race.py`<br>`backend/tests/venue/test_replacement_schema.py` | `venue-replacement.spec.ts` |
| US24 | SCRUM-92 | 21 | 8 | `backend/tests/venue/test_calendar.py`<br>`backend/tests/venue/test_multi_venue_api.py`<br>`backend/tests/venue/test_multi_venue_schema.py` | `attendee-registration.spec.ts`, `events-board.spec.ts`, `multi-venue.spec.ts`, `venue-booking-decision.spec.ts`, `venue-booking.spec.ts`, `venue-buffers.spec.ts` |
| US25 | SCRUM-93 | 18 | 6 | `backend/tests/venue/test_hold_schema.py`<br>`backend/tests/venue/test_holds.py` | `venue-hold.spec.ts` |
| US26 | SCRUM-94 | 19 | 4 | `backend/tests/equipment/test_equipment_api.py`<br>`backend/tests/equipment/test_equipment_schema.py`<br>`backend/tests/equipment/test_equipment_seed.py` | `equipment.spec.ts` |
| US27 | SCRUM-95 | 15 | 2 | `backend/tests/equipment/test_equipment_reservation_api.py`<br>`backend/tests/equipment/test_equipment_reservation_schema.py` | `equipment.spec.ts` |
| US28 | SCRUM-96 | 15 | 1 | `backend/tests/registration/test_event_registrations.py` | `event-registrations.spec.ts` |
| US29a | SCRUM-97 | 18 | 5 | `backend/tests/event/test_change_requests.py` | `change-request.spec.ts` |
| US29b | SCRUM-98 | 26 | 15 | `backend/tests/event/test_change_request_decision_schema.py`<br>`backend/tests/event/test_change_request_decisions.py`<br>`backend/tests/event/test_review_flags.py` | `change-request-review.spec.ts` |
| US30a | SCRUM-99 | 32 | 2 | `backend/tests/safety/test_safety_review.py` | `safety-review.spec.ts` |
| US30b | SCRUM-100 | 19 | 7 | `backend/tests/safety/test_safety_review.py` | `safety-review.spec.ts` |
| US31 | SCRUM-107 | 25 | 18 | `backend/tests/notification/test_inbox_api.py`<br>`backend/tests/notification/test_recorder.py` | `notifications.spec.ts` |

## Coverage

CI reports coverage on every run (Backend CI and Frontend CI job summaries; HTML reports uploaded as artifacts).

| Suite | Tests | Statement coverage | Why not 100% |
| --- | --- | --- | --- |
| Backend (pytest, real PostgreSQL) | 1,894 passed, 0 failed | 97% (6,769 statements, 178 missed) | Remaining lines are defensive `except` branches around best-effort notifications and DB-session failures, the production-only `LoggingNotifier` bodies (tests inject `FakeNotifier`), and `core/database.py`'s session factory, which tests override with a transactional session. |
| Frontend (Vitest + Testing Library + MSW) | 554 passed, 0 failed (53 files) | 88.6% statements, 81.5% branches | Unreached branches are mostly error-message `switch` defaults for API codes the UI never receives and loading/abort guards in effects. |
| E2E (Playwright, real backend + seeded DB) | 72 tests in 30 specs | n/a | Journey-level; login/sign-up cases that need Supabase secrets skip in CI. |
