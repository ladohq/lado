# Changelog

## 0.41.0 (unreleased)

- LADO's image carries mise, `make`, `gcc` and `g++`: an agent in the container installs
  the toolchain a project needs (Go, Rust, Java, a Python, ...) by itself, by the
  project's version files (`.tool-versions`, `mise.toml`, `.go-version`, ...), into the
  home volume, where it stays after a recreation and an update. The agents are told so in
  their instructions, only in a container; the image's Node 22 stays the agents' Node.
  Other system packages and databases are not covered (docs/install.md, The projects'
  toolchains).
- In LADO's container an agent's `npm install -g` works: it failed with `EACCES` at any
  uid. It and `uv tool install` now write to `~/.local` on the home volume, whose `bin`
  is on every agent's `PATH`, and also `docker compose exec`'s installs go there instead
  of the image's `/opt`.
- Install with Docker: docs/install.md's "Your first session" says how to answer Claude
  Code's question whether to trust a repository it has not seen ("Yes, I trust this
  folder"; Enter alone answers "No, exit" and closes the agent), and README's Docker start
  first checks the shell for `LADO_*` and `COMPOSE_*` variables, which beat `.env`.

## 0.40.0 (2026-10-17)

- Install with Docker: docs/install.md has a Docker section, from nothing to an agent that
  pushes over ssh, with compose first (`compose.yaml` of the latest release, `.env`,
  `docker compose up -d`), the logins, update, going back, a second LADO, removal of only
  its own container and volume, and what to do when something goes wrong. README and
  docs/install.md now present two ways to install, Docker first and recommended, then
  PyPI, and say how to update each. Every GitHub release now carries its `compose.yaml`,
  and each update downloads its version's (`releases/download/v<version>/compose.yaml`)
  before `docker compose up -d`. Coming from 0.39.0 needs the new `compose.yaml`: under
  0.39.0's the container has no git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`), no ssh
  agent (`LADO_SSH_AGENT`) and no `secrets/`.
- LADO's image knows GitHub's ssh host keys: an agent's first `git push` over ssh from a
  new home volume no longer fails with `Host key verification failed`.
- In LADO's container the web UI's Clone from URL works with an ssh address
  (`git@github.com:...`): the UI server now uses the host's ssh agent (`LADO_SSH_AGENT`)
  as the agents do. Before, the branch list failed with `github.com refused this machine's
  ssh key` while `ssh -T git@github.com` worked.
- In LADO's container, a session folder outside the projects folder (`LADO_REPOS`), which
  your computer does not see, gets a warning in the New session window (under Where and
  Clone into) and at `lado start`; the session still starts. Outside a container nothing
  changes.
- The comment of a gate's answer shows once in the chat, under the run's move it made,
  no longer also under the closed gate. A closed gate is a folded card that says it opens
  (its flag, run and state, the answer's chip coloured by where the run went, by whom, a
  chevron); opened, it shows the question and the answer on your ground, and folds the
  note (6 lines, then Show more) and the supervisor's recommendation ("you agreed" or
  "you answered otherwise") into a line each. Your own moves in a run's group stand on
  your ground, as your messages do. lado.db goes to schema 30.
- Renaming a session in the UI takes its name on Tab: while the title field is empty, or
  holds a start of the name, the rest of the name shows grey, and Tab (or → at the end)
  makes the name the field's text with the caret at its end, to type on and save with
  Enter. The hint under the field says so; with any other text Tab leaves the field and
  saves it, as before.
- LADO's container takes its sessions with it: `docker compose down` or `stop`, `docker
  stop`, or Docker's own end stops every running session as `lado stop` would (`docker
  logs`: `lado: the container stops: stopped sessions "app"; they resume at its start`),
  and the container's next start, after a new image's migration too, resumes them, as it
  does the sessions of a container that was killed (`lado: resumed session "app" at the
  container's start`). Sessions stopped by hand stay stopped; a session that cannot be
  resumed stays stopped with the reason in `docker logs` and is not tried again. Each
  resumed supervisor takes one model turn at the start and starts the workers its open
  flow runs need. Outside a container nothing changes.
- Agents get variables from a folder of files: with `LADO_ENV_DIR` set to an absolute
  path, each file directly in it is a variable (its name the file's, its value the
  content), laid over the login shell's environment at every agent's start, so a new file
  reaches the next agent and a kit's MCP server that needs it starts. A file LADO cannot
  use (a reserved name such as `PATH` or `LADO_*`, not a variable name, over 64 KiB, not
  text) is named in `lado start`'s warnings and by `lado doctor` (`Variables from
  outside`, names only), never applied. Without `LADO_ENV_DIR`, or with no folder or the
  null device at its path, nothing changes and nothing is said.
- LADO's container gives the agents real access: variables from an optional `secrets/`
  next to compose.yaml, mounted read-only at `/run/secrets` (`GH_TOKEN`,
  `CLAUDE_CODE_OAUTH_TOKEN`, a kit's key), never in `docker inspect`; git's identity from
  `LADO_GIT_NAME` and `LADO_GIT_EMAIL` in `.env`; git over https to github.com through
  gh (`GH_TOKEN` or `gh auth login` inside); and the host's ssh agent through
  `LADO_SSH_AGENT` without root's group. compose starts without `secrets/`, and LADO says
  nothing about it (`lado doctor` says how to give secrets); `LADO_SECRETS=./secrets` in
  `.env` and `mkdir -m 700 secrets` enable it, and compose then refuses to start while the
  folder is missing. The headers say how Claude Code, OpenCode and Kilo log in.
- A tab of the web UI closed or reloaded the very moment its clone shows running now
  cancels the clone at once too; before, the server cancelled it only after 150 s.
- The fields of the web UI's waiting card where the human writes, an own answer, a
  skip's comment and a gate's comment for the next step, open 3 lines high and grow with
  the text up to 8 lines, then scroll inside, like the composer. They have no resize
  handle any more, which grew a field under the Send button and off the screen; while
  the human types, the field's lower edge stays in view.
- The web UI's waiting card no longer cuts the focus ring of a gate's comment field on
  its left side, nor the ring of an own answer or of a question the human came to from
  the feed: the ring shows whole on every side, and nothing in the card moves.
- The UI's Activity tab: the checkbox "Show agent messages" is now a small icon at the end
  of the team's row, "Messages between agents", whose tooltip says whether the messages
  agents write to each other are shown and what a click does; the agents' chips no longer
  wrap for it in a narrow column.
- One-line texts may hold no hidden characters: a session's title, an agent's message
  summary, question and choices, `note_summary` and artifact title or summary are refused
  when they hold a line or paragraph separator, a bidi control (U+202A–U+202E,
  U+2066–U+2069) or a zero-width character (U+200B, U+FEFF), as they were for control
  characters, and the error names it (`a title is one line of visible text: U+202E
  RIGHT-TO-LEFT OVERRIDE is not allowed`); an emoji joined by U+200D stays. The human's
  chat message, gate comment, `lado flow-set` reason and uploaded file name are cleaned of
  them for their one-line form, and the whole text stays in the body (a `lado flow-set`
  note now keeps the whole reason too).
- Upgrade: schema 30, restart running sessions after the update (lado update does it).
- API: each closed gate in the UI server's gates keeps the run's event that closed it
  (`closed_by_event`).

## 0.39.0 (2026-10-15)

- Every release publishes LADO's Docker image, `docker pull ghcr.io/ladohq/lado:<version>`
  (linux/amd64 and linux/arm64; `latest` is the newest final release, a release candidate
  only its own tag), tested on each architecture before anything is published. It carries
  all four agent CLIs at the versions LADO is tested with: Claude Code, Codex CLI (only
  installed: its login does not reach the agents yet), OpenCode and Kilo CLI. The GitHub
  release names the image.
- `docker/compose.yaml` runs `ghcr.io/ladohq/lado:${LADO_VERSION}`: set `LADO_VERSION` (in
  `.env` next to the file), update by changing it and `docker compose up -d`, go back by
  putting the version before back. The image before an update keeps its version's tag, so
  nothing is kept by hand, and a second LADO, a folder of its own with its own `.env`,
  updates without touching the first.
- Before LADO upgrades `lado.db` to a newer schema, by any command and wherever it runs (a
  new Docker image on an old home volume, a LADO upgraded by hand), it copies it to
  `LADO_HOME/backups/lado.db.schema-<N>` and says so on stderr (in a container: `docker
  logs`). When the copy cannot be written, nothing is upgraded. A migration that fails is
  one message, without a traceback: `lado.db` is unchanged, where its backup is, and how
  to go back (in a container: the image of the version you ran before on the same home
  volume). `docker/compose.yaml`'s header gives the steps back after a migration that
  succeeded.
- A session can have a title, shown in the UI over its name (the list, the head, the
  browser tab, Needs you and notifications), the name small beside it: set it with the
  pencil in the session's head, Rename… in the session list's ⋯, or `lado title <session>
  TEXT` (`--clear` removes it); `lado ls` shows it. The name stays the session's
  identifier: its address, branches and CLI name do not change. The list's search finds a
  session by either. lado.db goes to schema 28.
- After an update from the UI, the System panel no longer says an update is running and
  keeps its Update… button: the page's wait ends once the update has released its lock.
- In a container (`LADO_CONTAINER`, which LADO's Docker image sets), `lado update` and the
  UI's update refuse at once, stopping nothing: a new image updates LADO there. When a
  newer LADO is out, `lado ls`, `lado doctor` and the System panel name its image
  (`ghcr.io/ladohq/lado:<version>`) and no command. `lado doctor`, the System panel (a
  `container` mark beside the version) and the system info for an issue say that LADO
  runs in a container.
- In a container the UI server no longer warns that it is open to other machines: it notes
  that how the container publishes its port decides who reaches it. `lado ui` there prints
  only the link for the host's browser and opens none, and the system info for an issue
  says the server runs in a container. `LADO_REPOS` names the folder of your repositories:
  the New session window suggests its subfolders in an empty Where, a clone by URL goes
  there by default (`lado start <git-url>` too), and `lado doctor` shows it.
- The UI colours a flow step's outcome by the order its flow declares, in the chat as in
  the Flows tab: green forward, orange back, so a `ready` after a review's `changes` no
  longer turns orange. A step back has a return icon, and hovering an outcome says where
  the step goes and, for a step back, which states run again.
- LADO's Docker image is in the repository (`docker/`): LADO from the build's wheel and
  the agent CLIs, started with one `docker run` (or `docker/compose.yaml`, whose `LADO_PORT`
  sets the port inside and on the host alike). `make docker` builds it from a checkout; CI
  builds and tests it on amd64 and arm64. Your projects folder is
  mounted at its own path (`-v "$P:$P" -e LADO_REPOS="$P"`; compose does it for
  `LADO_PROJECTS`), so a worker's worktree made in the container works on the host too,
  and on Linux the container's user takes the folder owner's uid, so the files the agents
  write are yours. `docker logs` warns when that folder is not mounted or not writable.
- `lado doctor` warns when LADO may not write in its repositories folder (`LADO_REPOS`).
- Selecting text in the UI shows a small bar to copy it or quote it into the composer; a
  quote from an artifact names it and its lines. Code blocks and messages have a copy
  button that shows on hover.
- UI: in a session's chat the waiting card can be minimized to one line, so the chat has
  the room while you talk a gate over with the supervisor; it comes back by itself when
  something new waits. Its top edge can be dragged to give it another height. Both are
  remembered in the browser.
- Upgrade: schema 28, restart running sessions after the update (lado update does it).
- API: `PUT /api/sessions/{name}/title` (`TitleChange`), `SessionInfo.title`,
  `Limits.max_title`.
- API: `GET /api/repos-folder` (`ReposFolder`).
- API: `UpdateInfo.container`; in a container `POST /api/update` is refused with 409 and
  `UpdateInfo.by_hand` is empty.

## 0.38.0 (2026-10-14)

- `lado stats` prints how you used LADO on this machine in the last 30 days (`--days N`,
  `--all`): sessions, agents per agent CLI and per role (with its kit), turn errors, flow
  runs, gates and how often you answered as the lead advised, questions, undelivered
  messages and LADO's own errors. It sends nothing.
- LADO now keeps an anonymous local record of these counts (no names, paths or texts),
  filled from your existing history at the upgrade, so `lado forget` no longer makes them
  smaller; the statistics report counts from it with the same fields. `lado log` names an
  agent's kit in its `spawned` line.
- `lado bug-report` and **Report a bug** on the UI's left menu: a report for a new GitHub
  issue, with the system info and LADO's errors of the last 30 days by kind, and no paths,
  session or repository names, nor message texts; a link opens GitHub's new issue form
  filled in with it (the terminal asks first), and nothing is sent until you submit it.
  `errors.jsonl` now keeps each error's scrubbed form too.
- UI: the expanded waiting card covers the session's chat (on Needs you, the page) instead
  of the whole window, so an artifact opened from it shows over it; Esc closes that
  artifact first, then folds the card. On Needs you an artifact opens over the page,
  keeping the answers you picked.
- Each release now also appears on GitHub (github.com/ladohq/lado/releases) with this
  changelog's section as its notes and the wheel and sdist attached; a release candidate is
  a GitHub pre-release.
- UI: the empty strip above a session's tabs is gone: the tabs start right under the top
  bar, level with the terminals' tabs; a start or resume notice still stands above them.
- `lado server stop`, `lado update` and `lado uninstall` wait until the old UI server's
  process has ended; a server that has stopped no longer makes `~/.lado` again after
  `lado uninstall`.
- Messages queued during an agent's turn reach it in its turn-end hook's output whenever
  its CLI takes that output; a race sometimes pasted them into its window.
- A gate in a session's chat always shows after the run's move that opened it.
- Upgrade: schema 27, restart running sessions after the update (lado update does it).
- API: `GET /api/bug-report`.

## 0.37.0 (2026-10-13)

- `lado uninstall [--dry-run] [--keep-data] [--yes]` removes LADO: it stops the UI server
  and every session, removes the worktrees and branches `lado finish` would remove (merged
  and clean) and lists the others with their git commands, deletes `~/.lado`, then the
  program installed with uv tool or pipx. With another `LADO_HOME` it deletes only that
  folder and keeps the program. `--keep-data` keeps the data and the repositories, so a
  LADO installed again resumes the sessions. See docs/install.md, Uninstall.
- `lado start --prompt TEXT` / `--prompt-file FILE` (`-` reads stdin) and the New session
  window's First message row give the supervisor a first message from you, also on a
  resume, where it comes after LADO's `session resumed`. The supervisor answers in the
  chat; the text never goes on an agent's command line.
- API: `prompt` in `POST /api/sessions` and `POST /api/sessions/{name}/resume`.
- The chat: a closed question card shows the choice you picked once, marked in its list;
  the reply block under it keeps who answered, when, and your comment.
- The supervisor's recommendation on a flow gate or on another agent's question is part
  of its card (the recommended option is the blue button; a disagreement is marked in
  orange) and of `lado answer` and the popup, instead of a separate chat message. LADO
  asks the supervisor for it each time; you can answer before it comes.
- MCP: the supervisor's tool `recommend`; the gate's line to the supervisor is now the
  request `recommend on gate #<id>: …`. API: `recommendation` in `GateInfo` and a
  question's `MessageInfo`. Schema 26: restart running sessions after the upgrade.
- The chat and Needs you: one card above the composer holds what waits for you in a
  session, a tab per agent with open questions and per open gate, each in that agent's or
  run's colour. An agent's tab takes a choice, your own answer (Other…) or Skip for each of
  its questions and sends them together: the agent gets all the answers at once and
  starts one turn. A gate's tab answers the gate as its card did. The card expands over
  the window (Esc folds it). In the feed an open question or gate is one line whose arrow
  leads to its tab; the hint over the composer is gone; a dismissed question reads
  "skipped". Each question shows the supervisor's recommendation, and its recommended
  choice comes picked: Send sends it unless you pick otherwise.
- API: `POST /api/sessions/{name}/answers` takes the answers to one agent's questions
  together; `POST …/questions/{id}/answer` and `…/dismiss` are gone.
- LADO asks you once, in the UI's banner and in `lado start` / `lado ui` on a terminal,
  whether it may send anonymous usage statistics and its own errors to its maintainers;
  nothing is sent before a yes. Settings → Usage statistics, `lado telemetry
  status|on|off|show`, `DO_NOT_TRACK=1` or `LADO_TELEMETRY=0` (docs/telemetry.md). An
  unreachable endpoint changes nothing you see.
- Every unexpected error of LADO (a command, a hook, an MCP tool, the session loop, the
  UI server) goes to `LADO_HOME/errors.jsonl` with its version and traceback, whatever you
  choose. `errors.jsonl`, `hooks.log`, `loop.log` and `server.log` stay under 1 MiB plus
  one `.1` file each.
- API: `GET`/`POST /api/telemetry`, `GET /api/telemetry/preview`, `SystemInfo.telemetry`;
  the System panel's row Statistics and the report's `- Statistics:` line.
- Release candidates: a minor release is first published to PyPI as a pre-release
  `X.Y.0rcN` for testing (docs/release.md). A final release of LADO is never offered one;
  a LADO on a release candidate is offered the next one and the release, and says it is a
  pre-release (`lado doctor`, the System panel's `pre-release` pill). API:
  `prerelease` and `available_prerelease` in `UpdateInfo`.
- The artifact panel shows all its buttons in one row at its top: Open in Artifacts tab,
  Open in new tab, Download and Copy link, then Expand and ×; a panel narrower than
  560 px shows the actions as icons with a tooltip.

## 0.36.0 (2026-10-12)

- `lado start <git-url> [<folder>] [--branch NAME]` and the New session window's Clone
  from URL clone a repository (by default into `~/lado/<repo>`; the window lists its
  branches by itself) and start a session in it, with git's progress and a cancel. LADO
  uses only the access git has on the machine, never asks for a password, and never
  touches a folder that exists: a clone of the same repository there is offered as it is.
- API: `POST /api/remote-branches`, `GET /api/clone-target`, `POST /api/clones`,
  `GET /api/clones/{id}`, `DELETE /api/clones/{id}`, `POST /api/clones/{id}/cancel`.
- Install guide for macOS, Linux and Windows (WSL2): README's Install section and
  docs/install.md.
- README's Update section is rewritten for users and says how to update from the web UI;
  the details (the steps, the rollback, updating by hand) moved to docs/install.md.
- Kits guide, docs/kits.md: find and install a kit, use kits in a session, create one (the
  flow format included), release new versions and share it. README's Kits section is a
  short overview that links it.
- Marketplaces guide, docs/marketplaces.md: what a marketplace is, how to make your
  team's own, its `index.json` and the CI that builds it, and how to propose a kit to the
  official marketplace. README has a Marketplaces section that links it.
- `lado start` and the UI's New session window say what a folder lacks: a file, git not
  installed, git that does not run (the macOS stub without the Xcode tools), not a
  repository, git refusing to read it, no commits; with the command that fixes it, which
  the window copies. No traceback or server error without git, also in `lado kits add`.
- `lado doctor` checks git (missing, not running, older than 2.31), and the System panel
  and its report show git's version.
- API: `FolderInfo.has_commits` is replaced by `problem_kind` and `hint`; `SystemInfo`
  has `git`.
- Kits come only from the installed and the built-in ones: a repository's `.lado/kits` is
  no longer read, so a session started with such a kit fails on resume with `kit not
  found`. To keep using a kit folder, install it once: `lado kits add <folder>` (read in
  place, so your edits show in the next agent). `lado kits --repo` is gone, and
  `GET /api/kits` takes no `where`: the list is the same for every folder.

## 0.35.0 (2026-10-11)

- Codex CLI runs read-only agents: their worktree tool is off, and on a model Codex has no
  metadata for, such as a local one, no tool but the shell writes files; each launch warns
  that an OpenAI model may keep apply_patch.
- LADO's messages to a read-only supervisor no longer tell it to start, merge or finish
  workers: they say what waits and your way (`lado flow-set`, `git merge`, `lado finish`).
- Codex CLI agents no longer get Codex's goal tools (`features.goals = false`): local
  models looped on them.
- UI: an artifact opened in a new tab scrolls when it is longer than the window (it was cut
  off on a wide window); a text record's bar stays on top.

## 0.34.0 (2026-10-11)

- Read-only roles: `read_only: true` in a role's frontmatter takes its agent's file
  editing tools away (Claude Code, OpenCode, Kilo; Codex CLI refuses such an agent), hides
  LADO's command tools from a read-only supervisor, and tells the supervisor (or you) when
  the repository changed during one of the agent's turns.
- The database schema is now 25: restart running sessions after the upgrade (`lado update`
  does it).
- UI: the artifact panel's width is yours: drag its left edge (a grip in its middle), or
  Expand it to almost the whole window; the browser remembers it.
- UI: in Activity's Team, a flow run's frame no longer spells out the run's name: its
  dashes are in the run's own colour (one of four, kept for the run's whole life), and a
  small Flows icon links to the run, its tooltip naming it.
- A Claude Code or Codex agent told at its turn's end to `read_messages` now gets the
  message's body in the turn that follows, where it used to get nothing until a later
  turn ended. A message an agent has read is never typed into its window again.
- A message handed to a Claude Code or Codex agent at its turn's end no longer arrives a
  second time when the turn that follows runs long without a tool call (a slow model): LADO
  waits for that turn to end, up to 10 minutes, instead of typing it in again after 15 s.
  Their turn-end hooks now have a 60 s limit.
- UI: an agent's terminal you control is marked in blue (its bar says "You're typing into
  <agent>", a frame around it, a keyboard on its tab) and goes back to view by itself when
  the page is hidden, the panel folded, the connection lost or after 10 minutes without
  input. The bar no longer says "live": it names the connection only when it is not open.
- The team chips above a session's Activity all look the same, compact and without the
  role (it is in the tooltip); the supervisor's chip no longer looks unlike the others.
- Markdown tables wrap their cells to fit the column; they scroll sideways only when their
  columns cannot fit.
- Dismissing an agent's question in the UI no longer loses what you typed: the button
  reads "Dismiss with comment" and the agent gets your text with the dismissal. The
  question and gate cards' buttons are now one height; "Submit" is called "Send".
- A flow run whose branch was pushed ends cleanly once merged: its worktree, branch and
  workers go, where the end used to fail and leave the workers behind. A worker whose
  branch or worktree was deleted by hand can be finished again (`lado finish`, the UI,
  `finish_worker`): it removes what is left and says what was already gone.
- UI: the session list's line under a Running session's name says its agents and how long
  the session ran, as its head does (`2 agents · 1 d 8 h`), instead of the time since its
  agents' last status change; a Stopped one says when it stopped and how long it ran. The
  card says the run time too. The API's `SessionInfo` no longer has `activity_since`.
- The supervisor can start a new, independent session in the same repository, with its
  session's kits, provider and settings, for a problem it found or a new ticket: it asks
  you with the brief attached and the choice `Start session <name>`, and once you pick it,
  the MCP tool `start_session` starts the session, whose supervisor gets a copy of the
  brief as its task. Nothing starts without your answer.
- In an agent's terminal in view, the wheel up shows that scrolling needs Take control
  instead of a read-only History layer, which full-screen CLIs never filled. The API's
  `GET /api/sessions/{name}/agents/{agent}/history` is gone.
- On Linux and WSL2, agents' PATH starts as a new terminal's: from `/etc/environment`
  (else the Linux login default), so a CLI in `/usr/local/bin` is found; on WSL with
  `/usr/lib/wsl/lib` but not the Windows PATH (add a Windows folder in `~/.profile` to give
  it to agents). `lado doctor` says where the agents' PATH starts from.
- On native Windows, `lado` says in one line that it runs only inside WSL2 instead of
  failing with a traceback (`No module named 'termios'`).
- Open in new tab for Markdown, text and images too: the artifact opens alone, without
  the UI around it.

## 0.33.0 (2026-10-10)

- On macOS, agents started over ssh (also by `lado update`) run in the graphical session,
  so Claude Code reads its login from the Keychain; LADO warns when it cannot. `lado doctor`
  and the UI's system panel say where LADO and its tmux server run (Graphical session), and
  the update's plan says where the agents resume.

## 0.32.0 (2026-10-09)

- The UI's `live` opens a system panel: LADO's version, the server, how long it runs, its
  home, tmux, the providers and the update check (with a check now), and one click to copy
  the system info for an issue (no paths, addresses, session names or tokens). A newer LADO
  shows as `↑ X.Y.Z` beside `live`, in place of the line under the top bar, and the panel
  updates LADO: it shows `lado update`'s plan, restarts, and says how the update ended.
- `lado update` backs up lado.db (`~/.lado/backups/`) before installing, and rolls back to
  the old version when the new one does not install right or its UI server does not come
  up, restoring lado.db only when its schema changed. It writes `~/.lado/update.log` and
  `~/.lado/update-result.json`, and refuses a second update while one runs. A session that
  does not resume no longer leaves the "an update did not finish" mark once you resume it.

- Codex CLI as a provider: `lado start --provider codex` and `spawn_worker(provider="codex")`.
  Each Codex agent gets its own Codex home in its config folder (its role as
  `developer_instructions`, LADO's hooks, already trusted, its MCP servers); from your own
  Codex config (`CODEX_HOME` or `~/.codex`, only read) it carries your model settings, your
  trust of the folder and of the repository's own hooks. A folder your Codex does not trust
  makes the agent wait for you, as with Claude Code. Your login is not carried yet: it runs
  on a model that needs none (e.g. a local one through Ollama). Permission modes `default`
  and `bypassPermissions`; in Codex's sandbox a worker may commit on its branch. `lado
  doctor` checks it (tested with 0.162).
- A Codex supervisor starts with one short line from `lado`, since Codex starts its session
  only at its first input: one model turn per start.

- A new agent status, `background`: a Claude Code agent whose turn ended while work it
  started still runs (background subagents, background shell commands) shows `background`
  instead of `idle` in `lado ls`, `list_agents`, the API and the UI, and its session counts
  as working. It takes messages at once, as an idle agent does. OpenCode and Kilo report
  no background work, so their agents stay `idle`. In the UI, busy is now a green dot and
  background a half-filled green one, both pulsing (not with reduced motion), and idle a
  grey ring. The Agents page reads a worker's git state again when the agent leaves busy.
  LADO is now tested with Claude Code 2.1.295.

- UI: the Kits page shows its kits as a grid of compact cards instead of a list of rows.
  A newer version a check found shows as `→ vX` with an ↑ button that opens the update to
  that version; an Available kit has a + by its version; Update…, Remove…, Install… and
  Copy address are in each card's ⋯. The session list's ⋯ now also shows on a touch
  screen.

- UI: a session's card (the tooltip of its row and of its icon in the collapsed list) no
  longer has a dot before the name, whose colour differed from the row's own dot; its
  status word now has its group's colour (green Running, orange Needs you, grey Stopped,
  red for a session whose tmux is gone or whose loop does not run).
- UI: the copy buttons (a session's link, path and git URL, an artifact's link, the
  session row's Copy link) copy in one click also on a page served over plain http from
  another machine (`lado ui --host`), instead of showing the text to copy by hand; that
  field shows only when the browser refuses every way to copy.

## 0.31.0 (2026-10-09)

- An agent's role prompt and its first input (a worker's task, a resumed supervisor's
  messages) are no longer on its process's command line, where `ps` shows them to every
  user of the machine: the role is read from a file, and the first input comes as a message
  from `lado` through the agent's queue, for every provider (Kilo and OpenCode see only its
  one-line notice on their command line, never its text).
- UI: the session's head shows its permission mode in the CLI's tooltip, not in the line.
- UI: a session's head is now the top bar, one line (the facts wrap to a second one in a
  narrow window), so the tabs and the chat start about 90 px higher; its status is a dot,
  in words only for a session that needs an action. The server's address moved into the
  tooltip of the feed's link on every page.
- UI: a Running session in the session list says whether its agents work now: a pulsing
  dot and `2 of 3 agents · 4 min` while some agent is busy, a ring and `1 agent · 12 min`
  (how long it has stood still) when all wait for the human's next message; its card and
  its icon in the collapsed list say it too. The API's `SessionInfo` has `busy` and
  `activity_since`.

## 0.30.0 (2026-10-08)

- kit.yaml takes `expects: {commands: [...]}`: the CLIs a kit cannot work without. A
  session start, resume or new worker is refused, with one error naming every missing
  command and its kit, while one is not on the agents' PATH; `lado kits check` lists them
  and warns about one missing on its machine, `lado kits show` says where each is.

## 0.29.0 (2026-10-08)

- kit.yaml takes `expects: {skills: [...]}`: skills another kit of the session must bring.
  `lado kits check` passes such a kit alone; a session in which no kit brings them does not
  start.
- UI: a popover below its button (a copy field, a row's menu) stays inside the window.
- UI: the Artifacts tab shows how many artifacts the session has; a row opens the artifact
  in the panel on the right.
