# LAD-94 share-access-link: review report

Pull request #95 `feature/lad-94-share-access` → `main`. Scale: full, reviewed for breadth
(round 1) and precision (rounds 2–4). Head reviewed last: `1c126a1` (= the remote
head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...5ad4f82`: the lenses spec, tests,
  silent failures, comments, types, general, and the architecture against AGENTS.md):
  F1 and F2 (important), F3 (minor), F4 refuted. Sent back to the developer.
- **Round 2, local** (precision over the delta `5ad4f82..8b5f305`): F1–F3 resolved. Both
  new tests shown able to fail: red on the sources of `5ad4f82` unpacked into a temporary
  folder, green on `8b5f305`. No new findings.
- **Round 1, external** (Claude Code GitHub Action over `8b5f305`,
  https://github.com/ladohq/lado/pull/95#issuecomment-6242621652; the decisions:
  https://github.com/ladohq/lado/pull/95#issuecomment-6242652747): nothing blocking or
  important; E1–E3.
- **Return from `conflicts`.** After the archive (`9f0e902`) `main` had taken PR #94
  (LAD-95, the phone layout) and the pull request no longer merged.
  - **Round 3, local** (precision over `8b5f305..729275f`): the archive `9f0e902`; the
    merge `76d8d56`, whose one conflict, `CHANGELOG.md`, keeps both 0.41.0 lines, and
    whose automatic merge of `Shell.tsx` is right (the `ShareDialog` import next to
    `usePhone`); `b8f9729` and `729275f`: E1 fixed and a UI test of the dialog on a
    phone. Nothing to fix. LAD-95's own code was reviewed in PR #94, not here.
  - **Round 2, external** (request 23:21:37Z, answer 23:23Z,
    https://github.com/ladohq/lado/pull/95#issuecomment-6243020698; the decisions:
    https://github.com/ladohq/lado/pull/95#issuecomment-6243049590): nothing blocking;
    E4–E6.

- **Return from `conflicts` again.** `main` had taken PR #96 (LAD-97, an empty server
  token never lets anyone in), which also rewrote how the token file is written.
  - **Round 4, local** (precision over `729275f..1c126a1`, the merge `1c126a1`, conflicts
    in `auth.py`, `tests/test_server.py`, `CHANGELOG.md` and `docs/design/ui.md`): one
    atomic write of the token, LAD-97's `_write` (`mkstemp` 0600, then `os.replace`), used
    by New link and for an empty file alike; `_valid` refuses an empty token; `renew`,
    `set_cookie` and `admits` kept; both tasks' tests kept but the one of the fixed
    `.tmp` name, which no longer exists; documents and changelog merged with nothing
    lost. New: F5 (minor).
  - No external round: the cap of 2 was used.

The external reviewer is of the same model family, so its "nothing blocking" weighs
less. External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (security) | a terminal whose token was checked before New link joined `OPEN` only after `close_all`, so it stayed open on the old token and took input (a probe on `5ad4f82`) | confirmed | important | fixed in `8b5f305`: the token is checked again right after `OPEN.add`, with no `await` between; `tests/test_terminal_socket.py::test_a_terminal_checked_before_a_new_token_but_not_yet_open_is_refused` red before, green after |
| F2 | 1 | local (same cause) | an event stream whose token was checked before New link subscribed to the hub after `end_streams` and stayed open (`app.py` `events` → `feed.stream`) | confirmed | important | fixed in `8b5f305`: `Guard.admits` after `hub.subscribe()`; `tests/test_feed.py::test_a_stream_checked_before_a_new_token_but_not_yet_open_ends_too` red before, green after |
| F3 | 1 | local (comments) | design D6 and `Guard.renew`'s docstring called a request checked before the token changed harmless | confirmed | minor | fixed in `8b5f305`: D6, `renew` and `docs/design/ui.md` |
| F4 | 1 | local (silent failures) | `close_all` could delay the response with the new cookie | refuted | — | dropped: uvicorn's sansio close does not wait for the client |
| E1 | ext 1 | external | the module docstring of `src/lado/server/terminals.py` still said "The token is checked at the connect only" | confirmed | minor | declined in round 1, then fixed in `b8f9729`; external round 2 confirmed it |
| E2 | ext 1 | external | asks for a comment on why the terminal's second check has no `changes=True` | confirmed (a wish) | minor | declined: Origin is already checked before the upgrade |
| E3 | ext 1 | external | a refused stream answers an empty 200, not 401 | refuted | — | dropped: the browser's reconnect gets 401 (`live.ts` `diagnose`) |
| E4 | ext 2 | external | `tests/ui/test_share_access.py::test_on_a_phone_the_dialog_fits_the_screen` closes its browser context only in its last line; on a failure only the `browser` fixture's teardown does | confirmed | minor | declined: test only, nothing leaks, the loop converged |
| E5 | ext 2 | external | `from test_phone import ...` runs `test_phone`'s module code | refuted | — | dropped: harmless, the existing pattern (`test_phone.py` imports `test_main_screen` the same way) |
| E6 | ext 2 | external | `box(icon)` is called twice per icon | confirmed | minor | declined: style |
| F5 | 4 | local (silent failures, the merge with LAD-97) | `POST /api/access/new-token` does not catch the `LadoError` of `Guard.renew` (LAD-97's `_write`, e.g. on a full disk): a bare 500, and the dialog shows a general error instead of the cause; the token does not change, since `renew` assigns after the write (`src/lado/server/app.py:427`) | confirmed (by the code) | minor | declined: rare, opens no access, the token stays whole; the loop converged |

Metrics: 4 local rounds, 2 external, 0 substitutes. Local confirmed 4 (2 important, 2
minor), refuted 1; external confirmed 4 minor (E1 fixed, three declined), refuted 2.
Findings in code changed by the developer's cleanup: 0.

## Checks

- On `1c126a1`: `make lint` clean; `make test` 3467 passed; integration
  `test_server_process.py` 11 passed; UI `test_share_access` + `test_system_panel` 11
  passed; `openspec validate --specs --strict` 36 passed; `make web` not rerun (`web/`
  unchanged since `729275f`). CI on `1c126a1`: all green with `ci-ok`.
- On `729275f`: `make lint` clean; `make test` first run under load 1 failed, 3463 passed
  (the failed test's name was lost: its log was overwritten), the rerun 3464 passed; UI
  `test_share_access` + `test_system_panel` 11 passed; integration
  `test_server_process.py` 11 passed; `make web` (vitest) 906 passed;
  `openspec validate --specs --strict` 35 passed.
- CI on `729275f`: all green with `ci-ok` (unit, integration ×6, ui ×2, js, container
  ×2, smoke ×8).

## Residual risk (not checked)

- Scanning the QR code with a real phone (AC-1): out of the automatic tests' reach.
- `make test-live` not run: no provider changed.
- One local flake in `make test` whose name is unknown.
- The flake of the UI test `test_an_up_to_date_final_release_shows_no_update` from the
  developer's report: whether to file a tracker task is the human's question.
- The merge with LAD-97 (`729275f..1c126a1`) was not seen by the external reviewer: the
  cap was used.
- LAD-95's code that came in with the merge was not reviewed here.

## Found on the way

None.
