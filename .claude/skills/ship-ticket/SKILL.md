---
name: ship-ticket
description: >-
  End-to-end ticket workflow for the ConnectSphere event-planner repo. Takes a
  pasted Jira ticket, creates a correctly-named branch off an up-to-date main,
  implements the change, runs the test suites relevant to what changed until
  they pass, then (after explicit confirmation) pushes and opens a PR — with the
  branch name, every commit, and the PR title following the repo's conventions.
  Use when the user pastes a ticket to implement or says "work on this ticket",
  "ship this ticket", or invokes /ship-ticket.
---

# Ship a ticket, end to end

Drive a single ticket from description to open PR. Input is a **pasted ticket**
(there is no Jira integration configured — if the user names a ticket like
`SCRUM-42` but pastes no text, ask them to paste the title, description, and
acceptance criteria).

Work the phases in order. **Do not skip the confirmation gate (Phase 6)** —
pushing and opening a PR are outward-facing and hard to undo.

> The conventions and commands below were verified against this repo's CI on
> 2026-09-27. If a run behaves unexpectedly, re-read the source-of-truth files
> in Phase 0 before trusting these — they may have changed.

---

## Repo facts (verified)

- **Monorepo:** `backend/` (FastAPI, Python 3.12, pytest), `frontend/`
  (React 19 + Vite + TypeScript, oxlint), `e2e/` (Playwright).
- **Ticket keys:** `SCRUM-<n>` (e.g. `SCRUM-5`). A commit/branch may reference
  more than one (`SCRUM-30/31`).
- **Remote:** `origin` → `github.com/mattlkz/connectsphere-event-planner`, PRs
  target `main`.
- **Postgres** is required for backend and e2e tests:
  `docker compose up -d postgres` and
  `DATABASE_URL=postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere`.

---

## Phase 0 — Re-confirm conventions (source of truth)

Read these if anything looks off; they define the rules, not this doc:

- `.github/workflows/pr-title-check.yml` — enforced PR-title rule
  (`amannn/action-semantic-pull-request@v5`).
- `.github/workflows/backend-ci.yml`, `frontend-ci.yml`, `e2e.yml` — exact
  test/lint/build commands.
- `git log --oneline -20` and `git branch -a` — how commits/branches are named.

> **OneDrive note:** this project is in a OneDrive "Files On-Demand" folder. If a
> read times out and `ls -lO <file>` shows a `dataless` flag, the content isn't
> downloaded. Ask the user to right-click the project folder in Finder →
> **"Always keep on this device"**, then retry. Don't guess to work around it.

## Phase 1 — Parse the ticket

Extract and echo back to the user:

- **Ticket key** (`SCRUM-<n>`) — if absent, ask; it's needed for naming.
- **Type** — map to a Conventional type: bug → `fix`, story/feature → `feat`,
  docs → `docs`, refactor → `refactor`, tests → `test`, chores/infra → `chore`,
  formatting-only → `style`. **Only these are allowed** (PR-title check rejects
  `ci`, `build`, `perf`, `revert`).
- **Short summary** — a few words for the branch slug and titles.
- **Acceptance criteria** — the checklist to satisfy and later verify with tests.

Restate your understanding in a line or two before proceeding.

## Phase 2 — Create the branch

Branch names are **not** CI-enforced and history is inconsistent. Normalize to
this clean canonical form:

```
<type>/<TICKET-KEY>-<kebab-summary>
```

e.g. `feat/SCRUM-42-rsvp-endpoint`, `fix/SCRUM-7-waitlist-offer-expiry`.

```bash
git switch main
git pull --ff-only            # if this fails, stop and report
git switch -c feat/SCRUM-42-rsvp-endpoint
```

- Slug: lowercase, hyphenated, concise.
- If the branch exists, ask whether to reuse it or rename.

## Phase 3 — Implement

- Use `EnterPlanMode` (or restate a short plan) for anything non-trivial.
- Follow existing patterns in `backend/app/`, `frontend/src/`, `e2e/tests/`.
- Add/update tests so the acceptance criteria are covered where practical.
- If the backend schema changes, add an Alembic migration (`backend/migrations`).
- Keep the change scoped to the ticket.

## Phase 4 — Run the tests (gate: all relevant suites must pass)

Run the suites for the area(s) you touched. Backend-only change → backend suite;
UI/flow change → frontend and/or e2e; multi-area → each affected suite.

**Backend** (`backend/`) — needs Postgres:
```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"       # first run only
DATABASE_URL=postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere pytest
```

**Frontend** (`frontend/`) — CI runs lint + typecheck/build (no unit suite):
```bash
cd frontend
npm ci                         # or npm install if deps unchanged
npm run lint                   # oxlint
npm run build                  # tsc -b && vite build (typecheck + build)
```

**E2E** (`e2e/`, Playwright) — only when the change affects end-to-end behavior;
mirror `e2e.yml`:
```bash
docker compose up -d postgres
cd backend && DATABASE_URL=postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere \
  uvicorn app.main:app --port 8000 &        # background; ensure it's up
npx --yes wait-on --timeout 60000 http-get://localhost:8000/api/events/health
cd ../e2e && npm ci && npx playwright install --with-deps chromium && npm test
```

Fix code (or a wrong test) and re-run until green. **Never push with failing or
skipped required tests, and never claim green without having seen it.** Report
actual results.

## Phase 5 — Commit

Commit in logical units. **Every commit follows Conventional Commits** (same
allowed types as the PR check), with the ticket key in the scope or subject —
matching this repo's history:

```
feat(SCRUM-42): add RSVP endpoint and validation
fix(SCRUM-7): expire waitlist offer after deadline
```

- Imperative mood, no trailing period in the subject.
- Multiple commits are fine; each must independently follow the convention.

## Phase 6 — Confirm before pushing  ⚠️ REQUIRED GATE

Show the user and get explicit approval:

- branch name, commit list, proposed PR title + body, and a test-results summary.

Only continue once the user approves.

## Phase 7 — Push and open the PR

```bash
git push -u origin <branch>
gh pr create --base main --title "<PR title>" --body "<body>"
```

- **PR title** must satisfy `pr-title-check.yml`: `type(scope): subject` or
  `type: subject`, type ∈ `feat|fix|docs|style|refactor|test|chore`. Include the
  ticket key (scope or subject), e.g. `feat(SCRUM-42): add RSVP endpoint`.
- If `gh` reports this is a fork, let it set the upstream base repo; otherwise
  the PR is opened on `mattlkz/connectsphere-event-planner` against `main`.
- **PR body:** summary of the change, ticket reference (`SCRUM-42`), how it was
  tested (which suites, all passing), and a checklist mapped to the acceptance
  criteria.
- End the PR description without any signoffs
- Report the PR URL back to the user.

---

## Guardrails

- Never push or open a PR without the Phase 6 confirmation.
- Never commit directly to `main`; keep the change on its own branch.
- Never fabricate test results; if a suite couldn't run, say so and why.
- If files can't be read (OneDrive dataless), stop and ask the user to hydrate
  them rather than guessing conventions.
