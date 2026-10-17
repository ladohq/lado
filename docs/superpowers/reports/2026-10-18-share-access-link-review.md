# LAD-94 share-access-link: review report

Pull request #95 `feature/lad-94-share-access` → `main`. Scale: full, reviewed for breadth
(round 1) and precision (round 2). Head reviewed last: `8b5f305` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...5ad4f82`: the lenses spec, tests,
  silent failures, comments, types, general, and the architecture against AGENTS.md):
  F1 and F2 (important), F3 (minor), F4 refuted. Sent back to the developer.
- **Round 2, local** (precision over the delta `5ad4f82..8b5f305`): F1–F3 resolved. Both
  new tests shown able to fail: red on the sources of `5ad4f82` unpacked into a temporary
  folder, green on `8b5f305`. No new findings.
- **Round 1, external** (Claude Code GitHub Action, request 2026-10-17 22:52:47Z,
  "Claude finished" 22:54:24Z,
  https://github.com/ladohq/lado/pull/95#issuecomment-6242621652; the reply with the
  decisions: https://github.com/ladohq/lado/pull/95#issuecomment-6242652747): nothing
  blocking or important; three remarks, E1–E3. The external reviewer is of the same model
  family, so its "nothing blocking" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (security) | a terminal whose token was checked before New link joined `OPEN` only after `close_all`, so it stayed open on the old token and took input (`terminals.py:42`, then `await`s, then `OPEN.add`; a probe on `5ad4f82` got the `size` frame and its input written) | confirmed | important | fixed in `8b5f305`: the token is checked again right after `OPEN.add`, with no `await` between; `tests/test_terminal_socket.py::test_a_terminal_checked_before_a_new_token_but_not_yet_open_is_refused` red before, green after |
| F2 | 1 | local (same cause) | an event stream whose token was checked before New link subscribed to the hub after `end_streams` and stayed open (`app.py` `events` → `feed.stream`) | confirmed | important | fixed in `8b5f305`: `Guard.admits` after `hub.subscribe()`; `tests/test_feed.py::test_a_stream_checked_before_a_new_token_but_not_yet_open_ends_too` red before, green after |
| F3 | 1 | local (comments) | design D6 and `Guard.renew`'s docstring called a request checked before the token changed harmless | confirmed | minor | fixed in `8b5f305`: D6, `renew` and `docs/design/ui.md` |
| F4 | 1 | local (silent failures) | `close_all` could delay the response with the new cookie, and that tab would get 401 | refuted | — | dropped: uvicorn 0.54's sansio close does not wait for the client; EventSource reconnects after ~3 s |
| E1 | ext 1 | external | the module docstring of `src/lado/server/terminals.py:15-16` still says "The token is checked at the connect only" | confirmed | minor | declined: the loop converged; one comment line, behaviour untouched |
| E2 | ext 1 | external | asks for a comment on why the terminal's second check has no `changes=True` | confirmed (a wish, not a defect) | minor | declined: Origin is already checked before the upgrade (`terminals.py:42`) |
| E3 | ext 1 | external | a refused stream answers an empty 200, not 401 | refuted | — | dropped: the reviewer itself finds it correct; the browser's reconnect gets 401 (`live.ts` `diagnose`) |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (2 important, 1
minor), refuted 1; external confirmed 2 minor (both declined), refuted 1. Findings in code
changed by the developer's cleanup: 0.

## Checks

- On `8b5f305`: `make lint` clean; `make test` 3464 passed; the new new-token tests (feed
  and terminal) 4 passed.
- On `5ad4f82`: integration `test_server_process.py` 11 passed; UI `test_share_access` +
  `test_system_panel` 10 passed; `make web` (vitest) 871 passed;
  `openspec validate --specs --strict` 33 passed, the change valid. The delta
  `5ad4f82..8b5f305` touches none of `web/`, the specs or the integration tests.
- CI on `8b5f305`: 23/23 green with `ci-ok` (unit, integration ×6, ui ×2, js, container
  amd64/arm64, smoke ×8).

## Residual risk (not checked)

- Scanning the QR code with a real phone (AC-1): out of the automatic tests' reach.
- `make test-live` not run: no provider changed.
- `make test-integration`, `make test-ui` and `make test-container` as a whole not run
  locally; CI ran them, green.

## Found on the way

None.
