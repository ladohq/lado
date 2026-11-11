Task: LAD-257

## Why

Symptom: in the manual check of 0.45.0rc1 (finding no. 4), `docker/install.sh` ran on a Mac
while Docker Desktop was still quitting (`docker info` no longer answered). The installer
said it was waiting for Docker Desktop, and after 2 minutes it stopped with "Docker Desktop
did not answer in 2 minutes". A second run, after Docker Desktop had quit fully, passed.
Someone who quits Docker Desktop and runs the installer right away hits the same thing.

Suspected cause: `start_docker_desktop` calls `open -a Docker` once, then only polls
`docker info`. While the quitting app's process is still alive, macOS treats the app as
running, so `open -a` launches nothing new and only activates the app that is quitting.
That app exits, and nothing asks for it again. The cause could not be reproduced here
(Linux container, no Mac). The fix does not depend on it, and the human's check on a Mac
confirms it (docs/release.md).

Options weighed:

- A (taken): during the wait, ask Docker Desktop again with `open -g -a Docker` every 10
  seconds. Once the old process has gone, the next ask starts the app. An ask while Docker
  Desktop is already starting changes nothing, and `-g` keeps its window from jumping to
  the front each time. The wait stays 120 seconds and the messages stay the same.
  Long-term cost: a few lines and one unit test.
- B: before `open`, wait until Docker Desktop's processes are gone (`pgrep`). It cannot tell
  quitting from starting (both have processes and a silent `docker info`), and it ties the
  installer to Docker's internal process names, which change between versions. Rejected.
- C: no change, calling it an artefact of the check's scenario. A user who quits and
  reinstalls right away still fails. Rejected.

The human chose A, a wait that stays at 2 minutes, and no reproduction before the build
(2026-11-11).

## What Changes

- `docker/install.sh`, `start_docker_desktop`: the first `open -a Docker` and its stop when
  the app is missing stay as they are. In the wait loop, after every 5th 2-second sleep
  (every 10 s) without an answer from `docker info`, it runs `open -g -a Docker`, ignoring
  its exit status and output. The loop stays at 60 sleeps (120 s), with the same messages.
- `tests/install_fakes.py`: the fake `open` can ignore its first N calls (setting
  `open_ignored`). The fake `docker info` can answer only after an `open` that was not
  ignored, then after a given number of further fails (setting `info_after_open`).
- `tests/test_install_sh.py`: a test where the first `open` is ignored (Docker Desktop
  quitting) and the installer still finishes, with `open -g -a Docker` among the calls.
  The test for "never answers" also checks that the wait still makes 60 sleeps.
- `docs/release.md`: the Mac installer check adds a run started right after Docker
  Desktop's Quit.
- `CHANGELOG.md`: a line under Fixed.

## Scope

Changed: `docker/install.sh`, `tests/install_fakes.py`, `tests/test_install_sh.py`,
`docs/release.md`, `CHANGELOG.md`. Capability `docker-installer`: the requirement "The
installer starts Docker Desktop on macOS" gains the repeat and a scenario. Nothing under
`src/`. A patch release (a fix).

## Out of scope

- Telling "quitting" from "starting" by Docker Desktop's processes (option B): it is
  unreliable and depends on Docker's internals.
- A longer wait: quitting takes seconds and a start usually less than a minute, so 2
  minutes cover both (the human's decision).
- `install.ps1` and WSL: there the installer does not start Docker Desktop, it tells the
  user to.
- A container test: CI has no Docker Desktop. The wait logic is shell logic and the fakes
  cover it at the unit layer.

## Impact

- Users on macOS: the installer recovers from a Docker Desktop that was still quitting.
  Nothing changes on Linux, WSL or Windows.
