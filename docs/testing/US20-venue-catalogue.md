# US20 — Manage the venue catalogue (SCRUM-87): test cases

**Story:** As a Venue Staff member, I want to record and maintain ConnectSphere's venues so that coordinators plan events using accurate venue information.

**Source of truth:** the acceptance criteria and the "Venue fields" table in Jira SCRUM-87, as updated on 13 Oct 2026.

**Delivery:** PR 1 (#53) added the `venues` table, its constraints, the seed and these test cases. PR 2 adds the endpoints, the access rule and the screens, with no migration.

**Tests:**

- PR 1: `backend/tests/venue/test_venue_schema.py`
- PR 2: `backend/tests/venue/test_venue_api.py` (API) and `e2e/tests/venue-catalogue.spec.ts` (Playwright); the seeded venue staff user is checked in `test_venue_schema.py`

## Test cases

There's one test case per acceptance criterion, two that cover the schema and the seed, and PR 2's cases for the API's edges (10 to 19). **PR** says which PR covers the case. "PR 1 (DB)" means the database layer only.

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US20-01 | 1. Create a venue with name, location, capacity, facilities, accessibility features, room layouts, operating hours, setup and turnaround minutes | A venue with every field saves and reads back unchanged, and is active by default. Through the API, tags and buffers left out take their defaults | Auto pytest | PR 1 (DB) · PR 2 (API create) |
| TC-US20-02 | 2. Edit any detail; setup and turnaround can't change while the venue has approved future bookings; capacity or hours edits flag affected bookings and notify | Edits change only the fields sent. A buffer edit while the venue has an approved future booking is refused (`409 VENUE_BUFFERS_LOCKED`) with an error saying why, and nothing is saved. Other fields stay editable. The bookings check is stubbed, so tests force it on. A capacity or hours edit flags the booking for review and notifies, and the booking itself is unchanged | Auto pytest | PR 2 (lock, against the stub) · US13/US22 (flagging and notifying) |
| TC-US20-03 | 3. Deactivate a venue: it leaves search, existing bookings are kept | `is_active` becomes false and the venue leaves non-staff lists and reads. Staff can still edit it, and it stays inactive. Reactivating brings it back. Both actions are idempotent. Its bookings remain | Auto pytest | PR 2 (bookings half in US22; search half verified again in US2) |
| TC-US20-04 | 4. Invalid data can't be saved (capacity ≤ 0, negative buffers, closing before opening), with an error naming the field; 0 minutes is valid | The database rejects each case with its own named CHECK, and 0/0 buffers save. The API answers `422 INVALID_VENUE` with `fields` and a message per field, reporting every invalid field at once | Auto pytest | PR 1 (DB) · PR 2 (API error) |
| TC-US20-05 | 5. See all venues in a list, with search by name | The list shows the seeded active venues; typing part of a name filters it | Auto Playwright | PR 2 |
| TC-US20-06 | 6. Other roles can view venue details but not change them | Organisers, coordinators and attendees list and read venues; every write route gives them `403 FORBIDDEN`, as it does an inactive staff member | Auto pytest | PR 2 (stub role until US16b, D19) |
| TC-US20-07 | 7. Setup and turnaround are set per venue only; a booking can't override them | Only `venues` has buffer columns; the booking API accepts no buffer fields | Auto pytest | PR 1 (DB) · US22 (booking API) |
| TC-US20-08 | Schema | `venues` has exactly the agreed columns, the named CHECKs, and RLS on | Auto pytest | PR 1 |
| TC-US20-09 | Seed | Six venues with varied capacity, tags and buffers: one with 0/0 buffers, exactly one inactive (a venue no seeded event uses), every tag from the fixed lists, no duplicate tags; a second run adds nothing. PR 2 adds a venue staff user (`operations_manager`, D19) | Auto pytest | PR 1 · PR 2 (staff user) |
| TC-US20-10 | 1, 4 | Tags are trimmed, de-duplicated and stored in D18's order | Auto pytest | PR 2 |
| TC-US20-11 | 4 | A tag outside D18's lists, in any of the three lists, is `422 INVALID_VENUE` naming the field and the tag | Auto pytest | PR 2 |
| TC-US20-12 | 1, 4 | Creating without required fields is `422 MISSING_REQUIRED_FIELD` listing them | Auto pytest | PR 2 |
| TC-US20-13 | 2, 4 | An edit is checked against the venue as it would be after it, so a new opening time after the stored closing time is refused. Nulling a required field is `MISSING_REQUIRED_FIELD` | Auto pytest | PR 2 |
| TC-US20-14 | 3, 6 | Staff list active, inactive or all venues and can read an inactive one; other roles never see inactive venues, even when they ask with `active=false` | Auto pytest | PR 2 |
| TC-US20-15 | 6 | Every venue route needs an identity: `401 UNAUTHENTICATED` without one | Auto pytest | PR 2 |
| TC-US20-16 | 5 | Name search is a case-insensitive substring. `min_capacity` and the facility and accessibility filters combine, and a venue must have every given tag. An unknown filter tag is `422` | Auto pytest | PR 2 |
| TC-US20-17 | 2 | With no bookings table, the buffer lock never triggers, so buffer edits pass. A buffer sent with its stored value isn't an edit, even while locked | Auto pytest | PR 2 |
| TC-US20-18 | — | An unknown venue id is `404 NOT_FOUND` on every route; an unknown body field is `422` | Auto pytest | PR 2 |
| TC-US20-19 | 1, 2, 3, 4, 6 | In the browser, Venue staff add a venue, see the API's capacity error on the field, fix it, edit capacity and setup, and deactivate it. Organisers then can't find it and never see Add or Edit | Auto Playwright | PR 2 |

## Decisions and constraints in PR 1

- **Tags come from fixed lists (D18, `DECISION-PENDING`).** Jira gives only examples, so the vocabularies live in `app/venue/models.py` and a migration CHECK mirrors them. Change both together, and `frontend/src/features/venue/tags.ts` too since PR 2.
  - Facilities: projector, screen, sound_system, microphone, stage, wifi, whiteboard, video_conferencing, power_outlets.
  - Accessibility: wheelchair, lift, accessible_toilet, hearing_loop, step_free_entrance.
  - Layouts: theatre, classroom, banquet, boardroom, u_shape, cabaret, standing.
- **Name and location can't be blank.** Names don't have to be unique.
- **One venue hosts one event at a time.** There's no rooms table.
- **Opening hours can't cross midnight.** `closes_at > opens_at` is AC 4's rule as written.

## Decisions in PR 2

- **`operations_manager` stands in for Venue Staff (D19, `DECISION-PENDING`).** US16b adds `venue_staff` with a migration, and PR 2 has none. So one constant, `VENUE_STAFF_ROLES` in `app/venue/service.py`, holds `operations_manager`, and US16b changes that line. The seed adds `venue.staff@smu.edu.sg` with that role; in the app it's **Acting as → Venue staff** (`VITE_DEV_VENUE_STAFF_ID`). Side effect: `operations_manager` also stands in for the Coordinator Lead, so this user can read the event-request queue (D11).
- **New error codes.** `422 INVALID_VENUE` carries `fields` plus `errors`, a message per field, for values present but invalid, including tags outside D18's lists (deviation 21). `409 VENUE_BUFFERS_LOCKED` carries `fields` and a `message` saying why (deviation 22). Missing required fields reuse `MISSING_REQUIRED_FIELD`. As backstops, the named CHECKs map to the same fields.
- **Buffer lock is a stub until US22.** `has_approved_future_bookings` returns `False` with a `TODO(US22)`. The refusal is built and tested by forcing that function on, but it can't happen in the product until bookings exist.
- **Inactive venues stay editable.** Staff may fix details before reactivating, and an edit doesn't reactivate.
- **Non-staff see active venues only.** An inactive venue is `404` to them, the same "not visible means not found" rule as elsewhere. `active` filters only staff's lists.
- **Deferred: flagging and notifying on capacity or hours edits (AC 2, TC-US20-02).** Such an edit should flag affected future bookings for review (US13's conflict flag) and notify Venue Staff and the assigned coordinators, never changing or cancelling a booking automatically. Neither bookings nor venue notifications exist yet. Flagging lands in **US13 (SCRUM-16)**, and the booking link and its approved status in **US22 (SCRUM-89)**, with US4 approving.
