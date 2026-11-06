# LAD-193 session-narrow-layout: review report

Pull request #224 `feature/lad-193-session-narrow-layout` → `main`. Scale: full, review depth:
breadth first. Head reviewed: `35149444`. Above 900 px the chat keeps 420 px: the terminals and
then the list fold for room and come back with it, leaving no trace in the saved choices. The
rail starts folded below 1600 px, the terminals take 40 % of the session's area, the tabs give
way in levels, and the strips of the terminals (32 px) and the list (48 px) gain buttons and
badges that tell sessions apart. At 601 to 900 px a session's page stands still, with the list
and the terminals over it. A window up to 600 px with a mouse gets the phone layout. The web UI
alone: no API, schema, MCP or CLI change, `src/lado` untouched. Delta: 17 requirements added, 6
modified, 2 removed in `chat-question-card`, `phone-layout`, `projects`, `session-head` and the
new `session-layout`.

## Rounds

1. Local, breadth, `origin/main...caddb5ad`: F1 to F9, then F10, F11 by the supervisor's #3779.
2. Local, precision, `caddb5ad..dd415122`: F12.
3. Local, precision, `dd415122..2a39c3d2`: nothing new.
4. External 1, Claude Code GitHub Action, `origin/main..ec3d23e7`: partial, nothing blocking.
5. External 2, the same reviewer, the files round 4 did not read: nothing blocking.
6. Local, precision, `ec3d23e7..0839523a`, back from `merge_ok` (refusal #3826): F22, F23.
7. Local, precision, `0839523a..274cec94`: F24.
8. Local, precision, `274cec94..6fb1b1c1`: nothing new.
9. Refused archive (integrator, at `6fb1b1c1`): `openspec validate --specs --strict` gave 59
   passed, 1 failed (F25); undone before any commit.
10. Local, precision, `6fb1b1c1..35149444`, back from the merge: F25 closed, a trial archive in
    a copy gave 60 of 60, nothing new.

External rounds used: 2 of 2. The design QA ran at `ec3d23e7`.

## The human's decisions

- **#3788:** F10, control ends with no message when a panel folds for room; the texts say so in
  `ec3d23e7`.
- **#3826, refusal at `merge_ok`:** the list `merge-reject-fixes` after the check of an iPad and
  the design QA; F5 accepted, recorded in BACKLOG.md (`592fc106`).
- **Touch targets:** chips of 24 px and tabs of 35 px kept (#3762, as `build-report` says).
- **An iPad on its side with the on-screen keyboard:** the gate's comment field is out of view
  while typing, an iPhone on its side alike. It stays as it is, with no task of its own, until
  users complain; the way round is to turn the screen. Touch targets on an iPad are LAD-216.
- **Gate `merge_ok`, approved:** with the trial archive added to the checks of `.lado/sdlc.md`.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | at 601 to 900 px an expanded short card took only part of the window | fixed in `dd415122` |
| F2 | important | dragging the list's edge folded the list itself | fixed in `dd415122` |
| F3 | important | the tabs' level was not chosen again when Find appeared | fixed in `dd415122` |
| F4 | important | terminals the human had not opened stayed beside a folded list | fixed in `dd415122` |
| F5 | minor | with a rail opened by hand, up to about 963 px the terminals' buttons do nothing, up to 927 px Sessions too | accepted by the human, #3826; BACKLOG.md, P2 |
| F6 | minor | stale descriptions and test names | fixed in `dd415122`, `3dc84df6` |
| F7 | minor | `design.md` differed from what was built (D6, D7, D11, D12) | fixed in `dd415122` |
| F8 | minor | a formatting slip in `Terminals.tsx` | fixed in `dd415122` |
| F9 | minor | the › button goes and the keyboard's focus falls to `body` | declined: the tabs stay reachable by Tab, the spec has the button go |
| F10 | important | the end of control when a panel folds for room is not seen | the human's #3788 |
| F11 | important | two tests lost the cover of a narrow window with a mouse | fixed in `3dc84df6`; tests only, so no red run |
| F12 | important | a double click on the list's edge folded the list | fixed in `2a39c3d2` |
| F13 | minor | external: a saved width of exactly 480 counts as "not set" | declined: decision D3, described in `docs/design/ui.md` |
| F14 | — | external: `max` not below 200 lets the list fold | refuted: with `listMax` below 200 the list is folded already, it has no edge |
| F15 | — | external: the fallback `shown(false, false)` | refuted: the reviewer itself holds it right |
| F16 | — | external: a window with a mouse up to 600 px becomes a phone | refuted: the human's decision, in CHANGELOG.md |
| F17 | — | external: `dataset.fit` and `setFit` may differ | refuted: `choose` writes the same level in the same tick |
| F18 | minor | external: `store` inside a state update | declined: the write is idempotent, the idiom older than the change |
| F19 | minor | external: a test's `count() == 0 or is_hidden()` passes either way | declined: other checks show the behaviour |
| F20 | minor | external: a test takes the first button of the Team group | declined: a fragile test, no defect |
| F21 | — | external: no test of Esc with the terminals and the list together | refuted: `over` is one value |
| F22 | important | a terminal in control lost to a saved `lado.lastColumn` | fixed in `274cec94`, finally `6fb1b1c1` |
| F23 | — | `.artifact-tab` keeps `height: 100dvh`: on iPadOS a record's end may lie under Safari's bar | unverifiable here; a probe by the human |
| F24 | important | in control, Sessions showed nothing (against AC-6); caused by the wording of the fix to F22 | fixed in `6fb1b1c1` |
| F25 | important | integrator: the new capability `session-layout` had no Purpose, so `openspec validate --specs --strict` failed after the archive | archive undone before any commit; fixed in `35149444`, the spec's text only |

F25 passed every round because `openspec validate <change> --strict` does not see a new
capability's Purpose and `validate --specs` does not see the capability before the archive. It
is the same kind of miss as F34 of LAD-194, so `.lado/sdlc.md` now holds a trial archive.

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec archive`, `openspec validate --specs --strict` | `f242072c` | 60 passed, 0 failed |
| CI of the pull request | `35149444` | 15 passed, 1 skipped, `ci-ok` green at the first attempt |
| `make lint` | `6fb1b1c1`, repeated by the developer at `35149444` | clean |
| `make web` | `6fb1b1c1` | 1284 passed |
| `make test` | `6fb1b1c1` | 4814 passed, 7 skipped |
| `uv run pytest -m ui -n 4` on 4 files | `6fb1b1c1` | 118 passed |

`35149444` changes one spec file, so the code's checks were not repeated on it. The whole UI
layer ran in CI, not locally. `make test-js`, `make test-integration`, the smoke and live tests
were not run locally: neither the plugin nor Python code changed.

## Metrics

Rounds: 7 local, 2 external, 0 stand-in, one design QA. Confirmed: 14 local, 4 external, 1 at the
archive. Refuted or no defect: 5 external. Unverifiable: 1 (F23). Findings in code changed by the
developer's cleanup: 1 (F18). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so no live test was needed.

## What was not checked

- The reviewer ran no real Safari: an iPad's height was checked with a substituted
  `--phone-height`, and the reviewer holds no result of the human's iOS Simulator run or the
  probe of F23. The device check was the iOS Simulator, not a real iPad.
- The delta after `ec3d23e7` (the iPad fix, `lado.lastColumn`, F22, F24) was not read externally:
  the cap was reached. Only the same local reviewer read it.
- The external rounds read the code in parts, of the tests only `test_narrow_layout.py`, few of
  the documents, and ran nothing. The reviewer is of the same model family.
- The design QA was not repeated after `ec3d23e7`, though the badges, tabs and link button changed
  by its remarks; the reviewer did not look at the screenshots taken at `274cec94`.
- Touch targets on an iPad: LAD-216.
- The cause of the flake of `test_the_tabs_give_way_in_levels` is not proven; a possible flake in
  `test_status_marks.py` has no link to the change. LAD-214 holds the Codex test.
