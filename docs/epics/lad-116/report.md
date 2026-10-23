# Readiness report: Projects in LADO (LAD-116)

Checked 2026-10-23 by `delivery`, first visit, on `origin/main` at d467359c (no epic
branch: every step merged into `main` on its own, D2). Previous release: v0.42.0.

## Verdict

**Gaps: 1.** The code is ready (every step done, checks and CI green, the upgrade from
0.42.0 keeps the user's state), but the documents are not true to it yet:

- **G1 — documents still say projects are not built.** `ROADMAP.md:144-152` leaves S2,
  S3, S4, S5a, S5b, S6 and S7 unchecked and the Projects item open; `AGENTS.md:193-194`
  says projects are "mostly not built yet"; `docs/design/projects.md:98-99` says "the UI's
  addresses are not built yet (step S6)"; `docs/design/ui.md:1842-1844` says a session in a
  project is "not built yet" and "decided with a mockup at S3". The brief's "done" asks
  that the docs describe the new model; the readiness topic Documentation is not met.
  A small docs step (patch-sized, under 0.43.0) closes it; see Questions for the human for
  one more line it could carry.

Nothing else is a gap. Open checks are all in the release checklist (`docs/release.md`),
one added by this report (Open checks).

## Results of all steps

| Step | Task | Pull request | Check | Evidence |
|---|---|---|---|---|
| S1 — docs rewrite, rename to Workspace | LAD-117 | #126 (6c2336e) | grep of old names, places rewritten, BACKLOG entry, checks, the human reads `projects.md` at merge | plan.md S1 Result: CI 23/23, `make test` 3614; one merge_ok rejection (F1) fixed |
| S1b — warnings and refusals stand out | LAD-120 | #128 (0fadd64) | mockup, UI e2e of three levels | plan.md S1b Result; tokens with contrast ≥ 5.4:1 |
| S2 — project in the core, `~/workspace` | LAD-123 | #131 (e943d5a) | integration of `lado project`, doctor lines, D3, migration (schema 32) | plan.md S2 Result: `make test` 3685, CI 23/23, lead's manual check |
| S2b — compose's `LADO_WORKSPACE` | LAD-124 | #136 (f99ebb7) | `tests/test_docker.py`, container tests on CI | plan.md S2b Result: CI 23/23 incl. container amd64/arm64; Docker Desktop's text open → `docs/release.md` 4.5 |
| S3 — a session in a project | LAD-125 | #138 (853ba87) | integration with the fake agent, refusals on every start path, UI head | plan.md S3 Result: schema 33, CI 23/23, lead's manual check |
| S4 — a project's repositories | LAD-128 | #141 (f466b90) | integration of `repo add/remove` | plan.md S4 Result: `make test` 3869, CI 23/23, X1 fixed, lead's manual check |
| S5a — plain variables | LAD-130 | #144 (d11c543) | integration of layers in two projects, kit keys, smoke probe per provider | plan.md S5a Result: schema 34, `make test` 3954, CI 23/23; live run open → 4.3 "Projects" |
| S5b — secrets | LAD-132 | #148 (63627cbb) | files 700/600, doctor, delete, canary integration test | plan.md S5b Result: `make test` 4110, CI green incl. smoke Linux/macOS; macOS link refusals open → 4.3 |
| S6a — UI Projects section, variables, secrets | LAD-134 | #151 (be6f9bb4) | mockups, UI e2e, canary over API and feed | plan.md S6a Result: CI 23/23; password managers open → 4.3 "Projects in the web UI" |
| S6b — New session's Project way | LAD-137 | #155 (f8b4a0c9) | mockup, UI e2e of the start in a project | plan.md S6b Result: CI 23/23, lead's manual check with the fake provider |
| S7a — project page, repositories, rename | LAD-138 | #157 (c0b17375) | mockups, UI e2e | plan.md S7a Result: `make test` 4204, vitest 1089, CI green |
| S7b — deleting the project | LAD-139 | #159 (d467359c) | mockup, UI e2e, core and server tests, canary over the delete | plan.md S7b Result: `make test` 4235, vitest 1104, CI 23/23 |

All twelve steps are done; no step is planned, in progress or dropped.

### The product's checks on what will be released (`origin/main`, d467359c)

| Command | Result |
|---|---|
| `make lint` | exit 0: 881 files already formatted, `All checks passed!` |
| `make test` | exit 0: **4235 passed, 2 skipped** in 39.8 s (the first run stopped at collection on a truncated `.pyc` of `tests/test_error_journal.py`, `EOFError: marshal data too short`, written by a concurrent run in the shared worktree; the rerun passed: outside the work) |
| `make web` | exit 0: stale-types check, tsc, vitest **59 files, 1104 tests passed**, build |
| `openspec validate --specs --strict` | exit 0: **47 passed, 0 failed** |
| CI on the push of d467359c to `main` (run 40028483018) | **success, 23/23 jobs** (lint, unit and integration on 3.10 and 3.13, Node, `make dist`, UI e2e, smoke, container) |

Integration and UI tests as a whole were not run locally (settings, Checks: CI runs
them on every push); CI's run above is their evidence.

## Checked by hand

| Step | Checked by hand | By whom |
|---|---|---|
| S1 | `docs/design/projects.md` read against the concept at merge_ok (gates #35, #37) | the human |
| S1b, S3, S6a, S6b, S7a, S7b | mockups approved at design_ok | the human |
| S2 | temp HOME on acbe045: workspace, doctor lines, create/delete | the lead |
| S3 | on 853ba87: `project show`, refusals of a folder and `--new` under `projects/`, unknown `--repo`, delete without `--yes` | the lead |
| S4 | on f466b90: clone from `file://` and `--new`, taken name, remove with unpushed branch, link removed as link | the lead |
| S5a | on d11c543: set in two projects, show, unset, refusals (`GH_TOKEN`, `MONKEY_MODE`, `PATH`, `LADO_FOO`, inside an agent) | the lead |
| S5b | on 63627cbb: secret from stdin 600/700, refusals, `show` names only, doctor names a 644 file, canary after unset | the lead |
| S6a | API and Chromium: create, 401 without token, value in no DOM, storage, URL or log, phone layout | the lead |
| S6b | fake provider, Chromium: start in Acme gets Acme's `BOARD_URL` and not Shop's `GH_TOKEN`; Folder refusal leads into Project | the lead |
| S7a | fake provider, Chromium: repositories, rename, Add by clone with Cancel, delete pushed/unpushed/running | the lead |
| S7b | fake provider, Chromium and CLI: refusal while running, three lists, id typed, both folders gone, link target kept | the lead |
| readiness | the upgrade from 0.42.0 below | `delivery` |

**Never checked by hand** (all in the release checklist, Open checks): a real agent CLI
with a project variable or secret (all hand checks used the fake provider or no agent);
`gh auth status` with a project secret; Docker Desktop's refusal for a missing workspace;
a project in LADO's image; the secrets' link refusals on macOS; the secret field with a
password manager in Chrome and Safari.

## Upgrade from 0.42.0

Done in `/tmp/lado-upgrade-u7Gh` (removed by name afterwards): `uv tool install
lado==0.42.0` from PyPI with `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` in that folder, `HOME`,
`LADO_HOME` and the tmux socket (`lado-upg-u7Gh`) of its own, `LADO_TELEMETRY=0`,
`LADO_REPOS` and `LADO_CONTAINER` unset (as on a computer), `LADO_ENV_DIR` a folder with
`BOARD_URL=outside`. The new build is a wheel of d467359c (`uv build --wheel` after `make
web`). The upgrade is the docs' "Installed otherwise" path (`docs/install.md`, Update):
stop the sessions, install the new build over the old (`uv tool install --force
--reinstall <wheel>`), start them again; `lado update` itself installs only from PyPI, so
it could not take an unreleased build. Real agent CLIs started, waiting at their trust
question; no model was called.

State made on 0.42.0: schema 31; session `app` on a repository in `src/`, session
`remote` cloned from a `file://` URL into the old default `~/lado/remote`, session
`mine` in `~/workspace/projects/mine` (a user's own folder named `projects`).

| What | Result |
|---|---|
| Migration | first command: `lado: upgraded lado.db from schema 31 to 35; its backup is …/backups/lado.db.schema-31` |
| Old sessions | `lado ls` lists all three (stopped); `lado start <folder>` resumes each under its old name; `remote` in `~/lado` works (CHANGELOG: "sessions in `~/lado` keep working") |
| Workspace without `LADO_REPOS` | `lado doctor`: `Workspace: ~/workspace (default)` |
| A user's own `~/workspace/projects/` | `[warn] Projects: … is your own folder (it holds mine): LADO cannot make projects there`; `lado project create shop` refuses naming the way out; the session `mine` there still resumes — loud, nothing changed or removed |
| Outside variables | doctor `Variables from outside: …: BOARD_URL`, unchanged |
| A project after the upgrade (folder moved away) | `create`, `repo add --new`, `set`, `set --secret` from a pipe, `show` (secret by name only); `lado start --project shop --repo app2` → session `shop-app2`, `lado ls` says `project shop`; its agent process has `BOARD_URL=https://project` and `GH_TOKEN`, session `app` without a project has `BOARD_URL=outside` |
| Going back to 0.42.0 | 0.42.0 refuses schema 35 by name (`made by a newer LADO … knows up to 31`); with the backup put back (as `lado update`'s rollback does) it works, sessions listed, the project unknown, `projects/shop` and `~/.lado/projects/shop/` left on disk (the brief, Data and migrations) |
| Up again on the restored database | migrates 31 → 35 again; doctor: `projects/` is "your own folder (it holds shop)"; after moving it away, `lado project create shop` refuses: `…/.lado/projects/shop is left from a project shop: remove it or choose another id` — the old secret is not taken over silently |
| `lado uninstall --yes` (new build) | deleted `LADO_HOME` with the secrets, removed the program, left `~/workspace` and its folders |

Nothing was lost or silently changed. Not run here: **the image's upgrade** (`LADO_PROJECTS`
→ `LADO_WORKSPACE` in an installed `.env`, the home volume's migration): there is no
Docker in LADO's container. The human runs `docs/release.md` 4.6 (the image's update from
the last final, with `LADO_PROJECTS` on purpose) and 4.5; CI's container tests
(`tests/container/test_migration.py`, `tests/test_docker.py`) cover the old `.env` and the
volume migration on Linux. `lado update` from PyPI is checked by 4.2 on the RC.

## Missing

Against the brief's "done":

| "Done" item | Covered by |
|---|---|
| docs describe the new model only | S1, kept by each step — **except G1** (four stale places) |
| `lado project list/create/show/rename/delete/set/unset`, `--project --repo`, doctor, `lado ls`, the head | S2, S3, S5a, S5b; seen in the upgrade above |
| two projects, different values, four CLIs, with and without Docker, kit keys | S5a integration (two projects) and smoke per provider; live four CLIs → 4.3; in the image → 4.5 (added now) |
| the canary test | S5b, extended in S6a, S6b, S7b |
| UI: Projects, page, variables, Project way, removal with unpushed work, token API | S6a, S6b, S7a, S7b |

Readiness checklist:

| Topic | Verdict |
|---|---|
| Goal and "done" | covered (above) |
| Users and how they use it | covered: CLI (S2–S5b), UI (S6a–S7b), API documented in OpenAPI |
| Scope and what is out | covered: concept "Не сейчас" in `docs/design/projects.md`; Later below |
| Data and migrations | covered: schema 31 → 35 (S2, S3, S5a), seen above; rollback restores `lado.db` |
| Secrets and credentials | covered: S5b files 700/600, write-only, canary; agents cannot change projects |
| Update and rollback | covered: upgrade and going back above; image update → 4.6 |
| Removal | covered: S4, S7a (repository), S2/S7b (project), `lado uninstall` above |
| Platforms | covered: four CLIs by smoke on Linux and macOS (CI); live → 4.3; macOS links → 4.3; image → 4.5 |
| Observability | covered: doctor lines (workspace, own `projects/`, foreign folders, missing folders, project variables, unusable secrets), refusals by name |
| Tests and what only a human can check | covered: unit, integration, UI e2e, smoke, container in CI; the human's checks in 4.3/4.5 |
| Documentation | **missing: G1** |

### Later (moved by the human or the plan, not missing)

From `plan.md`, Later: LAD-140 (S7b's E6, a link inside a project folder listed as work
that goes); S7b's E3 (`DELETE` not bound to the preview); the lead's M2 (ragged refusal
background); S7a's F3, F4, X3, X5; the image's own `/projects` mount point; database
extras for repositories; sessions over several repositories; tracker integration and kit
settings per project; project artifacts; isolation and per-project outside secrets;
workspace folders outside projects (BACKLOG). Done outside the epic: LAD-121, LAD-122,
LAD-131, LAD-133; LAD-127 open (flaky UI test).

## Open checks

Each check open until 0.43.0rc1 is in the release checklist `docs/release.md`:

| Check | Step | Where | What to run, what to expect |
|---|---|---|---|
| Docker Desktop's refusal for a missing workspace | S2b | 4.5, "A missing workspace" | `LADO_WORKSPACE` to a missing folder, `up -d` refuses with that path, nothing made |
| live run on four CLIs with a variable and a secret, `start_session`, the UI's start (incl. S3's F1, agents' `lado mcp` gets `LADO_REPOS`) | S5a, S5b, S3 | 4.3, "Projects" | both supervisor and worker print `https://a`; `gh auth status` logged in; `show` without the value |
| secrets' link refusals on macOS | S5b | 4.3, "Projects' secrets on the Mac" | `set --secret` and `unset` refuse naming the link |
| secret field with password managers, Chrome and Safari | S6a | 4.3, "Projects in the web UI" | no offer to save, field empty, `set · hidden` |
| **a project in LADO's image** (new, this report) | S5a, S6b ("with Docker" of the brief's done) | 4.5, "Projects in the image" | project `BOARD_URL=https://a` over `/run/secrets/BOARD_URL=outside` in a project session; `outside` in a session without a project; the project folder on the host |

## Found on the way (not gaps)

- `lado doctor` run first after an upgrade (before any other command migrated the
  database) says `Projects: not checked: … LADO was upgraded under a running session`
  though no session runs (`src/lado/state.py:1211`, since 4b1bc039, 2026-10-06, older than
  the epic); the line itself tells to run any `lado` command. A BACKLOG candidate.
- `decisions.md` row of question #1283 (S6b) still says "pending", though `plan.md` S6b
  records the human's answer (adding repositories in S7).

## Questions for the human

1. **G1:** a docs step before 0.43.0rc1 that ticks ROADMAP's Projects and fixes the three
   stale sentences (recommended), or leave them for the release task?
2. Should that step also tell, in `docs/install.md` "Going back to an older version", what
   going back from 0.43.0 leaves: projects made on 0.43.0 are forgotten, their folders stay
   in `<workspace>/projects/` (doctor then calls `projects/` "your own folder" and refuses
   new projects until it is moved) and their secrets stay in `~/.lado/projects/<id>/`
   until removed by hand? Recommended: yes, one paragraph.

## Decisions

99 rows. With a decision: 93; the recommendation was taken in 89 (one in a changed form,
#1031), not in 4 (#523, #631, #1273 — a change to the concept, #1314). Without a decision
outcome: the lead's five review records and #1283 (pending in the file, see Found on the
way).

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
| 2026-10-21 | S1 (LAD-117), design_ok gate #34 | The design of S1: tweak, texts only, code names and installation names kept, the Projects placeholder's sentence in this step, specs by RENAMED/MODIFIED and REMOVED+ADDED | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | S1 (LAD-117), merge_ok gate #35 | Merge PR #126 with F1 ("projects" meaning the workspace in README.md:173, docker/Dockerfile, two container test comments, the container spec) left for S2b, F2 and E2 accepted | approve with F1 deferred (reviewer); reject to fix F1 in this PR (lead) | reject, fix F1 now: the human asked for phase 0 with no leftovers of the old model; the brief's grep missed bare "projects" (lead, disagreeing with the reviewer) | rejected with the lead's text (human) | yes |
| 2026-10-21 | S1 (LAD-117), merge_ok gate #37 | Merge PR #126 after F1's fix; "the projects' toolchains" (Dockerfile, docs/install.md, modules.md, a test docstring) carried to S2 as a leftover; F2, E2 accepted | approve; reject | approve, leftover to S2 (lead) | approved (human) | yes |
| 2026-10-21 | review after S1, step_ok gate #41 | The plan's revision after S1 (S1 done, leftovers to S2, the rule "questions as cards") and the next step S1b | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | S1b (LAD-120), analyst's question #585 | The warning box's colour | A: a new amber token, orange stays "waiting for you"; B: the orange "waiting for you" ground | A (analyst, lead) | A (human) | yes |
| 2026-10-21 | S1b (LAD-120), analyst's question #587 | The kit list's load error: a refusal with Start enabled | make it a warning; keep it a refusal and disable Start | a warning (analyst, lead) | a warning (human) | yes |
| 2026-10-21 | S1b (LAD-120), design_ok gate #42 | The design: tweak, CSS on the existing note classes, tokens `--warn`, `--warn-ground`, `--danger-ground`, new capability `launch-notes` | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | S1b (LAD-120), developer's question #594 | On a 390×844 phone the warning box pushes Start below the edge (on main it was half visible) | A: accept, the window scrolls; B: 12px text on narrow screens; C: other | A (developer, lead) | A (human) | yes |
| 2026-10-21 | S1b (LAD-120), merge_ok gate #43 | Merge PR #128 with F1 (Resume window: a provider refusal does not disable Resume, older, out of scope), F2, F3 open | approve; reject | approve; F1 and the unit tests' `sleep 60` leak to be proposed as tasks at the review (lead) | approved (human) | yes |
| 2026-10-21 | review after S1b, question #606 | Tracker tasks for the defects found in S1b (the unit run's `sleep 60` leak; the Resume window's provider refusal) | both; one; none | both, the leak before S3 (lead) | both (human): LAD-121, LAD-122, derived from LAD-120 | yes |
| 2026-10-21 | review after S1b, step_ok gate #44 | The plan's revision after S1b and the next step S2; LAD-121 alongside | approve; reject | approve, LAD-121 as its own task alongside S2 (lead) | approved: "Запусти lad-121 параллельно" (human) | yes |
| 2026-10-21 | LAD-121 (alongside S2), design_ok gate #45 | The design: the fake git kills and waits for its child in ok mode; `LADO_TEST_ID` per test; the leftovers check names the test | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | S2 (LAD-123), analyst's questions #613 | Five design questions of S2 (scale and details) | as recommended; other | as recommended (analyst, lead) | as recommended, scale full (human) | yes |
| 2026-10-21 | S2 (LAD-123), analyst's question #615 | "Project" meaning a repository in the container spec and the agents' mise paragraph: in S2 or S2b | S2b; S2 | S2b (lead) | S2b (human) | yes |
| 2026-10-21 | S2 (LAD-123), design_ok gate #46 | The design `projects-in-core`: `projects.workspace()`, table `projects` (schema 32), `lado project`, doctor's Projects check, renames without aliases, fresh start's default also `~/workspace` | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | LAD-121 (alongside S2), merge_ok gate #47 | Merge PR #130 (the `sleep 60` leak fixed; `make test` exit 0) with two minor findings declined | approve; reject | approve, LAD-121 first, S2 brings in main (lead) | approved (human) | yes |
| 2026-10-21 | LAD-121 (alongside S2), merge_ok gate #48 | Merge PR #130 again after the archive's refusal (spec only: `LADO_TEST_ID` as its own requirement; trial archive passes) | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-21 | S2 (LAD-123), merge_ok gate #51 | Merge PR #131 with 7 minor findings declined, among them F2 (`delete` misses stash, detached HEAD, a repository at the folder's root) and E3 (an unreadable folder gives a traceback) | approve; reject | approve; F2 and E3 into S7's frame at the review; lead's manual check on acbe045 passed (lead) | approved (human) | yes |
| 2026-10-21 | S2 (LAD-123), developer's question #631 | A tracker task for the CI flake: macOS smoke jobs cancelled after 15 min with no runner | yes; no | yes, outside the epic, low priority (developer, lead) | no (human) | no |
| 2026-10-21 | review after S2, step_ok gate #54 | The plan's revision after S2 (S2's delete leftovers to S7; S2b's mount check; S3's trap) and the next step S2b | approve; reject | approve (lead) | approved (human); the deletion leftovers stay in S7 | yes |
| 2026-10-21 | S2b (LAD-124), analyst's question #694 | Compose's refusal with neither `LADO_WORKSPACE` nor `LADO_PROJECTS` (the brief's threshold: Compose on GitHub's runners checks a nested `:?` even when the outer variable is set, LAD-73) | 1: a placeholder path, `up` refuses; 2: nested `:?`; 3: no `LADO_WORKSPACE`, wording only | 1 (analyst, lead) | 1 (human) | yes |
| 2026-10-21 | S2b (LAD-124), design_ok gate #56 | The design `compose-workspace-variable`: `${LADO_WORKSPACE:-${LADO_PROJECTS:-/set-LADO_WORKSPACE-…}}` for `LADO_REPOS` and a long bind with `create_host_path: false`; tweak, patch | approve; reject | approve; Docker Desktop's error text on macOS to be seen in the manual check (lead) | approved (human) | yes |
| 2026-10-22 | S2b (LAD-124), merge_ok gate #59 | Merge PR #136 with F3 open (Docker Desktop's refusal text not seen) and the external round not reading the spec delta and `tests/container/` | approve; reject | approve; the lead's text wrongly called the placeholder an unasked deviation from the brief's threshold: it was the human's choice at #694 (lead) | approved (human) | yes |
| 2026-10-22 | review after S2b | F3 and the image's `/projects` mount point for `docker run` | F3: release checklist 4.5 now, or a check in S3; `/projects`: Later, a task, a step | F3 into the release checklist (done until 0.43.0rc1); `/projects` to Later without a task (lead) | approved at step_ok gate #62 (human) | yes |
| 2026-10-22 | review after S2b, step_ok gate #62 | The plan's revision after S2b (S2b done with F3 open until 0.43.0rc1 in the release checklist; `/projects` to Later; the review trap in S3's brief) and the next step S3 | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | S3 (LAD-125), analyst's question #802 | The default name of a session in a project | `<project>-<repository>` (`shop-frontend`); the folder's name as today | `<project>-<repository>`; collisions are refused by the existing name check (analyst, lead) | as recommended (human) | yes |
| 2026-10-22 | S3 (LAD-125), analyst's question #804 | Is `--repo` required with one repository | always; optional with one | always: "all repositories" comes later (analyst, lead) | as recommended (human) | yes |
| 2026-10-22 | S3 (LAD-125), analyst's question #806 | A symbolic link in the project folder to a repository elsewhere | not a repository; a repository | not a repository; the lead added: name the link in `show`/`doctor` (analyst, lead) | as recommended (human) | yes |
| 2026-10-22 | S3 (LAD-125), analyst's question #808 (brief's threshold) | Sessions started under `projects/<id>/` between S2 and S3 | left without a project, refusing only new ones; bound by path at migration | left without a project; the lead added: delete refuses while any running session sits inside the project folder (analyst, lead) | as recommended, no comment (human) | yes |
| 2026-10-22 | S3 (LAD-125), analyst's question #810 | Where the session header shows the project | A: first quiet fact "project Shop"; B: "Shop / shop-frontend" before the name | A (analyst, lead) | A (human) | yes |
| 2026-10-22 | S3 (LAD-125), design_ok gate #63 | The design `sessions-in-projects`: `sessions.project` (schema 33), one refusal function for every start path, `GET /api/projects/{id}`, header variant A; full scale | approve; reject | approve with a comment: delete refuses while any running session sits inside the project folder; a link given as `--repo` is named as a link (lead) | approved with the lead's comment (human) | yes |
| 2026-10-22 | S3 (LAD-125), review, question #824 (brief's threshold: `providers/`) | F1: the agents' `lado mcp` lacks `LADO_REPOS`, so `start_session` from a session in a project misses the project outside the image | 1: fix here (`providers/base.py:agent_env` passes `LADO_REPOS` as `LADO_ENV_DIR`), no live tests; 1 with live tests; 2: a derived task | 1, no live tests (reviewer, lead) | 1, no live tests (human) | yes |
| 2026-10-22 | S3 (LAD-125), merge_ok gate #64 | Merge PR #138 (F1 fixed; E3, E4, F2 declined; no external round read `server/models.py`, the UI's session files, the specs, docs and tests) | approve (reviewer: converged); reject: E4's line in ui.md, F2, a second external round naming the unread files | reject with that text, disagreeing with the reviewer (lead) | rejected with the lead's text (human) | yes |
| 2026-10-22 | S3 (LAD-125), merge_ok gate #67 | Merge PR #138 after the second external round (server, UI, integration tests read, no blockers; E4, F2 fixed; texts read locally only; E3 to S4, G1 to S7) | approve; reject | approve (lead, reviewer) | approved (human) | yes |
| 2026-10-22 | S3 (LAD-125), merge_ok gate #71 (after the merge step's `conflicts`) | Merge PR #138 again: only two specs rewritten as ADDED requirements (3e3ddf4), trial archive 45/45, CI 23/23 | approve; reject | approve (lead, reviewer) | approved (human) | yes |
| 2026-10-22 | review after S3 | Plan revision: S3 done; E3 to S4, G1 to S7, F1 to S5a's live check; trial archive before `merge_ok` in S4's brief; S4 proposed | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | review after S3, question #883 | The new UI test `test_launch.py::…_refused_with_the_projects_command` flaky under load | 1: a task outside the epic, derived from LAD-125; 2: fix in S4; 3: no task, watch | 1 (lead) | 1: LAD-127 created, derived from LAD-125, label `component lado` (human) | yes |
| 2026-10-22 | step_ok gate #72 | Approve the plan's revision after S3 and step S4 | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | S4 (LAD-128), design, question #892 | Scale full; CLI `lado project repo add/remove`; `remove` takes repositories and links only; repository name rule | yes, as recommended; amendments | yes, with the name taken checked case-insensitively (lead) | yes, as recommended (human); the lead's case point is met by the design's disk check (D1, D2) | yes |
| 2026-10-22 | S4 (LAD-128), design_ok gate #73 | The design `project-repositories`: `lado project repo add/remove` through `clone`/`scratch`, removal by path as S3's D9, server API (`POST /api/clones` with `project`, `POST`/`GET …/removal`/`DELETE /api/projects/{id}/repos`), E3's hints; full scale, no migration | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | S4 (LAD-128), merge_ok gate #77 | Merge PR #141: X1 (a project folder linked to another project's let `repo remove` delete the neighbour's repository) fixed by `_own_folder`; 7 minor declined; external rounds 2/2 read code only, specs, docs, tests and OpenAPI local only (the review trap a fourth time) | approve; reject | approve; the trap goes to the human at the step review as a question of the review process (lead) | approved (human) | yes |
| 2026-10-22 | review after S4 | Plan revision: S4 done; X3 to S7; S5b's notes get the link check of the secrets' folder; S5a proposed | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | review after S4, question #949 | The external review (Claude Code Action) reads code only, four steps running: specs, docs, tests and OpenAPI read locally only | 2: local reading of texts is enough, the coverage table stays; 1: a third external round for texts with their content in the request; 3: as now, decide at each gate | 2 (lead) | 2 (human) | yes |
| 2026-10-22 | step_ok gate #79 | Approve the plan's revision after S4 and step S5a | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | S5a (LAD-130), design, question #966 | Scale full; a kit key with a secret-like name (`YOUGILE_API_KEY`) waits for S5b's secrets, S5a checks the mechanism on a plain name; reserved names exact (shell, `LADO_*`, what LADO sets for each CLI) with a unit test; CLI and doctor output | accept all; amendments | accept all; note: the epic's goal (per-project `YOUGILE_API_KEY`/`GH_TOKEN`) works only after S5b (lead) | accept all (human) | yes |
| 2026-10-22 | S5a (LAD-130), design_ok gate #82 | The design `project-variables`: table `project_variables` (schema 34, cascade), the layer in `agent_env.resolve(project=…)`/`runtime._base_env`, `CLI_VARIABLES` with a test, `PUT`/`DELETE /api/projects/{id}/variables/{name}`, doctor's line, a smoke probe kit; `inherit` mode's unset limit documented (D12) | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-22 | S5a (LAD-130), build, question #1001 | File a task for the flaky integration test `test_agent_liveness::…transient_error…` (worker window closes before its first hook), seen on PR #144's CI | yes, file it (derived on LAD-130); no | yes, outside the epic, as LAD-127 (#883) (lead) | yes (human) | yes |
| 2026-10-23 | S5a (LAD-130), merge_ok gate #85 | Merge PR #144 with minors F3–F6 declined (F5: a set racing a delete gives 500); no live run before the merge | approve; reject | approve; F5 a note for S7, the live run on four CLIs to the release checklist (lead) | approved (human) | yes |
| 2026-10-23 | S5a (LAD-130), merge, question #1031 | LAD-127's UI test failed again on PR #144's CI: file a new task? | yes, relates to LAD-127; no; reopen LAD-127 | first "yes"; changed to "no": the failing run (fdf688d) did not contain LAD-127's fix cf2cec8 (lead) | no (human) | yes (the changed one) |
| 2026-10-23 | review after S5a | S5a's live run on four CLIs (with S3's F1) to the release checklist 4.3 "Projects"; F5 to S7; LAD-131 to Later; `unset`'s text slip to S5b | — | (lead) | — | — |
| 2026-10-23 | step_ok gate #87 | Approve the plan's revision after S5a and step S5b (project secrets) | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-23 | S5b (LAD-132), design, question #1060 | A name both a plain variable and a secret: what does `set` do? | А refuse with the `unset` hint; Б replace with a message | А (analyst, lead) | А (human) | yes |
| 2026-10-23 | S5b (LAD-132), design, question #1062 | May a secret have a name that does not look like one (`DATABASE_URL`)? | А any valid non-reserved name; Б only TOKEN/KEY/SECRET/PASSWORD names | А (analyst, lead) | А (human) | yes |
| 2026-10-23 | S5b (LAD-132), design, question #1064 (the brief's threshold) | A secret passes through the launch file `env.json` (600, removed at once) outside `secrets/`, as every key today | А accept, say so in the spec and docs; Б a separate task: delivery without a file | А; check no `env.json` is left (lead) | А (human) | yes |
| 2026-10-23 | S5b (LAD-132), design, question #1066 | Entering a secret's value | А once without echo or from stdin; refused on the command line and empty; Б empty allowed; В typed twice | А; the refusals never repeat the value (lead) | А (human) | yes |
| 2026-10-23 | S5b (LAD-132), design, question #1068 | A secret file with modes wider than 600/700 | А not used, named at the start and in doctor; Б used with a warning | А; only the project's folder, not `LADO_ENV_DIR` (lead) | А (human) | yes |
| 2026-10-23 | S5b (LAD-132), design_ok gate #91 | The design `project-secrets`: module `project_secrets.py`, link-safe writes (`dir_fd`, `O_NOFOLLOW`), one reader `agent_env.read_folder(own=…)`, write-only API by kind, conflict rule D4, the canary as an integration test (`LADO_HOME`, `ps`, tmux environment, change feed) | approve; reject | approve; for the build: the canary covers the command-line refusal, the API's conflict code tested, `env.json` gone with forget/delete (lead) | approved (human) | yes |
| 2026-10-23 | S5b (LAD-132), merge_ok gate #94 | Merge PR #148 with minors declined (F3/E5 reading follows links above `secrets/`; E2, E3, E6–E10; E11 per #1064); `cli.py` read by no external round | approve; reject | approve; the lead read `cli.py`'s diff for #949; E6–E9 to S6's canary, F3/E5 a docs line in S6/S7; secret and macOS link refusals to the release checklist (lead) | approved (human) | yes |
| 2026-10-23 | the human's question in chat (after gate #94) | Should the external review read every file? | full review of all files; risky code read fully and verifiably, texts local (#949) | the latter, plus a task to fix `claude.yml` (`fetch-depth: 0`, read-only `git diff`/`gh pr diff`, a review prompt listing the files read) (lead) | the latter; task LAD-133, relates to LAD-116 (human) | yes |
| 2026-10-23 | review after S5b | Secret and macOS link checks to the release checklist 4.3; E6–E9 and F3/E5 to S6; LAD-133 to Later (own session `review-scope`); S6 brief with a split threshold (S6a/S6b) | — | (lead) | — | — |
| 2026-10-23 | step_ok gate #96 | Approve the plan's revision after S5b and step S6 (UI of projects, L, split threshold S6a/S6b) | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-23 | S6 (LAD-134), design, question #1151 of the analyst | S6 is heavy: split into S6a (Projects section, project screen with variables and secrets, API, canary, docs) and S6b (the Project way of New session, a new task derived from LAD-134)? | split; keep one | split: each part merges alone, the review does not mix the secrets' way with `Launch.tsx`; S6b to the plan at the review after S6a (lead) | split (human) | yes |
| 2026-10-23 | S6 (LAD-134), design, question #1153 of the analyst | The mockup's recommendations 1–10 | accept all; change some | accept all; notes: the placeholder links `docs/design/projects.md` or `lado project show`, not the epic's files; the secret field `autocomplete` off and emptied after save, checked in UI e2e; a Cyrillic title leaves the Id to be typed (lead) | accept all (human) | yes |
| 2026-10-23 | S6 (LAD-134), design, question #1158 of the analyst | Adding repositories to a project in the UI: as planned (S6b and S7) or a button in S6a? | as planned, the CLI command in the placeholder; a button in S6a | as planned; the placeholder names the current project's id, covered by UI e2e (lead) | as planned (human) | yes |
| 2026-10-23 | S6a (LAD-134), design_ok gate #98 | The design `projects-section` (D1–D16): `/projects` routes, `GET`/`POST /api/projects`, `GET /api/project-id`, the secret's value only in an uncontrolled field and the `PUT` body, the canary E6–E9, UI e2e of the value's absence | approve; reject | approve; for the review: the external round reads `POST /api/projects`, `check_new` and the secret's way in full; a test pins the "looks like a secret" text the UI matches; S6b created only on the human's yes (lead) | approved (human) | yes |
| 2026-10-23 | S6a (LAD-134), merge_ok gate #101 | Merge PR #151 with minors declined (F4: Enter while busy repeats an idempotent `PUT`; E2: Create disabled without a reason on an absurd title) | approve; reject | approve; #949 met (external rounds read `ProjectVariables.tsx`, `Projects.tsx`, `project_secrets.py` in full, the routes and `putSecret` by diff); E2's hint may go to S7; lead's manual UI check at the review (lead) | approved (human) | yes |
| 2026-10-23 | review after S6a | S6 split recorded: S6a done, S6b (the Project way of New session) added as the next step; E2 and the lead's M1 (narrow desktop window) to S7; a release check of the secret field with password managers (4.3 "Projects in the web UI"); LAD-133 done | — | (lead) | — | — |
| 2026-10-23 | step_ok gate #105 | Approve the plan's revision after S6a and step S6b (the Project way of New session, M) | approve; reject | approve; S6b before S7 closes the UI's gap (a session in a project starts only from the CLI) (lead) | approved (human) | yes |
| 2026-10-23 | S6b (LAD-137), design, question #1273 of the analyst | The Project way's recommendations: the button last (2×2 on a phone); the window still opens in Folder/From scratch; preselect the last project and repository; no projects → a link to Projects; widen to the refusal's button in Folder, Clone into and Create in, and a "New session in this project" link on the project's page | accept all; accept with changes; discuss | accept all; notes: the chosen project plainly visible at Start (wrong project = another client's keys), checked by UI e2e; the default name `<project>-<repo>` passes the session name's rule with long ids (lead) | "the dialog is too complex: repositories are managed only on the project's page; New session only picks one of the project's repositories" (human, #1282) | no: a change to the concept, "+ new repository" leaves New session |
| 2026-10-23 | S6b (LAD-137), design, question #1283 of the analyst | After #1282: adding repositories on the project's page in S6b or in S7; the button last; the window's default way unchanged; preselect the last project and repository; no projects → a link to Projects; the Folder refusal → "Start in the project …" or "Open the project …", Clone into and Create in keep the CLI command; "New session in this project…" on the project's page | in S7; in this step; changes | in S7, S7 right after S6b and no 0.43.0rc1 between them (the UI cannot add a repository until S7); after S7 the Clone into / Create in refusals link the project's page (lead) | pending | |
| 2026-10-23 | S6b (LAD-137), design_ok gate #107 | The design `new-session-in-project` (D1–D15): `Where` with optional `path`/`project`/`repo`, the start is `runtime.start_session` as the CLI's, `GET /api/project-launch`, `projects.place`, `LaunchProject.tsx`, the canary starts through the API; "+ new repository" gone from the window (#1282) | approve; reject | approve; for the build: the chosen project plainly visible at Start and UI e2e that a changed choice starts there; a test of long ids' session name; the external round reads the start's route, `project-launch`, `place` and `LaunchProject.tsx` in full (lead) | approved (human) | yes |
| 2026-10-23 | S6b (LAD-137), build, question #1314 of the developer | A task for the flaky container test `test_the_first_ssh_to_github_knows_its_host_key` (port 22 timed out on the runner, PR #155's CI, run 39972297968)? | create; no | create: skip loudly only on an unreachable port 22 (maybe one retry first), a wrong host key still fails; derived from LAD-137; outside the epic, to "Later" (lead) | no (human) | no |
| 2026-10-23 | S6b (LAD-137), review, question #1332 (from the reviewer's report) | External rounds spent (2/2) with X1 (important: the repository list blinks and loses focus while a choice is checked) and X2 (minor: "Resume it" offered for a session without a project) open | fix + a third external round on the delta; fix + local check only (the reviewer's); accept and merge | fix + a third external round on the delta: X2 changes the start's Resume logic in `launch.py` (#949) (lead) | fix + third external round (human) | yes |
| 2026-10-23 | S6b (LAD-137), merge_ok gate #109 | Merge PR #155 with six minors declined (E1 `project-launch` silently offers another project when the asked one is gone; E2, X3, Y1, Z1, Z3); live tests not run | approve; reject | approve; the `runtime.py` change is one extracted expression (`project_session_name`), live not needed before merge; E1 noted for S7 (lead) | approved (human) | yes |
| 2026-10-23 | review after S6b | S7 gains "+ Add repository" (clone with progress and cancel, from scratch) as the UI's only way (#1282, #1283), E1 of S6b, the Clone into / Create in refusals linking the page; no 0.43.0rc1 before S7 merges; the release checklist's Projects item gains a start from the UI | — | (lead) | — | — |
| 2026-10-23 | step_ok gate #110 | Approve the plan's revision after S6b and step S7 (the project's page: repositories, + Add repository, removal, rename; leftovers of S2–S6b; split threshold S7a/S7b) | approve; reject | approve (lead) | approved (human) | yes |
| 2026-10-23 | S7 (LAD-138), design, question #1347 of the analyst | S7 is heavy: split into S7a (the page, repositories, + Add repository, repository removal, rename) and S7b (project removal, a new task derived from LAD-138)? | 1 split, rename in S7a; 2 split, rename in S7b; 3 one PR | 1: project removal gets a review of its own; the clone's extraction from `Launch.tsx` keeps its UI tests green unchanged; 0.43.0rc1 waits for S7b as well (lead) | 1 (human) | yes |
| 2026-10-23 | S7a (LAD-138), design, question #1350 of the analyst | Eight points of the project's page: sessions block (A), rename in place with `PATCH`, + Add repository dialog, X3 (a) forget pre-S3 sessions in the folder, E1 warning, repository removal confirmed by a red button only, links not shown, create S7b | as recommended + create S7b; as recommended, no S7b yet; changes | changes: 6 — type the repository's name when the preview shows unpushed work (projects.md: "works the same way"), a button when clean; 8 — F2/F3 fixed in S7a only, S7b checks its dialog shows them; the rest as recommended, create S7b (lead) | 1, 3–5, 7 accepted; #1352: Tab takes the id, the name typed when unpushed work shows, F2/F3 fixed in S7a; S7b created as LAD-139 (human) | yes |
| 2026-10-23 | S7a (LAD-138), design_ok gate #111 | The design `project-page` (D1–D17): `PATCH /api/projects/{id}` via `projects.rename`, shared `TitleEdit`, the clone's client moved to `useCloneJob`, X3 in the core, F2/F3 in `unpushed`, the name typed only with unpushed work, E1 via `ProjectLaunch.gone`, M1 by CSS; no canary change | approve; reject | approve; for the review: the window's clone tests (`tests/ui/test_launch.py`, `Launch.test.tsx`) unchanged; the external round reads the listed files in full (lead) | approved | yes |
| 2026-10-23 | S7a (LAD-138), merge_ok gate #112 | PR #157 at a96b79e9: review converged in 2 rounds (X1 fixed, external 2/2 clean, #949 coverage full, CI green); 6 minor declined to the gate (F1 Back doesn't cancel the clone, F2 a repository project folder always "uncommitted changes", F3, F4, X3, X5) | approve; reject | approve; F2 and F1 to S7b (LAD-139), F3, F4, X3, X5 to Later (lead) | approved | yes |
| 2026-10-23 | Review after S7a (LAD-138) | S7a done (PR #157); S7b (LAD-139) next with S7a's F1 and F2 and the delete leftovers of S2–S5a; F3, F4, X3, X5 to Later; no 0.43.0rc1 before S7b | next (S7b); finish | next: S7b (lead) | approved (#113) | yes |
| 2026-10-23 | step_ok gate #113 (after S7a) | S7b (LAD-139): deleting the project in the UI, the delete leftovers of S2–S5a, S7a's F1/F2, the canary over the delete | approve; reject | approve; at design_ok watch F5/G1 for a linked folder and S7a's F2 (no id typed for a false "uncommitted changes") (lead) | approved | yes |
| 2026-10-23 | S7b (LAD-139), question #1375 of analyst-139 | 1: "Delete project…" in its own block at the page's bottom (A) or in the header (B); 2: the id typed always or only with unpushed work; 3: the dialog lists unpushed work, sessions forgotten and (new) the names of variables and secrets deleted | A, id always, three lists; other | all as recommended: the concept says the id is typed in the UI, secrets are on no remote; the canary checks the preview answer too; the design decides G1 for a linked folder explicitly (lead) | all as recommended | yes |
| 2026-10-23 | S7b (LAD-139), design_ok gate #114 | The design `project-delete` (D1–D13): one preview `projects.deletion` for CLI, API and dialog; G1 — for a linked project folder only the link goes, so a session in its target neither blocks nor is forgotten; F2 — nested repositories excluded from the root's `git status`; E3 a "could not check" line; S5a's F5 — `IntegrityError` as `NoSuchProject`; `GET …/deletion`, `DELETE /api/projects/{id}` 204; `ProjectDelete.tsx`; F1 — `useCloneJob` cancels on unmount; the canary over preview and delete | approve; reject | approve; at review: the link path deletes the link only, read in full by the external round; the window's clone tests unchanged (lead) | approved | yes |
| 2026-10-23 | S7b (LAD-139), merge_ok gate #115 | PR #159 at 9e5af5ff: review converged in 2 rounds (E1 important — literal pathspec excludes — and L1 fixed; external 2/2 read the delete path in full; CI 23/23); declined L2 (a narrow set_secret/delete race, loud), E2 (full preview in delete, D1), E3 (DELETE not bound to the preview), E6 (a link inside the project folder shown as unpushed work, older than the change) | approve; reject | approve; E3 and E6 to Later, E6 offered as a task at the epic review; the lead's manual check after the merge (lead) | approved | yes |
| 2026-10-23 | After S7b, question #1397 (lead) | E6 of LAD-139's review: a link inside a project's folder listed as unpushed work (a false alarm, older than the epic) — a task? | a task in Later; none; fix before 0.43.0rc1 | a task in Later (lead) | a task in Later: LAD-140 | yes |
| 2026-10-23 | Review after S7b (LAD-139) | Every step S1–S7b done; E3, E6 (LAD-140) and the lead's M2 in Later; the next is the readiness check | finish; next | finish → readiness (lead) | — | |
