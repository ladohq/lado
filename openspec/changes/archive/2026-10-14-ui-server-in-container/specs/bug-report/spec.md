## MODIFIED Requirements

### Requirement: lado bug-report prints the report and asks before it opens a browser

`lado bug-report` SHALL print the warning, the whole report and the line `Open a new
issue: <link>`. When stdin and stdout are terminals and a browser can show (macOS with the
process in the graphical session; elsewhere `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER` set),
it SHALL then ask `Open it in the browser? [y/N]`. `y` SHALL open the link in the default
browser. Enter, `n`, EOF or Ctrl-C SHALL open nothing and exit 0. A browser that does not
open SHALL print `could not open a browser: open the link above`. Otherwise it SHALL ask
nothing. The command SHALL NOT migrate `lado.db`, and SHALL work with a `lado.db` of
another schema version or with none. Its `Server:` line SHALL say whether the UI server
runs (`not running`, or `running, loopback only` / `running, open to the network`; in a
container `running, in a container`, as the container's port publication, not LADO,
decides who reaches it).

#### Scenario: Over ssh on Linux
- **WHEN** the human runs `lado bug-report` over ssh, with no `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER`
- **THEN** it prints the report and the link and asks nothing

#### Scenario: The human says yes
- **WHEN** the human runs it in a Mac's terminal in the graphical session and answers `y`
- **THEN** the default browser opens the link

#### Scenario: A database of a newer LADO
- **WHEN** `lado.db` has a newer schema than this LADO's
- **THEN** `lado bug-report` prints the report with `schema <n>`, and the database is unchanged

#### Scenario: The server in a container
- **WHEN** the human runs `lado bug-report` in a container (`LADO_CONTAINER=1`) whose UI
  server listens on `0.0.0.0`
- **THEN** its `Server:` line reads `running, in a container`, and the System panel's copy
  and the Report a bug page read `in a container, up <time>`
