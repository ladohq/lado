## Context

`lado.git_servers` holds the rules of git servers (address, the github.com refusal, the
token's checks, the probe, save, remove) and `cli.py` the command's words around them.
Settings → Model servers is the pattern for a saved list with secrets on a page:
`lado.server.model_entries` calls the core, `models.EntryRefused` carries a refusal under a
form field, `SECRET_ROUTE` keeps a 422 from repeating a secret, `ModelSources.tsx` draws rows,
the add form, `SecretField` and the removal that asks first. Each Settings section is one entry
of `web/src/settingsSections.ts` and one page of `Settings.tsx`'s `PAGES`.

The human's answers (#7131): the scale full; the same-host rule refuses; one `+ Add server`
with gitlab.com filled in; the address checked without the token as the typing settles, its kind
a hint only; the kind chosen by hand when the server does not answer or answers as neither (a
redirect is refused with no choice); an address already saved is replaced by Add, no Change;
Remove asks first.

## Goals / Non-Goals

Goals: see, add and remove git servers in Settings with the command's rules and words; the
token only in one request's body; the same-host rule and the empty folder fixed in the core,
for the command and the page. Non-goals: the proposal's Out of scope.

## Decisions

### D1. One core, two front ends

The page's server code is `src/lado/server/git_entries.py`, as `model_entries.py` is for
model servers: `listing`, `check`, `add`, `remove`, each calling `lado.git_servers` and turning
`git_servers.Refused` into `models.EntryRefused` (reused: message, hint, field, warnings).
`cli.cmd_git_server_add` and `git_entries.add` run the same sequence of checks; the sequence
moves into one function `git_servers.add(at, token, kind_name, warn)` (address checks,
`check_git`, `check_token`, `probe`, `save`) that both call, so the command and the page cannot
drift. `cli.py` keeps only reading the token and printing.

### D2. Refusals carry their field and the page's words

`git_servers.Refused` gains `field` (`address`, `token`, `kind` or "") and `page`/`page_hint`
(None: the command's own), as `model_settings.Refused` has. Only lines that name a command get
page words: the address's user/password refusal (`its token: --token` → `put the token in
Token`), `_kind_hint` (→ `If the server is there for git but its API is not reachable from
here, choose its kind to save it without a check.`), "answers as GitHub and as GitLab; say
which: --kind …" (→ `choose its kind`), `check_git`'s `remove the servers (lado git-server
remove …)` (→ `update git`), the same-host hint (→ `Remove it first if the server moved to
this address.`), and "no saved git server; see them: lado git-server list" (→ no hint). The
fields: address checks, github.com, same host, sends elsewhere, does not answer → `address`;
empty, uncarriable or too large token, refuses the token, lacks read_api → `token`; answers as
both, as another kind than chosen → `kind`; git too old, a token file that cannot be written →
"".

### D3. The check without a token

`Kind.request(root, token)` takes `token: str | None`; None sends no credential header.
`git_servers.hint(at)` asks every kind at once with no token (`model_servers.ask_all`, the same
5 s cut and no redirect) and answers one of: a kind (exactly one kind's path answered as that
kind's refusal of a missing token, `Kind.refusal`, or its user); `silent` (no HTTP answer: the
`_silent` why); `moved` (a redirect: refused); `unknown` (neither kind, or both). `silent` and
`unknown` show the kind choice; a kind is only a hint and is never sent to Add (the page sends
`kind` only when the human chose one). Why not trust it: the human's answer #7131, and a proxy
in front of a server can answer 401 for any path. The check runs `check_not_github`, the
address rules, the same-host rule (D5), `check_git` and the plain-http warning first, and asks
no server when one of them refuses.

### D4. API

- `GET /api/git-servers` → `GitServers { servers: GitServerInfo[], kinds: GitKindInfo[] }`;
  `GitServerInfo { address, host, kind, kind_title, login: str | None, has_token }` (host is
  the server's key, `host[:port]`), `GitKindInfo { name, title, scopes }`. No lado.db is made
  (`database` dependency, as model settings).
- `POST /api/git-servers/check` `{ address }` → `GitServerCheck { address: str | None (the
  root), hint: str | None (a kind's name), token_page: str | None, scopes: str | None,
  choose_kind: bool, saved: bool, refusals: EntryRefused[], warnings: str[] }`; saves nothing,
  carries no token.
- `POST /api/git-servers` `{ address, token, kind: str | None }` → `GitServerAdded { server:
  GitServerInfo, line: str | None, replaced: bool, warnings: str[] }`; 400 `EntryRefused`.
- `DELETE /api/git-servers/{host:path}` → `GitServers`; 400 `EntryRefused` for no such server
  or a folder that cannot be removed.
- `SECRET_ROUTE` adds `git-servers(/|$)`. The routes take `guard.changes` as model servers do.
  The token is a `str` field of the body only; no response model has a token field.

### D5. One server per host name

`git_servers.check_host(at)`: a saved server whose host name (`urlsplit(address).hostname`)
equals `at.host` and whose key differs from `at.key` refuses `at`, field `address`:
`<host> already has a git server, <its address>; LADO keeps one server per host name, as git's
ssh addresses (git@<host>:…) carry no port`, hint `remove it first: lado git-server remove
<its address>`. It runs in the add sequence (D1) before the token is read and in the check
(D3). `save` checks it again inside its write, against an add of another port at the same
moment. No migration: no released version saved such a pair (0.48.0 is unreleased).
Rejected: keep both and drop their ssh rewrites (a silent change for the first server; rules
in `_entries`, `server_for` and the list).

### D6. The empty folder

`_remove_token` removes `<id>/`, then, when `state.git_servers()` is empty, `git-servers/`
itself through `open_chain((), make=False)` and `os.rmdir(TOKENS, dir_fd=…)`, ignoring
`ENOTEMPTY` and `ENOENT` (an add at the same moment keeps its folder). `_write_token` retries
once when its chain finds the folder gone between its opening and its `mkdir`.

### D7. The page

`web/src/GitServers.tsx` (`GitServersPage`, rows, `AddGitServer`, `RemoveGitServer`) reuses
Model servers' classes and components: `mx-srcs`/`mx-src`/`mx-head` rows without a chevron
(a server has nothing to open), `mx-form` with `launch-grid` fields, `SecretField`, the kind
choice as `segments` (General's Theme), `mx-confirm` for Remove, `refusalOf` for a request
LADO's server did not answer, `useDebounced` with `MODEL_DEBOUNCE` for the check, and
`useScrollAnchor` so nothing moves under the pointer. The section is the fourth entry of
`SETTINGS_SECTIONS` (`git-servers`, `Git servers`, `GitIcon`). The page reads the list when it
opens and after each change of its own; a check's late answer is dropped. The design doc
holds every line of the page.

### D8. Tests

- Unit (`tests/test_git_servers.py`, `tests/test_cli_git_server.py`): the same-host rule (a
  refusal before the token is read, by command and by `add`), the folder (gone with the last,
  kept with another), `hint` for every profile of `tests/fake_git_api.py` with no credential
  header sent, the page words and fields of each refusal.
- Unit (`tests/test_server_git_servers.py`, new): each route's answers and refusals with
  `tests/fake_git_api.py`, the canary token in no answer, no 422 that repeats it, the list as
  `lado git-server list` prints it, no lado.db made by the listing.
- `tests/fake_git_api.py` gains profiles that answer 401 without a credential and the user
  with the canary token (the real servers' behaviour); its own test grows with them.
- Vitest (`web/src/GitServers.test.tsx`): the form's states from fake API answers (hint and
  link, choice, refusals under fields, token emptied).
- UI e2e (`tests/ui/test_git_servers_section.py`, marker `ui`): a real `lado server` with
  `tests/fake_git_api.py` servers in process: add gitlab.com, add a server of the human's
  own, a silent server with the kind chosen, a refused token, remove; the list compared with
  `lado git-server list` on the same `LADO_HOME`; the canary token in no API answer, not in
  the DOM after the save, not in `server.log`. gitlab.com is reached with no network through
  a local proxy in the test (`HTTPS_PROXY`, honoured by `urllib`'s default opener) that
  answers CONNECT to `gitlab.com:443` with TLS from a certificate of a test CA (made by
  `fake_git_api.make_certificate`'s way, trusted through `SSL_CERT_FILE` of the server's
  process), `NO_PROXY=127.0.0.1,localhost`. `tests/ui/test_settings_pages.py` adds the section.
- No integration test: nothing new crosses processes besides the HTTP API, which the UI test
  and the server's unit tests cover; agents' use of a saved server is the previous change's.
