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

**Delivery:** three PRs, as US9 did: the schema alone first (§1a rule), then the API, then the screens.

| PR | Work | Tests |
| --- | --- | --- |
| 1 | `held` and `expired` booking statuses (the type rebuilt, as US16b did); `hold_expires_at`, `held_by_user_id`, `hold_warned_at`, `expired_at`; the overlap guard covers holds. Migration `20261115_1200_us25_holds` | `backend/tests/venue/test_hold_schema.py` (TC-US25-01 to 05) |
| 2 | Place, confirm, decline; expiry on read; the notices; holds in search, the availability check, the calendar and a cancel | Not built yet |
| 3 | Venue staff's hold form and the coordinator's held venues with a countdown | Not built yet |

## Decisions for this story

- **A hold is a venue booking with status `held`** (D105, `DECISION-PENDING`), so the existing overlap guard keeps another request out of the window (AC 2), even in a race. It blocks the window but is no booking anywhere else (AC 6): `BLOCKING_STATUSES` is the guard's set, and everything that counts an event's venues (venues arranged, readiness, the primary venue) keeps `LIVE_BOOKING_STATUSES`. A hold can't be the primary venue. While held, `requested_by_user_id` is the Venue staff member who placed it; confirming makes the coordinator the requester, so Venue staff can then approve it (D51).
- **Length** (D102, the story owner's choice, 1 Nov): any expiry from now up to 14 days ahead; no extension. To keep a venue longer, the coordinator confirms it, or Venue staff place a new hold once it lapses.
- **Expiry and the 24-hour warning** (D103, the story owner's choice, 1 Nov): no scheduler, as for waitlist offers (D2, §1a "Lapse on read"). A hold lapses on the next read or change of its venue's bookings; the warning goes out once, on the first read inside the last 24 hours (`hold_warned_at`), or at once for a hold placed with less than 24 hours left. It may arrive later than exactly 24 hours if nobody looks.
- **Released when** (D104, the story owner's choice, 1 Nov): the coordinator declines it (for example after choosing another venue), the event is cancelled (US9), or it's confirmed into a request. Rejection can't apply: holds exist only from Approved on.
- **A confirmed hold keeps its expiry** (AC 5): Venue staff must approve the request before it, or it lapses as `expired`.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US25-01 | 1 | Migrations applied | Inspect the schema | `venue_booking_status` gains `held` and `expired`; holds are blocking but not live; one migration head |
| TC-US25-02 | 2, 3 | A hold; an expired hold | Store an overlapping request at the same venue | Refused (`venue_bookings_no_overlap`); allowed |
| TC-US25-03 | 1, 3, 4 | | A hold without an expiry; an expiry without who placed it; a warning without a hold; expired without a time, or a time while held | Each refused (`venue_bookings_hold_consistent`, `venue_bookings_expired_consistent`) |
| TC-US25-04 | 6 | | A primary hold; a hold with a decision | Refused (`venue_bookings_hold_not_primary`, `venue_bookings_decided_consistent`) |
| TC-US25-05 | 5 | A hold | Confirm it into a request | It keeps its expiry and who placed it |

## Results

| Date | Suite | Result |
| --- | --- | --- |
| 1 Nov | Backend (`pytest`), PR 1 | 1559 passed, including TC-US25-01 to 05; the migration upgrades, downgrades and upgrades again on a local database |
