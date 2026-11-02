# One-line Docker install Implementation Plan

**Goal:** One command (`curl -fsSL …/install.sh | sh`; on Windows `irm …/install.ps1 |
iex`) installs or updates LADO's container: Docker checked, `.env` written from what the
computer knows plus at most three questions, the release's `compose.yaml` downloaded,
LADO started, its link printed and opened.

**Architecture:** `docker/install.sh` (POSIX sh) does every step; `docker/install.ps1` gets
Windows to WSL's Ubuntu and runs the same `install.sh` there. The release workflow stamps
both with the tag's version (`scripts/stamp_installers.py`) and attaches them to the GitHub
release beside `compose.yaml`. No Python of `src/lado/` changes.

**Tech Stack:** POSIX sh (dash, bash), PowerShell 5.1/7, Python 3.10+ for the stamp and
the tests, pytest (fakes on PATH, `pty`), real Docker in `tests/container/`.

**Spec:** `openspec/changes/docker-installer/` (proposal AC-1..AC-12, deltas of
`docker-installer`, `image-release`, `container`; design.md D1-D10) and
`docs/superpowers/specs/2026-10-31-docker-installer-design.md`.

## Global Constraints

- Every failure line starts `lado install:` and names the next step.
- The phone's warning, word for word: `LADO's link holds its key: anyone on the same
  network who gets it can run commands as you, it travels unencrypted (plain HTTP), and a
  laptop is open on every network it joins, a café's too.` Then `Open LADO on your phone
  too? [y/N]:`.
- The unstamped refusal: `lado install: this install.sh carries no version: take the
  release's (https://github.com/ladohq/lado/releases/latest/download/install.sh) or pass
  --version X.Y.Z`.
- Placeholders: `LADO_INSTALL_VERSION=` (a line of its own in install.sh),
  `$LadoVersion = ''` (install.ps1).
- No `sed -i`, no `sudo`, no bashisms; `main "$@"` on the script's last line.
- `.env` only gets variables that `docker/compose.yaml`'s header names.
- CHANGELOG.md: one line under `## 0.44.0 (unreleased)` → `### Added` (or a new
  `## 0.45.0 (unreleased)` if 0.44.0's RC is tagged first).
- Suites with `-n auto`; the container test with `make test-container` (after `make
  docker`), `-n0`.

## Review Focus

- A failure in the middle leaves `.env` and `compose.yaml` as they were (temporary files
  moved in place).
- The shell's `LADO_*` / `COMPOSE_*` never reach compose; check the fake docker's logged
  environment.
- Another folder's container is never touched; `--dir` gets its own project name.
- Version order: `0.44.0rc2 < 0.44.0 < 0.44.1 < 0.45.0`; a dev version refuses.
- Questions under `curl | sh` come from `/dev/tty`; with no tty the defaults are taken
  and said.
- The PowerShell script in 5.1: no PowerShell 7-only syntax; `wsl -l -q` UTF-16 output.

---

### Task 1: `install.sh` skeleton, flags, version, Docker checks

**Files:** Create `docker/install.sh`; create `tests/test_install_sh.py`, its fakes in
`tests/install_fakes.py`: fake `docker`, `curl`,
`git`, `uname`, `open`, `xdg-open`, `scutil`, `hostname`, `nc`, `systemctl`, `sleep`, each a small
Python script that logs `argv` and the `LADO_*`/`COMPOSE_*` of its environment to a
JSON-lines file and answers from a per-test settings file).

Requirements and their tests (unit):
- "The installer is one POSIX script": `test_it_runs_from_a_pipe_under_dash` (and
  `bash`, parametrized; skip a shell not on PATH, dash is on CI's Ubuntu).
- "An installer without a version refuses": `test_an_unstamped_copy_refuses_and_makes_nothing`.
- "The installer checks Docker before it changes anything":
  `test_no_docker_on_linux_names_docker_engine`, `test_no_docker_on_macos_names_docker_desktop`,
  `test_no_compose_names_the_plugin`, `test_permission_denied_names_the_docker_group`,
  `test_a_stopped_daemon_on_linux_names_systemctl`, each asserting the folder is not made
  and no `sudo` ran.
- "The installer starts Docker Desktop on macOS":
  `test_docker_desktop_is_started_and_waited_for` (fake `docker info` fails twice, then
  answers; a fake `sleep` on PATH returns at once, so no test waits for real).

Steps: write the failing tests; write the skeleton (`main`, `say`, `die`, flag parsing,
`--help`, version, env scrub, Docker); run `uv run pytest tests/test_install_sh.py -n0`;
commit "The Docker installer checks Docker and its own version (LAD-164)".

### Task 2: A fresh install's `.env`

Requirements and tests (unit, with `pty` for questions):
- "A fresh install asks for the workspace": `test_enter_takes_the_home_workspace_and_makes_it`,
  `test_a_relative_workspace_is_asked_again`.
- "A fresh install takes git's identity from the computer":
  `test_the_computers_git_identity_is_taken_unasked`, `test_a_missing_identity_is_asked`.
- "Questions come from the terminal, or their defaults are taken":
  `test_without_a_terminal_the_defaults_are_taken_and_the_identity_warned`.
- "The installer picks a free port": `test_a_taken_port_moves_to_the_next` (the fake `nc`
  answers per port, so the test binds no real port).
- "The installer gives the agents the ssh agent there is": `test_macos_gets_docker_desktops_agent`,
  `test_linux_without_an_agent_says_ssh_is_off`, `test_linux_socket_is_taken_with_its_note`.
- "The installer's folder and its compose project": `test_another_folder_gets_its_project_name`,
  `test_image_is_written`.
- "The installer's .env is the manual way's": `test_every_written_name_is_in_the_compose_header`.
- "The installer installs its own release": `test_the_versions_compose_file_is_downloaded`,
  `test_source_copies_and_downloads_nothing`.

Commit "The Docker installer writes .env for this computer (LAD-164)".

### Task 3: Start, link, opener, phone

- "The shell's LADO and COMPOSE variables do not reach the installer's compose":
  `test_stray_variables_never_reach_compose_and_are_named`.
- "The installer never replaces another folder's LADO": `test_another_folders_container_stops_it`.
- "The installer starts LADO and waits for its link": `test_the_link_is_waited_for`,
  `test_a_server_that_never_answers_shows_the_log_tail` (the fake `sleep` returns at
  once, so the 90 polls of 2 s run in milliseconds; no test-only flag).
- "The installer prints and opens the link": `test_the_link_is_printed_and_opened_on_macos`,
  `test_linux_without_a_display_only_prints`, `test_wsl_opens_windows_browser`,
  `test_no_open`.
- "The phone is asked after its warning, no by default": `test_enter_means_no_after_the_warning`,
  `test_yes_alone_means_no`.
- "The phone's yes publishes LADO under the computer's name": `test_macos_yes_uses_local_host_name`,
  `test_linux_without_avahi_takes_the_address_and_warns`, `test_wsl_takes_windows_name`,
  `test_the_phones_link_and_qr_hint_are_printed`.

Commit "The Docker installer starts LADO and opens its link (LAD-164)".

### Task 4: Reruns

- "A rerun updates an older LADO and keeps its settings": `test_an_update_keeps_the_bak_and_the_users_lines`,
  `test_a_release_candidate_updates_to_its_final`.
- "A rerun of the same version only starts LADO": `test_the_same_version_rewrites_nothing`.
- "The installer never goes back to an older version": `test_a_newer_env_refuses`,
  `test_a_dev_version_refuses`.
- "A rerun keeps the phone's choice unless a flag changes it": `test_phone_added_on_a_rerun`,
  `test_no_phone_removes_both_lines`.
- "Every stop of the installer says what and what to do": `test_a_failed_download_leaves_the_old_files`,
  `test_every_failure_line_starts_lado_install` (collects the stderr of every failure test
  above through a fixture).

Commit "A rerun of the Docker installer updates LADO (LAD-164)".
Then run shellcheck once: `mise exec shellcheck@latest -- shellcheck -s sh docker/install.sh`;
fix what it finds or say in the build report why not.

### Task 5: `install.ps1`

**Files:** Create `docker/install.ps1`, `tests/test_install_ps1.py`.

- "The Windows front is a PowerShell script of its release": `test_the_stamp_and_the_versions_install_sh`,
  `test_the_switches_map_to_the_flags`, `test_it_parses` (`pwsh -NoProfile -Command
  "$null = [System.Management.Automation.Language.Parser]::ParseFile(...)"` reporting
  errors; skipped without `pwsh`), `test_no_powershell_7_only_syntax` (no `?.`, `??`,
  `&&`, `||` outside strings, no ternary).
- "The Windows front checks Docker Desktop first": `test_no_docker_names_docker_desktop`.
- "The Windows front finds or offers Ubuntu in WSL": `test_ubuntu_is_found_and_docker_desktop_skipped`,
  `test_no_ubuntu_offers_wsl_install_and_a_rerun`.
- "The Windows front checks Docker inside Ubuntu": `test_no_integration_names_the_setting`.

Commit "The Windows front of the Docker installer runs it in WSL (LAD-164)".

### Task 6: The release's assets

**Files:** Create `scripts/stamp_installers.py`, `tests/test_stamp_installers.py`; modify
`.github/workflows/release.yml` (job `github-release`), `tests/test_release_workflow.py`.

- "The stamp replaces one placeholder or fails": `test_the_stamp_writes_both_copies`,
  `test_a_missing_or_doubled_placeholder_fails`.
- "The GitHub release carries the installers stamped with its version":
  `test_the_github_release_carries_the_stamped_installers` (the stamp runs with
  `${GITHUB_REF_NAME#v}` before `gh release create`, which names
  `$RUNNER_TEMP/installers/install.sh` and `install.ps1` after `docker/compose.yaml`).

Commit "Each release carries the Docker installers stamped with its version (LAD-164)".

### Task 7: The container test

**Files:** Create `tests/container/test_install.py` (helpers from `container_helpers`:
`PREFIX`, `IMAGE`; the script picks the port; the folder is `tmp_path /
f"{PREFIX}-install"`, so its project `lado-<prefix>-install` carries the prefix the
session's teardown checks).

- AC-1 (real Docker): `test_a_fresh_install_answers_its_link` (`--yes --no-open --version
  <lado.__version__> --source <ROOT>/docker --image <IMAGE> --dir <folder>`, a workspace
  under `tmp_path`; GET of the printed link answers 200).
- AC-8: `test_a_rerun_of_the_same_version_changes_nothing`,
  `test_an_older_env_is_updated_and_keeps_its_lines` (set `LADO_VERSION=0.0.1` and add a
  comment line of the user's; rerun; `compose.yaml.bak`, the line kept, the version).
- AC-7: `test_phone_prints_the_other_devices_link` (`--phone`; `LADO_PUBLIC_HOST` set;
  the output has `From another machine`-derived link).
- Teardown: `docker compose down -v` in the folder.

Run: `make docker`, then `uv run pytest -m container -n0 tests/container/test_install.py`.
Commit "A container test installs LADO with its installer (LAD-164)".

### Task 8: Docs

**Files:** README.md (Install → Docker; Update → Docker), docs/install.md (opening table,
`## Docker` led by the installer, "By hand" around today's steps, "Update the container"
led by the rerun, Windows), docker/compose.yaml's header (one paragraph: the installer
writes this `.env`; its line), docs/release.md (4.5: the RC's install.sh on a Mac and
install.ps1 on Windows, with `--dir /tmp/lado-rc-install` on the Mac so it meets no LADO
of yours), CHANGELOG.md, docs/design/modules.md (the `docker/` line names the
installers), AGENTS.md's `docker/` line (`install.sh`, `install.ps1`).

Tests (`tests/test_docker.py`), one per modified container requirement:
- "The install guide leads with the installer, then compose by hand":
  `test_the_guide_leads_with_the_installer` (+ the kept `Secrets as a step of their own`).
- "The guide and README check the shell's variables first": rework the README test to
  `test_readmes_docker_install_is_the_installer_alone`; the guide's manual way keeps the
  check.
- "An update takes the version's compose.yaml": rework README's update test to the
  installer's line; the header's and guide's manual update tests stay.
- "README and the guide present Docker first, then PyPI": add
  `test_the_guides_systems_name_windows_by_install_ps1`.
- "The stamp replaces one placeholder or fails" (the guide's lines):
  `test_readme_and_guide_use_the_latest_installer_address`.

Commit "README and the install guide lead with the one-line installer (LAD-164)".

### Task 9: Regression run

- `make lint`
- `make test` (report the numbers)
- `uv run pytest -m container -n0 tests/container/test_install.py` after `make docker`
  (or name CI's container cell as the proof if Docker is not available locally)
- `openspec validate docker-installer --strict`, `openspec validate --specs --strict`
- No `web/`, providers or MCP change: no UI, JS or integration run is needed; CI runs the
  rest.
