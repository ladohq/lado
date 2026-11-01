Task: LAD-158

## Why

Symptom: on PR #182 (LAD-157), CI run 40708216095, the cell `smoke macos-latest codex`
failed in its step "Smoke test" before any test ran. `npm install -g --prefix
~/.local @openai/codex@0.162.0` exited 0 with `added 1 package in 18s`, then `codex
--version` failed: `Error: Missing optional dependency @openai/codex-darwin-arm64.
Reinstall Codex`. `gh run rerun 40708216095 --failed` passed.

Cause: `@openai/codex` is a small JavaScript launcher (`bin/codex.js`); its native binary
comes in one of six `optionalDependencies`, one per system
(`@openai/codex-darwin-arm64` is `npm:@openai/codex@0.162.0-darwin-arm64`). npm treats
an optional dependency that fails to fetch or install as non-fatal: it drops it without
an error and exits 0. The log shows exactly that: one package added where a working
install adds two. So an install can "succeed" with a CLI that does not run; it is npm's
rule, not a defect of LADO, and a rerun fixes it. `scripts/smoke_ci.py run` already
checks `<cli> --version` after the install, so the smoke fails loudly, but on the first
attempt, and each such flake costs a manual rerun. Claude Code, OpenCode and Kilo ship
their native binaries the same way, so any provider can hit it.

The same install, without the check, builds LADO's image: `docker/Dockerfile` runs
`npm install -g --prefix /opt/agents` for each of the four CLIs and never runs one. The
container tests run Claude Code only, so an image whose Codex, OpenCode or Kilo lost its
binary passes CI and could ship in a release.

## What Changes

- `scripts/smoke_ci.py run <provider> <out>`: installing the CLI is up to three
  attempts. An attempt is `npm install -g --prefix ~/.local <package>@<pin>`, then
  `<cli> --version`; it succeeds only when both exit 0. After a failed attempt, but the
  last, the script prints a GitHub warning annotation
  (`::warning::<provider>: attempt <n> of 3: <what failed>; reinstalling`), runs `npm
  uninstall -g --prefix ~/.local <package>` (its exit status not checked) and tries
  again. After the third failed attempt the cell is red as today
  (`<package>@<pin> did not install` or `<cli> --version failed after the install`, exit
  1, no test run). The same for every provider; nothing knows how a package lays out its
  binaries.
- `docker/Dockerfile`: each of the four CLIs' `RUN` lines runs the installed CLI's
  `--version` (`/opt/agents/bin/<cli> --version`) after its `npm install` and before
  `npm cache clean --force`, so a CLI that does not run fails the image's build. No retry
  in the Dockerfile: a red build is rerun as any CI job (`.lado/sdlc.md`, Review traps).
- `docs/testing.md`: the smoke cell's line says the install is up to three attempts with
  the `--version` check; the image's paragraph says each CLI is run once at build.

## Scope

Changed: `scripts/smoke_ci.py` (`run` and its docstring), `tests/test_smoke_ci.py`,
`docker/Dockerfile`, `tests/test_docker.py`, `docs/testing.md`. Capabilities:
`continuous-integration` and `container` gain a requirement each. Nothing under `src/`.

## Out of scope

- Installing Codex's platform package by name (`@openai/codex-darwin-arm64@npm:...`): it
  puts Codex's package layout into CI, breaks when that layout changes, covers one
  provider of four, and a failed fetch still reddens the cell; rejected.
- Relying on `gh run rerun --failed` alone (today's way): a manual step on each flaky
  pull request; rejected.
- The second flake in the task's comments (run 40713637396: the macOS runner never took
  the job, cancelled after 15 minutes with no step run): GitHub's runner queue, which no
  code of LADO reaches; the Review trap's rerun rule covers it (the human's decision,
  2026-11-01).
- A retry inside the Dockerfile: the build fails loudly and is rerun; retry loops in a
  `RUN` line hide the cause in a long layer log.
- A pause between attempts: npm already retries each fetch; a fresh install after the
  uninstall fetches anew.
- The Windows probe: its WSL part runs `smoke_ci.py run` and gets the retry with no
  change of its own.

## Acceptance criteria

- AC-1: A smoke cell whose first install leaves a CLI whose `--version` fails, and whose
  second works, passes: it ran npm install twice and npm uninstall once in between, and
  printed one `::warning::` line naming the provider and attempt 1 of 3.
- AC-2: A smoke cell whose npm install fails on the first attempt and works on the
  second passes the same way.
- AC-3: A smoke cell whose CLI never runs is red after exactly three installs, runs no
  test, and prints `<cli> --version failed after the install`; one whose install always
  fails is red after three installs with `<package>@<pin> did not install`.
- AC-4: A cell that works at once installs once, uninstalls nothing and prints no
  warning (today's tests stay green unchanged in meaning).
- AC-5: Each of the four CLIs' `RUN` lines in `docker/Dockerfile` is `npm install ...
  && /opt/agents/bin/<cli> --version && npm cache clean --force`, the command being its
  `PINS` command (`tests/test_docker.py`); `make docker` builds and the container tests
  pass in CI.
- AC-6: `make lint`, `make test` pass; CI is green, the smoke and the container jobs
  included.

## Impact

- CI only: the smoke cells and the image's build. No API, schema, MCP, CLI or UI change.
- No CHANGELOG.md line (nothing users of LADO see; an image that fails to build ships
  nothing) and no version bump: a patch-level change inside the unreleased version.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a cause shown by the run's log; review
  by precision.
- Root cause: npm's silent drop of an optional dependency that fails to install; fixed by
  checking that the CLI runs and reinstalling, not by knowing a package's layout.
- Three attempts in all: one flake in tens of cells per run; three independent fetches
  make a red cell from this cause rare, and a real breakage (a bad pin) still fails in
  well under a minute more.
- An attempt fails on either a non-zero npm exit or a failing `--version`: both are the
  same kind of fetch flake, and a bad pin fails all three anyway.
- `npm uninstall` before a retry: a reinstall over the same version may keep the tree as
  it is and not fetch the dropped optional package again; the uninstall's own exit
  status is not checked, since the install that follows is what decides.
- The flake is loud though the cell turns green: a `::warning::` annotation shows in the
  run's summary, so a provider that flakes often is seen (no silent drops).
- The image checks each CLI at build without retrying: the build is loud, rerun by the
  CI rule; the human's decision, 2026-11-01.
- Test layer: unit (`tests/test_smoke_ci.py` with its npm stub made to fail N times;
  `tests/test_docker.py` reading the Dockerfile); the image's build in CI's container job.
