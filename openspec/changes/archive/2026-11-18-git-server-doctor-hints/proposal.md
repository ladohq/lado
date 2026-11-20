Task: LAD-297

## Why

A saved git server's token expires or is revoked, and today the human learns it only from a
failed clone or push whose text says `asks for a login; set up a git credential helper` and
names no server, or from opening Settings → Git servers and pressing Check. `lado doctor`
does not look at git servers at all. A clone from a GitLab or GitHub Enterprise host that is
not saved says nothing about adding it, though adding it is what makes LADO and its agents
sign in. A few small defects of Settings → Git servers were left from its last change.

## What Changes

- **`lado doctor` checks each saved git server**, by the same check as `lado git-server
  check`: one line per server, `ok` or `warn` with the line and the hint; servers asked at
  once; no line with none saved; never `FAIL`; nothing written to lado.db.
- **A failed clone or listing names its git server.** From a saved server's host refused
  (login asked, access refused, not found): the reason names the server, and the hint is
  `lado git-server check <address>` with the way to replace the token. From an unsaved http(s)
  host asking for a login or refusing access: the hint is `lado git-server add <address>
  --token`. A new kind `access_denied` for git's `The requested URL returned error: 403`.
  github.com and the failures that are no access failure keep their texts. The same texts
  reach kits' and marketplaces' git failures, which share these kinds.
- **The UI's clone notes open Settings.** In the New session window and a project's Add
  repository, a git server hint shows its sentence and `Check <host> ↗` or `Add git server ↗`,
  which opens Settings → Git servers in a new tab: the server's panel with its check running,
  or the add form with the address filled in.
- **Settings → Git servers' small fixes.** One `Replace token` after a check that finds the
  token refused or short (Sign-in's own, as the main button); no `✓` before a `Works:` line;
  an open ⓘ tip stays by its button when the layout switches between phone and wide; the
  author's Remove and Undo off while they ask.
- **Docs and housekeeping.** `docs/cli.md` (doctor, the clone hints, and that a gateway
  answering OAuth's `invalid_token` on every path is taken for GitLab), `docs/design/ui.md`,
  `docs/design/modules.md`; BACKLOG.md loses its entry of the flaky Kilo smoke on macOS, which
  task LAD-295 holds; CHANGELOG.md's 0.48.0.

Mockup: the run's `mockup-git-server-hints.html` (sections 2, 3 and 4, variant A; section 1
was declined).

## Scope

`src/lado/doctor.py` (the git server lines), `src/lado/git_servers.py` (a check that saves
no login; the clone texts of a server), `src/lado/clone.py` (the kind `access_denied`, the
saved and unsaved host texts, the server's way out on `CloneError`), `src/lado/server/models.py`
and `src/lado/server/clones.py` (`CloneRefused.git_server`), `web/openapi.json`,
`web/src/api.gen.ts`, `web/src/Launch.tsx`, `web/src/LaunchWhere.tsx`,
`web/src/ProjectRepos.tsx`, `web/src/GitServers.tsx`, `web/src/InfoTip.tsx` or
`web/src/Menu.tsx`, `web/src/styles.css`, tests (unit, integration, vitest, UI e2e), the docs
above, BACKLOG.md, CHANGELOG.md.

## Out of scope

- The System panel and its copied system info: unchanged, the human's answer to #7332 q1;
  doctor in the command is the place to see every server checked, Settings → Git servers the
  place to check one.
- github.com in the list of servers and signing in to GitHub from the UI: a later task; its
  clone hints stay as they are (but for the new `access_denied` kind, which gets the
  `gh auth status` hint its `not_found` has).
- The company certificate, `glab`: later tasks.
- An expired token seen before a check: it needs the token's expiry stored, a schema change.
- An ssh key refused by an unsaved host: its ssh hint stays; LADO does not suggest adding the
  server instead (#7332 q4: the human chose ssh for it).
- A host saved under another scheme or port than the URL's (`http://` for a saved
  `https://`): git takes no saved token for it, so no server hint; adding it would be
  refused as the same host.
- The flaky tests of LAD-295 and LAD-296: tasks of their own.

## Impact

- Version: 0.48.0 is the next minor and unreleased, so no further bump; the change adds to
  its git servers entry. No schema migration.
- CLI: `lado doctor` prints `git server <address>` lines; a clone's, listing's or kit's git
  failure has new texts for git servers and the new kind `access_denied`.
- API: `CloneRefused.git_server` (`{way: "check" | "add", host, address, text}` or null),
  `access_denied` among its kinds; `web-types` regenerated.
- UI: the clone notes' button; Settings → Git servers' `?check=` and `?add=`; the page's
  fixes.
