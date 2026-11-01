# US15 — Multi-session event programme (SCRUM-18): test cases

**Story:** As an Event Organizer, I want to build a structured multi-session event agenda with designated session titles, timings, and activity types, so that ConnectSphere staff and registered attendees have a clear breakdown of the event schedule.

**Source of truth:** the acceptance criteria in Jira SCRUM-18 and its subtasks SCRUM-138 to SCRUM-140, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. The Organiser adds, edits and deletes agenda items within a draft or active planning request.
2. Each session has a title, start time, end time, speaker or presenter, and session type.
3. A session outside the event's confirmed date and time window can't be saved.
4. Sessions that overlap within the same single-track schedule can't be saved.
5. The schedule is shown in chronological order on the event overview page.

**Delivery:** one PR per subtask, in this order.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-138 | `event_sessions` (one track per event); the seeded Agenda Demo, whose sessions a reseed clears | `backend/tests/agenda/test_event_sessions_schema.py` |
| 2 | SCRUM-139 | `GET` / `POST /api/v1/event-requests/{id}/sessions`, `PATCH` / `DELETE /api/v1/event-sessions/{id}` | backend `pytest`; the routes in US16b's role matrix (TC-US16B-14) |
| 3 | SCRUM-140 | **Agenda** on the request's details in the Organiser's Event requests screen | Vitest; E2E |

## Decisions for this story

Decided by the acting PO, Matthew, on 1 Nov (team channel).

- **D87, who and when (AC 1):** the request's own Organiser, while it's `draft` or `planning`; read-only in every other status, `awaiting_clarification` included, and for anyone else who can read the request.
- **D88, the window (AC 3):** a `planning` event's `[start_at, end_at]`; for a draft, D65's window (one of its preferred dates, between its preferred times). Existing sessions aren't re-checked when the dates change, so the Agenda marks any outside the current window.
- **D89, single track (AC 4):** each event is one track; no two of its sessions overlap. A track per room is a likely follow-up.
- **D90, session fields (AC 2):** the AC's types plus `other`; the speaker is required unless it's a break.
- **D91, where (AC 5):** the request's details in the Organiser's Event requests screen.

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US15-01 | — | A database at the previous head | `alembic upgrade head` | `event_sessions` exists with its columns, the `session_type` enum, RLS on and the exclusion constraint; one Alembic head | SCRUM-138 |
| TC-US15-02 | 2 | An event | Sessions are saved with: a blank title; an end not after the start; no speaker on a non-break; an unknown event; then a break with no speaker, and an `other` session with a speaker | Each of the first four is refused on its named CHECK or the foreign key; the break and the `other` session save | SCRUM-138 |
| TC-US15-03 | 4 | An event with a 10:00–11:00 session | Another session is saved on the same event at 10:30–11:30; one at 11:00–12:00; and one at 10:30–11:30 on a different event | The first is refused on the exclusion constraint; back-to-back saves; the other event's saves | SCRUM-138 |
| TC-US15-04 | — | The seed; sessions on Agenda Demo and on another event | The seed runs (twice) | Agenda Demo exists in `planning`, owned by the seeded organiser, with its times; the second run changes nothing; Agenda Demo's sessions are gone and the other event's remain | SCRUM-138 |
| TC-US15-05 | 1, 2, 5 | The owner's draft with preferred dates and times | The owner adds a presentation, a workshop, a panel, a break and an `other` session, then lists them | `201` each; the list is in chronological order with every field | SCRUM-139 |
| TC-US15-06 | 1 | A session | The owner edits its title, speaker and times; then deletes it | `200` with the new values; `204`, then it's gone from the list | SCRUM-139 |
| TC-US15-07 | 3 | A planning event (10:00–17:00), and a draft with two preferred dates, 09:00–12:00 | Sessions starting before, ending after, or on a date that isn't preferred; one exactly at the edges; a draft with no dates | Outside the window is `422 INVALID_SESSION` naming `starts_at` / `ends_at`; the edges save; no dates is `422` saying the event's dates are needed first | SCRUM-139 |
| TC-US15-08 | 4 | A 10:00–11:00 session | Adding, or editing another session to, 10:30–11:30; adding 11:00–12:00; editing the first session within its own times | `409 SESSION_OVERLAP` naming the 10:00 session; back-to-back saves; a session doesn't clash with itself | SCRUM-139 |
| TC-US15-09 | 2 | A blank title, an end before the start, a non-break with no speaker, an unknown type | The owner adds it | `422 INVALID_SESSION`, naming every invalid field at once | SCRUM-139 |
| TC-US15-10 | 1 | A request in `submitted`, `awaiting_clarification`, `approved` and `confirmed` | The owner adds, edits or deletes a session | `409 AGENDA_NOT_EDITABLE` with the status; nothing changes; listing still works | SCRUM-139 |
| TC-US15-11 | — | Another organiser; a Lead; the assigned coordinator; other roles; no identity; an unknown request or session | They list, add, edit or delete | Another organiser `404`; the Lead and the assigned coordinator list a submitted request's agenda but get `403` changing it; other roles `403`; no identity `401`; unknown `404` | SCRUM-139 |
| TC-US15-12 | 4 | Two overlapping sessions for one draft | Both are saved at the same moment | One `201`, the other `409 SESSION_OVERLAP`: a real two-connection race, as TC-US27-11 | SCRUM-139 |
| TC-US15-13 | 1, 2, 3, 5 | The owner's draft with preferred dates | They add a session, fix a field error, edit it and delete another | Errors show on the fields; the agenda is in chronological order after each change | SCRUM-140 |
| TC-US15-14 | 1, 3, 4 | A mocked `SESSION_OVERLAP`; a submitted request; a session outside the current window | The owner saves; opens the submitted one; opens the third | The overlap is shown naming the clashing session; the submitted one's agenda is read-only; the session is marked "Outside the event's times" | SCRUM-140 |
| TC-US15-15 | 1, 2, 5 | Agenda Demo (planning) | The organiser adds a break and a presentation, then edits one, out of time order | The agenda shows them in chronological order. Rerun after a reseed | SCRUM-140 |

## Run log

| Date | Subtask | What ran | Result |
| --- | --- | --- | --- |
| 1 Nov | SCRUM-138 | `pytest` (local Postgres): `tests/agenda/test_event_sessions_schema.py`, then the full backend suite; `alembic downgrade -1` and `upgrade head`; the seed | Tests written first: they failed on collection (no `app.agenda`). After the change: 12 items for TC-US15-01 to 04 pass. Whole backend suite 1249 passed; the migration round-trips and the seed runs |
