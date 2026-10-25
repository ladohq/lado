## 1. uvx in the image

- [ ] 1.1 `tests/test_docker.py`, beside `test_the_image_carries_the_agents_base_tools`
  (unit: the Dockerfile's text, the lowest layer that sees the copy): a test that the
  image's `COPY --from=uv` lines put both `/uv` and `/uvx` into `/usr/local/bin`, with a
  helper that returns what is missing, checked on the real Dockerfile and on a sample
  that copies `/uv` alone (it names `uvx`). Fails before 1.2 (AC-3).
- [ ] 1.2 `docker/Dockerfile`: `COPY --from=uv /uv /uvx /usr/local/bin/` in place of the
  one-file copy, the comment above it saying that uvx runs through the uv beside it and is
  what kits' MCP servers call. 1.1 passes; `make lint`, `make test`.
- [ ] 1.3 `tests/container/test_toolchains.py` (container: only the built image proves
  the binary is there and runs), beside
  `test_the_base_tools_and_openspec_answer_on_a_clean_home`: in a new container on a new
  home volume, `login(c, "command -v uvx")` is `/usr/local/bin/uvx`; `uvx --version`'s
  second field equals `uv --version`'s (AC-1); `uvx --offline --python <the image's
  python3.13> --from /tmp/hello_uv-1.0-py3-none-any.whl hello-uv` (the file's existing
  `wheel()`) prints `uv ok`, and `/opt/uv/tools` holds no `hello` (AC-2). Run with
  `make docker` then `uv run pytest -m container -n0 tests/container/test_toolchains.py
  -k uvx` when Docker is at hand; otherwise say "written, not run" in the build report
  and leave it to CI's container cell.
- [ ] 1.4 Docs: docs/install.md, "The repositories' toolchains", "git, Node.js 22, uv"
  becomes "git, Node.js 22, uv and uvx"; CHANGELOG.md, under `## 0.43.0 (unreleased)` a
  `### Docker image` group (after `### Fixed`, as 0.42.0 has it) with
  `- **uvx works in the image.** MCP servers and tools started with \`uvx\` run in the
  container, at the image's uv version.`
- [ ] 1.5 Regression: `make lint`, `make test`, `openspec validate image-uvx --strict`,
  `openspec validate --specs --strict`; the pull request's CI (container cell green).
