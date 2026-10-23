Task: LAD-127

## Why

Symptom: the UI test
`tests/ui/test_launch.py::test_a_folder_in_a_project_is_refused_with_the_projects_command`
fails now and then under load (a parallel `make test-ui`) with an empty list of Where's
suggestions; alone with `-n0` it passes, CI is green.

Cause (reproduced): in the New session window an empty **Where** opens its list of the
workspace's subfolders only at the moment it takes the focus, and only when the server's
answer about the workspace (`GET /api/repos-folder`) is already there (`WhereField`'s
`onFocus` in `web/src/Launch.tsx` checks `empty && made`). When the focus comes first,
the list stays closed until the field is left and entered again or something is typed.
The test focuses Where right after the window opens; under load the answer comes later.
With that answer held back 1.5 s in the browser (less than the test's 5 s wait), the
test fails every time with no list. Its neighbour
`test_where_starts_in_the_repositories_folder` waits for Where's placeholder (the answer)
before the focus and does not fail. A human sees the same: on a slow server, a click into
Where right after the window opens shows no suggestions, though the living spec
(`repos-folder`, "The New session window starts Where in the workspace") promises them
while the field is empty and has the focus.

Options weighed:
- A (taken, the human's choice, question #906): an empty Where that has the focus shows
  the subfolders as soon as the workspace is known, wherever the focus came first. A few
  lines in `WhereField`; the flaky test then holds as written. No long-term cost; it
  removes a defect users meet.
- B: only the test waits for the placeholder before the focus. One line, but the defect
  stays, and the next test that focuses Where early flakes again.

## What Changes

- An empty Where that takes the focus before the server has said where the workspace is
  lists the workspace's subfolders as soon as the answer comes, while it still has the
  focus; leaving the field before that shows nothing, as today.
- The living spec `repos-folder` gets a scenario for the focus before the answer.
- CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`.

## Scope

`web/src/Launch.tsx` (`WhereField`), `web/src/Launch.test.tsx`, the spec delta,
CHANGELOG.md. `tests/ui/test_launch.py` is not changed: its check stays as strict.

## Out of scope

- Changing the flaky UI test (option B): with the fix it is no longer racy, and waiting
  in it would hide the defect if it came back.
- Other tests' timeouts under load (BACKLOG.md, P1 "`make check` fails on timeouts"):
  a different cause, not this race.
- `docs/design/ui.md`: it says what Where suggests, not when the answer comes; nothing
  there turns false.

## Acceptance criteria

- AC-1: In the New session window with a made workspace, Where focused while
  `GET /api/repos-folder` has not answered yet lists the workspace's subfolders once it
  answers, with no second focus or typing (a unit test with the answer held back).
- AC-2: Where left before that answer comes shows no list after it; nothing is asked
  about folders before the focus (the existing "nothing before focus" check holds).
- AC-3: Without `made` an early focus suggests nothing, as today.
- AC-4: The test `test_a_folder_in_a_project_is_refused_with_the_projects_command`,
  unchanged, passes with `GET /api/repos-folder` held back 1.5 s in the browser (a check
  by hand, the throwaway test not committed), and in 20 runs of
  `uv run pytest -m ui tests/ui/test_launch.py -n auto` in a row.
- AC-5: `make lint`, `make web`, `make test` and `uv run pytest -m ui
  tests/ui/test_launch.py` pass; CI is green on the pull request's last commit.

## Impact

- Web UI only: no API, schema, MCP or CLI change. A fix: patch level; the version is
  not bumped here.
- Living spec: `repos-folder` ("The New session window starts Where in the workspace"
  modified: a scenario for the focus before the answer).
