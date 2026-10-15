# The projects at the host's path and owner in LADO's image: implementation plan

**Goal:** LADO's image sees the human's projects folder at the host's own path (`LADO_REPOS`)
and runs as the folder owner's uid on a Linux host, so a worker's worktree made in the
container is a working tree on the host and the agents' files are the host user's; `lado
doctor` warns about a repositories folder LADO may not write in.

**Architecture:** `docker/entrypoint.sh` between tini and the server: at a container's first
start it reruns itself as root through a one-shot sudo rule (removed first), matches
`lado`'s uid and gid to `LADO_REPOS`'s owner, moves the home volume, writes `LADO_REPOS`
into `/etc/profile.d/lado-repos.sh` for the agents, and drops to `lado` with `setpriv`;
then it warns about a missing or unwritable folder and execs the command. compose mounts
`LADO_PROJECTS` at itself. git trusts `*`. The container layer tests it with real Docker.

**Tech Stack:** POSIX sh, Dockerfile (BuildKit), Docker Compose v2, Python 3.10+ (pytest,
standard library).

**Spec:** `docs/superpowers/specs/2026-10-15-projects-at-host-path-design.md`,
`openspec/changes/projects-at-host-path/` (design.md D1-D11, deltas `container` and
`repos-folder`).

## Global Constraints

- The image keeps `USER lado`, `ENV LADO_REPOS=/projects`, `/projects` in the image, tini,
  and the `CMD` as it is (`tests/test_docker.py` pins it).
- The entrypoint: `/usr/local/bin/lado-entrypoint` from `docker/entrypoint.sh`, `#!/bin/sh`,
  `set -eu`, no bashisms; `ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/lado-entrypoint"]`.
- The sudo rule: `/etc/sudoers.d/lado-entrypoint`, mode 0440, exactly
  `lado ALL=(root) NOPASSWD:SETENV: /usr/local/bin/lado-entrypoint`; the marker
  `/etc/lado/first-start`. The root phase removes both before anything else.
- Warning lines, verbatim: `lado: warning: LADO_REPOS is not a folder in the container:
  <path>; mount the host's folder at this same path` and `lado: warning: LADO may not
  write in LADO_REPOS <path>`.
- Doctor's line, verbatim: `LADO may not write in LADO_REPOS <path>: <strerror>`, hint
  `give your user write access to it; in LADO's image on Linux, the folder's owner gives
  the container's user its uid`.
- Container tests: marker `container`; every container and volume named with
  `container_helpers.PREFIX` and removed after, also on a failure; `QUIET` env.
- Nothing under `docs/research/` changes.
- Commit messages: a plain sentence ending in `(LAD-69)`; the body says why.

## Review Focus

- The root phase must delete the sudo rule before any step that can fail (Task 2:
  `test_no_way_to_root_is_left` after a normal start; read the script's order).
- `sudo -E` keeps the container's environment for the server (`LADO_PORT`, `LADO_REPOS`,
  `LADO_TELEMETRY` of the tests); `HOME`, `USER`, `LOGNAME` are set back to `lado`'s before
  `setpriv` (Task 2: the server answers on its `LADO_PORT`; `lado ui --no-open` by
  `docker exec` finds its `server.json`, so LADO_HOME is `/home/lado/.lado`).
- `docker stop` still ends the container quickly: tini → sudo (it may stay as a parent) →
  the server; signals must reach the server (Task 2's test times the stop).
- `usermod -u` changes only files the old uid owned: the explicit `chown -R` of the home
  is what moves a volume of another earlier uid (Task 3's recreate test).
- `LADO_REPOS` quoting in the profile file (a path with a space or `'`).
- The doctor's probe file never left behind, also when closing fails.

---

### Task 1: The doctor's write check

**Files:** `src/lado/doctor.py` (`check_repos_folder`), `tests/test_doctor.py`.

- [ ] **Step 1: Tests first.** In `tests/test_doctor.py`:

```python
@pytest.mark.skipif(os.geteuid() == 0, reason="root writes any folder")
def test_a_repositories_folder_lado_may_not_write_in_warns(tmp_path, monkeypatch):
    folder = tmp_path / "repos"
    folder.mkdir(mode=0o555)
    monkeypatch.setenv("LADO_REPOS", str(folder))
    try:
        check = doctor.check_repos_folder()
    finally:
        folder.chmod(0o755)
    assert (check.name, check.level) == ("Repositories folder", doctor.WARN)
    assert check.detail.startswith(f"LADO may not write in LADO_REPOS {folder}: ")
    assert "Permission denied" in check.detail
    assert check.hint.startswith("give your user write access to it")
    assert list(folder.iterdir()) == []


def test_the_write_check_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert doctor.check_repos_folder().level == doctor.OK
    assert list(tmp_path.iterdir()) == []
```

Run: `uv run pytest tests/test_doctor.py -n0 -k "write"`; expected: the first fails (OK
instead of WARN).

- [ ] **Step 2: Implement.** After the `S_ISDIR` check:

```python
    try:
        handle, probe = tempfile.mkstemp(prefix=".lado-doctor-", dir=folder)
    except OSError as error:
        return Check(
            name,
            WARN,
            f"LADO may not write in LADO_REPOS {folder}: {error.strerror or error}",
            "give your user write access to it; in LADO's image on Linux, the folder's "
            "owner gives the container's user its uid",
        )
    os.close(handle)
    os.unlink(probe)
```

(`try/finally` around close and unlink so a failing close still removes the file.) Not
`os.access` (D8). Run the doctor tests: `uv run pytest tests/test_doctor.py -n0`.

- [ ] **Step 3: Commit** `lado doctor warns about a repositories folder it may not write in (LAD-69)`.

### Task 2: The entrypoint, the sudo rule and git's trust

**Files:** new `docker/entrypoint.sh`; `docker/Dockerfile`, `docker/profile.sh`,
`docker/Dockerfile.dockerignore`, `tests/test_docker.py`.

- [ ] **Step 1: Unit tests first** in `tests/test_docker.py`:
  - `test_profile_sets_what_env_sets_for_the_agents`: the expected set loses `LADO_REPOS`;
    `ENV` still has `LADO_REPOS=/projects`.
  - `test_the_entrypoint_runs_under_tini`: `ENTRYPOINT ["/usr/bin/tini", "--",
    "/usr/local/bin/lado-entrypoint"]`; the CMD line unchanged; `USER lado` still there.
  - `test_the_sudo_rule_names_the_entrypoint_alone`: the Dockerfile writes exactly the rule
    line of Global Constraints to `/etc/sudoers.d/lado-entrypoint` with mode 0440 and runs
    `visudo -cf` on it, and makes `/etc/lado/first-start`.
  - `test_git_trusts_every_repository`: `git config --system --add safe.directory '*'`.
  - `test_the_build_context_is_an_allowlist`: `["*", "!dist/lado-*.whl",
    "!docker/profile.sh", "!docker/entrypoint.sh"]`.
  - `test_the_entrypoint_removes_its_way_to_root_first`: in `docker/entrypoint.sh` the
    root branch's first commands are the `rm -f` of the rule and of the marker (read the
    text: their lines come before any `usermod`, `groupmod`, `chown` or `stat`).
  - `test_the_entrypoint_writes_lado_repos_for_the_agents`: it writes
    `/etc/profile.d/lado-repos.sh`.
  Run `uv run pytest tests/test_docker.py -n0`: they fail.

- [ ] **Step 2: `docker/entrypoint.sh`** (D2-D5), roughly:

```sh
#!/bin/sh
# LADO's image: between tini and the command. A container's first start reruns this as
# root through the one-shot sudo rule, which that run deletes first; see design D2.
set -eu
RULE=/etc/sudoers.d/lado-entrypoint
MARK=/etc/lado/first-start
SELF=/usr/local/bin/lado-entrypoint

if [ "$(id -u)" = 0 ]; then
    rm -f "$RULE" "$MARK"
    repos=${LADO_REPOS:-/projects}
    if [ -d "$repos" ]; then
        owner=$(stat -c '%u %g' "$repos")
        uid=${owner% *} gid=${owner#* }
        if [ "$uid" != 0 ] && [ "$uid:$gid" != "$(id -u lado):$(id -g lado)" ]; then
            groupmod -o -g "$gid" lado
            usermod -o -u "$uid" -g "$gid" lado
        fi
    fi
    if [ -n "$(find /home/lado \( ! -user lado -o ! -group lado \) -print -quit)" ]; then
        chown -R lado:lado /home/lado
    fi
    quoted=$(printf '%s' "$repos" | sed "s/'/'\\\\''/g")
    printf "export LADO_REPOS='%s'\n" "$quoted" > /etc/profile.d/lado-repos.sh
    chmod 644 /etc/profile.d/lado-repos.sh
    export HOME=/home/lado USER=lado LOGNAME=lado
    exec setpriv --reuid=lado --regid=lado --init-groups -- "$SELF" "$@"
fi

if [ -e "$MARK" ] && [ "$(id -un 2>/dev/null)" = lado ]; then
    exec sudo -E -n "$SELF" "$@"
fi

repos=${LADO_REPOS:-/projects}
case $repos in
/*)
    if [ ! -d "$repos" ]; then
        echo "lado: warning: LADO_REPOS is not a folder in the container: $repos; mount the host's folder at this same path" >&2
    elif ! probe=$(mktemp "$repos/.lado-write-check.XXXXXX" 2>/dev/null); then
        echo "lado: warning: LADO may not write in LADO_REPOS $repos" >&2
    else
        rm -f "$probe"
    fi
    ;;
esac
exec "$@"
```

  The developer checks `sudo`'s handling of `HOME` under `-E` on Debian 12 and whether it
  stays as the server's parent; signals must reach the server (Task 3 times the stop).

- [ ] **Step 3: Dockerfile.** Add `sudo` to the apt list. After `useradd`, as root:
  `COPY docker/entrypoint.sh /usr/local/bin/lado-entrypoint` (mode 755), the rule
  (`printf '%s\n' 'lado ALL=(root) NOPASSWD:SETENV: /usr/local/bin/lado-entrypoint' >
  /etc/sudoers.d/lado-entrypoint && chmod 0440 ... && visudo -cf ...`), `mkdir -p /etc/lado
  && touch /etc/lado/first-start`, `git config --system --add safe.directory '*'`. The
  `ENTRYPOINT` line of Global Constraints. Header comment: the same-path `docker run`
  (design doc, What the user sees). `docker/profile.sh`: drop `LADO_REPOS` and say in its
  comment that the entrypoint writes it to `lado-repos.sh`. The dockerignore: add
  `!docker/entrypoint.sh`.

- [ ] **Step 4:** `uv run pytest tests/test_docker.py -n0` green; `make docker` builds;
  `make test-container` still green (the old tests run through the entrypoint).

- [ ] **Step 5: Commit** `LADO's image takes the projects folder's owner and trusts its repositories (LAD-69)`.

### Task 3: Compose at the host's path

**Files:** `docker/compose.yaml`, `tests/test_docker.py`, `tests/container/test_image.py`.

- [ ] **Step 1: Tests first.** `tests/test_docker.py`: the projects volume is
  `${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}:${LADO_PROJECTS:?set
  LADO_PROJECTS to your projects folder}` and `environment.LADO_REPOS` is
  `${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}`.
  `tests/container/test_image.py::test_compose_serves_on_lado_port`: also
  `compose.run("exec", "-T", "lado", "lado", "doctor")` has `[ok  ] Repositories folder:
  <tmp_path> (LADO_REPOS)`.
- [ ] **Step 2:** change `docker/compose.yaml` and its header comment (the projects seen at
  their own path).
- [ ] **Step 3:** `uv run pytest tests/test_docker.py -n0`; `make test-container`.
- [ ] **Step 4: Commit** `The compose file mounts the projects at the host's own path (LAD-69)`.

### Task 4: Container tests of the path and the owner

**Files:** `tests/container/container_helpers.py`, `tests/container/conftest.py`,
`tests/container/test_image.py` (the Claude session's setup moved into a helper),
new `tests/container/test_projects.py`.

- [ ] **Step 1: Helpers.** `run_container(name, *args, home=None)`: the home volume
  `home or f"{name}-home"`; `remove_container(name, home=None)` removes that volume unless
  the test keeps it. A fixture `projects_volume` → `make(uid, gid, mode="755")` creates
  `new_name() + "-proj"`, chowns its root through `docker run --rm -u 0 --entrypoint sh -v
  <vol>:/p <image> -c 'chown <uid>:<gid> /p && chmod <mode> /p'`, removes it after.
  `claude_session(container, repo, session)` moved from
  `test_a_claude_session_gets_to_idle_and_knows_the_container`: the fake endpoint, the
  profile lines, `.claude.json` trusting `repo`, `lado start`, waiting for idle.

- [ ] **Step 2: Tests** (`pytestmark = pytest.mark.container`):

```python
def test_a_workers_worktree_works_on_the_host(start, tmp_path):
    # the host folder at its own path, a repository made on the host
    projects = tmp_path / "projects"; app = projects / "app"
    ... git init -b main, a commit, on the host
    port = free_port()
    c = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}",
              "-v", f"{projects}:{projects}", "-e", f"LADO_REPOS={projects}")
    health(port)
    claude_session(c, str(app), "smoke")
    c.python("from lado import runtime; runtime.spawn_worker('smoke', name='w1')")  # signature as in runtime.py
    wt = app / ".lado" / "worktrees" / "smoke" / "w1"
    c.sh(f"cd {wt} && echo hi > hello.txt && git add hello.txt && "
         "git -c user.name=t -c user.email=t@example.com commit -qm hello")
    # on the host
    assert run(["git", "-C", str(wt), "status", "--short"]).returncode == 0
    listing = run(["git", "-C", str(app), "worktree", "list", "--porcelain"]).stdout
    assert str(wt) in listing and "prunable" not in listing
    assert os.stat(wt / "hello.txt").st_uid == os.getuid()
    head = run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()
    obj = app / ".git" / "objects" / head[:2] / head[2:]
    assert os.stat(obj).st_uid == os.getuid()
    # the worker's own environment: the host's path
    environ = c.exec("cat", f"/proc/{agent_pid(c, 'smoke', 'w1')}/environ").stdout.split("\0")
    assert f"LADO_REPOS={projects}" in environ
    assert c.exec("lado", "stop", "--all", check=False).returncode == 0


def test_the_user_takes_the_projects_owner(start, projects_volume):
    vol = projects_volume(2001, 2001)
    c = start(port, ..., "-v", f"{vol}:/srv/projects", "-e", "LADO_REPOS=/srv/projects")
    health(port)
    assert c.exec("id", "-u").stdout.strip() == "2001"
    assert c.exec("sudo", "-n", "true", check=False).returncode != 0
    link = c.exec("lado", "ui", "--no-open").stdout  # docker exec as lado, finds server.json
    assert link.startswith(f"http://127.0.0.1:{port}/?token=")
    t0 = time.monotonic(); docker("restart", "-t", "10", c.name)
    assert time.monotonic() - t0 < 8  # signals reach the server
    health(port); assert c.exec("id", "-u").stdout.strip() == "2001"


def test_recreated_with_another_owner_keeps_the_home(start, projects_volume):
    # first container: projects 2001, home volume H kept; second: projects 2002, home H
    ...
    assert c2.exec("id", "-u").stdout.strip() == "2002"
    assert c2.sh("find /home/lado ! -uid 2002 -print -quit").stdout == ""
    assert not [l for l in c2.exec("lado", "doctor", check=False).stdout.splitlines()
                if l.startswith("[FAIL]")]
    assert c2.exec("lado", "ls", check=False).returncode == 0


def test_owner_0_keeps_1000_and_warns(start, projects_volume):
    vol = projects_volume(0, 0)
    ...
    assert c.exec("id", "-u").stdout.strip() == "1000"
    assert "lado: warning: LADO may not write in LADO_REPOS /srv/projects" in c.logs()


def test_lado_repos_not_mounted_warns(start):
    ... "-e", "LADO_REPOS=/home/me/projects"
    assert ("lado: warning: LADO_REPOS is not a folder in the container: /home/me/projects; "
            "mount the host's folder at this same path") in c.logs()
```

  The `start` fixture gets a way to keep the home volume between two containers of one
  test (both removed at its end). The session teardown's "left behind" check covers the
  `-proj` volumes by their prefix.

- [ ] **Step 3:** `make docker && make test-container` green locally (a Mac: the host-path
  test's owner is the host's user through Docker Desktop's mapping).
- [ ] **Step 4: Commit** `Container tests: a worker's worktree on the host and the projects owner's uid (LAD-69)`.

### Task 5: Docs, the regression run and CI

- [ ] **Step 1:** AGENTS.md: the `docker/` paragraph of Layout (the entrypoint and its
  one-shot root step, the uid, `safe.directory`, `LADO_REPOS` written for the agents to
  `lado-repos.sh`, compose's same-path mount) and the Commands paragraph of the container
  tests (what they check now). CHANGELOG.md 0.39.0: the image line names the projects at
  the host's path and the owner's uid; a line for `lado doctor`'s new warning.
- [ ] **Step 2: Regression:** `make lint`, `make test`, `openspec validate --specs
  --strict`, `openspec validate projects-at-host-path --strict`, `make docker && make
  test-container`.
- [ ] **Step 3:** push; CI's `container (amd64)`, `container (arm64)` and `ci-ok` green;
  the jobs' times in the build report.
- [ ] **Step 4: By hand on a Mac (AC-9):** `make docker`; `docker run` with the projects at
  their path; a session in the UI on a project there; a worker commits; on the host `git
  worktree list` clean, `git -C <worktree> status` works. Screenshots as run artifacts.
- [ ] **Step 5: Commit** `Docs: the image's projects at the host's path and owner (LAD-69)`.
