## Context

`server/run.Listening.of(host, port)` decides what a server on an address reports: the
local `url` (also server.json's), `remote` (the link for other machines) and `warning`.
`lado server` (`run.serve`) prints the warning, `lado ui` (`cli.cmd_ui`) prints it and the
`From another machine` line. `doctor.report` writes the `Server:` line from a
`ServerState`; `doctor.System.container` is LAD-59's `update.in_container()`.
`clone.default_folder` joins `clone.DEFAULT_PARENT` (`~/lado`) and the repo's name, for
`lado start <git-url>` and the server's `GET /api/clone-target`. The New session window's
Where field (`Launch.tsx`, `WhereField`) suggests the subfolders of the folder up to the
last `/` by `GET /api/folders`; an empty field suggests nothing.

Root cause: LADO decides who reaches the server from the address it listens on, and a
container breaks that link, as only the port's publication, outside LADO, decides it; and
the folders LADO starts from (none for Where, `~/lado` for a clone) are the container's,
not the host's.

Options weighed for the server's message:
1. `LADO_CONTAINER` words it (chosen): no new setting, the image sets the variable already
   (T1). Long-term cost: none beyond one branch; when TLS or a real login come, the note
   changes with the warning.
2. A `--published <address>` option of `lado server`: exact, but a second source of what
   compose's `ports:` says, and `lado ui` must read it back from server.json.
3. The launcher on the host prints the link (research 5.6, way 2): no launcher exists
   yet; it can still do so later on top of option 1.

Options for the start folder: a `LADO_` variable the image sets (chosen), the container's
`$HOME` (the home volume, not the projects), or the recent folders only (empty on a first
start).

## Decisions

- **D1. `Listening.of(host, port, container=False)`.** The caller passes
  `update.in_container()` (`run.serve` and `cli.cmd_ui`), so `Listening` stays pure and its
  tests need no environment. In a container a non-loopback address gives `remote=None`,
  `warning=None` and a new field `note` with the container text; a loopback address is as
  today. `url` is as today (`http://127.0.0.1:<port>` for `0.0.0.0`). `serve` and `cmd_ui`
  print a `note` as `lado: note: <note>` on stderr where they print the warning.
- **D2. `lado ui` in a container never opens a browser.** `cmd_ui` prints the link alone
  (as `--no-open`) and, without `--no-open`, `Open it in your browser on the host.` after
  it; `webbrowser.open` is not called (there is no browser, and Python's `webbrowser` would
  fail silently or find a text browser). `--no-open` output stays one line, for a launcher
  that reads it (`docker exec lado lado ui --no-open`).
- **D3. The report reads `System.container`.** `doctor.report` passes `system.container` to
  `_server_line`, whose place is then `in a container` instead of `open to the network` /
  `loopback only`; `ServerState` does not change, so the CLI and the API callers do not.
- **D4. One reader of `LADO_REPOS`: `clone.repos_folder()`.** It returns the expanded
  (`~`) absolute path, or None when the variable is unset, empty or not absolute after
  expansion; read at each call. `clone.default_parent()` is `repos_folder()` or
  `~/lado` (`DEFAULT_PARENT` stays the text of the fallback), used by `default_folder`.
  In `clone.py` because the clone's default is its first user and the server's launch
  code and the doctor import it already; no import of the server.
- **D5. `GET /api/repos-folder` → `ReposFolder {path: str | None}`.** A small endpoint of
  its own (`app.py`, beside `/api/folders/recent`), read once per window. Not in
  `FolderInfo` (that is per path), `Limits` (the composer's limits) or `SystemInfo` (slow,
  the System panel's). The window then lists the folder with the existing
  `GET /api/folders`.
- **D6. The Where field with a repositories folder.** In `WhereField`, an empty field
  (after `trim`) with a folder takes `{parent: "<folder>/", prefix: ""}` as its split, so
  focus shows its subfolders and a pick sets `<folder>/<name>`. The placeholder is
  `<folder>/…` (else `~/projects/app` as today); the row `Repositories folder:` with one
  `chip-button` comes before Recent, hidden when the field is disabled (Resume), as Recent
  is; its click sets `<folder>/` and opens the list. **Clone into**'s placeholder is
  `<folder>/<repo>` (else `~/lado/<repo>`); its value already comes from the server.
- **D7. The doctor's check `Repositories folder`.** Only when `LADO_REPOS` is set and not
  empty: `OK` `<path> (LADO_REPOS)` for a folder; `INFO` `<path> (LADO_REPOS), not made
  yet: the first clone makes it` when missing; `WARN` for a value that is not absolute
  (`LADO_REPOS is not an absolute path: <value>; LADO ignores it`, hint `set it to a full
  path, e.g. ~/repos or /Users/me/repos`) or a path that is not a folder (`LADO_REPOS is not a folder: <path>`).
  Unset: no line, as nothing changes. It reads the variable itself only to word the
  warning; the folder is `repos_folder()`'s.
- **D8. Test layers.** `Listening`, `cmd_ui`, the report line, `repos_folder`,
  `default_folder`, the doctor check and the endpoint: unit (`tests/test_server.py`,
  `tests/test_doctor.py`, `tests/test_clone.py`, `tests/test_server_launch.py`,
  `tests/test_server_clones.py`). The note in a real server process's log: integration
  (`tests/integration/test_server_process.py`, `LADO_CONTAINER=1` in the server's
  environment; crosses a process). The window: vitest (`Launch.test.tsx`) and one UI e2e
  test (`tests/ui/test_launch.py`) against a server started with `LADO_REPOS` (a temp folder with two repositories).
  The image: by hand in the LAD-52 prototype. The plan
  (docs/superpowers/plans/2026-10-14-ui-server-in-container.md) names each test.
- **D9. The tests never see the developer's `LADO_REPOS`.** `tests/conftest.py` clears it
  with `LADO_CONTAINER`, and a test that wants it sets it itself; else a developer whose
  shell sets it would see the clone and doctor tests fail.

## Risks

- A host that publishes another port number gets a link with the wrong port. The note
  names the publication rule, and T3's compose keeps the numbers equal.
- `LADO_REPOS=/` or with a trailing `/`: the window takes the folder as a parent with
  exactly one `/` at its end (`/`, not `//`).
- `LADO_REPOS` pointing at a huge folder: the window lists at most `launch.SUBFOLDERS`
  (50) subfolders, as for any folder.
