Task: LAD-63

## Why

In LADO's Docker container the UI server listens on `0.0.0.0` so that the container's
published port reaches it, but the port is published on the host's loopback only
(docs/research/docker-install.md, H2, 5.3, 5.6). Yet `Listening.of` takes `0.0.0.0` as a
server open to other machines: `docker logs` warns that the token travels to other
machines, `lado ui` prints `From another machine: http://lado:8765/...` with the
container's hostname, which works nowhere, and tries to open a browser the container does
not have; the issue report says `open to the network`. The New session window has no start
folder, so a typed `/` lists the container's root (`bin/`, `etc/`, ...), and a clone by URL
goes to `~/lado/<repo>`, in the container's home volume, which the host does not see. This
is step T2 of the Docker install plan (docs/research/docker-install-plan.md); LAD-59 gave
LADO `LADO_CONTAINER`.

## What Changes

- In a container (`update.in_container()`), a server on a non-loopback address prints a
  note instead of the "open to other machines" warning, in `docker logs` (`lado server`)
  and in `lado ui`:
  `lado: note: the LADO server runs in a container and listens on <host>:<port> inside it;
  who reaches it depends on how the container publishes the port (127.0.0.1:<port>:<port>:
  this computer only). Published to other machines, the token travels unencrypted (plain
  HTTP).`
- In a container `lado ui` prints no `From another machine` line; its link is the server's
  local one, `http://127.0.0.1:<port>/?token=...`, which the host's browser opens when the
  host publishes the same port number. It never tries to open a browser there: with or
  without `--no-open` it prints the link, and without `--no-open` a second line
  `Open it in your browser on the host.`
- In a container the system report's `Server:` line (`lado bug-report`, the System panel's
  copy, Report a bug) says `running, in a container` (or `in a container, up ...`) instead
  of `open to the network` / `loopback only`.
- A new environment variable `LADO_REPOS` names the folder of the human's repositories
  (an absolute path, `~` allowed; LADO's image will set it to the projects folder mounted at
  the host's path). It works with or without a container. With it:
  - a clone's default folder is `$LADO_REPOS/<repo>` instead of `~/lado/<repo>`
    (`lado start <git-url>` and the window's Clone from URL, its **Clone into** and its
    placeholder);
  - the New session window's empty **Where** field suggests the subfolders of
    `$LADO_REPOS` on focus (picking one puts its full path in), its placeholder is
    `<folder>/…`, and a row `Repositories folder: <folder>` under it, like Recent, puts
    `<folder>/` into the field (variant 2 of `mockup-where-start.html`);
  - `lado doctor` names the folder, and warns about a value it ignores.
  Without it everything is as before.

## Scope

`src/lado/server/run.py` (`Listening`), `src/lado/cli.py` (`lado ui`, `lado bug-report`'s
server state, `lado start`'s help), `src/lado/doctor.py` (the report's server line, a check
of `LADO_REPOS`), `src/lado/clone.py` (the repositories folder, the default folder),
`src/lado/server/app.py` and `models.py`, `tests/conftest.py` (clears `LADO_REPOS`) (`GET /api/repos-folder`), `web/src/Launch.tsx`
and `web/src/api.ts`, `web/openapi.json` and `web/src/api.gen.ts`, tests at the layers
tasks.md names, AGENTS.md (Layout: `clone.py`, `server/`; Try it locally), docs/design/ui.md
(Server's Host; Launch and session control), CHANGELOG.md. Capabilities: `container` and
`bug-report` and `session-clone` change, a new `repos-folder`. Minor version: a new
environment variable, CLI output and API endpoint (0.39.0, unreleased already). No schema
change.

## Out of scope

- A host port other than the container's: the link assumes the host publishes the same
  number (`127.0.0.1:8765:8765`); the image's compose file (T3) keeps both the same. A
  variable for the published port would be a second source of a number compose already
  holds; added when a compose file needs it.
- The image, its compose file and the mount of the projects folder at the host's path
  (T3, T4); setting `LADO_REPOS` and `LADO_CONTAINER` there. docs/research/docker-install-plan.md
  is updated by pull request #42, not here.
- Pre-filling **Where** with the repositories folder (variant 1 of the mockup): the folder
  check would show `not inside a git repository` until the human picks a subfolder.
- Detecting the published address from inside the container: Docker does not tell the
  container how its port is published.
- A server bound to a loopback address inside a container: unreachable from the host, but
  that is the image's command line to get right, and the message stays as today.
- The name `LADO_PROJECTS`: "Projects" is a coming notion of LADO's core (ROADMAP.md,
  Later), which the name would take.

## Impact

- CLI: `lado server` and `lado ui` output in a container; `lado ui` opens no browser
  there; `lado start <git-url>`'s default folder with `LADO_REPOS`; `lado doctor` line;
  `lado bug-report`'s `Server:` line in a container.
- API: `GET /api/repos-folder` (`ReposFolder`); `GET /api/clone-target`'s default path
  follows `LADO_REPOS`; `SystemInfo.report` and `BugReport` text in a container.
- UI: New session window, Where and Clone into.
- Spec: `container`, `bug-report`, `session-clone` modified; new `repos-folder`.
