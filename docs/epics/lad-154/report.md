# Readiness report: Model and power choice for agents (LAD-154)

First visit, 2026-11-07, by `delivery`, on the local branch `readiness/lad-154` at c4688ba7:
`origin/epic/lad-154-models` at 428415b9 with `origin/main` at 27d01d17 merged in. Plan and
decisions read from the run's branch at 4ab398cc. Previous release: v0.44.0 (schema 35).
This build: schema 39.

## Verdict

**One gap (G1).** The epic's product is ready in everything else: all 15 steps of D47's and
D48's scope are done, the checks are green on what will be released, the upgrade from 0.44.0
loses and changes nothing, and the way back runs.

**G1: the way back from 0.45.0 does not say what happens to model servers and their keys.**
`lado update 0.44.0` drops every saved model server, model and CLI default with `lado.db`,
and its warning and `docs/install.md` list "sessions, runs, gates, messages, projects" only.
The key file stays on disk, `~/.lado/model-servers/<id>/key`, and neither the warning, nor
"What stays" in `docs/install.md`, nor 0.44.0's `lado doctor` says so. Evidence and the
proposed fix are under "Upgrade from 0.44.0, and back".

## The base merge

`git merge origin/main` into `readiness/lad-154`: no conflict, 5 files, all of LAD-232 (PR
#250: `tests/test_uninstall.py`, its archived change and review report). Nothing to resolve.
The merge c4688ba7 is local and not pushed; the lead pushes it at `close` after the human's
yes, or a later visit makes it again.

## Results of all steps

Fifteen steps done. S4, S5c, S7, S7b and S8 moved to a new epic (D47); S5a and S5b were taken
into S3c and S3d (D18); S5d was dropped and S6 moved to "Later" (D42). None is planned or in
progress.

| Step | Task | Pull request (merge) | Check | Evidence |
|---|---|---|---|---|
| S1 — the agent's model is visible | LAD-169 | #194 (b377959a) | model, effort, source in `lado.db`, `list_agents`, API, card; migration | plan.md S1: schema 35 → 36, CI 23/23, smoke on four providers; Kilo's event open |
| S2 — one model per session | LAD-174 | #201 (69bd2306) | `lado start --model`, Advanced, smoke per provider, migration | plan.md S2: schema 36 → 37, spec `session-model`, CI 23/23 |
| S2b — the Model field, small fixes | LAD-176 | #202 (f2cbf119) | field's look and note, trim, cache, a kept model at resume | plan.md S2b: CI green, 2 review rounds |
| S3a — what a model server is | LAD-177 | #203 (cf072b9d) | fake servers, the compatibility rule, Docker's hint | plan.md S3a: spec `model-servers`, CI 23/23 |
| S3c — the store, servers, models | LAD-182 | #208 (acc2b129) | `model-server`, `model`, key in a 600 file, doctor, canary, migration | plan.md S3c: schema to 38; seen in the run below |
| S3e — fixes of the manual check | LAD-183–186 | #210 (27679604) | LiteLLM's type, embeddings, same address, remove hint | plan.md S3e, gate #236 |
| S3d — Settings → Models | LAD-187 | #211 (e52a547f) | the page, mock-up, UI e2e | plan.md S3d: 13 review rounds, manual checks r1–r4, CI 23/23 |
| S3f — external models, a default per CLI | LAD-200 | #216 (540ab41a) | picker, a CLI's list computed, migration 38 → 39 | plan.md S3f: 2 design QA passes, gate #276 |
| S3b — a session on a model reference | LAD-180 | #219 (2d33817c) | start and resume check, `/model`, key only in the environment, canary, smoke | plan.md S3b: CI 23/23 on 9e6ffda9, gate #285 |
| S3g — a worker on a model by name | LAD-208 | #220 (df5545f8) | `list_models`, `spawn_worker(model=…)`, integration | plan.md S3g: 5 code files, manual check passed |
| S10 — OpenCode and Kilo on local models | LAD-211 | #223 (5003e2f2) | the closed list, each item fixed, moved or named | plan.md S10: gates #297–#302; LAD-210's fix cb76505d is in |
| S10b — Kilo's first message | LAD-212 | #225 (995ab826) | first try, no loss, five runs | plan.md S10b: CI 23/23 on f5a53dea, 8 of 8 by hand |
| S9a — a model server for Claude Code | LAD-217 | #226 (141de01f) | `ANTHROPIC_BASE_URL`, key in the environment, smoke, refusal | plan.md S9a: CI 23/23 on 241d2bd5, report `manual-check-226-r2` |
| S11 — an external provider by key | LAD-220 | #235 (d0464c6a) | the closed list on cloud.ru and OpenRouter, 401, 429, cost | plan.md S11: passed at f9b7e98b, #4501 |
| S9b — a model server for Codex | LAD-230 | #246 (7c044e39) | `model_providers` in `CODEX_HOME`, refusal, smoke | plan.md S9b: CI 23/23 on 725557bb, passed #4676 |

### The product's checks on what will be released (c4688ba7)

| Command | Result |
|---|---|
| `make lint` | exit 0: `All checks passed!` |
| `make test` | exit 0: **5960 passed, 7 skipped** in 55.7 s. The first run, beside this report's wheel build and `uv tool` runs: the same 5960 passed, and one collection error, `EOFError: marshal data too short` in `tests/live/test_live.py` importing `lado` (a torn `.pyc`, not a test); the rerun alone is clean |
| `make web` | exit 0: stale-types check, tsc, vitest **1758 passed (1758)**, build |
| `make test-js` | exit 0: **39 passed**, 0 failed |
| `openspec validate --specs --strict` | exit 0: **78 passed, 0 failed** |
| `uv run pytest -m integration -n auto tests/integration` | exit 0: **288 passed, 3 skipped** in 84.8 s |
| `make test-ui` | exit 0: **581 passed** in 171.7 s |
| CI on `origin/main` at 27d01d17 (run 42407727620) | success, 23/23 jobs |

CI has not run on c4688ba7 or on the epic branch's 428415b9: no run is listed for the branch,
and the last CI over the epic's code is PR #246's on 725557bb, 23/23. The final pull request's
CI is the first over the merged result; the smoke and the container tests are not in the table
above. LAD-232's change against 428415b9 is one test file.

**The epic's numbering.** The diff `origin/main...readiness/lad-154` outside `docs/epics/`
(300 files) searched for `S1`…`S11` with a letter and for `docs/epics/`: code, `web/`, `docs/`
but for `docs/superpowers/`, `openspec/`, `CHANGELOG.md`: no hit. 16 hits, none of them the
epic's numbering in the product: nine are the rule itself in `docs/superpowers/plans/` ("No step
numbers of the epic…"), seven in `docs/superpowers/reports/2026-11-04-model-settings-page-review.md`
are the ids of the human's findings of round r2 (`S1`–`S5`).

**CHANGELOG, 0.45.0.** The epic's lines stop where D47 stops: nothing promises effort as a
choice, a power table, kit marking or `spawn_worker(power=…)`; the word `effort` appears once,
in "See which model each agent runs on", which S1 built. Of S11's F9 (a line of four lines): no
S11 line is over three now. Over docs/release.md's three lines are two items, neither from
S11: **Set models in Settings** (the epic's) and **The card that waits for you** (`main`'s). No
script refuses them; a remark, not a gap.

## Checked by hand

| Step | Checked by hand | By whom |
|---|---|---|
| S1 | on another machine, epic branch at c9f068e3, no remarks | the human |
| S2 | on another machine at 0d18c677: two remarks on the Model field → S2b | the human |
| S2b | the PR's branch before gate #207, no remarks | the human |
| S3c | LM Studio and LiteLLM 1.105.1 → LAD-183–186 (S3e) | the human |
| S3d | manual checks r1–r4 (`pr-211-manual-check-r2`, `-r3`, D29, D30) in Chromium | the human |
| S3f | all 8 items on dc3d70e8, a fake server in place of LM Studio | the human |
| S3b | 2 rounds on a real LM Studio and Ollama, a proxy for LiteLLM (F1 → D46) | the human |
| S3g | all 4 steps and 2 extra on a real LM Studio through a proxy | the human |
| S10 | real LM Studio, Ollama and LiteLLM 1.108.1; item 6 not run (moved to S11) | the human |
| S10b | 8 of 8 on real Kilo and OpenCode | the human |
| S9a | Claude Code 2.1.319, LM Studio, cloud.ru's Anthropic API (`manual-check-226-r2`) | the human |
| S11 | 3 rounds on cloud.ru and OpenRouter, passed at f9b7e98b (#4501) | the human |
| S9b | every item of the PR on Codex 0.163.0, OpenRouter and LM Studio, a key revoked mid-session (#4676) | the human |
| S3a, S3e | no check of their own; S3e's result by S3d's and S3b's checks; the open check below | nobody |
| readiness | the upgrade and the way back below, real OpenCode and Codex, a fake server, no model called | `delivery` |

**Never checked by hand** (each in the release checklist, or named in "Later"): `make test-live`
on any provider (no step's record shows a run); Settings → Models and the picker in Safari, Firefox and on a real
phone (Chromium only); the stop at the third overflow on a real server; Kilo's model in
`chat.message`; a resume at the container's start with a CLI not logged in; Qwen through Alibaba
Model Studio and a model of a provider the CLI logged in to itself; on a real provider 429, 402
and a quota during a turn; Codex on Ollama and vLLM; the epic in LADO's image.

## Upgrade from 0.44.0, and back

Done in `/tmp/lado-upgrade-X42j` (removed by name afterwards, with its tmux server
`lado-upg-X42j`): `uv tool install lado==0.44.0` from PyPI with `UV_TOOL_DIR` and
`UV_TOOL_BIN_DIR` there, `HOME`, `LADO_HOME` and the tmux socket of its own, `LADO_TELEMETRY=0`,
every other `LADO_*` unset. The new build: a wheel of c4688ba7 built in a copy of the tree with
the version `0.45.0rc0` in the copy only (`lado update` cannot reach a build that is not on
PyPI), put in by `uv tool install --force` after `lado stop --all`, the manual path of
`docs/install.md`. Agents were the real OpenCode 1.18.35 and Codex 0.162.0, with no login and
no model called; the server `tests/fake_model_server.py`, profile `openai`, with a canary key.

State made on 0.44.0: session `app` on OpenCode; project `shop` with `BOARD_URL`, two secrets and
the repository `cdx`, session `shop-cdx` on Codex; the user's `~/.codex/config.toml`
(`model = "gpt-5.1-codex"`, `model_reasoning_effort = "high"`), `~/.claude/settings.json` and
OpenCode's `model.json`.

| What | Result |
|---|---|
| Doctor before the migration | `[info] lado.db: schema 35, this LADO knows 39: lado ls or lado start upgrades it`; model servers `not checked` for the same reason |
| Migration | `lado: upgraded lado.db from schema 35 to 39; its backup is …/backups/lado.db.schema-35` |
| Old sessions | both listed `(stopped)`, resumed by `lado start <folder>` and `lado start --project shop --repo cdx`, in their project |
| Unset, as today | `app` on the CLI's default: `model` empty, source `cli`, then `opencode/big-pickle` from its event; `shop-cdx` shows `gpt-5.1-codex`, model and effort `high` from source `cli-config`, carried into its `CODEX_HOME` |
| The user's files | `~/.codex/config.toml`, `~/.claude/settings.json`, `model.json`: sha256 unchanged on the new build, before and after the agents ran. `model.json` changed once, on 0.44.0 after the way back: OpenCode's own write (`variant`), no `lado-…` entry; 0.44.0's agents share that file |
| New on the upgraded home | `model-server add lab … --key` from a pipe, `model add`, `model default`; doctor `[ok] Model servers`, `[ok] Default models`; a new session on `Local`, source `default`, `lado ls` says `Local`; the canary only in `model-servers/<id>/key`, 600 in a 700 folder |
| A kept session and a new default | `lado start <folder>` prints `changed model: CLI default -> Local` |
| Its server silent | doctor warns on both lines; `lado start` refuses with `…does not answer…; start with --model '' for its settings, or change it with lado model default opencode` |
| Back: `lado update 0.44.0 --yes` | the warning came first and named `onsrv` as not started again; stopped all three, installed 0.44.0 from PyPI, `Restored lado.db from …schema-35 (schema 35)`, resumed `app` and `shop-cdx`, `LADO 0.44.0 is ready.`; `backups/` keeps the copy |
| After the way back | the servers, models and defaults are gone with `lado.db`; **`model-servers/<id>/key` stays, 0.44.0's doctor says nothing of it (G1)** |
| Up again | schema 35 → 39 again; `lado model-server list`: none; doctor `[warn] Model servers: left over: …/model-servers/ed6044c73df5 (no saved server's)`, also after the same server is added again under a new id |
| `lado uninstall --yes` | `Deleted …/.lado`, the key with it; the workspace and the CLIs' own folders stay |

**G1, in full.** The warning (`src/lado/self_update.py:322`) and `docs/install.md:1036` list what
is lost; "What stays" (`docs/install.md:1064`) names a project's secrets on disk. Neither knows
the epic's store: a user going back is not told that their servers, models and defaults go, and
a key to a paid provider stays in a folder nothing names until they upgrade again. The human's
rule is that removing a server removes its key (S3c, D15), and for projects' secrets LADO took
care to name exactly this (LAD-116's second question). Proposed step, small, no schema change:
add model servers, models and defaults to the warning and to the docs' list; say in "What
stays" and in Docker's "Go back to the version before" that `model-servers/` stays with its keys
and how to remove it; a unit test of the warning's text.

Not run here: **`lado update` itself onto 0.45.0** (the build is not on PyPI; it runs at 4.2 of
the release checklist) and **the image's upgrade**: LADO's container has no Docker. The epic
changes only two comments in `docker/`. The human runs 4.5 and 4.6; CI's container tests cover
the image on each pull request.

## Missing

Against the brief's "done", as D47 and D48 left it:

| "Done" item | Covered by |
|---|---|
| every agent shows its model, effort and their source | S1, S2, S3b; seen above |
| a session runs on one chosen model | S2, S3b; effort as a choice: "Later" (D47) |
| a CLI takes a default model; `/model` offers every ticked external model | S3f, S3b; seen above; `/model` by the human in S3b |
| a session on a model server through OpenCode/Kilo, Claude Code, Codex; a check before the start, a loud refusal | S3b, S9a, S9b, S11; the refusal seen above |
| the supervisor starts a worker on a model by name | S3g |
| no value dropped silently on the four CLIs | S2 and S3b's refusals and warnings, S9a, S9b; effort next to the model: "Later" |
| the power table, kit marking | "Later" (D42, D47) |

Readiness checklist:

| Topic | Verdict |
|---|---|
| Goal and "done" | covered (above) |
| Users and how they use it | covered: CLI (`lado model`, `model-server`), Settings → Models, the launch window, `list_models` |
| Scope and what is out | covered: D47, D48; "Later" below |
| Data and migrations | covered: schema 35 → 39, seen above |
| Secrets and credentials | covered: the key's file, `{env:…}`, canary tests, seen above; F15 (an agent can read its server's key by `env`) in "Later" on the human's word; **the key left by the way back: G1** |
| Update and rollback | **gap G1**; the mechanics work, seen above; the image → 4.6 |
| Removal | covered: `model-server remove`, `--with-models`, `lado uninstall` seen above |
| Platforms | covered: four CLIs by smoke on Linux and macOS (CI), Docker's hint; live → section 2; browsers and phone → 4.3 |
| Observability | covered: `lado ls`, the card, doctor's lines, refusals by name, seen above |
| Tests and what only a human can check | covered: unit, integration, UI e2e, smoke; the human's manual checks; the rest in the release checklist |
| Documentation | covered but for G1: `docs/install.md` (local models, a cloud provider, limits), `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`, `docs/design/modules.md`, 78 specs. `ROADMAP.md` has no line on the epic; the brief does not ask for one |

### Later (moved by the human or the plan, not missing)

From `plan.md`, Later. The new epic (D47): S4 effort, S5c the power table, S7 and S7b, S8; its
tracker task on the human's yes at `close`. S6 the project's table, statement step 10, profiles
(LAD-80), named sets, automatic power and fallback models. Tasks: LAD-190, LAD-191, LAD-201,
LAD-202, LAD-204, LAD-205, LAD-209, LAD-213. F15 for all CLIs at once. Not seen on a real
provider or server after S11 and S9b: 429, 402, a quota, a 5xx, a server gone in mid-turn, a
compaction at 1048576, Ollama and vLLM on Codex. Declined findings of S1, S2b, S3c, S3e, S9a,
S11, S9b. A session's tokens or money in LADO; Claude Code offered without a login; flakes with
no task; `/tmp/claude-1000` shared by a container's agents.

## Open checks

Each moved in this commit into `docs/release.md`, 4.3 "Models" unless it says otherwise.

| Check | Step | Where | What to run, what to expect |
|---|---|---|---|
| `make test-live` per provider, Claude Code with the human's yes | S1–S9b | section 2, step 3, as for any RC; 4.3 says what to look at | green; no step's record shows a run |
| Kilo's model in `chat.message` | S1 | 4.3 | after a turn of a Kilo agent, `lado ls` names its model |
| a Codex model list, and a repository's own `.codex/config.toml` | S2 ("Later") | 4.3 | `--model` from the list reaches the agent; a model in the repository's file: what the card says |
| a resume at the container's start with a CLI not logged in | S2b | 4.6 | the kept model is not refused falsely |
| the stop at the third overflow on a real server | S10 | 4.3 | the turn ends with LADO's words, no endless `busy`; LM Studio answers 400 and never gets there |
| S3e on LM Studio and a real LiteLLM | S3e | 4.3 | LiteLLM typed OpenAI-compatible, embeddings refused, the same address named |
| Settings → Models in Safari, Firefox, on a real phone | S3d, S3f | 4.3 | no scrolling by itself, the key in dots, the phone's width, the picker above the keyboard |
| Qwen through Alibaba Model Studio; a model of a provider the CLI logged in to itself | S11 | 4.3 | a real session, tools, LADO's MCP |

Not for the checklist: at `close`, the step tasks move from Review to done with `waiting for
release` and the release field (the lead's proposal in the plan's State).

## Questions for the human

1. The plan's State says the live runs and the external-provider checks come **before the final
   pull request**; docs/release.md runs `make test-live` at the RC anyway. Run them on the epic
   branch first, as planned, or leave them to the RC? Recommended: OpenCode, Kilo and Codex
   before the final pull request (the providers `providers/` changed most, and a defect is
   cheaper to fix on the epic branch than on a frozen `main`), Claude Code with your yes.

## Decisions

50 rows. With a decision: 48; the recommendation was taken in 36 (2 in a changed form, D29 and
D30, 1 but for one part, D49), partly in 2 (D14, D31), not in 10 (D9, D10, D11, D13, D17, D21,
D24, D26, D27, D28). Without a yes or no: 2 (Q2, D33). Counter lines: 16, with 121 gates and
questions decided as recommended, some of them with a comment.

| Date | Where (step, gate) | Question | Options | Recommended (by whom) | Decided (by whom) | Taken? |
|---|---|---|---|---|---|---|
| 2026-11-01 | intake, round 1 (D1), question #2329 | The epic's key; does it continue an epic | key `lad-154`, a new epic (only `lad-116`, another feature, is in `docs/epics/`) | `lad-154`, new (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D2) | Branch strategy | every step merges into `main`; an epic branch | every step into `main`, leaving the product working: unset means today's behaviour; each step is a minor; steps wait while main is frozen for an RC (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D3) | What "done" means | steps 1–9 of the statement; all 10 | steps 1–9, step 10 (a model for one role) to "Later"; the core value is steps 1–3 (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D4) | Where a model server's key lives | the key itself as a secret of the server; option B of `lad-154-profiles.md`: the connection names a variable, its value comes from LADO's or the project's secrets | option B: a reference by name, the UI offers to create the secret when the address is entered, the value reaches no agent's config file (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D5) | LADO in Docker and a `localhost` address | silent rewrite to `host.docker.internal`; check as given and suggest | check the address as given; when it does not answer in a container, suggest `host.docker.internal` with the same port loudly; never rewrite silently (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D6) | Marking kit sdlc's roles and steps (statement step 7) | in this repository's step; a task of its own in kit sdlc's repository | the power field in LADO is an epic step; kit sdlc's marking is a separate task (`component kit-sdlc`) with `dependencies.lado` on the release that has the field, run as an epic step after that release (lead) | as recommended (human) | yes |
| 2026-11-01 | intake, round 1 (D7) | Checking a model server | a fake OpenAI-compatible server in CI; the human checks steps 3 and 9 by hand on a real server | as described (lead) | as recommended; which server and address the human will add (human) | yes |
| 2026-11-01 | intake, round 1 (D8) | BACKLOG's "Choose the model per agent" (postponed 2026-10-01 until provider-neutral names) | replace by a link to LAD-154 in the epic's first pull request; leave | replace (lead) | as recommended (human) | yes |
| 2026-11-01 | plan_ok, gate #190 (D9) | Approve the plan, whose risks named a minor release per step and main frozen for each RC | approve; reject | approve (lead) | rejected: «я не планирую делать релизы между задачами. Я думаю следующий релиз будет включать весь эпик целиком или мы примем решение о релизе в ходе работы над эпиком.» (human) | no |
| 2026-11-01 | plan_ok, gate #191 (D10) | Approve the plan revised for D9 (steps into `main`, one minor for the epic) | approve; reject | approve (lead) | rejected: «я передумал. Давай сделаем epic-ветку и будем вести разработку в ней. Я могу попросить тебя после некоторых задач помочь мне сделать ручную проверку, чтобы оценить как задача реализована визуально» — an epic branch `epic/lad-154-models` replaces D2; manual visual checks after some steps on request (human) | no |
| 2026-11-01 | S1 (LAD-169), design_ok gate #195 (D11) | The design of S1 (CHANGELOG under the current `0.44.0 (unreleased)`) | approve; reject | approve (lead) | rejected: «я думаю эпик войдет в релиз 0.45.0. Я в скором времени собираюсь выпустить релиз 0.44.0 без этого эпика. Обновления нам надо будет подтянуть» — the epic's lines go under 0.45.0, the epic branch brings `main` in after 0.44.0 (human) | no |
| 2026-11-02 | S2, manual check by the human; question #2509 (D12) | The human's remarks on the launch window's Model field (its note sticks to the field; the field looks unlike the other dropdown fields): fix them, and where in the plan | a step S2b before S3a; S2b after S3a; inside S3b; not fixed, to "Later" | S2b before S3a, with S2's declined launch-window findings F3, F4, E3 (lead) | as recommended (human) | yes |
| 2026-11-02 | step_ok, gate #204 (D13) | Approve S2's review and S3a as the next step | approve; reject | approve (lead) | rejected: «сначала S2b» — as agreed at #2509, S2b goes before S3a (human) | no |
| 2026-11-02 | S2b (LAD-176), question #2515 (D14) | A kept model its CLI's list lacks at a resume (F3), with LADO's own resumes (`lado update`, the container's start) | A: refused at every resume, LADO's own leave it stopped; B: LADO's own start with a warning; C: only warnings | A, with the reason of a session LADO left stopped shown in `lado ls`, on the session in the UI and in `lado update`'s summary, not only in the log (lead); A as the analyst wrote it (analyst) | A without the lead's condition: the reason goes to the server's output and `lado update`'s (human) | partly |
| 2026-11-02 | S3a (LAD-177), questions #2541, #2548, #2551 (D15, replaces D4) | Where a model server's key lives | A: the key is part of the server (asked without echo or read from stdin, never in arguments; later in the server's own file in LADO_HOME, mode 600, given only to that server's agents through their environment); B: LADO's secrets take any name, the server names one; C: an environment variable | A (analyst; lead agreed: LADO's secrets reach every agent's environment, a project's secret does not fit a shared server) | A, after the human asked how a user would add a server in one go (#2541) (human) | yes |
| 2026-11-02 | S3a (LAD-177), design_ok gate #209 (D16) | Approve the design of the model server probe | approve; reject | reject with a case: a gateway answering 400/422 with JSON to every POST and no model list must not count as proving the APIs (lead, against the analyst's design) | rejected with the lead's text (human) | yes |
| 2026-11-02 | step_ok, gate #222 (D17, Q4) | The epic's version now that `main`'s heading is 0.45.0 | `main` releases 0.45.0 when it wants and the epic takes the next minor; 0.45.0 waits for the epic | `main` releases when it wants, the epic in the first minor after it is ready (lead) | «будем выпускать 0.45.0 с main и нашим эпиком» (human) | no |
| 2026-11-02 | step_ok, gate #222 (Q2) | The real model server for the manual checks (D7) | — | — (lead asked) | LM Studio at localhost and an external LiteLLM; tell the human when the check is due (human) | — |
| 2026-11-02 | S3b (LAD-180) at design; the human's message, questions #2715, #2721 (D18) | Where models and model servers are set | the plan's order (a model, then a server's address and key in the launch window from S2/S3b; Settings → Models later in S5a/S5b); models and servers set once in Settings → Models under names, everything else refers to a name | the second, as the concept `concept-models`: S3b′ «Models in settings» next (taking in S5a, S5b), then S3c «A session on a model from settings»; the launch window's free model input removed (only configured models and the CLI's default); a server is an entry models refer to; ready-made models for the installed CLIs (lead, after the human's «задавать модель в диалоге новой сессии — это слишком сложно для пользователя … задавать модели где-то в настройках системы, а в остальных местах … ссылаться на сконфигурированные модели») | «Да, всё как рекомендовано (1 да, 2а, 3 да, 4 да)» (human); run task/lad-180 cancelled, LAD-180 back to Backlog for S3c | yes |
| 2026-11-03 | S3c's review, the human's manual check of S3c; question #2824 (D19) | The four tasks the human created from the manual check (LAD-183 the same address under two names, LAD-184 an embeddings model taken as an agent's, LAD-185 the remove hint names one model, LAD-186 LiteLLM typed Anthropic-compatible) | 1: one step S3e on LAD-186 with the other three in it, before S3d; 2: four steps before S3d; 3: into S3d; later | 1 (lead): S3d's page shows the same checks and refusals, and S3d is near its threshold | 1 (human) | yes |
| 2026-11-03 | step_ok, gate #234 (D20) | Approve S3c's review and S3d as the next step | approve; reject | approve at first; after #2824 (D19) reject (lead) | rejected: «сначала S3e: LAD-183…186» (human) | yes |
| 2026-11-03 | S3e in work; the human's question on external providers (D21) | Check an external provider (OpenRouter, Qwen by key) in S3b's manual check, or later | in S3b's manual check; at the epic's end | in S3b's manual check (lead) | an open check at the epic's end, nothing changed now (human) | no |
| 2026-11-03 | S3d (LAD-187), design_ok gate #240 (D22) | Approve the design of Settings → Models (two lists, explicit entries, ready-made Claude chips) | approve; reject | reject: the human had asked to stop and think over the page's UI/UX first (lead) | rejected: pause for the UI/UX discussion (human) | yes |
| 2026-11-03 | S3d (LAD-187), the human's messages #2879, #2889; question #2890 (D23) | How the Models page works | A: two lists, explicit entries (the design at #240); B: sources (CLIs and saved servers) whose lists are read fresh, models enabled by a tick, names filled in; C: no model entries, pick from sources everywhere | B (lead), with: renaming entries (references hold the entry, not its name); removing a server removes its models after a confirmation listing them (replaces #2733's refusal; `--with-models` in the CLI); no «new model» badge; no ready-made chips | B and all four as recommended (human) | yes |
| 2026-11-03 | S3d (LAD-187), merge_ok gate #242 (D24) | Merge PR #211 (review converged, 5 minor declined) | approve; reject | approve; the manual check on a real LM Studio and gateway after the merge (lead) | rejected: the human's manual check found several problems, and they have remarks on the UI; problems first, the UI after | no |
| 2026-11-03 | S3d (LAD-187), the human's 12 UI remarks #2949; question #2950 (D25) | How to fix the Models page's UI | fixes in build; redesign with a clickable mock-up and a checklist; plus a UI/UX skill task for the kit | redesign with a clickable mock-up on real data volumes and a checklist; the concept questions (why a model has a CLI, where «Other model…» is needed) first; no UI/UX skill: `frontend-design` is visual style, not interaction, and a skill is the kit's change (lead) | as recommended | yes |
| 2026-11-03 | S3d (LAD-187), design_ok gates #244, #246 (D26) | Approve the redesigned Models page (clickable mock-up) | approve; reject | approve both times (lead), warning at #246 that the design grows round after round | rejected twice: #244 with six remarks (models by CLI, a server's model in several CLIs, Refresh, Change), answered by questions #2969, #2978, #2984 as recommended; #246 with the term «CLI» against «Provider» used elsewhere | no |
| 2026-11-03 | S3d (LAD-187), merge_ok gate #253 (D27) | Merge PR #211 after the redesign (review converged at 7d228984, one external round beyond the cap by #3081) | approve; reject | approve; the manual check after the merge together with S3e's (lead) | rejected: «я бы хотел прогнать наши решения по дизайну через ui-design flow, чтобы проверить, на сколько наш дизайн качественный»; the developer held; question #3095 (ui-review or ui-design; the lead recommended ui-review of the built page): the human chose ui-design anew from our decisions, run ui-design/models-page | no |
| 2026-11-03 | S3d (LAD-187), question #3107 after ui-design/models-page (D28) | What to do with the built Models page (PR #211) after the fresh ui-design | (A) merge as is, the redesign as a step S3f before S3b; (B) the differences into this step, tabs kept; (C) the new mock-up whole into this step, no tabs | (A) (lead) | (C): the ui-design mock-up whole, without tabs, in LAD-187; replaces the tabs of gate #244; the design changes AC-8/AC-14 (spec §4, row 13) | no |
| 2026-11-04 | S3d (LAD-187), merge_ok gate #260 (D29) | Merge PR #211 after the redesign (review converged at cb869827) | approve; reject | approve first; after the human's manual check r2 (`pr-211-manual-check-r2`) changed to reject with five points (lead) | rejected with the lead's five points: the key shown in plain text in Key/New key (a security regression of the redesign), Change's Save on a silent address, the phone's model row, one order of agent CLIs, `Saved…` kept; an exact review pass, no external round | yes (the changed recommendation) |
| 2026-11-04 | S3d (LAD-187), merge_ok gate #263 (D30) | Merge PR #211 after the fixes of D29 (review converged at a863eac2) | approve; reject | approve first; after the human's manual check r3 (`pr-211-manual-check-r3`) changed to reject with one point (lead) | rejected with the lead's point: Change clears a rejected New key and a second Save keeps the old key silently; keep it in its field with the refusal and Save off, as Add server does; an e2e test | yes (the changed recommendation) |
| 2026-11-04 | S3d's review, step_ok gate #266 (D31) | Cut the epic after S3b and S4 (the human asked for a sooner release); S5c–S9b to a second epic; Claude/Codex on a server refused in S3b; key-form polish into S4; tasks for the sidebar and the test_tmux flake | approve; reject | approve (lead) | rejected: «Давай оставим S9a и S9b в этом эпике. В остальном согласен» — the epic keeps S3b, S4, S9a, S9b; S5c–S8 go to a second epic; S3b's refusal item dropped (S9a, S9b come before the release); polish into S4; LAD-190 (sidebar), LAD-191 (test_tmux) created | partly (S9a, S9b kept) |
| 2026-11-04 | S3b (LAD-180) brief, question #3263 (D32) | How S3b's launch window is designed: the brief had only «the Model field becomes a choice» and UI e2e | ui-design before design_ok; a mock-up by the analyst only; as in the brief | ui-design before design_ok (lead; S3d was redesigned after its review, D27/D28) | ui-design before design_ok: the launch window's model choice, empty state, refusals and the agent's card | yes |
| 2026-11-04 | The epic's scope, message #3294 (D33) | Cancel D31's split, after the lead explained that one model per session gives no other model during the work | keep the split; cancel it | none asked: the human's own request | cancelled: S5c, S5d, S6, S7, S7b, S8 stay in this epic; S3b's frame unchanged | — |
| 2026-11-05 | Concept v3, question #3338 (D34) | What Settings → Models keeps (the human's #3310, #3316) | built-in and external models as entries (D18, D23); only external models | only external models: a CLI's full list is computed (its built-in models read live plus the external ones), the list adds and never limits; a model reference is external (the entry's id) or built-in (a CLI + a name); one picker everywhere; ticks stay only for a server's model × CLI (lead) | as recommended (human); replaces D18 and D23 where they keep built-in models; custom names of built-in models go | yes |
| 2026-11-05 | Concept v3, question #3338 (D35) | A default model per CLI (#3310, #3316) | none; in the CLI's card | a card per CLI with `Default model`, built-in or external; unset, nothing changes (lead) | as recommended (human) | yes |
| 2026-11-05 | Concept v3, question #3338 (D36) | The launch window's Model field (#3294, #3310) | removed; optional in Advanced, the list by the chosen CLI (variant B) | optional in Advanced, variant B (lead) | as recommended (human); the human's answers #3272, #3279 on the first S3b design (model optional, 1а, 2а, 3а, 4) stand only where this concept keeps them | yes |
| 2026-11-05 | Concept v3, question #3338 (D37) | A name outside the list for a CLI with no full list (Claude; Codex on another provider) | aliases only; «Other name…» for those CLIs, S2's warning | «Other name…» only for them; `lado start --model opus` works (lead) | as recommended (human); replaces D18's answer 2а in part | yes |
| 2026-11-05 | Concept v3, question #3338 (D38) | What goes into an OpenCode or Kilo agent's config | the chosen model's server only; every external model ticked for that CLI | every ticked model, one provider per server, so `/model` offers them; every such server's key reaches each such agent's environment, never a file (lead) | as recommended (human); changes D15's «only to that server's agents» | yes |
| 2026-11-05 | Concept v3, question #3338 (D39) | How the supervisor picks a worker's model | by power only (statement, S8); by name and by power | both: `spawn_worker(model=…)`, `spawn_worker(power=…)`, a new tool `list_models`; a kit still names no model (lead) | as recommended (human); changes the statement's «a power, not a model» and S8's refusal of a name | yes |
| 2026-11-05 | Concept v3, question #3338 (D40) | Several models in one power row (#3310); a row's CLI against the agent's (Q3) | one model, the row's CLI decides (Q3 a); an ordered list | an ordered list: the first model that suits the agent's CLI and works; none: the CLI's default, said on the card; the CLI wins, another CLI only through an explicit `spawn_worker(provider=…)` (lead) | as recommended (human); replaces Q3 (a), P15, P17 | yes |
| 2026-11-05 | Concept v3, question #3338 (D41) | Where the effort lives, now built-in models have no entry | in the model entry (D18); next to the picker | next to the picker (lead) | as recommended (human); changes S4's frame | yes |
| 2026-11-05 | Concept v3, question #3338 (D42) | S5d (the session's table) and S6 (the project's table) | keep; drop | S5d dropped, S6 to «Later»: the Model field and the choice by name cover them (lead) | as recommended (human); changes the statement's three levels and the brief's «done» | yes |
| 2026-11-05 | Concept v3, question #3338 (D43) | The order of the steps; gate #268 | keep; S3f before S3b, S3g after it, S9a and S9b before S5c; #268 reject or the run cancelled | S3f → S3b → S3g → S4 → S9a → S9b → S5c → S7 → S7b → S8; run task/lad-180b cancelled, gate #268 closed by the cancel, its branch and artifacts kept (lead) | as recommended (human) | yes |
| 2026-11-05 | The human's #3511, at gate #279 (D44) | Does a session's model limit its agents? | a session on one model; the model is only where an agent starts | only where it starts: an agent keeps its CLI's built-in models and every external model ticked for that CLI, whatever is chosen; said outright in S3b's brief, title and Check, a test of each case; Claude Code and Codex hold one model per process, so per agent there (lead) | the human's statement; D38 had it for OpenCode and Kilo, the brief's wording read as one model | yes |
| 2026-11-05 | The human's #3518, at gate #279 (D45) | How an external model is told from a built-in one | by the model's name; by a LADO mark | by LADO's reference in LADO (the entry's id, D34) and, inside OpenCode and Kilo, by the provider: an id `lado-…` from the server's id and a label with LADO; a name both saved and built-in stays refused (`check_default`) (lead) | the human's idea; extends the cancelled design's D8 to one provider per server; the human may still change it at `design_ok` | yes |
| 2026-11-05 | S3b's manual check, question #3605 (D46) | `/model` in a LADO agent writes `lado-<id>` into the CLI's shared `model.json`: `--model ''` starts on a LADO model, the human's own CLI remembers a provider it lacks | fix in PR #219; a next step; only document | fix in PR #219: a state folder per OpenCode or Kilo agent (`XDG_STATE_HOME`, moves only the state, checked by `debug paths`), seeded with the user's `model.json` without `lado-…` entries, the user's file only read (lead) | as recommended (human) | yes |
| 2026-11-05 | The epic's scope, the human's #3631, questions #3632, #3634 (D47) | Stop the epic short of power and put the weight on OpenCode and Kilo with local models | the plan as it is; S3g and a clean-up and debugging; S3g, S9a, S9b and debugging | S3b → S3g → a debugging step of OpenCode and Kilo on local models → S9a → S9b → readiness → the final pull request and 0.45.0; S4, S5c, S7, S7b, S8 to a new epic (lead) | the human kept S9a and S9b in the epic (#3633) and took the order as recommended; replaces D43's order and the brief's «done» on effort, power and kit marking; the plan is rewritten at S3b's review and confirmed at step_ok | yes |
| 2026-11-06 | S9a's manual check, question #4030 (D48) | After the human's report: local models are too slow for development; an external provider by key (cloud.ru) | S9a → S11 → release, S9b to the new epic; S9a → S11 → S9b → release; S9a → S9b → release | S9a → S11, S9b to the new epic (lead) | S9a → S11 → S9b → release (human): S9b stays; S11, a closed list on an external provider by key, comes before it | yes |
| 2026-11-07 | S9b's design, question #4538 (D49) | The human saved `OPENROUTER_API_KEY` in the project's secrets: may agents use it for paid runs of Codex on OpenRouter? | Allow, as recommended; the human runs them | Allow: `deepseek/deepseek-v4-flash`, short tasks, a separate `LADO_HOME`, the key piped from its file and never shown, the long session left to the human, the secret removed after the check (lead) | Allowed; the secret need not be removed (the human) | Yes, but for the removal |

Epic: plan_ok gate #194 — approved as recommended (Q1 in S5c; Q3 option (a) with the critic's P15 and P17; Q2 open until S3b's merge); step_ok gate #198 (S2) — approved as recommended; step_ok gate #205 (S2b) — approved as recommended; step_ok gate #222 (S3b, Q6 → LAD-179) — approved as recommended; step_ok gate #225 (D18's plan, S3c) — approved as recommended; step_ok gate #236 (S3e, after D19/D20) — approved as recommended; step_ok gate #239 (S3d), step_ok gate #272 (concept v3's plan, S3f) — approved as recommended; step_ok gate #279 (S3b, with D44, D45 from #3511, #3518; design QA of the running build stays, the human did not object at the gate; #3498: no task) — approved as recommended; step_ok gate #286 (D47's plan, S3g; LAD-209, F3 into LAD-203, the new epic's task at `close`, branch task-lad-180b removed) — approved as recommended; step_ok gate #297 (S10's closed list) — approved as recommended; step_ok gate #304 (S10b, LAD-212) — approved as recommended; step_ok gate #308 (S9a; real Claude Code against a fake server allowed) — approved as recommended; step_ok gate #326 (S11, LAD-220, S9b after it) — approved as recommended; step_ok gate #357 (S9b, LAD-230, OpenRouter the server of its real run) — approved as recommended.
S1: question #2357, gates #196, #197 — approved as recommended
S2: questions #2471, #2501, gates #200, #202, #203 — approved as recommended
S2b: questions #2515 (points 1, 3, 4), #2521 (the lead's «нет» against the developer's proposal), gates #206, #207, #208 — approved as recommended
S3a: questions #2630 (LAD-178), #2699 (Q5 → LAD-181), #2658 (one more build visit for E5, no third external round), gates #210, #220 — approved as recommended
S3c: gates #228, #232, question #2733 (as the analyst recommended; the lead's two additions — re-check models after `--replace`, a warning at saving a Claude/Codex model on a server — not taken, carried to S3b) — approved
S3e: gates #237, #238, questions #2832, #2835 — approved as recommended
S3d: gate #241, questions #2875 (all eight; points 4 and 7 later replaced by D23), #2890, #2913 (LAD-188 into S3b), #2935 (points 3, 4, 8 of the manual check: undo, the page's own refusal lines, CLI in default names), #2969, #2978, #2984, #2995 (the UI says «agent CLI» everywhere, four labels in this step), gate #247, #3081 (review round 5: J2 — the spec, not the code: the key field empties after Add/Save, Cancel and closing the form, Check key keeps it; one external round beyond the cap after the redesign), gate #255 (design_ok of the ui-design mock-up: F11 option 2, 27 files kept in the step, ok notes blue), gate #256 (continue at the review limit), #3134 (one more external round after the scroll blocker L1), gate #257 (continue at the review limit), gate #258 (continue at the review limit), #3151 (N1: fix the hook, not the browser's anchoring; the lead to bring option (b) back if another scroll defect is found), gate #259 (continue at the review limit), #3174 (push over HTTPS through gh while SSH refuses), gate #261 (continue at the review limit), gate #262 (continue at the review limit), #3198 (the ssh case without an agent goes into LAD-162 as a comment, outside the epic), gate #264 (continue at the review limit), gate #265 (approved after the human's manual check r4; N9 and Check key active after a refused key left for a polishing task), gate #243 (rejected as the lead recommended: the review converged before the redesign of D25 reached it) — approved as recommended
S3b: gate #267 (step_ok: the plan of D31 with S9a and S9b kept, S3b started), #3263 (D32: ui-design before design_ok), #3272, #3279 (model optional, 1а, 2а, 3а, 4) — approved as recommended; run task/lad-180b cancelled at design_ok #268 (D43); run task/lad-180c: #3523 (the CLI's settings past a default, a session with no choice follows the default, the sources' words, the http warning for every server of the config, Settings in a new tab) — as recommended; design_ok #280 — approved, with the comment that a resume on a changed default prints `changed model: … -> …`; #3574 (a task for the phone test's flake) — see the review; merge_ok #281 — rejected as recommended: F16, E6, F17–F20 of the second design QA and the external round, the rename of a model under a running agent; the human's manual check after the fixes; #282 rejected for F1 of the manual check (D46); #285 approved after the second round of the manual check
S3g: gate #286; #3655 (a name picks the worker's CLI, a free name needs `provider`, the supervisor does not change a model by itself, a choice is not remembered), design_ok #288 — approved as recommended
S10: gate #297; #3731 (stop after 3 overflows, a warning before the start (1б), small models a named limit, npm's switches, no kept list) — as recommended with 1б, the lead's view; design_ok #300 — approved with the comment: npm's switches only while `@opencode-ai/plugin` is not in OpenCode's config folder (it is OpenCode's own install, once on a fresh `HOME`), a start with no network and the package there measured; #3766 (LAD-212 before the final pull request, LAD-213), merge_ok #302 — approved as recommended; #3822 (main into the epic branch, 4e6ad3bf) — as recommended
S10b: gate #304; #3842 (a TUI plugin reports the prompt's focus, the 30 s mark stays, LM Studio's overflow in LADO's words, the docs link, no repeat) — as recommended; design_ok #305 — approved with the comment: a TUI plugin that never reports, its server plugin alive: after 30 s the agent counts as ready, messages go as today, and the mark says so
S9a: gate #308; #3880 (full, `/model` only the chosen model, the agent lives with the user's `~/.claude`, no login needed) — as recommended; design_ok #310 — approved; merge_ok #313 — rejected as recommended: F1 (the output capped) and F2 (LADO's tools allowed) of the manual check; merge_ok #319 — approved as recommended after the second manual check (#4077): its F1 and F2 go to S11; base merge #4135, #4147 — pushed as recommended
S11: gate #326; #4153 (OpenRouter the second provider, keyless requests allowed), #4163 (no limit of one's own, a warning on a public server, LADO's words, Claude Code 7 repeats, no resume after a 429, cost as an honest line in the docs, a real run on OpenCode and Kilo) — as recommended; design_ok #329 — approved; the premise «cloud.ru lists no context» was the lead's mistake: LADO read only `max_input_tokens`; merge_ok #338 — rejected as recommended after the manual check (#4311): a 400 is not a refusal (cloud.ru's wrong key), Claude Code past its context before compaction at 131072 with the output of 32000, `effortLevel` of the user's settings, the resumes' count; merge_ok #350 — approved as recommended after the third manual check (#4501): steps 3 and 5 on Claude Code passed on cloud.ru; base merge #4525 — pushed as recommended
S9b: gate #357; #4538 (D49), #4550 (the journal read for a Codex agent on a server only, reversing 2026-10-09 for them; one model in `/model`; LM Studio refused by its type, the rest allowed) — as recommended, without the lead's addition of a warning for servers not checked, named again at the gate; design_ok #358 — approved; the analyst's two first runs went to the human's OpenAI login by mistake (two short turns on gpt-6-luna, outside D49's conditions), named to the human; merge_ok #364 — approved as recommended after the manual check (#4676), F15 to «Later» for all CLIs on the human's word; base merge #4695 — pushed as recommended
S3f: questions #3358 (`lado model default`, a question before removing a default, the background read for a built-in default only, the card of a CLI not installed), #3395 (one block: a CLI's card holds its models), gate #274 — approved as recommended; #3421 (the shift at the page's end to a derived task, the line after a stale removal fixed in the step) — as recommended; the two QA passes (ui-review/lad-200-qa, lad-200-qa2) and the manual check on dc3d70e8 (all 8 items; a fake server in place of LM Studio), gate #276 — approved as recommended; #3505 (main into the epic branch with the CHANGELOG conflict joined) — as recommended
