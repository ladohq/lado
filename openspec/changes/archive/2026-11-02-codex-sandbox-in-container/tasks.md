## 1. The failing tests

- [x] 1.1 `tests/test_codex.py`: an autouse fixture replaces the probe (the new function of
  2.1) with one that says the sandbox starts, so no unit test runs the real `codex` (CI's
  unit runners have none; this container has one whose sandbox fails). The existing
  `test_permission_modes`, `test_a_worker_in_the_sandbox_may_commit_but_not_change_git_hooks`
  and `test_bypassing_the_sandbox_needs_no_permission_profile` stay green unchanged.
  Done in `tests/conftest.py` (`codex_sandbox`), as `tests/test_runtime.py` and others
  launch Codex agents too. The real-CLI layers take the real probe back
  (`real_clis.isolated`), and the Codex smoke checks its start warned as the real probe
  answered.
- [x] 1.2 `tests/test_codex.py`, requirement "LADO tries Codex's sandbox before it launches a
  Codex agent on Linux": the probe is called with the agent's `CODEX_HOME` after
  config.toml is written (the fake reads it and sees `default_permissions`), for modes
  None and `default` on Linux (`sys.platform` patched); not called for
  `bypassPermissions`, nor on `darwin`. A real probe function test: a fake `codex` script on
  PATH that exits 1 with a bwrap line on stderr gives that line; one that sleeps past the
  timeout (patched short) and a missing `codex` each count as cannot start.
- [x] 1.3 `tests/test_codex.py`, requirement "A Codex agent in LADO's container runs without
  a sandbox that cannot start" and "The container's warning names the agent and the
  cause": `LADO_CONTAINER=1`, the probe fails with `bwrap: No permissions to create a new
  namespace, likely …`: mode `default` gives argv `["codex", "--no-daemon", "-a",
  "on-request", "--sandbox", "danger-full-access"]`, mode None gives `["codex",
  "--no-daemon", "--sandbox", "danger-full-access"]`; config.toml has neither
  `default_permissions` nor `permissions`; `launch.warnings` holds the exact line of D5
  with the agent's name and the bwrap line (only its first line).
- [x] 1.4 `tests/test_codex.py`, requirement "A Codex agent on a host keeps a sandbox that
  cannot start, with a warning": no `LADO_CONTAINER`, the probe fails: argv and config as
  with a working sandbox, and `launch.warnings` holds the host line of D5.
- [x] 1.5 `tests/container/` (marker `container`; a new `test_codex.py` or
  `test_image.py`), requirement "A Codex agent in LADO's container runs without a sandbox
  that cannot start", scenario "A supervisor in the container": first the control,
  `codex sandbox -- true` in the image exits nonzero with `bwrap:` in its stderr (else the
  test fails with a line saying the image's sandbox now starts: re-check LAD-151's cause,
  D7); then a repository and `lado start --provider codex --permission-mode default` with
  a dummy `OPENAI_API_KEY` (a login variable, so the start is not refused): its stderr
  holds `Codex's sandbox cannot start here (bwrap:` and `Codex agent supervisor runs without
  it`; the supervisor's `/proc/<pid>/cmdline` holds `--sandbox` `danger-full-access` and
  `-a` `on-request`; its config.toml has no `default_permissions`. The agent need not reach
  a model. Run: `make docker && make test-container` (CI runs it). In
  `tests/container/test_codex_sandbox.py`; not run in the build (no Docker there): CI's
  container cell runs it.

## 2. The fix

- [x] 2.1 `src/lado/providers/codex.py`: a function (e.g. `_sandbox_error(home, environ)`)
  that runs `codex sandbox -- true` with `CODEX_HOME=<home>` in the agent's environment
  (`spec.environ or os.environ`), timeout 10 s, and returns None on exit 0, else the first
  non-empty line of stderr (or a short reason for a timeout or a missing command). Its
  comment holds the cause of LAD-151 (bubblewrap needs a user namespace; Docker's seccomp
  refuses it; `use_legacy_landlock` refuses in 0.162). 1.2 passes.
- [x] 2.2 `launch_command`: on Linux and in any mode but `bypassPermissions`, after
  config.toml is written, call it; on an error in the container (`update.in_container()`),
  write config.toml again without `default_permissions`/`permissions` and add `--sandbox
  danger-full-access` after the approval flags; on an error elsewhere keep everything; add
  the warning of D5 in either case. 1.3 and 1.4 pass.
- [x] 2.3 Integration and other unit tests that launch a Codex agent
  (`tests/integration/fake_provider.py`, `tests/integration/test_provider_logins.py`,
  `tests/test_runtime.py`): check none of them now runs a real or fake `codex sandbox` with
  a result that changes what they assert; where one does, the fake answers `sandbox` with
  exit 0 or the probe is replaced as in 1.1. Run each changed integration file with
  `-m integration`. None does: the autouse fixture of 1.1 covers the unit tests, and no
  integration test launches a Codex agent; no integration file changed.

## 3. Docs

- [x] 3.1 `docs/install.md`, the Docker part (e.g. under "The agents' variables" or "If
  something goes wrong in Docker"): Codex agents in the container run without Codex's own
  sandbox, because Docker does not allow the user namespaces it needs; the container is
  their boundary, as for every agent there; the start warns so. The Linux part's "If
  something goes wrong": the host warning, why (kernel, AppArmor on Ubuntu 23.10+,
  seccomp), the remedies (allow unprivileged user namespaces for bubblewrap, or
  `bypassPermissions`), with no command that changes system security silently.
- [x] 3.2 `docs/design/agents.md` (Codex's permission modes/sandbox) and
  `docs/design/modules.md` (Codex CLI): the probe, the container's fallback, the host's
  warning, and that it is Linux-only.
- [x] 3.3 CHANGELOG.md, under the `## X.Y.Z (unreleased)` heading of the target branch
  (add it when missing: the patch after the last release), `### Fixed`: **Codex agents run
  shell commands in LADO's container.** Codex's sandbox cannot start in Docker; in the mode
  `default` every command asked "retry without sandbox?". They now run without it there,
  and the start says so.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `openspec validate codex-sandbox-in-container --strict`,
  `openspec validate --specs --strict`; the changed integration files with `-m
  integration`; `make docker && make test-container` for 1.5 if Docker is reachable,
  otherwise CI's container cell on the pull request.
- [ ] 4.2 Manual check on the next release candidate (docs/release.md §4.5), the human's:
  a Codex session in `default` in the container; the start notice shows the warning, and a
  shell command (`git show`) runs with no "retry without sandbox?" question (scenario "A
  shell command in the container", which no automated layer reaches without a model).
  Open: the human's, at the next release candidate.
