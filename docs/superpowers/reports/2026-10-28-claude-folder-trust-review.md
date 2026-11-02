# LAD-106 claude-folder-trust: review report

Pull request #177 `fix/lad-106-claude-folder-trust` → `main`. Scale: tweak, reviewed in
breadth in round 1 (the code writes the user's `~/.claude.json` and changes `providers/`
and `runtime.py`). Head reviewed last: `1783df80` (= the remote head); round 1 reviewed
`75d7496e`. Before it starts a Claude agent, LADO sets `hasTrustDialogAccepted` in the
`projects` entry of the repository's main root in Claude Code's config through one careful
writer (`edit_config`: one lock, re-read, no write when nothing changes, temp file and
atomic replace, mode and symlink kept, a file it cannot parse left untouched); the trust
question stays the fallback, with the reason the write failed. AGENTS.md names the
exception to "Never touch the user's global agent config". `providers/` (claude.py,
base.py), `runtime.py` and `tests/live/` changed: live tests may be wanted. Schema
migration: no.

## Rounds

- **Round 1** (`origin/main..75d7496e`): a local pass in breadth with every lens: the
  spec (each scenario of `claude-folder-trust` and `container` covered by code and a
  test), tests (each new test can fail), silent drops, docs, the architecture against
  AGENTS.md (nothing above `providers/` knows Claude's file; `Blocker.note` is neutral).
  **External 1** (Claude Code GitHub Action, "Claude finished" in 44 s): read `src/`
  whole, not the tests, docs or openspec texts, which were read locally; no blockers.
- **Round 2** (`75d7496e..1783df80`, after the first archive failed strict validation):
  a precision pass over one commit that shortens the `container` requirement's text to
  500 characters; code and tests unchanged. No external round: the cap of 1 was used.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | three new tests that close a folder with mode 0o500 are not skipped under root, where the write succeeds | confirmed | minor | declined: CI and the image run tests as `USER lado` |
| F2 | 1 | local | tasks.md 2.2 names `_record_trust(cwd, env)`, the code `_record_trust(repo, env)` | confirmed | minor | declined: the deviation is in the build report |
| E1 | 1 | external 1 | the config is read and written in the locale's encoding with `ensure_ascii=False` | confirmed (narrowly) | minor | declined: only a non-UTF-8, non-C locale; the cheapest fix is `encoding="utf-8"` |
| E2 | 1 | external 1 | the replace loses the file's owner when LADO runs as root in the container | refuted | — | dropped: the image runs as `USER lado` |
| E3 | 1 | external 1 | a read-only (0444) config is still replaced | confirmed | minor | declined: Claude Code rewrites the file itself |
| E4 | 1 | external 1 | no fsync of the folder after `os.replace` | confirmed | minor | declined: a lost rename brings the trust question back |
| F3 | 2 | local | the shortened `container` requirement no longer says the trust is kept on the home volume (docs/install.md still does) | confirmed | minor | declined: behaviour and tests unaffected |

## Checks

Round 1 (`75d7496e`): `make lint` green; `make test` 4328 passed, 2 skipped;
`uv run pytest -m integration -n auto tests/integration/test_agent_liveness.py` 13 passed;
`openspec validate claude-folder-trust --strict` valid; `openspec validate --specs
--strict` 49 passed; `make test-smoke PROVIDER=claude` (Claude Code 2.1.295) 2 passed by
the developer. Round 2 (`1783df80`): `openspec validate claude-folder-trust --strict`
valid, `openspec validate --specs --strict` 49 passed, CI 23 of 23 including `ci-ok` and
the Claude smoke on Linux and macOS. At archive: `openspec validate --specs --strict` 50
passed after the new capability's Purpose was written.

## Not checked

The live tests (`tests/live/conftest.py` and `tests/real_clis.py` changed, written, not
run; the live Claude test now writes the trust into the human's real `~/.claude.json`).
The race with Claude Code's own writes of its config (D3, accepted); that Claude Code
re-reads the file was checked by hand on 2.1.295, not by a test. The config's format is
pinned only by that manual check and the smoke with the real CLI.
