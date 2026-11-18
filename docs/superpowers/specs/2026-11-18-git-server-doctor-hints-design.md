# lado doctor checks git servers, and a failed clone names its server: design

Task: LAD-297. Change: `openspec/changes/git-server-doctor-hints/` (proposal, deltas of
`doctor`, `session-clone` and `git-servers-page`, `design.md` with decisions D1–D12).
Mockup: the run's `mockup-git-server-hints.html`, sections 2, 3 and 4 variant A (approved
with #7332; section 1, the System panel, declined).

## What the human sees

### lado doctor

```
$ lado doctor
[ok  ] LADO: 0.48.0, the latest version
...
[ok  ] git: git version 2.47.1
[ok  ] git author: user.name and user.email set
[ok  ] git server https://gitlab.corp.ru: Works: GitLab, signed in as ann, may clone and push.
[warn] git server https://ghe.corp.ru: GitHub refused the token: it expired or was revoked
       replace it: lado git-server add https://ghe.corp.ru --token
[warn] git server https://git.lab.corp.ru: git.lab.corp.ru does not answer: it did not answer in 5 s
       check that this computer reaches it: the company VPN or proxy; with LADO in Docker, its container
[ok  ] Workspace: ...
```

- No server saved: no `git server` line. lado.db at another schema: `[info] git servers: not
  checked: lado.db is not at this LADO's schema (see lado.db)`.
- Never `FAIL`; the exit status is that of the other checks. All servers are asked at once,
  together with the model servers: about 10 s at most.
- Doctor writes nothing: a server saved without a check that works stays `not checked` in
  `lado git-server list` (Check in Settings or `lado git-server check` saves the login).

### A failed clone or listing in the command

```
$ lado start https://gitlab.corp.ru/team/app.git
lado: cannot read https://gitlab.corp.ru/team/app.git: gitlab.corp.ru refused the token of the git server https://gitlab.corp.ru (fatal: Authentication failed for 'https://gitlab.corp.ru/team/app.git/')
  Check the git server; if its token expired or was revoked, replace it (lado git-server add https://gitlab.corp.ru --token): lado git-server check https://gitlab.corp.ru

$ lado start https://git.acme.io/team/app.git
lado: cannot read https://git.acme.io/team/app.git: git.acme.io asks for a login (fatal: could not read Username for 'https://git.acme.io': terminal prompts disabled)
  Add it as a git server with a token: lado git-server add https://git.acme.io --token
```

| URL's host | git says | Reason | Hint |
|---|---|---|---|
| saved server | `Authentication failed` | `<host> refused the token of the git server <root>` | check (below) |
| saved server | `returned error: 403` | `<host> refused access with the token of the git server <root>` | check |
| saved server | `Repository not found` / `… not found` | `no repository there, or the token of the git server <root> cannot read it` | check |
| unsaved http(s), not github.com | login asked | `<host> asks for a login` | add |
| unsaved http(s), not github.com | `returned error: 403` | `<host> refused access` | add |
| unsaved, not github.com | not found | as today | none |
| github.com | login asked, not found | as today | as today |
| github.com | `returned error: 403` | `github.com refused access` | `gh auth status` |
| any | unreachable, ssh, no branch, other | as today | as today |

Check hint: `Check the git server; if its token expired or was revoked, replace it (lado
git-server add <root> --token):` `lado git-server check <root>`. Add hint: `Add it as a git
server with a token:` `lado git-server add <root> --token`. A kit's or marketplace's git
failure (`lado kits add …`) shows the same, on one line.

### The UI

- **New session → Clone from URL**, and a project's **Add repository**: the note under the
  URL (a failed listing) or after a failed clone shows the page sentence and a link button:
  - saved server: `Check this git server; if its token expired or was revoked, replace it
    there.` `Check gitlab.corp.ru ↗`;
  - unsaved host: `Add git.acme.io as a git server with a token: LADO and its agents then
    sign in to it.` `Add git server ↗`.

  The link opens Settings → Git servers in a new tab; the window keeps its fields. No
  command to copy in these two cases; every other failure is shown as today.
- **Settings → Git servers** opened by `?check=<host>`: that server's panel open, `Checking…`,
  then the check's line. By `?add=<address>`: the add form with the address, its kind's line,
  the focus in Token. The query leaves the address bar.
- **One Replace token**: a line about a refused or short token has no button; Sign-in's
  `Replace token` is blue (main) while it shows. `Works: …` has no `✓`.
- **The ⓘ tip** stays by its button when the page switches between phone and wide.
- **Remove** (author) and **Undo** are off while they ask.

## The root cause and the options

The clone's texts predate git servers and know only github.com and the machine's own login
(`clone._reason`); doctor was left out of the previous change by the human's split (#7241).
The options and why each was taken are in `design.md`: D1 (one check with `save_login`, over
calling it as is, which would write lado.db, and over a read-only copy, a second source), D3
(the server git took the token of, by `server_for`), D6 (the core decides the way out and
the page shows it, over the page guessing it from the kind).

## Tests per requirement

| Requirement | Layer | Tests |
|---|---|---|
| doctor: lado doctor checks each saved git server | unit | `tests/test_doctor.py`: against `tests/fake_git_api.py`, a working and a refused server (lines, levels, hint), none saved (no line), lado.db at an older schema (`info`, no request) |
| doctor: A git server's failure never fails lado doctor | unit | a server that does not answer (a closed port / the fake's delay with `TIMEOUT` patched) beside one that works; a missing token file (no request); a saved address the address rule refuses (row written by hand); `main()`'s exit status unchanged; servers asked at once (two delayed servers end in about one delay) |
| doctor: check writes nothing | unit | doctor on a server saved with `--kind` that works: `state.git_servers()` keeps `login` None; `git_servers.check` with the default still saves it |
| session-clone: login/access table (`access_denied`) | unit | `tests/test_clone.py`: `kind_of` of git's 403 line; github.com 403 reason and `gh auth status` |
| session-clone: A saved git server's access failure names the server | unit + integration | unit: `failure()` with saved servers in a temp `LADO_HOME` for `login_needed`, `access_denied`, `not_found`, and the ssh form; integration `tests/integration/test_git_server_access.py`: real git against `tests/fake_git_server.py`, a saved server with a wrong token → `list_branches` fails with the server's reason and hint (git's real words) |
| session-clone: An unsaved host … offers to add it | unit + integration | unit: unsaved https login, 403, not found (no hint), unreachable (no hint), a host saved under `https` asked by `http` (no hint), github.com unchanged, a kit's `explain` carries the add hint; integration: the fake server with no saved entry → the add hint |
| session-clone: The New session window clones from a URL / The window's note opens Settings | unit (API) + vitest + UI e2e | `tests/test_server_clones.py`: `CloneRefused.git_server` for both ways, null otherwise, in a job's error too; vitest `Launch.test.tsx`, `ProjectRepos.test.tsx`: the note's sentence, the link's text, `href` and `target`, no Copy; UI e2e `tests/ui/test_launch.py`: the listing of a URL on `tests/fake_git_server.py` (no network) with a saved wrong token and with no saved server shows each note, and the link opens a tab on the settings page with the server's check running |
| git-servers-page: Check on the panel (lines, no ✓, expired token) | vitest | `GitServers.test.tsx`: the `token_refused` line has no button, Sign-in's Replace token has class `primary`; a `Works:` line has no `✓` class |
| git-servers-page: A refused or short token leaves one Replace token | vitest | after `scopes_missing`, after Add/Replace with a missing right: exactly one `Replace the token of <address>` |
| git-servers-page: Replace token replaces a saved server's token | vitest | the existing tests, the missing-right case updated |
| git-servers-page: The page opens a server from its address | vitest + UI e2e | vitest: `?check=` opens and checks, `?add=` fills and focuses Token, unknown host opens nothing, the query is dropped; the UI e2e above |
| git-servers-page: An open info tip stays by its button when the layout changes | UI e2e | `tests/ui/test_git_servers_section.py`: open the Token tip at 390 px, resize to 900 px, the tip's box touches its button's |
| git-servers-page: Remove and Undo off while they ask | vitest | a pending removal: Remove disabled, a second click sends no request; the same for Undo |

Regression run: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_git_server_access.py`, `uv run pytest -m ui
tests/ui/test_launch.py tests/ui/test_git_servers_section.py`, `make web`, `openspec validate
git-server-doctor-hints --strict` and the trial archive of `.lado/sdlc.md`.

## Docs

- `docs/cli.md`: doctor's `git server` lines (after the `Model servers` and `Default models`
  paragraphs); the clone's texts (the clone section's table of kinds); in `lado git-server
  add`'s refusals one line: a gateway that answers OAuth's `invalid_token` on every path is
  taken for GitLab.
- `docs/design/ui.md`: New session window (the git server note), Projects (Add repository's
  note), Git servers (`?check=`, `?add=`, one Replace token, `Works` without ✓, Remove/Undo
  busy), the info tip after a layout switch.
- `docs/design/modules.md`: `doctor.py` (git server lines), `clone.py` (`access_denied`,
  `ServerWay`).
- CHANGELOG.md, `## 0.48.0 (unreleased)`: the git servers entry gains doctor and the clone
  hints.
- BACKLOG.md: the entry "Flaky: the Kilo smoke on macOS times out on `kilo models`" removed
  (task LAD-295).

## Manual check (for the pull request)

Preparation, in a fresh temporary folder (never the human's checkout):

1. `env | grep -E '^(GIT_|GH_|LADO_)'`; `unset` each variable left from an earlier check.
2. `git config --global --list --show-origin > "$TMPDIR/gitconfig-before.txt" 2>&1`.
3. `git clone https://github.com/ladohq/lado.git && cd lado && git checkout <branch>`;
   `uv sync`; `make web`.
4. `export LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-297`.

Steps:

5. `uv run lado doctor`: no `git server` line.
6. **[человек]** `uv run lado git-server add <your GitLab> --token` with a working token;
   then `uv run lado doctor`: `[ok  ] git server <address>: Works: …`.
7. `uv run lado git-server add https://127.0.0.1:9 --token --kind gitlab` with any text as
   token; `uv run lado doctor`: its line is `[warn]` with `does not answer`, the GitLab line
   follows, the exit status is 0 unless another check fails.
8. **[человек]** Revoke the token of step 6 on the server. `uv run lado doctor`: `[warn] …
   refused the token: it expired or was revoked` with the replace hint.
9. **[человек]** `uv run lado start <a private repository of that server>`: the failure names
   the server and gives `lado git-server check <address>`.
10. `uv run lado start https://<a GitLab host you have not saved>/<private group>/<repo>.git`
    (e.g. a private project on gitlab.com when gitlab.com is not saved): `asks for a login`
    with `lado git-server add https://<host> --token`.
11. `uv run lado start https://no-such-host.invalid/a/b.git`: `cannot be reached`, no
    server hint.
12. `uv run lado ui`; New session → Clone from URL with the URL of step 9: the note `Check
    <host> ↗`; press it: a new tab on Settings → Git servers, the server's panel open,
    its check saying the token is refused; the New session window keeps the URL.
13. Same with the URL of step 10: `Add git server ↗` opens the add form with the address,
    the focus in Token.
14. In the panel of step 12: one `Replace token`, blue; replace the token **[человек]**;
    Check: `Works: …` with no ✓.
15. Narrow the window to a phone's width (or turn the phone), open the ⓘ of Token, widen it
    past 900 px: the tip stays by its ⓘ.
16. Set a commit author, press Remove: Remove is off until it is done; Undo likewise.
17. `uv run lado git-server remove …` for each server added; `uv run lado stop --all`;
    `git config --global --list --show-origin > "$TMPDIR/gitconfig-after.txt" 2>&1` and
    `diff` both files: no difference.

A short repeat after fixes names the steps by these numbers; check them against the pull
request's text before posting.
