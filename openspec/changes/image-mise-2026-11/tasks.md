## 1. The image

- [x] 1.1 Cherry-pick Dependabot's commit `2766bfe92f31851cb1dc621f842e8c61fab1e2f0` (PR #277):
  `docker/Dockerfile` takes `jdxcode/mise:2026.11.0@sha256:6e05da4113a812cc8ac72b21a38889d019fb0f97df6ce8075c0de98d1cf48cc4`.
  Check: `git show --stat HEAD` names only `docker/Dockerfile`.
- [x] 1.2 `docker/mise.toml`: remove `idiomatic_version_file_ignore_minimum_versions = true`;
  rewrite its comment to say that from mise 2026.11.0 a `go.mod` names a Go only by its
  `toolchain` line, or by an exact `go X.Y.Z` line when it has none, and a minimum `go` line
  (`go 1.23`) is not read. Check: `grep -rn ignore_minimum docker/ src/ docs/install.md`
  finds nothing.

## 2. Tests

- [x] 2.1 `tests/test_docker.py` (unit layer):
  `test_mise_reads_the_version_files_of_go_java_python_and_ruby_alone` asserts
  `"idiomatic_version_file_ignore_minimum_versions" not in settings`, with a comment that mise
  2026.11.0 removed it and warns of it as an unknown field. Check: the test passes with `-n0`.
- [ ] 2.2 `tests/container/test_toolchains.py` (container layer): keep the asserts as they are
  (no `WARN` from `go build` and `go version`, a minimum `go` line not read); adjust a comment
  only if it names the setting. Check: `make docker` and
  `uv run pytest -m container -n0 tests/container/test_toolchains.py` when Docker is available
  here; otherwise the pull request's container cells on amd64 and arm64, and the build report
  says which.

## 3. Docs

- [x] 3.1 `docs/install.md`: the sentence "A `go.mod` names a Go only by its `toolchain` line:
  its `go` line is a minimum and is not read." says a `go.mod` names a Go by its `toolchain`
  line, or by an exact `go` line (`go 1.23.4`) when it has none; a `go` line without the patch
  (`go 1.23`) is a minimum and is not read.

## 4. Pull request and checks

- [x] 4.1 `make lint`, `make test`, `openspec validate --specs --strict`.
- [ ] 4.2 Once the pull request is open, comment on PR #277 that this pull request takes its
  bump with the fix of `docker/mise.toml`, and that Dependabot closes #277 when it is merged;
  do not close #277 by hand.
