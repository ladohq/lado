# Installed kits only: implementation plan

**Goal:** LADO looks kits up only among the installed (lado.db) and the built-in ones; a
repository's `.lado/kits` is never read (LAD-22).

**Architecture:** the kit lookup in `src/lado/kits.py` loses its folder input; its callers
(runtime, runs, CLI, server) follow, the web UI's sources stay as they are; tests that made a
project kit install a folder kit in the test's `LADO_HOME` through one helper.

**Spec:** `openspec/changes/installed-kits-only/` (proposal, delta `kit-lookup`,
`design.md` D1–D12). **Design doc:** `docs/superpowers/specs/2026-10-12-installed-kits-only-design.md`.

## Task 1: The test helper

**Files:** `tests/agent_helpers.py`, `tests/test_kits.py`.

1. Write the test first: in `tests/test_kits.py`, a folder kit made under `tmp_path /
   "kits" / "team"` and passed to `install_kit` is what `kits.find("team")` returns, with
   `where == "user"`.
2. Add `install_kit(folder: Path) -> str` to `tests/agent_helpers.py`: read `name` from
   `folder / "kit.yaml"` (the kit's own loader, `kits.load(folder)`, or a plain YAML read),
   `state.add_kit(state.InstalledKit(name, folder=str(folder)))`, return the name.
3. Run `uv run pytest tests/test_kits.py -n0 -k install_kit`; commit.

## Task 2: The core lookup (D1, D2, D3)

**Files:** `src/lado/kits.py`, `tests/test_kits.py`.

1. Tests first in `tests/test_kits.py`:
   - `test_a_repository_kit_is_not_read`: `<repo>/.lado/kits/team/kit.yaml` exists;
     `kits.find("team")` raises `KitError` whose text starts with `kit "team" not found;
     looked in the installed kits in` and names `builtin_kits`, and has no `.lado/kits`.
   - `test_an_installed_kit_shadows_the_built_in_one`: install a folder kit `default`;
     `kits.available()` pairs the built-in `default` with `"user"`; `kits.find("default")`
     is the installed one.
   - The `project` fixture becomes `kits_dir` (`tmp_path / "kits"`); each test that wrote a
     kit there installs it with `install_kit`; tests of project-over-installed shadowing
     are deleted (replaced by the two above).
2. Delete `project_kits`; drop `repo` from `candidates`, `find`, `available`, `resolve`;
   `find`'s message as in the spec; drop `_in_folder`'s broken-link list and
   `Found._check`'s broken-link branch; docstrings and the `where` comment.
3. `uv run pytest tests/test_kits.py -n auto`; commit.

## Task 3: Callers in the core (D7, D8)

**Files:** `src/lado/runtime.py`, `src/lado/runs.py`, `tests/test_runtime.py`.

1. Test first in `tests/test_runtime.py`: a stopped session of a repository with
   `.lado/kits/team/` whose kits are `["team"]` is in `kit_users("team").stopped`.
2. `kits.resolve(sess.kits, sess.without)` in `start_session`, `spawn_worker` and
   `runs.py`; `kit_users` without the project check; `exclude_worktrees`' docstring.
3. Commit.

## Task 4: Move the unit tests (D9, D10)

**Files:** test_produces, test_fingerprint, test_read_only_hooks, test_mcp_server,
test_server_runs, test_feed, test_reads, test_runtime, test_runtime_start_approved,
test_server_gates, test_server_session, test_server_artifacts, test_attachments, test_runs,
test_cli, test_server_launch (all under `tests/`).

1. Each `repo / ".lado" / "kits" / <name>` becomes `tmp_path / "kits" / <name>` followed
   by `install_kit(...)` before the session starts. `test_fingerprint.py` and
   `test_runtime.py`'s `git status` check use `.lado/sdlc.md` as "a file under `.lado/`".
2. `make test` green (numbers in the report); commit.

## Task 5: CLI (D4)

**Files:** `src/lado/cli.py`, `tests/test_cli.py`.

1. Tests first: `lado kits --repo x` exits 2 with argparse's `unrecognized arguments`;
   `lado kits` run with the cwd in two repositories that differ only in `.lado/kits`
   prints the same output; `lado start <repo> --kit team` with `team` only in
   `<repo>/.lado/kits` exits 1 with `kit "team" not found` and stores no session.
2. Remove `--repo` and `_repo_or_none`; `cmd_kits`, `cmd_kits_show`, `cmd_kits_check`
   without a repository.
3. Commit.

## Task 6: API (D5)

**Files:** `src/lado/server/launch.py`, `src/lado/server/app.py`,
`tests/test_server_launch.py`, `tests/test_server_kits.py`, `web/openapi.json`,
`web/src/api.gen.ts`.

1. Tests first: `GET /api/kits` lists the installed and built-in kits;
   `GET /api/kits?where=<repo with .lado/kits/team>` answers 200 with the same list (no
   `team`); `GET /api/kits/team/remove-preview` names a stopped session of a repository
   with `.lado/kits/team`.
2. `list_kits(has_db)`, `launch.kit_infos(has_db)`, `launch._session_kit(name)`.
3. `make web-types`; commit the two generated files with the change.

## Task 7: Web UI stays (D6)

The New session window is another task: `web/src/api.ts` and `web/src/Launch.tsx` are not
changed. Check that `git diff origin/main -- web/src` shows only `api.gen.ts` and that
`make web` is green (stale-types check, tsc, vitest).

## Task 8: UI e2e

**Files:** `tests/ui/test_launch.py`, `test_artifacts_tab.py`, `test_flows_tab.py`,
`test_gates.py`, `test_layout.py`.

1. Kits made in the repository become installed folder kits (`install_kit`), before the
   page opens; the tests' assertions stay.
2. `uv run pytest -m ui <files>` green; commit.

## Task 9: Integration and live tests

**Files:** `tests/integration/test_session_start.py`, `test_agent_kits.py`,
`test_flow_runs.py`, `test_read_only.py`, `tests/live/test_live.py`.

1. Kits outside the repository, installed with `install_kit` before `lado start`.
2. New case in `test_session_start.py`: a repository with `.lado/kits/team`, `lado start
   --kit team` is refused with `kit "team" not found`; no tmux session and no session row.
3. `passive_kit(tmp_path, ...)` writes and installs the kit outside the repository;
   `check_mcp_token` reads `mcp-token` from that folder.
4. `uv run pytest -m integration -n auto <the four files>` green; the live file: "written,
   not run". Commit.

## Task 10: Docs (D11, D12)

**Files:** `AGENTS.md`, `docs/kits.md`, `docs/design/ui.md`, `CHANGELOG.md`, `src/lado/kits.py`
docstrings (done in Task 2).

1. AGENTS.md: the `kits.py` lookup, `/api/kits` in `launch.py`, the remove-preview line,
   the "Explicit lookup" principle (installed, then built-in).
2. docs/kits.md: delete "Project kits"; Troubleshooting's `kit not found` without
   `--repo`.
3. docs/design/ui.md: Launch's Kits line says the list is the installed and built-in kits
   (the server ignores the folder the window sends);
   the Kits page's Installed tab without "not a project's kits".
4. CHANGELOG.md under `## 0.36.0 (unreleased)`: "Kits are looked up only among the
   installed and the built-in ones: a repository's `.lado/kits` is no longer read; install
   a kit folder with `lado kits add <folder>`. `lado kits --repo` and `GET
   /api/kits?where=` are gone."
5. `grep -rn "\.lado/kits\|project kit\|kits --repo" AGENTS.md README.md docs src web/src`
   finds nothing; commit.

## Task 11: Regression

`make lint`; `make test`; `make web`; `uv run pytest -m integration -n auto` and `uv run
pytest -m ui` on the changed files; `openspec validate --specs --strict`; push; CI green
(the full `make check` and the smoke on Linux and macOS).
