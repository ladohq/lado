Task: LAD-293

## Why

A saved git server is checked only once, when it is added. Later its token expires, is
revoked or loses a right, and the human learns it from an agent whose push fails. Settings →
Git servers shows each server's facts as running text, with no way to check a server or to
replace its token except adding it again, and its explanations take more room than its
values. A few edge cases of the earlier git server work are open too: a host written with a
trailing dot (`gitlab.corp.ru.`) slips past "one server per host"; a remote written with
another letter case or with `:443` gets the token but not the commit author; a removal can
race a replacement of the same server; a failed write leaves a hidden temporary file.

## What Changes

- **Check a saved server.** `lado git-server check <address>` and `Check` on the server's
  panel ask the server again with the saved token and say in one line what they found: works
  (with the login), the token is refused, the token lacks a right agents need, no answer in
  5 seconds, the certificate is not trusted, a redirect, another kind than the saved one, or
  neither kind. A check reads the token's rights: GitLab's own information about the token,
  GitHub's list of a classic token's scopes; a GitHub token that tells no scopes (a
  fine-grained one) works with "the token's rights are not checked". A check stores nothing,
  except that a passing check saves the login it saw, so a server saved without a check is
  no longer "not checked".
- **Add and Replace token warn of a missing right.** A token the server accepts but that
  lacks `write_repository` (GitLab) or `repo` (GitHub) is saved with a warning that agents
  can clone but not push, and a way to replace it.
- **Settings → Git servers by the approved layout.** Explanations go behind ⓘ buttons; a
  server's row opens to a panel with Sign-in (`Check`, `Replace token`), Commit author
  (`Set author`, `Edit`, `Remove` with `Undo`) and `Remove server`; Add on an address
  already saved leads to that server's Replace token; the page shows at most one result
  line at a time, and the focus after each action is fixed. Mockups:
  `ui-design/lad-292-v2/mockup.html` (the session's, approved) and the run's
  `mockup-check-cases.html` for the cases the approved one does not draw.
- **Replace token** sends the saved address and the new token to the same API as Add. When
  the server does not answer, the human may save the token without a check under the saved
  kind.
- **Small fixes.** A trailing dot is dropped from a host; commit author entries match a
  remote's host in any letter case and with the scheme's own port written out; saving,
  replacing and removing a server take a lock of `LADO_HOME`; a removal whose server is gone
  but whose empty folder cannot be removed warns instead of failing; the refusal of an old
  git names every server with an author; an author file's failed write leaves no temporary
  file; a token refused by both kinds' APIs (a gateway that answers 401 everywhere) is
  refused without guessing a kind; the page's Add, when the server stops answering between
  the address check and Add, offers the kind choice.
- Docs: `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, CHANGELOG.md's 0.48.0
  entry of git servers.

## Scope

`src/lado/git_servers.py` (the check, scopes, the trailing dot, the author globs, the lock,
the removal, the old-git refusal, the author file), `src/lado/git_kinds/` (the scopes of
each kind), `src/lado/model_servers.py` (an answer's headers), `src/lado/cli.py`
(`lado git-server check`), `src/lado/server/git_entries.py`, `src/lado/server/app.py`,
`src/lado/server/models.py` (the check route, the warnings, `choose_kind`),
`web/src/GitServers.tsx`, `web/src/InfoTip.tsx`, `web/src/styles.css`, `web/openapi.json`,
`web/src/api.gen.ts`, tests (unit, integration, vitest, UI e2e), the docs above.

## Out of scope

- `lado doctor`'s list of servers with their check, and clone hints from the list (a failed
  clone from a listed host naming its server, from an unlisted host suggesting to add one),
  in the command and in the UI's clone window: the human's answer to #7241 q1, a task of
  their own, to keep this one within three days of work.
- github.com in the list and signing in to GitHub from the UI: a later task of the same
  work; the github.com block of the approved mockup is not built.
- The company certificate: a later task; its row of the panel is not built, and the
  "certificate not trusted" line says in its ⓘ what to do meanwhile (#7241 q2).
- `glab` in LADO's image: a later task.
- An expired token seen on a closed row before `Check`: it needs the token's expiry or the
  last check stored, a schema change; the results of a check are not stored.
- A list of running agents to restart after a change: a feature for all of Settings.
- Editing a saved server's address in place: the address is the server's identity; add
  the new one and remove the old.
- ssh remotes written with an upper-case host (`git@GitLab.corp.ru:`): git rewrites them to
  https only as written, so neither token nor author reaches them; unchanged.

## Impact

- Minor version: a CLI command, a server API route and UI; 0.48.0 is already the next minor
  (unreleased), so no further bump. No schema migration: a passing check writes the login
  column that exists.
- New: `lado git-server check <address>` (exit 0 works, 1 a failure, 2 an address it does
  not take); `POST /api/git-servers/{host}/check`; `warning` and `missing_scopes` in Add's
  answer; `choose_kind` in Add's refusal.
- Changed: Add warns instead of saving silently a token without the push right; the page's
  texts and layout; the refusal of an old git where authors are set names every such server.
