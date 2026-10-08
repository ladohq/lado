# Changelog

## 0.30.0 (unreleased)

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
