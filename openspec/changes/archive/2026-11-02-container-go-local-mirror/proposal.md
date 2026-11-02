Task: LAD-178

## Why

Symptom: on PR #203 (LAD-177) CI's job `container (amd64)` (run 41522195315, attempt 1)
failed at `tests/container/test_toolchains.py::test_a_projects_go_is_installed_once_and_kept_in_a_new_container`
with `subprocess.TimeoutExpired` after 600 s: the login shell that runs two `mise install`
of Go 1.23.4 at once (the projects' `.tool-versions`) did not end. Rerunning the failed job
was green; the PR does not touch the image or the toolchains.

Facts checked in this run:

- The test normally takes 12-19 s as a whole (19 s on amd64 in the rerun, 12 s on arm64 in
  the same run): 600 s is a hang, not a slow machine. In the last 100 CI runs it is the only
  such failure (the one other red container job of that sample is another test).
- The cause cannot be read from the failed run: the shell prints mise's logs only after
  `wait`, and the timeout kills `docker exec` first, so the output is lost.
- mise 2026.10 (its HTTP client, `crates/mise-util/src/http.rs`) aborts a request when no
  byte arrives for `http_timeout` (30 s, with `http_retries` = 3), but bounds a whole
  download only by `http_download_timeout` (30 min). A download of the ~70 MB archive from
  dl.google.com that slows to a trickle without stopping outlives the test's 600 s: the
  likeliest cause. Other candidates: the second `mise install` waiting on mise's lock while
  the first hangs, or a request for Go's remote versions.
- mise's Go takes its archive and its `.sha256` from `go.download_mirror`
  (`MISE_GO_DOWNLOAD_MIRROR`, default `https://dl.google.com/go`). Tried in LADO's
  container with mise 2026.10.13: with the mirror set to a `python3 -m http.server` on
  127.0.0.1 holding the two files, two parallel `mise install` succeed in 1.9 s, one
  installs and the other finds it installed, the server's log has exactly one GET of the
  `.sha256` and one of the archive, and nothing else is fetched (`go.repo` pointed at an
  unreachable host was not needed).

Why it is built so: the test (LAD-93) checks the image's promise that a repository's tool
installs through mise without root, once for two agents, and stays on the home volume; it
used the real download because that is what an agent does, and printed the logs at the end
because it expected the installs to end.

Options weighed (the human chose B):

- A: diagnostics and short bounds only: each `mise install` under its own `timeout`, debug
  logs always printed, a short `MISE_HTTP_DOWNLOAD_TIMEOUT`. Cheap, but the test stays at
  the mercy of dl.google.com: a 10-minute hang becomes a 4-minute explained failure.
- B (taken): a local mirror plus the same diagnostics. The test downloads the archive and
  its `.sha256` on the host once, with its own timeouts and checksum check, copies them into
  the container and serves them there; mise installs from that mirror. The whole check
  (two agents at once, one install, kept in a new container) stays; mise's path has no
  network. Long-term cost: a helper of some 30 lines in the test file; a mise release that
  drops `go.download_mirror` or fetches something more from the network fails the test
  loudly with mise's own log.
- C: A plus a retry of the installs on a timeout: against the project's rule of no automatic
  retries inside pytest, and it hides a real hang.

Held against the design principles and ROADMAP.md: the change is test-only; LADO's code,
the image and its neutral core do not change; no silent drop (every failure of the installs
now shows its exit codes and both logs); one source of truth (the Go version stays the test
file's `GO`, the archive's name and checksum come from Go's own files).

## What Changes

- `tests/container/test_toolchains.py`: a session fixture downloads Go's archive for the
  image's architecture and its `.sha256` on the host; the Go test copies them into the first
  container, serves them on the container's loopback and runs both `mise install` with
  `MISE_GO_DOWNLOAD_MIRROR` set to it, each under its own `timeout`, with debug logs that a
  failure always shows; the test also checks that the archive was fetched from the mirror
  exactly once.
- `docs/testing.md`: one sentence on the container tests' Go coming from a local mirror.
- No CHANGELOG line: nothing a user sees changes. No version bump of its own (tests only).
- No delta spec: the container spec's requirement "The image carries mise and keeps its
  data on the home volume" and its scenarios still hold as written; where the archive comes
  from is not part of them.

## Scope

- The Go test of `tests/container/test_toolchains.py` and its helper.

## Out of scope

- The image's mise settings (e.g. a shorter `http_download_timeout` in `docker/mise.toml`):
  it would cut a slow but healthy download of a large tool (a JDK) for the agents of a user
  on a slow link; the flake is the test's dependence on the network, not a defect users met.
- The other container tests that download through mise (Node 20, Python 3.12, an old
  openspec): no failure of theirs has been seen; a mirror for each would grow the task. When
  one flakes it gets its own task.
- A CI cache of the archive (`actions/cache`): the host download is one request per run with
  our own timeout and attempts; a cache adds a ci.yml step and a key to keep in step with
  `GO` for little gain.
- A retry of the installs (option C), above.

## Decisions for the record

- D1. The mirror runs inside the container (`python3 -m http.server` on 127.0.0.1, started
  with `docker exec -d`), not on the host: no host port, no `host-gateway`, nothing differs
  between Docker Desktop and Linux; the image's `python3` is there for every user anyway.
- D2. The host downloads with `urllib` (a socket timeout per read, an overall deadline, at
  most three attempts) and checks the archive against Go's `.sha256` before the test uses
  it, so a broken download fails at the fixture with its own message, not inside mise.
- D3. The architecture comes from the container (`uname -m`: `x86_64` → `amd64`,
  `aarch64` → `arm64`), as the image is built for the machine that runs it; another value
  fails the fixture naming it.
- D4. Each `mise install` runs under `timeout -k 10 240` with `MISE_LOG_LEVEL=debug`, its
  output in its own log file: both end well before the login shell's 600 s, so the shell
  always reaches the `cat` of exit codes and logs, and the assertion message holds them (exit
  124 names a timeout). The mirror's access log goes into the message too.
- D5. The test asserts that the mirror's log has exactly one GET of the archive: it proves
  the install came from the mirror and that the two agents downloaded once.
- D6. The mirror is set only for the two installs; `go build`, `go version` and the second
  container run without it, as an agent would, and a download there would show as a changed
  install folder (the test's existing check).
- D7. Test layer: container (the only layer with the image and mise); the proof is the test
  green locally on the developer's machine (`make docker`, then the test alone with `-n0`)
  and in CI's container cells on amd64 and arm64 of the pull request.

## Impact

- Tests: `tests/container/test_toolchains.py`.
- Docs: `docs/testing.md` (one sentence); CHANGELOG: none.
- Specs: none.
- Version: none of its own (a test fix).
