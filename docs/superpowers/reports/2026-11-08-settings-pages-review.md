# LAD-238 settings-pages: review report

Pull request #256 `feature/lad-238-settings-pages` → `main`. Scale: full. Head reviewed:
`b567f568`. Tasks of the pull request: LAD-238, LAD-244. Settings become a page per section beside
a list of their names and icons (General, Agent CLIs, Model servers, Statistics), old addresses lead
to the new pages, default models move into each CLI's row on Agent CLIs, Model servers keeps the
servers and one Your models table, and the rail gets a Settings cogwheel and one Help item with a
menu (Documentation, GitHub, Report a bug). Delta: the new capabilities `settings-pages` and
`rail-help`, and changes to `bug-report`, `configured-models`, `container`, `model-servers`,
`model-settings-page`, `phone-layout`, `provider-logins`, `session-layout`, `session-model`,
`usage-telemetry`.

## Rounds

1. Local, breadth, `origin/main...cebe9ec4`, 106 files: lenses spec, tests, silent failures,
   comments, types, general and the architecture against AGENTS.md. Found F1 and F2.
2. Local, precision, `cebe9ec4..f84362b9`: no new finding; F1 and F2 closed.
3. External 1, Claude Code GitHub Action, `origin/main..f84362b9`: E1 and E3 minor, E2 refuted.
4. Local, precision, `f84362b9..b567f568` (the return from `merge_ok`), 16 files: the fixes after the
   human's check and LAD-244; no new finding. The CI flake C1 examined at the supervisor's request.
5. External 2, `f84362b9..b567f568`: E4 minor, E5 and E6 refuted; it agreed with the decline of E1
   and E3 and the refutation of E2. It read the code diffs only, not the tests, specs or `ui.md`.

External rounds used: 2 of 2. Stand-ins: 0.

## The human's decisions

- **Return from `merge_ok`:** a list of remarks after the human checked the pages on a tablet and a
  phone. Items 1, 2, 5, 6, 7 and 10 fixed, each with a test; items 3, 4, 8 and 9 taken out of this
  pull request by the human's decision. LAD-244 (the list of sections stands still on a short page
  above 900 px) joined the pull request.
- **Gate `merge_ok`, approved** with no comment: E1, E3 and E4 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | Model servers did not start the check of the CLIs: on a fresh server, ticks appeared for CLIs that are not installed, and the page polled the rows in vain | fixed in `3bb8d5db`, test in `ModelSettings.test.tsx` |
| F2 | minor | `#<cli>` with a broken `%`-code threw `URIError` and blanked the UI | fixed in `3bb8d5db`, test in `Providers.test.tsx` |
| E1 | minor | external: `settingsRedirect` takes inherited keys of `OLD_SLUGS` (`/settings/constructor`) | declined: the second redirect still lands on `/settings`, both with replace; a one-line fix (`Object.hasOwn`) |
| E2 | — | external: the redirect from an old slug loses the hash | refuted: old slugs carried no row anchor; released anchors go through `OLD_HASHES` |
| E3 | minor | external: polling the CLI rows is repeated in `ModelSettings.tsx` and `Providers.tsx` | declined: two callers with different state; a simplification, not a defect |
| E4 | minor | external: the line "Not supported by this browser." is not in the toggle's `aria-describedby` | declined: the gap is older than the pull request (the red notice was not linked either); the toggle reads as disabled; a one-id fix |
| E5 | — | external: `.pv-state .dot { margin-top: 4.5px }` holds only for a 9 px dot | refuted: `.dot` is 9 px; the UI test `dot_on_first_line` measures it at 1440 and 768 |
| E6 | — | external: `.mx-acts { align-self: start }` relies on two columns of `.mx-head` on a phone | refuted: the two columns stay; `test_the_section_at_a_phones_width` checks the icons on the name row |
| C1 | — | CI: is the flake of `test_tab_walks_the_list_s_foot_with_the_keyboard` on `8d3672ca` a race the pull request brought? | refuted as a race of this pull request: the path changed only in the link's text and address; a test of the same foot failed on `main` on 2026-11-07; 30 of 30 local runs passed |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `b567f568` | green: 23 of 23 checks (run 42508758379) |
| `make lint` | `b567f568` | clean |
| pytest `test_server_model_settings.py`, `test_model_settings.py`, `test_cli_model_settings.py` | `b567f568` | 364 passed |
| vitest `Shell`, `Notifications`, `ModelSettings`, `ModelSources` | `b567f568` | 79 passed |
| UI `test_settings_pages.py`, `test_models_section.py` | `b567f568` | 40 passed |
| `test_tab_walks_the_list_s_foot_with_the_keyboard` repeated | `b567f568` | 30 of 30 passed |
| `make test`; vitest; `openspec validate` and the trial archive | `cebe9ec4` | 5980 passed, 7 skipped; 1785 passed; 80 passed |
| `openspec validate --specs --strict` after the archive | archive commit | 80 passed |

`make check` was not run locally: CI ran what it holds. The live tests were not run: `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

Flakes: C1 (above), older than the pull request; its mechanism is not established.

## Metrics

Rounds: 3 local, 2 external, 0 stand-in. Local: 2 confirmed (1 important, 1 minor), 0 refuted, plus
C1 at the supervisor's request. External: 3 confirmed minor, 3 refuted. Findings in code changed by
the developer's cleanup: 0.

## What was not checked

- The full `make test`, vitest, UI and integration suites were not run by the reviewer in round 4;
  CI ran them green, and the developer ran them (5980 / 1789 / 596).
- The rail's `100dvh` was checked only by reading the rule (vitest): in desktop Chromium `vh` equals
  `dvh`; not on a real iPad.
- The mechanism of the flake C1 is not established; the test may fail again on CI regardless of this
  pull request.
- The shift of a row after a `#<cli>` arrival when rows above it render late was not checked on a
  really slow first read.
- At archive the integrator updated the `## Purpose` of `provider-logins` and `model-settings-page`
  (task 11.2); the scenario `Settings → Models` of `model-servers` keeps its old name, as the archive
  keeps scenario names.

## Found on the way

- P3 in BACKLOG.md (`f84362b9`): `web/src/Chat.tsx:338` has the same unguarded
  `decodeURIComponent(hash)`.
- The focus flake in the model list's foot (C1): `tests/ui/test_launch_model.py`
  (`test_tab_walks_the_list_s_foot_with_the_keyboard`,
  `test_the_focus_in_the_foot_outlives_a_new_read_of_the_list`); older than the pull request; a task
  waits for the human's answer.
