# LAD-226 rail-height-resume-path: review report

Pull request #242 `hotfix/lad-226-rail-height-resume-path` → `main`. Scale: hotfix, review depth:
precision. Head reviewed: `e7c78fb8`. Two defects of the web UI: in a window wider than 900 px the
rail stayed `100vh`, so on a touch screen Report a bug and Settings lay under the screen's edge;
and the Resume window cut a long path in Where. The rail now follows the app (`.app .rail` in the
media block), and in Resume Where is text that wraps. The web UI alone: no API, schema, MCP or CLI
change. Delta: 1 requirement added to `session-layout`, 1 to `stopped-session`.

## Rounds

1. Local, precision, `a44d5252..e7c78fb8`: no wide pass needed, the diff touches no business logic
   and no user data. The spec, the tasks (12 of 12 checked), the design's decisions and the
   screenshots were checked. The mock-up was checked by the design's description of `.where-fixed`
   only: its HTML was not opened.
2. External 1, Claude Code GitHub Action: no blocker, no important finding. It read the risky files
   of the diff (`styles.css`, `Launch.tsx`, the tests); `CHANGELOG.md`, `BACKLOG.md` and
   `docs/design/ui.md` stand under its `Files not read`, though it says they match the behaviour.
   It took 17 seconds and ran no tests, and it is the same model family: its verdict weighs less.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Answer #4414:** Where in Resume shows the whole path, so the task's check "the ellipsis shows"
  is replaced: nothing is cut, there is no ellipsis. Scrolling the rail with the keyboard open
  stays out of the task.
- **Gate `merge_ok`, approved** with no comment.

## Findings

Confirmed, both minor and declined:

- **F1, local.** The pull request's description expects a conflict with #240 in `styles.css`, and
  it does not name the BACKLOG.md entry. `git merge-tree --write-tree` with
  `origin/fix/lad-224-session-screen-qa-fixes` (`9b724eb7`) exits 0, so there is no conflict at
  those heads. It says nothing false of the diff itself, and #240's branch may still change.
- **F3, external.** Moving the combobox to a component of its own would make the diff of
  `WhereField` smaller. No defect: without whitespace the change is small (`git diff -w`), and the
  reviewer itself calls it optional for a hotfix.

Refuted, external:

- **F2.** Where in Resume no longer takes focus, so the window's first focus might have moved. A
  disabled input took no focus before either; `Launch.tsx` has no `autoFocus` on `main` or on the
  branch, and its one `.focus()` is the Workspace button's, not shown while disabled.

## Found on the way

- Where in the New session window has a label of normal weight while Name and Kits are bold:
  `.field > label` does not reach the `label` inside `.where-head`. Read from the CSS, not measured
  in a browser. Older than this task, but now it shows, as the same word is bold in Resume. P3. The
  run reaches the merge with no further `build`, so BACKLOG.md does not have it.

## Checks

| Check | Head | Result |
|---|---|---|
| `make lint` | `e7c78fb8` | exit 0 |
| `uv run pytest -m ui tests/ui/test_phone.py tests/ui/test_launch.py -n auto` | `e7c78fb8` | 104 passed |
| vitest `src/Launch.test.tsx`, `src/phone.test.ts` | `e7c78fb8` | 177 passed |
| `tsc --noEmit` | `e7c78fb8` | exit 0 |
| `openspec validate rail-height-resume-path --strict` | `e7c78fb8` | exit 0 |
| `openspec validate --specs --strict` | `e7c78fb8` | 65 passed, 0 failed |
| A trial archive, then the specs | `e7c78fb8` | 65 passed, 0 failed |
| CI of the pull request (run 42314277006) | `e7c78fb8` | `ci-ok` green: 15 pass, smoke skipped, every file on the skip list |

The unit tests, the integration tests and the whole UI suite ran in CI, not locally. The live tests
were not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change.

## Not checked, what remains

- **WebKit and a real iPad.** The task asked for WebKit; the design replaced it with Chromium, as
  WebKit does not start in LADO's container. The rail's fix was not seen in Safari: only the
  cascade's logic and the developer's red run in Chromium (`688 == 560`). A real iPad is the human's.
- **The rail's red run** was not repeated by the reviewer, as it needs a change to the file.
- **`make check` as a whole** did not run locally: CI runs it, by the settings.
- **A low rail.** With the keyboard open on an iPad held sideways Settings may pass the edge: out of
  the task, with an entry in BACKLOG.md. The same may happen on a touch screen wider than 900 px
  with a visible height of about 501 to 545 px (estimated from a screenshot, not measured).
- **#240.** No conflict at the current heads, but how the two changes of `styles.css` work together
  after #240's merge was not checked.
- **History.** `14017d22` holds a red vitest, fixed in `3c0b8079`: it matters only to `git bisect`.
