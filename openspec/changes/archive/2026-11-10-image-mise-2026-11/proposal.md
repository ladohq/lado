Task: LAD-268

## Why

Symptom: Dependabot's PR #277 bumps the image's mise from 2026.10.21 to 2026.11.0, and the
container checks go red on amd64 and arm64 (run 42876727522):
`tests/container/test_toolchains.py::test_a_projects_go_is_installed_once_and_kept_in_a_new_container`
finds `mise WARN unknown field in /etc/mise/config.toml:13:1:
settings.idiomatic_version_file_ignore_minimum_versions` on stderr, where it asserts no `WARN`.

Cause: mise 2026.11.0 removes that setting (Breaking Changes, jdx/mise#15266, announced in
2026.8.10). It stops reading minimum versions from `go.mod` altogether: a bare `go 1.23` line
no longer selects a Go; a `toolchain goX.Y.Z` line, or an exact `go X.Y.Z` line when there is
no `toolchain` line, still does. `docker/mise.toml` set it to `true` (LAD-93, the human's
check H2) so that the minimum was not read and mise did not warn of it on every call. With
2026.11.0 the setting does nothing and its own name is the warning.

Checked by hand on 2026-11-10 with the release binaries (linux-arm64) and the image's config:
2026.10.21 with the setting and 2026.11.0 without it pick the same Go in every case:

| Folder | 2026.10.21, setting on | 2026.11.0, no setting |
|---|---|---|
| `go.mod` with `go 1.23` only | none | none |
| `go.mod` with `go 1.23.12` only | 1.23.12 | 1.23.12 |
| `go.mod` `go 1.23.12`, `.go-version` 1.23.4 | 1.23.12 | 1.23.12 |
| `go.mod` `go 1.23`, `.go-version` 1.23.4 | 1.23.4 | 1.23.4 |
| `go.mod` `go 1.23.12` + `toolchain go1.22.5`, `.go-version` 1.23.4 | 1.22.5 | 1.22.5 |

The other breaking changes of 2026.11.0 (`--locked` needs checksums, safe mode no longer trusts
project lockfiles, global environments beside a project `.miserc.toml`) touch nothing the image
configures: `docker/` uses no lockfile, `--locked` or `.miserc.toml`.

Options weighed:

- A (taken): take the bump and drop the setting from `docker/mise.toml`; 2026.11.0 already does
  what it was for. Cost: none lasting; the config holds only settings mise knows.
- B: keep the setting and silence mise's unknown-field warning. Left out: mise has no switch for
  that one warning, and a dead setting in the image's config misleads the next reader.
- C: stay on 2026.10.21 and ignore the bump. Left out: it only defers A, and Dependabot's
  next bump of mise meets the same warning.

## What Changes

- `docker/Dockerfile` takes mise 2026.11.0 by the digest of PR #277 (its commit, cherry-picked).
- `docker/mise.toml` loses `idiomatic_version_file_ignore_minimum_versions`; its comment says
  that from mise 2026.11.0 a `go.mod` names a Go only by its `toolchain` line or an exact `go`
  line.
- `tests/test_docker.py` checks that the setting is gone instead of that it is `true`.
- `docs/install.md`: the sentence on `go.mod` says what mise reads, the exact `go` line too
  (it was read before as well; the sentence left it out).

No rule of the living specs changes, so the change has no delta. Archive it with
`--skip-specs`.

## Scope

In: `docker/Dockerfile`, `docker/mise.toml`, `tests/test_docker.py`, the comment in
`tests/container/test_toolchains.py` if it names the setting, `docs/install.md`. No change under
`src/` or `web/`.

## Out of scope

- Building on PR #277's branch: a push to it stops Dependabot's rebases of it, and its branch
  name is not the project's pattern. This change takes its commit instead; Dependabot closes
  #277 by itself once main carries 2026.11.0, and the pull request of this change says so on
  #277.
- A new container test for an exact `go X.Y.Z` line or the `toolchain` line: mise's own
  behaviour, unchanged by this bump (table above); the existing test already checks that a
  minimum `go` line is not read and gives no `WARN`.
- `docs/research/` and the archived changes that name the setting: records of their time.

## Impact

No release line: an update of the image's pinned mise with no change users see, as Dependabot's
earlier bumps of the image had none; CHANGELOG.md stays as it is, no minor or patch bump of its
own. Neutral core: no provider is involved; every agent CLI in the container uses the same mise.
