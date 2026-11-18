# Plan: Git servers (LAD-162)

## State
Phase: steps · Epic run: epic/epic-git-servers · Branch: base (main), decided at intake (#7068 q2)
In work: none · Next: S5b (waits at step_ok) · Open checks: the human's check on the company GitLab, on the release candidate that carries S8
Standing rules of the human:
- One tracker task at a time, created when its step is reached, linked `derived` to LAD-162; findings and leftovers of a step go into the next step (2026-11-15, #7064).
- Explain to the human in plain words, technical details after.
- The statement's decisions (brief.md) are not reopened.
Last review: 2026-11-18, after S5, base at b66064e5

## Steps

Steps are numbered in order while none is in the tracker; once a step's task exists,
its number stays (a later split makes S<n>a, S<n>b).

Every step merges into main, so releases between steps carry part of the feature (a list
without "Check", for example); each part works on its own, and the docs describe only what
is built.

The way back, the same for every step that stores data: a rollback (`lado update`'s, or
installing the previous version) puts back the copy of lado.db made before the migration
(`backups/lado.db.schema-<N>`); an older LADO refuses a newer schema, so there is no
"old LADO with the new data". After the rollback the stored entries are gone, files the
step keeps in `LADO_HOME` (tokens, certificates) stay without an entry and are not used;
git for a host that was listed goes the old way. Each such step checks it with an upgrade
and rollback test, as earlier migrations do, and names whether its files are cleaned up.

### S1 — Git servers: the list and https access for agents (walking skeleton)
Status: done (LAD-289, PR #320, merged a76695bc on 2026-11-16, in release 0.48.0). The human ran
the manual check with Claude Code on gitlab.com and on the company GitLab: all OK.
Leftovers: E4 and the empty `git-servers/` folder → S2; E2 → S5; on the company GitLab
https was not told apart from ssh (the human has an ssh key there) → S8's check; no live test
of Claude Code or of Codex with a model through a git server → S8's release candidate.
Check: unit tests per server kind against a fake API: `lado git-server add <address>
--token` finds the kind itself by asking the server's API with the token (GitLab's
`/api/v4/user`, GitHub's `/api/v3/user` or api.github.com) and says "GitLab, signed in as
<name>"; when the server does not answer (unreachable, untrusted certificate, a proxy)
it refuses with the reason in plain words unless `--kind github|gitlab` is given, then
saves with a warning that it was not checked; a plain `http://` address is accepted with
a warning that the token goes unencrypted. An integration test with a local https git
server that requires a token: a server added with `lado git-server add` (and through the
API) is used by an agent process (the
fake agent) and by LADO's own git (`clone`, `gitcache`) to clone and push by https with
no prompt; `git@<host>:<path>` and `ssh://git@<host>[:port]/<path>` addresses of a listed
host go over https; a host not in the list behaves as before; a removed server's host
behaves as before; `~/.gitconfig` and the system config unchanged; git older than the
version that reads `GIT_CONFIG_*` from the environment (2.31) is refused loudly where a
server is listed, and `lado doctor` says so; a real CLI's git uses the entry: Codex's
sandbox runs git with the helper (`codex sandbox -- git ls-remote …` against the local
server), Claude Code by a live test or a manual check in the pull request (the smoke layer
has no model, so no agent runs git there); natively, where `lado` is not on the agent's
PATH, the helper is still found; the upgrade and rollback test of the way back; the
docs describe what was built (docs/cli.md).
Touches: a new module of server kinds (github, gitlab), `agent_env.py`, `runtime.py`,
`providers/` (where a sandbox needs the helper), `cli.py` (`lado git-server add|list|remove`,
a credential helper command), `state.py`, `server/app.py` (API), `doctor.py`, tests, docs/cli.md.
Notes: `lado model-server add|list|remove` and `model_settings.py` are the precedent for
a saved list with a secret, and `model_servers.py` for finding a server's type from its
address (D: the kind is found, `--kind` the fallback, #7092). Each kind is a module that
knows how to recognise its server, check a token, its host tool and its token page, so a
new kind (Bitbucket, Gitea) is one more module. The token lives in LADO's secret store under `LADO_HOME`
(as a model server's key), never in a git config file or an agent's worktree. A github.com
entry is not accepted until S6 (plan decision, P6): github.com keeps today's path through
`gh` until S6 settles which source wins.

### S2 — Settings → Git servers
Status: done (LAD-290, PR #321, merged 16c5e3e3 on 2026-11-16, in release 0.48.0). The human's
agent ran the manual check in a browser on gitlab.com and on the company GitLab: all OK; the
kind hint without a token says "Looks like GitLab" on the company GitLab too. E4 is settled:
one server per host name (#7131). Leftovers → S5.
Check: a UI e2e test adds a gitlab.com and a self-hosted server (address, prefilled for
gitlab.com; token with a "where to get it" link; the kind shown once found, chosen by hand
only when the server did not answer) and removes one; the list matches
`lado git-server list`; docs/design/ui.md and the user's docs describe the screen.
Touches: `web/src/` (Settings), `server/app.py` (the API for the list: add with the kind
found, list, remove; S1 built none, "Only what is used"), `web/openapi.json` and
`src/api.gen.ts`, docs/design/ui.md.
Leftovers of S1 (ledger E4, the human's manual check):
- Two servers on one host name with different https ports (`host` and `host:8443`): the
  `git@host:` and `ssh://git@host/` rewrites of both clash; the analyst asks the human for
  the rule (e.g. refuse or warn the second one, or rewrite ssh forms for neither) and
  applies it in the CLI and the screen alike.
- After the last server is removed, an empty `<LADO_HOME>/git-servers/` folder stays:
  remove it with the last server.

### S3 — The commit author of a server
Status: done (LAD-291, PR #322, merged eb9632eb on 2026-11-16, in release 0.48.0). The human's
agent ran the manual check on gitlab.com: all OK, a commit in an agent's own worktree (the
integrator's archive commit) included. Needs git 2.36 where an author is set (#7165).
Leftovers → S5.
Check: an integration test: an agent's commit to a listed host carries the server's author
(name, email) in both author and committer, otherwise LADO's as today; Settings and
`lado git-server` set and clear it (UI e2e); the way back (above) with its upgrade and
rollback test; docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `state.py`, `cli.py`, `web/src/`, docs.

### S4 — A mockup of the whole Git servers page
Status: done (LAD-292, runs ui-design/lad-292, then ui-design/lad-292-v2 after #7224; the mockup approved at #7234 on 2026-11-16); added at the review after S3, the human's decision #7196, #7198
Why: the page grew piece by piece (S2 the list and Add, S3 ✎ for the author) and the human
finds it not logical (#7194: editing a server changes only the author, a token is replaced
through Add with the same address); S5–S7 put three more things on it.
Check: a run of the flow `ui-design` of the kit design-studio (designer, critic; no code,
no commit): a brief, `mockup.html` checked at three widths, a spec and a critique of the
whole page with every field it will hold — the list and the server's state, Add, replacing
a token, the commit author, "Check" and its answers (S5), the github.com entry from the
GitHub login (S6), the company certificate (S7) — and the human's remarks and the small
things of S2's and S3's manual checks (below); the human approves the mockup. The spec
names any change it needs below the page (the API, a server's address edited in place):
each becomes part of S5's frame or a question for the human.
Touches: nothing in the repository; the run's artifacts (`<run>/mockup.html`, `spec`,
`design-system`, `critique`) are attached to the step's tracker task and to S5's brief.
Notes: one tracker task for the step, as for every step. The page's current code:
`web/src/GitServers.tsx`, `docs/design/ui.md` (Git servers).

### S5 — The page from the mockup and "Check"
Status: done (LAD-293, PR #324, merged b66064e5 on 2026-11-18, in release 0.48.0). Split at
design (#7241): `lado doctor` and the clone hints went to S5b. The human ran the manual check
in a browser on gitlab.com (rejected at #544: a revoked GitLab token named as neither kind, an
address with spaces taken; both fixed, the repeat check passed, #545). Leftovers → S5b.
The check as planned (doctor and clone hints now S5b's):
Check: unit tests per server kind against a fake API: "Check" in Settings and `lado
git-server check` check a saved server again (the same request as `add` in S1) and say
"works, this is <name>" or why not in plain words (wrong token, missing rights, server
unreachable), and a server saved with `--kind` unchecked is checked when it answers; `lado doctor` lists the servers and their
check; a server whose two kinds both refuse the token names the reason without guessing the
kind (S1 ledger E2: a gateway that answers 401 on every path); a failed clone from a listed host names its entry, from an unlisted host suggests
adding it, in the UI too (UI e2e); the Git servers page is rebuilt as S4's approved mockup
and spec say (`ui-design/lad-292-v2/mockup.html` and `spec`: explanations behind ⓘ
`InfoTip`, one panel per server, Replace token on the server, one result at a time; UI e2e
of its scenarios, the human's manual check in a browser), with the github.com row (C1) and
the certificate row (C7) left out until S6 and S7; the spec's C2–C6, C8, C9 built
(#7234); docs describe what was built.
Touches: the server kinds module, `doctor.py`, `clone.py`, `server/`, `web/src/` (Settings,
the clone window), docs.
Leftovers of S3 (ledger of LAD-291, the human's manual check report):
- An automated test of an agent's commit in its own git worktree carrying the server's
  author (checked by hand and by the lead on git 2.39, no test).
- Removing an author asks nothing (removing a server asks first); after Cancel in the
  author form the focus goes to the page, not back to ✎ (the same as Esc in S2) — for the
  mockup.
- The critique of S4's mockup, F1–F6 (consider): "certificate not trusted" says what to do
  now; the github.com ⓘ says how to sign in (with S6); the ⓘ outside the `h3`; ⓘ names by
  the result; the ⓘ hit area not over the field on a phone; the Token tip not over the link.
- F2: a remote with the host in another case or an explicit `:443` gets no author
  (documented); E2: with git older than 2.36 the refusal names only the first server with
  an author; E4: a failed write leaves a hidden temporary file in the agent's folder.
Leftovers of S2 (ledger of LAD-290, the human's manual check report):
- F3: the address check found a kind, then Add gets "does not answer" and says to choose
  a kind the form does not show; with "Check" the form should offer the choice there too.
- E2: an address with a trailing dot (`git.corp.example.`) escapes the one-server-per-host
  rule; normalise the host name.
- E3, E4 (minor, the page reports them): a removal racing a replacement of the same server
  can leave it without a token file; a failed removal of the empty `git-servers/` folder
  reports an error after the server is gone.
- The page: an empty list shows no "No git servers yet" line; after Esc in the removal
  dialog the focus goes to the page, not back to 🗑; an old "Removed …" line stays above a
  new "Saved …"; the `http://` warning is lost among the lines of a server answering as
  neither kind.

### S5b — `lado doctor` and clone hints from the list
Status: planned (split from S5 at its design, #7241)
Check: unit tests: `lado doctor` lists the git servers with their check (the same check as
`lado git-server check`, network failures named, not fatal to the rest of doctor); a failed
clone from a listed host names its server entry and what to do (Check, Replace token), from
an unlisted host suggests adding the server, in the CLI and in the UI's clone window (UI e2e,
no network); the UI's system facts (doctor in the UI) show the same; docs describe what was
built (docs/cli.md, docs/design/ui.md); the human's manual check in a browser.
Touches: `doctor.py`, `clone.py`, `server/clones.py`, `web/src/` (the clone window; the Git
servers page for the leftovers), docs.
Leftovers of S5 (the human's repeat check #545, ledger of LAD-293):
- An open ⓘ tip stays at its old place when the page switches between the phone and the wide
  layout (a phone turned); closing and opening it again helps.
- After Check a panel shows two Replace token buttons.
- BACKLOG.md got an entry for the flaky kilo smoke on macOS that LAD-295 now holds: remove it.
- Ledger E7: docs/cli.md says that a gateway answering OAuth `invalid_token` on every path is
  named GitLab (declined as a defect, a fair docs line).
- Ledger, declined minor: the author's Remove and Undo stay enabled during their request; the
  `✓` prefix also stands before `Works: …`.
Not checked in S5 (residual risk, for S8's live check on the company GitLab): GitLab's
answers to a revoked and an expired token came from the human's report and docs; "`api` on
GitLab gives push over https" only from docs.

### S6 — GitHub from the list: today's login becomes the github.com entry, `gh` takes the entry's token
Status: planned
Check: an integration test of an upgrade: a user with `GH_TOKEN` (an outside variable or a
project's secret) or `gh auth login` on the home volume sees a github.com entry that
"Check" confirms, and agents clone, push and run `gh` as before; a GitHub Enterprise entry
(kind GitHub, own address) gives `gh` its token and host (`GH_ENTERPRISE_TOKEN`,
`GH_HOST`) so an agent can open a pull request there (against a fake API); a project's own
`GH_TOKEN` is handled as the human decides (open question 1); nothing is deleted
(`GH_TOKEN` and gh's login stay), so after a rollback (the way back above) the old path
works — checked by running it after the rollback; the docs say where the GitHub login is now.
The kind hint without a token (S2) on a real GitHub Enterprise was never seen live: check
it when a GHE server is at hand, or name it as not checked.
Touches: the server kinds module (github), `logins.py`, `agent_env.py`, `clone.py`
(`_github_login`), `docker/Dockerfile` (the system helper for github.com), docs.
Notes: decided at intake (D5). The analyst decides whether the entry is stored or derived
from the existing login (one source of truth). The page's github.com row as S4's mockup and
spec place it (§10, C1, #7234), with the critique's F2 (how to sign in).

### S7 — The company certificate
Status: planned
Check: an integration test with the local https server signed by a test CA: without the
certificate "Check" says the server is not trusted and the clone fails with that reason;
with it uploaded, LADO's git, the agents' git and `gh` clone, push and check; the user's and
the system's trust stores unchanged; the way back (above): after a rollback the
certificate file stays unused under `LADO_HOME` and git for that host fails as before the
step, checked by the upgrade and rollback test; docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `state.py`, `server/`, `web/src/`
(Settings: the certificate row as S4's spec §10 places it, C7), docs.

### S8 — GitLab: `glab` in the image, agents open merge requests
Status: planned
Check: a container test: `glab` is in the image at a pinned version and, for an agent whose
repository is on a listed GitLab, is configured from the entry (host, token, certificate)
with no login of its own (`glab auth status` against a fake server); the image grows by at
most 60 MB (past it: ask the human before merging); docs describe what was built (the
GitLab part of docs/install.md). Then the human's check, on the release candidate that
carries S8 (Docker on a Mac, the company GitLab over the company's VPN): Settings → Git
servers → "Check" green; an agent clones, commits with the given author, pushes and opens
a merge request; github.com works as before. The push must be shown to go over https, not
the human's ssh key (S1's manual check could not tell them apart there): the agent runs
`GIT_SSH_COMMAND=false git push …`, or the human's ssh key is set aside for the check. The
release candidate's live tests (each RC, docs/release.md) include an agent with a model
pushing through a listed server, for Claude Code and Codex (S1 had none).
Touches: `docker/Dockerfile`, `scripts/` pins, the server kinds module (gitlab),
`agent_env.py`, `tests/container/`, `tests/live/` (a push through a listed server), docs/install.md.

### S9 — The guide "Connect your own git server"
Status: planned
Check: a new guide file in `docs/` in plain words: where to create a token on GitHub and
GitLab, which rights it needs, what each "Check" failure means and what to do; its links
work (the docs checks pass); the human reads it.
Touches: the new guide file and a link to it from docs/install.md's table of contents
only — a candidate to run alongside S8 if the human asks for two at once.

## Open questions

1. A project's own `GH_TOKEN` secret after S6 (`clone.py` suggests `lado project set
   <project> GH_TOKEN --secret` today): which wins for that project's git and `gh` — the
   project's token or the github.com entry? Recommended: the project's token while it
   exists, with Settings and `lado doctor` naming the project that overrides the entry, so
   nothing that works today stops working. Asked when S6's brief is drafted.

## Later

- Flaky tests met in S5, not the epic's: the kilo smoke on macOS (LAD-295, #7281) and
  `test_send_text_pastes_multiline_text` in CI (LAD-296, #7294); both in the Backlog, derived
  from LAD-293.
- An expired token shown on a closed row before Check (S4's mockup F7): its expiry date or a
  stored last check, a schema change (#7234).

- ssh for a server (an optional "ssh key" field, host key confirmation) — out by the
  statement; the server entry leaves room for it.
- Bitbucket and Gitea as new server kinds — out by the statement; the kinds module is
  meant for them.
- Several accounts on one server — out: LADO is single-user.
- The host's ssh agent (`LADO_SSH_AGENT`): not developed further; whether to remove it is
  decided apart.
- Kit sdlc: a `.lado/sdlc.md` example for GitLab and "merge request" wording — in the
  kit-sdlc repository; its task is created on the human's yes after S8 (D6).
- A company certificate for model servers inside the company — the same file may serve
  them; not asked for now.
