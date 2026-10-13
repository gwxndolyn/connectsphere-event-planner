# US20 — Manage the venue catalogue (SCRUM-87): test cases

**Story:** As a Venue Staff member, I want to record and maintain ConnectSphere's venues so that coordinators plan events using accurate venue information.

**Source of truth:** the acceptance criteria and the "Venue fields" table in Jira SCRUM-87, as updated on 13 Oct 2026.

**Delivery:** PR 1 adds the `venues` table, its constraints, the seed and these test cases. PR 2 adds the endpoints, the access rule and the screens.

**Tests:**

- PR 1: `backend/tests/venue/test_venue_schema.py`
- PR 2: the API tests and a Playwright spec, to be added

## Test cases

One test case per acceptance criterion, plus two that cover the schema and the seed. **PR** says which PR covers the case; "PR 1 (DB)" means the database layer only.

| ID | AC | Check | Type | PR |
| --- | --- | --- | --- | --- |
| TC-US20-01 | 1. Create a venue with name, location, capacity, facilities, accessibility features, room layouts, operating hours, setup and turnaround minutes | A venue with every field saves and reads back unchanged, and is active by default | Auto pytest | PR 1 (DB) · PR 2 (API create) |
| TC-US20-02 | 2. Edit any detail; setup and turnaround can't change while the venue has approved future bookings; capacity or hours edits flag affected bookings and notify | Edits save. A buffer edit with an approved future booking is refused with an error saying why. A capacity or hours edit flags the booking for review and notifies; the booking itself is unchanged | Auto pytest | PR 2 (flagging needs US13, locking needs bookings from US22/US4) |
| TC-US20-03 | 3. Deactivate a venue: it leaves search, existing bookings are kept | `is_active` becomes false; the venue no longer appears in search; its bookings remain | Auto pytest | PR 2 (the search half is verified again in US2) |
| TC-US20-04 | 4. Invalid data can't be saved (capacity ≤ 0, negative buffers, closing before opening), with an error naming the field; 0 minutes is valid | The database rejects each case with its own named CHECK; 0/0 buffers save. The API turns each into an error that names the field | Auto pytest | PR 1 (DB) · PR 2 (API error) |
| TC-US20-05 | 5. See all venues in a list, with search by name | The list shows every venue; typing part of a name filters it | Auto Playwright | PR 2 |
| TC-US20-06 | 6. Other roles can view venue details but not change them | Other roles get the details; their writes are refused | Auto pytest | PR 2 (stub until US16b) |
| TC-US20-07 | 7. Setup and turnaround are set per venue only; a booking can't override them | Only `venues` has buffer columns; the booking API accepts no buffer fields | Auto pytest | PR 1 (DB) · US22 (booking API) |
| TC-US20-08 | Schema | `venues` has exactly the agreed columns, the named CHECKs, and RLS on | Auto pytest | PR 1 |
| TC-US20-09 | Seed | Six venues with varied capacity, tags and buffers: one with 0/0 buffers, exactly one inactive (a venue no seeded event uses), every tag from the fixed lists, no duplicate tags; a second run adds nothing | Auto pytest | PR 1 |

## Decisions and constraints in PR 1

- **Tags come from fixed lists (D18, `DECISION-PENDING`).** Jira gives only examples, so the vocabularies live in `app/venue/models.py` and a migration CHECK mirrors them. Change both together.
  - Facilities: projector, screen, sound_system, microphone, stage, wifi, whiteboard, video_conferencing, power_outlets.
  - Accessibility: wheelchair, lift, accessible_toilet, hearing_loop, step_free_entrance.
  - Layouts: theatre, classroom, banquet, boardroom, u_shape, cabaret, standing.
- **Name and location can't be blank.** Names don't have to be unique.
- **One venue hosts one event at a time.** There's no rooms table.
- **Opening hours can't cross midnight.** `closes_at > opens_at` is AC 4's rule as written.

## Notes for PR 2 (not built here)

- **Access:** create, edit and deactivate need the Venue Staff role, which arrives with US16b (SCRUM-82). Until then, guard the write routes with a `DECISION-PENDING` stub on the dev identity, and give it a new D-number in `claude_instructions.md`.
- **Buffer lock:** refuse a setup or turnaround edit while the venue has approved future bookings, with an error saying why. This needs the bookings table from US22/US4; if that table isn't merged yet, stub the check and say so.
- **Capacity or hours edits:** flag affected future bookings for review (US13's conflict flag) and notify Venue Staff and the assigned coordinators. Never change or cancel a booking automatically.
- **Duplicate tags:** the database doesn't reject them (a CHECK can't hold a subquery), so the API trims and de-duplicates tag lists before saving.
- **Errors naming the field:** map each named CHECK (`venues_capacity_positive`, `venues_hours_valid`, and so on) to the field it guards.
