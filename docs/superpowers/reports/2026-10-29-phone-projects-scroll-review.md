# LAD-159 phone-projects-scroll: review report

Pull request #183 `hotfix/lad-159-phone-projects-scroll` → `main`. Scale: hotfix, reviewed
in precision (one CSS line of the phone layout, UI tests, docs; no business logic, user
data or code rewritten in an earlier round). Head reviewed: `f6c74826` (= the remote head).
On a phone `:root[data-phone] .projects` gets `height: 100%`, as Sessions has, so the
project list and the project's page scroll by themselves under the top bar; before, the
narrow window's `height: auto` let `.projects` grow to its content and the clipping content
area cut off Variables, Secrets and Delete project. The UI tests now scroll with the mouse
wheel instead of `scroll_into_view_if_needed`, which scrolled the clipped box from script.
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
unchanged. Schema migration: no.

## Rounds

- **Round 1** (`1e15c3ed..f6c74826`): a local precision pass over the whole diff: the spec
  (each scenario of the modified requirement "The Projects section takes the phone's
  screen in turns" covered by a test), the acceptance criteria, the decisions D1-D3, the
  architecture against AGENTS.md. **External 1** (Claude Code GitHub Action, "Claude
  finished" in 16 s): read all code, test and doc files, not the openspec texts, which
  were read and validated locally; no blockers.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| L1 | 1 | local | the new line in `docs/design/ui.md` (Projects, Layout) is 101 characters, wider than the file's wrap | confirmed | minor | declined: the file has other long lines, nothing checks the width |
| E1 | 1 | external 1 | `wheel_to_the_end` checks only `bottom <= innerHeight`; the target could end under the top bar | refuted | — | dropped: the scrolling pane lies under the top bar and the target is its last element |
| E2 | 1 | external 1 | the mouse sits in the window's centre; another layout could send the wheel to another pane | confirmed | minor | declined: right for both pages tested; a risk only for future callers |

## Checks

Round 1 (`f6c74826`): `uv run pytest -m ui tests/ui/test_project_page.py
tests/ui/test_projects_section.py tests/ui/test_phone.py -n auto` 48 passed; `make lint`
green; `openspec validate phone-projects-scroll --strict` valid; `openspec validate
--specs --strict` 50 passed; CI `ci-ok` green (unit, integration, UI, JS, container),
the smoke skipped by ci.yml's skip list. Not run locally: `make web`, `make test` (no
Python or TS code changed; CI ran the unit tests). At archive: `openspec validate --specs
--strict` 50 passed.

## Not verified

- The new tests failing without the fix ("3 failed") was reported by the developer, not
  reproduced by the reviewer (read-only role); the mechanism was confirmed by reading.
- A real finger swipe on iPhone Safari: Playwright only has the wheel, which follows the
  same rule of which box scrolls (D2).
- A phone held sideways (`data-phone="short"`) has no test of its own; the rule is the
  same `:root[data-phone]`.
