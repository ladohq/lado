# LAD-187 model-settings-page: review report

Pull request #211 `feature/lad-187-model-settings-page` → `epic/lad-154-models`. Scale:
full, review depth: breadth, then precision. Head reviewed: `b66a7c70` (= the remote head).
Settings → Models: the page where the human sees what each agent CLI and saved model server
offers, ticks the models to keep under names, renames them, and adds, changes and removes
servers, with the rules of `lado model-server` and `lado model`; and the server API it uses,
which a server's key enters and never leaves. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change. The step's 27 code files
(over the ~25 threshold) were accepted by the human.

## Rounds

- **Rounds 1–6**: breadth (1, 5), then precision; external rounds 1–3 (Claude Code GitHub
  Action; round 3 with the human's leave).
- **Round 7**: breadth after the page's redesign (three blocks without tabs, scroll anchor,
  Undo). **Rounds 8–10**: precision; external round 4 with the human's leave.
- **Rounds 11–13**: precision after the human's manual checks r2 and r3, without an
  external round by the human's decision.

13 local rounds, 4 external, three manual checks by the human (r1: R1–R8, r2: S1–S5,
r3: T1). The external reviewer is of the same model family, so its "no findings" weighs
less; it did not see the deltas after external round 4 (N1/N2, r2, N8, r3).

Findings in code rewritten by a fix: L1 → M1; N1 in the code of L1/M1; N8 in the code of
S2; N9 in the code of T1. T1 was found by neither review: the key was emptied on send long
before the redesign, and no one but the human walked "a refused key, then a second Save".

## Findings

| ID | Source | Level | Finding | Outcome |
|---|---|---|---|---|
| F1 | local | important | Change of a collapsed server showed no result | fixed in `d3bf8fd3` |
| F2 | local | minor | The remove confirmation named the models of a stale read | fixed in `d3bf8fd3` |
| F3 | local | minor | The live check ran the list command on every keystroke | fixed in `9f25521f` |
| F4 | local | minor | Names `.` and `..` cannot be given from the page | declined: the name rule is shared with the CLI |
| F5 | local | minor | API fields without a consumer | fixed in `1bd6c289` |
| D1 | local | minor | Line width of documents | declined |
| E1 | external | minor | The live check's `hint` is lost | declined: the path is practically unreachable |
| E2 | external | — | rename/remove return the whole listing | refuted: design decision |
| X1 | external | important | The default name did not pass the name rule | fixed in `fc7114f3` |
| X2 | external | minor | A late answer of an old poll | fixed in `d69d97ae` |
| X3 | external | minor | A model added after the confirmation was removed | fixed in `7aae1ddf` |
| G1 | local | minor | The hidden-character refusal reads as a name refusal | declined: core string shared with the CLI |
| R1–R8 | human r1 | important/minor | Eight remarks of the first manual check | fixed |
| H1, H2 | local | minor | A comment; Undo pressed twice | fixed in `936a9100` |
| J1 | local | important | A refusal on leaving the rename field was dropped silently | fixed in `db7911fd` |
| J2 | local | important | Check key and the key's emptying against the spec | fixed in `843a6831` |
| J3 | local | minor | `docs/cli.md`: the section's old name | fixed in `ad7cb34a` |
| J4 | local | minor | The Undo line vanished before the reread | fixed in `a3ecc04d` |
| J5 | local | minor | `provider-logins`' Purpose named the old section | fixed at archive |
| J6/K2 | local, external | minor | Change probed the address only for the warning | declined: the key does not leave, within 5 s |
| K1, K4 | external | — | | refuted |
| K3 | external | minor | "has other models now: none" under a concurrent remove | declined: rare race, the refusal is right |
| L1 | local | blocker | The page scrolled by itself (`firstInView`) | fixed in `694ca0f2` |
| L2 | local | minor | `note()` on every scroll of the document | fixed in `694ca0f2` |
| M1 | local | important | Opening `#models` shifted the section by 451 px (regression of L1) | fixed in `e5a39c0e` |
| M2 | local | minor | The correction after the scroll's end counted from an unreachable place | fixed in `e5a39c0e` |
| N1 | external | important | The hook kept the anchor (focus) off screen | fixed in `cb869827` |
| N2 | external | important | Change of a server with a saved key said nothing under Address | fixed in `ea3616e9` |
| N3 | external | — | `lower()` against `casefold()` in `check_server` | refuted: two names equal by fold cannot be saved |
| N4 | external | — | The comment of `ModelCheck.name` is inexact | refuted |
| N5 | external | — | `keepAtTop` does not stop on dragging the scrollbar in Safari and Firefox | unverifiable: residual risk |
| N6 | external | minor | A layout read on every render | declined: not noticeable |
| N7 | local | minor | In Change of a server with a key, a new key hides the line under Address | declined: Save checks and says |
| S1 | human r2 | important | Key and New key in plain text | fixed in `bfb3dc0a` |
| S2 | human r2 | minor | Change's Save on while the address does not answer, the refusal twice | fixed in `bfb3dc0a` |
| S3 | human r2 | minor | On a phone ids broke per character and were cut | fixed in `16810955` |
| S4 | human r2 | minor | Different orders of the agent CLIs | fixed in `7cb5b679` |
| S5 | human r2 | minor | `✓ Saved model server …` stayed after later actions | fixed in `bfb3dc0a` |
| N8 | local | important | Change's refused Save did not take the check line's place | fixed in `a863eac2` |
| T1 | human r3 | important | The key field was emptied on send; after "refused the key (401)" a second Save silently kept the old key | fixed in `b66a7c70` |
| N9 | local | minor | The key field stays enabled during Save or Add; a key typed in those ≤5 s is emptied on success | declined: short window, the button says "checking the server…" |

Confirmed: 25 local, 9 external, 14 by the human. Refuted: 5 external, 0 local.
Unverifiable: 1 (N5).

## Checks at the last round

- vitest `ModelSources.test.tsx`: 41 passed; `tsc --noEmit` clean.
- UI `test_models_section.py`: 15 passed; developer's `make test-ui` 266 passed,
  `make web` 1251 passed, `make lint` clean, trial archive 61 passed.
- `openspec validate model-settings-page --strict`: valid.
- CI of PR #211 on `b66a7c70`: 23/23 (attempts 1–3 failed on cancelled macOS smoke cells
  during a GitHub Actions incident).
- Flakes: LAD-188; `test_providers_section` in BACKLOG.md;
  `test_tmux.py::test_popup_opens_on_the_clients_attached_to_the_session` with the
  supervisor.

## Not checked (residual risk)

- Safari and Firefox: everything checked in Chromium only (N5, `overflow-anchor`).
- The key field's dots on a phone: by CSS; e2e at 1280 px only.
- A repeated refused Save in Change and Enter in Add server after a refused key: by code,
  no test of their own.
- Changes from the terminal while the page is open show at the next read; no e2e.
- Not run locally: `make test-integration` and `make check` whole (CI), smoke, live
  (providers untouched).
- The manual check on real servers is left to the human.
