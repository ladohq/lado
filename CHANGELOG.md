# Changelog

## 0.31.1 (unreleased)

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
