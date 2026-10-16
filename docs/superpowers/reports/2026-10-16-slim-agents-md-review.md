# LAD-82 slim-agents-md: review report

Pull request #78 `fix/lad-82-slim-agents-md` → `main`. Scale: tweak, reviewed for
precision (not widened: docs and one unit test, no logic or data). Head reviewed last:
`ea9d4e0` (= the remote head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`
and `agent_env.py` did not change; `tests/live/conftest.py` changed in one docstring line
only, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (precision over `14a38dc..ea9d4e0`, the whole pull request): the
  spec's requirement and its three scenarios are covered by `tests/test_agents_md.py`
  (red on the old AGENTS.md, "2127 lines, at most 200", green on the new); tasks 6/6
  checked. The move (AC-2) checked by a script of the reviewer's own: of the old file's
  125 paragraphs and list items, 17 are not found word for word, and in each a word diff
  changes only cross-references; the heading "## Try it locally" became the title of
  `docs/cli.md`. Every relative link of AGENTS.md and the new documents names an existing
  path; every module of `src/lado/` is in the map. F1 (minor, declined).
- **Round 1, external** (Claude Code GitHub Action over the whole pull request, request
  07:24:12Z, "Claude finished" 07:25:21Z): "approve as is"; F2, F3 (minor, declined), F4,
  F5, F6 refuted. The external reviewer is of the same model family, so its verdict
  weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (links) | `BACKLOG.md:1695` says "say so in AGENTS.md's Commands" about `--with-deps` for `make browser`; by the new rule such test-setup detail belongs in `docs/testing.md` | confirmed | minor | declined: AGENTS.md's Commands exists and names `make browser`, so the reference is not false; whoever takes the entry places the edit |
| F2 | ext 1 | external | the test does not parse reference-style links (`[x][ref]` + `[ref]: path`) | confirmed | minor | declined: AGENTS.md has none ("Only what is used") |
| F3 | ext 1 | external | links inside fenced code blocks or `<…>` targets would fail the test falsely | confirmed | minor | declined: the failure is loud, and none exist now |
| F4 | ext 1 | external | an anchor `#section` is dropped, so a link to a vanished heading passes | refuted | — | by design: tasks 2.2 drops anchor and query; the spec asks only for the path |
| F5 | ext 1 | external | `.lado/sdlc.md:168` "AGENTS.md's Versions rule" no longer matches a heading | refuted | — | not changed by the pull request; the paragraph "Release and versions" holds the rule |
| F6 | ext 1 | external | the Russian note in `docs/design/macos-gui-session.md:7` breaks the file's language | refuted | — | the file is Russian throughout |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 1 (minor), refuted 0;
external confirmed 2 (minor), refuted 3. Findings in code changed by the developer's
cleanup: 0. Found on the way: nothing.

## Checks

- On `ea9d4e0`: `make lint` green; `uv run pytest -n0 tests/test_agents_md.py
  tests/test_ci_workflow.py`, 44 passed; `openspec validate --specs --strict`, 31 passed;
  `openspec validate slim-agents-md --strict` valid.
- CI on `ea9d4e0`: all 23 checks pass (unit, integration ×6, ui ×2, js, container ×2,
  smoke on Ubuntu and macOS for 4 providers, `ci-ok`).
- The developer: `make test` 3360 passed.

## Residual risk (not checked)

- `make test` in full was not run by the reviewer (CI covers it).
- The moved text was checked for its wording, not against the code: the move is word for
  word by the human's decision; shortening it is a task of its own.
