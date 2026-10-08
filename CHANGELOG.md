# Changelog

## 0.30.1 (unreleased)

- An agent's role prompt and its first input (a worker's task, a resumed supervisor's
  messages) are no longer on its process's command line, where `ps` shows them to every
  user of the machine: the role is read from a file, and the first input comes as a message
  from `lado` through the agent's queue, for every provider (Kilo and OpenCode see only its
  one-line notice on their command line, never its text).
- UI: the session's head shows its permission mode in the CLI's tooltip, not in the line.
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
