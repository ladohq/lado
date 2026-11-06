## 1. Readiness

- [x] 1.1 `opencode_tui_plugin.js` (D2, D3). Check: `make test-js`, new test file.
- [x] 1.2 `tui.ready` in `EVENTS`, `plugin.init` removed from `EVENTS` and the server plugin (D1). Check:
  `tests/test_providers.py`, `make test-js`.
- [x] 1.3 `tui.json` and `tui_config_variable` (D4). Check: `tests/test_providers.py`.
- [x] 1.4 The queue waits for a late session start, the 30 s reason comes and goes (D1). Check: integration
  test with the fake agent, `-m integration`.
- [x] 1.5 Smoke: a message right after the start, `attempts` 1, Kilo and OpenCode. Check: `pytest -m smoke
  -k <test>` locally on both CLIs; CI.
- [x] 1.6 Measure: five starts of Kilo and of OpenCode under load, message at once, `attempts` 1, none lost.
  Check: the table in `build-report`. A start with `attempts` 2: stop and report `redesign`.
- [x] 1.7 Correct the comments on the TUI's input (D5).
- [x] 1.8 A silent TUI: the server plugin's `tui.silent`, `Event.note`, the line to the lead (D1a). Check:
  `make test-js`, `tests/test_runtime.py`, integration, smoke with a TUI plugin that does not load.
- [x] 1.9 A late TUI gets what failed: `Event.ready` ends a wait with no key, a dialog's stays (D1b). Check:
  `tests/test_runtime.py`, integration.

## 2. Words of an error

- [x] 2.1 The plugin sends a stop as `stopped`; `parse_event` builds both lines, the bodies (D6). Check:
  `tests/test_providers.py`, `make test-js`.
- [x] 2.2 The server's words through LADO with the key's canary. Check: integration, `-m integration`.

## 3. Launch window and documents

- [x] 3.1 The link (D7). Check: `web/src/Launch.test.tsx`, `tests/ui/test_launch_model.py` `-m ui`, `make web`;
  a screenshot of the warning in `build-report`.
- [x] 3.2 `docs/install.md`: the heading (D7) and four facts: a gateway's limit comes from its model info
  (LiteLLM: `model_info.max_input_tokens`), else it is unknown; an Ollama model not running at the start goes
  with no limit; a model that writes tool calls as text ends its turn with no answer; a weak model answers
  only in its terminal. Check: read against the human's report of LAD-211.
- [x] 3.3 `docs/design/agents.md` (session start, the first input, `--prompt`, the plugin), `docs/design/modules.md`,
  `docs/design/ui.md`, the provider's docstrings. Check: grep for `plugin.init` and "no event".
- [x] 3.4 CHANGELOG.md under `## 0.45.0 (unreleased)`. Check: `docs/release.md`'s rules.

## 4. Before review

- [x] 4.1 `make lint`, `make test`, `make test-js`, `openspec validate --specs --strict`, a trial archive on a
  copy. Check: the build report.
- [x] 4.2 The pull request into `epic/lad-154-models` holds the manual check: branch, folder, commands,
  expected; `env | grep LADO_` and `unset`; own `LADO_HOME` and `LADO_TMUX_SOCKET`. A new Kilo session with a
  message at once; LM Studio's error on a small context.
