## 1. docs/release.md: the checks of every RC check LADO, not its kits

- [ ] 1.1 4.3 and its line in "The checks of every RC" as the proposal says: a session of the
  built-in supervisor (the chat, a question card answered in the UI, the System panel's
  `pre-release`); flows and gates named as the tests' (`tests/ui/test_gates.py`,
  `tests/live/test_live.py`). No mention of the sdlc kit is left in sections 2-4
  (`grep -n sdlc docs/release.md` finds only section 5's `.lado/sdlc.md`).
- [ ] 1.2 4.4: the whole recipe of the user's own way back on a test home (`HOME`, `LADO_HOME`,
  `LADO_TMUX_SOCKET`, `LADO_TELEMETRY=0`, `LADO_AGENT_ENV=inherit`, `PATH`, `uv tool install`, an
  OpenCode session, the two updates, the cleanup), as a code block with the proposal's commands.

## 2. docs/releases/0.45.0.md: rc1's section corrected

- [ ] 2.1 The line under `## 0.45.0rc1` and the five corrections of the proposal (default model's
  `changed model` at resume; stop on an `ask_human` question, a gate not counted; Undo of a model,
  a server's removal asks; Codex's kept model resumes after `codex logout`; the keys' folder of a
  server with a key, recipe from 4.4). Each item's first line still names its check alone.

## 3. docs/releases/0.45.0.md: the section `## 0.45.0rc2`

- [ ] 3.1 The section after rc1's: its paragraph, Before you start, the items of LAD-253, LAD-256
  (two), LAD-254, the LAD-255 group with its known F1 note, and "Left open on rc1", in the
  proposal's words and with its exact lines; top-level `- [ ] **Title.** …` items, details
  nested. The intro paragraph of the file is unchanged except where it would contradict rc2.
- [ ] 3.2 Every exact line quoted for LAD-254 and LAD-255 is checked against the code
  (`web/src/Team.tsx`, `web/src/LaunchTeam.tsx`, `web/src/LaunchModel.tsx`,
  `web/src/ModelPicker.tsx`, `src/lado/server/model_entries.py`) and the living spec
  `provider-logins`; one that differs takes the code's words.

## 4. The test and the checks

- [ ] 4.1 `tests/test_rc_check.py`: the test over the real `docs/release.md` and
  `docs/releases/0.45.0.md` checks `0.45.0rc2` too (with `version = "0.45.0rc2"`): no warning
  line, the six every-RC lines first, the 4.3 line the new one. Unit; passes.
- [ ] 4.2 `make lint` and `make test PYTEST_ARGS="tests/test_rc_check.py tests/test_release_check.py
  tests/test_agents_md.py"` green; `openspec validate release-checklist-0-45-0-rc2 --strict`
  passes.
