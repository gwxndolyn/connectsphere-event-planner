# US2 — Search for suitable venues (SCRUM-7): test cases

**Story:** As an Event Coordinator, I want to search ConnectSphere's venues by date, time and expected attendance so that I do not waste time raising booking requests that Venue Staff will reject.

**Source of truth:** the acceptance criteria in Jira SCRUM-7.

**Delivery:** one PR (#65), rebased on US22 PR 1 (#64), whose `venue_bookings` it reads. It adds the `venue_blocks` table, `GET /api/v1/venues/available`, the search form on the Venues page, and the seeded slot that shows AC 5. The same PR also adds the frontend's Vitest unit and integration suites and more E2E journeys across the existing screens.

**Tests:**

- Backend: `backend/tests/venue/test_venue_search.py` (TC-US2-01 to 12)
- Frontend: `frontend/src/features/venue/api.test.ts` (unit) and `venueSearch.integration.test.tsx` (integration, the real `App` against the MSW fake backend). The fake doesn't apply the search rules: it returns the venues a test queues (`nextSearchResult`), so integration tests check what the screen sends and shows, and AC 4 to 6 are proven only by the backend and E2E tests
- E2E: `e2e/tests/venue-search.spec.ts` (TC-US2-13 to 16)

## Acceptance criteria

1. Can search venues by date, start and end time, and expected attendance
2. Can further filter by location, accessibility requirements, and required facilities
3. Sees, for each result, the venue's capacity, facilities and accessibility information
4. Sees only venues whose capacity is at least the expected attendance
5. Does not see venues that are already booked, tentatively held, or blocked for the requested date and time
6. Does not see venues where the requested time falls outside the venue's operating hours
7. Is shown a clear "no matching venues" message, along with the criteria applied, when nothing matches
8. Receives search results within 3 seconds

## Test cases

| ID | AC | Check | Type |
| --- | --- | --- | --- |
| TC-US2-01 | 1 | Date, start, end and attendance return the suitable venues with the criteria echoed. Each of the four is required, and all missing ones are listed at once (`422 MISSING_REQUIRED_FIELD`) | Auto pytest |
| TC-US2-02 | 2 | Location is a case-insensitive, trimmed substring of the venue's location, with `%` and `_` taken literally; a whitespace-only location is no filter. A venue must have every required facility and accessibility feature. Filters combine with capacity. The criteria echo the tags in D18's order | Auto pytest |
| TC-US2-03 | 3 | Each result carries capacity, facilities and accessibility features, plus name, location, hours and layouts | Auto pytest |
| TC-US2-04 | 4 | Capacity equal to the attendance counts; one seat short doesn't. Results are smallest suitable venue first, then by name | Auto pytest |
| TC-US2-05 | 5 | An overlapping `requested` ("tentatively held") or `approved` ("booked") US22 booking hides the venue, as does an overlapping block; `rejected` and `withdrawn` bookings don't. Overlap is half-open for both, so back-to-back doesn't clash and a one-minute overlap does. A block spanning several days hides the venue on every day inside it. Other days and other venues don't count. Inactive venues never appear (US20 AC 3) | Auto pytest |
| TC-US2-06 | 6 | The whole requested time must sit inside operating hours: exactly the hours pass, a minute either side fails | Auto pytest |
| TC-US2-07 | 7 | No match is `200` with an empty list and the criteria applied, filters included | Auto pytest |
| TC-US2-08 | 8 | 500 venues and 5,000 bookings return in well under 3 seconds; on 50,000 bookings and 20,000 blocks the plan reaches both tables through an index, never a sequential scan | Auto pytest |
| TC-US2-09 | — | A past date, a zero-length or reversed time, attendance below 1 or not a whole number (`1.5`, `1e3`, text), and unknown tags are `422 INVALID_VENUE_SEARCH` naming the field, with a message. Today is allowed; an empty attendance is missing | Auto pytest |
| TC-US2-10 | — | Coordinators and operations managers may search (D25); organisers and attendees `403`; no identity `401`; inactive `403`. `/available` isn't read as a venue id | Auto pytest |
| TC-US2-11 | 5 | `venue_blocks` has the agreed columns, `venue_blocks_window_valid`, the `(venue_id, starts_at, ends_at)` index, a foreign key to `venues` and RLS. The database rejects zero-length and reversed blocks. Blocks may overlap each other and bookings. No buffer columns (US20 AC 7). `venue_bookings`' own schema and overlap guard are US22's (TC-US22-01, 02) | Auto pytest |
| TC-US2-12 | 5 | The seed gives three venues a requested booking, an approved booking and a block on one slot five days ahead, idempotently; each booking is for an approved event and requested by the seeded coordinator; searching the slot returns only the two free active venues | Auto pytest |
| TC-US2-13 | 1, 3, 4, 5, 8 | In the browser, as Coordinator, the seeded slot lists the library room and Lawn C, not the requested, approved and blocked venues; results show capacity, facilities and accessibility; they come back on another day; the search returns in under 3 seconds | Auto Playwright |
| TC-US2-14 | 2, 6 | A slot past the library's closing time leaves it out; location and a facility narrow to the library; an accessibility feature it lacks gives no match | Auto Playwright |
| TC-US2-15 | 7 | An attendance nothing fits shows "No matching venues." and the criteria applied; a reversed time marks End time with the API's message | Auto Playwright |
| TC-US2-16 | — | Organisers see the catalogue but no search form (D25) | Auto Playwright |

## Decisions

- **Bookings are US22's `venue_bookings` (#64).** AC 5's "tentatively held" is US22's `requested` and "booked" is `approved`, so search leaves out anything in `LIVE_BOOKING_STATUSES`, the same pair US22's `venue_bookings_no_overlap` keeps apart. `rejected` and `withdrawn` don't count.
- **Blocks get their own table, `venue_blocks` (deviation 30).** AC 5's "blocked" venue has no event or requester, which `venue_bookings` requires, so a block is `venue_id`, `starts_at`, `ends_at`, `note`. Search checks both tables. Blocks may overlap each other and bookings. US23a (SCRUM-90, CR-02) adds Venue Staff's screens for blocks.
- **Who searches (D25, `DECISION-PENDING`).** US2 is the Event Coordinator's story, so `coordinator` may search, plus `operations_manager`, which stands in for the Coordinator Lead and Venue Staff until US16b. Organisers and attendees can't. In the app, the search form shows for Coordinator and Venue staff, above the catalogue.
- **Buffers aren't applied (D26, `DECISION-PENDING`).** Search checks the window itself, the same plain window as US22's D22. US13 (SCRUM-16) owns buffer scheduling, and CR-01 says buffer conflicts are flagged rather than hidden. If the team wants search to hide buffer clashes too, it's one change in `find_available`.
- **The seed's approved booking locks the auditorium's buffers.** US22's `has_approved_future_bookings` is live, so the seeded Mochtar Riady Auditorium can't have its setup or turnaround changed until that booking ends.
- **Times are Singapore wall-clock (D9, TC-X-01),** and a search can't cross midnight, like venue hours.
- **New error code `INVALID_VENUE_SEARCH`** (deviation 31, 422 with `fields` and `errors`), for values present but invalid, including attendance that isn't a whole number. Missing criteria reuse `MISSING_REQUIRED_FIELD`.
