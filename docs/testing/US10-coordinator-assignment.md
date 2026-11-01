# US10a to US10d — Coordinator assignment (SCRUM-13, 67, 68, 69): acceptance evidence

**Source of truth:** the acceptance criteria in Jira SCRUM-13, SCRUM-67, SCRUM-68 and SCRUM-69. The test cases themselves are in `claude_instructions.md` §4 (TC-US10A, TC-US10B, TC-US10C, TC-US10D). This file maps each AC to its tests and to evidence from the running app.

All four stories were built in Sprints 3 and 4 (PRs #63 to #72, #89). An audit on 1 Nov found every AC implemented and tested, with three follow-ups, made in this PR:

- **SCRUM-69 AC 3:** a reassignment's history entry said "Lena Lim assigned Dana Lim". It now says "Lena Lim reassigned the event to Dana Lim", so the sentence matches the Reassignment label (TC-US10D-12 checks both wordings).
- **SCRUM-13 AC 7:** new TC-US10A-32 proves a Lead who isn't a coordinator gets `403` on approve, reject, confirm, readiness and preparation. Before, only approve, reject and confirm had a Lead test.
- **Evidence:** the screenshots and notice logs below.

**Known, recorded deviations** (still open with the PO, not changed here):

- **D27:** assigning moves a request to `under_review`, not Planning.
- **D30:** the picker's count includes `under_review`, `awaiting_clarification` and `approved` as well as `planning`. A Planning-only count would never rise on assignment (SCRUM-67 AC 3) because of D27.
- **D28, D29:** notices are log-only, and the "event date" is the request's preferred dates until a date is confirmed.
- **D42:** events assigned before the history table start with an empty history.
- **D46:** a user holding both Lead and Coordinator can decide events assigned to them as coordinator.

## SCRUM-13 (US10a) — assign a coordinator

| AC | Tests | Evidence |
| --- | --- | --- |
| 1. New requests go to an unassigned queue; nobody is assigned or suggested | TC-US10A-05, 07, 21; E2E TC-US10A-26 | [10a-02](screenshots/US10/10a-02-ac1-ac2-unassigned-queue-with-details.png) queue; [10a-03](screenshots/US10/10a-03-ac1-no-suggestion-10b-ac1-ac2-workload-counts.png) picker with nothing chosen and Confirm disabled |
| 2. Name, organiser, preferred dates, attendance and status shown | TC-US10A-06, 21; E2E | [10a-02](screenshots/US10/10a-02-ac1-ac2-unassigned-queue-with-details.png) |
| 3. Assign one active coordinator to a Submitted, unassigned request | TC-US10A-08, 15 to 17 | [10a-04](screenshots/US10/10a-04-ac3-assigned.png) |
| 4. Inactive or non-coordinator refused with a reason; nothing changes | TC-US10A-10, 11, 22 | [10a-11](screenshots/US10/10a-11-ac4-inactive-refused-with-reason.png) "That coordinator is inactive.", still Submitted |
| 5. The request leaves the queue | TC-US10A-08, 23; E2E | [10a-05](screenshots/US10/10a-05-ac5-left-the-queue.png) |
| 6. Only the Lead assigns; others see no Assign | TC-US10A-13, 24; TC-US16B-14; E2E | [10a-07](screenshots/US10/10a-07-ac6-no-assign-for-other-roles.png) the coordinator's screen, no Assign |
| 7. The Lead can't self-assign, approve, reject or confirm | TC-US10A-12, **32 (new)**; TC-US19-11; TC-US18-20 | Backend tests (`403 FORBIDDEN`, `422 INVALID_COORDINATOR` `self_assignment`) |
| 8. The organiser sees "Unassigned", then the name | TC-US10A-05, 09, 25; E2E | [10a-01](screenshots/US10/10a-01-ac8-organiser-sees-unassigned.png) before; [10a-06](screenshots/US10/10a-06-ac8-organiser-sees-coordinator-name.png) after (Hackathon Kick-off shows Dana Lim, its coordinator after the reassignment) |
| 9. Earlier assignments are kept | TC-US10A-04, 20 | [10a-06](screenshots/US10/10a-06-ac8-organiser-sees-coordinator-name.png) seeded events keep Casey Tan |
| 10. A returned request goes back to its coordinator, not the queue | TC-US10A-19 | [10a-08](screenshots/US10/10a-08-ac10-returned-request-keeps-coordinator.png) Sustainability Talk is under review with Casey Tan after the organiser answered the clarification; [10a-09](screenshots/US10/10a-09-ac10-not-back-in-unassigned-queue.png) not in the queue. "Returned" is a clarification round: a rejected request can't be resubmitted (`EVENT_REQUEST_LOCKED`) |
| 11. The Lead is told about a new queued request: name, organiser, dates | TC-US10A-27 to 31 | [10a-10 log](screenshots/US10/10a-10-ac11-lead-notified-log.txt) both Leads, with the reference, name, organiser and preferred dates |

## SCRUM-67 (US10b) — workload in the picker

| AC | Tests | Evidence |
| --- | --- | --- |
| 1. Each entry shows the name and the count (D30) | TC-US10B-01 to 03, 07; E2E | [10a-03](screenshots/US10/10a-03-ac1-no-suggestion-10b-ac1-ac2-workload-counts.png) |
| 2. None shows 0 | TC-US10B-01, 07 | [10a-03](screenshots/US10/10a-03-ac1-no-suggestion-10b-ac1-ac2-workload-counts.png) Dana Lim, Morgan Lau: 0 |
| 3. After an assignment the count is 1 higher | TC-US10B-04, 05, 08 | [10a-03](screenshots/US10/10a-03-ac1-no-suggestion-10b-ac1-ac2-workload-counts.png) Casey Tan 6 → [10b-02](screenshots/US10/10b-02-ac3-count-one-higher.png) 7 after Sustainability Talk was assigned to her (Dana 0 → 1 after the reassignment) |

## SCRUM-68 (US10c) — notices

| AC | Tests | Evidence |
| --- | --- | --- |
| 1. The coordinator is told the event, coordinator and date | TC-US10C-01, 03, 05, 07 | [10c-01 log](screenshots/US10/10c-01-ac1-ac4-notification-log.txt), coordinator notice |
| 2. The organiser gets the same | TC-US10C-02, 06 | the same log, organiser notice |
| 3. Nothing is sent for an assignment that doesn't complete | TC-US10C-04 | The refused assignment in 10a-11 sent nothing (no "coordinator assigned" line for Design Critique Night) |
| 4. On reassignment: new and previous coordinators and the organiser, with name, date and new coordinator | TC-US10E-16 to 18 | the same log, three "event reassigned" lines |
| 5. Other Leads optional; the action always recorded | TC-US10C-02, TC-US10D-02, TC-US10E-01 | No Lead notices in the log; the history in 10d-01 |

## SCRUM-69 (US10d) — assignment history

| AC | Tests | Evidence |
| --- | --- | --- |
| 1. A record of who, which coordinator, which event, when | TC-US10D-01 to 04, 15 | [10d-01](screenshots/US10/10d-01-ac1-ac2-ac3-history-newest-first.png) |
| 2. Newest first | TC-US10D-06, 12; TC-US10E-15 | [10d-01](screenshots/US10/10d-01-ac1-ac2-ac3-history-newest-first.png) the reassignment above the assignment |
| 3. Assignment or reassignment, the Lead, the coordinator and the time; visible to the Lead | TC-US10D-05, 09, 11, **12 (updated)**, 14; TC-US10E-25; E2E | [10d-01](screenshots/US10/10d-01-ac1-ac2-ac3-history-newest-first.png) "Lena Lim reassigned the event to Dana Lim" with its reason, then "Lena Lim assigned Casey Tan" |

## How the evidence was taken

1 Nov 2026, branch `docs(SCRUM-13-69)Coordinator-Assignment-Evidence`. Local Postgres 16 in UTC, seeded with `python -m app.seed`, plus a second coordinator (Dana Lim) as in §1a "When something looks broken". Uvicorn ran with app INFO logging on, so the log-only notices could be captured. The screens are in dev mode with Acting as: the seeded organiser (Olivia Organiser), the Lead (Lena Lim) and the coordinator (Casey Tan).

## Run log

1 Nov 2026, this branch:

- Backend: `pytest` — 1592 passed (TC-US10A-32 new).
- Frontend: `npm run lint`, `npm run build`, `npm test` — 472 passed.
- E2E: `npx playwright test --project=chromium` — 49 passed. The `login` project needs Supabase secrets and wasn't run.
