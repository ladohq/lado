## 1. The mirror

- [ ] 1.1 `tests/container/test_toolchains.py`: a session-scoped fixture `go_archive`
  (host side) that, given the Go architecture, downloads
  `https://dl.google.com/go/go{GO}.linux-{arch}.tar.gz` and its `.sha256` into a
  `tmp_path_factory` folder with `urllib` (timeout per read, overall deadline, at most three
  attempts), checks the archive's sha256 against the file, and returns the folder; reused
  within the session (D2). The architecture comes from the container's `uname -m`
  (`x86_64` → `amd64`, `aarch64` → `arm64`, anything else fails naming it) (D3).
- [ ] 1.2 A helper that copies the two files into a container (`docker cp` into
  `/tmp/go-mirror`, readable by `lado`) and starts `python3 -m http.server <port> --bind
  127.0.0.1` there with `docker exec -d`, its log in `/tmp/go-mirror.log`, and waits until it
  answers; it returns the mirror's URL (D1).

## 2. The Go test

- [ ] 2.1 `test_a_projects_go_is_installed_once_and_kept_in_a_new_container`, requirement
  "The image carries mise and keeps its data on the home volume", scenario "Two agents
  install the same version at once": both installs run with
  `MISE_GO_DOWNLOAD_MIRROR=<mirror>` and `MISE_LOG_LEVEL=debug`, each as
  `timeout -k 10 240 mise install` with its own log; the shell then prints both exit codes,
  both logs and the mirror's log, and the assertion message holds all of it (D4).
- [ ] 2.2 The test asserts that the mirror's log has exactly one GET of the archive (D5).
  Everything else of the test stays: one install folder, `go build` without `WARN`, the shim
  path, `.go-version`, the second container with the same folder (D6). The docstring and the
  `GO` comment say the archive comes from a local mirror and why (the hang of LAD-178).

## 3. Docs

- [ ] 3.1 `docs/testing.md`, the container tests' paragraph: one sentence that the Go test
  installs from a mirror inside the container, fed by one host download per run.

## 4. Checks

- [ ] 4.1 `make lint`; `openspec validate container-go-local-mirror --strict`;
  `openspec validate --specs --strict`.
- [ ] 4.2 Locally with Docker: `make docker`, then
  `uv run pytest -m container -n0 "tests/container/test_toolchains.py::test_a_projects_go_is_installed_once_and_kept_in_a_new_container"`
  passes; once more with the mirror's server stopped by hand before the installs (a local
  edit not committed) to see that the failure ends within 260 s and its message shows the
  exit codes and both mise logs. Without Docker on the machine: say so in the build report.
- [ ] 4.3 On the pull request: CI's `container (amd64)` and `container (arm64)` are green,
  and the Go test takes seconds (the job log's timestamps).
