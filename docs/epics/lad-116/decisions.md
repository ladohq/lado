# Decisions: Projects in LADO (LAD-116)

| Date | Where (step, gate) | Question | Options | Recommended (by whom) | Decided (by whom) | Taken? |
|---|---|---|---|---|---|---|
| 2026-10-21 | intake, round 1 (D1) | The epic's key and tracker task | create an epic task in Yougile and use its key; no task, key `projects` | create the task (lead) | create the task — LAD-116, key `lad-116` (human) | yes |
| 2026-10-21 | intake, round 1 (D2) | Branch strategy | every phase merges into `main`; an epic branch | every phase into `main`, leaving the product working (lead) | every phase into `main` (human) | yes |
| 2026-10-21 | intake, round 1 (D3) | The workspace without `LADO_REPOS` | `~/workspace`, also the default clone parent of sessions without a project (today `~/lado`); keep `~/lado` and call it the workspace | `~/workspace` for both; existing sessions keep their folders, CHANGELOG says so (lead) | `~/workspace` (human) | yes |
| 2026-10-21 | intake, round 1 (D4) | A release between phases | allowed, each phase complete, UI stub until phase 4, no feature flag; no release until phase 4 | allowed (lead) | allowed (human) | yes |
| 2026-10-21 | intake, round 1 (D5) | Checks on real CLIs | a smoke test per provider in CI that a kit's MCP server sees a project variable, plus one live check with models before the release that ships phase 2 (Claude only with the human's yes); integration tests only | smoke per provider + one live check (lead) | as recommended (human) | yes |
| 2026-10-21 | plan, critic P4 | Is there a kit key check before an agent starts? | none (critic); `kits.ResolvedAgent.mcp_servers` refuses before launch (lead) | the check exists, S5a feeds it the project layer (lead) | the critic withdrew P4 on the code (`kits.py:257–276`, `runtime.py:2714`) | yes |
| 2026-10-21 | plan_ok, gate #33 (Q1) | S3 (session in a project) before S5a/S5b (variables), against the concept's phase order | S3 first; concept order | S3 first (lead) | approved as recommended (human) | yes |
| 2026-10-21 | plan_ok, gate #33 (Q2) | Compose's `LADO_PROJECTS` | (a) step S2b adds `LADO_WORKSPACE`, old name kept; (b) keep the name, change the message | (a), as S2b (lead) | approved as recommended (human) | yes |
| 2026-10-21 | plan_ok, gate #33 (Q3) | `~/workspace` without `LADO_REPOS` | LADO makes it on first need, doctor says "not made yet", Where hints once it exists | as described (lead) | approved as recommended (human) | yes |
| 2026-10-21 | plan_ok, gate #33 (Q4) | Split S5 | S5a plain variables + S5b secrets; one step | split (lead) | approved as recommended (human) | yes |
| 2026-10-21 | plan_ok, gate #33 | The plan and the first step S1 | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | run (S1 in work), human's remark #523 | Warnings and refusals in the New session window are small and grey, users do not take them seriously | a separate tweak task after S1; an epic step between S1 and S2; not now | a separate task after S1 (lead) | an epic step between S1 and S2 — S1b (human) | no |
