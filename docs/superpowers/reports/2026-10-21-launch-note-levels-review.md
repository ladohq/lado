# LAD-120 launch-note-levels: review report

Pull request #128 `fix/lad-120-launch-note-levels` → `main`. Scale: tweak, reviewed by
precision: the diff touches CSS, three tokens, the class of one note, tests and documents,
no business logic or user data, so no breadth pass. Head reviewed: `b01cadd` (= the
remote head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so no live tests were needed.

## Rounds

- **Round 1, local** (precision, `587855c..b01cadd`, the whole pull request against
  `main`): the diff by hand against the `launch-notes` delta (every requirement and
  scenario has code and a test; 12 of 12 tasks checked; decisions D1–D5 kept, but for the
  panels' padding, `4px 8px` instead of `6px 10px`, within D5's threshold and accepted by
  the human, #594); every `field-note bad` of `Launch.tsx` held against `ready`,
  `cloneReady` and `scratchReady`; the screenshots against `docs/design/ui.md` and the
  design. F1, F2, F3.
- **Round 1, external** (Claude Code GitHub Action; request 12:49:59Z, comment
  6316397765, "Claude finished" 12:51:47Z): no blockers; E1–E4 refuted. It is of the same
  model family, so its "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | in the Resume session window a provider refusal (`ProviderNote`, `field-note bad`) can show while Resume stays on (`Launch.tsx:377-380`) | confirmed | minor, older than the change | declined: outside the step's scope (the New session window); found on the way |
| F2 | 1 | local (tests) | the scenario "A hint stays quiet" (12 px, no ground or stripe) has no assertion of its own | confirmed | minor | declined: the hint's CSS did not change; the e2e test compares the panels with it |
| F3 | 1 | local (PR description) | the description says "No markup or text changes" though one note's class goes `bad` → `warn` | confirmed | minor | declined: the next item of the same description names that change (#587) |
| E1 | 1 | external | the kits list's load warning has no `⚠` | refuted: design D4, its text is the server's and texts do not change | — | dropped |
| E2 | 1 | external | server errors of the folder, scratch and clone-branch lookups could leave Start on through a stale `ok` | refuted: `useAsked` gives the answer of the latest key only, an error makes the value null and every `*Ready` false | — | dropped |
| E3 | 1 | external | the `other_repo` note (`bad`) is not in the `*Ready` conditions | refuted: `cloneReady` needs `CAN_CLONE` = {new, empty} | — | dropped |
| E4 | 1 | external | the scratch target's `problem` | refuted: `ScratchTarget.name` is None with a `problem`, and `scratchReady` needs a name | — | dropped |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 3 (all minor, all
declined), refuted 0; external confirmed 0, refuted 4. Findings in code changed by the
developer's cleanup: 0.

## Checks

- `make lint` green (725 files formatted, ruff check passed).
- `make web`: 53 files, 977 vitest tests passed.
- `uv run pytest -m ui tests/ui/test_launch.py`: 25 passed. Able to fail: against the old
  CSS the warning's and the hint's grounds are both `rgba(0, 0, 0, 0)`.
- `openspec validate launch-note-levels --strict` green; `openspec validate --specs
  --strict` 43 of 43 after the archive (the new capability's Purpose written at archive).
- CI on `b01cadd`: `ci-ok` green (unit 3.10/3.13, integration, js, ui, container); smoke
  skipped, the pull request is within CI's skip list.

## Not checked

- `make test` was not run by the reviewer: the diff touches no Python the unit run
  collects; CI ran it green. The developer's run gave 3614 passed with exit 2 from a
  leftover `sleep 60` (recorded in BACKLOG, outside the task).
- Contrast is checked by the tokens' unit test; by eye only on two screenshots.

## Found on the way

- F1: the Resume session window's provider refusal does not turn Resume off.
