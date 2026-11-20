# Checking a saved git server, and Settings → Git servers by the approved layout: design

Task: LAD-293. Change: `openspec/changes/git-server-check/` (proposal, deltas of `git-servers`
and `git-servers-page`, `design.md` with decisions D1–D18). Mockups: the session's
`ui-design/lad-292-v2/mockup.html` with its spec (approved, #7234) and the run's
`mockup-check-cases.html` (frames A1, B, C, D, E; approved with #7241; frame A2 not taken).

## What the human sees

### The command

```
$ lado git-server check gitlab.corp.ru
Works: GitLab, signed in as ivan.petrov, may clone and push.

$ lado git-server check ghe.corp.ru
Works: GitHub, signed in as ivan; the token's rights are not checked.

$ lado git-server check gitlab.corp.ru
lado: GitLab refused the token: it expired or was revoked
  replace it: lado git-server add https://gitlab.corp.ru --token
$ echo $?
1
```

The other failures, each `lado: <line>` with a hint, exit 1:

| Outcome | Line | Hint |
|---|---|---|
| a right missing | `the token lacks write_repository: agents can clone but not push` (`…neither clone nor push` without the read right) | `replace it with a token with the scopes read_repository, write_repository, read_api: lado git-server add <address> --token` |
| no answer | `gitlab.corp.ru does not answer: it did not answer in 5 seconds` (or the name is not found, the connection is refused) | `check that this computer reaches it: the company VPN or proxy; with LADO in Docker, its container` |
| certificate | `the certificate of https://gitlab.corp.ru is not trusted` | `ask your IT department to make this computer trust it (with LADO in Docker, its container), then check again` |
| redirect | `it redirects to https://sso.corp.ru/login: add that address instead` | — |
| another kind | `it answers as GitLab, not GitHub: remove it and add it again` | `lado git-server remove <address>`, then `lado git-server add <address> --token` |
| neither kind | `it answers as neither GitHub nor GitLab` | — |
| no such server | `https://git.lan is no saved git server` | `see them: lado git-server list` |
| token file missing | `the token file of https://gitlab.corp.ru is missing` | `replace it: lado git-server add https://gitlab.corp.ru --token` |

A bad address exits 2. A passing check of a server saved with `--kind` saves its login, so
`lado git-server list` no longer says `not checked` for it.

`lado git-server add` with a token that lacks a right still saves it and warns:

```
$ lado git-server add gitlab.corp.ru --token
GitLab, signed in as ivan.petrov
Saved git server https://gitlab.corp.ru.
warning: the token lacks write_repository: agents can clone but not push
  replace it with a token with the scopes read_repository, write_repository, read_api: lado git-server add https://gitlab.corp.ru --token
```

### Settings → Git servers

As the approved mockup (§1–§8 of `ui-design/lad-292-v2`), without the github.com block and
the company certificate row, and with the cases of `mockup-check-cases.html`:

- **The page.** `Servers <n>` with an ⓘ beside it (agents clone and push with the token;
  running agents get a change after they restart), the rows, `+ Add server`. No running
  text: explanations are behind ⓘ.
- **A closed row.** The address, the kind, `plain http`; line 2 `signed in as <login>` /
  `⚠ not checked` / `⚠ token missing` / after a failed Check of this visit `✕ check failed:
  <reason>` or `⚠ check: no answer`; line 3 `commits as <name> <<email>>`.
- **An open row** is a panel: Sign-in (value, `Check`, `Replace token`), Commit author
  (value, `Set author` or `Edit` and `Remove`), the foot `Remove server`.
- **Check** shows one line under Sign-in (the table of the page's spec), with its way out at
  its end. The certificate line: `The server's certificate is not trusted.` ⓘ `About the
  certificate` (ask the IT department to make LADO's computer trust it, with LADO in Docker
  its container, then check again) and `Check again` (frame A1).
- **Replace token** opens a form under Sign-in; done `✓ Token replaced: signed in as
  <login>.`; another user adds `⚠ Before, it was <old>.` ⓘ; a token without the push right
  `⚠ The token lacks write_repository: agents can clone but not push.` [Replace token]
  (frame C); no answer `⚠ No answer in 5 seconds: save it without a check, as GitLab.` [Save
  without a check] [Cancel] (frame D).
- **Commit author**: `✓ Author saved.`; `Remove` at once → `✓ Author removed.` [Undo].
- **Remove server**: the foot asks `Remove <address>?` / `Its token and commit author go too.
  This cannot be undone.`; done `Removed <address>.`
- **Add server**: `GitLab answers.`; `⚠ Plain http://: the token travels unencrypted.` ⓘ;
  `Already saved.` [Replace its token]; github.com `github.com uses the GitHub CLI's login: it
  is not added here.` (frame E); no answer → Kind; stopped answering at Add → `⚠ It stopped
  answering when you pressed Add.` [Try again] + Kind; done → the new row open with `✓ Saved:
  GitLab, signed in as <login>.`
- At most one result line on the page; the focus moves by the page spec's table.

## The root cause and the options

Root cause: the token is checked only at `add`, and nothing later asks the server again; the
first version of the page put facts and explanations in running text and had no place for a
server's actions. Options weighed against the coming work of git servers (github.com in the
list, the company certificate, `glab`, `lado doctor`):

- **A (taken): one `check` in the core, used by the command, the API and later doctor**; the
  page's texts in the core beside the command's (`Check.page`, as `Refused.page`). Cost: one
  more route and one more dataclass; the certificate's task adds an outcome's way out, not a
  second check. Doctor's task calls `check` per server.
- **B: the page asks the server through Add's API without a token change.** Rejected: Add
  writes, so a check would rewrite the row and the token file and race removals; no
  "another kind" outcome.
- **C: store the last check's time and outcome.** Rejected by the human's earlier answer
  (results are not stored): a schema change, and a stored "works" goes stale.

Held against the design principles: one source of truth (the outcomes and texts in one
module, the kinds in `git_kinds/`); no silent drops (a missing right is a warning, not a
silent save; a removal's left folder is a warning); neutral core (no agent CLI involved:
works the same for every provider).

## Tests per requirement

| Requirement | Layer | Tests |
|---|---|---|
| git-servers: lado git-server check checks a saved server again | unit | `tests/test_cli_git_server.py`: works → stdout, exit 0; each failure → stderr with hint, exit 1; no such server and token missing send no request (the fake API's `paths()` empty); bad address exit 2 |
| git-servers: A check names each outcome in one line | unit | `tests/test_git_servers.py` against `tests/fake_git_api.py`, per kind: token refused, no answer (timeout; unknown name), certificate (the fake's own CA, untrusted), redirect (no request to the target), another kind, neither kind |
| git-servers: A token's rights are read from the server | unit | `tests/test_git_servers.py` per kind: GitLab scopes full, without `write_repository`, without `read_repository`, `api` alone, token-self 404; GitHub `X-OAuth-Scopes` with `repo`, `read:org`, empty, absent; `tests/test_model_servers.py`: `Answer.headers` |
| git-servers: A passing check saves the login it saw | unit | `test_git_servers.py`: a `--kind` server checked → login saved, list shows it; any other outcome changes nothing (row and token file compared) |
| git-servers: A token without a right … is saved with a warning | unit | `test_git_servers.py`, `test_cli_git_server.py`: saved, warning on stderr, exit 0; `tests/test_server_git_servers.py`: `warning` and `missing_scopes` in the answer |
| git-servers: Saving and removing a server are done one at a time | unit | `test_git_servers.py`: a removal in a thread waits while a save holds the lock; a held lock past 10 s refuses; a replacement racing a removal ends with the row and the token file in step |
| git-servers: A git server's address (modified) | unit | `test_git_servers.py`: `gitlab.corp.ru.` → `https://gitlab.corp.ru`, replaces; `...` names no host |
| git-servers: A server that cannot be checked … (modified) | unit | `test_git_servers.py`: the gateway profile of the fake API (401 JSON on every path) → the refusal names no kind; with `--kind gitlab` it names GitLab |
| git-servers: lado git-server remove … (modified) | unit | `test_git_servers.py`, `test_cli_git_server.py`: a file of the human's in `git-servers/` → removed, warning naming the folder, exit 0 |
| git-servers: Agents commit … as its author (modified) | unit + integration | unit: the new globs against real git (`GitLab.corp.ru`, `:443`, `:80`, the near-miss hosts, the ssh forms as before); integration `tests/integration/test_git_server_author.py`: a session's repository cloned by LADO from the local https server, a worker's commit in its own worktree carries the author; a remote `https://GIT.test:8443/…` too |
| git-servers: A commit author's file … (modified) | unit | `test_git_servers.py`: `os.replace` made to fail → no temp file left, the error raised |
| git-servers: A commit author needs git 2.36 (modified) | unit | `tests/test_runtime_git_servers.py`: two servers with authors, fake git 2.34.1 → both `--clear` commands named |
| git-servers-page: every requirement | unit + vitest + UI | `test_server_git_servers.py`: the check route per outcome (body fields, 404, 422), `choose_kind`, the canary token in no answer and no log line; `web/src/GitServers.test.tsx` and `web/src/InfoTip.test.tsx`: each state, the one result line, the focus table, `place="above"`; UI e2e `tests/ui/test_git_servers_section.py` against the fake API, no network: Add (checking, answered, plain http, already saved → Replace its token, github.com, no answer, stopped answering, token refused, done, missing scope), Check (every outcome, the closed row's line 2), Replace token (done, another user, refused, no answer → save without a check), the author with Undo, Remove server, the focus after each action, one result line, the canary token in the DOM; 1440, 768, 390 with no horizontal scroll and the Token tip leaving the link pressable at 390; screenshots of each frame |

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_git_server_author.py tests/integration/test_git_server_access.py`,
`uv run pytest -m ui tests/ui/test_git_servers_section.py tests/ui/test_settings_pages.py`,
`make web` (stale types), the openspec checks of `.lado/sdlc.md`.

## Docs

- `docs/cli.md`: `lado git-server check` (outputs, exit codes, the login saved), the rights
  read and the warning of `add`, the removal's warning, the trailing dot, the author's https
  forms in any letter case and with the default port.
- `docs/design/ui.md`: Git servers by the new layout (rows, panel, results, focus, ⓘ), the
  route `POST /api/git-servers/{host}/check` and the fields `warning`, `missing_scopes`,
  `choose_kind`; `InfoTip`'s `place`.
- `docs/design/modules.md`: `git_servers.py` (`check`, the lock, the removal), `git_kinds/`
  (`needs`, `rights`), `model_servers.Answer.headers`.
- CHANGELOG.md: the 0.48.0 git servers entry gains Check (the command and the page) and the
  token's rights; no new version (minor already next).

## Manual check (for the pull request)

The agent may run every step but those marked **[человек]**, which need the human's token or
hands; the agent never sees the token.

1. In a fresh clone in a temporary folder, branch `feature/lad-293-git-server-check`:
   `env | grep -E '^(GIT_|GH_|LADO_)'` and `unset` every variable a previous check left;
   `uv sync`; `make web`; `CHECK=$(mktemp -d)`; `export LADO_HOME=$CHECK/home
   LADO_TMUX_SOCKET=lado-check-293`; `git config --global --list --show-origin >
   $CHECK/gitconfig.before 2>&1`.
2. **[человек]** `uv run lado git-server add gitlab.com --token` with a gitlab.com token
   with all three scopes (or the company GitLab's address) → `GitLab, signed in as <you>`.
3. `uv run lado git-server check gitlab.com` → `Works: GitLab, signed in as <you>, may clone
   and push.`, exit 0.
4. **[человек]** make a second token with `read_repository, read_api` only; `uv run lado
   git-server add gitlab.com --token` with it → saved with the warning that it lacks
   `write_repository`; `uv run lado git-server check gitlab.com` → the same, exit 1.
5. `uv run lado ui`, Settings → Git servers, at full width and at 390 px (the browser's
   device mode): the page as the approved mockup's §1; ⓘ beside `Servers` opens and Esc
   closes it; the row opens to its panel.
6. **[человек]** `Check` → the missing-scope line with its ⓘ and `Replace token`; Replace
   token with the full token → `✓ Token replaced: signed in as <you>.`; `Check` → `Works: …`.
7. **[человек]** revoke the second token on gitlab.com, or replace with a wrong one through
   the CLI: `Check` → `GitLab refused the token: it expired or was revoked.` and the closed
   row says `✕ check failed: token refused`; replace it back with the good token.
8. Commit author: `Set author` (`Test Author`, `test-author@example.com`) → `✓ Author
   saved.`; `Remove` → `✓ Author removed.` [Undo]; `Undo` → `✓ Author saved.`, focus on
   `Edit`.
9. `+ Add server`, type `gitlab.com` → `Already saved.` [Replace its token] opens the
   server's Replace token; type `github.com` → `github.com uses the GitHub CLI's login: it is
   not added here.`; type `git.invalid` → `⚠ No answer…` and the Kind choice; Cancel.
10. On a phone width the Token ⓘ leaves the token page link pressable, and pressing an ⓘ
    never focuses its field.
11. `Remove server` → the question, `Remove server` → `Removed https://gitlab.com.`, focus on
    `+ Add server`; `uv run lado git-server list` → none.
12. `git config --global --list --show-origin > $CHECK/gitconfig.after 2>&1; diff
    $CHECK/gitconfig.before $CHECK/gitconfig.after` → no difference.
13. **[человек]** revoke the test tokens on gitlab.com.
