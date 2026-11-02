# US23a — Mark a venue unavailable and flag affected bookings (SCRUM-90): test cases

**Story:** As a Venue Staff member, I want to mark a venue temporarily unavailable so that it isn't booked during maintenance or other problems, and so that coordinators of affected events find out.

**Source of truth:** the acceptance criteria in Jira SCRUM-90. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Venue staff record an unavailability period for a venue with a start, an end and a reason (maintenance, equipment failure, renovation, safety, other).
2. A period whose end is before its start can't be saved.
3. Every existing booking or hold overlapping the period is marked "Needs rearrangement"; the event isn't cancelled and the booking isn't deleted.
4. The assigned coordinator and the organiser of each affected event are told the venue, period, reason and next action. Attendees aren't told.
5. New booking requests and approvals for that venue are blocked during the period.
6. The period shows on the venue's availability calendar (US21).

**Delivery:** two PRs: the schema alone first (§1a rule), then the API and the screens together (the story owner's choice, 2 Nov). Finding a replacement, restoring the original booking and moving the event back to Planning are US23b's (SCRUM-91).

| PR | Work | Tests |
| --- | --- | --- |
| 1 | An unavailability period is a `venue_blocks` row (US2's table), which gains `reason` and `created_by_user_id`; a booking or hold it overlaps names it in `rearrangement_block_id`, with `rearrangement_flagged_at`, and keeps its status. The seeded block's reason is maintenance. Migration `20261116_1200_us23a_blocks` | `backend/tests/venue/test_unavailability_schema.py` (TC-US23A-01 to 03) |
| 2 | Record a block, mark the bookings and holds it overlaps, notify; Needs rearrangement on the event's venues; the reason on the calendar | To be added |

## Decisions for this story

- **"Needs rearrangement" names the block; the status stays** (D113, the story owner's choice, 2 Nov, `DECISION-PENDING`). The booking keeps its window under the overlap guard, so US23b can restore it or mark it replaced. Jira's subtask names a `needs_rearrangement` status instead; that would lose the original status and need the status type rebuilt.
- **Already in place from US2, US13 and US21:** a block refuses new requests and approvals that overlap it (AC 5, `VENUE_UNAVAILABLE`), hides the venue from search, and is drawn on the calendar as "Unavailable" (AC 6). PR 2 adds the reason to those.
- **Blocks made before US23a** (the seeded one, and any on Supabase) are backfilled `other`; the seed then sets its block to `maintenance`.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US23A-01 | 1 | Migrations applied | Store a block with each reason, an unknown reason, no reason; read the seed | Each of the five is stored; an unknown one is refused (`venue_blocks_reason_known`) and a missing one too (not null); the seeded block is for maintenance; one migration head |
| TC-US23A-02 | 2 | A venue | Store a block ending at, or before, its start | Refused (`venue_blocks_window_valid`) |
| TC-US23A-03 | 3 | A block over a requested booking, an approved booking and a hold | Mark each with the block; mark one with only the block or only the time | Each keeps its status and still holds its window under the overlap guard; a half marker is refused (`venue_bookings_rearrangement_consistent`); a partial index finds a block's bookings |
