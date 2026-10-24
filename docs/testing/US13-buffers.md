# US13 — Venue setup and turnaround buffers (SCRUM-16): test cases

**Story:** As Venue Staff, I want each venue's setup and turnaround time to be included automatically when availability is checked, so that consecutive events don't overlap and the venue can be prepared and reset between uses.

**Source of truth:** the acceptance criteria in Jira SCRUM-16, as updated on 13 Oct 2026 (CR-01 and clarification sessions 2 and 3). If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Use the venue's own setup and turnaround (US20) whenever availability is checked or a booking is evaluated.
2. The occupied window is [start − setup] to [end + turnaround]: 10:00–12:00 with 30/45 occupies 09:30–12:45.
3. Any overlap of the occupied window with an approved booking, an unexpired hold or an unavailability period, even by one second, is a conflict and prevents approval. Windows that only touch don't conflict. No override.
4. Venue Staff see the exact overlap period and the conflicting booking's reference.
5. Approval is blocked if the occupied window runs outside the venue's operating hours.
6. A buffer change is refused while the venue has approved future bookings (US20's `VENUE_BUFFERS_LOCKED`).
7. Buffers apply to venue bookings only; equipment uses the event's own times.

**Delivery:** one PR per subtask, in this order. PR 1 is the only one with a migration.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-114 | Each booking stores its occupied window; `venue_bookings_no_overlap` covers it; bookings get a reference; the seed, factories and US2 search's booking check read the stored window | `backend/tests/venue/test_buffer_schema.py`, plus the whole E2E suite on a reseeded database |
| 2 | | The reusable rule for US4 (`evaluate_window`, `evaluate_booking`); opening hours (`VENUE_OUTSIDE_HOURS`); the overlap and reference in `VENUE_UNAVAILABLE`; the staff evaluation endpoint; buffer-edit recompute (`VENUE_BUFFERS_CONFLICT`); US2 search with the searched venue's own buffers and hours | `backend/tests/venue/test_buffer_api.py` |
| 3 | | The occupied window in the booking form, panel and pending list; conflicts on Venue staff's pending list | lint, build, unit and integration tests, `e2e/tests/venue-buffers.spec.ts` |

## Test cases

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US13-01 | 2 | `venue_bookings` has `occupied_starts_at` and `occupied_ends_at` (not null), the CHECK `venue_bookings_occupied_covers_window` and a unique `reference`; RLS is still on; buffers stay venue-only (TC-US20-07); the seed stores each booking's occupied window | Auto pytest | 1 |
| TC-US13-02 | 2 | `occupied_window()`: 10:00–12:00 with 30/45 gives 09:30–12:45; 0/0 gives the plain window; the factory fills it from the venue | Auto pytest | 1 |
| TC-US13-03 | 3 | The database refuses a live booking whose setup overlaps another's turnaround by one second, and a plain window inside another's setup; touching (setup starts as turnaround ends) is allowed; withdrawn and rejected bookings occupy nothing; another venue is unaffected | Auto pytest | 1 |
| TC-US13-04 | 3 | Migration: existing bookings get windows from their venue's buffers and references in the order they were made; it refuses, naming both bookings, when the backfilled windows of live bookings would overlap; downgrade restores the plain-window guard | Auto pytest | 1 |
| TC-US13-05 | 4 | References are `VB-<year>-<6 digits>`, in order, unique (`venue_bookings_reference_key`); seeded bookings have one | Auto pytest | 1 |
| TC-US13-06 | 1, 2 | Create stores the occupied window from the venue's current buffers and returns it with the reference | Auto pytest | 2 |
| TC-US13-07 | 3, 4 | A request whose occupied window overlaps a live booking's, even by one second, is `409 VENUE_UNAVAILABLE` with the overlap period; touching is accepted | Auto pytest | 2 |
| TC-US13-08 | 3 | Setup or turnaround inside a venue block is refused with the overlap; touching a block is accepted | Auto pytest | 2 |
| TC-US13-09 | 5 | An occupied window starting before opening or ending after closing is `422 VENUE_OUTSIDE_HOURS`; exactly opening to closing is accepted; a window crossing midnight is refused | Auto pytest | 2 |
| TC-US13-10 | 3, 4, 5 | `evaluate_booking` lists every conflict (bookings, blocks) with overlap and reference, plus any hours breach, excluding the booking itself; it's empty when clear (US4's contract) | Auto pytest | 2 |
| TC-US13-11 | 4 | `GET /api/v1/venue-bookings/{id}/evaluation`: Venue Staff only (`403` otherwise), `404` for an unknown id; it shows a block added after the request | Auto pytest | 2 |
| TC-US13-12 | 6 | A buffer edit with only Requested future bookings recomputes their windows; an edit that would make two overlap, or run one outside hours, is `409 VENUE_BUFFERS_CONFLICT`, naming them, with nothing saved; past bookings are untouched; approved future bookings are still `VENUE_BUFFERS_LOCKED` | Auto pytest | 2 |
| TC-US13-13 | 1, 3, 5 | US2 search hides a venue whose occupied window clashes or runs outside its hours; a touching window is shown | Auto pytest | 2 |
| TC-US13-14 | 3 | Race: two requests whose plain windows don't overlap but whose occupied windows do; one is `201`, the other `409` | Auto pytest | 2 |
| TC-US13-15 | 7 | Buffers apply to venue bookings only; equipment has no reservations yet, so this is recorded as not applicable, and a test asserts no other table has buffer columns | Auto pytest | 2 |
| TC-US13-16 | 2 | In the browser, the form previews the occupied window for the chosen venue | Auto Vitest | 3 |
| TC-US13-17 | 3, 5 | In the browser, an overlap shows its period; outside hours shows on the time fields | Auto Vitest | 3 |
| TC-US13-18 | 4 | In the browser, Venue staff's pending list shows each request's occupied window and any conflict with its overlap and reference | Auto Vitest | 3 |
| TC-US13-19 | 2, 3 | In the browser, a request whose setup would overlap a seeded booking's turnaround is refused with the overlap; the touching time is accepted | Auto Playwright | 3 |

## Decisions (story owner's choices, 24 Oct; `DECISION-PENDING` for the team)

- **D31: buffer edits while Requested future bookings exist.** Recompute their occupied windows in the same transaction, and refuse the edit with `409 VENUE_BUFFERS_CONFLICT` if any would then clash or run outside hours (PR 2).
- **D32: when AC 5 applies.** At request time too, and again at approval through `evaluate_booking`, since hours can change (PR 2).
- **D33: booking reference.** `VB-<year>-<6 digits>` on every booking, from `next_venue_booking_reference()` (the column default), the year it was made in Singapore (PR 1).
- **D34: overlaps the buffers create in existing data.** The migration refuses and names each pair, for a person to withdraw or reject one of them. CR-01 says such bookings are identified, not removed, and an exclusion constraint can't be added `NOT VALID` (PR 1).
- **D35: what a coordinator sees in a 409.** The overlap period and the kind of clash, but not the other booking's reference, which AC 4 gives to Venue Staff (PR 2).
- **D36: AC 4 before US4.** A Venue Staff evaluation endpoint, and conflicts on the pending list (PR 2, 3).
- **D37: US20's deferred flag-and-notify on hours or capacity edits.** Not in US13. AC 5 at approval covers hours; capacity is US22's create check.
- **Confirmed:** blocks have no buffers of their own (the booking's occupied window is checked against the block's plain window); US2 search uses each venue's own buffers.

## PR 1 notes

- **Buffers are on for every booking from PR 1:** the guard covers the stored occupied window. Tests that prove US22's and US2's plain `[)` rule (back-to-back, one-second overlap, withdrawn and rejected, blocks, search next to a booking) use venues with 0/0 buffers, so they keep proving that rule; TC-US13-03 covers the buffered one.
- **US2 search's booking check reads the stored occupied window,** which is the range the exclusion constraint's GiST index holds (TC-US2-08 needs the index). So an existing booking's buffers already keep a venue out of search; the searched venue's own buffers and hours come in PR 2.
- **Not until PR 2:** opening hours, the overlap period and reference in errors, the block check on the occupied window, and recomputing windows when buffers change. Until PR 2, a buffer edit leaves Requested bookings' stored windows as they were made.
