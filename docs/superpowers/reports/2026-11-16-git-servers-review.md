# LAD-289 git-servers: review report

Pull request #320 `feature/lad-289-git-servers` → `main`. Scale: full. Head reviewed:
`9edc2df0`. LADO keeps a list of git servers (GitHub, GitLab, self-hosted included) with a
token each; `lado git-server add|list|remove` manages it, the kind is found from the
server's API (`--kind` as a fallback, `http://` with a warning). Every agent process and
LADO's own git get `GIT_CONFIG_*` for the listed hosts: LADO's credential helper, no
password prompt, and the ssh forms of the address rewritten to https; git below 2.31 is
refused loudly where a server is listed.

## Rounds

1. Local, a full pass over `ed9b43c5..e95375ec`, all lenses and the architecture against
   AGENTS.md. Found F1–F3 (minor).
2. External 1, Claude Code GitHub Action (2026-11-15): six notes E1–E6. It read all of
   `src/`, not the tests, docs or openspec. Converged; at `merge_ok` the human sent F1–F3
   back to be fixed.
3. Local, precision, over the delta `e95375ec..9edc2df0` (the usage line, its test, the
   pull request's description): F1–F3 resolved, nothing new.
4. External 2, Claude Code GitHub Action (2026-11-16): "No findings"; it accepted the
   answers to E1, E3, E5 and E6.

External rounds used: 2 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: `add`'s usage put `--token` before the address; the command as shown took the address for the token | fixed in `9edc2df0`: usage `add [-h] address --token [--kind …]`, test `test_the_usage_puts_the_address_before_the_token` |
| F2 | minor | local: the pull request's description said the Linux Codex smoke runs inside the sandbox | fixed in the description: macOS always runs in the sandbox, the Linux cell's path is not visible |
| F3 | minor | local: the manual check put its snapshot in the shared `/tmp`, and its `diff` failed without `~/.gitconfig` | fixed in the description: the snapshot in `$LADO_HOME`, works without `~/.gitconfig` |
| E1 | — | external: `--kind gitlab` refuses a token without `read_api` | refuted: the design's decision, refused as a refused token |
| E2 | — | external: when both kinds refuse, the first of `KINDS` is named | unverifiable: needs a gateway answering 401 on every path; GitLab and GitHub Enterprise answer 404 on the other's API |
| E3 | — | external: a hidden `KeyError` in `dict(found)[chosen]` | refuted: unreachable with two kinds |
| E4 | minor | external: two servers on one host with different ports make the ssh forms ambiguous | declined: https is not affected, the scp form carries no port; the rule is a product question for a later task |
| E5 | — | external: `variables()` overwrites `LADO_GIT_CONFIG_BASE` in the agent's shell | refuted: `for_git`'s environment goes only to LADO's own git subprocess |
| E6 | — | external: `add` checks git on LADO's own PATH | refuted: the spec asks for it; an agent's launch checks the agents' PATH |

## Metrics

Rounds: 2 local, 2 external, 0 stand-ins. Findings: local 3 confirmed (minor), 0 refuted;
external 1 confirmed (E4, declined), 4 refuted, 1 unverifiable; findings in code changed by
the developer's cleanup: 0.

## Checks

- Round 2, on `9edc2df0`: `make lint` exit 0; `uv run pytest -n0
  tests/test_cli_git_server.py` 24 passed; `lado git-server add --help` shows the new order;
  the developer's `make test` 5643 passed.
- Round 1, on `e95375ec`: `make lint` exit 0; `make test` 5642 passed, 7 skipped;
  integration `test_git_server_access.py` and `test_update_process.py` 15 passed;
  `openspec validate git-servers --strict` valid; `--specs --strict` 85, trial archive 86.
- CI of PR #320 on `9edc2df0`: 27 of 27 pass.

## Residual risk

- Claude Code is checked only by the manual check in the pull request; no live test.
- The Codex sandbox is checked through `codex sandbox`, inside it on macOS; the Linux cell's
  path is not visible. Codex's shell tool with a model through a git server not run.
- E2: a gateway answering 401 on every path not checked.
- `make check`, the whole `make test-integration`, smoke and container not run locally;
  covered by CI.
- `runtime.py` (`_ours`, `_check_commands`) and `agent_env.py` (`for_git`,
  `without_launch`) changed: live tests may be wanted.
- The external reviewer is a model of the same family.

Found on the way: none.
