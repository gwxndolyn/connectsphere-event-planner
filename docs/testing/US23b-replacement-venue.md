# US23b — Find a replacement venue for an affected booking (SCRUM-91): test cases

**Story:** As an Event Coordinator, I want to find and request a replacement venue for a booking that's been affected by venue unavailability, so that my event can still go ahead.

**Source of truth:** the acceptance criteria in Jira SCRUM-91. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The coordinator sees a "Needs rearrangement" notice on the affected event with the original venue, period, reason and booking details; the event is back in Planning while it is unresolved.
2. A venue search starts from the notice with the event's date, time and attendance filled in.
3. A replacement request goes through Venue staff's full approval like any new booking.
4. Once the replacement is approved, the original booking is marked "Replaced" and keeps its details in the history.
5. If the original venue is free again for the whole occupied window (setup and turnaround included) before a replacement is confirmed, the coordinator can ask to restore the original booking, which Venue staff must confirm.
6. The event is never cancelled automatically; the coordinator may cancel it through the normal flow (US9).
7. Attendees are told only once a replacement is confirmed and what they see changes.

**Delivery:** two PRs: the schema alone first (§1a rule), then the API and the screens together (the story owner's choice, 3 Nov). Built on US23a (SCRUM-90).

| PR | Work | Tests |
| --- | --- | --- |
| 1 | Booking status `replaced` with `replaced_at`; `replaces_booking_id` on a replacement request, at most one live replacement each; the coordinator's restore request on a marked booking and Venue staff's last decline of one; a venue block ended early (`ended_early_at`, `ended_early_by_user_id`, `scheduled_ends_at`). Migration `20261117_1200_us23b_replacement` | `backend/tests/venue/test_replacement_schema.py` (TC-US23B-01 to 04) |
| 2 | Moving an affected event back to Planning; replacement requests from the notice; Replaced on approval; ending a block early, restore requests and Venue staff's decision; attendee notices; the seeded Replacement Venue Demo | `backend/tests/venue/test_replacement.py` (TC-US23B-05 to 12, 20's reseed); `frontend/src/features/venue/replacement.integration.test.tsx` (TC-US23B-13 to 19); `e2e/tests/venue-replacement.spec.ts` (TC-US23B-20) |

## Decisions for this story

- **Replaced is a status** (D117, the story owner's choice, 3 Nov, `DECISION-PENDING`). A replacement is a new request naming the booking it replaces; once it is approved, the original becomes `replaced` and, like a withdrawn booking, stops holding its window, keeping its reference, venue, times and the block that marked it. One live replacement at a time.
- **A venue comes back when Venue staff end the block early** (D118, the story owner's choice, 3 Nov, `DECISION-PENDING`). The block's `ends_at` moves to then, or to its start if it hadn't begun (an empty block, overlapping nothing), and `scheduled_ends_at` keeps the original end. The coordinator then asks to restore; Venue staff confirm or decline.
- **The event goes back to Planning when the venue is marked** (the story owner's choice, 3 Nov): PR 2 changes US23a's `POST /venues/{id}/blocks` so an affected Confirmed or Preparation event moves to Planning, clearing its confirmation as an approved change request does (US29b).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US23B-01 | 4 | Migrations applied; an approved booking marked by a block | Make it Replaced; store Replaced without a time, or a time without Replaced; book the same window | One migration head; it keeps its reference, window, decision and block; both halves refused (`venue_bookings_replaced_consistent`), and Replaced without a marker too; the window is free again |
| TC-US23B-02 | 3 | A marked booking | Request a replacement naming it; name the booking itself; a second while one is requested, approved or held; a second after one was rejected or withdrawn | Stored; refused (`venue_bookings_replaces_another`); refused (`venue_bookings_one_live_replacement`); stored. A primary original's replacement made primary while the original is live is refused (`venue_bookings_one_primary_per_event`); made primary after the original is Replaced, the event has exactly that one primary |
| TC-US23B-03 | 5 | A marked booking; an unmarked one | Ask to restore with who and when; only one of them; on the unmarked booking | Stored; refused (`venue_bookings_restore_consistent`) for both. A decline with who, when and a reason is stored; one missing who or when, or a reason with no decline, is refused (`venue_bookings_restore_decline_consistent`). A restore request on a replaced or withdrawn booking is refused (`venue_bookings_restore_consistent`); on a marked hold it's stored |
| TC-US23B-04 | 5 | A block | End it early; end one before it began; store an empty block not ended early; leave out who, when or the scheduled end, or a scheduled end not after the new end | The new end and the scheduled one kept; an empty block overlapping nothing; refused (`venue_blocks_window_valid`); refused (`venue_blocks_ended_early_consistent`); the status type lists `replaced` last |
| TC-US23B-05 | 1 | A Confirmed or Preparation event, an Approved or Planning one, an unaffected Confirmed one | Venue staff mark its venue unavailable | The first goes to Planning, no longer confirmed, with Status and Confirmation entries in History by the Venue staff member; the others keep their status |
| TC-US23B-06 | 3 | A marked booking | The coordinator requests a replacement naming it; names an unmarked one, another event's, or a hold naming one; a second while the first is live; one after withdrawing the first | `201` Requested, not primary, Venue staff told, in the pending list, the original showing its replacement; `409 BOOKING_NOT_REPLACEABLE`; `422` on `replaces_booking_id`; `409 REPLACEMENT_EXISTS` with the first's reference; `201` |
| TC-US23B-07 | 4 | A requested replacement | Venue staff approve it; or reject it | Approved and primary; the original Replaced with its time, venue, window and decision kept, venues arranged, its window free once the period ends; rejected, the original still needs rearrangement with no replacement |
| TC-US23B-08 | 7 | Registered, wait-listed and withdrawn attendees | Mark the venue; request a replacement; approve it; a replacement for a non-primary venue; a failing notice | Nobody told on marking or requesting; on approval the registered and wait-listed only, with the new venue; nobody for a non-primary venue; the replacement still approved |
| TC-US23B-09 | 5 | A period under way, one not begun, one over, two overlapping periods | Venue staff end it early; at another venue; as a coordinator | Its end now, the scheduled end kept, its marked booking listed and its coordinator told; empty and gone from the calendar; `409 BLOCK_ENDED`; `404`; `403`; the booking moved to the other period's marker, and nobody told |
| TC-US23B-10 | 5 | A marked booking | The coordinator asks to restore while the period runs; after it ends early but with another period over its setup; once free; again; with a live replacement; as another coordinator | `409 VENUE_UNAVAILABLE` twice; `200` with `venue_staff_to_restore`, Venue staff told and the request listed; `409 RESTORE_ALREADY_REQUESTED`; `409 REPLACEMENT_EXISTS`; `404` |
| TC-US23B-11 | 5 | A restore request | Venue staff confirm; confirm after a new period; decline with a reason; confirm with no request | Restored: approved, primary, no marker, venues arranged, the coordinator told; `409 VENUE_UNAVAILABLE` with the request kept; still needing rearrangement, the reason sent and kept on the booking until the coordinator asks again; `409 RESTORE_NOT_REQUESTED`. Withdrawing, rejecting, cancelling the event or a hold's lapse clears a waiting request |
| TC-US23B-12 | 6 | A Confirmed event whose venue is marked and whose replacement is rejected | Nothing more | It stays in Planning, the original stays approved; the coordinator can still cancel it through US9 |
| TC-US23B-13 | 1, 2, 3 | A marked booking (screens) | The coordinator opens the event and chooses **Find a replacement**, picks a venue the search found and sends | The search sent with the booking's date, times and attendance; only its results offered; the request names the original; the notice and the row say a replacement is requested |
| TC-US23B-14 | 2 | No venue free | The search runs; the coordinator changes the times and searches again | "No venue is free …"; the new search sent with the new times and its result shown |
| TC-US23B-15 | 4 | A replaced booking and its approved replacement | The coordinator opens the event | Replaced by the new venue with its reference, no actions; the replacement reads "Replaces …" |
| TC-US23B-16 | 5 | A marked booking whose period ended early | The coordinator chooses **Ask to restore** | The request sent; the notice and row say Venue staff confirm it. After a decline, the row shows when and why, and asking again replaces it |
| TC-US23B-17 | 5 | Two restore requests | Venue staff confirm one and decline the other with a reason | **Requests to restore a booking (2)**; each call sent, the reason in the body, a notice for each |
| TC-US23B-18 | 5 | A period on the calendar | Venue staff choose **End early**, then **End period** | Asked first; the call sent; "Ended early. 1 booking can now be restored once its coordinator asks." |
| TC-US23B-19 | 2 | Instants | Read them back as Singapore date and time | 10:00 on the day, past midnight on the next day, and a round trip through `singaporeInstant` |
| TC-US23B-20 | 1 to 4 | The seeded Replacement Venue Demo (E2E) | The coordinator requests a venue and Venue staff approve it, then mark it unavailable; the coordinator finds a replacement from the notice; Venue staff approve it | The notice with the reason and note; the search for the booking's time and attendance; the original Replaced by the new venue, which is Approved and Primary; withdrawn after. A reseed deletes the event's bookings and the periods that marked only them |
