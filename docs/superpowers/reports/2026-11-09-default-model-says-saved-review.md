# LAD-242 default-model-says-saved: review report

Pull request #258 `fix/lad-242-default-model-saved` → `main`. Scale: tweak. Head reviewed:
`8c81eed5`. On Settings → Agent CLIs, each save of a CLI's default made in its row shows a green
`✓ Saved` beside the field (on the `Default model` line over it in a narrow row) until the human's
next change on the page. Delta: one added requirement of `model-settings-page`, `A default saved
says so`.

## Rounds

1. Local, precision, `b1037656..300b2809`, plus external 1 (Claude Code GitHub Action): E1 and E2
   minor. It read the risky files `CliDefault.tsx`, `Providers.tsx` and `styles.css`, not the docs,
   the spec or the tests. After it, CI's UI tests found F2.
2. Local, precision, `300b2809..8c81eed5`: F1 and F2 closed; F3 and F4 found.
3. Local, precision: no new commit; the pull request's description checked against the diff, F3
   closed.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved**, with the request to file a task about agents sharing `/tmp`
  (Found on the way).
- Beyond the approved mockup (1440 and 390): in a CLI's row of 542 px or narrower (a tablet, a
  window up to about 915 px), the `Default model` label and `✓ Saved` stand over the field, as on a
  phone, and the field is wider than on main (428 against 304 px at 768).

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F2 | important | The empty `.cli-saved` slot in a third column narrowed the field at 768 px (251 against 304 px) and cut `qwen3-8b · lmstudio`; `test_each_page_beside_the_list[tablet-*]` red in CI | fixed in `8c81eed5`: a container query on the CLI row (≤542 px) puts the label and the slot over the field; UI tests at 390, 768 and 901 |
| F1 | minor | Two edited lines of `docs/design/ui.md` not wrapped | fixed in `8c81eed5` |
| F3 | important | The description of PR #258 held the text of PR #260 (LAD-240): a file shared by the container's agents, `/tmp/claude-1000/pr.md`, was overwritten | fixed by editing the description, no commit |
| E1 | minor | external: a save started before ↻ or a login sheet and finished after it shows `✓ Saved` again | declined: the save succeeded after ↻, a new success |
| E2 | minor | external: `line-height: 38px` of `.cli-saved` is tied to the field's height | declined: the same means as `.cli-ml`; the UI e2e tests catch a shift |
| F4 | minor | An edited line of the requirement in the spec delta not wrapped | declined: cosmetic; validation and the trial archive pass |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `8c81eed5` | green (unit ×2, integration ×6, ui ×2, js, container ×2; smoke skipped by the skip list) |
| `make lint` | `8c81eed5` | clean |
| `make test` | `8c81eed5` | 5980 passed, 7 skipped |
| `make web` | `8c81eed5` | 1796 vitest passed |
| UI `test_models_section.py`, `test_settings_pages.py` | `8c81eed5` | 44 passed |
| `openspec validate default-model-says-saved --strict`, `--specs --strict`, the trial archive | `8c81eed5` | passed |
| `openspec validate --specs --strict` after the archive | archive commit | 80 passed |

The live tests were not run: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 3 local, 1 external, 0 stand-in. Local: 4 confirmed (2 important, 2 minor), 0 refuted.
External: 2 confirmed minor, 0 refuted. Findings in code changed by the developer's cleanup: 0. F2
was found by an existing UI test in CI, not by a review pass.

## What was not checked

- Integration, smoke, live and container tests were not run locally; integration and container
  passed in CI, smoke was skipped by the skip list (the diff is web, docs, openspec and tests/ui).
- The external reviewer did not read the tests or the docs; the local passes did.
- "Each test seen red" is the developer's word; the reviewer saw `test_each_page_beside_the_list`
  red on `300b2809`.

## Found on the way

- A temporary file shared by the container's agents (`/tmp/claude-1000/pr.md`) let the agent of one
  run overwrite another run's pull request description. Drafts belong in each agent's scratchpad.
