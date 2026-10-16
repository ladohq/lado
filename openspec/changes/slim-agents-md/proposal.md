Task: LAD-82

## Why

AGENTS.md has grown to 175 KB, 2127 lines (about 45 thousand tokens), and every agent of
every session loads it whole (CLAUDE.md is `@AGENTS.md`). Most of it is not needed for an
arbitrary task: Layout (80 KB) describes each module's behaviour in paragraphs, How agents
talk (40 KB) is the delivery protocol with the agent CLIs' facts checked by hand, Commands
(25 KB) is mostly the setup of the live, smoke and container tests, CI and the Windows
probe, and Try it locally (23 KB) is the CLI's behaviour.

Root cause: the developer's rule in `.lado/sdlc.md`, "Keep AGENTS.md (Layout, How agents
talk, the CLI sections) true to the code in the same pull request", made every pull
request add its behaviour to AGENTS.md, and nothing bounds the file.

## What Changes

- AGENTS.md becomes a map of at most 200 lines: what LADO is, the commands, one line per
  module or folder of the layout, the test layers in short with the main isolation rules,
  the design principles and rules as they are (with release, versions and CHANGELOG in
  short), and where to read more.
- What leaves AGENTS.md moves nearly word for word into documents read on demand:
  - `docs/design/agents.md`: How agents talk;
  - `docs/design/modules.md`: Layout;
  - `docs/testing.md`: the test infrastructure of Commands (integration, live, smoke,
    container tests, CI, the Windows probe, the test-run lock) and Testing in full;
  - `docs/cli.md`: Try it locally.
  Only the cross-references inside the moved text change (to the file that now holds the
  section) and each file gets a title and a line saying what it holds.
- References to AGENTS.md's sections elsewhere point at the new files: `docs/design/ui.md`,
  `docs/design/macos-gui-session.md`, `BACKLOG.md`, `.github/workflows/windows-shell.yml`,
  `tests/local_models.py`, `tests/live/conftest.py`, and the Purpose line of the living spec
  `turn-end-hand-over` (not a requirement, so it needs no delta).
- A unit test keeps AGENTS.md at most 200 lines and every relative link in it pointing at
  a file of the repository.
- `.lado/sdlc.md`'s developer rule becomes: AGENTS.md is the project's map, and gets only
  what an agent needs in any task; behaviour goes to `docs/design/agents.md`,
  `docs/design/modules.md`, `docs/testing.md`, `docs/cli.md` or the module's docstring,
  kept true to the code in the same pull request.
- No version bump of its own and no CHANGELOG line: docs and a test only, nothing a user of
  LADO sees (a patch by the versions rule).

## Scope

- `AGENTS.md`, the four new documents, the references listed, `.lado/sdlc.md`, the new
  unit test.

## Out of scope

- Shortening the moved text: a near-verbatim move keeps the facts checked by hand and lets
  the review see a pure move; shortening is a task of its own (the human's decision).
- Moving the text into module docstrings: a long move over dozens of files; the documents
  are one place to read now.
- `docs/superpowers/` and `openspec/changes/archive/`: history, they name AGENTS.md as it
  was then.
- `ci.yml`'s smoke skip list: it holds `docs/` already, so the new documents skip the smoke
  as AGENTS.md does; `tests/test_ci_workflow.py` stays as it is.
- ROADMAP.md: its line about AGENTS.md stays true.

## Impact

- Docs, `.lado/sdlc.md` and one unit test. No product code, API, CLI, MCP or schema change.
- Every agent's context loses about 40 thousand tokens at each session start.
