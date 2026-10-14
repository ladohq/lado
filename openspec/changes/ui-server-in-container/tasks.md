## 1. The server's note and lado ui in a container

- [ ] 1.1 Unit tests first (layer 1), red before the code, `tests/test_server.py`:
  `Listening.of("0.0.0.0", 8765, container=True)`: `url` `http://127.0.0.1:8765`,
  `remote` and `warning` None, `note` the container text with `0.0.0.0:8765` and
  `127.0.0.1:8765:8765`; `192.0.2.7` in a container likewise (its own `url`); a loopback
  address in a container: no note; `container=False` as the existing tests. `lado ui
  --no-open` with `LADO_CONTAINER=1` and a server on `0.0.0.0` (`write_info`): stdout
  exactly the link, stderr the note and no `open to other machines`; `lado ui` without
  `--no-open` in a container: `webbrowser.open` (replaced by a recorder) not called, stdout
  the link then `Open it in your browser on the host.`; the existing tests without
  `LADO_CONTAINER` unchanged.
- [ ] 1.2 `server/run.py`: `Listening.note`, `of(..., container=False)`; `serve` and
  `cli.cmd_ui` pass `update.in_container()` and print `lado: note: ...`; `cmd_ui` in a
  container (D1, D2). `make lint`, `make test`.
- [ ] 1.3 Integration (layer 2), `tests/integration/test_server_process.py`: a background
  server started with `--host 0.0.0.0` and `LADO_CONTAINER=1` in its environment: its
  `server.log` has the note and no `open to other machines`. `uv run pytest -m
  integration -n auto tests/integration/test_server_process.py`.

## 2. The report's server line

- [ ] 2.1 Unit tests first, `tests/test_doctor.py`: `report` with `System(container=True)`
  and `ServerState(open_to_network=True, up_seconds=None)` reads `running, in a
  container`, with `up_seconds` `in a container, up ...`; with `container=False` as
  before. `tests/test_server_bug_report.py` or the CLI's bug-report test: in a container
  the `Server:` line says `in a container`.
- [ ] 2.2 `doctor.py`: `_server_line` takes `system.container` (D3). `make test`.

## 3. The repositories folder

- [ ] 3.1 Unit tests first, `tests/test_clone.py`: `repos_folder()` for unset, empty,
  `code` (None), `~/code` (expanded), `/abs`; `default_folder` gives `$LADO_REPOS/<repo>`
  with it and `~/lado/<repo>` without. `tests/test_server_clones.py`: `GET
  /api/clone-target` without `path` gives `<LADO_REPOS>/app`. `tests/test_doctor.py`: the
  `Repositories folder` check, ok, info (missing), warn (relative, a file), no line when
  unset or empty. `tests/test_server_launch.py`: `GET /api/repos-folder` with and without
  the variable.
- [ ] 3.2 `clone.py`: `repos_folder`, `default_parent`, `default_folder` through it (D4);
  `doctor.py`: `check_repos_folder` in `run_checks` (D7); `server/models.py`:
  `ReposFolder`; `server/app.py`: `GET /api/repos-folder` (D5); `cli.py`: `lado start`'s
  folder help names `$LADO_REPOS/<repo>, else ~/lado/<repo>`. `make web-types`, commit
  `web/openapi.json` and `web/src/api.gen.ts`. `make lint`, `make test`.

## 4. The New session window

- [ ] 4.1 vitest first, `web/src/Launch.test.tsx`: with `/api/repos-folder` giving a
  folder, the empty Where's focus lists its subfolders (`/api/folders` of it), a pick puts
  `<folder>/<name>`, the placeholder is `<folder>/…`, the row `Repositories folder:` and
  its button put `<folder>/`, the row is absent in Resume, no folder check before a type or
  pick; Clone into's placeholder `<folder>/<repo>`; with `{path: null}` the window as
  before.
- [ ] 4.2 `web/src/api.ts` (`getReposFolder`), `web/src/Launch.tsx` (`WhereField`, Clone
  into's placeholder) to `task/lad-63/mockup-where-start.html`, variant 2 (D6). `make web`.
- [ ] 4.3 UI e2e (layer 4), `tests/ui/test_launch.py`: a `lado server` started with
  `LADO_REPOS` at a temp folder with two repositories: New session, click into Where, the
  two subfolders show; pick one, the check says `✓ git repository`; a screenshot (`shot`)
  of the open list and of Clone into with a URL, as run artifacts. `uv run pytest -m ui
  tests/ui/test_launch.py`.

## 5. Docs and the check by hand

- [ ] 5.1 AGENTS.md: Layout (`clone.py`: `repos_folder`, `default_parent`; `server/`:
  `run.Listening`'s note in a container, `GET /api/repos-folder` with the launch endpoints;
  `update.in_container`'s users), Try it locally (`lado start <git-url>`'s default
  folder). docs/design/ui.md: Server's Host paragraph (the container's note and link, no
  browser), Launch and session control (Where's repositories folder, Clone into's
  default), the report's server line. CHANGELOG.md under `## 0.39.0 (unreleased)`: in a
  container the server's note instead of the false warning, `lado ui` prints the link for
  the host and opens no browser, the report says `in a container`; `LADO_REPOS` (the
  window's start folder, the clone's default folder, `lado doctor`).
- [ ] 5.2 By hand in the LAD-52 prototype (`docs/research/docker-install/`), the image
  built with this branch's LADO, `LADO_CONTAINER=1` and `LADO_REPOS` set to the mounted
  projects folder: `docker logs lado` has the note and no `open to other machines`;
  `docker exec lado lado ui --no-open` prints one link that the host's browser opens;
  New session's Where lists the projects folder's subfolders; Clone into defaults to
  `$LADO_REPOS/<repo>`. Record the output in the build report (the prototype's files stay
  unchanged in the commit). `openspec validate ui-server-in-container --strict`.
