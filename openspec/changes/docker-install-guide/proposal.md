Task: LAD-83

## Why

LADO's image `ghcr.io/ladohq/lado` is published, but the only instructions for it are the
headers of `docker/compose.yaml` and `docker/Dockerfile`. This is step T8 of the Docker
install plan (docs/research/docker-install-plan.md).

- **No guide.** docs/install.md and README say nothing about Docker. A user does not know
  where to get `compose.yaml`: it is only in the repository.
- **Shell variables beat `.env`.** Twice (LAD-69, LAD-73) the human's check by hand went
  wrong because `LADO_*` variables were left in the shell from an earlier test, and
  compose took them over `.env`. Nothing written warns about it.
- **The first ssh push fails.** A new home volume has no `known_hosts`, and the image
  knows no host key. The agent's first `git push` over ssh to GitHub fails with `Host key
  verification failed` (LAD-76's check by hand). An agent's shell cannot answer ssh's
  question.
- **A session folder the host does not see.** In a container the host sees only the
  projects folder (`LADO_REPOS`). A session started in another folder, e.g.
  `/home/lado/app` (in the container `~` is `/home/lado`; LAD-69's check typed it), lives
  only on the home volume. Neither its files nor the agents' work in it reach the host,
  and nothing says so.

Root cause: the Docker install was built step by step (T1–T10) with its reference in the
headers, and no step wrote the user's path from zero to a working session.

## What Changes

- **A Docker section in docs/install.md, and a link from README's Install.** It leads
  with compose:
  - get `compose.yaml` from the latest release;
  - write `.env` (`LADO_VERSION`, `LADO_PROJECTS`, `LADO_PORT`, `LADO_GIT_NAME`,
    `LADO_GIT_EMAIL`, `LADO_SSH_AGENT`, with the values for a Mac and for Linux);
  - make `secrets/` and put the variables in it (`GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`,
    kits' and providers' keys);
  - start it with one command and open the UI's link with its token;
  - log in to the agent CLIs: Claude Code first by one login inside the container, then
    by a token from `claude setup-token` as the other way; OpenCode and Kilo; Codex not
    yet (T15);
  - ssh: the key registered on GitHub must be in the host's agent;
  - update and go back by `LADO_VERSION`, with the migration's backup;
  - a second LADO beside the first, and how the sessions follow the container;
  - remove it: only its own container and its own volume, by name;
  - the pitfalls (below).
  A short part gives `docker run` and points to the Dockerfile's header. The headers stay
  the reference: the guide links to them and repeats only the steps a user runs.
- **The pitfalls, in the guide.**
  - Shell variables beat `.env`: check `env | grep LADO` and `unset`.
  - An older Compose v2 asks for `LADO_VERSION` also beside `LADO_IMAGE`.
  - A git name or email removed from `.env` stays on the volume.
  - Every agent of one LADO sees all its secrets. Other values need another LADO, until
    profiles (LAD-80).
  - Docker Desktop's ssh agent socket is one for all containers. A second LADO with
    another uid takes it from the first until the first's next start.
  - F12 (LAD-69): `--user root --cap-drop ALL` does not start.
  - F13 (LAD-69): an owner change that failed half way is not tried again; a new
    container tries it again.
  - A session folder outside the projects folder (the warning below).
- **`compose.yaml` on every GitHub release.** The Release workflow attaches
  `docker/compose.yaml` as the asset `compose.yaml`. The guide downloads it from
  `https://github.com/ladohq/lado/releases/latest/download/compose.yaml`.
- **GitHub's host keys in the image.** The Dockerfile copies `docker/ssh_known_hosts`,
  which holds GitHub's published public host keys, to `/etc/ssh/ssh_known_hosts`. The
  first ssh to github.com on a new volume asks nothing, and ssh still refuses a key that
  is not GitHub's.
- **No private data in the image (the human's requirement).** The image holds no key,
  login, password or token of anyone. The only keys in it are GitHub's public host keys.
  The user always works with their own keys and logins, given at run time.
- **A warning for a session folder outside `LADO_REPOS`, in a container only.**
  - The New session window shows it under Where (the folder check) and under Clone into
    (the clone's target). The check mark stays, and Start stays available: a warning, not
    a refusal (mockup `task/lad-83/mockup-outside-repos.html`, variant 2).
  - A start or resume of such a session gives it among its warnings: `lado start` on
    stderr, the UI's `Started.warnings`, the supervisor's `start_session`.
  - Outside a container nothing changes.
- **Tests.**
  - Unit: the guide's commands equal the headers' (start, update, way back), the guide's
    `.env` names every variable compose reads, no `prune` anywhere, the release attaches
    `compose.yaml`, the host keys file holds only github.com's public keys, the warning's
    rule, its fields in the API.
  - Web (vitest): the notes under Where and Clone into.
  - Container: the first `ssh` to github.com on a new home volume fails on the missing
    key, not on the host key.
  - UI e2e: the warning in a container.
- **Version:** a minor, as a feature (the warning). CHANGELOG under `0.40.0 (unreleased)`,
  or under the version open on main when this merges.

## Scope

- `docs/install.md` (a new section `Docker`, the contents list), README.md (Install).
- `docker/compose.yaml` and `docker/Dockerfile` headers (a line pointing to the guide),
  `docker/Dockerfile` (the host keys), a new `docker/ssh_known_hosts`,
  `docker/Dockerfile.dockerignore`.
- `.github/workflows/release.yml` (the asset).
- `src/lado/runtime.py` (the warning's rule and the start's warning),
  `src/lado/server/launch.py`, `src/lado/server/clones.py`, `src/lado/server/models.py`
  (`FolderInfo.warning`, `CloneTarget.warning`), `web/src/Launch.tsx`,
  `web/openapi.json`, `web/src/api.gen.ts`.
- `docs/design/ui.md` (Launch and session control), AGENTS.md (Layout, `docker/`),
  CHANGELOG.md.
- The tests named above.

## Out of scope

- **Host keys of other git hosts** (GitLab, Bitbucket). Only GitHub is asked for; the
  guide shows how to add another host's key on the home volume.
- **A refusal for a folder outside `LADO_REPOS`.** A folder on the volume works; only the
  host does not see it. The human chose a warning.
- **The warning outside a container.** There `LADO_REPOS` is only where suggestions start,
  and every folder is the host's.
- **A launcher with no settings typed into a terminal.** That is T14.
- **Codex's login in the container.** That is T15.
- **Windows and a real Linux host by hand.** That is T11, which follows this guide.
- **Profiles of variables.** That is LAD-80.
- **A `.env` file as a release asset.** The guide writes `.env` in one step. A second file
  to download would be one more thing that can be out of date.
- **`docs/research/docker-install-plan.md` and the kit-epic journal.** lad-52's
  supervisor keeps them.

## Impact

- New behaviour only in a container (`LADO_CONTAINER`): the warning. A native install is
  unchanged.
- The API gets two optional fields (`FolderInfo.warning`, `CloneTarget.warning`); no
  schema, MCP tool or CLI change.
- Every release gets one more asset.
- When GitHub rotates its host keys, ssh to GitHub from the container fails until a new
  image. The container test, run on every CI run and daily, turns red then.
