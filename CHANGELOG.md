# Changelog

## 0.37.0 (unreleased)

- `lado start --prompt TEXT` / `--prompt-file FILE` (`-` reads stdin) and the New session
  window's First message row give the supervisor a first message from you, also on a
  resume, where it comes after LADO's `session resumed`. The supervisor answers in the
  chat; the text never goes on an agent's command line.
- API: `prompt` in `POST /api/sessions` and `POST /api/sessions/{name}/resume`.
- The chat: a closed question card shows the choice you picked once, marked in its list;
  the reply block under it keeps who answered, when, and your comment.

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
