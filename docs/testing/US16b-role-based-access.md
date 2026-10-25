# US16b — Role-based access (SCRUM-82): test cases

**Story:** As ConnectSphere, I want each user to see and change only what their role and relationship to an event allow so that client and internal information stays protected.

**Source of truth:** the acceptance criteria in Jira SCRUM-82 (changed 12 and 13 Oct 2026) and its subtasks SCRUM-119 to SCRUM-121, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Each user has one or more roles: Event Organiser, Event Coordinator, Event Coordinator Lead, Venue Staff, Technical Support Staff, Safety Officer or Attendee.
2. A user with more than one role can switch between them, and sees only the current role's navigation and screens.
3. Opening a screen or action for a role the user doesn't hold is refused; nothing is shown or changed.
4. An Organiser sees only their own organisation's requests; another organisation's request behaves as if it doesn't exist.
5. An Event Coordinator can only manage events assigned to them.
6. An Attendee can't see internal planning information (clarifications, bookings, equipment, safety reviews).
7. More than one user can be a Lead, each Lead's supervisory scope is recorded, and the Lead role doesn't include account administration.

**Delivery:** one PR per subtask, in this order, all in Sprint 4 (none landed in Sprint 3).

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-119 | `users.roles` replaces `users.role`; `venue_staff` and `safety_officer`; checks on held roles; `/me` returns `roles` and, until PR 3, `role`; `operations_manager` retired; seed one user per role and a two-role user | backend `pytest` |
| 2 | SCRUM-120 | Coordinators scoped to their assigned events, with the thread following a reassignment; no approving your own request; organiser, attendee, role-matrix and Lead checks; the clarification E2E gains a Lead-assign step | backend `pytest`, E2E |
| 3 | SCRUM-121 | Role switcher and navigation per current role; Safety officer's "no screens yet"; **Acting as** gains Safety officer; `/me` drops `role` | lint, build, Vitest, Playwright |

## Decisions for this story

Taken by the story owner on 25 Oct, before any code; the PR #86 review added D51 and refined D47 and D48. The full logic, the alternatives and the consequences are in `claude_instructions.md` §9, "US16b role-based access: decisions".

- **D45, roles are a list:** a `roles` column on `users` (at least one, no repeats), replacing `users.role`; not a separate table.
- **D46, the API checks every role a user holds:** the current role is the frontend's choice (the switcher) and isn't sent to the API, as AC 3 speaks of roles a user doesn't *hold*.
- **D47, an organiser's organisation is the organiser:** another organiser's request is `404`; no organisation model. **Asked the PO on 25 Oct** whether colleagues at one organisation should see each other's requests; if yes, an organisations model goes into Sprint 4.
- **D48, coordinators see only their assigned requests:** the review queue, details, thread and clarifications; anyone else `404`. No coordinator can clarify an unassigned request, and on reassignment the thread follows the request to the new coordinator. Retires D14 and narrows D11 for coordinators.
- **D49, `operations_manager` is retired:** its users become `venue_staff`; the value stays in the type, unused. Retires D19.
- **D50, the two-role seed user:** `multi.role@smu.edu.sg`, Coordinator and Venue staff.
- **D51, no approving your own request:** a Venue Staff member can't approve or reject a booking they requested, and Tech Support can't review an equipment line they requested (`403`). **To confirm with the PO.**

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US16B-01 | 1 | A database at the previous head | `alembic upgrade head` | `users.roles` exists, not null, with named CHECKs for at least one role and no repeats; `user_role` includes `venue_staff` and `safety_officer`; `users.role` is gone; RLS is still on; one Alembic head | SCRUM-119 |
| TC-US16B-02 | 1 | Users holding each existing role | The upgrade runs, then the downgrade | Each user's `roles` is their old role; `operations_manager` users hold `venue_staff`. The downgrade restores `role`, and refuses while a user holds two roles or `safety_officer` | SCRUM-119 |
| TC-US16B-03 | 1 | A user | Saved with no roles, or a role twice | Refused on a named CHECK | SCRUM-119 |
| TC-US16B-04 | 1, 7 | The seed | Runs twice | One active user per role (Organiser, Coordinator, two Leads, Venue staff, Tech support, Safety officer, Attendee) and `multi.role@smu.edu.sg` holding Coordinator and Venue staff, each with a full name; no user holds `operations_manager`; the second run adds nothing | SCRUM-119 |
| TC-US16B-05 | 1, 3 | A user holding Coordinator and Venue staff | Calls a Coordinator route, a Venue Staff route, and a Lead route | The first two are allowed; the Lead route is `403 FORBIDDEN` | SCRUM-119 |
| TC-US16B-06 | 1 | A `venue_staff` user | Edits a venue, opens the pending bookings, approves one | Allowed: Venue Staff is the real role now (D19 retired) | SCRUM-119 |
| TC-US16B-07 | 1 | Any signed-in user | `GET /api/v1/me` | `roles` lists every role they hold, in the role type's order, and `role` is the first of them (kept until SCRUM-121); sign-up creates `[organiser]` or `[attendee]`, and a staff role is still `422 INVALID_ROLE` *(changed 25 Oct)* | SCRUM-119 |
| TC-US16B-08 | 3 | A user holding any staff role, with a matching unlinked email | Logs in for the first time | Not linked by email (SCRUM-102's rule now reads every held role) | SCRUM-119 |
| TC-US16B-09 | 5 | Requests assigned to coordinator A, to coordinator B, and one unassigned | A opens the review queue | Only A's | SCRUM-120 |
| TC-US16B-10 | 5 | A request assigned to coordinator A | B opens its details or its clarification thread | `404 NOT_FOUND`; A gets them | SCRUM-120 |
| TC-US16B-11 | 5 | A request assigned to coordinator A, and an unassigned request | B sends a clarification on A's; any coordinator sends one on the unassigned request | `404` both times; nothing saved, nobody notified; A can send one on theirs (D14 retired) *(changed 25 Oct)* | SCRUM-120 |
| TC-US16B-12 | 4 | Organiser A's request | Organiser B opens it, its thread, edits, submits or responds to it | `404` every time, as if it doesn't exist | SCRUM-120 |
| TC-US16B-13 | 6 | An attendee | Calls each internal route (clarifications, venue bookings, equipment lines, event requests, venue search, assignment history), then opens the events board and My events | `403 FORBIDDEN` on every internal route, nothing returned; the attendee's own event endpoints (`/events/available`, `/me/registrations`) carry no clarification, booking or equipment fields *(changed 25 Oct)* | SCRUM-120 |
| TC-US16B-14 | 3 | Each role, and no identity | Calls each role-gated route family | Allowed only for the roles the route names; others `403`; no identity `401` | SCRUM-120 |
| TC-US16B-15 | 7 | Two Leads | Each assigns a request, then opens the Assigned tab; the app's routes are listed | Each sees only their own (D44); no route creates users or changes roles | SCRUM-120 |
| TC-US16B-16 | 5 | Acting as the organiser, the Lead and the coordinator | Submit, assign to the coordinator, ask for clarification, answer | The journey works with the assign step; the coordinator doesn't see the request before it's assigned (E2E) | SCRUM-120 |
| TC-US16B-17 | 2 | A user with one role | Logs in | No role switcher; their home screen | SCRUM-121 |
| TC-US16B-18 | 2 | `multi.role@smu.edu.sg` (Coordinator, Venue staff) | Logs in | The switcher lists exactly those two; it starts on Coordinator's home, and navigation shows only Coordinator's screens | SCRUM-121 |
| TC-US16B-19 | 2 | The same user | Switches to Venue staff, then refreshes | Navigation and home change to Venue staff's, and stay after the refresh | SCRUM-121 |
| TC-US16B-20 | 2, 3 | A stored screen or current role the user no longer has, or a different user on the same browser | The app loads | It falls back to the user's first held role and its home screen | SCRUM-121 |
| TC-US16B-21 | 1 | A Safety officer | Logs in | "Your account's role doesn't have any screens yet" with Log out | SCRUM-121 |
| TC-US16B-22 | 2 | Dev mode | Opens **Acting as** | Safety officer is the one new option; Venue staff sends the seeded `venue_staff` user's id *(changed 25 Oct)* | SCRUM-121 |
| TC-US16B-23 | 2 | `multi.role@smu.edu.sg` in the login E2E | Logs in, sees Event requests, switches to Venue staff | Venues with the pending list shows; a refresh keeps Venue staff (E2E) | SCRUM-121 |
| TC-US16B-24 | 1, 3 | `multi.role@smu.edu.sg` (Coordinator, Venue staff), plus Leads and Venue staff who also hold other roles | A Lead opens the coordinator picker and assigns a request to `multi.role`; an organiser submits a request; a coordinator requests a venue | The picker lists `multi.role` with the right planning count and the assignment succeeds; every active Lead is told of the submitted request and every active Venue Staff member of the venue request, whatever other roles they hold *(added 25 Oct)* | SCRUM-119 |
| TC-US16B-25 | 3 | `multi.role@smu.edu.sg` requested a venue booking as Coordinator; a Coordinator who is also Tech support requested an equipment line | Each tries to approve or reject their own request in their other role | `403` with a code of its own, nothing changes; another Venue Staff member or Tech Support user can decide it (D51) *(added 25 Oct)* | SCRUM-120 |
| TC-US16B-26 | 5 | A request with an open clarification, assigned to coordinator A | It's reassigned to coordinator B (the assignment changed directly, until SCRUM-83 builds reassigning) | B reads the thread and can continue it; A now gets `404` (D48) *(added 25 Oct)* | SCRUM-120 |
| TC-US16B-27 | 2 | Any signed-in user, after SCRUM-121 | `GET /api/v1/me` | Only `roles`, no `role`; the frontend reads `roles` everywhere it read `role` *(added 25 Oct)* | SCRUM-121 |
