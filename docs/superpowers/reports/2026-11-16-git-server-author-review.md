# LAD-291 git-server-author: review report

Pull request #322 `feature/lad-291-git-server-author` → `main`. Scale: full. Head reviewed:
`f6db0072`. A saved git server gets an optional commit author (name and email), kept in its
row of lado.db and set or cleared with `lado git-server author` and the ✎ on its row in
Settings → Git servers. An agent whose repository's remote is on a listed server's address
commits with that author as author and committer, through `includeIf "hasconfig:remote.*.url:…"`
files under the agent's folder, passed in the process environment (`GIT_CONFIG_*`); global and
system git config are never touched. Needs git 2.36; an older git is refused loudly.

## Rounds

1. Local, a full pass over `origin/main..f6db0072`, all lenses, the spec and the architecture
   against AGENTS.md. Found F1, F2, F3 (minor). Author patterns checked on real git 2.39:
   https with and without a user, `git@host:` with and without folders, `ssh://` with a
   port, IPv6.
2. External 1, Claude Code GitHub Action (2026-11-16): six notes E1–E6, no blocker or
   important. It read `git_servers.py`, `runtime.py`, `state.py` (changed parts only), not
   `cli.py`, `server/*`, `web/*`, the tests, docs or openspec. E6 merged with F3.

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the manual check's `cp ~/.gitconfig …` fails without `~/.gitconfig`, into a fixed path under `/tmp` | declined: the failure shows at once and does not change the result |
| F2 | minor | local: a remote host in another case or with an explicit `:443` does not match the author's patterns, though LADO gives it the token | declined: documented in `docs/cli.md` |
| F3 | minor | local and external: the author files are written again 2–3 times per launch | declined: atomic, cheap writes |
| E1 | — | external: the author is set against LADO's git, the launch checks the agents' git | refuted: the spec asks for exactly that; the launch's refusal names `--clear` |
| E2 | minor | external: with an old git and several authored servers, the refusal names only the first | declined: rare; needs a new test; no effect on the result |
| E3 | — | external: stale author files stay after `--clear` until the stop | refuted: no include entry points at them; the stop removes the folder (integration test) |
| E4 | minor | external: a failed write leaves a hidden temp file | declined: cosmetic, inside the agent's folder removed at the stop |
| E5 | — | external: an address with a trailing slash makes `//**` | refuted: `address()` drops the trailing slash |

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 3 confirmed (minor), 0 refuted;
external 2 confirmed (minor), 3 refuted, 1 merged; findings in code changed by the
developer's cleanup: 0.

## Checks

- On `f6db0072`: `make lint` clean; unit tests of git servers, CLI, runtime, API and state
  388 passed; integration `test_git_server_author.py` 1 passed; `openspec validate
  git-server-author --strict` valid, `--specs` 87 passed.
- The developer's numbers: 5784 unit passed, UI 18 passed.
- CI of PR #322 on `f6db0072`: every cell passed, `ci-ok` included (smoke on Linux and macOS
  for four providers).

## Residual risk

- The change touches `src/lado/runtime.py` and `tests/smoke/`: live tests were not run.
- The CI log does not show whether Codex's real sandbox ran in the Linux smoke; on macOS it
  did.
- git older than 2.36 was checked only with a faked `git --version`.
- The human's manual check from the pull request's description had not been run at review.
