# US25 — Place a tentative venue hold that expires (SCRUM-93): test cases

**Story:** As a Venue Staff member, I want to place a temporary hold on a venue with an expiry time so that a coordinator can finalise arrangements without the venue being reserved indefinitely.

**Source of truth:** the acceptance criteria in Jira SCRUM-93. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Venue staff place a hold on a venue for an event and time, with a required expiry in the future. Venues only, not equipment.
2. The held period is blocked from other requests until the hold is confirmed or expires.
3. The hold expires on its own at its expiry: the venue is free again and the event stays in Planning.
4. The coordinator is told 24 hours before expiry (at once if the hold is shorter) and when it expires.
5. A hold becomes an approved booking only when the coordinator confirms the held venue and Venue staff then approve it, before the hold expires.
6. An expired hold is never shown or counted as a confirmed booking.
7. A hold is released when the event is rejected or cancelled, or the booking is updated.

**Delivery:** two PRs: the schema alone first (§1a rule, #123), then the API and the screens together (the story owner's choice, 2 Nov).

| PR | Work | Tests |
| --- | --- | --- |
| 1 | `held` and `expired` booking statuses (the type rebuilt, as US16b did); `hold_expires_at`, `held_by_user_id`, `hold_warned_at`, `expired_at`; the overlap guard covers holds, and so do the app's copies of its rule (the availability check, US2's search, the buffer-edit recompute). Migration `20261115_1200_us25_holds` | `backend/tests/venue/test_hold_schema.py` (TC-US25-01 to 06) |
| 2 | Place, confirm, decline; expiry on read and the warnings; the notices; holds in search, the calendar and a cancel; Venue staff's **Hold a venue**, the coordinator's Confirm and Decline with the time left, holds on the calendar; the seeded Venue Hold Demo | `backend/tests/venue/test_holds.py` (TC-US25-07 to 17, 24's reseed); `frontend/src/features/venue/holds.integration.test.tsx` (TC-US25-18 to 23); `e2e/tests/venue-hold.spec.ts` (TC-US25-24) |

## Decisions for this story

- **A hold is a venue booking with status `held`** (D105, `DECISION-PENDING`), so the existing overlap guard keeps another request out of the window (AC 2), even in a race. It blocks the window but is no booking anywhere else (AC 6): `BLOCKING_STATUSES` is the guard's set, and everything that counts an event's venues (venues arranged, readiness, the primary venue) keeps `LIVE_BOOKING_STATUSES`. A hold can't be the primary venue. While held, `requested_by_user_id` is the Venue staff member who placed it; confirming makes the coordinator the requester, so Venue staff can then approve it (D51).
- **Length** (D102, the story owner's choice, 1 Nov): any expiry from now up to 14 days ahead; no extension. To keep a venue longer, the coordinator confirms it, or Venue staff place a new hold once it lapses.
- **Expiry and the 24-hour warning** (D103, the story owner's choice, 1 Nov): no scheduler, as for waitlist offers (D2, §1a "Lapse on read"). A hold lapses on the next read or change of its venue's bookings; the warning goes out once, on the first read inside the last 24 hours (`hold_warned_at`), or at once for a hold placed with less than 24 hours left. It may arrive later than exactly 24 hours if nobody looks.
- **Released when** (D104, the story owner's choice, 1 Nov): the coordinator declines it (for example after choosing another venue), the event is cancelled (US9), or it's confirmed into a request. Rejection can't apply: holds exist only from Approved on.
- **A confirmed hold keeps its expiry** (AC 5): Venue staff must approve the request before it, or it lapses as `expired`.
- **No warning if nobody looks** (D103): a hold nobody reads in its last 24 hours just expires, and the coordinator hears only that.
- **Which events Venue staff see** (D106, `DECISION-PENDING`): they read no event requests (D55), so `GET /venue-holds/events` lists only each Approved or Planning event's name, reference, schedule and attendance.
- **The expiry must also come before the held time starts**: a hold on a slot that has begun keeps nothing for anyone.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US25-01 | 1 | Migrations applied | Inspect the schema | `venue_booking_status` gains `held` and `expired`; holds are blocking but not live; one migration head |
| TC-US25-02 | 2, 3 | A hold; an expired hold | Store an overlapping request at the same venue | Refused (`venue_bookings_no_overlap`); allowed |
| TC-US25-03 | 1, 3, 4 | | A hold without an expiry; an expiry without who placed it; a warning without a hold, or at the expiry; a hold requested by someone other than who placed it; expired without a time, a time while held, or before the expiry | Each refused (`venue_bookings_hold_consistent`, `venue_bookings_expired_consistent`) |
| TC-US25-04 | 6 | | A primary hold; a hold with a decision | Refused (`venue_bookings_hold_not_primary`, `venue_bookings_decided_consistent`) |
| TC-US25-05 | 5 | A hold | Confirm it into a request | It keeps its expiry and who placed it, read back from the database |
| TC-US25-06 | 2 | A hold; an expired hold at another venue | The availability check over each window | The hold is the conflict, by its reference; the expired one is no conflict. Fails without `BLOCKING_STATUSES` in the check |
| TC-US25-07 | 1, 4 | An Approved event and a venue | Venue staff place a hold | `201`, held, not primary, `coordinator_to_confirm`, the expiry and who placed it; the coordinator told (`placed`) |
| TC-US25-08 | 1 | | No expiry (alone, or with other missing fields); one in the past, over 14 days ahead, after the start, inside the venue's setup, or with no offset; too many attendees; a draft; a Confirmed event | `MISSING_REQUIRED_FIELD` naming every gap / `INVALID_HOLD` on `hold_expires_at`, nothing stored; `VENUE_CAPACITY_EXCEEDED`; `404`; `409 EVENT_NOT_BOOKABLE` |
| TC-US25-09 | 1 | Approved and Planning events with a coordinator, an unassigned Approved one, an Under Review one | Venue staff list the events to hold for | The assigned Approved and Planning ones, by name (D106) |
| TC-US25-10 | 2, 6 | A hold | Another event requests the same window; a coordinator searches it; the event's venues are read | `409 VENUE_UNAVAILABLE` naming the conflict; the venue not in the results; not arranged, no primary, nothing allocated |
| TC-US25-11 | 5 | A hold | Its coordinator confirms; another coordinator; confirm twice | Requested, the coordinator the requester, primary, the expiry and placer kept, Venue staff told; `404`; `409 HOLD_NOT_HELD` |
| TC-US25-12 | 5 | A confirmed hold | Venue staff approve before its expiry; at its expiry | Approved; `409 BOOKING_NOT_PENDING` (`expired`), the coordinator told |
| TC-US25-13 | 7 | A hold; a hold past its expiry that nothing has read | The coordinator declines it, then Venue staff hold the window again; a stale screen declines the lapsed one | Withdrawn, then the new hold placed; `409 BOOKING_NOT_LIVE` (`expired`) and the coordinator told it expired |
| TC-US25-14 | 3, 4 | A hold | The first read is at its expiry | Expired with `expired_at`; the window free; the event unchanged; the coordinator hears placed then expired, with no warning (D103) |
| TC-US25-15 | 4 | A hold; one placed with 6 hours left | Reads 25 and 23 hours before expiry, twice; a read | One warning, inside the last 24 hours; the short one warned at once |
| TC-US25-16 | 2, 6 | A hold | Read the calendar; read it after the expiry | Kind `hold`, label "Hold", with its expiry; then nothing |
| TC-US25-17 | 7 | A hold | The event is cancelled (US9) | The hold withdrawn |
| TC-US25-18 | 1 | Venue staff on Venues | Place a hold: the event, venue, purpose, times, layout and expiry date | "Held Hall A for Alumni Night until …"; the body has the times and the expiry at 17:00 +08:00 |
| TC-US25-19 | 1 | | Place a hold without an expiry | "Complete the fields marked below."; the expiry field marked |
| TC-US25-20 | 4, 5 | A hold on the coordinator's event | They open it, then Confirm hold | Held, until when and the time left; then the confirmation notice, Requested, and the approve-by time |
| TC-US25-21 | 7 | A hold | The coordinator presses Decline hold, then confirms | A confirm step saying the venue is free to anyone at once, nothing sent until confirmed; then "Hold on Hall A declined. The venue is free again."; Withdrawn |
| TC-US25-22 | 4 | | The countdown at 3 days, 20 hours, 45 minutes and past | "expires in 3 days", "expires in 20 h", "expires in 45 min", "expiring now" |
| TC-US25-23 | 2 | A hold in the calendar's week | Venue staff open it on the calendar | A "Hold" item; its details show Held and "Held until" |
| TC-US25-24 | 1, 2, 4, 5 | The seeded Venue Hold Demo (E2E, real backend) | Venue staff hold a venue 400+ days ahead; the coordinator sees it and confirms it; then withdraws it | Each step's message, "From a hold: Venue staff must approve it by"; then Withdrawn. Passes twice without a reseed; a reseed clears the event's rows |

## Results

| Date | Suite | Result |
| --- | --- | --- |
| 1 Nov | Backend (`pytest`), PR 1 | 1563 passed, including TC-US25-01 to 06; the migration upgrades, downgrades and upgrades again on a local database |
| 2 Nov | PR 2: backend (`pytest`), frontend (Vitest), E2E (Playwright, local Postgres and the real backend) | Backend 1618 passed (after the review fixes) (TC-US25-07 to 17, 24); frontend 466 (TC-US25-18 to 23); E2E 50 passed and 11 skipped, TC-US25-24 included, which also passes twice in a row without a reseed |
