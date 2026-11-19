Task: LAD-304

## Why

LADO signs agents in to the human's own GitHub or GitLab, a company's included, by the
host of the repository's address: a token, a commit author and a certificate per server
(Settings → Git servers, `lado git-server`). What a person who knows little of git servers
needs to get there is spread over docs/install.md ("GitHub and your git servers", a dense
reference paragraph per kind) and docs/cli.md (`lado git-server`, every line of every
command), and neither says, in plain words, what each answer of **Check** means and what to
do about it. LADO is meant for people who are not engineers too, so the path from "I have a
GitHub or GitLab account" to "the agents push there" needs a guide of its own.

Root cause: documentation, and one gap of the page. The behaviour exists and is covered by
the specs `git-servers` and `git-servers-page`, but no guide walks a newcomer through it.
Writing the guide against the code showed the gap: a GitLab token without `api` leaves the
agents' `glab` unable to open merge requests, and `lado git-server check` and `add` say so
(`git-servers`, "A GitLab token without api is said to leave glab without merge requests"),
but the page does not. The page builds its own sentence (`git_servers.Check.page`, and the
`Saved:` and `Token replaced:` lines in `GitServers.tsx` from the login alone), and the
tool's ending, added to the command's line (`Check.text`, `Checked.line`), was not added to
the page's. The human ruled it an unfinished part of the git servers' work and asked for it
in this task, with a test, and for the guide to describe the fixed page.

## What Changes

- A new guide, `docs/git-servers.md` ("Connect your git server"), in English as every
  document of `docs/`, written for a reader who is not an engineer: plain words first, the
  technical details after, or behind a link to docs/install.md and docs/cli.md. Sections:
  1. **What this does**: agents clone and push to your GitHub or GitLab with a key you give
     LADO once (a token); LADO chooses the server by the host of the repository's address.
  2. **Make a token**: where to make it and which rights (scopes) to tick.
     - GitHub (github.com and GitHub Enterprise): a classic token at
       `<address>/settings/tokens` with `repo`, the minimum; `read:org` (pull requests of an
       organization's repository) and `workflow` (pushing `.github/workflows/`) only if the
       user wants them. A fine-grained token works too, but Check cannot see its rights and
       says so ("the token's rights are not checked").
     - GitLab (gitlab.com or a company's): at
       `<address>/-/user_settings/personal_access_tokens` with `api`, which the agents need to
       open merge requests; for clone and push alone, `read_api`, `read_repository` and
       `write_repository` (LADO refuses a token without `read_api`: it asks GitLab's API
       who the token is), and then the page says `glab cannot open merge requests: the token
       lacks api`.
     - An expiry date the user will remember, and that the token is shown once.
  3. **Add the server**: Settings → Git servers → **Add server**, the address as opened in a
     browser, the token, **Add server**; what the form may say while the address is typed
     (the kind it found, plain `http://`, no answer and **Add without a check**, a company
     certificate: see 5). Running agents get the server after they restart.
  4. **Check**: what **Check** does, and a table of every answer it gives, each with its
     text as the page shows it, what it means and what to do (the full list under
     "Check's answers").
  5. **Your company's certificate**: the card "Trust this server?" (who signed the
     certificate, its validity, its SHA-256 fingerprint; compare the fingerprint with your IT
     department), **Trust this server** and **Don't trust**, a certificate that has changed
     (**Trust the new certificate**, **Keep the old one**, and why not to trust a change IT
     did not announce), and a certificate file from IT given in the terminal
     (`lado git-server certificate <address> <file>`, in Docker by stdin; `--certificate` of
     `lado git-server add`), with a link to docs/cli.md for the rest.
  6. **The agents at work**: start a session on a repository whose origin is on the server,
     or **Clone from URL**; `git@…` addresses of a saved server go over https with its
     token; each agent is told which server its repository is on and which tool goes with it
     (`gh` for GitHub's pull requests, `glab` for GitLab's merge requests).
  7. **Commit author (optional)**: the row **Commit author** of a server, the name and email
     on the agents' commits there; without one, the user's own git author. One paragraph,
     with a link to docs/cli.md.
  8. **What LADO does not use**: your own `gh auth login` / `glab auth login`, and a
     `GH_TOKEN` or `GITLAB_TOKEN` from outside (your shell, a project, `secrets/`); only the
     token of Settings → Git servers. The one-time move of an older GitHub login into
     Settings is named with a link to docs/install.md.
  9. **With Docker or without**: the same steps; LADO's image has `gh` and `glab`, without
     Docker the user installs `gh` and `glab` 1.114.0 or newer themselves (link to
     docs/install.md's "Common problems").
  10. **More**: links to docs/install.md ("GitHub and your git servers") and docs/cli.md.
- The page says what `glab` cannot do, in the command's words: for a GitLab token that works
  for git but lacks `api`, Check's `Works:` line, Add server's `✓ Saved:` line and Replace
  token's `✓ Token replaced:` line end with `; glab cannot open merge requests: the token
  lacks api` before their full stop (mockup `mockup-glab-line.html`). The line keeps its ok
  tone, place and buttons: git works, as the command's exit 0 says. Delta of
  `git-servers-page`: a new requirement, and Check's list of lines.
- docs/design/ui.md, Settings → Git servers: the three lines gain that ending.
- docs/install.md: an item for the guide in its contents list, and a link to it at the top
  of "GitHub and your git servers".
- A unit test (`tests/test_git_servers_guide.py`) pins the guide to the code: every relative
  link of the guide resolves (files and docs/install.md's anchors), and each Check answer the
  guide quotes is in the guide and, by its fixed part, in the source it comes from
  (`src/lado/git_servers.py`, `web/src/GitServers.tsx`).
- CHANGELOG.md: one line under `## 0.48.0 (unreleased)`.

## Check's answers

The texts as `main` gives them (`git_servers.check`'s `page` and `page_hint`, shown by
`GitServers.tsx`'s `checkLine`; `<…>` the parts that vary). The guide quotes each one; the
pull request holds the table "text in the guide ↔ place in the code".

| Answer (outcome) | The page's line | Its tip, or what follows |
|---|---|---|
| works, first check (`ok`) | `Works: <GitHub\|GitLab>, signed in as <login>.` | — |
| works (`ok`) | `Works: signed in as <login>, may clone and push.` | — |
| works, GitLab without `api` (`ok`, after this change) | `Works: signed in as <login>, may clone and push; glab cannot open merge requests: the token lacks api.` (`Works: GitLab, signed in as <login>; glab …` on a first check) | — |
| works, rights unknown (`ok`) | `Works: signed in as <login>; the token's rights are not checked.` | — |
| token refused (`token_refused`) | `<GitHub\|GitLab> refused the token: it expired or was revoked.` | **Replace token** |
| a right missing (`scopes_missing`) | `The token lacks <scopes>.` | `Agents can <neither clone nor push\|clone but not push> with it. Make one with the scope <repo\|api>.` |
| GitLab without read_api (`scopes_missing`) | `The token lacks read_api.` | `LADO asks the server's API with it. Make one with the scope api.` |
| no answer (`no_answer`) | `⚠ No answer in <n> seconds.`, `⚠ No answer: the name is not found.`, `⚠ No answer: the connection is refused.`, `⚠ No answer: TLS failed (<why>).` | `Check that LADO's computer reaches the server: the company VPN or proxy; with LADO in Docker, its container.`, **Check again** |
| certificate not trusted (`cert_untrusted`) | `⚠ The server's certificate is not trusted.` and the trust card | `ABOUT_TRUST`; after **Don't trust**: `Not trusted: LADO and agents cannot clone or push here over https.` |
| certificate changed (`cert_changed`) | `⚠ The server's certificate has changed since you trusted it.` and the card with Before and Now | `ABOUT_CHANGED`; after **Keep the old one**: `The saved certificate does not fit the server: LADO and agents cannot clone or push here over https.` |
| certificate for another host (`cert_name`) | `The server's certificate is not issued for <host>: trusting it would not help. Ask the server's administrator.` or `The server's certificate names its host only in the old Common Name field, which LADO refuses: ask the server's administrator to reissue it.` | — |
| certificate expired (`cert_expired`) | `The server's certificate expired on <date>: ask the server's administrator to renew it.` | — |
| sends elsewhere (`redirect`) | `It redirects to <url>: add that address instead.` | — |
| another kind (`other_kind`) | `It answers as <GitLab>, not <GitHub>: remove it and add it again.` | — |
| neither kind (`unrecognised`) | `It answers as neither GitHub nor GitLab.` | — |
| token file missing (refused) | `Its token file is missing.` | **Replace token** |

A closed server row shows a failed check of this visit as its second line (`✕ check
failed: token refused`, `⚠ check: no answer`, …; `FAILED` in `GitServers.tsx`); the guide
names that the row says so, not each label.

## Acceptance criteria

- AC-1: `docs/git-servers.md` walks from start to end: make a token, add the server, Check,
  trust a company's certificate when asked, the agents at work.
- AC-2: the token's rights as What Changes, 2 says: GitHub `repo` (`read:org`, `workflow`
  optional); GitLab `api`, or `read_api`, `read_repository` and `write_repository` without
  merge requests.
- AC-3: every Check answer of "Check's answers" is in the guide with what it means and what
  to do, its text the same as `main`'s code; the pull request holds the table "text in the
  guide ↔ place in the code".
- AC-4: the certificate section covers the trust card, Don't trust, a changed certificate
  and a file from IT.
- AC-5: the guide says what LADO does not use: `gh`/`glab`'s own logins, `GH_TOKEN` and
  `GITLAB_TOKEN` from outside; `git@` addresses go over https.
- AC-6: Docker and without Docker are the same steps; without Docker the user installs `gh`
  and `glab`.
- AC-7: docs/install.md's contents list links to the guide; the guide links to docs/install.md
  and docs/cli.md for details instead of repeating them, and names no plan step or
  `docs/epics/` file.
- AC-8: for a GitLab token without `api`, Check, Add server and Replace token on the page end
  their line with `; glab cannot open merge requests: the token lacks api`, as the delta of
  `git-servers-page` says; a token with `api` and GitHub keep their lines.
- AC-9: the tests of tasks.md, 4 pass with `make lint` and `make test`; the human has
  read the guide and said whether it is clear.

## Scope

- `docs/git-servers.md` (new), docs/install.md (contents list, one link), CHANGELOG.md,
  `tests/test_git_servers_guide.py` (new).
- The page's glab ending: `src/lado/git_servers.py` (`check`'s page line),
  `src/lado/server/models.py` and `git_entries.py` (the add's answer carries the ending),
  `web/src/GitServers.tsx`, `web/openapi.json` and `web/src/api.gen.ts`, docs/design/ui.md,
  their tests.

## Out of scope

- Other code and UI texts: the guide describes what the code does. Any other text that
  should change for the guide to be clear is a new task, asked of the human first (the
  brief's threshold). The glab ending is the one exception, by the human's ruling.
- A louder look for the glab ending (a warning tone, Replace token as the main button):
  not asked for; the human asked for the command's line, and git does work.
- The closed row's second line for it: it says `signed in as <login>`, as for any working
  token; `lado doctor` keeps its warning.
- Translations of the guide: not asked for; every document of `docs/` is English.
- The kits (`kit-sdlc`, `kit-epic`, `kit-builder`): changed after the git servers' work, on
  the human's yes.
- ssh to a server, Bitbucket and Gitea, a certificate for `gh`: not built; the guide says
  in the product's words what is not there (`gh` does not get a company certificate; `git@`
  addresses go over https), without promising them.
- Repeating docs/install.md or docs/cli.md: the guide links to them for every detail
  (commands' flags, files under `LADO_HOME`, `lado doctor`'s lines), so there is one source.

## Impact

- Documentation, and a fix of the page of the unreleased 0.48.0: one optional field in the
  answer of `POST /api/git-servers` (types regenerated), no CLI, MCP or schema change. A fix
  and docs, so patch-level; its CHANGELOG line goes under the open `## 0.48.0 (unreleased)`,
  whose git servers are not released yet.
- Delta spec of `git-servers-page`; archived with its specs.
- Test layers: unit for the check's page line and the add's answer (`tests/test_git_servers.py`,
  `tests/test_server_git_servers.py`) and for the guide (`tests/test_git_servers_guide.py`);
  vitest for the page's three lines (`web/src/GitServers.test.tsx`); one UI e2e test for Add
  and Check with a fake GitLab token without `api` (`tests/ui/test_git_servers_section.py`),
  as the project asks of UI work. Nothing else crosses a process. The guide's clarity is
  checked by the human reading it (tasks.md, section 5).
