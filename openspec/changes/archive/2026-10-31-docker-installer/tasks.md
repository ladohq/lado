The plan with each task's tests: `docs/superpowers/plans/2026-10-31-docker-installer.md`.

## 1. install.sh

- [x] 1.1 Skeleton (`main "$@"` last), flags, `--help`, the stamped or `--version` version
  and the unstamped refusal, the shell's `LADO_*`/`COMPOSE_*` scrubbed, Docker's checks
  and Docker Desktop's start on macOS (D3, D4). Check: `tests/test_install_sh.py` with the
  fakes of `tests/install_fakes.py`, under dash and bash.
- [x] 1.2 A fresh install's `.env`: workspace, git identity, port, ssh, folder and project
  name, `--image`, `--source`, the version's `compose.yaml`; questions from `/dev/tty`,
  defaults with `--yes` or no terminal (D5). Check: `tests/test_install_sh.py` (pty).
- [x] 1.3 Another folder's container refused; `docker compose up -d`; the wait for `lado ui
  --no-open`; the link printed and opened; the phone's warning, question, flags and names
  (D4, D7, D8). Check: `tests/test_install_sh.py`.
- [x] 1.4 Reruns: update with `compose.yaml.bak` and only `LADO_VERSION` changed, the same
  version, a refused downgrade or dev version, `--phone`/`--no-phone` on a rerun; files
  moved in place only when complete (D6). Check: `tests/test_install_sh.py`; shellcheck
  once through `mise exec shellcheck@latest`.

## 2. install.ps1

- [x] 2.1 Docker Desktop's check and start, Ubuntu found or offered, Docker inside Ubuntu
  checked, the version's `install.sh` run with the mapped switches, the unstamped refusal
  (D9). Check: `tests/test_install_ps1.py` (text, 5.1 syntax, `pwsh` parser when present).

## 3. Release

- [x] 3.1 `scripts/stamp_installers.py`; the job `github-release` stamps and uploads
  `install.sh` and `install.ps1` beside `compose.yaml` (D2). Check:
  `tests/test_stamp_installers.py`, `tests/test_release_workflow.py`.

## 4. Container

- [x] 4.1 A real install, a rerun of the same version, an update from `0.0.1`, the phone's
  link, with `lado:local`. Check: `make docker`, `uv run pytest -m container -n0
  tests/container/test_install.py`.

## 5. Docs

- [x] 5.1 README (Install → Docker, Update → Docker), docs/install.md (the table, `##
  Docker` led by the installer with the download-read-run way and the PowerShell
  download-and-run form, "By hand", "Update the container", Windows), the compose header,
  docs/release.md 4.5 (the RC's `install.sh` on a Mac with `--dir`, `install.ps1` on
  Windows by the human), docs/design/modules.md and AGENTS.md's `docker/` line,
  CHANGELOG.md (`## 0.44.0 (unreleased)`, Added). Check: `tests/test_docker.py`,
  `tests/test_agents_md.py`.

## 6. Regression

- [x] 6.1 `make lint`, `make test`, the container test, `openspec validate
  docker-installer --strict`, `openspec validate --specs --strict`.
