## Context

`lado.git_servers` checks a server once, at `add`: `probe` asks every kind's user API at once
through `model_servers.ask_all` (5 s, no redirect), tells the kind by `Kind.login` and a
refused token by `Kind.refusal`, and `save` writes the row and the token file. An answer
(`model_servers.Answer`) keeps the status, the JSON body, the redirect target, why there was
no answer and whether TLS failed; not the headers. GitLab's 403 `insufficient_scope` on
`/api/v4/user` already refuses a token without `read_api`; no other right is checked, so a
read-only token is saved silently and agents learn it at their first push.

The page (`web/src/GitServers.tsx`) is the first version: one line of facts per server, 🗑
and ✎ on the row, Add that also replaces a token, leads of running text. The approved layout
is the session's `ui-design/lad-292-v2` (mockup and spec, the human's answer to #7234); the
run's `mockup-check-cases.html` draws the cases it lacks, approved by the human's answer to
#7241 (all recommendations: doctor and clone hints out, the certificate's way out in its ⓘ,
the texts of a fine-grained token, a missing scope saved with a warning, Replace token's
save without a check, github.com's refusal, the command's output).

Facts checked on 2026-11-16 in the code: `address()` lowercases the host and drops the
scheme's own port, but keeps a trailing `.`; `author_entries` writes the address as saved,
and git's `hasconfig:remote.*.url:` compares the remote as written (wildmatch, case
sensitive), while git's credential and `url.*` matching of https lowercases the host and
drops a default port, so `https://GitLab.corp.ru:443/…` gets the token and no author;
`author_files` writes a temp file and `os.replace`s it with no cleanup on failure;
`check_author_git` takes one address to clear; `remove_host` removes the row, then the token
folder, then `git-servers/` and fails on the last after the row is gone.

## Goals / Non-Goals

Goals: a saved server checked again from the command and the page, the token's rights among
the findings; the page by the approved layout; the edge cases of the proposal. Non-goals:
the proposal's Out of scope.

## Decisions

### D1. One check in the core, two texts

`git_servers.check(at: Address) -> Check`, used by the command and the API alike. It finds the
saved server (`saved_server`, refusing an unknown address), refuses a missing token file
(`has_token`) before any request, reads the token, and asks every kind at once with it
(`_ask_kinds`, as `probe`), so "another kind" can be told. The answers are judged by the saved
kind first:

| Saved kind's answer | Outcome |
|---|---|
| a login | `ok`, then the rights (D3); `scopes_missing` when they lack one |
| its refusal | `token_refused` |
| a redirect (any kind's `location`) | `redirect` |
| no HTTP answer, TLS failed on a certificate | `cert_untrusted` |
| no HTTP answer otherwise | `no_answer` (with `_silent`'s reason) |
| another kind's login | `other_kind` |
| anything else | `unrecognised` |

`Check` is a frozen dataclass: `outcome`, `kind`, `login`, `missing_scopes: tuple[str, ...]`,
`rights_checked: bool`, `was_checked: bool` (the row had a login before), `text` and `hint`
in the command's words, `page` in the page's words (the texts of the specs). The page's
buttons and ⓘ come from `outcome`; its sentence from `page`, so the texts live in one place,
as `Refused.page` does today. Rejected: the page composing its own sentences from the fields
(two copies of each text).

### D2. An answer keeps its headers

`model_servers.Answer` gets `headers: Mapping[str, str]` (names lowercased; empty when there
was no HTTP answer). `ask_all` fills it from the response. Nothing else reads it; model
servers are unchanged.

### D3. The rights of a token, per kind

`Kind` gets `needs: tuple[str, ...]` and `rights(answer, ask) -> Rights | None`, `Rights`
being the scopes the server told; None when it told none. `ask` is a callable that sends one
more request with the token (same timeout, no redirect).

- GitHub: from `X-OAuth-Scopes` of the user answer. Absent header (a fine-grained token) →
  None. Present and empty → no scopes. Needs `repo`.
- GitLab: one request to `<root>/api/v4/personal_access_tokens/self` after a login; 200 with
  a `scopes` list → those; any other answer (404 on a GitLab before 15.5, 401, no answer) →
  None. Needs `read_repository` and `write_repository`; `api` counts as both. The developer
  checks the `api` rule in GitLab's docs on personal access token scopes; if `api` does not
  grant Git-over-HTTP push, `api` counts for nothing and the spec's scenario stays as written.

`missing = needs - told`, in `needs`' order. The command's and the page's text for missing
`write_repository` (or `repo`) alone: "agents can clone but not push"; with the read right
missing too: "agents can neither clone nor push". GitHub's `repo` is one scope for both, so a
GitHub token without it gets "neither".

### D4. Add reads the rights and warns

`probe` returns `Checked` with `missing_scopes` and `rights_checked`, read as in D3 for the
kind it found (not with `--kind` on a server that does not answer: no rights then). `add`
saves as before and the command prints the warning on stderr with the hint `replace it with a
token with the <scopes>: lado git-server add <address> --token`; exit 0. The API's
`GitServerSaved` gets `warning: str | null` (the page's text) and `missing_scopes:
list[str]`. A token without `read_api` stays refused (GitLab's 403 on the user API, as today).

### D5. A passing check saves its login

On `ok` (rights missing is not `ok`), `check` writes the login it saw with
`state.save_git_server` under the lock (D9), the server's id, address, kind, token and author
unchanged, when the server is still there; a server removed meanwhile is not written back.
`was_checked` false gives the page `Works: <Kind>, signed in as <login>.` No other outcome
writes anything (no schema change: the results are not kept).

### D6. `lado git-server check <address>`

A subcommand with one required address (no "check all": `lado doctor`'s task). stdout: the
`ok` line; stderr `lado: <text>` and the hint for any other outcome. Exit 0 / 1 / 2 as the
spec says. The address goes through `address()` and `saved_server`, so `gitlab.corp.ru.` and
`GitLab.corp.ru` find `https://gitlab.corp.ru`.

### D7. The API route

`POST /api/git-servers/{host}/check` (guard `changes`: it may write the login), `{host}` the
server's key as in the author routes (`ghe.example.com:8443`, `[::1]:8080`); 200 with
`GitServerCheck {outcome, kind, login, missing_scopes, rights_checked, was_checked, message,
hint}` (`message` is `Check.page`) for every outcome of D1; 404 `EntryRefused` for no such
server; 422 `EntryRefused` with `field: null` for a missing token. Registered before
`DELETE /api/git-servers/{host:path}` (a POST, so no clash). It reads the token file and
never puts the token in an answer or a log line.

### D8. A trailing dot, a letter case, a default port

`address()` drops trailing dots of the host name (`gitlab.corp.ru.` → `gitlab.corp.ru`); a
host of dots alone is "the address names no host". So "one server per host" and every lookup
see one host.

`author_entries`' https/http globs write each ASCII letter of the host as `[xX]` and add, for
an address without a port, the same globs with the scheme's port (`:443`, `:80`); four
https/http globs instead of two. The ssh globs stay as written: git rewrites `git@host:` to
https only for the host as written (`url.*.insteadOf` is a literal prefix), so an upper-case
ssh host gets neither token nor author, and the two stay in step. The near-miss tests of the
first author change are kept and extended to the new globs.

### D9. One lock for saving and removing

`git_servers._locked()`: an exclusive `fcntl.flock` on `<LADO_HOME>/git-servers.lock`, waited
for at most 10 s (non-blocking tries every 50 ms), then refused as `another change of the git
servers is running; try again`. `save` holds it from reading the saved server of the host to
writing the row and the token file; `remove_host` from reading the row to removing the
folder; D5's write of the login too. The network check of `add` runs outside it, so no lock
is held for 5 s. The lock file stays (as `update.lock` does). LADO refuses native Windows, so
`fcntl` is there.

### D10. A removal whose folder stays

`remove_host` removes the row first, as today; then the token folder and an empty
`git-servers/` are removed best effort: an `OSError` becomes a warning `could not remove
<path>: <why>` (the command's stderr, the API's `warning` in its answer, the page's result
line `Removed <address>.` unchanged with the warning under it), and the exit is 0. A token
folder left so holds a token no row names, so no git reaches it; `lado doctor` reporting
such folders goes with doctor's task.

### D11. The old-git refusal names every server with an author

`check_author_git(env, clear: Sequence[str] = ())` names `lado git-server author <address>
--clear` for each address, joined with `, `; the launch passes every server with an author.

### D12. An author file's write leaves no temp file

`author_files` writes each file to a temp name in the same folder and `os.replace`s it; a
`try/finally` unlinks the temp name if it still exists. The error itself propagates as today.

### D13. A token refused by every kind

`probe` without `--kind`: when every kind's `refusal` matches and none gives a login, the
refusal is `<root> refuses the token on GitHub's and GitLab's API alike` with the hint `check
that the token was copied whole; a sign-in gateway in front of the server refuses any token
too`, field Token; the page's text `The server refused this token on both GitHub's and
GitLab's API: copy it whole, or ask whether a sign-in gateway stands in front of it.` With
`--kind`, the refusal names that kind as today. On the page this case rarely shows: such a
server makes the address check show the kind choice, and the refusal then names the kind
chosen.

### D14. Add's lost server offers the kind

`Refused` gets `choose_kind: bool`; `probe`'s refusal for a server that gives no HTTP answer
to any kind sets it; `EntryRefused` carries it to the page. The page then shows the "stopped
answering" state with the Kind segments and `Try again`, the token kept.

### D15. Replace token reuses Add's API

The Replace token form posts `{address: <saved address>, token}` to `POST /api/git-servers`;
a refusal with `choose_kind` makes the form say `⚠ No answer in 5 seconds: save it without a
check, as <Kind>.` with `Save without a check`, which posts again with `kind: <saved kind>`.
A server that now answers as another kind is refused as with `--kind` today. The Add form no
longer replaces: an address already saved shows `Already saved.` and `Replace its token`.

### D16. The page's structure and state

`GitServers.tsx` keeps one component per part: `GitServersPage` (data, the one result, focus
targets), `GitRow` (head and panel), `SignIn` (Check, Replace token and their results),
`GitAuthor` (form, Remove with Undo), `RemoveGitServer` (the foot's question), `AddGitServer`.
The one result line is page state `{server, place, kind, text, actions}`; any action sets or
clears it; opening a panel does not. A failed check's line 2 (`✕ check failed: …`) is page
state keyed by server, gone on reload. Undo keeps the removed name and email in that state
and re-sends `PUT /api/git-servers/{host}/author`: no API change. Focus targets are refs restored after
the next render, with `useScrollAnchor` as today.

### D17. The info tips

`InfoTip` gets `place?: "below" | "above"` (default below); Token's tip opens above so the
token page link under the field stays visible (critic F6). Headings get a wrapper `div.mx-h`
holding the `h3` and the tip beside it, not in it (F3). Tips inside a result line are named
by their outcome: `About the missing scope`, `About no answer`, `About the certificate`,
`About the other user` (F4). On a phone (≤ 600 px) `.field-head` is at least 44 px high, so
the tip's 44 × 44 hit area ends above the field (F5).

### D18. Texts that differ from the approved spec, with the reason

| The approved spec | Built | Reason |
|---|---|---|
| github.com: `…: see github.com below.` | `github.com uses the GitHub CLI's login: it is not added here.` | no github.com block is built (#7241 q6) |
| certificate line: no button now | `Check again`, and the ⓘ says to ask the IT department to make LADO's computer trust it | the line needs a way out now (critic F1, #7241 q2) |
| `⚠ No answer in 5 seconds.` for every no answer | the same for a timeout; `⚠ No answer: <why>.` (the name is not found, the connection is refused) otherwise | the 5-seconds text would be false for those |
| no line for a fine-grained token | `Works: signed in as <login>; the token's rights are not checked.` | GitHub does not tell its rights (#7241 q3) |
| only `write_repository` missing | `The token lacks <scopes>.`; the ⓘ "clone but not push" or "neither clone nor push" | a token may lack the read right too; GitHub's `repo` is both |
| no "neither kind" outcome | `It answers as neither GitHub nor GitLab.` | a check can meet it (a proxy page in front of a server) |
| Replace token, no answer: not drawn | `⚠ No answer in 5 seconds: save it without a check, as <Kind>.` + `Save without a check` | the kind is known (#7241 q5) |
| Add, a scope missing: not drawn | saved, `⚠ The token lacks <scope>: agents can clone but not push.` + `Replace token` | a read-only token stays possible (#7241 q4) |
| a token refused on both APIs: not drawn | `The server refused this token on both GitHub's and GitLab's API: copy it whole, or ask whether a sign-in gateway stands in front of it.` | naming one kind would guess (D13) |
| the panel's certificate row, the github.com block | not built | later tasks of the same work |

## Risks / Trade-offs

- GitLab's `api` scope as covering repository access (D3) is checked against the docs, not a
  live server; the fake API pins the behaviour chosen.
- A check sends the token to the saved address again: the same address and rules as `add`, no
  redirect followed.
- The lock's 10 s wait can refuse a save during a slow removal; both are local and fast.

## Migration Plan

None: no schema change, no new file but `git-servers.lock`. A rollback to the previous 0.48.0
build leaves the lock file unused.
