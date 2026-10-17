## 1. The guide

- [x] 1.1 docs/install.md, Docker, "Your first session": after the paragraph on **Start
  session**, a paragraph on Claude Code's folder-trust question (proposal, What Changes,
  first item): where it shows (Needs you, the agent's terminal), the answer ("Yes, I trust
  this folder"; Enter alone is "No, exit" and closes the agent), once per repository,
  remembered on the home volume, asked again by another LADO container, and only for a
  repository whose `.claude/` settings and `.mcp.json` you accept. Words as Claude Code
  2.1.295 shows them (the same as `ClaudeProvider.first_hook_blocker`'s reason). Check: read
  the rendered section on GitHub's preview of the branch.
- [x] 1.2 docs/install.md, "If something goes wrong in Docker": an entry **An agent closed
  right after the session started**: Enter on the trust question answered "No, exit";
  start the session again (`lado start` resumes it, or the UI's start) and choose "Yes, I
  trust this folder". Check: as 1.1.
- [x] 1.3 README.md, Install, Docker: before `mkdir ~/lado-docker`, one sentence (a shell
  variable beats `.env`) and

  ```bash
  env | grep -E '^(LADO|COMPOSE)_'      # left from an earlier try? unset each name printed
  unset LADO_VERSION LADO_PROJECTS LADO_PORT LADO_IMAGE COMPOSE_PROJECT_NAME
  ```

  matching docs/install.md's "Check the shell" (no new variable names). Check:
  `uv run pytest -n0 tests/test_agents_md.py` and any README test still green (`make test`).
- [x] 1.4 CHANGELOG.md: on top, `## 0.40.1 (unreleased)` with one line: the Docker guide
  says how to answer Claude Code's "trust this folder?" question of a new repository, and
  the README's Docker start checks the shell for `LADO_*`/`COMPOSE_*` variables first.

## 2. Tests

- [x] 2.1 `tests/test_docker.py`, `test_readmes_docker_install_checks_the_shell_first`:
  README's Docker install (`readme_part("Install", "Docker")`) has
  `env | grep -E '^(LADO|COMPOSE)_'` and an `unset` naming `LADO_VERSION` and
  `COMPOSE_PROJECT_NAME`, both before `docker compose up -d`. Check: red on main's README,
  green after 1.3, `uv run pytest -n0 tests/test_docker.py`.
- [x] 2.2 `tests/test_docker.py`, `test_the_first_session_names_claude_codes_trust_question`:
  the guide's Docker "Your first session" (`guide_part`) has "Needs you",
  "Yes, I trust this folder" and "No, exit", and each of the two answers is in the reason
  of `ClaudeProvider().first_hook_blocker(<a fresh git repo in tmp_path>, {"HOME": <empty
  tmp folder>})`. Check: red before 1.1, green after; `uv run pytest -n0
  tests/test_docker.py`.

## 3. Checks

- [ ] 3.1 `make lint`, `make test` green (counts in the build report);
  `openspec validate --specs --strict` green.
- [ ] 3.2 No `docker volume prune`, `docker system prune` or other global Docker command
  added to any document: `git diff origin/main -- README.md docs/ | grep -n prune` finds
  nothing.

## 4. Manual check for the human (put these steps in the pull request's description)

- [ ] 4.1 The pull request's description carries these steps, in English:
  1. Read the docs from the branch without switching your checkout:
     `git -C ~/Projects/lado fetch origin && git -C ~/Projects/lado worktree add
     /tmp/lad-87-docs origin/fix/lad-87-docker-folder-trust`; open
     `/tmp/lad-87-docs/README.md` (Install, Docker) and `/tmp/lad-87-docs/docs/install.md`
     (Docker, Your first session).
  2. In the folder of your Docker LADO (e.g. `~/lado-docker`), follow the README's Docker
     start: `env | grep -E '^(LADO|COMPOSE)_'`; `unset` each name printed; `docker compose
     up -d`; `docker compose exec lado lado ui --no-open`, open the link. Expected: the
     version in the UI is the one in `.env`.
  3. Make a repository the container's Claude Code has never seen:
     `mkdir -p "$LADO_PROJECTS_PATH/trust-check" && cd "$_" && git init -q && git commit
     -q --allow-empty -m init` (your projects folder's full path in place of
     `$LADO_PROJECTS_PATH`).
  4. In the UI, **Launch**: pick `trust-check`, agent CLI Claude Code, permission mode
     `default` (not `bypassPermissions`), **Start session**. Expected: the supervisor shows
     in **Needs you** with "asks whether to trust …/trust-check"; its terminal shows the
     question, as the guide says.
  5. In the agent's terminal choose "Yes, I trust this folder". Expected: the agent starts
     and leaves Needs you.
  6. Stop the session and start it again on the same repository. Expected: no question.
  7. Clean up: `git -C ~/Projects/lado worktree remove /tmp/lad-87-docs`; stop the
     session; delete `trust-check` if you like. Touch no other container or volume.
