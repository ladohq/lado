## 1. The smoke cell's install

- [x] 1.1 Unit tests first (layer 1), `tests/test_smoke_ci.py`: the npm stub learns to
  fail its first N installs (a counter file), either by exiting 1 or by writing a CLI
  that prints `Error: Missing optional dependency ...` and exits 1, and records `npm
  uninstall ...` calls. Tests: a broken CLI once, then good: the cell passes, `ran` has
  install, uninstall, install in that order and one `::warning::` line naming the
  provider and `attempt 1 of 3` (AC-1); an install exit 1 once, then good: passes the
  same way (AC-2); a CLI broken three times: red, three installs, two uninstalls, no
  `uv run`, `<cli> --version failed after the install` (AC-3); an install failing three
  times: red, `did not install` (AC-3); a good first attempt: one install, no uninstall,
  no `::warning::` (AC-4). They fail before 1.2.
- [x] 1.2 `scripts/smoke_ci.py`: `run` installs in up to three attempts (a module
  constant), each `npm install` then `<cli> --version`; after a failed attempt but the
  last, `::warning::<provider>: attempt <n> of 3: <what failed>; reinstalling` on stdout,
  then `npm uninstall -g --prefix <local> <package>` (exit not checked). The last
  failure keeps today's messages and exit 1. The module docstring says so. `uv run
  pytest tests/test_smoke_ci.py -n0`.

## 2. The image's build

- [ ] 2.1 Unit test first, `tests/test_docker.py`: each CLI's install line runs
  `/opt/agents/bin/<command> --version` (the command from `PINS`) between its `npm
  install` and `npm cache clean --force` (AC-5); the existing tests of those lines stay
  green.
- [ ] 2.2 `docker/Dockerfile`: the four `RUN` lines gain `&& /opt/agents/bin/<cli>
  --version`; the comment above them says why (npm drops an optional dependency without
  an error). With Docker: `make docker` builds, and the check leaves no new files in
  `/home/lado` of the image (compare `docker run --rm lado:local ls -A /home/lado` with
  the image of `main`); without Docker, say so in the build report and rely on CI's
  container job.

## 3. Docs and checks

- [ ] 3.1 `docs/testing.md`: the smoke cell's sentence (three attempts with the
  `--version` check, the warning, the uninstall) and the image's paragraph (each CLI run
  once at build).
- [ ] 3.2 `make lint`, `make test` (counts in the build report), `openspec validate
  agent-cli-install-check --strict`; CI green, the smoke and both container cells
  included (AC-6).
