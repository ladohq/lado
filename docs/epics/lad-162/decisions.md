# Decisions: Git servers (LAD-162)

| Date | Where (step, gate) | Question | Options | Recommended (by whom) | Decided (by whom) | Taken? |
|---|---|---|---|---|---|---|
| 2026-11-15 | intake, #7064 | Create all five step tasks up front, with an epic branch? | tasks 1–5 with an epic branch; tasks 1–5 to main; task 1 only | tasks 1–5, epic branch (lead) | one task at a time, created when its step is reached; findings and leftovers go into the next step (human) | no |
| 2026-11-15 | intake, #7068 q1 | The epic's key | lad-162 | lad-162 (lead) | lad-162 (human) | yes |
| 2026-11-15 | intake, #7068 q2 | Branch strategy | each step into main; epic branch `epic/lad-162-git-servers` | into main (lead) | into main (human) | yes |
| 2026-11-15 | intake, #7068 q3 | Where the human checks on the company GitLab | Docker on a Mac over the company VPN; native | Docker on a Mac (lead) | Docker on a Mac (human) | yes |
| 2026-11-15 | intake, #7068 q4 | Documentation | each step documents itself, step 4 writes the plain guide; all in step 4 | each step plus the guide (lead) | as recommended (human) | yes |
| 2026-11-15 | intake, #7068 q5 | Removal and rollback | a removed server's host works as today; `GH_TOKEN` and `gh`'s login are kept on migration, so a rollback to 0.47 breaks nothing | as listed (lead) | as recommended (human) | yes |
| 2026-11-15 | intake, #7068 q6 | Step 5, kit sdlc's GitLab example (other repository) | in this epic; Later, task created on the human's yes after steps 1–3 | Later (lead) | Later (human) | yes |
