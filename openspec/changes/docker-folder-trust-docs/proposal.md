Task: LAD-87

## Why

In LADO's container Claude Code has no record of the folders it trusts, so the first
session on each repository in a permission mode other than `bypassPermissions` waits, before
any hook, for "Yes, I trust this folder" in the agent's terminal. LADO already foresees this
(`ClaudeProvider.first_hook_blocker`, `_trusted` in `src/lado/providers/claude.py`) and shows the
agent in Needs you with what to answer, but docs/install.md's Docker section ("Your first
session") does not mention it, so a new user meets an agent that seems stuck (finding M3 of
PR #82's ledger, LAD-83). The same ledger's M1: the README's short Docker start does not tell
the reader to check the shell for `LADO_*` and `COMPOSE_*` variables, which beat `.env` and
twice ran a manual check on the wrong version (LAD-69, LAD-73); docs/install.md already has
it ("Check the shell"), the README does not.

Root cause: documentation only. The question is Claude Code's own and is asked once per
repository: the trust is kept by the repository's main root (the workers' worktrees are
covered), in Claude Code's config on the container's home volume
(`CLAUDE_CONFIG_DIR=/home/lado/.claude`), so it survives restarts and updates.

## What Changes

- docs/install.md, Docker, "Your first session": a paragraph on Claude Code's folder-trust
  question: the first session on a repository the container's Claude Code has not seen
  waits in Needs you; open the agent's terminal and choose "Yes, I trust this folder"
  (Enter alone answers "No, exit" and closes the agent); it is asked once per repository
  and remembered on the home volume; another LADO container asks again, since it has its
  own home volume; only trust a repository whose `.claude/` settings and `.mcp.json` you
  accept, since a trusted folder's hooks and MCP servers run.
- docs/install.md, "If something goes wrong in Docker": an entry for an agent closed by
  Enter on the trust question (start the session again and choose "Yes").
- README.md, Install, Docker: before `mkdir ~/lado-docker`, the shell check
  `env | grep -E '^(LADO|COMPOSE)_'` and `unset` of each name printed, with the reason in
  one line, as docs/install.md's "Check the shell" has it.
- `tests/test_docker.py` pins both: README's Docker install checks the shell before
  `docker compose up -d`, and the guide's "Your first session" quotes the two answers as
  `ClaudeProvider.first_hook_blocker`'s reason words them, so the guide and the Needs you text
  cannot drift apart (one source of truth: the provider's reason).
- The living spec `container`, requirement "The install guide leads with compose and runs
  the headers' commands", gains both rules and a scenario for each.
- CHANGELOG.md: a line under a new `## 0.40.1 (unreleased)`.

## Scope

- README.md, docs/install.md, CHANGELOG.md, tests/test_docker.py, the delta of `container`.

## Out of scope

- LADO recording the trust itself in the container for folders under `LADO_PROJECTS`
  (with or without a setting in `.env`): decided against with the human. It would break
  "Never touch the user's global agent config" in spirit, race Claude Code, which rewrites
  the same `.claude.json` while other agents run, depend on an undocumented key of its
  config, and silently run the hooks and MCP servers of any repository cloned with Clone
  from URL. The question costs one answer per repository.
- Kilo and OpenCode: they ask no such question, LADO foresees none; nothing to document.
- Codex: its trust question in the container belongs to step T15 (Codex's login is not
  carried in the container yet).
- The PyPI install's "Your first session": outside the container the question comes once
  per repository the user's own Claude Code has not trusted, the same as when they run it
  by hand; not raised by M3.
- docs/research/docker-install-plan.md and the kit-epic journal: kept by session lad-52.

## Impact

- Documentation and its unit tests only: no product code, API, CLI, MCP or schema change.
  A patch release (0.40.1).
- Test layer: unit (`tests/test_docker.py`), the lowest that reads the documents and the
  provider's reason; no process boundary is crossed. The question itself is already covered
  by the existing first-hook-blocker tests. Checked by hand in the container (tasks.md,
  section 4).
