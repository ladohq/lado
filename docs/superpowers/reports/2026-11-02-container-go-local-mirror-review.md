# LAD-178 container-go-local-mirror: review report

Pull request #206 `hotfix/lad-178-container-go-mirror` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `62052190` (= the remote head). The container test
`test_a_projects_go_is_installed_once_and_kept_in_a_new_container` no longer installs Go
from dl.google.com: a session fixture downloads the archive and its `.sha256` on the host
(own timeouts, three attempts, checksum check), the test serves them from a
`python3 -m http.server` on the container's loopback and runs both `mise install` with
`MISE_GO_DOWNLOAD_MIRROR`, each under `timeout -k 10 240` with a debug log that a failure
always shows. Only tests, `docs/testing.md` and openspec changed; no delta spec.

## Rounds

- **Round 1** (`origin/main...62052190`): local precision with a check against the
  design's acceptance criteria, and external 1 of 1 (Claude Code GitHub Action), which read
  `test_toolchains.py` and `docs/testing.md` (not the openspec files, which hold no code).
  No blocking or important findings.

External rounds used: 1 of 1 (the hotfix cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the `go_archive` docstring says it returns a folder; the fixture returns `fetch(arch)` | declined: a one-line fix at the next touch of the file |
| F2 | minor | `download` retries a permanent HTTP error (404) up to three times | declined: at most two extra attempts 2 s apart; the message still names the URL and error |
| E1 | minor | external: `free_port()` picks a port free on the host, while the server listens in the container's network | declined: only LADO listens inside the container, on a port already taken on the host; the wait loop shows a clash with the server's log |
| E2 | — | external: the `.sha256` is copied to the mirror but mise does not fetch it | refuted: the prototype and the developer's run saw exactly one GET of the `.sha256` and one of the archive |

## Checks

- `make lint`: exit 0.
- `openspec validate container-go-local-mirror --strict` valid; tasks 8/8;
  `openspec validate --specs --strict` 56 passed.
- `pytest -m container tests/container/test_toolchains.py`: 11 skipped locally (no Docker
  in LADO's container).
- CI on head `62052190`: all 23 checks pass, among them `container (amd64)`,
  `container (arm64)` and `ci-ok`.
- Not run locally: `make test` (no unit test touched; CI ran them green on 3.10 and 3.13).

## Residual risk

- The container test never ran locally in the image; the happy path is proven only by CI
  on both architectures.
- The failure path in the image (a silent mirror, exit 124, logs printed before 600 s) was
  checked only outside Docker, with the bound cut to 5 s.
- The root cause of the original hang is not confirmed; if the flake returns, mise's logs
  will now name it.
