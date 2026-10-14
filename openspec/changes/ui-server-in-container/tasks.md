Follows docs/superpowers/plans/2026-10-14-ui-server-in-container.md; each task there has
the tests' code and the commit.

## 1. The server's note and lado ui in a container

- [x] 1.1 Unit tests first (layer 1), `tests/test_server.py`: `Listening.of` in a container
  for `0.0.0.0` and `192.0.2.7` (no `remote`, no `warning`, the `note` verbatim), for a
  loopback address (no note), outside a container (no note); `lado ui --no-open` in a
  container (stdout only the link, the note on stderr, no `open to other machines`),
  `lado ui` in a container (no `webbrowser.open`, the link and `Open it in your browser on
  the host.`), against a loopback server in a container (as outside). Plan, Task 1.
- [x] 1.2 `server/run.py`: `CONTAINER_NOTE`, `Listening.note`, `of(..., container)`,
  `serve` prints the note; `cli.cmd_ui` (D1, D2). `make lint`, `make test`.
- [x] 1.3 Integration (layer 2), `tests/integration/test_server_process.py`: `lado ui
  --no-open --host 0.0.0.0` with `LADO_CONTAINER=1`: one stdout line, the note in its
  stderr and `server.log`, no `open to other machines`. `uv run pytest -m integration -n
  auto tests/integration/test_server_process.py`. Plan, Task 2.

## 2. The report's server line

- [x] 2.1 Unit tests first: `tests/test_doctor.py` (`running, in a container`, `in a
  container, up 1 min`, `not running`), `tests/test_cli_bug_report.py` (`lado bug-report`
  in a container). Plan, Task 3.
- [x] 2.2 `doctor._server_line(server, container)`, `report` passes `system.container`
  (D3); `tests/conftest.py` clears `LADO_REPOS` (D9). `make test`.

## 3. The repositories folder in the core

- [x] 3.1 Unit tests first: `tests/test_clone.py` (`repos_folder` unset, empty, relative,
  `~/code`, absolute; `default_folder` with and without), `tests/test_server_clones.py`
  (`/api/clone-target` default in `LADO_REPOS`), `tests/test_doctor.py` (the
  `Repositories folder` check: ok, info, warn for a file and a relative value, none unset;
  `run_checks` holds it only when set). Plan, Task 4.
- [x] 3.2 `clone.REPOS`, `repos_folder`, `default_parent`, `default_folder` (D4);
  `doctor.check_repos_folder` in `run_checks` (D7); `lado start`'s folder help. `make
  lint`, `make test`.

## 4. The API

- [x] 4.1 Unit test first, `tests/test_server_launch.py`: `GET /api/repos-folder` null,
  a folder, null for a relative value. Plan, Task 5.
- [x] 4.2 `models.ReposFolder`, `app.py`'s endpoint (D5); `make web-types`, commit
  `web/openapi.json` and `web/src/api.gen.ts`; `api.ts`'s `getReposFolder`. `make web`.

## 5. The New session window

- [x] 5.1 vitest first, `web/src/Launch.test.tsx`: the empty Where with a folder (no
  folder request before focus, the placeholder, the list on focus, the pick, the row's
  button), `repos = "/"` asks `/` not `//`, no row in Resume, Clone into's placeholder,
  `null` as before. Plan, Task 6.
- [x] 5.2 `Launch.tsx`: `withSlash`, `WhereField`'s `repos`, the row, the placeholders
  (D6), to `task/lad-63/mockup-where-start.html`, variant 2. `make web`.
- [x] 5.3 UI e2e (layer 4), `tests/ui/test_launch.py`: a server started with `LADO_REPOS`
  at a folder of two repositories: placeholder, row, list `api/`, `app/`, the pick and its
  check, Clone into's default; screenshots of the list and the clone as run artifacts.
  `uv run pytest -m ui tests/ui/test_launch.py`. Plan, Task 7.

## 6. Docs and the check by hand

- [x] 6.1 AGENTS.md (Layout: `clone.py`, `server/run.py`, the launch endpoints,
  `update.in_container`'s users, `doctor.py`, the conftest paragraph; Try it locally),
  docs/design/ui.md (Server's Host; New session window; `GET /api/repos-folder`),
  CHANGELOG.md under `## 0.39.0 (unreleased)`. Plan, Task 8.
- [x] 6.2 By hand in the LAD-52 prototype with this branch's LADO, `LADO_CONTAINER=1` and
  `LADO_REPOS` at the projects folder mounted at the host's path: `docker logs`, `lado ui
  --no-open`, the window's Where and Clone into, `lado doctor`, `lado bug-report`; the
  output in the build report.
- [x] 6.3 Regression: `make lint`, `make test`, the changed integration and UI files with
  their markers, `make web`, `openspec validate ui-server-in-container --strict`,
  `openspec validate --specs --strict`.
