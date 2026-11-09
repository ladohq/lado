Task: LAD-258

## Why

The manual check of 0.45.0rc1 (2026-11-09, session artifact `rc-report-0.45.0rc1-c825a281.md`,
"Расхождения чеклиста с кодом") found six places where `docs/releases/0.45.0.md` or
`docs/release.md` expect something the product rightly does not do, or give a recipe that does
not run as written. The fixes merged after rc1 (LAD-253, LAD-254, LAD-255, LAD-256) need their
checks in the section `## 0.45.0rc2`, written before the RC's commit (docs/release.md, section 2,
step 0), together with what rc1's list left open.

The human also decided that the release check checks LADO itself, not its kits: check 4.3 ran an
sdlc run to its first gate, which needs the sdlc kit, a kit with the skill `tracker`, `gh` and a
remote, none of them LADO's.

Facts the section rests on (checked on `61ef05ed`, main after rc1's fixes):

- `git log --first-parent v0.45.0rc1..origin/main`: LAD-253, LAD-254, LAD-256, LAD-255. LAD-236
  (`fc7ddcfd`) was merged before the tag `v0.45.0rc1`: rc2 has nothing of it to check.
- `SCHEMA_VERSION` is 39 at `v0.45.0rc1` and on main; `src/lado/state.py`,
  `src/lado/self_update.py`, `src/lado/runtime.py`, `src/lado/providers/` and `docker/` did not
  change after rc1.
- The human's LADO went back to 0.44.0 at rc1's end; `~/.lado-rc` holds `lado.db.0.44.0` and the
  `-shm` and `-wal` rc1's rollback left. `rc_check.py upgrade` from a final writes its copy as the
  only file of that folder (`_copy`), so it removes them itself.

Options weighed for the rc1 section:

- A (taken, the human's choice): correct the wrong expectations in place in `## 0.45.0rc1`, with
  one line at its top saying they were corrected after rc1's check. The file is how the next
  release learns what this one was checked for; a wrong line would teach it the wrong thing. The
  corrected checks are not repeated on rc2: rc1's check already tried what they mean.
- B: leave `## 0.45.0rc1` as written and put the corrected checks into `## 0.45.0rc2`. The record
  stays exact, but the file keeps six wrong expectations, and rc2's list grows by checks already
  done.

## What Changes

### `docs/release.md`

- 4.3 and its line in "The checks of every RC": a session of the built-in supervisor instead of an
  sdlc run. The line reads `- [ ] 4.3 A session of the built-in supervisor: the chat, a question
  card answered in the UI, pre-release.` The section says: New session on any folder with the
  built-in supervisor; ask it in the chat to ask you a question with choices; its card shows, and
  the choice pressed in the UI reaches it (it names it in the chat); the System panel's
  `pre-release` pill. Flows and gates are left to the tests: gate cards to the browser tests with
  the fake agent (`tests/ui/test_gates.py`), a flow run by a real CLI to the live tests
  (`tests/live/test_live.py`, flow `tiny` of a test kit).
- 4.4, the user's own way back on a test home: the whole recipe, which rc1's check had to find
  out. A temporary folder `T` as `HOME`, `LADO_HOME=$T/.lado`, `LADO_TMUX_SOCKET=lado-rc-back`,
  `LADO_TELEMETRY=0`, `LADO_AGENT_ENV=inherit` (a new `HOME` has no shell profile, so without it
  the agent's CLI is not on its PATH and LADO refuses with that hint), `PATH=$T/.local/bin:$PATH`;
  `uv tool install lado==<the final before>`, a session of OpenCode (no login needed), `lado update
  <the RC> --yes`, the RC's own checks of the way back, `lado update <the final before>`; then
  `lado stop --all`, `tmux -L lado-rc-back kill-server`, `rm -rf "$T"`, and the terminal closed.

### `docs/releases/0.45.0.md`, section `## 0.45.0rc1`

One line under the heading: `Expectations corrected after rc1's check (LAD-258); rc1 was checked
against what they mean.` Then:

1. "A CLI's default model": `changed model: CLI default -> Local` is printed by the resume of an
   OpenCode session stopped while it ran on the CLI's default, after the default was set; a new
   session prints no such line. After `--clear`, its resume prints `changed model: Local -> CLI
   default`.
2. "Stop with an open question": on a question the agent asked (`ask_human`), not on a gate. An
   open gate stays open through a stop and is not counted: `lado stop` then says only that open
   runs and gates are kept.
3. "Settings → Model servers and Agent CLIs in Safari and Firefox": Undo belongs to a removed
   model (× in Your models); removing a server asks first (`Remove <server> and its <n> model:
   <name>? This cannot be undone.`) and has no Undo.
4. "A kept model of a CLI not logged in resumes" (4.6): `lado start --provider codex --model …`
   with Codex not logged in is refused, rightly. The check: Codex logged in, `kept` started on a
   name of its list, then `codex logout` in the container, `docker compose restart`; the log has
   `lado: resumed session "kept" at the container's start` and `session "kept": Codex CLI is not
   logged in: log in in Settings → Agent CLIs, or set OPENAI_API_KEY; the agent starts by itself
   once you do`; `lado ls` shows `kept` waiting, its model kept.
5. "The user's way back names the model server": the keys' folder exists only for a server saved
   with a key. The test home saves a second server with a key (`printf %s <key> | lado
   model-server add Keyed <an address that answers> --key`, e.g. OpenRouter) beside `Fake`; the
   warning names the keys' folder of `Keyed` (by its id) and none for `Fake`. Its recipe is
   docs/release.md 4.4's.
6. rc1's "Before you start" loses nothing for the sdlc kit: 4.3 no longer needs one.

### `docs/releases/0.45.0.md`, a new section `## 0.45.0rc2`

After `## 0.45.0rc1`. A short paragraph: the RC's tag `v0.45.0rc2` (its commit and `live.yml`'s run
are filled in at the RC, as rc1's); the fixes since rc1 are LAD-253, LAD-254, LAD-255 and LAD-256,
LAD-236 was in rc1 already; the schema is 39 as at rc1 and neither the migration nor the image
changed, so 4.6 and 4.4's way back on a test home are not repeated; 4.1, 4.2 (from 0.44.0 again:
your LADO went back to it at rc1's end), 4.3, 4.4's `rollback` and 4.5 are. Then these items, each
a top-level `- [ ] **Title.** …` with its detail nested, as rc1's:

- **Before you start** (no item): your LADO is 0.44.0; `ls -a ~/.lado-rc` shows `lado.db.0.44.0`
  and, on the Mac, the `-shm` and `-wal` rc1's rollback left: leave them, `upgrade` removes them.
  An OpenRouter key; a test workspace for 4.5.
- **The checklist rc_check prints (LAD-253).** `sandbox 0.45.0rc2` and `upgrade 0.45.0rc2` end with
  `Left to check by hand on LADO 0.45.0rc2:`, the six `[ ] 4.x` lines of docs/release.md, then
  the first lines of this section's items, and no `warning:` line.
- **~/.lado-rc after upgrade (LAD-256).** After `upgrade 0.45.0rc2`, `ls -a ~/.lado-rc` lists
  `lado.db.0.44.0` alone.
- **~/.lado-rc after rollback (LAD-256).** After 4.4's `rollback`, last, `ls -a ~/.lado-rc` lists
  `lado.db.0.44.0` alone: no `-shm`, no `-wal`.
- **An agent's popup names its model (LAD-254).** A session on a saved model of OpenRouter (e.g.
  `Cloud` for OpenCode); the pointer on the supervisor's avatar in the session's head: its name
  after its status dot and the status in words; under a line `CLI opencode` and `Model Cloud`
  (the saved name, not the server's id), no `Role` (it is the name), `Flow` only for an agent of a
  run; under a second line, smaller, `Click to open the terminal`. No effort, no source of the
  model. The same popup on the terminals' strip; an agent on its CLI's default reads `Model CLI
  default`, muted.
- LAD-255, a group "New session without a login, on a server's model", in the container of 4.5
  before Claude Code and Codex are logged in there, with OpenRouter saved in it
  (`printf %s "$OPENROUTER_KEY" | docker compose exec -T lado lado model-server add OpenRouter
  https://openrouter.ai/api/v1 --key`) and one model each: `CloudClaude` (`--cli claude`) and
  `CloudCodex` (`--cli codex`). Then log them in and go on with 4.5.
  - **Claude Code without its login starts on the server's model.** New session → Change →
    Agent: `Claude Code <version> · not logged in: your server's models only`; under it `Claude
    Code is not logged in: its agents run on your server's models only. Log in for its own
    models.`; the Model field holds `CloudClaude` with `For this session only: Claude Code is not
    logged in, so it runs on your server's model.`; Start starts it, the supervisor answers.
  - **Codex without its login starts on the server's model.** The same with Codex CLI and
    `CloudCodex`.
  - **A built-in model is refused before the start.** `opus` picked in Model: `Claude Code is not
    logged in, so it cannot run opus: pick a model of your server, or log in first.` with `Use
    CloudClaude` and `Log in first`, the mark `! needs login`, the footer `To start: fix the
    model`; in the list `Claude Code's settings`, `opus` and `sonnet` carry `needs login`,
    `CloudClaude` none; `Use CloudClaude` puts it back.
  - **Two server models: you pick.** A second Claude model saved (`CloudOpus`): a new session's
    field reads `Claude Code's settings` with `Claude Code is not logged in, so it runs on your
    server's models only: pick one.` and `Log in first`; Start is off until one is picked.
  - **Resume of a session on the server's model.** The Claude session stopped, New session on its
    folder: Claude Code stays chosen with the note, Model holds `CloudClaude`, `Resume <name>` is
    on and resumes it.
  - Known, not a defect for rc2 (LAD-255 review, F1): switching Agent from a CLI with a picked
    model to one without its login and one server model may say the model is back to that CLI's
    default although the field took the server model.
- A group "Left open on rc1", each rc1's check as rc1 wrote it (corrected), named by its title;
  skip what you have no device, server or key for, and note it:
  - **Codex's shared login, live.** First: `providers/codex.py` changed much in 0.45. Your own
    ChatGPT account will do, in a `CODEX_HOME` of its own, from a clone at `v0.45.0rc2`.
  - **Safari and Firefox.** rc1's project secrets with the password manager on, Settings → Model
    servers and Agent CLIs, the New session window.
  - **A real iPhone and iPad.** rc1's "A real phone and tablet", Settings on a real phone, the
    phone's link of the installer.
  - **The image on Linux.** 4.5's pull and one session.
  - **LM Studio and Ollama.** rc1's probe of LM Studio, the embeddings model refused, Codex on
    Ollama, a session on each saved local model, LM Studio from the container answering, OpenCode
    without internet.
  - **Qwen through Alibaba Model Studio, and a real LiteLLM.**
  - **Codex's model from its config.** rc1's `model = …` of `~/.codex/config.toml` named by `lado
    ls` after the upgrade, and a `model` in the repository's own `.codex/config.toml`.

`tests/test_rc_check.py`'s test over the real files checks `0.45.0rc2` too: no warning line.

## Scope

- `docs/release.md` (4.3, its line of "The checks of every RC", 4.4), `docs/releases/0.45.0.md`,
  the real-file test of `tests/test_rc_check.py`.

## Out of scope

- CHANGELOG.md: the task says so, and its "undo a removal" beside a server's removal (finding 3)
  stays: users see no change, the item is 0.45.0's and unreleased; a later task may reword it.
- `scripts/rc_check.py` and the spec `release-candidates`: the list's file and form do not change,
  only its texts; no rule changes, so the change has no delta.
- Repeating 4.6 and 4.4's way back on a test home on rc2: the schema, the migration and the image
  did not change since rc1, whose check passed them.
- Deleting the leftover `-shm` and `-wal` by hand before `upgrade`: `upgrade` removes them, and
  seeing it do so is part of the check of LAD-256.
- Windows' installer: `docker/install.ps1` did not change since v0.44.0.
- The findings of rc1 that are not the checklist's (Kilo's permissions, Codex answering only in
  its terminal, Claude Code's raw permission words, the long model list of `model-server add`, the
  installer's race with a closing Docker Desktop): not this task.

## Impact

- Docs only: `docs/release.md`, `docs/releases/0.45.0.md`; one unit test extended.
- No code, API, MCP, CLI or schema change; no CHANGELOG line; no version bump (patch-level, inside
  0.45.0; the final may differ from its last RC in this file, docs/release.md section 6).
