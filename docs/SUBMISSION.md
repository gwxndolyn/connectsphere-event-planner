# Week 12 submission checklist (G8T4)

One `.zip`, sub-folders numbered **1–7** exactly as in the Project Instructions. Due **23:59, Friday Week 12** on eLearn;
one second late is a 10% penalty.

| Folder | Deliverable | Source | Status |
| --- | --- | --- | --- |
| `1 - Product Backlog` | Full final backlog, all stories | Master Backlog (statuses fixed, Change Log sheet) xlsx + PDF | Done 4 Nov; **to do:** add a Jira CSV export |
| `2 - System Design` | C4 model | [`docs/c4/README.md`](c4/README.md) (as built) PDF + High Level Design v0.6 | Done 4 Nov |
| `3 - Test Cases` | Traceable test cases, unit/integration/E2E | Test Cases tab PDF, [`docs/testing/TRACEABILITY.md`](testing/TRACEABILITY.md), `docs/testing/US*.md` + screenshots | Done; **to do:** run the 22 manual UI cases and mark them |
| `4 - Sprint Meetings` | Per sprint: backlog/goal, estimation, end board, burndown, retro; Sprint 4 recordings | Sprint tabs, planning docs, reviews, retros, burndowns from merge dates | Done; **to do:** recording links, Jira board screenshots |
| `5 - Slide Deck` | IS212 Week 11 template, as PDF | `G8T4_Slide_Deck.pptx` | Filled 4 Nov; **to do:** team review of red items, export PDF from PowerPoint |
| `6 - Code` | All code, README with run steps, tests, CI scripts | `git archive` of `main` (excludes `node_modules`, `.venv`) | Ready once this branch merges |
| `7 - README` | README with Git link; instructors given repo access | [`README.md`](../README.md) | **To do:** add both instructors as collaborators |

## Gaps found on 4 Nov 2026

### Scrum evidence (largest grade risk)

- **Sprint 4 retrospective is a copy of Sprint 2's** (same date "11 October", same goal and outcome). Write the real one.
- **Sprint Review doc**: Sprint 1 and 2 sections are template text; the Sprint 2 tables are empty; Sprint 3's
  `[Feedback from the customer…]` and `[Burndown screenshot from Jira]` are placeholders; no Sprint 4 review.
- **Sprint 1 retro** keeps `[date/time]`, `[review of previous retrospective]`, `[lessons learnt]`; Sprint 3 retro keeps `[Team's own points]`.
- **Playbook** still carries the "Highlighted text has not been confirmed" note and highlighted placeholders.
- **Sprint 4 recordings** (planning, review, retro, one standup): upload unlisted, put links on slide 2 and in folder 4.
- **Burndown charts** for every sprint: export from Jira.
- **Master Backlog inconsistencies**: *Product Backlog* tab shows US23a and US23b as "To Do" and US31 as "In Review",
  while *Sprint 4* tab and `main` show them Done. *Core Features* tab "Points Done" is 0 for F1, F5, F7, F9–F17, F19.
  *Spint Plan* tab name is misspelt. Sprint 3 notes say "still Active in Jira".
- **PR review evidence**: 41 of 118 merged PRs have no approving review (mostly Sprint 1–2, plus #128), and
  `main` has **no branch protection**. Turn it on now and say so honestly on slide 9 (Git strategy).

### Software (fixed on branch `fix(SCRUM-148)Core-Feature-Gaps`)

| Gap | Core feature | Fix | Tests |
| --- | --- | --- | --- |
| Nothing ever set an event to **Completed** | F6 Event Status Management | `POST /api/v1/event-requests/{id}/completion` + "Mark as completed" button (D120) | TC-US18-47 … 51, 2 Vitest |
| An event created in the app never reached the **attendee board** (`registration_enabled` was only set by the seed) | F18 Attendee Registration | Confirming opens registration when the request asked for it (D121) | TC-US18-44 … 46 |
| No notice when an attendee **registers or withdraws** | F20 Notification System | `Notifier.registration_changed`, recorded in the inbox (D122) | TC-US3-19 … 21, TC-US7-27 … 29, TC-US31-02 row |
| Coverage not reported in CI (DoD criterion 7) | CI | `pytest --cov` and `vitest --coverage` in CI with job summaries and HTML artifacts | — |

### Software (known, not fixed — raise in the deck as known shortcomings or fix if time allows)

- Venue search has **no room-layout filter** and doesn't say **why** a venue is unsuitable; reasons appear only when booking (F10, F11).
- Approving a request leaves it at `approved`; `planning` is only reached after a significant change (D53/D86). The
  coordinator's Events/edit screen lists only `planning`/`confirmed`/`cancelled`/`completed`, so normal edits are
  only reachable in Planning (F7).
- The coordinator's own critical edits notify no one; attendees aren't told of significant changes (D105).
- Organisers can't use venue search.
- Several decisions still marked `DECISION-PENDING` in `claude_instructions.md` (D4–D6, D15, D22, D53, D87–D91,
  D102–D107 rows still say pending although §1a says decided 3 Nov, D113–D122).

## Numbers for slide 10 (as of this branch)

| Metric | Result |
| --- | --- |
| Backend tests (pytest, real Postgres) | 1,894 passing, 0 failing |
| Frontend unit + integration (Vitest) | 554 passing, 0 failing (53 files) |
| Automated E2E (Playwright) | 72 tests in 30 specs, green on `main` |
| Backend coverage | 97% statements |
| Frontend coverage | 88.6% statements, 81.5% branches |
| CI runs | Backend 292 (5 red), Frontend 292 (2 red), E2E 152 (1 red), Markdown 109 (2 red), PR title 153 (1 red) |
| PRs | 138 opened, 118 merged |
