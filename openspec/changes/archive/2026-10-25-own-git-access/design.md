## Context

LADO runs git for itself in two modules: `gitcache._git` (kits, skill packs, marketplaces:
`ls-remote --tags`, a pinned clone, a marketplace's clone and fetch) and
`clone._start_git` (`ls-remote --symref` and `clone` of a URL, for `lado start <url>`, the
server's clone jobs, `lado project repo add` and the project page). Both pass
`os.environ`. The agents get more: `agent_env.resolve` lays the outside folder
(`LADO_ENV_DIR`) and the project's layer (`runtime._base_env`: `state.project_variables`
with `project_secrets.read(...).values` over them) over the login shell's environment. In
the image the server's process has `LADO_ENV_DIR=/run/secrets` (Dockerfile `ENV`) and no
`GH_TOKEN`; the system git config makes `gh auth git-credential` github.com's only https
helper, and gh reads `GH_TOKEN` from its environment.

## Decisions

### D1. One function builds the environment of LADO's own git

`agent_env.for_git(project: Mapping[str, str] | None = None) -> dict[str, str]` returns
`{**os.environ, **outside().values, **(project or {})}`, the outside folder read anew by
the same reader (its unused files are not applied, as for agents; no warning line here:
`lado doctor` and each launch already name them). No login shell (proposal, option B).
`gitcache._git` and `clone._start_git` take their environment from it, with the no-prompt
variables (D3) over it, so LADO's own `LADO_*` and the no-prompt values always win.
`TMUX`/`TMUX_PANE` need no dropping: git does not read them.

### D2. One function builds a project's layer

`project_secrets.layer(id) -> dict[str, str]`: the project's plain variables from lado.db
with its secrets over them (today's expression in `runtime._base_env`, moved, not copied).
`runtime._base_env` calls it; so does the clone path. `project_secrets` already imports
`state` and `agent_env`, so no import cycle appears.

### D3. The no-prompt variables live in gitcache

`NO_PROMPT` moves from `clone` to `gitcache` (the lowest git module; `clone` and
`projects._git` use `gitcache.NO_PROMPT`), and `gitcache._git` runs with it too: today it
sets only `GIT_TERMINAL_PROMPT=0`, so an askpass program could still be asked, and without
`LC_ALL=C` git's words are not the English ones the kinds match (D5).

### D4. The project reaches the clone's git calls as an argument

`clone.list_branches(url, project=None)` and `clone.clone(..., project=...)` (which already
takes `project` for the target check) pass `project_secrets.layer(project)` to
`for_git` when a project is given; `_start_git` takes the environment as an argument.
`projects.add_clone` already passes `project=id`. The server: `RemoteAsk.project: str |
None = None`; `clones.remote_info(url, project)` refuses an unknown project before git runs
(`projects.NoSuchProject` → 404, as the other project routes), and the clone job passes its
`project` as today. `web/src/api.ts` `getRemoteBranches(url, project?)` sends `project` only
when given; `ProjectRepos.tsx` gives its project; `Launch.tsx` none. `make web-types`.

### D5. One table of failure kinds for clones and kits

The reason and hint of a kind stay in `clone` (`_reason`, `failure`), which gains the
login hint's choice: a `project` (from `failure(..., project=...)`) gives the project
secret's hint; else an outside folder that is a directory (`os.path.isdir` of
`outside().folder`, so `/dev/null` and a missing folder do not count) gives the folder's
hint; else today's. A new `clone.explain(url, stderr) -> str` returns
`<reason> (<git's line>)` plus `. <hint.line()>` for a known kind, and git's line alone
for `git_failed`. `gitcache`'s network calls (`remote_tags`, `fetch_pinned`'s clone,
`clone_branch`, `refresh`) build their texts with it through a function-level
`from lado import clone` (clone builds on gitcache, as `projects._git` already does), keeping
their own heads (`cannot read the tags of <address>`, `cannot get <address>@<ref>`,
`cannot clone <address>`, `cannot update <folder>`). Their local git calls and their own
refusals (a branch pinned, no such tag) are unchanged.

### D6. Tests run real git against a local repository behind an https URL

No CI job has a token. The tests make git's access depend on the layer under test: the
outside folder (or a project's secret) holds `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0=url.<a
local bare repo>.insteadOf`, `GIT_CONFIG_VALUE_0=https://example.invalid/acme/private`, so
a listing or clone of that https URL reaches the local repository only when git got the
layer, and fails as `unreachable` otherwise. A test that also needs the suite's
no-maintenance entries (`tests/agent_helpers.no_maintenance_env`) numbers its entries after
them. That `GH_TOKEN` reaches gh's helper is proven already
(`tests/container/test_access.py::test_gh_gives_github_its_token`); the container test of
this change proves the server's own git sees `/run/secrets`.

## Risks

- A name in the outside folder now changes LADO's own git (e.g. a `GIT_DIR` file there
  would). Accepted: the folder is the human's; agents already get the same values, and the
  reserved names stay reserved.
- An `HTTPS_PROXY` or `GIT_SSH_COMMAND` in the folder now reaches LADO's git as well: the
  intended effect (the same access as the agents).
