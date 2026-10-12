# LAD-16 kits-guide: review report

Pull request #4 `fix/lad-16-kits-guide` → `main`. Scale: tweak, review depth: precision.
Head reviewed last: `676ea4c`; the archive commit follows it. Docs only: README.md,
docs/kits.md (new), links in AGENTS.md, BACKLOG.md and docs/design/ui.md, CHANGELOG.md and
the openspec change; no code. Each claim of the guide was checked against the code
(`kits.py`, `flows.py`, `cli.py`) and `lado kits … --help`.

## Rounds

- **Round 1** (`origin/main...6939fe0`): local precision pass and check of the guide
  against the code and the change. F1 important, F2 minor.
- **Round 2** (`6939fe0..8fb7808`): local precision pass over the fixes, and the external
  round (1 of 1) by the Claude Code Action (request issuecomment-6118777344, "Claude
  finished" at 06:11:00Z; answered in issuecomment-6118793723). F1 and F2 resolved; F3, F4
  declined, F5 refuted; new: F6 (a conflict with `main` kept CI from running).
- **Round 3** (`8fb7808..676ea4c`): local precision pass over the merge of `main`. F6
  resolved, nothing new. No second external round: the cap for a tweak is 1, and the delta
  is the conflict's resolution, checked with `git merge-tree`.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: precision | The guide said an MCP server of one name in two kits stops the start; `_merge` combines only agents, skills and flows | confirmed | important | fixed in `8d10806` |
| F2 | 1 | local: precision | "A pre-release is offered only with `--pre`" is wrong for `outdated`, and `--pre` was put on `update` with an explicit version | confirmed | minor | fixed in `8d10806` |
| F3 | 2 | external (Action) | Unclear that a `reads` with no producer stops a kit from loading, while one with no *earlier* producer fails only `lado kits check` | confirmed | minor | declined: section 5 already says what does not parse stops the kit from loading |
| F4 | 2 | external (Action) | A "known issue" note on `${KIT_DIR}` in an MCP server's command in Troubleshooting | confirmed | minor | declined: the guide describes the intended behaviour; the bug is in BACKLOG.md (`8fb7808`) |
| F5 | 2 | external (Action) | No rule found that a name in `reads` cannot be in the state's own `produces` | refuted | — | dropped: `flows.py` refuses such a flow at parse |
| F6 | 2 | local: CI / merge | The PR conflicted with `main` in CHANGELOG.md, so CI did not run | confirmed | important | fixed in `676ea4c` (`main` merged, both lines kept) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 3 (F1, F2, F6) | 0 | — |
| external, Claude Code Action | 2 (F3, F4) | 1 (F5) | — |

No blocker; both important findings fixed.

## Found on the way

- `lado kits check` takes `${KIT_DIR}` in an MCP server's command or env for a hardcoded
  path (it checks the path after substitution). In BACKLOG.md, P2 (`8fb7808`).
- The Codex smoke flake "the supervisor's turn reached no model API" happens on ubuntu too
  (CI run 38211402167, attempt 1, job `smoke ubuntu-latest codex`); BACKLOG.md's entry
  names only macOS and should be widened.

## Checks

- On `676ea4c`: `make lint` clean (182 files), `openspec validate kits-guide --strict`
  valid, `openspec validate --specs --strict` 2 passed; CI run 38211402167 green (check
  3.10/3.13, js, ui, 8 smoke cells; ubuntu/codex passed on its second attempt, the flake
  above).
- At archive (`--skip-specs`, no delta): `openspec validate --specs --strict` 2 passed,
  0 failed.

## Residual risk

- No local test run: docs only, CI ran everything green.
- The guide's UI claims (the Kits page, the update check button) were checked against
  AGENTS.md and docs/design/ui.md, not by running the UI.
- Versions in the examples (`sdlc@v0.5.0`, `index.json`) are illustrative, not checked
  against real tags.
