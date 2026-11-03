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
| 1 | Booking status `replaced` with `replaced_at`; `replaces_booking_id` on a replacement request, at most one live replacement each; the coordinator's restore request on a marked booking; a venue block ended early (`ended_early_at`, `ended_early_by_user_id`, `scheduled_ends_at`). Migration `20261117_1200_us23b_replacement` | `backend/tests/venue/test_replacement_schema.py` (TC-US23B-01 to 04) |
| 2 | Moving an affected event back to Planning; replacement requests from the notice; Replaced on approval; ending a block early, restore requests and Venue staff's decision; attendee notices | To come |

## Decisions for this story

- **Replaced is a status** (D116, the story owner's choice, 3 Nov, `DECISION-PENDING`). A replacement is a new request naming the booking it replaces; once it is approved, the original becomes `replaced` and, like a withdrawn booking, stops holding its window, keeping its reference, venue, times and the block that marked it. One live replacement at a time.
- **A venue comes back when Venue staff end the block early** (D117, the story owner's choice, 3 Nov, `DECISION-PENDING`). The block's `ends_at` moves to then, or to its start if it hadn't begun (an empty block, overlapping nothing), and `scheduled_ends_at` keeps the original end. The coordinator then asks to restore; Venue staff confirm or decline.
- **The event goes back to Planning when the venue is marked** (the story owner's choice, 3 Nov): PR 2 changes US23a's `POST /venues/{id}/blocks` so an affected Confirmed or Preparation event moves to Planning, clearing its confirmation as an approved change request does (US29b).

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US23B-01 | 4 | Migrations applied; an approved booking marked by a block | Make it Replaced; store Replaced without a time, or a time without Replaced; book the same window | One migration head; it keeps its reference, window, decision and block; both halves refused (`venue_bookings_replaced_consistent`); the window is free again |
| TC-US23B-02 | 3 | A marked booking | Request a replacement naming it; name the booking itself; a second while one is requested or approved; a second after one was rejected or withdrawn | Stored; refused (`venue_bookings_replaces_another`); refused (`venue_bookings_one_live_replacement`); stored |
| TC-US23B-03 | 5 | A marked booking; an unmarked one | Ask to restore with who and when; only one of them; on the unmarked booking | Stored; refused (`venue_bookings_restore_consistent`) for both |
| TC-US23B-04 | 5 | A block | End it early; end one before it began; store an empty block not ended early; leave out who, when or the scheduled end, or a scheduled end not after the new end | The new end and the scheduled one kept; an empty block overlapping nothing; refused (`venue_blocks_window_valid`); refused (`venue_blocks_ended_early_consistent`); the status type lists `replaced` last |
