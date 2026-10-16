## 1. Move the sections out

- [ ] 1.1 `docs/design/agents.md` holds How agents talk, `docs/design/modules.md` Layout,
  `docs/cli.md` Try it locally, `docs/testing.md` Commands' test infrastructure (from
  "Unit and integration tests run in parallel" to the Windows probe's end) and Testing,
  each nearly word for word, with a title and one line of what it holds; a reference to a
  section of AGENTS.md inside the moved text names the file that holds it now. Check: each
  paragraph of the old AGENTS.md (`git show origin/main:AGENTS.md`) is in one of the new
  files or in the new AGENTS.md, by a diff of the sorted paragraphs, changed only in its
  cross-references.

## 2. The new AGENTS.md

- [ ] 2.1 AGENTS.md, at most 200 lines: what LADO is and ROADMAP.md; Commands (the uv and
  make targets, `make browser`, parallel tests with no shared path, port or file, the
  test-run lock in one line); Layout, one line per module or folder of `src/lado/`,
  `web/`, `tests/`, `scripts/`, `docker/`, `npm/`; Testing, the seven layers in short with
  the isolation rules (fake agent, own `LADO_HOME` and tmux socket, never the default
  socket, Claude Code's live test only with the human's yes); Design principles and Rules
  as they are, with release, versions, CHANGELOG and SECURITY.md in short; "Read more"
  naming `docs/design/agents.md`, `docs/design/modules.md`, `docs/testing.md`,
  `docs/cli.md`, `docs/design/ui.md`, `docs/design/artifacts.md`, `docs/release.md`,
  `openspec/specs/`. Check: `wc -l AGENTS.md`.
- [ ] 2.2 `tests/test_agents_md.py`: AGENTS.md at most 200 lines, and each relative link
  (`[...](path)`, anchor and query dropped) names a path of the repository; failures name
  the count or the link. Check: red once with a 201-line copy and with a link to a missing
  file (the test reads a path it is given), then green with `uv run pytest -n0
  tests/test_agents_md.py`.

## 3. References and the rule

- [ ] 3.1 Point the references at the new files: `docs/design/ui.md` (lines naming How
  agents talk and AGENTS.md's principles), `docs/design/macos-gui-session.md`,
  `BACKLOG.md`, `.github/workflows/windows-shell.yml`'s header, `tests/local_models.py`,
  `tests/live/conftest.py`. Check: `git grep -n -e 'AGENTS.md' -e 'How agents talk' -e
  'Try it locally' -- ':!openspec/changes/archive' ':!docs/superpowers'` names only
  references that are still true.
- [ ] 3.2 `.lado/sdlc.md`, Developer: the rule "Keep AGENTS.md (Layout, How agents talk,
  the CLI sections) true to the code in the same pull request" becomes "AGENTS.md is the
  project's map: add to it only what an agent needs in any task. Behaviour goes to
  `docs/design/agents.md`, `docs/design/modules.md`, `docs/testing.md`, `docs/cli.md` or
  the module's docstring; keep them true to the code in the same pull request." Check:
  read the section.

## 4. Checks

- [ ] 4.1 `make lint`, `make test` green (counts in the build report);
  `openspec validate --specs --strict` green.
