## 1. The fakes

- [x] 1.1 `tests/install_fakes.py`: the fake `open` ignores its first `open_ignored` calls
  (default 0). With `info_after_open` set, the fake `docker info` fails until an `open`
  call that was not ignored, then that many more times. The module docstring names both.
  Check: the existing `tests/test_install_sh.py` passes unchanged.

## 2. The repeat

- [x] 2.1 `tests/test_install_sh.py`: `test_docker_desktop_still_quitting_is_started_again`
  (Darwin, `open_ignored=1`, `info_after_open=2`): the install succeeds, and the `open`
  calls are `["-a", "Docker"]`, then `["-g", "-a", "Docker"]`. It fails before 2.2.
  `test_docker_desktop_that_never_answers_stops` also asserts 60 sleeps and 11 calls of
  `open -g -a Docker` (after sleeps 5, 10, …, 55). Layer: unit, the lowest that runs the
  shell's wait loop. CI has no Docker Desktop for a container test.
- [x] 2.2 `docker/install.sh`, `start_docker_desktop`: after every 5th sleep without an
  answer, and before the timeout, run `open -g -a Docker >/dev/null 2>&1 || true`. The first
  `open -a Docker` with its `die` stays. Check: 2.1 passes, `make test` passes, and the test
  passes under each shell that `tests/test_install_sh.py`'s `shell` fixture runs.

## 3. Docs

- [x] 3.1 `docs/release.md`, the Mac installer check: also run the line right after Docker
  Desktop → Quit, before it has fully quit. It waits, starts Docker Desktop and installs.
- [x] 3.2 `CHANGELOG.md`: a `## 0.46.1 (unreleased)` heading, unless one is already there,
  with an entry under Fixed: the Mac installer now waits for a Docker Desktop that was still
  quitting, instead of stopping after 2 minutes.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `openspec validate docker-desktop-quitting --strict`, and
  a trial archive in a copy (`.lado/sdlc.md`, Checks).
- [ ] 4.2 The human's check on a Mac (3.1's scenario) before the merge.
  Not yet: it needs a Mac with Docker Desktop, which the build's container lacks; the human
  runs it before the merge.
