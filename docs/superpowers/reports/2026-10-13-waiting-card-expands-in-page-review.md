# LAD-48 waiting-card-expands-in-page: review report

Pull request #27 `fix/lad-48-waiting-card-expands-in-page` → `main`. Scale: tweak, web UI
only. Head reviewed last: `0166076`; the archive commit follows it. No API, schema or MCP
change; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` untouched, so no live tests before the merge.

## Rounds

- **Round 1** (`origin/main..2aa0a2a`): local pass over the spec, tests, screenshots and
  mockup; external round 1 by the Claude Code Action (request 19:06:28 UTC, answer
  19:07:29 UTC). F5 to fix, F1–F4 declined, E1 refuted. CI green after rerunning three
  macOS smoke jobs cancelled for want of a runner.
- **Round 2** (`2aa0a2a..0166076`): local precision pass over the delta (`Chat.tsx`'s
  `follow` and its ResizeObserver on `.chat-feed`, the `clientHeight` stub in
  `Chat.test.tsx`, the ui.md line, two UI tests, the BACKLOG.md entry, the PR
  description). No new findings.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: spec, screenshots | On Needs you the expanded card stays in the 760 px column, the notices bar above it | confirmed | minor | declined: as in the approved mockup (screen 7) |
| F2 | 1 | local: spec | In a window ≤ 900 px the session's name row goes under the top bar | confirmed | minor | declined: design decision D5 |
| F3 | 1 | local: tests | The Needs you UI test does not check the hidden `.waits-item`, focus back on the chip, or a reload with `?view=&session=` | confirmed | minor | declined: vitest and one CSS rule suffice for a tweak |
| F4 | 1 | local: general | A hand-typed `/needs-you?view=x` without `session` switches the card's Esc off and shows no panel | confirmed | minor | declined: the UI never leads there |
| E1 | 1 | external (Action) | `display: none` resets the feed's `scrollTop` | refuted | — | Playwright probe: position 3000 kept in Chromium, WebKit and Firefox |
| F5 | 1 | local, while checking E1 | While the expanded card hides the feed, the chat's scroll rule reads zero heights, records `bottom: true` and scrolls nothing: after the fold new messages sit below the edge, and a reader above is pulled down by the next message | confirmed | important | fixed in `0166076`: the rule skips a hidden feed (`clientHeight === 0`), a ResizeObserver applies it when shown; UI tests in `tests/ui/test_chat.py` (red before the fix by the developer's run) |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 5 (F1–F5) | 0 |
| external, Claude Code Action | 0 | 1 (E1) |

The external false finding led to the real defect next to it, F5.

## Checks

- `make lint`: clean.
- `make web`: 703 passed.
- `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_needs_you.py -n 2`: 21 passed.
- CI on `0166076`: 12 of 12 green; `smoke macos-latest codex` failed once (the known
  BACKLOG.md flake "the Codex smoke on macOS reached no model API") and passed on rerun.

## Found on the way

- The `test_gates.py` scroll flake with a new cause (a strict-mode match of "You"),
  recorded in BACKLOG.md in `ec6cc91`.

## Not checked

- Locally not run: `make check` as a whole, the full integration suite, live and smoke
  tests; CI ran all but live, which the change does not need.
- F5's tests red before the fix: by the developer's word, not reproduced by the reviewer.
- Safari on a real machine: only Playwright's WebKit.
