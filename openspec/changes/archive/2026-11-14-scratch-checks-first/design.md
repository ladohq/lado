## Context

`runtime.start_session` checks a new session in its head (lines ~788–862 at d432b0f6): kits not
empty, the prompt, the folder (`check_repo`, `projects.refusal`), the name and title, a taken
name (`SessionExists`), the provider (given, or `_new_sessions_provider`), the permission mode,
`kits.resolve`, `_check_commands`, the model (`_start_model`) and the login (`check_login`).
Only then does it store anything (`state.add_session`). A fresh start, a set-up and the CLI's
clone change the disk before calling it, guarded only by `runtime.check_start_login` (the
login and model, when the provider is known) and `runtime.check_name`.

## Decisions

**D1. One function `runtime.check_new_session(path, name, permission_mode, provider, kit_names,
without, title, model, project=None)`, the new session's checks without the repository.** It
takes the folder as a full path that may not exist and returns what `start_session` needs
next (the session's name, the stored title, the provider chosen, the resolved kits, the
layers and base environment, the start model, the warnings), as a small dataclass. It runs, in
`start_session`'s order: kits not empty, the name (`slug`, `check_name`: another folder's
session) and title (`check_title`), a taken name (`SessionExists`), the provider (given, else
`suggested_provider(None, …)` as `_new_sessions_provider` does; when none can be chosen it
refuses as `start_session` does now), `_check_permission_mode`, `kits.resolve`,
`_check_commands`, `_start_model` and `check_login(…, logins.SESSION, …)`. Why: one source of
truth; a check added to the start later is a check before the folder too.

**D2. `start_session` calls `check_new_session` for a new session (`not old`) after
`check_repo`.** The repository's root replaces the path given (a fresh start's root is its
real path: `scratch.make` returns it). A resume keeps its own path through the same code it
has now. Refusals keep their types and texts (`LadoError`, `kits.KitError`, `SessionExists`,
`ModelRefused`), so the API's status codes and the CLI's lines stay.

**D3. `runtime.check_start_login` goes; its callers use `check_new_session`.** Callers:
`cli._start_new`, `cli._start_clone` (the clone's folder as the path), `app.start` for
`scratch` and `setup`. Its unit tests move to `check_new_session`'s. A provider that cannot be
chosen before the folder exists (several installed, none given, no past session) refuses
before the folder too, with the same text as later: no change for the human but the order.

**D4. `scratch.make` reports what it made; `scratch.remove_unused(path, made)` undoes it
after a late refusal.** `make` returns the root and the path it created (the topmost new
folder) or None (an empty folder given). `remove_unused` removes it (or `.git` alone) only when
the folder holds nothing but `.git` and `.DS_Store`, `git rev-list --all` is the one commit
with the subject `Start from scratch`, `git status --porcelain` is empty, and
`state.last_session(root)` is None; it returns whether it removed. `cli._start_new` and
`app.start` (scratch) call it on any refusal of `start_session`. Why the conditions: a removal
must never take the human's work or a session's folder.

**D5. The window keeps its code path.** `Launch.createAndStart` already turns Where to Folder
only when `getFolder(where)` answers `ok`; with no folder made it stays on New empty folder and
shows the refusal (Team opens for a kit's refusal, as now). A vitest pins it; the comment above
`createAndStart` is corrected.

## Test layers

- D1–D3: unit (`tests/test_runtime.py`, `tests/test_cli.py`, the server's tests with
  TestClient: `POST /api/sessions` with `where.kind` `scratch` and `setup` and a kit that lacks
  a skill → 400, the folder unchanged). No new process boundary: no integration test.
- D4: unit with real git in a temp folder (each condition that keeps the folder).
- D5: vitest of `Launch` (a 400 on Create and start with the folder not made).
