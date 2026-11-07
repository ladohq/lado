# LAD-174 session-model: review report

Pull request #201 `feature/lad-174-session-model` → `epic/lad-154-models`. Scale: full,
review depth: breadth, then precision. Head reviewed: `d91d911b` (= the remote head). A
session keeps one model as a power table (`sessions.power`, rows light / normal / heavy
with the same model); `lado start --model` and the launch window's Model field under
Advanced choose it. Each agent on the session's CLI starts on that model in its CLI's own
way (Claude Code a flag, Codex its `CODEX_HOME` config, OpenCode and Kilo their config).
A model is checked against the CLI's aliases and local list: refused before the start
when the CLI has a list, a loud warning when it has none. A worker of another CLI stays
on its CLI's default model, and its card and `spawn_worker` say so. The agent's model
gets the source `session`. `providers/`, `hooks.py` and `runtime.py` changed.

## Rounds

- **Round 1** (`c9f068e3..35c5de32`, the whole pull request): a local breadth pass over
  every lens and the architecture of AGENTS.md (12 of 12 tasks done, screenshots against
  `docs/design/ui.md`, Claude Code's aliases checked against binary 2.1.295, Codex's
  `--bundled` list read by codex 0.162.0 without network); external 1 of 2 (Claude Code
  GitHub Action), which read every risky code file but not docs, openspec, tests or the
  generated types. No blocking or important findings.
- **Round 2** (`35c5de32..d91d911b`), back from `merge` after the archive failed strict
  validation (the new capability's placeholder Purpose; an `agent-model` requirement
  over 500 characters): a local precision pass over the two spec deltas, the archive
  reproduced on a copy (56 passed, 0 failed); external 2 of 2, no problems in the delta.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | The change's `design.md` (D6, D7) still names Claude aliases `default` and `haiku[1m]`; the code follows the binary's list | declined: drift in the document only, named in the PR |
| F2 (+E1) | minor | `PowerTable.from_json` fails on an unknown row key, a table without `normal` or broken JSON, and every reader of sessions reads it | declined: no writer of this release makes such a row; the change that adds a key to a row must make it tolerant or bump the schema |
| F3 | minor | The Resume window rechecks the saved model and disables Start when the CLI's list no longer has it, while the server and `lado start <session>` do not | declined: the note is true, the field can be cleared |
| F4 | minor | `lado start --model` does not trim spaces, the UI does | declined |
| E3 | minor | external: a failed model list stays cached for 60 s | declined: "no list" only warns |
| F5 (+Q1) | — | Claude `same_model` knows only `claude-<family>-…` names: Bedrock/Vertex ids or names normalised by OpenCode/Kilo switch the source to `cli` | unverifiable: display of the source only; a risk |
| Q2 | — | external: a Codex profile or model in the repository's `.codex/config.toml` may override the session's model | unverifiable: Codex names the model in its hooks, the source becomes `cli`; a risk |
| E2 | — | external: the model is checked for a running session too | refuted: a running session is refused earlier |
| E4 | — | external: Resume may send the saved model for another CLI | refuted: the field starts with the session's provider, a change of provider clears it, the server builds the table for the resolved CLI |

Found on the way: `tests/real_clis.with_model` rebuilds `Launch` and loses its `model` and
`effort` (from before this change).

## Checks

`make lint` clean; `make test` 4812 passed, 7 skipped; `tests/integration/test_session_model.py`
3 passed (all at `35c5de32`); `openspec validate --specs --strict` after the archive 56
passed; CI on `d91d911b` 23 of 23, smoke for four providers on Linux and macOS included.

## Not checked

- Live tests were not run, though `providers/`, `hooks.py` and `runtime.py` changed.
- Whether Kilo's plugin reports the model in `chat.message` is still unconfirmed; the
  card takes the model from the launch.
- Codex's path with a model list is not exercised by the smoke (it runs the "no list"
  path).
- The Model field in a project's launch window is covered by unit tests of the API only.
