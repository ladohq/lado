## 1. The environment of LADO's own git

- [x] 1.1 `tests/test_agent_env.py` (unit): `agent_env.for_git()` holds the process's
  variables, an outside folder's file over the same name, and a project mapping over both
  (requirement "One core function builds the environment of LADO's own git calls",
  scenario "The order of the layers"); a file added after a first call is in the next one;
  a file the folder does not give is not in it. Fails before 1.3.
- [x] 1.2 `tests/test_project_secrets_store.py` (unit): `project_secrets.layer`
  gives plain variables with secrets over them; a session's agents still get the same
  layer (the existing `_base_env` tests stay green).
- [x] 1.3 `src/lado/agent_env.py` `for_git` (design D1), `src/lado/project_secrets.py`
  `layer` and `runtime._base_env` calling it (D2); docstrings say who uses them.

## 2. Clones and listings

- [ ] 2.1 `tests/test_clone.py` (unit, real git, design D6): with the outside folder's
  `GIT_CONFIG_*` mapping `https://example.invalid/acme/private` to a local bare repository,
  `clone.list_branches` lists its branches and `clone.clone` clones it; without the folder
  both fail (AC-1). A project's secret holding the same entries makes
  `projects.add_clone("shop", url, None)` and `list_branches(url, project="shop")` pass,
  and a clone without a project fails (AC-2, scenarios "A project's own token", "Another
  project's token is not used").
- [ ] 2.2 `tests/test_clone.py` (unit): `failure("clone", "https://github.com/acme/private",
  <could not read Username>)` gives the three `login_needed` hints of the delta: with
  `project="shop"`, with `LADO_ENV_DIR` naming a folder, with it unset or `/dev/null` (AC-3).
- [ ] 2.3 `src/lado/gitcache.py` `NO_PROMPT` (D3), `src/lado/clone.py` `_start_git` with
  `for_git` and the project's layer, `list_branches(url, project=None)`, `clone` passing its
  project, the login hint's choice in `_reason`/`failure` (D4, D5); `projects._git` takes
  `gitcache.NO_PROMPT`.
- [ ] 2.4 `tests/test_server_clones.py` (unit, TestClient):
  `POST /api/remote-branches` with `project` lists in the project's layer (the 2.1 set-up);
  an unknown project is 404 and runs no git (AC-2).
- [ ] 2.5 `src/lado/server/models.py` `RemoteAsk.project`, `server/clones.py`
  `remote_info(url, project)`, `server/app.py`; `make web-types`, both files committed.
- [ ] 2.6 `web/src` vitest: the project page's Add repository posts `{url, project}` to
  `/api/remote-branches`; New session → Clone still posts `{url}` alone (the existing
  `Launch.test.tsx` check). Then `web/src/api.ts` `getRemoteBranches(url, project?)` and
  `ProjectRepos.tsx` (D4). `make web` passes.

## 3. Kits, skill packs and marketplaces

- [ ] 3.1 `tests/test_gitcache.py` (unit, real git, D6): with the outside folder's
  `GIT_CONFIG_*` mapping an https URL to a local kit repository with a tag `v1.0.0`,
  `gitcache.remote_tags` and `fetch_pinned` pass, and `clone_branch` / `refresh` of a
  marketplace pass; without the folder they fail (AC-1, scenario "A kit added through the
  server" at the core).
- [ ] 3.2 `tests/test_gitcache.py` (unit): a `remote_tags` failure with git's `could not
  read Username` line for a github.com address gives the delta's one-line text with the
  outside folder's hint; a failure of no known kind keeps `<head>: <git's line>` (AC-4).
- [ ] 3.3 `src/lado/gitcache.py` `_git` with `for_git()` and `NO_PROMPT`, its network
  calls' texts through `clone.explain` (D5); the module docstring says so.

## 4. The image

- [ ] 4.1 `tests/container/test_access.py` (container, not run locally: CI runs it): the
  image with a secrets folder holding the D6 `GIT_CONFIG_*` entries for a bare repository
  made inside the container; `POST /api/remote-branches` of the served server lists its
  branches, and `lado kits add` of the mapped https URL of a tagged kit repository passes
  (AC-5). Say "written, not run locally" in the build report.

## 5. Documents

- [ ] 5.1 `docs/design/modules.md` (agent_env, project_secrets, gitcache, clone, the server's
  clones), `docs/design/ui.md` (Clone from URL: the server's git takes the outside folder's
  and, on a project's page, the project's variables), `docs/marketplaces.md` ("A private
  repository"), `docs/install.md` (the folder's `GH_TOKEN` and a project's `GH_TOKEN`
  secret also serve LADO's own clones and kits).
- [ ] 5.2 CHANGELOG.md, 0.43.0 (unreleased), Fixed: a private repository's kit or clone
  in Docker uses the token of `/run/secrets`, and a clone into a project the project's
  secret.

## 6. Checks

- [ ] 6.1 `make lint`, `make test`, `make web` pass; `openspec validate own-git-access
  --strict` passes; CI green on the pull request's last commit, its container job included.
