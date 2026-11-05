# Plan: Model and power choice for agents (LAD-154)

## State
Revised by concept v3 (D34–D43, question #3338, 2026-11-05, the artifact `concept-v3`): Settings → Models keeps only external models, a CLI's full list is computed, a model reference is external or built-in, a default model per CLI. Run task/lad-180b cancelled at design_ok #268; S3f added before S3b, S3g after it, S9a and S9b moved before S5c, S5d dropped, S6 to «Later».
Split cancelled (2026-11-04, D33, the human's message #3294: «возможность предоставить CLI все доступные модели - это важно. Давай отменим решение о разделении эпиков?»): D31's move of S5c, S5d, S6, S7, S7b and S8 to a second epic is undone, every step stays in this epic and it ships whole in 0.45.0.
Revised at S3b's design (D18, questions #2715, #2721, 2026-11-02): models and model servers are set once in Settings → Models under names; everything else refers to a name (the concept `concept-models`). S3b's run cancelled; S3c «Models in settings» runs before S3b; S5a and S5b dropped into S3c. At the review S3c split into S3c (store, servers and models from the CLI) and S3d (Settings → Models).
Rejected at `step_ok` (gate #234, 2026-11-03): «сначала S3e: LAD-183…186» (D19, D20; S3e added before S3d)
Rejected at `step_ok` (gate #204, 2026-11-02): «сначала S2b» (D13; S2b added before S3a, question #2509, D12)
Rejected at `plan_ok` (gate #191, 2026-11-01): «я передумал. Давай сделаем epic-ветку и будем вести разработку в ней. Я могу попросить тебя после некоторых задач помочь мне сделать ручную проверку, чтобы оценить как задача реализована визуально»
Rejected at `plan_ok` (gate #190, 2026-11-01): «я не планирую делать релизы между задачами. Я думаю следующий релиз будет включать весь эпик целиком или мы примем решение о релизе в ходе работы над эпиком.»
Phase: steps · Epic run: epic/epic-models · Branch: epic/lad-154-models
In work: none · Next: S3b (LAD-180), S3g, S4, S9a, S9b, S5c, S7, S7b, S8, then readiness · Open checks: Settings → Models in Safari (and Firefox if at hand) by the human before the final pull request: the page does not scroll by itself, the key in dots, the phone width, S3f's picker above a real phone's keyboard (S3d and S3f checked in Chromium only; N5 of S3d's ledger, F21 of S3f's); the human's manual check of S3e on LM Studio and LiteLLM 1.105.1 (LiteLLM's header behaviour reproduced only by a fake), before S3d's design or with it; at `close`, the epic's step tasks move from Review to done with the label `waiting for release` and the release field (the lead's proposal; `.lado/sdlc.md`: «Into an epic branch… the task stays in review»); Kilo reporting the model in `chat.message` (S1), unconfirmed: one `make test-live PROVIDER=kilo` on the epic branch before the final pull request; a resume at the container's start with a CLI not logged in yet must not refuse a kept model falsely (S2b), checked with the live runs; one `make test-live` per provider on the epic branch before the final pull request (Claude Code only with the human's yes); an external provider by key (OpenRouter, Qwen through Alibaba Model Studio) checked by the human at the epic's end, before the final pull request: `probe` and `add` on its address (its path: `/api/v1`, `/compatible-mode/v1`), OpenCode/Kilo agents on it, and a model of a provider the CLI logged in to itself (`openrouter/<model>` from the CLI's list) (the human, 2026-11-03)
Standing rules of the human:
- Every step merges into the epic branch `epic/lad-154-models` and leaves it working; unset means today's behaviour; the epic reaches `main` by one final pull request (D10, replacing D2).
- The epic ships in 0.45.0; 0.44.0 is released from `main` soon without it, and the epic branch takes `main`'s updates (S1 design_ok gate #195, D11; refines D9). 0.45.0 is released from `main` together with the epic: `main` waits for it (step_ok #222, Q4, D17).
- The human checks a model server step by hand on LM Studio at localhost and on an external LiteLLM; the lead tells them when the check is due (step_ok #222, Q2).
- After some steps the human may ask the lead to help with a manual check of how the step looks; the lead then gives the branch, the folder, the commands and what to look at (gate #191, D10).
- Each step's task gets the label `component lado` (kit sdlc's: `component kit-sdlc`) and is linked to LAD-154; LAD-80 is not touched.
Last review: S2, 2026-11-02, base at 228a1de2 (0.44.0 + the unreleased 0.44.1 hotfix LAD-151, Codex's sandbox in the container), merged into the epic branch as 0d18c677: conflicts resolved by joining both sides (CHANGELOG: 0.45.0 above 0.44.1 (unreleased); `tests/smoke/test_smoke.py`: one import line, `CLASSES` and `SANDBOX_ERROR`); `providers/codex.py` merged without conflict; schema on `main` 35, the epic's 37 on top; `make lint`, `make test` (4826 passed, 7 skipped), integration `test_session_model.py` (3 passed), smoke collected (23), `openspec validate --specs --strict` (57) green; CI of the merge runs with S3a's pull request
Last review: S2b, 2026-11-02, base at 228a1de2 (unchanged since S2's review); S2b merged as f2cbf119; `openspec validate --specs --strict` (57) green on the epic branch; the CI of the LAD-151 merge passed with PR #202
Last review: S3a, 2026-11-02, base at 84c8f7c4 (hotfixes LAD-175, LAD-172; `main`'s heading is now `## 0.45.0 (unreleased)`), merged into the epic branch as d6ded361: CHANGELOG resolved into one 0.45.0 section (the epic's lines under `### New`, `main`'s under `### Fixed`); schema on `main` 35, the epic's 37; `make lint`, `make test` (4958 passed, 7 skipped), integration of the merged files (17 passed), `openspec validate --specs --strict` (59) green
Last review: S3c, 2026-11-03, base at 22940ebc (hotfixes LAD-178 #206, LAD-181 #207), merged into the epic branch as 95db9d78: one conflict in `src/lado/cli.py` resolved by keeping both guards (S3c's `model-server` refusal of extra words, then LAD-181's quiet refusal); CHANGELOG merged without conflict (LAD-181's line under `### Fixed`); schema on `main` 35, the epic's 38; `make lint`, `make test` (5112 passed, 7 skipped), integration `test_session_model.py` (3 passed), `openspec validate --specs --strict` (60) green
Last review: S3b's cancelled run (task/lad-180b), 2026-11-05, base at 931818bb (unchanged): nothing to merge
Last review: S3f, 2026-11-05, base at ae840669 (LAD-199 #215, LAD-192 #217), merged into the epic branch as d82bdfba on the human's yes (#3505): one conflict in CHANGELOG, both sides kept; `make lint`, `make test` (5338 passed, 7 skipped), `make web` (1358), `openspec validate --specs --strict` (63) green; UI e2e and integration not run for the merge
Last review: S3d, 2026-11-04, base at 931818bb (unchanged since S3e's review): nothing to merge; S3d merged as e52a547f; CI 23/23 on its last head
Last review: S3e, 2026-11-03, base at 931818bb (LAD-179 #209: CI reruns jobs GitHub gave no runner; its first live run passed on PR #210), merged into the epic branch as 132552ce without conflict; `make lint`, `make test` (5183 passed, 7 skipped), `openspec validate --specs --strict` (60) green

## Steps

Statement steps 1–9 map to S1–S9 (from D18: S3c and S3d «Models in settings» before S3b, S5a into S3c, S5b into S3d; from D43: S3f before S3b, S3g after it, S9a and S9b before S5c, S5d dropped, S6 to «Later»); S3 and S9 split in two, S5 in four (each part merges
alone), S7 gains S7b for kit sdlc's own repository (D6). Statement step 10 is in "Later"
(D3). Every step targets the epic branch `epic/lad-154-models`; after each step the lead
brings `main` into it (D10). A conflict of that merge (migration numbers in `state.py` and
`tests/agent_helpers.previous_schema`, CHANGELOG's heading) is aborted and put to the human
with a recommendation, usually a small sdlc task that brings `main` in and renumbers the
epic's migrations on top of `main`'s (critic P19). No two steps run at once: S3a and S4 both change `cli.py` and the server's API
(`web/openapi.json`, `web/src/api.gen.ts`), the others build on each other.

Rules for every step of LADO (not S7b, which is kit sdlc's own release):
- Its Check includes: a CHANGELOG line under `## 0.45.0 (unreleased)` (one minor for the
  whole epic, D11), a heading the first step adds on the epic branch above `main`'s
  `## 0.44.0`; the epic's migrations number after 0.44.0's; the spec of its capability in `openspec/specs/` (a new one for
  agent models, session models, model servers, power tables) and `openspec validate
  --specs --strict`; `make lint`, `make test`, `make web` when `web/` or the API changed,
  the changed tests with their markers; CI green.
- A step that changes the schema has in its Check: the migration from
  `tests/agent_helpers.previous_schema`; the way back: an `lado update` rollback restores
  `lado.db` from its backup, an older LADO refuses a newer database (`state.py`).
- A model reference (D34) is external (the entry's id) or built-in (a CLI + the CLI's name
  for the model). S2's rows already keep the built-in form, so they need no migration; the
  session's choice stays in the power table's format from S2 on. An entry is an external
  model: a server's model for one CLI. The effort sits next to the reference (D41), not in
  the entry.
- Thresholds of the model check (all steps that take a model; from D18 at saving a model in Settings): a model that is neither
  one of the CLI's aliases nor in the CLI's or server's list starts with a loud warning
  when the CLI gives no list; it is refused before the start when the CLI or the server
  gives a list and the model is not in it.

### S1 — The agent's model is visible (M)
Status: done (LAD-169, PR #194, merged into the epic branch as b377959a; 49 files, schema 35 → 36; CI 23/23, smoke on all four providers). Check open: Kilo's model in its event (State). Checked by hand by the human on another machine from the epic branch at c9f068e3, 2026-11-02: no remarks.
Leftovers: carried into S2 (source `session`, Codex on top of `cli-config`, Kilo, the CLI's event against the session's model, the migration number) and S4 (Claude Code reports no effort; Codex's effort after `/model`); the rest in "Later".
Check:
- Unit and integration tests with the fake agent: each agent in `lado.db` has a model,
  an effort and their source; `list_agents`, `GET` of the session's agents in the API
  and the UI card show them; unset, the card says the CLI's default, and names the model
  where the CLI reports it in its events (Codex's Stop input carries `model`; Claude and
  OpenCode/Kilo checked by the analyst against `docs/design/agents.md`); for Codex the
  model carried from the user's `config.toml` shows with that source.
- Codex's carried model and effort are read by the same rule as `_model_provider`
  (`providers/codex.py`): the chosen profile's, else the top level's.
- The schema migration and the way back (rules above).
- UI e2e of the card, a mockup at `design_ok`; `docs/design/ui.md`, `docs/cli.md` (where
  `lado ls` or `lado log` show it), `docs/design/agents.md` describe what was built.
Notes: no model is chosen yet; this step only learns and shows. No terminal reading
(Events, not screens): a CLI that reports nothing shows "CLI default" without a name.
BACKLOG's "Choose the model per agent" is replaced by a link to LAD-154 here (D8).
The analyst may split the UI card off when the design cannot take it in one round.

### S2 — One model per session (L)
Status: done (LAD-174, PR #201, merged into the epic branch as 69bd2306; schema 36 → 37, `sessions.power`; new spec `session-model`, delta of `agent-model`; CI 23/23, one review round, 0 blockers, 6 minor declined). Checked by hand by the human on another machine from the epic branch at 0d18c677, 2026-11-02: two remarks on the launch window's Model field (its note sticks to the field under the focus ring; the field looks unlike the other dropdown fields) → S2b. Born in the step: LAD-175 (Later).
Leftovers: F2 and `real_clis.with_model` carried into S4; F3, F4, E3 and the manual check's remarks into S2b; Q2, F5 and Codex's list path in smoke to "Later".
Check:
- `lado start --model <model>` and a field in the launch window's Advanced; the session
  keeps it (in the table's format); every agent of the session's CLI starts on it through
  the CLI's own way (Claude `--settings`/`--model`, Codex `CODEX_HOME` on top of the
  carried user value, OpenCode/Kilo config content); S1's card shows it with the source
  "session".
- The model check by the thresholds above; an agent of another CLI in the same session
  (a worker started with another provider) keeps its CLI's default and its card and
  `spawn_worker`'s warnings say so (no silent drop).
- Smoke per provider (CI): the model reaches the real CLI's argv or config.
- The schema migration and the way back (rules above).
- UI e2e and mockup; `docs/cli.md`, `docs/design/ui.md` describe what was built.
- From S1: the session's model is a new source next to `cli` and `cli-config`
  (`state.source_words`), with no change of the agent's six columns; for Codex it goes
  on top of the model carried from `config.toml`; a Kilo card shows the session's model
  even when Kilo reports none; the design says what the card shows when a CLI's event
  names another model than the session's (`/model`); the migration numbers after
  `main`'s.
Notes: walking skeleton: choose → reaches the CLI → visible. A model is a CLI + a model;
which CLI's models the field offers comes from the session's provider. Free input with a
check, no catalogue of LADO's own.

### S2b — The launch window's Model field: its look and small fixes (S)
Status: done (LAD-176, PR #202, merged into the epic branch as f2cbf119; tweak, no schema or API change; the window's own combobox `SuggestField`, the note inside its `.field`; every resume checks the kept model, LADO's own resumes leave it stopped with the reason in the server's output and `lado update`'s (D14); CI green, review 2 rounds, 0 blockers, 4 minor declined). The human set out to check the PR's branch by hand before #207 and approved without remarks.
Leftovers: L1, L2, E1, E2 and the reason of a LADO resume in `lado ls`/UI (D14) to "Later"; the false refusal without a CLI login to the open checks.
Check:
- From the human's manual check of S2 (screenshot at question #2509): the field's note
  (refusal, warning, check) stands below the field with the same gap as the other
  fields' notes and is never covered by the focus ring; the Model field looks like the
  window's other dropdown fields (Provider, Permission mode): the same arrow, height,
  border and width rules, while keeping free input with the CLI's suggestions (no
  catalogue of LADO's own).
- From S2's ledger: `lado start --model` trims spaces as the UI does (F4); a failed
  model list is not kept in the server's cache (E3); Resume and `lado start <session>`
  treat a saved model that left the CLI's list the same way, and the window says how to
  go on (clear the field or pick another) (F3).
- UI e2e of the field (note placement, focus, the look next to Provider), screenshots
  for the human; unit tests of F4 and E3; `docs/design/ui.md` describes what was built;
  a CHANGELOG line only if users of 0.45.0 see a difference from its S2 line (else none).
Touches: `web/src/Launch.tsx`, `web/src/styles.css`, `cli.py` (trim),
`server/launch.py` (cache).
Notes: no schema or API change. S3b builds the server's address field in the same
Advanced section on this field's component, so it comes before S3a. A widening beyond
the Model field (other fields of the window) is a question to the human.

### S3a — Find out what a model server is (M)
Status: done (LAD-177, PR #203, merged into the epic branch as cf072b9d; `lado model-server probe <address> [--key]`, new spec `model-servers`, `Provider.server_api`; no schema, API or UI change; a control POST to a path that cannot exist tells a gateway answering 400 to everything (D16); the key is part of the server, asked without echo or read from stdin, never in arguments (D15, replaces D4); review 4 local and 2 external rounds, 8 findings fixed, E5 (the key printed through `--help`) closed by the parser's own `error()`; CI 23/23; the openspec archive tried before the review: no return after merge_ok).
Leftovers: E3 (no warning when the key goes over `http://`) and D15 into S3b; D15 into S5a; F3 (a key over 64 KiB) to "Later"; found on the way: `lado project set --secret` prints a value starting with `-` (a question to the human: a task and a hotfix to `main`).
Check:
- Against fake servers in tests (an OpenAI-compatible `/v1/models`, Ollama, LM Studio, an
  Anthropic-compatible one): given only an address (and a key by name, D4), LADO names
  the server's type, its models and the CLIs that can use it; an address that does not
  answer, a 401 and an unknown server give a clear message.
- Compatibility rule: an OpenAI-compatible server (chat completions) is named usable by
  OpenCode and Kilo; one that answers the Responses API by Codex; one that answers the
  Anthropic Messages API by Claude Code; the fake servers prove each yes and each no
  (which request proves each API is the analyst's call).
- In Docker, `localhost`/`127.0.0.1` that does not answer gives the loud hint
  `host.docker.internal:<port>` (D5); never a silent rewrite; no network scan.
- `docs/cli.md` describes the command.
Notes: no session uses the result yet; S3b does; S9a and S9b rest on its rule.

### S3c — Models in settings: the store, servers and models from the CLI (M)
Status: done (LAD-182, PR #208, merged as acc2b129; added at S3b's design on D18, question #2721; runs before S3d and S3b; takes in S5a; split from «Models in settings» at the review: a schema change with an interface and two capabilities the user sees, `epic-files`)
Check:
- A store of the user's settings on the server (in `lado.db` or `LADO_HOME`, the
  analyst's call); the schema migration (or the new file) and the way back (rules above);
  `lado uninstall` removes it with `LADO_HOME`.
- A model server is an entry of its own (D18, answer 3): a name, an address and a key;
  `lado model-server add/list/remove` (S3a's `probe` stays): on adding, S3a's probe names
  its type, models and CLIs and refuses an address that does not answer; the key is part
  of the server (D15): asked without echo or read from stdin as S3a's `--key`, kept in the
  server's own file under `LADO_HOME` (mode 600), never in `lado.db`, LADO's shared
  `secrets/`, arguments, output, log or error text (canary test, LAD-116; the parser's
  own `error()` as S3a's); removing a server removes its key file; in Docker, a
  `localhost` that does not answer gives the loud `host.docker.internal` hint (D5); from
  S3a (E3): a key over `http://` to an address that is neither `localhost` nor a private
  network gives a loud warning.
- A configured model is an entry: a name, a CLI, the CLI's model and an optional server;
  `lado model add/list/remove`; on adding, the model is checked (S2's thresholds, now
  here) and the server must suit the CLI (S3a's rule).
- `lado doctor` checks the saved servers (answer, key taken).
- Removing a model or server a session uses: that session's next start or agent refuses
  loudly, naming it (once S3b makes sessions use them; here the rule in the store).
- The server's API (for S3d's UI) when the analyst finds it simpler to add now; else S3d.
- `docs/cli.md`, `docs/design/modules.md` describe what was built.
Notes: no session uses the entries yet; S3b does. The store is the one place of the
user's later settings (the power table of S5c), not a second format.

### S3e — Fixes from the manual check of the model server commands (S)
Status: done (LAD-186 with LAD-183, LAD-184, LAD-185, PR #210, merged as 27679604; approved at step_ok #236; created by the human after the manual check of S3c on LM Studio and LiteLLM 1.105.1; one step on D19, question #2824; runs before S3d)
Check:
- LAD-186: a gateway that speaks both APIs (LiteLLM) is typed OpenAI-compatible: the
  model list is asked without `anthropic-version` (or as the design finds, within the
  probe's request limits); the spec `model-servers`' scenario «The server's type» corrected;
  a test with a fake server that changes its list's form by the header.
- LAD-184: a model the server marks as embeddings (LM Studio's `type` in
  `/api/v0/models`) is refused or warned at `lado model add`; a server with no such mark
  stays as today.
- LAD-183: `lado model-server add` names a saved server with the same address after the
  probe's normalisation; a refusal or a warning is the design's call (two keys on one
  address may be wanted).
- LAD-185: the refusal to remove a server used by models covers every model (a command
  each, or `lado model remove` taking several names).
- `docs/cli.md`, the specs and CHANGELOG's line under 0.45.0 describe what was built.
Notes: the integrator updates all four tasks and links them to LAD-154; S3d's page reuses
the corrected type, refusals and hint.

### S3d — Models in settings: Settings → Models (M)
Status: done (LAD-187, PR #211, merged into the epic branch as e52a547f; redesigned through ui-design on D27/D28; 13 review rounds, the human's manual checks r1–r4 (D29, D30); CI 23/23; approved at step_ok #239; split from «Models in settings» at the review; runs after S3e, before S3b; takes in S5b)
Check:
- Settings → Models: «Servers» (add by name, address and key in a password field, S3a's
  result shown; remove) and «Models» (name, CLI, the CLI's model with suggestions from the
  CLI's aliases and list or the server's list on S2b's `SuggestField`, an optional server;
  remove); the same checks as S3c's commands, shown under the fields as S2b's notes.
- Ready-made entries for the installed CLIs («Claude: haiku / sonnet / opus») added in
  one click (D18, answer 4).
- UI e2e and a mockup at `design_ok` that shows the page next to Settings' other pages;
  screenshots for the human; `docs/design/ui.md`.
Notes: the human's manual check of the page is likely (gate #191's standing rule).
From S3c (LAD-182): S3c added no API method (only what is used), so S3d adds the server's
API for servers and models over `model_settings.py`, the key only going in, never out
(canary test, LAD-116); a model is changed by removing and adding it (no `--replace` for
models); removing a server some models use is refused naming them, and the page shows that
refusal.
Reshaped by D23 (question #2890, the cases in `ux-models-cases`): sources (CLIs and saved
servers) whose model lists are read fresh on expanding or Refresh; a model enabled by a
tick, its name filled in and renamable; removing a server removes its models after a
confirmation (`--with-models` in the CLI); no ready-made chips, no «new model» badge.
From S3e (LAD-186): the page shows the `(embeddings)` mark and the `same address as model
server "<name>"` line the commands print, and uses `lado model remove`'s several names where
it helps; `Probe.models_why` keeps a stale reason when the list came from the request with
`anthropic-version` (E1, invisible today): clear it if the page's API shows the reason.

### S3f — Settings → Models: external models and a default per CLI (M)
Status: done (LAD-200, PR #216, merged as 540ab41a; two design QA passes, the human's manual check on a fake server; gate #276)
Check:
- Settings → Models keeps only external models (D34): the ticks of built-in models and
  their custom names go, the ticks of a server's model × CLI stay; the block of agent CLIs
  becomes a card per CLI with `Default model` (D35). The blocks of servers, Add, Change and
  the key's handling do not change (four manual checks of S3d stand).
- One picker (D34), a component the launch window and the table rows reuse: «the CLI's own
  settings», built-in models read live from the CLI, external models; a search for a long
  list (Kilo gives 321); «Other name…» only for a CLI with no full list, with S2's warning
  (D37). Unset, nothing changes.
- A CLI's full list is computed in one place (server's API), never stored; a CLI whose
  list cannot be read shows why.
- `lado model add` takes external models only; a `lado model` command sets and clears a
  CLI's default.
- The store: `models.id` (from S3b; from S3d's D8: an entry's name is renamable, so
  references hold the id), a CLI's default as a model reference; rows without a server go
  (they exist only on the epic branch's stands). The migration 38 → 39 and the way back
  (rules above).
- Removing a server or a model a default uses: the confirmation names it and the default
  is cleared; a built-in default the CLI's list lost is shown on the card, not dropped
  silently.
- UI/UX first (D32, moved here from S3b; D43): the step's `design` runs the flow `ui-design`
  on the picker across the CLI's card, the launch window's Model field and a power row, so
  S3b and S5c build the same picker; input: `ui-design/launch-model` with its variant B.
- Design QA before the human's manual check (the human's message #3415): the flow `ui-review`
  on the running build's URL, which the lead gives the critic (the critic builds nothing),
  against `ui-design/model-picker` and the design; the scenarios walked by actions, refusals
  and 390 px included.
- UI e2e, vitest, `make web-types`; the human's manual check; `docs/design/ui.md`,
  `docs/cli.md`.
Notes: the default is stored and shown here and applied to agents in S3b. Measured: 18 code files of the threshold's 25; the migration 38 → 39 and `models.id` are done here.

### S3b — A session on a model reference (L)
Status: planned (LAD-180; runs task/lad-180 and task/lad-180b cancelled at design, D18 and D43; rewritten by D34–D43)
Check:
- An agent starts on the session's model when one is chosen, else on its CLI's default
  (D35), else as today; a worker of another CLI takes its own CLI's default. The card says
  which, with its source.
- The session's model is where an agent starts, not a limit (D44): whatever is chosen, a
  built-in model, an external one or nothing, an OpenCode or Kilo agent has its built-in
  models and every external model ticked for its CLI in `/model`; a test of each case.
  Claude Code and Codex hold one model per process: the choice there is per agent (S3g,
  S9a, S9b).
- The launch window: the Model field stays optional in Advanced, S3f's picker, the list by
  the chosen CLI, the default preselected (D36, variant B); no address or key shown.
  `lado start --model <name>` takes a built-in name of the session's CLI or an external
  model's name (D37), by S2's check.
- OpenCode and Kilo: every external model ticked for the CLI goes into each agent's config
  content (D38), one OpenAI-compatible provider per server, each key only in the agent's
  environment through `{env:…}`, so `/model` offers them next to the built-in models
  (additive: checked on OpenCode 1.18.35, 10 + 2, and Kilo 7.8.8, 321 + 2, by `<cli>
  models` only); a real agent and `/model` on two servers are checked in this step's
  design. A canary test (LAD-116): no key in a config file, `lado.db`, output, log or
  error text.
- Before the start (and every resume, by S2b's rule) LADO checks the server of the model
  the agent starts on: it answers and has the model, else a loud refusal; a server that does
  not answer at LADO's own resume leaves the session stopped with the reason (3а of #2706).
  A silent server of another ticked model does not stop the start. An agent of a CLI the
  server does not suit (Claude or Codex before S9a/S9b) is refused at its start, naming the
  server's CLIs.
- From S3a (E3): a key sent over `http://` to an address that is neither `localhost` nor
  a private network gives a loud warning before the start.
- From S3d (question #2995): the launch window says «agent CLI».
- LAD-188 (question #2913): two flaky tests of the epic's own, seen on PR #211's CI and
  green on rerun — `web/src/Launch.test.tsx:1077` (the Model field's listbox looked up
  synchronously after `findByText`, LAD-176) and `test_session_model.py::
  test_a_worker_of_another_cli_runs_its_default_and_says_so` (a worker of another CLI got
  the session's model, LAD-174): both stable, and №2 told apart as a race of the test or of
  the product. The first design found the product's side: the inherit mode leaks the model
  (its D14, `LADO_LAUNCH_VARS`).
- From S2 (F2): `PowerTable.from_json` reads a row with an unknown or missing key and a
  broken row without breaking every session; a unit test of each case. A row now holds a
  model reference (D34): an external one is new, S2's rows stay as they are.
- S1's card: «Локальная Qwen · qwen3-8b · server <address>» with its source; Kilo's card
  shows the session's model even when Kilo reports none.
- From S3f (proposal, Out of scope): `lado doctor` says what it finds on a default once agents run on it (a default on a server gone silent, a built-in name no longer listed). Its picker is `web/src/ModelPicker.tsx`, a typed name goes through `model_settings.check_default`, the list through `model_settings.choices`: S3b adds no second way.
- UI: the launch window follows S3f's checked mock-up; a further `ui-design` only for what
  it left out (the refusals, the agent's card).
- The human's manual check before the merge on LM Studio at localhost and an external
  LiteLLM (Q2), with a real session (S3f's manual check ran on a fake server and read item 8 in the code); the lead tells them when it is due. In Docker, LM Studio on their machine
  is `host.docker.internal`.
- Smoke (CI): OpenCode and Kilo with a fake server; UI e2e of the field; `docs/install.md`
  (local models, Docker), `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`.
Notes: the core value of the epic. Rests on S3c's store and S3f. Reuse from the cancelled
run (branch `lado/lad-154-epic/task-lad-180b`, artifact `task/lad-180b/design`): D8 (the
provider, the key's variable; per server now; the first fetch of the npm package over 60 s
is a risk), D13, D14, the refusals' texts.

### S3g — A worker on a model by name (S)
Status: planned
Check:
- A new MCP tool `list_models` shows the supervisor the models of the session's CLIs: name,
  CLI, server; `spawn_worker(model=…)` starts a worker on a model reference (D39); a name
  of no list is refused loudly; `model` against an explicit `provider` of another CLI is
  refused naming both; the card's source says «supervisor».
- From S3b (LAD-180, the human's answer 3a, #3279; moved from S8): `spawn_worker` checks the
  model's server as the start does and refuses with the reason.
- The supervisor's text and the MCP tools' descriptions say how to choose; a kit still names
  no model.
- Integration test with the fake agent through `lado mcp`; `docs/design/agents.md`.

### S4 — Effort with the model (S)
Status: planned
Check:
- The effort sits next to S3f's picker (D41): the CLI's card, the launch window, and later a
  power row; `lado start --effort`; Claude (`--effort`/settings), Codex
  (`model_reasoning_effort` on top of the carried value), OpenCode/Kilo (variant) get it;
  where the CLI or the model cannot take it, a loud warning before the start; S1's card
  shows it.
- Unit tests per provider, smoke per provider (CI); `docs/cli.md`, `docs/design/ui.md`.
- From S2 (F2): done in S3b (a row's tolerant reading); the row keeps the effort next to the
  model reference (D41).
- From S2 (found on the way): `tests/real_clis.with_model` rebuilds `Launch` and drops
  its `model` and `effort`; S4's smoke passes them through.
- From S1: Claude Code reports no effort in its events, so its card shows the effort
  S4 sets with the source "session"; Codex's effort after a `/model` in the CLI stays
  "your Codex config" (no hook reports it): S4's design says whether that holds.
- From S3d (LAD-187, the ledger's N9 and the human's manual check r4): the key field of
  Add server and Change is off while Save or Add checks the server, so a key typed then
  is not lost; Check key is off after a refused key until the key is edited, as Add
  server is.
Notes: the CLIs' scales differ (research §1.3); LADO passes the CLI's own value and keeps
no common scale.

### S9a — A model server for Claude Code (M)
Status: planned
Check:
- A configured model of Claude Code whose server is Anthropic-compatible (S3a names it)
  runs Claude Code agents through `ANTHROPIC_BASE_URL` in the agent's own environment, the
  key from the server's entry (D15) only in that environment; a server that
  is not Anthropic-compatible refuses Claude loudly before the start.
- An external model takes the whole process (one address, one provider): the picker says so,
  and such an agent's `/model` offers only what the server gives, unless a gateway serves
  both (what `/model` shows there is checked here).
- Smoke (CI) with a fake Anthropic-compatible endpoint; the human's manual check on a real
  server (D7); `docs/install.md`, `docs/design/agents.md`.

### S9b — A model server for Codex (M)
Status: planned
Check:
- A configured model of Codex whose server has the Responses API runs Codex agents through
  a `model_providers` entry in the agent's `CODEX_HOME` (on top of the carried user values),
  the key from the server's entry (D15) only in the agent's environment; a server
  without the Responses API refuses Codex loudly before the start.
- From S3d (the human's manual check of PR #211): Settings → Models offers a Codex column on
  LM Studio, but LM Studio's Responses API drops Codex's MCP tools (type `namespace`,
  `tests/local_models.py`, `docs/testing.md`), so a Codex agent there cannot talk to LADO:
  either refused loudly before the start (and the column says so), or proven to work.
- An external model takes the whole process (one address, one provider): the picker says so,
  and such an agent's `/model` offers only what the server gives, unless a gateway serves
  both (what `/model` shows there is checked here).
- Smoke (CI) with a fake endpoint; the human's manual check (D7); `docs/install.md`,
  `docs/design/agents.md`.

### S5a — The user's settings store and model servers in the CLI (M)
Status: dropped (taken into S3c on D18, question #2721)
Check:
- A store of the user's settings on the server (in `lado.db` or `LADO_HOME`; the
  analyst's call); a `lado` command adds a model server by address (S3a's probe; its key
  part of the server, D15: asked without echo or from stdin, kept in the server's own
  file, mode 600, given only to its agents' environment), lists and removes it; `lado
  start` takes a saved server by name; `lado doctor` checks the saved servers (answers,
  the key is taken).
- Removing a server a session uses: the session's next agent refuses loudly at start;
  removing a server removes its key file; a session's own server (S3b) moves to a saved
  one without asking for its key again.
- The schema migration (or the new file) and the way back (rules above); `lado
  uninstall` removes the settings with `LADO_HOME`.
- `docs/cli.md`, `docs/design/modules.md` describe what was built.

### S5b — Model servers in Settings and the launch window (M)
Status: dropped (taken into S3d on D18, question #2721)
Check:
- Settings → Models lists the saved servers: add by address with S3a's result shown, a
  key by name with the offer to create the secret, remove; the launch window chooses a
  saved server.
- UI e2e, mockup at `design_ok`; `docs/design/ui.md`.

### S5c — The user's power table (M)
Status: planned
Check:
- The user's table light / normal / heavy, each row an ordered list of model references
  on S3f's picker (D40), built-in and external, set in Settings → Models and by a `lado`
  command; an agent takes the row's first model that suits its CLI and works; none, or an
  empty row: the CLI's default, said on the card; with no one choosing a row an agent takes
  "normal"; S1's card names the row ("normal work, user table").
- The agent's CLI wins over a row (D40): another CLI only through an explicit
  `spawn_worker(provider=…)`; the login check goes by the agent's CLI as today.
- The launch window shows one summary line of the rows the session will take («Модели:
  обычная — …, сильная — … из ваших настроек»), with a link to Settings (concept §3).
- The table is kept in S3c's store: the schema is unchanged when S3c's store holds it,
  else the migration and the way back (rules above).
- Unit tests of the resolution; UI e2e, mockup; `docs/design/ui.md`, `docs/cli.md`.
Notes: light and heavy take effect from S7/S8, when roles, steps and the supervisor choose
a row. A ready-made table over built-in models («Claude: haiku / sonnet / opus») here (Q1).

### S5d — The session's table row by row (S)
Status: dropped (D42: the launch window's Model field and the choice by name cover its cases)

### S6 — The project's power table (S)
Status: dropped to «Later» (D42)

### S7 — Power on roles and flow steps (M)
Status: planned
Check:
- A role (`agents/<role>.md`) and a flow step take a power (light / normal / heavy); an
  agent of that role or step gets that row; a value outside the three is a load error; the
  kit docs say a kit with the field needs `dependencies.lado: ">=<this release>"`, and
  `kits.warnings()` asks for it as it does for `expects`.
- Unit tests of the kit and flow loaders, integration test with the fake agent: a role's
  power reaches the agent's model; docs of the kit format.
Notes: the strict keys (`kits.AGENT_KEYS`, `flows.STATE_KEYS`) mean an older LADO refuses
such a kit; `dependencies.lado` makes the refusal clear.

### S7b — Kit sdlc's roles and steps marked (S)
Status: planned
Check: kit sdlc (its own repository) marks its roles and steps with a power and
`dependencies.lado` on the LADO release that ships S7; a session with that kit shows each
role's row on its cards (checked against LADO's epic branch before that release).
Status of its check: open until the LADO release that carries the epic (D9): kit sdlc's
pull request merges and is released by kit sdlc's own rules only after it.
Notes: tracker task with `component kit-sdlc` (D6). With no LADO release mid-epic (D9) it
is built during the epic and waits for that release to merge.

### S8 — Power when the supervisor spawns a worker (S)
Status: planned
Check:
- `spawn_worker(power=…)` takes a power and overrides the role's and the step's; `list_models`
  (S3g) shows each model's rows; `power` with `model` together is refused loudly; the
  card names the source ("supervisor").
- Integration test with the fake agent through `lado mcp`; `docs/design/agents.md`, the
  MCP tool's description.

## Open questions

- Q1 (decided at `plan_ok` #194: in S5c). Ready-made tables («Claude: haiku / sonnet / opus», «Всё на сервере») go with the
  user's table in S5c, not with S7 as the statement had it: they are the table's UI and
  need nothing of S7. Recommended: in S5c.
- Q2 (answered at `step_ok` #222). LM Studio at localhost, and an external LiteLLM the
  human wants to try; the lead tells them when the check is due.
- Q3 (decided at `plan_ok` #194: (a) with P15 and P17; replaced by D40: the agent's CLI wins, a row is an ordered list). A table row names a CLI (heavy → Claude opus); the agent's provider may come from
  elsewhere (the session's `--provider`, `spawn_worker`'s provider). Options: (a) the
  row's CLI decides the agent's CLI; an explicit `--provider` of the session (only one
  the human chose: `lado start --provider`, or a provider picked in the launch window
  rather than its default; not the value the session keeps for its resume; critic P17)
  is the session level and overrides the CLI of the user's and the project's rows (each level
  overrides only where it says something; critic P15); without it the session's provider
  is only the default for agents whose row is empty; the login check goes by the CLI the
  agent resolves to; a provider passed explicitly to `spawn_worker` that differs from the
  row is refused loudly, naming both; (b) the provider always wins and the row
  is used only when its CLI matches, otherwise the CLI's default with a loud warning;
  (c) any mismatch is refused. Recommended: (a): the row is a model and a model is a CLI
  + a model (statement), the explicit conflict is the only one a human or supervisor made
  on purpose, and nothing is replaced silently.
- Q4 (answered at `step_ok` #222: «будем выпускать 0.45.0 с main и нашим эпиком» — 0.45.0
  waits for the epic; D17). Asked at S3a's review: `main`'s heading is now `## 0.45.0 (unreleased)` (LAD-172,
  a change of the MCP tools' behaviour, and LAD-151): if `main` releases 0.45.0 before
  the epic is done, the epic ships in 0.46.0 and its lines move under that heading at
  readiness. Recommended: let `main` release 0.45.0 when it wants, the epic takes the next
  minor; the standing rule "the epic ships in 0.45.0" becomes "in the first minor after the
  epic is ready".
- Q5 (answered at question #2699: «Да, заведи задачу» → LAD-181, a hotfix into `main`, outside the epic; fixed in `main` by PR #207, in the epic branch since S3c's review). Asked at S3a's review: `lado project set --secret` prints a value that starts with
  `-` (found at S3a's review, already in `main`). Recommended: a task of its own, a hotfix
  into `main`, outside the epic.
- Q6 (answered at `step_ok` #222: «создай. Разберемся отдельно» → LAD-179, outside the
  epic). Asked at S3a's review: The second macOS smoke job cancelled without a runner
  (PR #203). Recommended: a task to find the cause (not our `timeout-minutes`).

## Later

- At the very end of Settings → Models, closing a form moves what the human works with (89 px; the known limit of S3f's one block, #3421) — LAD-201 (derived from LAD-200).
- The picker: model ids in mono as the mock-up says, the highlight after a failed request to LADO (F22, F24 of S3f's review, declined; the human's check was clean) — LAD-202 (derived from LAD-200).
- `web/src/SystemPanel.test.tsx` depends on the locale, `make web` fails on a Russian one (S3f's manual check; also on `main`) — LAD-203 (derived from LAD-200).
- Flaky UI test of the section Models staying at the top, one 451 for 0, cause not proved (S3f's review) — LAD-204 (derived from LAD-200).
- The project's power table (S6) — dropped from the epic (D42) — LAD-154 — if a project ever needs its own rows.
- The session's table row by row (S5d) — dropped (D42), no plan to bring it back.
- The sidebar stays expanded when the window is narrowed (seen in S3d's manual checks,
  outside the epic) — LAD-190 (D31, derived from LAD-187).
- Flaky `tests/test_tmux.py::test_popup_opens_on_the_clients_attached_to_the_session`
  (seen on PR #211's CI, green on rerun, outside the epic's code) — LAD-191 (D31, derived from LAD-187).
- A model for one role (statement step 10) — not needed yet (D3) — LAD-154 — after S7, if
  a power row is too coarse.
- Profiles with a default model set — LAD-80 — the table's format is the "saved table"
  they would name (`lad-154-profiles.md`, option B).
- Named model sets («Экономный», «Максимум», «Локально») — out of the statement — none —
  the user table of S5c is the one set until profiles come.
- Automatic power by task complexity; fallback models on an error — out of the epic
  (statement).
- The model in `lado log` and the `spawned` event — S1 left them out (proposal, Out of
  scope) — LAD-169 — when the log is asked for it.
- A model change in Claude Code's own terminal (`/model`) shows only at its next
  SessionStart — S1 (Events, not screens) — LAD-169 — if Claude Code gets a hook that
  names the model on a change.
- `lado ls`: a model name over 18 characters shifts the branch column (E3, declined at
  S1's review) — LAD-169 — with the next change of `lado ls`.
- Codex's hooks record the model in a short write transaction even when nothing changed
  (F4, declined) — LAD-169 — if hooks ever show up in profiling.
- The card's source turns `cli` where the CLI names the session's model under another
  name: Bedrock/Vertex ids (`us.anthropic.…`), names OpenCode/Kilo normalise (F5/Q1,
  unverifiable at S2) — LAD-174 — with S9b (Claude Code on a server) or when a user meets it.
- A Codex profile or model in the repository's own `.codex/config.toml` may override the
  session's model; the card then says `cli` (Q2, unverifiable at S2) — LAD-174 — check
  with the open live run of Codex.
- Codex's path with a model list is not walked by the smoke (S2's residual risk) —
  LAD-174 — with the open live runs before the final pull request.
- The launch window after S2b (LAD-176, declined at its review): the "Use <CLI>'s default"
  button is in the monospace `.chip-button` font (L2); a failed or hanging model list is
  asked again at each check, no single-flight (L1); SuggestField's list stays shown for a
  moment when the field turns disabled (E1); the Where and Branch fields could move onto
  `SuggestField` — with the next change of the launch window (S3b adds the server's field).
- A session LADO's own resume (`lado update`, the container's start) left stopped because
  its kept model left the CLI's list shows the reason only in the server's output and
  `lado update`'s, not in `lado ls` or on the session in the UI (D14, the lead's
  condition not taken); each such resume asks the CLI's list, up to 15 s a session, one
  after another (E2) — LAD-176 — if the human meets it.
- macOS smoke jobs cancelled without a runner: PR #202 (run 41496744121, 15 min) and
  PR #203 (smoke macos opencode, 23 min); not our `timeout-minutes` of 20 — no task yet
  (question #2521: «нет»); at the second occurrence the human said create: LAD-179
  (outside the epic, derived from LAD-177).
- Flaky container test of the Go toolchain (`mise install` over 600 s) — LAD-178
  (derived from LAD-177, outside the epic) — fixed in `main` by PR #206, in the epic branch
  since S3c's review.
- A model server's key over 64 KiB is refused by S3a's probe (F3, declined) — LAD-177 —
  if a real gateway's key is ever that long.
- Flaky Codex smoke: Codex's own background `git ls-remote` to `openai/plugins` outlives
  the test — LAD-175 (Backlog, derived from LAD-174, outside the epic) — its fix (turning
  the sync off in the agent's own Codex config) helps every step that touches `providers/`.
- S3c's small edges (LAD-182, the ledger's «not checked»): `lado doctor` names an unreadable
  key twice in one line; a key write refused midway leaves an empty server folder that
  `doctor` names as left over — if the human meets them.
- S3c's declined findings (LAD-182): the plain-`http://` warning also fires for CGNAT
  `100.64/10` and private DNS names (F10, D6: names are not resolved) — an extra warning,
  never a missing one; `--help=<key>` exits 0 on Python 3.11+ (F4) — the key is not shown.
- Changing a configured model in place (`--replace` for models), renaming a server or a
  model, removing a server's key alone: out of S3c's frame (remove and add again) — LAD-182
  — when the human asks; S3d's page follows the same rule.
- S3e's declined findings (LAD-186): a port out of range in a hand-edited `lado.db` row breaks
  `same_address` (E2, unreachable through LADO); `lado model remove`'s «all or none» help is
  inexact only when two processes race (E3, D5 documents it) — if the human meets them.
- A server saved with a wrong type before S3e keeps it until `--replace` (LAD-186, D7, no
  migration: unreleased, test stands only) — on the human's stand: replace the LiteLLM entry
  once.
- The project's mockup rule (`.lado/sdlc.md`, the Analyst and Review traps) names only
  `html, body`; a mockup shown in LADO also needs `.content` overridden (`overflow`,
  `overscroll-behavior`, `min-height`), or the wheel sticks in it past 900 px (LAD-187's
  analyst) — the human edits the rule; not the epic's file.
