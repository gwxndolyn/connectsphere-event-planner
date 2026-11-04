# ConnectSphere — C4 model (as built, Release 1)

This is the C4 model of the system **as it is implemented on `main`**. It supersedes the stack
named in the High Level Design v0.5 (Next.js Server Actions on Vercel): during Sprint 1 the team
switched the scaffold to a **FastAPI backend + React/Vite SPA** (commit `d521b6e`, "Switch scaffold to
FastAPI/Postgres backend and TS frontend"). Supabase stayed as the database and identity provider.
The responsibilities, design rules and Week 7 change traceability in the HLD still hold; only the
technology of the containers changed. See [Design decisions](#design-decisions-and-trade-offs).

Diagrams are Mermaid, so they render directly on GitHub.

## Level 1 — System context

```mermaid
flowchart TB
    subgraph External["External users"]
        ORG["Event Organiser<br/><i>submits and tracks event requests</i>"]
        ATT["Attendee<br/><i>registers for events</i>"]
    end
    subgraph Internal["ConnectSphere staff"]
        LEAD["Event Coordinator Lead<br/><i>assigns / reassigns coordinators</i>"]
        COORD["Event Coordinator<br/><i>reviews, plans, books, confirms</i>"]
        VS["Venue Staff<br/><i>venues, bookings, holds, unavailability</i>"]
        TS["Technical Support Staff<br/><i>equipment checks and reservations</i>"]
        SO["Safety Officer<br/><i>operational safety review</i>"]
    end
    CS(["<b>ConnectSphere Event Planner</b><br/>Event requests, venue booking, equipment,<br/>registration and in-app notifications"])
    AUTH[["Supabase Auth<br/><i>external identity provider</i>"]]
    MAIL[["Email / SMS provider<br/><i>out of scope for Release 1</i>"]]

    ORG --> CS
    ATT --> CS
    LEAD --> CS
    COORD --> CS
    VS --> CS
    TS --> CS
    SO --> CS
    CS -- "verifies JWTs (JWKS)" --> AUTH
    CS -. "not used in R1 (notifications are in-app)" .-> MAIL
```

## Level 2 — Containers

```mermaid
flowchart LR
    U(("User<br/>browser"))
    subgraph CS["ConnectSphere"]
        SPA["<b>Web SPA</b><br/>React 19 + TypeScript, Vite<br/><i>frontend/</i><br/>Role screens and forms. No business rules."]
        API["<b>REST API</b><br/>Python 3.12, FastAPI, SQLAlchemy 2<br/><i>backend/app</i><br/>Validates input, checks role + relationship<br/>to the event, applies all workflow rules,<br/>writes audit entries and notifications."]
        DB[("<b>Database</b><br/>PostgreSQL 16 (Supabase)<br/>Alembic migrations, RLS enabled<br/><i>backend/migrations</i>")]
    end
    SA[["Supabase Auth"]]

    U -- "HTTPS" --> SPA
    SPA -- "JSON/HTTPS, Bearer JWT<br/>(X-User-Id stub in dev/E2E only)" --> API
    SPA -- "sign-up / log-in<br/>(supabase-js)" --> SA
    API -- "verify token signature (JWKS)" --> SA
    API -- "SQL over psycopg 3<br/>(server-side only)" --> DB
```

| Container | Technology | Responsibility |
| --- | --- | --- |
| Web SPA | React 19, TypeScript, Vite, supabase-js | One screen set per role, chosen from the user's roles. Calls only the REST API (plus Supabase Auth for the session). Holds no business rules. |
| REST API | FastAPI, Pydantic v2, SQLAlchemy 2, PyJWT | Single entry point for every read and change. Every route resolves the caller, checks role **and** relationship to the event, then calls a domain service. |
| Database | PostgreSQL 16 on Supabase (Docker Postgres locally and in CI) | All persistent state. Schema owned by Alembic; RLS is on and the browser never talks to the database directly (SCRUM-118 grants). |
| Supabase Auth | Managed | Sign-up, log-in, sessions; issues the JWT the API verifies. |

## Level 3 — Components of the REST API

```mermaid
flowchart LR
    R["<b>Routers</b> (HTTP layer)<br/>event · request · edit · change_decision<br/>venue · booking · equipment<br/>registration · roster · safety<br/>agenda · notification · user<br/><i>*/router.py</i>"]
    ACC["<b>Access policy</b><br/>get_current_user,<br/>require_user_roles,<br/>coordinator scoping<br/><i>user/dependencies.py, auth.py</i>"]
    subgraph EV["Event workflow — app/event"]
        S_REQ["Requests, decisions,<br/>clarifications"]
        S_ASG["Coordinator<br/>assignment"]
        S_EDIT["Edits + change<br/>requests/decisions"]
        S_CONF["Confirmation,<br/>completion, cancellation"]
        S_IMP["<b>Change impact</b><br/>review_flag_service"]
    end
    subgraph VN["Venues — app/venue"]
        S_VEN["Catalogue, search,<br/>calendar, blocks"]
        S_BOOK["Bookings, holds,<br/>primary venue"]
        S_AV["<b>Availability rules</b><br/>start−setup … end+turnaround<br/><i>availability.py</i>"]
    end
    subgraph OT["Other domains"]
        S_EQ["Equipment + tech staff<br/><i>app/equipment</i>"]
        S_REG["Registration + waitlist<br/><i>app/registration</i>"]
        S_SAF["Safety check<br/><i>app/safety</i>"]
        S_AG["Agenda<br/><i>app/agenda</i>"]
    end
    NOTI["<b>Notifier</b><br/>recorder.py → notifications<br/>(protocol, swappable)"]
    CLK["Clock<br/>core/clock.py"]
    ORM["SQLAlchemy models + Session<br/>*/models.py, core/database.py"]
    DB[("PostgreSQL")]

    R --> ACC
    R --> EV
    R --> VN
    R --> OT
    S_EDIT --> S_IMP
    S_SAF --> S_IMP
    S_CONF --> S_BOOK
    S_CONF --> S_EQ
    S_VEN --> S_AV
    S_BOOK --> S_AV
    EV --> NOTI
    VN --> NOTI
    OT --> NOTI
    EV --> ORM
    VN --> ORM
    OT --> ORM
    EV -.-> CLK
    NOTI --> ORM
    ORM --> DB
```

### Design rules visible in this view

1. **Every change goes through a router that calls the access policy first.** Coordinators see only
   events assigned to them; the Lead sees all assignments (US16b).
2. **One availability rule.** `venue/availability.py` is the only place that applies setup and
   turnaround time, so search, booking, holds, approval and the calendar always agree (CR-01, US13).
3. **Flag, never silently delete.** When an event edit, a venue unavailability or a safety outcome
   affects existing arrangements, `review_flag_service` / `block_service` flag the bookings and
   reservations for review (CR-02, US12, US23a, US29b).
4. **Services raise `DomainError`; routers never build error responses by hand** (`core/exceptions.py`).
5. **Notifications are written by services through the `Notifier` protocol**, never by the UI.
   Tests inject a recording notifier and assert on the calls.
6. **Time is injected** (`core/clock.py`), so hold expiry and waitlist-offer expiry ("lapse on read")
   are deterministic in tests without a scheduler.
7. **Row locking for races.** Approve, cancel, replacement and primary-venue changes lock rows in a
   fixed order (`SELECT … FOR UPDATE`); race tests prove it (`test_*_race.py`).

## Level 4 — Data model (key tables)

```mermaid
flowchart TB
    USERS[("users<br/>roles[]")] -- "organises / coordinates" --> EVENTS[("<b>events</b><br/>status, dates, capacity,<br/>registration flags")]
    USERS -- receives --> NOTIF[("notifications")]
    subgraph Workflow["Request and planning workflow"]
        direction LR
        CA[("coordinator_<br/>assignments")]
        CL[("event_request_<br/>clarifications")]
        CR[("event_change_<br/>requests")]
        AU[("event_audit_<br/>entries")]
        RF[("event_review_<br/>flags")]
        EC[("event_<br/>cancellations")]
        SR[("safety_<br/>reviews")]
        SE[("event_<br/>sessions")]
    end
    subgraph Venue["Venues"]
        direction LR
        VB[("venue_bookings<br/>purpose, is_primary")]
        V[("venues<br/>setup / turnaround")]
        BL[("venue_blocks")]
    end
    subgraph Equip["Equipment"]
        direction LR
        EL[("equipment_<br/>request_lines")]
        ET[("equipment_<br/>types")]
        ER[("equipment_<br/>reservations")]
        TS[("tech_staff_<br/>assignments")]
    end
    subgraph Reg["Registration"]
        direction LR
        RG[("registrations")]
        RA[("registration_<br/>answers")]
        AL[("attendance_<br/>log")]
    end
    EVENTS --> Workflow
    EVENTS -- "1 : n" --> VB
    V -- "1 : n" --> VB
    V -- "1 : n" --> BL
    EVENTS -- "1 : n" --> EL
    ET --> EL
    EL -- "1 : 0..1" --> ER
    EVENTS --> TS
    EVENTS -- "1 : n" --> RG
    RG --> RA
    RG --> AL
```

Full column-level definitions: [`claude_instructions.md` §2](../../claude_instructions.md#2-data-model-supabase--postgres).

## Event status lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> submitted: organiser submits (US1)
    submitted --> under_review: Lead assigns a coordinator (US10a)
    under_review --> awaiting_clarification: coordinator asks (US8a/d)
    awaiting_clarification --> under_review: organiser responds (US8c)
    under_review --> rejected: coordinator rejects (US17)
    under_review --> approved: coordinator approves (US17)
    approved --> confirmed: readiness complete incl. safety approval (US18, US30a)
    planning --> confirmed: readiness complete again (US18)
    confirmed --> planning: significant change approved (US29b) / venue unavailable (US23a)
    confirmed --> preparation: start preparation, safety approved (US18 AC 6)
    preparation --> completed: event has ended (D119)
    approved --> cancelled: US9
    planning --> cancelled: US9
    confirmed --> cancelled: US9
    preparation --> cancelled: US9
    rejected --> [*]
    cancelled --> [*]
    completed --> [*]
```

> Every transition above is a line in a service under `backend/app/event/` or `backend/app/venue/block_service.py`
> (search for `event.status = EventStatus.`). The Safety Officer's decision is a **gate in the readiness list**,
> not a status of its own: a rejection or "request changes" (US30a/b) keeps the event where it is and blocks
> confirmation until the coordinator revises the arrangement.

## Design decisions and trade-offs

| Decision | Alternatives considered | Why |
| --- | --- | --- |
| FastAPI + React SPA instead of the HLD's Next.js Server Actions | Next.js full-stack on Vercel | The team's strongest language was Python; pytest + a real Postgres gave fast, trustworthy integration tests of business rules; clean HTTP contract between SPA and API made frontend work parallel (MSW mocks the API in Vitest). Cost: two deployables instead of one. |
| Business rules only in the API; RLS as a second line | Rules in Postgres (RLS/policies) or in the UI | Rules are testable in Python, one place to change; RLS still blocks direct table access with the public key (SCRUM-118). |
| A single `availability.py` rule | Each feature computing its own overlaps | CR-01 (buffers) touched search, booking, approval, holds and calendar — one rule meant one change. |
| "Lapse on read" for holds and waitlist offers instead of a scheduler | Cron / background worker | No scheduler is available on the chosen hosting; computing expiry when the record is read is deterministic and testable via the injected clock. Trade-off: no proactive "about to expire" push unless a user opens the app. |
| In-app notifications table behind a `Notifier` protocol | Email/SMS now | Customer confirmed email/SMS is out of scope for R1; the protocol lets a real provider be added without touching services. |
| Flag affected arrangements rather than auto-cancel | Automatic cancellation/rebooking | Customer clarification: changes must not silently remove bookings; a human decides (CR-02, US12, US29b). |
| Pessimistic row locks for approve / cancel / replace | Optimistic versioning | Collisions are rare but costly (double booking); locks in a fixed order are simpler to reason about and are covered by race tests. |
