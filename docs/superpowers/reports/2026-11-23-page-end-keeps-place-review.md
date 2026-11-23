# LAD-201 page-end-keeps-place: review report

Pull request #355 `hotfix/lad-201-page-end-keeps-place` → `main`. Scale: hotfix, review
depth: precision, widened to breadth in round 1 (the shared hook `useScrollAnchor`, rewritten
in LAD-200/F14, changes both settings pages). Head reviewed: `493f8e51`. At the very end of
Settings → Model servers (and Git servers, the same hook) a form that closes no longer moves
what the human acted on: the hook leaves blank room under the section, as tall as is missing,
as inline bottom padding, and trims it to the part in view on each scroll. Web UI only; a
patch; a delta to model-settings-page ("Nothing moves under the pointer").

## Rounds

1. Local, breadth, `origin/main...c809aeed`. Lenses: spec, tests, comments, general,
   architecture; silent failures and types skipped (no new error handling or types). F1 found.
2. Local, precision, `c809aeed..e0c9928c`: F1 resolved. External 1, Claude Code GitHub Action
   (request #issuecomment-7097497514, answer #issuecomment-7097503059): F2, F3, F4. The
   external reviewer read the hook and its callers, not the tests, UI e2e, openspec or docs;
   the local pass covered those.
3. Local, precision, `e0c9928c..493f8e51`: F2 resolved, no new findings; the PR description
   and design.md D7 updated to match the diff.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `design_ok`**: option A (blank room trimmed as the human scrolls); option B (room kept
  until the page is left) and option C (keep the limit) rejected; Git servers gets the same
  behaviour.
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | local: a human's small scroll up, then a shrink below the view, was taken for the browser's clamp: room added and the page scrolled back down | fixed in `e0c9928c`: `follow` notes the position on every scroll but the browser's clamp at a nearer end; probe seen red on `c809aeed` |
| F2 | important | external: a page left far shorter than its view: two measuring passes were too few, the row moved and room no scroll removes was left | fixed in `493f8e51`: room first "missing + view height", then trimmed by `floor(end − want)`, so `want ≤ end < want + 1`; test "a page far shorter than its view" seen red on `e0c9928c` |
| F3 | minor | external: a stale note survives a shrink outside the section | declined: the hook's section is the whole settings page on both users (`ModelSettings.tsx:147`, `GitServers.tsx:416`); nothing else in `.content` can trigger it |
| F4 | — | external: the room does not follow later growth of the page | refuted: by decision D3 |

## Checks

| Check | Result |
|---|---|
| vitest of the hook (reviewer) | 28 passed on `493f8e51` |
| `make web` (developer) | 2011 passed |
| UI e2e models + git servers (developer) | 45 passed |
| `make test` (developer) | 6088 passed on `4da51d88`; no Python change since |
| `openspec validate page-end-keeps-place --strict` | valid |
| `openspec validate --specs --strict` after the archive | 89 passed |
| CI on `493f8e51` | 19 pass, 1 skip (smoke: changes within ci.yml's skip list); MERGEABLE, CLEAN |

## Metrics

Rounds: local 3, external 1, stand-ins 0. Confirmed: local 1 (F1), external 2 (F2 important,
F3 minor). Refuted: external 1 (F4). Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing.

## Not verified (residual risk)

- No UI e2e of Git servers at the page's end (out of scope by the design).
- The far shorter page (F2) is proved only by a unit test on the layout imitation, not in a
  real browser.
- Safari not checked (it has no `overflow-anchor`; the hook does not rely on it).
- Should the hook serve a section with something else on the page changing height, F3 becomes
  real, and `room()` would also have to count the section's own CSS bottom padding (it reads
  only the inline value).

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
