Task: LAD-105

## Why

Symptom, found while checking 0.41.0rc1: in the New session window, New empty folder with the
kit `sdlc` and no tracker kit, **Create and start** first makes the folder and its repository
(`~/lado/rc-check-sdlc`, one empty commit), and only then is refused with `kit "sdlc" expects
skill "tracker"` (400). The window turns Where to Folder on the folder it just made, and an
empty repository the human never wanted stays on disk.

Cause, checked against the code at d432b0f6: before it makes anything, a fresh start checks
only the folder, the author, the session's name and the supervisor CLI's login
(`runtime.check_start_login`, LAD-157's way for a clone and `--new`). Every other check of a new
session (at least one kit, the kits resolved with their expected skills, the title, the
permission mode, the commands the kits expect, the model) lives inside `runtime.start_session`,
which needs the folder to be a repository already (`check_repo`). So `scratch.make` runs, then
`start_session` refuses. The living spec says so on purpose (session-scratch, "A failed fresh
start removes what it made": "A start refused after the repository was made SHALL keep it"),
and the same order holds for Set up (`setup.make`) and `lado start <git-url>` (the clone).

Options with their long-term cost:

- **One pre-check of a new session that needs no folder (taken, the human's decision #6749).**
  `start_session`'s checks of a new session move into one function that takes the folder as a
  path that may not exist yet; `start_session` calls it, and so do the fresh start, the set-up
  and the CLI's clone before they change anything. One source of truth: a check added to the
  start later is a check before the folder too. Cost: a refactor of `start_session`'s head.
- Make the folder, and remove it on a refusal: the folder still appears and goes; a set-up of
  the human's files and a downloaded clone cannot be undone this way. Rejected as the fix;
  kept only as a safety net for a fresh start refused late (below).
- Repeat the kits' checks in the window before Create and start: a second source of truth in
  TypeScript, and the CLI keeps the bug. Rejected.

## What Changes

- A new session is checked whole (kits, skills, name, title, permission mode, the kits'
  commands, the provider's login and model) before New empty folder, `lado start --new`, Set
  up and `lado start <git-url>` make a folder, a repository or a clone; a refusal there leaves
  the disk as it was. For New empty folder the window stays on it with the refusal (the Team
  section opens for a kit's refusal, as for a folder).
- A fresh start refused after its repository was made after all (a race: the name taken in
  the same second, the login gone, the agent's window failed) removes the folder it made when
  it still holds only that repository's one empty commit and no session uses it;
  `lado start --new` then says `lado: removed <folder>, which this start made`. When the folder
  changed meanwhile, it stays, as now (`the repository stays in <folder>`).
- Docs: `docs/cli.md` (`--new`, the clone), `docs/design/ui.md` (New empty folder's refusal),
  `docs/design/modules.md` (`runtime`, `scratch`), CHANGELOG under Fixed.
- Version: a fix, patch; it goes under the open `## 0.47.0 (unreleased)`.

## Scope

`src/lado/runtime.py` (the pre-check, `start_session` on it, `check_start_login` replaced),
`src/lado/scratch.py` (removing an unused fresh repository), `src/lado/cli.py` (`--new`, the
clone), `src/lado/server/app.py` (`POST /api/sessions` for scratch and setup), unit tests, a
vitest of the window, the docs above, CHANGELOG.

## Out of scope

- The window's Clone from URL: its clone runs as its own job (`POST /api/clones`) before
  `POST /api/sessions`, so a check before it needs a new request; the human's decision #6749:
  a separate task if wanted. A start refused after it keeps the clone, as now.
- Removing a set-up's repository or a clone after a late refusal: the set-up holds the human's
  files and the clone a download; both stay, as the living specs say.
- Showing a kit's refusal in the window before Create and start is pressed: a second source of
  truth (rejected above); the refusal on press now changes nothing on disk.
- Checks that need the repository itself (`check_repo`, a resume's folder): a fresh start's
  folder has none yet; they stay in `start_session`.

## Impact

- A refused fresh start, set-up or CLI clone leaves nothing behind for every refusal the start
  can give before it launches; only a late refusal of a fresh start removes a folder, and only
  one LADO made and nothing has touched.
- `runtime.check_start_login` is gone; its callers use the pre-check, whose refusals are the
  same as `start_session`'s (the same texts, 400/409 in the API).
- No schema change, no API model change, no CLI option change.
