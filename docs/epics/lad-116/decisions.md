# Decisions: Projects in LADO (LAD-116)

| Date | Where (step, gate) | Question | Options | Recommended (by whom) | Decided (by whom) | Taken? |
|---|---|---|---|---|---|---|
| 2026-10-21 | intake, round 1 (D1) | The epic's key and tracker task | create an epic task in Yougile and use its key; no task, key `projects` | create the task (lead) | create the task — LAD-116, key `lad-116` (human) | yes |
| 2026-10-21 | intake, round 1 (D2) | Branch strategy | every phase merges into `main`; an epic branch | every phase into `main`, leaving the product working (lead) | every phase into `main` (human) | yes |
| 2026-10-21 | intake, round 1 (D3) | The workspace without `LADO_REPOS` | `~/workspace`, also the default clone parent of sessions without a project (today `~/lado`); keep `~/lado` and call it the workspace | `~/workspace` for both; existing sessions keep their folders, CHANGELOG says so (lead) | `~/workspace` (human) | yes |
| 2026-10-21 | intake, round 1 (D4) | A release between phases | allowed, each phase complete, UI stub until phase 4, no feature flag; no release until phase 4 | allowed (lead) | allowed (human) | yes |
| 2026-10-21 | intake, round 1 (D5) | Checks on real CLIs | a smoke test per provider in CI that a kit's MCP server sees a project variable, plus one live check with models before the release that ships phase 2 (Claude only with the human's yes); integration tests only | smoke per provider + one live check (lead) | as recommended (human) | yes |
