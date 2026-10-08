# CLAUDE.md

Read [`claude_instructions.md`](claude_instructions.md) before working in this repo, starting at §1a. It is the team's development spec: data model, API contracts, test cases, rules and open decisions.

## Team rules

- **Branches:** `<type>(SCRUM-<n>)Title-Case-Words`, e.g. `feat(SCRUM-45-47)Submit-Event-Request-Form`, cut from an up-to-date `main`.
- **Commits and PR titles:** `<type>(SCRUM-<n>): lowercase summary`, e.g. `feat(SCRUM-11): add event withdrawal flow`. Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. CI (`pr-title-check.yml`) rejects any other PR title.
- **Keep `claude_instructions.md` current:** every PR updates it for what the change did (status row, rules, schema/API, deviations) before merging to `main`.
- To implement a Jira ticket end to end, use the `/ship-ticket` skill.
