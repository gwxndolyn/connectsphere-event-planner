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
| 2 | `POST /api/v1/venues/{id}/blocks`: record a period, mark the bookings and holds it overlaps, notify each affected event's coordinator and organiser; Needs rearrangement on the event's venues for the coordinator and the Organiser; a marked hold can't be confirmed; the reason on the calendar; Venue staff's **Mark a venue unavailable**; the seeded Venue Unavailability Demo | `backend/tests/venue/test_unavailability.py` (TC-US23A-04 to 12, 20's reseed); `frontend/src/features/venue/unavailability.integration.test.tsx` (TC-US23A-13 to 16, 18, 19) and `EventVenuesOverview.test.tsx` (TC-US23A-17); `e2e/tests/venue-unavailability.spec.ts` (TC-US23A-20) |

## Decisions for this story

- **"Needs rearrangement" names the block; the status stays** (D113, the story owner's choice, 2 Nov, `DECISION-PENDING`). The booking keeps its window under the overlap guard, so US23b can restore it or mark it replaced. Jira's subtask names a `needs_rearrangement` status instead; that would lose the original status and need the status type rebuilt.
- **Already in place from US2, US13 and US21:** a block refuses new requests and approvals that overlap it (AC 5, `VENUE_UNAVAILABLE`), hides the venue from search, and is drawn on the calendar as "Unavailable" (AC 6). PR 2 adds the reason to those.
- **Who is told, and the next action** (D114, `DECISION-PENDING`): one notice per affected event for its coordinator and one for its organiser, naming every affected booking of that event; the coordinator is asked to find a replacement or withdraw it, the Organiser told the coordinator will arrange one.
- **Already marked, or under way** (D115, `DECISION-PENDING`): a booking keeps the first period that marked it and isn't announced again; a period may start in the past but not have ended; periods can't be edited or deleted yet.
- **By the occupied window:** a booking whose setup or turnaround falls in the period is affected, as the availability check compares them; touching isn't overlapping.
- **Blocks made before US23a** (the seeded one, and any on Supabase) are backfilled `other`; the seed then sets its block to `maintenance`.

## Test cases

| ID | AC | Given | When | Then |
| --- | --- | --- | --- | --- |
| TC-US23A-01 | 1 | Migrations applied | Store a block with each reason, an unknown reason, no reason; read the seed | Each of the five is stored; an unknown one is refused (`venue_blocks_reason_known`) and a missing one too (not null); the seeded block is for maintenance; one migration head |
| TC-US23A-02 | 2 | A venue | Store a block ending at, or before, its start | Refused (`venue_blocks_window_valid`) |
| TC-US23A-03 | 3 | A block over a requested booking, an approved booking and a hold | Mark each with the block; mark one with only the block or only the time | Each keeps its status and still holds its window under the overlap guard; a half marker is refused (`venue_bookings_rearrangement_consistent`); a partial index finds a block's bookings |
| TC-US23A-04 | 1 | Venue staff; a coordinator, organiser or attendee; no such venue | Record a period with each reason; try as another role; for an unknown venue | `201` with the venue, period, reason, trimmed note and who recorded it; `403`; `404 NOT_FOUND` |
| TC-US23A-05 | 1 | Venue staff | Send nothing but a blank reason; an unknown reason; a note over 500 characters; a time with no offset | `MISSING_REQUIRED_FIELD` naming all three; `INVALID_BLOCK` naming each field |
| TC-US23A-06 | 2 | Venue staff | End before the start, or at it; a period already over; one under way | `INVALID_BLOCK` on `ends_at` and nothing saved; refused; accepted |
| TC-US23A-07 | 3 | A requested booking, an approved one and a hold in the period; bookings touching or overlapping only by setup or turnaround; one elsewhere, a withdrawn one, a rejected one | Record the period | The three are marked and keep their status; the event stays in Planning; setup or turnaround overlap counts, touching doesn't; the others are untouched |
| TC-US23A-08 | 3, 4 | An approved primary booking, marked; closed bookings with a marker | The coordinator and the Organiser read the event's venues | `unavailability.kind: "venue_unavailable"` with the period, reason and note; next action the coordinator's; venues not arranged; on the readiness list the booking is outstanding ("needs rearrangement") and Confirm event is refused `EVENT_NOT_READY`; a withdrawn, rejected or expired booking keeping a marker isn't read as needing rearrangement |
| TC-US23A-09 | 3 | A booking already marked; a hold past its expiry | Record another overlapping period; record a period over the hold | The booking keeps the first period, nobody is told again; the hold expires instead of being marked |
| TC-US23A-10 | 4 | Two affected bookings of one event; a second affected event with no organiser; an unaffected event; the mail server down | Record the period | One notice each for the coordinator and organiser with the venue, period, reason, both references and the next action; the second event's coordinator only; nobody else; the period still saved |
| TC-US23A-11 | 5 | A period | Request the venue in it; approve a marked request; confirm a marked hold; withdraw a marked booking | `409 VENUE_UNAVAILABLE` for the first three, nothing changed; withdrawn |
| TC-US23A-12 | 6 | A period with a reason; a block from before US23a | Read the calendar | The block shows, labelled Unavailable, with its reason and note |
| TC-US23A-13 | 1, 3, 4 | Venue staff on Venues; an approved booking in the period | Fill **Mark a venue unavailable** and send | The body in Singapore time; the end date filled from the start; the status names the period, reason and the booking needing rearrangement, and says who was told |
| TC-US23A-14 | 2 | The form | An end before the start | Refused on the end date, nothing sent |
| TC-US23A-15 | 1 | The form | No reason | The API's refusal marks the Reason field |
| TC-US23A-16 | 3, 4 | A marked approved booking and a marked hold | The coordinator opens the event | **Needs rearrangement** with the period, reason and note; Withdraw offered; the hold's Confirm hidden, Decline offered |
| TC-US23A-17 | 4 | A marked booking | The Organiser opens the event's venues | Needs rearrangement, the period and reason, and that the coordinator will arrange a replacement |
| TC-US23A-18 | 6 | A block with a reason | Open it on the calendar | Its details show the reason |
| TC-US23A-19 | 1, 2 | Form values | Build the body; compare the end with the start | Singapore offsets, a blank note left out; an end at the start is caught |
| TC-US23A-20 | 1, 3, 4, 5 | The seeded Venue Unavailability Demo (E2E) | The coordinator requests a venue, Venue staff mark it unavailable over the request, the coordinator opens the event and withdraws it | Listed as needing rearrangement; the coordinator sees it with the reason and note, still Requested; withdrawn. A reseed deletes the event's bookings and the periods that marked only them |
