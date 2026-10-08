# Changelog

## 0.30.1 (unreleased)

- UI: the session's head shows its permission mode in the CLI's tooltip, not in the line.
- UI: a session's head is now the top bar, one line (the facts wrap to a second one in a
  narrow window), so the tabs and the chat start about 90 px higher; its status is a dot,
  in words only for a session that needs an action. The server's address moved into the
  tooltip of the feed's link on every page.

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
