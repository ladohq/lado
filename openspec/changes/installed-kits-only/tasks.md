## 1. Test helper

- [ ] 1.1 `tests/agent_helpers.install_kit(folder) -> str` (D9): reads the name from the
  folder's kit.yaml, writes the `kits` row with `folder=` into the test's `LADO_HOME`.
  Unit test in `tests/test_kits.py`: a folder installed by it is found by `kits.find`.

## 2. Core lookup

- [ ] 2.1 `kits.py` (D1, D2, D3): delete `project_kits`; drop `repo` from `candidates`,
  `find`, `available`, `resolve`; drop the broken-link handling of `_in_folder` and
  `Found._check`; module docstring and `Found.where` comment. Unit tests
  (`tests/test_kits.py`): "A repository's own kit is not read" (`find` refuses a name only
  in `<repo>/.lado/kits`, with the spec's text), "An installed kit shadows a built-in one"
  (`available` marks the built-in `default` shadowed by `user`); the `project` fixture
  becomes installed folder kits (1.1).
- [ ] 2.2 Callers: `runtime.start_session`, `spawn_worker`, `runs.py`, `cli.py`,
  `server/launch.py`. `runtime.kit_users` without the project exception (D7);
  `exclude_worktrees`' docstring (D8). Unit test (`tests/test_runtime.py`): "A session
  whose repository has a kit folder of that name" is a user of the kit.
- [ ] 2.3 Move the unit tests that made a project kit to `install_kit` (D9, D10):
  test_produces, test_fingerprint, test_read_only_hooks, test_mcp_server,
  test_server_runs, test_feed, test_reads, test_runtime, test_runtime_start_approved,
  test_server_gates, test_server_session, test_server_artifacts, test_attachments,
  test_runs, test_cli, test_server_launch. `make test` green.

## 3. CLI

- [ ] 3.1 `lado kits` without `--repo`, `_repo_or_none` deleted, `kits show` and `kits
  check` without a repository (D4). Unit tests (`tests/test_cli.py`): "--repo is refused"
  (exit 2), "The same list for every folder" (`lado kits` in two repos with different
  `.lado/kits` prints the same), "A repository's own kit is not read" for `lado start`.

## 4. API and UI

- [ ] 4.1 `GET /api/kits` without `where`, `launch.kit_infos(has_db)`,
  `launch._session_kit(name)` (D5); `make web-types`, commit `web/openapi.json` and
  `web/src/api.gen.ts`. Unit tests (`tests/test_server_launch.py`): the list is the
  installed and built-in kits; `?where=<repo with .lado/kits>` gives the same list (200).
  `tests/test_server_kits.py`: the remove-preview names a stopped session of a repository
  with `.lado/kits/<kit>`.
- [ ] 4.2 The web UI's sources stay as they are (D6): `git diff origin/main -- web/src`
  shows only `api.gen.ts`; `make web` green (stale-types check, tsc, vitest).
- [ ] 4.3 UI e2e: `tests/ui/test_launch.py`, `test_artifacts_tab.py`, `test_flows_tab.py`,
  `test_gates.py`, `test_layout.py` on installed folder kits (fixtures only; the window
  does not change). `uv run pytest -m ui <files>` green.

## 5. Integration and live tests

- [ ] 5.1 `tests/integration/test_session_start.py`, `test_agent_kits.py`,
  `test_flow_runs.py`, `test_read_only.py` on installed folder kits (D9).
  `uv run pytest -m integration -n auto <files>` green; add one case to
  `test_session_start.py`: a repository with `.lado/kits/team` and `--kit team` is refused
  with `kit "team" not found`, and no tmux session is made.
- [ ] 5.2 `tests/live/test_live.py`'s `passive_kit` on an installed folder kit outside the
  repository; `check_mcp_token` reads the token from that folder. Written, not run (live
  tests run at release).

## 6. Docs

- [ ] 6.1 AGENTS.md, docs/kits.md, docs/design/ui.md, CLI help (D11); `grep -rn
  "\.lado/kits\|project kit\|--repo" AGENTS.md README.md docs src web/src` finds no
  project-kit mention.
- [ ] 6.2 CHANGELOG.md under `## 0.36.0 (unreleased)` (D11, D12).

## 7. Regression

- [ ] 7.1 `make lint`, `make test`, `make web`, the changed integration and UI files with
  their markers, `openspec validate --specs --strict`; CI green on the pull request (the
  full `make check` and the smoke).
