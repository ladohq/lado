# LAD-176 model-field-suggestions: review report

Pull request #202 `fix/lad-176-model-field` → `epic/lad-154-models`. Scale: tweak, review
depth: breadth (the change touches `runtime.start_session`), then precision. Head
reviewed: `c09289c0` (= the remote head). The launch window's Model field becomes a
combobox of the window's own (`SuggestField`): Provider's height, frame, font and a drawn
chevron, a column of the window's grid, the CLI's aliases tagged `alias` then its list,
free text kept; its note stands inside the field's `.field`, 6 px below it, out of the
focus ring's reach. `runtime.start_session` trims the model (`lado start --model` and the
API), and every resume (`lado start <session>`, the window, LADO's own resumes) checks the
model the session keeps; a refusal of the kept model names `--model ''` and
`--model <model>`, and the window offers `Use <CLI>'s default`. The server keeps a list
of models only once read. `runtime.py` changed; `providers/` did not.

## Rounds

- **Round 1** (`origin/epic/lad-154-models..2cc31ac2`, the whole pull request): a local
  breadth and precision pass (spec, tests, silent drops, screenshots against
  `docs/design/ui.md`, the architecture of AGENTS.md); external 1 of 1 (Claude Code
  GitHub Action), which read every risky code file but not tests, docs or openspec. No
  blocking or important findings.
- **Round 2** (`2cc31ac2..c09289c0`), back from `merge` after the archive failed strict
  validation (three requirements of `session-model` over 500 characters): the delta
  split into one MODIFIED and six ADDED requirements, every approved scenario kept; a
  local precision pass, the archive reproduced on a copy (57 passed). No external round:
  the tweak's cap of 1 was used.

The external reviewer is of the same model family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| L1 | minor | A list of models that could not be read is run again at every check of the field (up to 15 s), with no single flight | declined: not caching a failed list was the task; single flight is out of scope |
| L2 | minor | The button `Use <CLI>'s default` is set in the monospace font of `.chip-button` | declined: cosmetic, the class the design named |
| E1 | minor | external: the suggestion list stays open when the field turns disabled while open | declined: visible only for an instant |
| E2 | minor | external: every resume with a kept model runs the CLI's list; the container's start and `lado update` resume sessions one after another | declined: the rule the human chose; bounded by `MODEL_LIST_TIMEOUT` |
| E3 | — | external: the warning of an unread list repeats on each resume | refuted: the spec requires it |
| E4 | — | external: an aliases-only CLI (Claude) is no longer cached | refuted: its list is a constant, no process |

Found on the way: nothing.

## Checks

`openspec validate --specs --strict` after the archive 57 passed;
`pytest -n auto tests/test_runtime.py tests/test_server_launch.py tests/test_cli.py` 891
passed (round 1); CI `ci-ok` green on `2cc31ac2` and `c09289c0` (two macOS smoke jobs
passed on a rerun of the failed jobs: no runner). The developer's build: 4832 unit, 1173
vitest, 34 UI tests passed.

## Not checked

- Live tests were not run, though `runtime.py` changed.
- On real CLIs: whether a list command at the container's start without a login could
  refuse a kept model falsely (Codex reads its list locally, so it is unlikely).
- Many sessions resumed at the container's start or by `lado update` are slower, up to
  15 s each with a list command that hangs (E2).
