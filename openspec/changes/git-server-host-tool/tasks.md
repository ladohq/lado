The plan with each task's tests: `docs/superpowers/plans/2026-11-19-git-server-host-tool.md`.

## 1. The kinds and the helper

- [x] 1.1 `Kind.tool_oldest`, `Kind.changes`, `Kind.tool_needs`; `lado.git_credential`'s
  `token` mode (D2, D5, D11). Check: `tests/test_git_kinds.py`, `tests/test_git_credential.py`.

## 2. glab's configuration

- [x] 2.1 `glab_config`, `glab_command`, `glab_variables`: `config.yml` 600 in a 700 folder,
  whole by a rename, per host `api_protocol`, `subfolder`, `ca_cert`, the header command, no
  token (D1). Check: `tests/test_git_servers.py`.

## 3. The tool and the line

- [x] 3.1 `tool_state`, `tool_line`, `tool_warning`: the five lines and the warnings word for
  word (D4, D6). Check: `tests/test_git_servers.py`.

## 4. The launch

- [x] 4.1 `GITLAB_VARIABLES` dropped in `agent_env.merge`; `GLAB_CONFIG_DIR` in `_ours`; the
  line in the instructions; the warning in the launch notes (D3, D4, D6). Check:
  `tests/test_agent_env.py`, `tests/test_runtime_git_servers.py`.

## 5. doctor

- [x] 5.1 The tool lines and `GitLab login outside LADO` (D6, D7). Check: `tests/test_doctor.py`.

## 6. The token's right for merge requests

- [ ] 6.1 The check's ok line names a GitLab token without `api`; doctor warns; the kind's
  `scopes` text is `scope api` (D11). Check: `tests/test_git_servers.py`,
  `tests/test_doctor.py`, `tests/test_cli_git_server.py`.

## 7. End to end

- [ ] 7.1 Integration with the fake agent and the fake git server: the line, the variables,
  the warnings; a real glab against the fake server when one is on PATH (D9). Check:
  `uv run pytest -m integration tests/integration/test_git_server_host_tool.py`.

## 8. The image

- [ ] 8.1 glab 1.130.0 by SHA-256 per architecture in its own layer, update check and
  statistics off; the unit pin tests; the container test (version, auth status under a test
  CA, another host, configs unchanged, growth ≤ 60 MB) (D8). Check: `tests/test_docker.py`,
  `uv run pytest -m container -n0 tests/container/test_glab.py`.

## 9. Live

- [ ] 9.1 An agent pushes through a saved git server, Claude Code and Codex (D9). Check:
  written, not run; `make test-live` on the RC.

## 10. Docs

- [ ] 10.1 docs/install.md's GitLab part, docs/cli.md, docs/design/agents.md,
  docs/design/modules.md, docs/testing.md, the Dockerfile's header, CHANGELOG 0.48.0. Check:
  `uv run pytest -n0 tests/test_agents_md.py`, read against the code.

## 11. Regression

- [ ] 11.1 `make lint`, `make test`, 7.1 with `-m integration`, `openspec validate
  git-server-host-tool --strict`, `openspec validate --specs --strict`, the trial archive; the
  pull request carries the manual check. Check: the commands' exit status.
