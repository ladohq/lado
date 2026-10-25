Task: LAD-115

## Why

Symptom: in LADO's image, Kits → add a kit by the URL of a private repository
(`https://github.com/ladohq/kit-epic.git`) fails with `cannot read the tags of
https://github.com/ladohq/kit-epic.git: fatal: could not read Username for
'https://github.com': terminal prompts disabled`, while the same `lado kits add` in an
agent's terminal of the same container passes. A clone by a private URL from the UI (New
session → Clone, a project's page → Add repository, its branch list) fails the same way,
and `lado project repo add` cannot use a project's `GH_TOKEN` secret at all.

Cause: the variables of the outside folder (`LADO_ENV_DIR`, `/run/secrets` in the image,
where `GH_TOKEN` lives) and a project's variables and secrets reach only the agents'
environment (`agent_env.resolve`, `runtime._base_env`). LADO's own git calls run with the
bare environment of LADO's process: `gitcache._git` (kits, skill packs, marketplaces) and
`clone._start_git` (the listing and the clone of a URL) pass `os.environ`. The process of
`lado server` in the image has `LADO_ENV_DIR=/run/secrets` and no `GH_TOKEN`, so the
image's credential helper of github.com (`gh auth git-credential`) has no token to give.
The server's branch listing (`POST /api/remote-branches`) does not even know which project
asks.

Options weighed:

- A (taken): one core function builds the environment of LADO's own git calls: LADO's
  process environment, the outside folder's variables over it, and, for a listing or clone
  into a project, the project's variables and secrets over those, in the agents' order of
  layers, by the agents' readers, read anew at each call. A few lines in the core, no new
  state; it holds when the projects' kits come (the project's layer is one argument).
- B: give LADO's git the agent's whole environment, the login shell's included. Up to 10 s
  per call (the window lists branches as the URL is typed), and it changes what LADO's git
  sees on every host, far beyond this defect, during a release candidate.
- C: read `/run/secrets` once into the server's environment at its start. A secret added
  later is not seen, a project's secrets cannot be done that way, and every token goes into
  every process the server starts (tmux, `LADO_AGENT_ENV=inherit` agents). Rejected.

## What Changes

- LADO's network git calls (a kit's or skill pack's tags and clone, a marketplace's clone
  and update, the listing and clone of a URL) run with the outside folder's variables over
  LADO's process environment, read anew at each call.
- A listing or clone for a project (`lado project repo add`, the project page's Add
  repository and its branch list) gets the project's variables and secrets over those.
  `POST /api/remote-branches` takes an optional `project`; the project page sends it.
- A login failure on github.com names the access LADO can use: a project's secret for a
  clone into a project, the outside folder's `GH_TOKEN` file when that folder is there.
- A kit's, skill pack's or marketplace's git failure is told by the clone's kinds, with the
  same reason and hint, on one line; LADO's git for kits runs with the clone's no-prompt
  variables (`LC_ALL=C` included, which the kinds need).
- Docs: `docs/design/modules.md`, `docs/design/ui.md`, `docs/marketplaces.md`,
  `docs/install.md`; a CHANGELOG line under 0.43.0's Fixed.

## Scope

`src/lado/agent_env.py`, `src/lado/project_secrets.py`, `src/lado/runtime.py`
(`_base_env`), `src/lado/gitcache.py`, `src/lado/clone.py`, `src/lado/projects.py`
(`add_clone`, `_git`'s `NO_PROMPT`), `src/lado/server/clones.py`, `src/lado/server/app.py`,
`src/lado/server/models.py` (`RemoteAsk`), `web/src/api.ts`, `web/src/ProjectRepos.tsx`,
`web/openapi.json`, `web/src/api.gen.ts`, their tests, `tests/container/test_access.py`,
the docs above, CHANGELOG.md.

## Out of scope

- The login shell's variables for LADO's git (option B): its cost is under option B; the
  process's own environment already has what the human's shell gave `lado start`.
- LADO's local git calls (worktrees, branches, status, the unpushed scan): they use no
  credential.
- The `not_found` hint (`gh auth status`) and the hints of other hosts: unchanged; a token
  that lacks access is a matter of the account, not of where LADO takes the token.
- A project's layer for kits: kits are installed for the whole LADO, not for a project; the
  projects' kits come with the Projects epic.
- New UI: no screen changes, the hint is shown where it is shown today; so no mockup.
- A test against a real private repository: CI has no token; it is a manual check at the
  release candidate (docs/release.md's RC steps).

## Impact

Patch-class fix inside 0.43.0 (unreleased, after 0.43.0rc1): no schema migration, no CLI
or MCP change; one optional field of a server API model (`RemoteAsk.project`), so
`make web-types`. Works for every provider: it is LADO's own git, not an agent's.

## Acceptance

- AC-1: with `GH_TOKEN` (or any access variable) only in the outside folder, a kit's add
  and update, a skill pack's clone, a marketplace's clone and update, and a listing and
  clone of a URL (CLI and UI server) use it, read anew at each call.
- AC-2: a listing and clone into a project (`lado project repo add`, the project page,
  `POST /api/remote-branches` with `project`) use the project's variables and secrets over
  the folder's; one without a project gets none of a project's; an unknown project is 404.
- AC-3: a github.com login failure names the project's secret for a clone into a project,
  the outside folder's `GH_TOKEN` file when that folder is a folder, else `gh auth login`.
- AC-4: a kit's, pack's or marketplace's git failure is told by the clone's kinds, reason
  and hint on one line; one of no known kind keeps git's line.
- AC-5: in LADO's image, the served server lists a remote's branches and `lado kits add`
  adds a kit through a variable only in `/run/secrets` (container test).
- AC-6: `make lint`, `make test`, `make web` and CI green; `openspec validate
  own-git-access --strict` passes.
