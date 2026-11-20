# The container without the host's ssh agent: design

Task: LAD-300. Change: `openspec/changes/container-without-ssh-agent/` (proposal, deltas of
`container`, `docker-installer`, `session-clone`, `git-servers-page`, and `design.md` with
decisions D1–D7). Mockup: the run's `mockup-git-servers.html` (the empty add form with the
chosen placeholder, the first of three; GitHub's token hint; the clone's hint in Docker and
outside). The human's answers: #7451 and #7456 (#7458).

## What the human sees

### Docker

- `LADO_SSH_AGENT` is gone from the installer, `compose.yaml`, the image and the guide. An
  `.env` that still has it starts as before, and the line does nothing: no socket inside, no
  `SSH_AUTH_SOCK`, and neither `docker compose logs lado` nor `lado doctor` says anything
  about it (#7456).
- An agent in the container has no ssh at all: not git over ssh to a host that is no saved
  git server, not `ssh` to another machine (#7451, point 1).
- A saved git server's `git@<host>:` and `ssh://git@<host>/` addresses go over https with
  its token, as they do today.

### The installer

- A fresh install asks nothing about ssh and writes no `LADO_SSH_AGENT`; the notes about
  "your ssh agent" and "git over ssh is off" go.
- A rerun (update or start of the same version) on an `.env` with `LADO_SSH_AGENT` keeps the
  line and adds one note to the end's notes:

  ```
  LADO_SSH_AGENT in .env is no longer used: git goes over https through Settings → Git servers; remove the line once you no longer go back to a version before 0.48.0.
  ```

### Clone hints in the container

For an ssh address, both `Permission denied (publickey)` and `Host key verification failed`:

| Address | Reason | CLI hint | UI |
|---|---|---|---|
| port 22 (or none), host with no saved server | `LADO's container has no ssh key for <host>` | `Add it as a git server with a token:` `lado git-server add https://<host> --token` | `Add <host> as a git server with a token: its git@ addresses then go over https too.` and `Add git server ↗` |
| another port, another user, or a saved host | `LADO's container has no ssh: clone by the repository's https address` | none | none |

So `lado start git@github.com:acme/app.git` with no github.com entry prints:

```
lado: cannot clone git@github.com:acme/app.git: LADO's container has no ssh key for github.com (git@github.com: Permission denied (publickey).)
  Add it as a git server with a token:
    lado git-server add https://github.com --token
```

(the layout of a hint as `runtime.Hint` prints it today). Outside the container the hints
are unchanged. Kits, skill packs and marketplaces of an ssh address (`gitcache.explain`)
get the same text.

### Settings → Git servers

`+ Add server` opens Address empty and focused, placeholder `github.com or
gitlab.example.com`, on any list; the way out of a failed clone still fills in its
address. Typing `github.com` gives `GitHub answers.` and `Make one on its token page with the
scope repo.` as today.

## Decisions for the record

The engineering forks are in `design.md`: D1 every piece of the ssh agent and GitHub's ssh
host keys removed, the ssh client kept; D2 the container learns nothing of the variable; D3
the installer's note on every rerun, the line kept; D4 the clone's two container texts in
`clone.py`; D5 the form's initial value and placeholder; D6 the way back with
`compose.yaml.bak`; D7 tests per layer.

## Tests per requirement

| Requirement (capability) | Layer | Tests |
|---|---|---|
| The container has no ssh (container) | unit + container | `tests/test_docker.py`: compose has no bind with `ssh`, no `LADO_SSH_AGENT`; the Dockerfile has no `ssh-agent`, `ssh_known_hosts`, `/run/lado`; the files are gone; no `SSH_AUTH_SOCK` in `docker/`. `tests/container/test_access.py::test_an_old_ssh_agent_line_changes_nothing`: `.env` with `LADO_SSH_AGENT` naming a socket on the host (a sidecar's or a bound one), started: no `/run/lado/ssh-agent.sock`, `bash -lc 'echo ${SSH_AUTH_SOCK:-none}'` prints `none`, the server's `/proc/<pid>/environ` has none, logs and `lado doctor` have no line with `ssh` |
| ssh address of a saved server (container) | existing | `tests/integration/test_git_server_access.py` (the rewrite of `git@`/`ssh://` to https); container test `test_github_com_takes_the_token_of_its_git_server_alone` stays |
| The root step removes its own way to root first (container) | container | `test_image.py` / `test_access.py`: `sudo -n true` fails, `sudo -n -l` grants nothing |
| compose binds the secrets folder (container) | unit | `tests/test_docker.py` unchanged in behaviour (text only) |
| The headers (container) | unit | `tests/test_docker.py`: the words of the scenario, `no ssh` in both headers, no `LADO_SSH_AGENT` or `SSH_AUTH_SOCK` |
| The image holds no private data (container) | unit | `tests/test_docker.py`: the allowlist is the wheel, `profile.sh`, `entrypoint.sh`, `mise.toml` |
| The installer gives the container no ssh agent (docker-installer) | unit | `tests/test_install_sh.py`: macOS fresh install has no `LADO_SSH_AGENT` and no ssh words; Linux with a socket in `SSH_AUTH_SOCK` has none; an update from 0.47.0 keeps the line and prints the note once; a same-version rerun prints it; an `.env` without it prints no note |
| ssh failure outside the container (session-clone) | unit | `tests/test_clone.py`: the existing tests, `in_container` false |
| In the container: port 22, host not saved (session-clone) | unit + UI e2e | `tests/test_clone.py`: both kinds, scp and `ssh://git@host:22/` forms, reason, hint and `ServerWay("add", "github.com", "https://github.com", …)`; `gitcache.explain` text. `tests/ui/test_launch.py`: a server with `LADO_CONTAINER=1` and a fake ssh failure shows the reason and `Add git server ↗` linking `?add=https://github.com` |
| In the container: other ssh address (session-clone) | unit | `tests/test_clone.py`: port 2222, `alice@host:`, a saved host: the https reason, no hint, no way |
| The add form starts empty (git-servers-page) | UI e2e | `tests/ui/` git servers: an empty list and a list with gitlab.com: Address empty, focused, placeholder; no `answers.` line; `?add=` still fills it |
| The add form checks the address (git-servers-page) | UI e2e | the gitlab.com scenario typed; github.com gives `scope repo` (existing test kept) |

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto` on the changed
files, `uv run pytest -m ui` on the changed files, `make web`, `openspec validate
container-without-ssh-agent --strict`, the trial archive; the container tests run in CI
(`make docker` + `make test-container` locally when Docker is at hand).

## Docs

- `docs/install.md`: the two `.env` examples and the paragraph after them lose
  `LADO_SSH_AGENT`; "GitHub and your git servers": one line that `repo` is the minimum and
  that `read:org` (`gh` on pull requests of an organization's repository) and `workflow`
  (pushing `.github/workflows/`) are added when needed; "git over ssh" rewritten: a saved
  server's ssh addresses go over https with its token; the container has no ssh, to other
  machines neither; for ssh from agents run LADO without Docker; "If something goes wrong":
  the item about another host's key goes; "Go back": to get the host's ssh agent back on a
  version before 0.48.0, put `compose.yaml.bak` back too.
- `docker/compose.yaml` and `docker/Dockerfile` headers: no `LADO_SSH_AGENT`; "The
  container has no ssh: a git server's ssh addresses go over https with its token."
- `docs/design/modules.md` (Docker part, the allowlist and the entrypoint), `docs/testing.md`
  (the container tests), `docs/cli.md` (clone hints), `docs/design/ui.md` (the add form).
- CHANGELOG 0.48.0 (unreleased), group "Changed": **No ssh in LADO's container.** with the
  container having no ssh, to other machines too, `LADO_SSH_AGENT` ignored, the way through
  Settings → Git servers; the add form line under the git servers' items.

## Manual check (in the pull request from the start)

Steps marked **[human]** need the human's token or hand; the agent running the check never
sees a token. Before writing it into the pull request, the developer checks every command
against the code of the version it runs (0.47.0's `compose.yaml` and image, and the
branch's `install.sh`), as the last two checks went wrong on that.

0. `env | grep -E '^(GIT_|GH_|LADO_)'`; `unset` what a previous check left. Snapshot:
   `git config --global --list --show-origin > "$TMPDIR/gitconfig-before.txt" 2>&1`.
1. A fresh clone in a temp folder `D=$(mktemp -d)`: `git clone https://github.com/ladohq/lado
   "$D/lado" && cd "$D/lado" && git checkout <branch>`; `make docker LADO_IMAGE=lado:lad-300`.
2. The version before, in its own folder and compose project: `mkdir "$D/run" "$D/ws" && cd
   "$D/run"`; `curl -fLO
   https://github.com/ladohq/lado/releases/download/v0.47.0/compose.yaml`; `.env` with
   `LADO_VERSION=0.47.0`, `LADO_WORKSPACE=$D/ws`, `LADO_PORT=8793`,
   `COMPOSE_PROJECT_NAME=lado-check-300`, `LADO_SECRETS=./secrets`, `LADO_GIT_NAME`,
   `LADO_GIT_EMAIL`, `LADO_SSH_AGENT=/run/host-services/ssh-auth.sock` (Linux: your
   `$SSH_AUTH_SOCK`); `mkdir -m 700 secrets`. **[human]** `printf %s '<token>' >
   secrets/GH_TOKEN`, a token with `repo`, `read:org` and `workflow` (for `gh` on a pull
   request of an organization's repository). `docker compose up -d`; `docker compose exec
   lado bash -lc 'ssh-add -l'` lists your key.
3. The update to the branch: `sh "$D/lado/docker/install.sh" --dir "$D/run" --version 0.48.0
   --source "$D/lado/docker" --image lado:lad-300 --yes` (check these flags against the
   branch's `install.sh`). Expect: `Updated LADO 0.47.0 → 0.48.0`, the note
   `LADO_SSH_AGENT in .env is no longer used: …`, `.env` still has `LADO_SSH_AGENT`.
4. `docker compose logs lado`: the line `LADO took your GitHub login (GH_TOKEN in
   /run/secrets) into Settings → Git servers: github.com, signed in as <you>.` once, and no
   line about ssh. `docker compose restart lado`; the logs have no second takeover line.
5. `docker compose exec lado bash -lc 'echo ${SSH_AUTH_SOCK:-none}; ls /run/lado
   /etc/ssh/ssh_known_hosts'`: `none`, both missing. `docker compose exec lado lado
   doctor`: no ssh line; github.com's row signed in.
6. In the UI (the link of `docker compose exec lado lado ui --no-open`): Settings → Git
   servers lists `https://github.com`; `+ Add server`: Address empty with the placeholder
   `github.com or gitlab.example.com`; Cancel.
7. New session → Clone from URL `git@github.com:<you>/<a test repository>.git`, provider
   `<CLI>`: branches listed, clone works (over https). Ask the agent to commit, push a
   branch and open a pull request with `gh pr create`: it works and the PR is yours.
8. Clone from URL `git@gitlab.com:<any>/<repo>.git` (no gitlab.com saved): `LADO's container
   has no ssh key for gitlab.com …` and `Add git server ↗`, which opens Settings → Git
   servers with `https://gitlab.com` in Address.
9. The way back: `docker compose down`; in `.env` put `LADO_VERSION=0.47.0` back and drop
   the `LADO_IMAGE` line; `cp compose.yaml.bak compose.yaml`; `docker compose run --rm lado
   sh -c 'cd ~/.lado && rm -f lado.db-wal lado.db-shm && cp backups/lado.db.schema-<N>
   lado.db'` (`<N>` from step 4's logs); `docker compose up -d`. `docker compose exec lado
   bash -lc 'ssh-add -l'` lists your key again; an agent pushes as before.
10. Clean up only this check's things: `docker compose down -v` in `$D/run`, `docker image
    rm lado:lad-300`; `git config --global --list --show-origin >
    "$TMPDIR/gitconfig-after.txt" 2>&1`, `diff` the two snapshots: no change; remove `$D`.

A short repeat after fixes names the steps by these numbers.

Not verified: a Linux host's ssh agent before the update (the human's machine is a Mac);
`install.ps1` on Windows (unchanged, it runs `install.sh`).
