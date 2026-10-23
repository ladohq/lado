# LAD-135 gate-shown-once: review report

Pull request #152 `fix/lad-135-gate-shown-once` → `main`. Scale: tweak, reviewed by
precision. Head reviewed last: `16d7b126` (= the remote head). Only the web UI (`gate_open`
out of the chat's run lines in `Chat.tsx`, its CSS rule), its vitest and UI e2e tests,
`docs/design/ui.md`, the spec delta and CHANGELOG.md changed; `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not, so no live tests
were needed.

## Rounds

- **Round 1, local** (`origin/main..16d7b126`, the whole pull request): the diff read by
  hand and checked against the spec. The ADDED requirement "The gate's opening is no line
  of its run" is met by `RUN_EVENT_LINES` without `gate_open`; the filter runs before
  grouping, so the event does not split the run's group. The MODIFIED "share one time"
  holds without a core change: `state.update_run` writes the move before it opens the
  gate in the same transaction, so the gate's row stands under the move that led to it.
  No other consumer of `gate_open` in `web/src`, no other requirement about the "waits
  for you" line in `openspec/specs/`. `tasks.md` 6 of 6.
- **Round 1, external** (Claude Code GitHub Action; request at 11:38:14Z, "Claude
  finished" at 11:39:01Z, issuecomment-6364003272): no blockers; it repeated F1 and
  raised E2. Every risky file of the diff was read; only the openspec documents were
  not, and the local round covered them. It is of the same model family, so its
  "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (docs) + external | `docs/design/ui.md:1152` is 118 characters long while its paragraph wraps at about 90 | confirmed | minor | declined: cosmetic, the rendered Markdown is the same |
| E2 | 1 | external | the selector `:scope > .run-group + article` in `tests/ui/test_chat.py` assumes the gate's row comes right after the group and breaks if something is put between them | refuted: that adjacency is the requirement under test (the gate's row stands right under the group) | — | dropped |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 1 (F1), refuted 0;
external confirmed 0 new (F1 repeated), refuted 1 (E2). Findings in code changed by the
developer's cleanup: 0.

## Checks

- `openspec validate gate-shown-once --strict`: valid; `openspec validate --specs
  --strict`: 46 of 46 before and after the archive.
- `npx vitest run src/Chat.test.tsx`: 94 passed.
- CI on `16d7b126`: every job green (unit 3.10/3.13, integration ×6, js, ui ×2,
  container ×2), `ci-ok` green; the smoke skipped (every file of the diff on ci.yml's
  skip list).
- Screenshots of the open and the answered gate in the chat match variant 1 of the
  mockup: no "waits for you" line, the gate's row under the move that led to it.

## Not checked

- Not run locally by the reviewer: `make lint`, `make test`, `make web` as a whole and the
  UI e2e tests; green CI on the same head covers them, and the developer reported them
  green.
