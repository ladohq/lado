## 1. Tests never reach the user's Claude Code config

- [x] 1.1 `tests/conftest.py`: `claude_config` becomes `autouse=True` (D5); `fake_clis` keeps
  taking it. `make test` stays green (a test that reached the user's config would now write
  there). Check: `grep -n "autouse" tests/conftest.py` shows it; `make test`.

## 2. The careful writer and the trust (unit: pure file logic, the lowest layer)

- [x] 2.1 `tests/test_providers.py`, beside the `_trusted` tests, with `claude_home`
  (requirements "LADO records Claude Code's trust…", "…one careful writer", "A missing
  config…", "A config LADO cannot understand…", "The trust question stays the fallback…"):
  - untrusted repo: `_blocker` returns `Blocker(note=...)` with no reason; the file's
    `projects[str(repo.resolve())]` is `{"hasTrustDialogAccepted": true}`; `numStartups` and
    another project's entry kept (scenarios "A repository Claude Code has not seen", "The
    rest of the config is kept");
  - a worktree: the main root's key is written, not the worktree's ("A worker in a
    worktree");
  - already trusted (its entry, or a folder under a trusted one): bytes and `st_mtime_ns`
    unchanged, `Blocker()` ("Already trusted");
  - an entry `{"hasTrustDialogAccepted": false, "x": 1}` becomes `true` with `x` kept ("An
    entry Claude Code made earlier");
  - `CLAUDE_CONFIG_DIR` and the older `.config.json` are the files written ("The agent's
    own config folder", "An older config file");
  - no file: created as `{"projects": {repo: {"hasTrustDialogAccepted": true}}}`, mode 600
    ("A fresh home");
  - a symlink to a mode-600 file: still a symlink, the target written, mode 600 ("Mode and
    symlink");
  - not JSON, `[]`, `{"projects": []}`: unchanged bytes and the existing warning (the
    parametrised `test_claude_config_it_cannot_read_is_a_warning` also asserts the bytes);
    an entry `"x"` or `null`: unchanged bytes, reason starts with `Claude Code asks whether
    to trust <repo>: LADO could not record the trust (` and names the file ("Not JSON",
    "The repository's entry is not an object");
  - a read-only config folder: reason with the error, folder listing unchanged, no
    `*.tmp` left ("A config folder LADO cannot write", "No temporary file is left");
  - `os.replace` raising (monkeypatched): no `*.tmp` left, the old file unchanged.
  The test `test_claude_blocks_the_first_hook_in_a_folder_it_does_not_trust` and
  `test_claude_reads_only_the_projects_of_its_config` change to these expectations. All
  fail before 2.2.
- [x] 2.2 `src/lado/providers/base.py`: `Blocker.note: str | None = None` (what the provider
  did so that nothing holds the agent, told and logged as the reason is);
  `first_hook_blocker`'s docstring says it may first settle what LADO answers itself.
  `src/lado/providers/claude.py`: `_config_path(env)` shared by `_trusted` and the writer;
  `edit_config(env, change)` (D2, D3: flock on `LADO_HOME/claude-config.lock`, re-read,
  `change(config) -> bool`, temp file in the same folder, indent 2, fsync, mode kept or
  600, symlink resolved, `os.replace`, the temp file removed on any failure; `ValueError`
  naming the file for a top level that is not an object); `_record_trust(cwd, env)` (D4)
  through it; `first_hook_blocker` records when `_trusted` is false and returns
  `Blocker(note="LADO recorded Claude Code's trust in <repo> in <file>")`, or the fallback
  reason with `(<why>)` on `OSError`/`ValueError`. The comment block above `_trusted`
  gains the hand checks of 2.1.295 (proposal, Why) and the exception's reason; the old
  comment "LADO only reads whether it trusts the folder" goes. 2.1 passes.

## 3. The runtime tells and logs the note (unit)

- [x] 3.1 `tests/test_runtime.py` with `fake_tmux` and an untrusted `claude_config`
  (`config.trust()` with no folder): `start_session(..., provider="claude")` returns the
  note in `Started.warnings`, loop.log holds it once, the supervisor is not `waiting`;
  `spawn_worker` returns it in its warnings and loop.log holds it once (scenarios "The
  session's start", "A worker's spawn"); a resume does the same. `tests/test_cli.py`:
  `lado start` prints it on stderr as `lado: <note>`. Fail before 3.2.
- [x] 3.2 `src/lado/runtime.py`: `_first_hook_blocker` returns the note with the reason
  and the warning; start and resume write the blocker's lines to loop.log as the spawn
  does (each line once). 3.1 passes.

## 4. Across processes (integration, the fake agent)

- [x] 4.1 `tests/integration/fake_provider.py`: under `FAKE_AGENT_TRUST=1` the fake
  provider's `first_hook_blocker` uses `claude.first_hook_blocker`'s trust logic on the
  test's `CLAUDE_CONFIG_DIR` (the fake agent's title in the reason), and
  `tests/integration/fake_agent.py`, under the same variable, asks first (as
  `FAKE_AGENT_ASKS_FIRST`) only when that config does not trust its folder's main root.
  A new test in `tests/integration/test_agent_liveness.py`: with an untrusted config
  holding other keys, `spawn_worker` starts `w1`, which reaches `idle` and gets its task
  without anything typed; the config holds the entry and the other keys; loop.log holds
  the note. A second test: the config's folder read-only, `w1` waits with the fallback
  reason, and a typed "yes" lets it go on. Run with
  `uv run pytest -m integration -n auto tests/integration/test_agent_liveness.py`.

## 5. Real CLIs

- [x] 5.1 `tests/smoke/conftest.py`: the Claude config drops its `projects` entry (D6),
  keeping `hasCompletedOnboarding` and `bypassPermissionsModeAccepted`, and its comment
  says LADO records the trust; `tests/smoke/test_smoke.py` (Claude) asserts the config
  then trusts the repo. Run by CI (needs the real CLI); locally `make test-smoke
  PROVIDER=claude` when Claude Code is on PATH.
- [x] 5.2 `tests/real_clis.py` `answer_dialogs` and `tests/live/conftest.py`'s docstring:
  Claude Code's trust dialog is no longer expected (LADO records the trust in the live
  config); if it shows, the test fails with the reason. Written, not run (live: Claude
  only with the human's yes).

## 6. Docs

- [x] 6.1 `tests/test_docker.py` `test_the_first_session_names_claude_codes_trust_question`:
  the reason comes from a read-only home (the fallback); the guide also names that LADO
  trusts the repository and that its `.claude/` settings and `.mcp.json` run. Fails before
  6.2.
- [x] 6.2 docs/install.md, Docker "Your first session": LADO records Claude Code's trust in
  the repository a session starts in, so it does not ask; the repository's own Claude Code
  settings (`.claude/`) and MCP servers (`.mcp.json`) run without a question, so start
  sessions only in repositories whose settings you accept; when LADO cannot record it, the
  old text (Needs you, the two answers, the reason says why). "If something goes wrong in
  Docker": the entry on "No, exit" says it happens only when LADO could not record the
  trust. 6.1 passes.
- [x] 6.3 AGENTS.md, Design principles: "Never touch the user's global agent config"
  gains its one exception (Claude Code's trust in the session's repository, through
  `claude.edit_config`, LAD-106); `tests/test_agents_md.py` passes (at most 200 lines).
  docs/design/agents.md (the paragraph on the CLI that asks before any hook: Claude Code
  is asked no more when LADO records the trust; the note) and docs/design/modules.md
  (`claude.py`: "only `projects` is read, nothing written" becomes what is written and
  how; `Blocker.note`). docs/testing.md: the smoke's Claude config without the trust, the
  live test without the dialog, `claude_config` autouse.
- [x] 6.4 CHANGELOG.md: `## 0.44.0 (unreleased)` on top, `### Added`: **Claude Code trusts
  the session's repository.** LADO records Claude Code's folder trust itself, so a session
  started from the UI or a phone no longer waits for "Yes, I trust this folder"; the
  repository's own Claude Code settings run (docs/release.md's rules: at most three lines).

## 7. Checks

- [x] 7.1 `make lint`, `make test`, the integration file of 4.1 with its marker,
  `openspec validate claude-folder-trust --strict`, `openspec validate --specs --strict`.
