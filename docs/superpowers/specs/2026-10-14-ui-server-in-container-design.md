# The UI server in a container, and the repositories folder: design

Task: LAD-63. Change: `openspec/changes/ui-server-in-container/` (proposal, deltas
`container`, `bug-report`, `session-clone`, new `repos-folder`, `design.md` D1-D9). Step T2
of the Docker install plan (docs/research/docker-install-plan.md); research
docs/research/docker-install.md, H2, 5.3, 5.6.

## Problem

LADO's image runs `lado server --host 0.0.0.0 --port 8765` and publishes the port on the
host's loopback only (`127.0.0.1:8765:8765`). What the human sees today (LAD-52's
prototype, H2):

```
$ docker logs lado
lado: warning: the LADO server listens on 0.0.0.0:8765, open to other machines: whoever reaches it with the token can run commands as you, and the token travels unencrypted (plain HTTP). Use it only on a network you trust.
LADO server 0.37.0 at http://127.0.0.1:8765, listening on 0.0.0.0:8765, pid 7
$ docker exec lado lado ui --no-open
http://127.0.0.1:8765/?token=<token>
From another machine: http://lado:8765/?token=<token> (or this host's address)
```

The warning is false (no other machine reaches the host's loopback), the second link works
nowhere (`lado` is the container's hostname), `lado ui` without `--no-open` says
`Opening ...` and opens nothing, and the issue report says `Server: running, open to the
network`. In the New session window a typed `/` lists the container's root, and a clone by
URL goes to `~/lado/<repo>` in the container's home volume, which the host cannot see.

Root cause: LADO judges who reaches its server by the address it listens on, and in a
container only the port's publication, outside LADO, decides that. And the folders LADO
starts from are the container's: Where has none, a clone `~/lado`.

## What the human sees after the change

In a container (`LADO_CONTAINER=1`, set by the image):

```
$ docker logs lado
lado: note: the LADO server runs in a container and listens on 0.0.0.0:8765 inside it; who reaches it depends on how the container publishes the port (127.0.0.1:8765:8765: this computer only). Published to other machines, the token travels unencrypted (plain HTTP).
LADO server 0.39.0 at http://127.0.0.1:8765, listening on 0.0.0.0:8765, pid 7
$ docker exec lado lado ui --no-open
http://127.0.0.1:8765/?token=<token>
$ docker exec -it lado lado ui
http://127.0.0.1:8765/?token=<token>
Open it in your browser on the host.
```

(the note also on `lado ui`'s stderr). The report: `- Server: running, in a container,
schema 27` (the UI's copy: `in a container, up 5 min`).

With `LADO_REPOS=/Users/me/repos` (the image will set it to the projects folder mounted at
the host's path, T4; a native install may set it too):

| Where | Before | After |
|---|---|---|
| New session, Where, empty, focused | no list | the folder's subfolders (`api/`, `app/`, `site/`); a pick gives `/Users/me/repos/app` |
| Where's placeholder | `~/projects/app` | `/Users/me/repos/…` |
| Under Where | Recent | `Repositories folder: /Users/me/repos` (a button putting `/Users/me/repos/`), then Recent |
| Clone into (default) | `~/lado/app` | `/Users/me/repos/app` |
| `lado start <url>` folder | `~/lado/<repo>` | `/Users/me/repos/<repo>` |
| `lado doctor` | — | `[ok  ] Repositories folder: /Users/me/repos (LADO_REPOS)` |

Mockup: `task/lad-63/mockup-where-start.html`, variant 2. Without `LADO_CONTAINER` and
without `LADO_REPOS` nothing changes.

## Options weighed

The server's message:

1. **`LADO_CONTAINER` words it** (chosen). No new setting; the image sets the variable
   already (T1). Cost: one branch in `Listening`; when TLS or a real login come, the note
   changes with the warning.
2. A `--published <address>` option of `lado server`. Exact, but a second source of what
   compose's `ports:` already says, and `lado ui` would have to read it back from
   server.json.
3. A launcher on the host prints the link (research 5.6, way 2). No launcher yet; it can
   still come on top of option 1.

The start folder:

1. **A variable `LADO_REPOS`** (chosen). The image sets it; a native user can too. Cost: one
   reader, one endpoint, a doctor line.
2. The container's `$HOME`: the home volume, not the projects.
3. Only the recent folders: empty on a first start, which is when it matters.

The Where field (mockup): variant 1, Where pre-filled with the folder, shows the red
`not inside a git repository` until a subfolder is picked; variant 2 (chosen) keeps the
field empty and suggests.

## Holding it against the roadmap and the principles

- **Roadmap**: Docker install, stage 0 (LADO's code, no image). T3 (the image in CI) sets
  `LADO_CONTAINER` and `LADO_REPOS` and keeps the host's port number the same as the
  container's; T4 mounts the projects at the host's path. Projects (ROADMAP, Later) is a
  coming notion of LADO's core; the variable is named `LADO_REPOS`, not `LADO_PROJECTS`,
  so as not to take its name.
- **Neutral core**: no provider is touched.
- **One source of truth**: `update.in_container()` for the container (LAD-59),
  `clone.repos_folder()` for the folder; the port number in the link is the server's own,
  the same as the published one by T3's compose, not a second setting.
- **No silent drops**: a `LADO_REPOS` LADO ignores (relative) or cannot use (a file) is a
  `lado doctor` warning; a publication to other machines is still named in the note.
- **Only what is used**: the image (T3/T4) uses both variables; no published-port variable
  until a compose file needs one.

## Tests

| Rule | Layer | Where |
|---|---|---|
| `Listening.of` in and out of a container | unit | `tests/test_server.py` |
| `lado ui` output, no browser in a container | unit | `tests/test_server.py` |
| the note in a real server's log | integration | `tests/integration/test_server_process.py` |
| the report's server line | unit | `tests/test_doctor.py`, `tests/test_cli_bug_report.py` |
| `repos_folder`, `default_folder` | unit | `tests/test_clone.py` |
| `GET /api/clone-target`, `GET /api/repos-folder` | unit | `tests/test_server_clones.py`, `tests/test_server_launch.py` |
| `lado doctor`'s Repositories folder | unit | `tests/test_doctor.py` |
| the window | vitest, UI e2e | `web/src/Launch.test.tsx`, `tests/ui/test_launch.py` |
| the image | by hand | LAD-52's prototype |

Regression: `make lint`, `make test`, the changed integration and UI files with their
markers, `make web`; CI runs the rest.

## Version

Minor: a new environment variable, a new API endpoint, CLI output (0.39.0, unreleased
already). No schema change.
