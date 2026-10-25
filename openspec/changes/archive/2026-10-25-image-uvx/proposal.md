Task: LAD-148

## Why

Symptom: LADO's image has `/usr/local/bin/uv` but no `uvx`. In a fresh container an
agent's `uvx <package>` is `command not found`; where some agent once installed uv through
mise, `uvx` on `PATH` is mise's shim, which fails with `mise ERROR No version is set for
shim: uvx`. So a kit's MCP server or a Python tool started with `uvx` does not start in
the container, and the kit's agent comes up without that server (the commands of MCP
servers are not checked before a start: BACKLOG.md). The live tests in a container hit it
too (Codex reaches LM Studio through litellm, run with `uvx`). On a host, uv's installers
always put `uvx` beside `uv`. Found at the release of 0.43.0rc1, 2026-10-25.

Cause: `docker/Dockerfile` copies one file from the image `ghcr.io/astral-sh/uv`,
`COPY --from=uv /uv /usr/local/bin/uv`. That image ships `/uvx` beside `/uv` (uvx is a
small binary that runs `uv tool run` through the `uv` next to it), and the copy leaves it
out. Since the image was first built (0.39.0) `uv` was only LADO's own installer; the
agents' use of `uvx` was never covered.

Options weighed:

- A (taken): copy `/uvx` too, from the same pinned stage, to `/usr/local/bin/uvx`, beside
  `uv`: one line, the same version and source as `uv` by construction, and `uvx` finds its
  `uv` next to it as on a host. `/usr/local/bin` is before mise's shims on `PATH`, so a uv
  installed through mise does not shadow it.
- B: a script `uvx` that runs `exec uv tool run "$@"`: no second binary, but a second
  piece of code to keep true to uv's own `uvx` (its `--version`, its help, its options
  that `uv tool run` names otherwise); it drifts with every uv update.
- C: tell the agents to run `uv tool run` or install uv through mise: leaves every kit
  whose MCP server says `uvx` broken in the container and puts the image's gap on each
  agent.

## What Changes

- `docker/Dockerfile` copies `/uv` and `/uvx` of the pinned `uv` stage into
  `/usr/local/bin`; the comment above it says why both.
- A unit test of the Dockerfile names a `uv` stage copy that leaves `uvx` out; a container
  test checks that `uvx` answers in an agent's login shell, at `uv`'s version, and runs a
  package.
- docs/install.md ("The repositories' toolchains") names `uvx` beside `uv`; CHANGELOG.md's
  0.43.0 gets a line under "Docker image". A patch-level fix inside 0.43.0 (an RC fix for
  0.43.0rc2): no version bump.

## Scope

- The image's `uvx` and its tests and docs.

## Out of scope

- Checking the commands of a kit's MCP servers before a start (BACKLOG.md's entry): a
  separate task; this change only removes this one missing command.
- Other tools a kit may expect (`pipx`, ...): no kit or test needs them now (only what is
  used).
- The `mise use -g uv@0.13.5` set by hand in the current container: the human's container,
  not the image; it stays harmless, as the image's `uvx` comes first on `PATH`.

## Impact

- Image: `docker/Dockerfile`.
- Tests: `tests/test_docker.py` (unit), `tests/container/test_toolchains.py` (container).
- Docs: `docs/install.md`, `CHANGELOG.md`.
