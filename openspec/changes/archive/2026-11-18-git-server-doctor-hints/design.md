## Context

`git_servers.check(at)` (the previous change, git-server-check) asks a saved server again with
its token: every kind's user API at once (`_ask_kinds`, 5 s per request), then the token's
rights (`_rights`, one more request of up to 5 s), so one check takes at most about 10 s. It
returns a `Check` with the command's `text`/`hint` and the page's `page`/`page_hint`, and on
`ok` it saves the login it saw (`_save_login`, under `git-servers.lock`). It raises `Refused`
for no such server, an unknown kind or a missing token file, and `BadAddress` (a
`ValueError`) for a saved address the current address rule no longer takes.

`lado doctor` (`doctor.run_checks`) builds `Check(name, level, detail, hint)` lines; its
`Model servers` line probes every saved model server at once in a thread pool. Doctor never
migrates or writes lado.db (docs/cli.md); a check that reads lado.db says `not checked` when
lado.db is not at this LADO's schema (`NOT_AT_SCHEMA`).

A clone's or listing's failure (`clone.failure`) and a kit's git failure (`clone.explain`,
for `gitcache`) share `_told` → `kind_of(stderr)` (the regexes of `KINDS`) → `_reason(kind,
address, branch, project)`, which gives the reason and a `runtime.Hint(text, command)`; only
github.com gets login and access hints. git runs with LADO's git variables
(`agent_env.for_git(remote=url)`), which give a saved server's token to git for its https
URLs and rewrite its ssh addresses to https (`git_servers.variables`, `server_for`). With a
revoked token git prints `Authentication failed` (`login_needed`); with a token GitLab takes
but that may not read the project, `The requested URL returned error: 403` (no kind today:
`git_failed`); with no access to a private repository GitHub and GitLab answer `not found`.

The UI shows a `CloneRefused {message, kind, hint}` in four places: under Repository URL
(`LaunchWhere.tsx`), at a failed clone's end (`Launch.tsx`), and twice in a project's Add
repository (`ProjectRepos.tsx`), each with `FolderHint` (sentence, command, Copy). The New
session window is a modal dialog: leaving it for Settings loses what is typed.

The root cause of the task: the failure texts of a clone were written before git servers
existed, so they know only github.com and the machine's own login; and doctor was left out
of the git servers work by the human's split of the previous task (#7241).

Settings → Git servers (`GitServers.tsx`): a check's line under Sign-in carries a way out
(`way: "replace"`) beside Sign-in's own `Replace token`, so after a refused token the panel
shows two; `.gx-result.ok > .t::before` puts `✓` before every ok line, `Works: …` too; the
author's `Remove` and `Undo` stay on while they ask; `InfoTip` places its tip with
`Menu.useBelow`, which places again on a window `resize`, but an open tip stays at its old
place when the page switches between the phone and the wide layout (#545).

## Goals / Non-Goals

Goals: every saved server checked by `lado doctor`; a clone's failure that names the server
to check, or suggests adding one; the UI's notes leading to Settings → Git servers; the page's
leftovers. Non-goals: the proposal's Out of scope, the System panel above all (#7332 q1).

## Decisions

### D1. Doctor uses the same check, which saves no login there

`git_servers.check(at, save_login: bool = True)`; doctor passes `False`. One check, one set of
outcomes and texts, so doctor and `lado git-server check` never disagree.

Options weighed:
- a. Call `check` as it is: it would write the login to lado.db, against "doctor never
  writes lado.db"; cheap now, but a rule of doctor broken for good.
- b. A read-only copy of the check for doctor: a second source of the outcomes that drifts
  (AGENTS.md: one source of truth).
- c. **Chosen**: a parameter. Cost: one argument and one test that doctor writes nothing.

### D2. Doctor's lines: one per server, asked at once, beside the model servers

`doctor.check_git_servers() -> list[Check]`: no lado.db or no server → `[]`; `SchemaError` →
`[Check("git servers", INFO, NOT_AT_SCHEMA)]`. Each server is checked in a thread pool, one
worker per server; its line is named `git server <address>`: `ok` → `OK`, `found.text`;
any other outcome → `WARN`, `found.text`, `found.hint`; `Refused` → `WARN`, its text and
hint; `ValueError` (a saved address the address rule no longer takes) → `WARN`, `its saved
address is not taken any more (<why>)`, hint `remove it: lado git-server remove <address>`;
`OSError` → `WARN` with its reason. Never `FAIL`. In `run_checks` the git servers start in a
pool before the model servers are probed and are collected after, so doctor waits about the
longer of the two (at most about 10 s), not their sum. The lines stand after `git author`.

Why one line per server, not one `Git servers` line as the model servers: the task asks for
a failure "in its line" (the brief), and a check's hint (a command with the address) needs a
line of its own to be copied.

### D3. The clone's server: the one git takes the token of

`_told` looks up the saved servers once (`state.git_servers()` when lado.db is at this
schema; none otherwise, and on `SchemaError`) and passes `_reason` the server
`git_servers.server_for(url, servers)` gives: the very server whose token git used, by host
and port for https, by host for the ssh forms LADO rewrites. A host saved under another
scheme or port than the URL's gets no server hint (git took no token from it), and no add
hint either (adding it would be refused as the same host): its kind's plain text stays.

### D4. A new kind `access_denied`

`KINDS` gets `("access_denied", re.compile(r"The requested URL returned error: 403"))`
after `login_needed` and before `not_found`. Reason `<host> refused access`; github.com's
hint is `gh auth status`, as its `not_found`; other hosts none, but for D5's texts. It is the
only new git line; the threshold of the task (more than about five patterns) is far.

### D5. The texts

A saved server `S` (address `<root>`, D3), kinds `login_needed`, `access_denied`,
`not_found`:

| Kind | Reason |
|---|---|
| `login_needed` | `<host> refused the token of the git server <root>` |
| `access_denied` | `<host> refused access with the token of the git server <root>` |
| `not_found` | `no repository there, or the token of the git server <root> cannot read it` |

Hint: `Check the git server; if its token expired or was revoked, replace it (lado
git-server add <root> --token):` `lado git-server check <root>`. Page text: `Check this git
server; if its token expired or was revoked, replace it there.`

An unsaved host (D3) of an `http`/`https` URL, not github.com (`git_servers.GITHUB_COM`),
kinds `login_needed` and `access_denied`: the reason stays (`<host> asks for a login`, the
credential helper's half dropped; `<host> refused access`); hint `Add it as a git server with
a token:` `lado git-server add <root> --token`, `<root>` by `git_servers.address(<scheme>://
<host>[:<port>]).root` (no hint when it refuses the host). Page text: `Add <host> as a git
server with a token: LADO and its agents then sign in to it.` `not_found` of an unsaved
host keeps no hint: it is as often a wrong address (#7332 q3 concerns a saved server only).

ssh failures of an unsaved host keep the ssh hints (#7332 q4).

### D6. `CloneError.server`, `CloneRefused.git_server`

`clone.CloneError` gets `server: ServerWay | None` (a frozen dataclass in `clone.py`: `way`
`"check"` or `"add"`, `host` (the server key, `S.host` or the new root's key), `address`
(`<root>`), `page` (the page text)) beside `hint`, which stays the command's. The CLI prints
`hint` as before. `models.CloneRefused` gets `git_server: GitServerWay | None` (`way, host,
address, text`), filled in `server/clones.refused`; a clone job's error is a `CloneRefused`,
so it carries it too. `make web-types` regenerates `web/openapi.json` and `api.gen.ts`.

Options weighed: the page could tell the way from `kind` and the URL itself; that repeats the
core's decision in TypeScript (two sources). A `runtime.Hint` with a URL instead of a command
would break every caller that copies the command. The extra field is the cheapest.

### D7. The UI's note: a link to Settings in a new tab

One component (`GitServerNote`, beside `FolderHint` in `LaunchWhere.tsx`) shows the page
text and an `<a className="quiet button-like" target="_blank" rel="noopener">`, `Check
<host> ↗` (`/settings/git-servers?check=<host>`) or `Add git server ↗`
(`/settings/git-servers?add=<encoded address>`), with the app's base path; its accessible
name says it opens a new tab. The four places show it instead of `FolderHint` when
`git_server` is set. A new tab keeps the modal window and its fields (#7332 q2); the human
retries there after fixing. At 760 px or less the link is 44 px high, as the window's other
note buttons.

### D8. The page's `?check=` and `?add=`

`GitServersPage` reads `useSearchParams` once its list has loaded: `check=<host>` of a saved
server → open its panel and run `check(server)` as the button does (its focus rules); `add=`
→ open the add form with the address, which checks it as typed (no token), focus in Token;
then `setSearchParams({}, { replace: true })`. An unknown host or an empty value opens
nothing. A reload does not check again.

### D9. One Replace token

`Result.way` loses `"replace"`; a line about a refused or short token (a check's
`token_refused` and `scopes_missing`, a save's missing-right warning at Sign-in or at the
panel's top) sets `tokenBad`, which makes Sign-in's `Replace token` `primary` while it shows.
`Check again` lines are unchanged. `✓` stays on the page's ok lines but a check's `Works: …`
(a class of its own on that line). Variant A of the mockup (#7332 q5).

### D10. The tip after a layout switch

The developer finds why `useBelow` does not place the tip again when the layout switches
(the resize render may run before the Shell's `usePhone` switch re-renders the page, or the
button moves inside `.content` without a resize) and fixes it in `useBelow` or `InfoTip`, so
every tip of the UI (and the menus on `useBelow`) gains it: for instance, place again on the
next animation frame after a resize and on a `matchMedia` change of the phone query. Proved by
a UI e2e test at 390 → 900 px (vitest has no layout).

### D11. Remove and Undo busy

The author's `Remove` and the `Undo` of its line are `disabled` while their request runs, as
Save author is.

### D12. Docs and housekeeping

`docs/cli.md`: doctor's git server lines (beside `Model servers`), the clone texts (the
clone section), and one line in `lado git-server add`'s refusals: a gateway that answers
OAuth's `invalid_token` on every path is taken for GitLab, as one answer cannot tell them.
`docs/design/ui.md`: the clone notes' link, the page's `?check=`/`?add=`, one Replace token,
the tip. `docs/design/modules.md`: `doctor.py`, `clone.py`. BACKLOG.md: the entry "Flaky:
the Kilo smoke on macOS times out on `kilo models`" goes, as task LAD-295 holds it.
CHANGELOG.md: the 0.48.0 git servers entry grows by doctor and the clone hints (no new
version: 0.48.0 is unreleased).

## Against AGENTS.md and the roadmap

- Neutral core: nothing here touches `providers/`; doctor, clone and the page are the same
  for every agent CLI.
- One source of truth: one check for doctor, the command and the page (D1); the clone's
  decision in the core, the page only shows it (D6).
- No silent drops: a server doctor cannot check is its own `warn` line (D2); a host saved
  under another scheme gets its kind's plain text, said in the docs (D3).
- Only what is used: `git_server` is read by the four notes; `save_login` by doctor.
- The coming work (github.com in the list) adds a server for github.com; D3's `server_for`
  then finds it and github.com's texts give way to D5's without a change here.

## Risks / Trade-offs

- A doctor run waits up to about 10 s with a server that hangs; as the model servers do.
- `not_found` from a saved server suggests Check also for a mistyped path (#7332 q3: both
  are named in the text).
- git's English lines are matched with `LC_ALL=C` as today; a git server that prints its
  own words for 401/403 still ends with git's own `fatal:` line.
