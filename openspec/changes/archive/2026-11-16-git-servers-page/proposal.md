Task: LAD-290

## Why

`lado git-server add|list|remove` keeps the human's GitLab and GitHub Enterprise servers with
their tokens, but only in a terminal: a human who runs LADO from its web UI, often in Docker
without a shell at hand, has no way to see, add or remove a git server. The previous change
built no server API for the list on purpose (AGENTS.md, "Only what is used": no screen used
one yet).

Two leftovers of that change are carried here:

- Two servers on one host name with different https ports (`https://git.corp.example` and
  `https://git.corp.example:8443`) are both saved, and both rewrite the same ssh addresses
  (`git@git.corp.example:`, `ssh://git@git.corp.example/`) to their own https address. git
  then silently takes the first rewrite, and `git_servers.server_for` the first server: a
  remote may go to the other server, with its token. Root cause: a server is identified by
  host and port, but git's ssh address of a host carries no port, so the rewrite cannot
  tell the two apart.
- Removing the last server leaves an empty `<LADO_HOME>/git-servers/` behind: the token's
  folder `<id>/` is removed, its parent never.

Options weighed for the screen (cost over the coming work: a commit author per server, a
"Check" of a saved server, github.com in the list, a company certificate):

- A (taken): a server API in `lado.server.git_entries` over the same `lado.git_servers`
  functions the command uses (one rule set, one source of truth), and a Settings page built
  like Model servers (rows, an add form under the list, a removal that asks first). The
  coming fields are one more line in a row and one more field in the same form.
- B: the page runs `lado git-server` as a subprocess. Rejected: the token would go through
  a pipe of another process for nothing, and refusals would have to be parsed back from
  text.
- C: one generic "secrets and servers" page for model and git servers. Rejected: the two
  lists have different rules (names and keys vs hosts and kinds); merging them ties two
  things that change apart.

For the same-host rule: refuse the second server (taken, the human's answer to #7131), or
save it with a warning and rewrite no ssh address of that host for either (rejected: a
silent loss of ssh→https for the first server, and a rule in three places).

## What Changes

- Settings gets a section **Git servers** (`/settings/git-servers`, after Model servers):
  the saved servers, each with its address, its kind, the login it signs in as or `⚠ not
  checked`, and 🗑 Remove, which asks first; **+ Add server** opens a form under the list:
  Address (`https://gitlab.com` filled in and selected while gitlab.com is not saved),
  Token (the secret field of the project page, never shown again) with a link to the
  token page of the kind the address looks like and the rights the token needs, and a
  choice of the kind only when the server does not answer or answers as neither kind.
  The section's lead says that running agents get a change after a restart.
- The address is asked **without the token** as the typing settles: the kind it looks like
  is only a hint for the token's link; Add server sends the token and saves exactly as
  `lado git-server add` does, each request at most 5 s.
- Every refusal on the page is the command's, in words that name no command (a wrong token,
  a server that does not answer, github.com through gh's login, `http://` with its warning);
  a server that sends elsewhere is refused with no choice of the kind on the page.
- Server API: `GET /api/git-servers`, `POST /api/git-servers/check` (no token),
  `POST /api/git-servers` (the token in the body only), `DELETE /api/git-servers/{host}`.
  No answer, log or error carries the token.
- **One git server per host name**, in the command and on the page alike: a server whose
  host name already has a server on another port is refused, naming that server; the
  same host and port still replaces.
- `lado git-server remove` (and the page's Remove) removes `<LADO_HOME>/git-servers/`
  itself with the last server.
- Docs: `docs/design/ui.md` (Settings, Git servers), `docs/cli.md`, `docs/design/modules.md`,
  AGENTS.md's Layout line of `server/`, CHANGELOG.md (the 0.48.0 entry of git servers).

## Scope

`src/lado/git_servers.py` (the host-name rule, the page's words of refusals, the request
without a token, the folder), `src/lado/git_kinds/base.py` (the request without a token),
`src/lado/server/git_entries.py` (new), `src/lado/server/app.py` (routes, `SECRET_ROUTE`),
`src/lado/server/models.py`, `src/lado/cli.py` (the refusal's hint), `web/src/GitServers.tsx`
(new), `web/src/settingsSections.ts`, `web/src/Settings.tsx`, `web/src/api.ts`,
`web/src/styles.css`, `web/openapi.json`, `web/src/api.gen.ts`, tests (unit, vitest, UI e2e),
the docs above.

## Out of scope

- A commit author per server, "Check" of a saved server, `lado doctor`'s servers, clone
  hints, github.com in the list, a company certificate, `glab`, ssh keys and other kinds:
  later tasks of the same work, each a field or a line in this page.
- **Change** of a saved server (✎): adding the same address again replaces its token, as the
  command does; a separate form would be a second way to the same thing.
- A choice of the kind for a server that sends elsewhere: the human's answer to #7131; the
  page refuses it as the command does without `--kind` (the command keeps `--kind`).
- The kind told without the token as more than a hint: the human's answer to #7131; only the
  check with the token decides it.
- Telling running agents of a change: they get the list at their launch (the previous
  change's rule); the page says so.
- Two servers already saved on one host name: no released version saved them (0.48.0 is not
  released), so no migration or warning for them.

## Impact

- Minor version: a Settings page and server API; 0.48.0 is already the next minor (it brings
  `lado git-server`), so no further bump. No schema change, no MCP tool, no new dependency.
- `lado git-server add` refuses one more case (another port of a saved host name).
