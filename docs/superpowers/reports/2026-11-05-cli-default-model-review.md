# LAD-200 cli-default-model: review report

Pull request #216 `feature/lad-200-cli-default-model` → `epic/lad-154-models`. Scale: full,
review depth: breadth, then precision. Head reviewed: `dc3d70e8`.
Settings → Models keeps external models only: a card per agent CLI with its Default model,
one model picker, `lado model default`, `lado model add` with `--server` only, schema 39
(`models.id`, `cli_defaults`). The value is stored and shown; no session uses it yet.
`providers/` changed (`base.py`, `claude.py`, `codex.py`, `opencode_family.py`: the attribute
`external_whole_process`, the flag `ModelList.fixed`); `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not. 18 code files, under the ~25 threshold.

## Rounds

- **Round 1**: local, breadth, `origin/epic/lad-154-models...2052d34a`, with a helper for the
  spec and the tests.
- **Round 2**: local, precision, `2052d34a..dc3d70e8`. The diff of code, spec and `ui.md` read
  by hand; six screenshots of the build and the mock-up compared, the mock-up's spec read,
  `mockup.html` not opened whole.
- **Round 3**: external 1 of 2 (Claude Code GitHub Action), `dc3d70e8`. No blockers. The risky
  files were not read whole, so round 4 was requested.
- **Round 4**: external 2 of 2, the same head, the unread files only. `ModelPicker.tsx` and
  `ModelSettings.tsx` read whole, `ModelSources.tsx` in part, the spec by grep. Three minors.

2 local rounds, 2 external, 0 substitute. Local: 17 confirmed, 4 refuted, 1 unverifiable.
External: 4 confirmed, 1 refuted. Findings in code rewritten by the developer's cleanup: 1
(F1, `set_default`). The external reviewer is of the same model family as the kit's agents,
so its "no findings" weighs less.

## Findings

| ID | Source | Level | Finding | Outcome |
|---|---|---|---|---|
| F1 | local | important | `Other name…` saved what `lado model default` refuses or reads otherwise | fixed in `dc3d70e8`: one reading, `model_settings.check_default` |
| F2 | local | important | The picker's external models came from the page's records, `ModelChoices.external` was unread | fixed in `dc3d70e8` |
| F3 | local | important | `docs/design/ui.md` described what was removed | fixed in `dc3d70e8` |
| F4 | local | minor | The `Other name` form stayed open after a choice from the list | fixed in `dc3d70e8` |
| F5 | local | minor | `Show all 5 models` with five models and a removed row | fixed in `dc3d70e8` |
| F6 | local | minor | The spec's text on the focus at closing was inexact | fixed in `dc3d70e8` |
| F7 | local | minor | `lado model default <cli>` had no requirement | fixed in `dc3d70e8` |
| F8 | local | minor | Three gaps in the tests | fixed in `dc3d70e8` |
| F9 | local | minor | A name from `Other name` under a failed read is not marked `other name` | declined: LADO does not keep where a name came from |
| F10 | local | minor | Undo replaces a value chosen after × | declined: a ten-second window, the spec asks for the value back; left to the human |
| F11 | local | minor | The page does not read `ModelDefaultSaved.check` | declined: the field is in the approved design |
| F12 | local | minor | The whole-process line waits for the first read of the list | declined: a new field does not pay |
| F13 | local | minor | The block's head counts removed rows | declined: on purpose, the block does not jump above a row with Undo |
| F14 | local | minor | A new server goes last while the spec says by name | declined: older than this pull request |
| F15 | local | minor | `check_default` reads the list past `choices()` | declined: it checks one name, nothing is kept or shown |
| F16 | local | minor | A built-in choice under a failed read waits up to 15 s with no busy sign | declined: the existing timeout, a rare case |
| F17 | local | — | `#models` scrolls more than once | refuted: `keepAtTop` unchanged, behaviour pinned by a test |
| F18 | local | — | The footer's count differs with aliases | refuted: no such CLI |
| F19 | local | — | The order of `--with-models` rows | refuted: the spec's scenario has that order |
| F20 | local | — | A refused Undo does not expire | refuted: on purpose, the row says why |
| F21 | local | — | A phone's keyboard, 60dvh, Undo's 44 px, hover borders, the pinned row in a browser | unverifiable: needs a real phone and Safari |
| F22 | local | minor | Model ids in the picker use the plain font, the mock-up asks for mono: no general `.mono` rule | declined: the loop converged; one CSS rule, left to the human |
| F23 | external | minor | Undo's ten seconds restart on each render while logins are polled | declined: older than this pull request |
| F24 | external | minor | After a failed request to LADO the picker keeps the old list and `Read again` shifts the highlight | declined: the loop converged; left to the human |
| F25 | external | minor | Two quick saves may show the older answer | declined: cured by the next read |
| F26 | external | minor | `defaults()` reads over different connections | declined: nothing is saved wrong |
| F27 | external | — | An id collision | refuted: 48 bits |

## Checks on `dc3d70e8`

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `make web` | exit 0, 1340 tests |
| `make test` | exit 0, 5313 passed, 7 skipped |
| `pytest -m integration`, canary and process | exit 0, 9 passed |
| `pytest -m ui tests/ui/test_models_section.py` | exit 1: 22 passed, 1 failed, see below |
| `openspec validate --specs --strict` | 61 passed |
| `openspec validate cli-default-model --strict` | valid |
| CI of the pull request | 23 of 23 |

Not run: `make check` and `make test-integration` as a whole, smoke (CI), live, `make test-js`
(the plugin did not change).

**Flake.** `test_opened_at_models_the_section_stays_at_the_top_while_the_sections_above_grow`:
one sample of 451 instead of 0. It passed twice alone with `-n0` and is green in CI; the whole
file was not rerun. The guess, not proven: the sample fell between the growth of a section
above and `ResizeObserver` in `keepAtTop`, which this pull request did not change.

## Not checked

- F21: a real phone and its keyboard, Safari.
- Codex on real logins.
- The fixes of `dc3d70e8` had no design QA: the `Other name` form and the list were seen by
  tests only.
- The external reviewer did not read all of `ModelSources.tsx`, `cli.py`, `styles.css`,
  `providers/`, the tests and the documents; `ModelSources.tsx` and `cli.py` were read
  locally, `styles.css` only in spots.
- The flake's cause.
