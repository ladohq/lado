## Context

The human's answers (2026-10-16): the guide leads with compose; `compose.yaml` is a
release asset; GitHub's host keys are in the image; the warning about a folder outside
`LADO_REPOS` is in this task, as on the mockup; Claude Code's login inside the container
comes first and the token second. The human added a requirement: the image holds no
private data, only GitHub's public host keys.

## Decisions

**D1. The guide leads with compose; `docker run` is one short part.** Compose keeps every
setting in `.env`. The update, the way back and a second LADO are already a new
`LADO_VERSION` and `up -d`, and the container tests run them. With `docker run` the whole
command is typed again at every update. What LADO prints in a container about an update
names the image (`update.available_line`) and fits both, so it stays.
Alternatives: `docker run` first (no file to download, but the longest command at every
update); both at the same depth (two ways to keep the same).

**D2. `compose.yaml` is an asset of every GitHub release.** `gh release create` in the
job `github-release` uploads `docker/compose.yaml#compose.yaml` beside `dist/*`. The
guide uses `releases/latest/download/compose.yaml`: one address with no version in it,
the newest final's file. A release candidate's file is on its own release page.
Alternative: a raw link by tag (works now, but the guide's address carries a version the
user must replace). The asset works from the first release after this merge. Until then
the human's check takes the file from the worktree.

**D3. GitHub's host keys are a file in `docker/`, copied to `/etc/ssh/ssh_known_hosts`.**
`docker/ssh_known_hosts` holds GitHub's three published keys, taken from
`https://api.github.com/meta` (`ssh_keys`) and checked against the fingerprints on
docs.github.com ("GitHub's SSH key fingerprints"). It is a file in the repository, so the
build makes no network call for it and a key change shows in a diff.
- Alternative: `StrictHostKeyChecking accept-new` for github.com. It trusts the first key
  it sees, so the first connection can be spoofed. After a rotation it fails until a line
  on the volume is removed by hand.
- Alternative: `ssh-keyscan` at build time. Its first look is not authenticated, and the
  build depends on the network.
The cost: after GitHub rotates its keys (it did in 2023), ssh from the container fails
until a new image ships. The container test (D4) does a real ssh to github.com on every CI
run and daily, so it turns red at once.

**D4. The container test does a real ssh to github.com.** In a container on a new home
volume with no ssh agent, `ssh -T -o BatchMode=yes git@github.com` in `lado`'s login
shell must fail with `Permission denied (publickey)`, never with `Host key verification
failed`. It needs the network, which CI's runners have; with no network it fails, never
skips (the container job's pass rule makes a skip red anyway). A unit test checks the
file: only `github.com` lines and the three key types. It does not pin fingerprints that
the test itself would have to keep up to date: the live ssh is the check.

**D5. One rule for the warning, in the core: `runtime.outside_repos(path) -> str | None`.**
It returns the warning when `update.in_container()` is true, `clone.repos_folder()` gives
a folder, and the path's real path is neither that folder's real path nor below it
(`Path.resolve()`, `is_relative_to`). A path that does not exist is resolved as far as it
goes. It imports `update` and `clone` inside the function: `clone` imports `runtime`, and
the CLI's commands import `update` lazily (`tests/test_lazy_imports.py`). Callers:
- `launch.folder_info` sets `FolderInfo.warning` for the folder as given;
- the clone target's endpoint (`clones.py`) sets `CloneTarget.warning` for the target;
- `runtime.start_session` appends it to `Started.warnings` for the session's root, new
  and resumed alike. `lado start`, the UI and `start_approved_session` already show those
  warnings.
The text is one constant, `runtime.OUTSIDE_REPOS`, with the folder filled in.
Alternatives: a check in the web UI against `GET /api/repos-folder` (a second copy of the
rule, and blind to links and to the CLI); a refusal (the human chose a warning).

**D6. The UI shows the warning as a `field-note warn` line after the check's line.** In
the Folder tab it goes under Where, after `✓ git repository · branch …`. In the Clone tab
it goes under Clone into, after the target's note. It is the same element the provider's
warning uses, so no new style is needed. Start stays as the folder check makes it. The
new fields are optional (`str | None = None`), so an older page ignores them.
`make web-types` refreshes `web/openapi.json` and `web/src/api.gen.ts`.

**D7. The guide repeats only the steps a user runs, and tests keep them equal to the
header.** `tests/test_docker.py` gets `guide_steps(heading)`. It reads the fenced `bash`
blocks of docs/install.md's `## Docker` section under a heading. Tests compare:
- the guide's first start (`mkdir -m 700 secrets`, `docker compose up -d`, `docker compose
  exec lado lado ui --no-open`) with the header's;
- the update with `header_steps("To update, …")`;
- the way back with `way_back()`.
The container tests already run the header's steps, so the guide runs what is tested. The
guide's `.env` block must name every `${VAR}` compose.yaml reads, but `LADO_IMAGE` and
`LADO_SECRETS` (advanced, named in the header). A test asserts that no file of `docs/*.md`,
`docker/` or README.md holds `prune` (docs/research/ and docs/superpowers/ are records). The headers get one line each pointing to the
guide.

**D8. Removal is by name.** The guide removes with these commands:
- `docker compose down`;
- `docker volume rm <project>_home` (`lado_home` for the default project, the
  `COMPOSE_PROJECT_NAME` prefix otherwise; `docker volume ls --filter
  name=<project>_home` shows it first);
- optionally `docker image rm ghcr.io/ladohq/lado:<version>`, which Docker refuses while
  another container uses the image.
It does not use `down --volumes`, so the user sees exactly which volume goes. It runs
nothing global.

**D9. The pitfalls are one subsection, `If something goes wrong`, as the other systems
have.** Each pitfall gives the symptom and the fix:
- Shell variables beat `.env`: `env | grep -E '^(LADO|COMPOSE)_'` and `unset`.
- An older Compose v2 wants `LADO_VERSION` beside `LADO_IMAGE`.
- A git name or email removed from `.env` stays: the global config on the volume.
- All agents of one LADO share its secrets: another LADO, until LAD-80.
- Docker Desktop's ssh socket is shared: the LADO started last owns it, so the other
  needs `docker compose restart`.
- F12: `--user root --cap-drop ALL` does not start; drop one of them.
- F13: an owner change that failed half way is not retried; `docker compose down` and
  `up -d` make a new container, whose first start tries again. The developer checks this
  against `entrypoint.sh` (the marker is in the container's filesystem, not the volume).
- A folder outside the projects folder: the warning.
- `~` in the UI's folder field is `/home/lado`.
- Another git host's key: `docker compose exec lado sh -c 'ssh-keyscan gitlab.com >>
  ~/.ssh/known_hosts'`, said to trust the first answer.

**D10. The version and the CHANGELOG.** The warning is a feature, so this is a minor. It
goes in `0.40.0 (unreleased)`, the minor already open on main. If a 0.40.0 release
candidate is cut before the merge, the line goes under the version open on main at merge
time. Lines: the guide, the asset, the host keys, the warning.

## Risks

- A rotation of GitHub's keys breaks ssh from older images. D3, D4: loud in CI, and fixed
  by a new image.
- The guide's address `latest/download` gives the final's file even when the user runs a
  release candidate. The compose file changes rarely, and a release candidate's page has
  its own.
