Task: LAD-151

## Why

Symptom: in LADO's container (Docker Desktop on a Mac, arm64; 0.43.0rc1, 0.43.0rc2 and
0.44.0rc1, Codex CLI 0.162.0) a Codex agent in the permission mode `default` runs no shell
command. Each one fails with `bwrap: No permissions to create a new namespace, likely
because the kernel does not allow non-privileged user namespaces`, and Codex then asks
"retry without sandbox?" in its terminal, for the supervisor and every worker alike. The
agent stands in Needs you until a human answers in its terminal; a worker nobody watches
stands for hours. With `bypassPermissions` everything works.

Cause, checked in this run inside LADO's container (Codex 0.162.0):

- LADO starts Codex in `default` with `-a on-request` and its own permission profile
  (`default_permissions = "lado"`, which extends Codex's `:workspace` with write access to
  the git folders, `providers/codex.py`, `_git_profile`). Both are filesystem-restricted.
- On Linux, Codex 0.162 restricts the filesystem only through bubblewrap, and bubblewrap
  needs a new user namespace. `codex sandbox -- true` fails with the bwrap line above in
  30 ms; `unshare -U true` fails with "Operation not permitted" although
  `kernel.unprivileged_userns_clone` is 1: Docker's default seccomp profile forbids
  unprivileged user namespaces in a container.
- Codex's former way without bubblewrap (feature `use_legacy_landlock`) is deprecated in
  0.162 and refuses: `filesystem-restricted execution requires bubblewrap to isolate
  app-server sockets`.
- `codex sandbox -c sandbox_mode="danger-full-access" -- echo full` runs.

Why it is built so: the Codex provider was written and checked by hand on macOS and on
Linux hosts, where the sandbox works; the permission profile was added so that a worker
can commit inside Codex's sandbox. The container came later, and the manual check of a
release candidate (docs/release.md) is the first place a Codex agent ran there in
`default`.

Options weighed:

- A (taken): when a Codex agent starts with Codex's sandbox (any mode but
  `bypassPermissions`) on Linux, LADO first tries Codex's
  own sandbox (`codex sandbox -- true` with the agent's home). In LADO's container, when it
  cannot start, the agent runs without Codex's sandbox (`--sandbox danger-full-access`, no
  permission profile; approvals stay `on-request`) and the start warns loudly; the container
  is the agent's boundary, as it already is for Claude Code, which has no OS sandbox. On a
  host the sandbox stays and the start warns that every shell command will ask, naming
  docs/install.md. Long-term cost: one probe of 30 ms per Codex agent, pinned by a
  container test that fails when Codex or the image changes the facts.
- B: the container allows user namespaces (a seccomp profile in compose.yaml and the
  `docker run` line). It weakens the container's isolation from the host for every agent,
  cannot be checked on Docker Desktop in CI, bubblewrap may still fail on Docker's masked
  `/proc`, and every existing compose file stays broken, so A would be needed anyway.
- C: only a warning and docs/install.md ("use bypassPermissions"). The agent still stands
  in Needs you.

Held against the design principles and ROADMAP.md: the change stays in
`providers/codex.py` (neutral core; Claude Code, Kilo and OpenCode have no OS sandbox to
lose); no silent drop (the sandbox is dropped only in the container, with a warning at
every start, and kept with a warning on a host); one source of truth (Codex itself answers
whether its sandbox starts, not a list of kernels or Docker versions; LADO's container is
known by `LADO_CONTAINER`, `update.in_container`); only what is used (no new option,
field or UI). ROADMAP's stage 8 (ACP) keeps Codex's approvals as they are, and the cloud
workers (Later) run LADO's image, where this is the behaviour they need.

## What Changes

- A Codex agent started in any mode but `bypassPermissions` (`default`, or no mode) on
  Linux gets a probe of Codex's sandbox before its launch. In LADO's container, a sandbox
  that cannot start makes LADO launch the agent with `--sandbox danger-full-access` and
  without LADO's permission profile, the mode's approvals kept (`-a on-request` for
  `default`), and add a launch warning. On a host the agent launches as before and
  gets a launch warning that each shell command will ask for approval.
- `docs/install.md`: Codex's sandbox in the container and on Linux hosts.
- `docs/design/agents.md` and `docs/design/modules.md` (Codex CLI): the probe and the
  fallback.
- CHANGELOG.md, Fixed: Codex agents in LADO's container run shell commands in `default`.
- A fix: the patch level.

## Scope

- Codex agents on Linux in every mode but `bypassPermissions`: `default` (`-a
  on-request`) and no mode (Codex's own approvals), as both get LADO's permission profile
  and so Codex's sandbox: the probe, the fallback in the container, the warning on a host.
- The launch warnings: `lado start`'s stderr and the UI's start notice for the supervisor,
  loop.log for a worker (where launch warnings already go).
- Tests: unit (the launch with the probe faked), container (the image: the probe fails,
  the agent gets the fallback and the warning).

## Out of scope

- Allowing user namespaces in the container (option B): weaker isolation for every agent,
  and not checkable on Docker Desktop in CI.
- Dropping the sandbox on a host (the human's decision, 2026-11-02): outside the container
  an agent without the sandbox could change anything in the user's home.
- `-a untrusted` instead of `on-request` without the sandbox (the human's decision,
  2026-11-02): it would ask before most commands and keep agents in Needs you.
- macOS and Windows: Codex's sandbox there is not bubblewrap, and it works; no probe.
- A UI element for the fallback: the existing launch warnings say it.

## Decisions for the record

- D1. The probe is Codex's own `codex sandbox -- true`, run with the agent's `CODEX_HOME`
  and environment after its config.toml is written, so it meets the very sandbox and
  profile the agent would get; any nonzero exit, a timeout (10 s) or a failure to run it
  means the sandbox cannot start, and the warning quotes the first line of its stderr. No
  check of kernels, sysctls or Docker settings: Codex is the one source.
- D2. Linux only (`sys.platform == "linux"`): only there does Codex's sandbox need
  bubblewrap; macOS's works, and native Windows is refused by LADO.
- D3. The fallback is `--sandbox danger-full-access` on the argv and no
  `default_permissions`/`permissions` in config.toml (the config is written again without
  them); the approval policy LADO gives stays as it is (`-a on-request` for `default`,
  none for no mode). `--sandbox` on the argv rather than `sandbox_mode` in the config: it is
  visible in the agent's command line and wins over a carried setting.
- D4. "In LADO's container" is `update.in_container()` (`LADO_CONTAINER`), the image's own
  marker, read from the environment LADO runs in.
- D5. The warnings are launch warnings (`base.Launch.warnings`), one line each, naming the
  agent: in the container `Codex's sandbox cannot start here (<first stderr line>): Codex
  agent <name> runs without it, and LADO's container is its only boundary`; on a host
  `Codex's sandbox cannot start here (<first stderr line>): Codex agent <name> asks before
  each shell command; docs/install.md says how to allow it, or use bypassPermissions`.
- D6. The probe runs at each launch of the agent (start, resume, worker spawn), not once
  per session: a container recreated with other settings may answer otherwise.
- D7. Tests: unit for the launch (the probe replaced by a fake that fails or passes, in
  and out of the container, each mode); a container test for the real image, the lowest
  layer that has Docker's seccomp and the real Codex, with a control that
  `codex sandbox -- true` fails in the image, so the test fails rather than passes empty
  once an image or Codex release lets the sandbox start. The smoke layer does not reach the
  container; its default-mode Codex test runs on CI's Linux host as before.

## Impact

- Code: `src/lado/providers/codex.py` (`launch_command`, a probe function).
- Tests: `tests/test_codex.py`, `tests/container/test_image.py` (or a new
  `tests/container/test_codex.py`).
- Docs: `docs/install.md`, `docs/design/agents.md`, `docs/design/modules.md`,
  CHANGELOG.md.
- Specs: a new capability `codex-sandbox`.
- Version: the patch level (a fix; no option, MCP tool, CLI or schema change).
