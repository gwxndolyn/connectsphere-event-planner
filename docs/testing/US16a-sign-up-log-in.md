# US16a — Sign up, log in and log out (SCRUM-81): test cases

**Story:** As a ConnectSphere user, I want to sign up or log in with my own account so that the system knows who I am and shows me my own work.

**Source of truth:** the acceptance criteria in Jira SCRUM-81, as updated on 12 Oct 2026, and its subtasks SCRUM-101 to SCRUM-106, which hold these test cases. If they disagree, Jira wins; fix this file.

**Acceptance criteria (short form):**

1. Log in from a single login page with email and password.
2. After logging in, land on the home screen for your role.
3. A wrong email or password shows "Email or password is incorrect", with no hint whether the email exists.
4. Stay logged in across a page refresh, until logging out or the session expiring.
5. After logging out, any protected page shows the login page.
6. Organisers and Attendees can sign up with name, email and password, choosing their role, confirm their email through the link sent to them, and can then log in. An email that already exists is refused. (Changed 16 Oct: email confirmation before first login.)
7. Staff accounts can't be created through sign-up; they're seeded. There's no System Administrator role.

**Test case ids 46 to 50** were added on 16 Oct (PR #55 review), and 51 on 20 Oct (SCRUM-105), after 01 to 45, so existing ids didn't move.

**Delivery:** one PR per subtask, in this order. The design follows `claude_instructions.md` §9.

| PR | Subtask | Scope | Tests |
| --- | --- | --- | --- |
| 1 | SCRUM-101 | `users.auth_user_id` + `users.full_name` (schema only) | `backend/tests/user/test_auth_link_schema.py` |
| 2 | SCRUM-102 | Verify the Supabase token in the identity dependency; dev header fallback behind `AUTH_DEV_HEADERS` | to be added |
| 3 | SCRUM-103 | `POST /api/v1/auth/profile` for sign-up | to be added |
| 4 | SCRUM-104 | Seed Supabase Auth logins for the seeded users | to be added |
| 5 | SCRUM-105 | Login page, logout, session handling; `GET /api/v1/me` | `backend/tests/user/test_me.py`; `e2e/tests/login.spec.ts` (login project, `VITE_DEV_AUTH` unset; logged-in cases need `E2E_SEED_PASSWORD`); lint, build |
| 6 | SCRUM-106 | Sign-up page | to be added (lint, build, Playwright) |

## Decisions agreed for this story

- **The header stubs stay as a dev and test fallback.** `X-User-Id` / `X-Attendee-Id` work only when `AUTH_DEV_HEADERS=true` (local dev, tests, CI E2E); the default is `false`, so production accepts tokens only (TC-US16A-14).
- **Sign-up refuses any email that already has a `users` row**, including unlinked seeded staff. Otherwise anyone could sign up as a seeded coordinator and gain that role (TC-US16A-21).
- **"Confirm email" is on** (changed 16 Oct, PR #55 review). Sign-up sends a confirmation link and gives no session until it's clicked; the profile is created at the first login after that (SCRUM-103, 106).
- **First login links by email only for an active Organiser or Attendee, and only when the token says the email is verified** (TC-US16A-06). Staff rows are linked by the seed instead (SCRUM-104).
- **A token that fails verification never falls back to the header stubs**, even when they're enabled (TC-US16A-15).
- **Identity on the profile endpoint comes from the token**, never the request body (TC-US16A-25).
- **New error codes:** `PROFILE_REQUIRED` (403, valid token but no profile), `INVALID_ROLE` (422, sign-up role not Organiser or Attendee), `EMAIL_ALREADY_REGISTERED` (409). Each is recorded as a deviation in §1a by the PR that adds it.
- **E2E sign-up tests delete the accounts they create**, so the shared Supabase project doesn't fill with test users. CI needs the Supabase keys as GitHub secrets: agree this with the team before SCRUM-106 merges.

## Test cases

| ID | AC | Given | When | Then | Subtask |
| --- | --- | --- | --- | --- | --- |
| TC-US16A-01 | Schema | A database at the previous head | `alembic upgrade head` | `users` has `auth_user_id` (uuid, nullable, unique) and `full_name` (text, nullable); existing rows are unchanged; one Alembic head | SCRUM-101 |
| TC-US16A-02 | Schema | Two users | Both are given the same `auth_user_id` | The second write fails on the unique constraint; any number of users can be unlinked | SCRUM-101 |
| TC-US16A-03 | Schema | A user with `auth_user_id` or `full_name` set | Downgrade one revision | Refused, rather than discarding account data; with nothing set, the columns are dropped | SCRUM-101 |
| TC-US16A-04 | Schema | The whole backend suite | Run after the migration | All existing tests pass unchanged | SCRUM-101 |
| TC-US16A-05 | 1 | A user linked by `auth_user_id` | A role route is called with their valid token | It runs as that user | SCRUM-102 |
| TC-US16A-06 | 1 | A seeded, active Organiser or Attendee with no `auth_user_id` | Their first valid token arrives (new `sub`, email matches ignoring case, email verified) | The row is linked to `sub`; later calls find it by `auth_user_id`. Not linked, row unchanged: email not verified → `401`; staff row → `401`; inactive row → `403 FORBIDDEN` | SCRUM-102 |
| TC-US16A-07 | 1 | A row already linked to a different `sub` | A token arrives with the same email but another `sub` | `401 UNAUTHENTICATED`; the link is unchanged | SCRUM-102 |
| TC-US16A-08 | 5 | Dev headers off | No `Authorization` header, or a malformed one (`Basic …`, `Bearer` with no token, a non-JWT) | `401 UNAUTHENTICATED` | SCRUM-102 |
| TC-US16A-09 | 4 | A token past its `exp` by more than 10 seconds | Any protected route | `401 UNAUTHENTICATED`; a token expired less than 10 seconds ago is still accepted (clock-drift leeway) | SCRUM-102 |
| TC-US16A-10 | 1 | A token signed by another key, or tampered | Any protected route | `401 UNAUTHENTICATED` | SCRUM-102 |
| TC-US16A-11 | 1 | A token with the wrong `aud` or `iss` | Any protected route | `401 UNAUTHENTICATED` | SCRUM-102 |
| TC-US16A-12 | 6 | A valid token whose `sub` and email match no `users` row | A role route | `403 PROFILE_REQUIRED` | SCRUM-102 |
| TC-US16A-13 | 1 | An inactive user with a valid token | A role route | `403 FORBIDDEN` | SCRUM-102 |
| TC-US16A-14 | 5 | Dev headers off | A request sends only the seeded coordinator's `X-User-Id` | `401 UNAUTHENTICATED`: headers can't impersonate anyone in production | SCRUM-102 |
| TC-US16A-15 | — | Dev headers on | The existing suite runs; header stubs are used | All existing tests pass unchanged. An invalid token with a valid `X-User-Id` is `401`: a bad token never falls back to the stub | SCRUM-102 |
| TC-US16A-16 | 1 | An attendee's valid token | `GET /api/v1/me/registrations` | It returns that attendee's registrations | SCRUM-102 |
| TC-US16A-17 | — | An organiser's valid token (no `attendees` row) | An attendee-only route | `401 UNAUTHENTICATED`, as today | SCRUM-102 |
| TC-US16A-18 | 6 | A valid token for a new account | Profile created as `organiser` with a name | `201` with `{id, email, full_name, role}`; a `users` row with role `organiser`, `full_name`, and `auth_user_id`/`email` from the token | SCRUM-103 |
| TC-US16A-19 | 6 | A valid token for a new account | Profile created as `attendee` | `201`; `users` and `attendees` rows share one id; `GET /me/registrations` returns empty sections | SCRUM-103 |
| TC-US16A-20 | 7 | A valid token | Role is `coordinator`, `operations_manager`, another staff role, or unknown | `422 INVALID_ROLE`; nothing is created | SCRUM-103 |
| TC-US16A-21 | 7 | The token's email belongs to an unlinked seeded staff row | Profile created as `organiser` | `409 EMAIL_ALREADY_REGISTERED`; the staff row is unchanged and not linked | SCRUM-103 |
| TC-US16A-22 | 6 | The token's email belongs to any existing `users` row | Profile created | `409 EMAIL_ALREADY_REGISTERED` | SCRUM-103 |
| TC-US16A-23 | 6 | A profile already exists for this `sub`, or a simultaneous call wins the race | The endpoint is called again | `409 EMAIL_ALREADY_REGISTERED`; still one row | SCRUM-103 |
| TC-US16A-24 | 6 | A valid token | `full_name` and/or `role` missing or blank | `422 MISSING_REQUIRED_FIELD` listing each missing field; nothing is created | SCRUM-103 |
| TC-US16A-25 | 6 | The body includes `email` or `auth_user_id` | Profile created | `422`; identity can't be set from the body | SCRUM-103 |
| TC-US16A-26 | 6 | No token, an invalid one, or one whose email isn't verified | Profile created | `401 UNAUTHENTICATED`; nothing is created | SCRUM-103 |
| TC-US16A-27 | 7 | Secret key and password set | Seed runs | One confirmed auth account per seeded user; each `users` row gets its `auth_user_id` | SCRUM-104 |
| TC-US16A-28 | 7 | Auth accounts already exist | Seed runs again | Accounts the seed created (marked, confirmed) found by email and reused; no duplicates; links unchanged. An account the seed didn't create, or an unconfirmed one, is refused; a row linked to a different account is never re-pointed | SCRUM-104 |
| TC-US16A-29 | — | No URL, secret key or password; or a password under 12 characters | Seed runs | Missing: seeds as today; output says logins were skipped and names what's missing. Too short: refused, nothing linked | SCRUM-104 |
| TC-US16A-30 | — | Secret key set | Seed runs | Neither the secret key nor the password appears in the output | SCRUM-104 |
| TC-US16A-31 | — | The Admin API errors, times out or replies badly for one user | Seed runs | Stops with a message naming that email and exits 1; no half-linked row | SCRUM-104 |
| TC-US16A-32 | 1, 2 | The seeded organiser's email and password | Logs in | Lands on Event requests | SCRUM-105 |
| TC-US16A-33 | 2 | The seeded coordinator; a seeded attendee | Each logs in | Coordinator lands on the review queue; attendee on the events board | SCRUM-105 |
| TC-US16A-34 | 3 | A wrong password; an email with no account | Each is submitted | Both show exactly "Email or password is incorrect" | SCRUM-105 |
| TC-US16A-35 | 4 | Logged in | The page is refreshed | Still logged in, on the same screen | SCRUM-105 |
| TC-US16A-36 | 5 | Logged in | Logs out, then opens My events or Event requests | The login page is shown | SCRUM-105 |
| TC-US16A-37 | 5 | Not logged in | Opens any protected screen directly | The login page is shown | SCRUM-105 |
| TC-US16A-38 | — | `VITE_DEV_AUTH` unset | The app loads, then a user logs in | No **Acting as** switch, before or after logging in | SCRUM-105 |
| TC-US16A-39 | — | Logged in | Any API call | Carries `Authorization: Bearer …` and no `X-User-Id` / `X-Attendee-Id` | SCRUM-105 |
| TC-US16A-40 | 6 | A new email | Signs up as Attendee, confirms the email, logs in | First login creates the profile; lands on the events board; My events shows the empty state | SCRUM-106 |
| TC-US16A-41 | 6 | A new email | Signs up as Organiser, confirms the email, logs in | First login creates the profile; lands on Event requests | SCRUM-106 |
| TC-US16A-42 | 7 | The sign-up page | The role choice is opened | Only Organiser and Attendee are offered | SCRUM-106 |
| TC-US16A-43 | 6 | A seeded email (e.g. a staff account) | Sign-up is submitted | Refused; no account is created and nobody is logged in | SCRUM-106 |
| TC-US16A-44 | 6 | Name, email or password missing, or password under 6 characters | Sign-up is submitted | Inline field errors; no request sent | SCRUM-106 |
| TC-US16A-45 | 1, 6 | A user who signed up and confirmed | Logs out, then logs in again | Same account and role | SCRUM-106 |
| TC-US16A-46 | — | Supabase's public keys can't be fetched | A token arrives | `503 AUTH_UNAVAILABLE`, not `401`; a warning is logged | SCRUM-102 |
| TC-US16A-47 | — | `SUPABASE_URL` is not set | A token arrives | `500 AUTH_NOT_CONFIGURED`; an error is logged | SCRUM-102 |
| TC-US16A-48 | — | `AUTH_DEV_HEADERS=true` | The backend starts | A warning is logged that the header stubs bypass login | SCRUM-102 |
| TC-US16A-49 | — | Any token is refused (401) | The refusal happens | A warning names the reason; the token never appears in the log | SCRUM-102 |
| TC-US16A-50 | 6 | A new email | Signs up | Sees "Check your email to confirm your account"; not logged in until the link is clicked | SCRUM-106 |
| TC-US16A-51 | 2 | A valid token | `GET /api/v1/me` | `200 {id, email, full_name, role}` for a user with a profile (`full_name` null until a name is set); `403 PROFILE_REQUIRED` without one; `403 FORBIDDEN` for a deactivated user; `401` without a token | SCRUM-105 |

## Run log

### 24 Oct 2026: SCRUM-105 login E2E with real logins (PR #62)

Setup: local Postgres at `alembic` head, seeded from #56's branch (SCRUM-104) with `SEED_AUTH_PASSWORD`, which
created and linked nine Supabase logins. Backend from #62 with `SUPABASE_URL` set; Playwright `login` project
with `E2E_SEED_PASSWORD`.

| Test case | Result | Note |
| --- | --- | --- |
| TC-US16A-32 | Pass | Organiser lands on "My event requests" |
| TC-US16A-33 | Pass | Coordinator on "Requests to review"; attendee on the events board |
| TC-US16A-34 | Pass | Wrong password and unknown email |
| TC-US16A-35 | Pass | Refresh keeps the login and My events |
| TC-US16A-36 | Pass | Log out, then reload: login page |
| TC-US16A-37 | Pass | No login: login page |
| TC-US16A-38 | Pass | Checks the login page only, so it passes either way (PR #62 review, point 5) |
| TC-US16A-39 | Pass | Bearer token, no dev headers |

- **First run: TC-32, 33, 35 and 36 failed.** The backend's CORS list allowed only `localhost:5173`, so the browser
  blocked `GET /api/v1/me` from the login frontend on `:5174`. Fixed by adding `:5174` to the default `CORS_ORIGINS`.
- **Staff screens with a real login (PR #62 review, point 1):** the organiser, coordinator, Coordinator Lead and venue
  staff each land on their home screen, but every one gets `401` from `GET /api/v1/me/registrations` and
  `GET /api/v1/events/available` straight after logging in, and My events shows "Set VITE_DEV_ATTENDEE_ID in
  frontend/.env…". The attendee has no failed calls.
- **Fixed the same day:** each logged-in role now gets only its own screens (`frontend/src/auth/screens.ts`), and the
  attendee lists load only for attendees. TC-US16A-32 and 33 now also check there are no attendee links or failed
  calls for staff and no staff links for the attendee. Rerun: login project 8 of 8, full E2E suite 30 of 30.

### 24 Oct 2026: PR #62 review notes

- TC-US16A-38 now also checks there's no **Acting as** switch once logged in; the old check alone couldn't fail.
- TC-US16A-51 has a deactivated-user case (`403 FORBIDDEN`), which the frontend now names in its own message.
- Login errors other than wrong details (unconfirmed email, 429, no connection) get their own message; unit tests in
  `frontend/src/auth/messages.test.ts`. Log out is `scope: "local"`.
- A role the frontend doesn't know yet (e.g. `tech_support` from US16b) gets "Your account's role doesn't have any
  screens yet" and Log out instead of a broken page; unit tests in `frontend/src/auth/screens.test.ts`.
- Rerun: backend 526, frontend 208, login project 9 of 9, full E2E suite 31 of 31.

### 24 Oct 2026: SCRUM-106 sign-up with real Supabase

Setup: local Postgres seeded from `main`; backend checking real tokens; Playwright `login` project with `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Supabase as in `claude_instructions.md` §9 (Confirm email on, Gmail SMTP, Site URL `http://localhost:5173`).

| Test case | Result | Note |
| --- | --- | --- |
| TC-US16A-40 | Pass | Attendee signs up, confirmed through the Admin API, first login creates the profile, lands on the events board; My events is empty |
| TC-US16A-41 | Pass | Organiser lands on "My event requests" |
| TC-US16A-42 | Pass | Unit: only the two radios, and metadata never yields a staff role |
| TC-US16A-43 | Pass | `event.coordinator@smu.edu.sg` refused; the existing Supabase account is unchanged |
| TC-US16A-44 | Pass | Unit: field errors, nothing sent |
| TC-US16A-45 | Pass | Log out and back in: same account and home screen |
| TC-US16A-50 | Pass | "Check your email to confirm your account", not logged in, account unconfirmed until confirmed |

- The test accounts are deleted from Supabase after each run; their profile rows stay in the local database (harmless: unique emails, and CI starts fresh).
- Full E2E suite: 34 of 34. Frontend: 225 tests, lint and build clean.
- An Admin-API-confirmed account's token carries `user_metadata.email_verified: true`, which the profile endpoint requires; checked before writing the E2E.
