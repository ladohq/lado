# Secrets and git access in LADO's container Implementation Plan

**Goal:** Agents in LADO's container get variables from a mounted folder of files (no
value in `docker inspect`), a git identity, GitHub over https through `gh`, and the host's
ssh agent without root's group.

**Architecture:** `agent_env` gains one more source, the folder `LADO_ENV_DIR` names,
laid over the login shell's environment inside `resolve()`, the one point every launch and
every kit check goes through. `runtime` turns the files it cannot use into start, resume
and spawn warnings; `doctor` gets a check. The image sets `LADO_ENV_DIR=/run/secrets`;
compose binds `./secrets` there and the ssh socket at `/run/lado/ssh-agent.sock`; the
entrypoint's every-start phase writes git's identity and, through a narrow sudo rule,
gives Docker Desktop's root-owned socket to `lado`; the image's git config makes `gh` the
credential helper for github.com.

**Tech Stack:** Python 3.10+ (standard library), POSIX sh, Dockerfile, Docker Compose,
pytest (unit, integration with the fake agent, container).

**Spec:** `openspec/changes/container-secrets-and-git/` (proposal, `design.md` D1-D14,
delta specs `agent-variables` and `container`) and
`docs/superpowers/specs/2026-10-16-container-secrets-and-git-design.md` (AC-1..AC-13,
manual check).

## Global Constraints

- Texts, verbatim:
  - a file not used: `variable file <name> in <folder> not used: <reason>`; reasons:
    `not a variable name`, `a reserved name`, `not a regular file`, `in a subfolder`
    (named by the subfolder: `variable file <sub>/ in <folder> not used: in a subfolder`),
    `larger than 64 KiB`, `not UTF-8 text`, `cannot be read: <strerror>`;
  - a provider-set name: `variable file <name> in <folder> not used: LADO sets <name> for
    <provider>`;
  - a folder problem: `variable folder <folder> (LADO_ENV_DIR) not used: <reason>`
    (`not an absolute path`, `not a folder`, `cannot be listed: <strerror>`);
  - doctor: check name `Variables from outside`; detail `<folder>: <NAME>, <NAME>` (names
    sorted), `<folder>: none`, `<folder>: no folder`; files not used follow after `; `,
    `<name> not used: <reason>`;
  - git: `lado: warning: git has no user.name or user.email: agents cannot commit; set
    LADO_GIT_NAME and LADO_GIT_EMAIL`;
  - ssh: `lado: warning: lado (uid <uid>) cannot use the ssh agent socket of uid <owner>:
    <reason>`, reasons `ssh-add cannot connect` or `no root to give it to lado
    (no-new-privileges or dropped capabilities)`.
- Reserved names: `HOME USER LOGNAME SHELL PATH PWD OLDPWD SHLVL _ TERM TERM_PROGRAM
  TERM_PROGRAM_VERSION TMUX TMUX_PANE` and every name starting with `LADO_`.
- Limits: 64 KiB per file (`65536` bytes; larger is refused); one trailing `\n` or `\r\n`
  dropped; NUL or invalid UTF-8 is `not UTF-8 text`.
- Paths: `LADO_ENV_DIR=/run/secrets` (image `ENV`), socket `/run/lado/ssh-agent.sock`,
  program `/usr/local/bin/lado-ssh-agent-socket`, rule `/etc/sudoers.d/lado-ssh-agent`.
- No value in an exception, a log line, `lado.db`, the API, a doctor line or the bug
  report. Only `env.json` of the agent's config folder (existing, 600) holds values.
- No schema, MCP, API or UI change. CHANGELOG under `## 0.40.0 (unreleased)`.
- Container tests: only the run's own containers and volumes, named by
  `container_helpers.new_name()`; never `docker system prune` or `docker volume prune`.
  Only fake secrets anywhere in tests.
- Don't touch `docs/research/docker-install-plan.md`.

## Review Focus

- A file `secrets/GH_TOKEN` saved by an editor with a trailing newline and a Windows
  `\r\n`: the value has neither (Task 1, `test_one_trailing_newline_dropped`).
- An editor's swap or backup file (`.GH_TOKEN.swp`, `GH_TOKEN~`): the dotfile is passed
  over silently, `GH_TOKEN~` is warned about as `not a variable name` (Task 1).
- `LADO_ENV_DIR` pointing at a folder `lado` cannot read (a Linux host's 700 folder of
  another uid): the launch goes on with the login shell's environment and the warning
  names the folder (Task 1, `test_folder_cannot_be_listed`).
- A git name with spaces and an apostrophe (`Ann O'Lee`): written as is, never split or
  evaluated (Task 5, container test with that name).
- `docker compose restart` after Docker Desktop made its socket root's again: the
  entrypoint's every-start phase gives it back (Task 6, restart in the container test).

---

### Task 1: The outside folder in agent_env

**Files:**
- Modify: `src/lado/agent_env.py` (new constants, `Outside`, `outside()`, `resolve()`)
- Test: `tests/test_agent_env.py`

**Interfaces:**
- Produces:
  - `agent_env.ENV_DIR_VAR = "LADO_ENV_DIR"`, `agent_env.MAX_VALUE = 65536`,
    `agent_env.RESERVED: frozenset[str]`
  - `class Outside(NamedTuple): folder: str; values: dict[str, str]; unused: list[str]`
    (`unused` holds full lines `variable file … not used: …` and the folder line)
  - `def outside(environ: Mapping[str, str] | None = None) -> Outside` (reads
    `os.environ` when None; `folder == ""` when the variable is unset or empty)
  - `resolve()` unchanged in signature; its result now includes `outside().values`

- [ ] **Step 1: Write the failing tests** in `tests/test_agent_env.py`:

```python
def write(folder, name, data: bytes):
    (folder / name).write_bytes(data)


@pytest.fixture
def outdir(tmp_path, monkeypatch):
    folder = tmp_path / "secrets"
    folder.mkdir()
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    return folder


def test_a_file_is_a_variable(outdir):
    write(outdir, "YOUGILE_API_KEY", b"k-123\n")
    assert agent_env.outside().values == {"YOUGILE_API_KEY": "k-123"}


def test_one_trailing_newline_dropped(outdir):
    write(outdir, "A", b"x\r\n")
    write(outdir, "B", b"y\n\n")
    write(outdir, "C", b" z ")
    assert agent_env.outside().values == {"A": "x", "B": "y\n", "C": " z "}


def test_files_not_used_are_named_with_their_reason(outdir):
    write(outdir, "gh-token.txt", b"x")
    write(outdir, "PATH", b"/evil")
    write(outdir, "LADO_HOME", b"/x")
    write(outdir, "BIG", b"a" * 65537)
    write(outdir, "BIN", b"a\0b")
    write(outdir, ".hidden", b"x")
    (outdir / "sub").mkdir()
    found = agent_env.outside()
    assert found.values == {}
    folder = str(outdir)
    assert sorted(found.unused) == sorted([
        f"variable file BIG in {folder} not used: larger than 64 KiB",
        f"variable file BIN in {folder} not used: not UTF-8 text",
        f"variable file LADO_HOME in {folder} not used: a reserved name",
        f"variable file PATH in {folder} not used: a reserved name",
        f"variable file gh-token.txt in {folder} not used: not a variable name",
        f"variable file sub/ in {folder} not used: in a subfolder",
    ])


def test_no_folder_variable_no_layer(monkeypatch):
    monkeypatch.delenv("LADO_ENV_DIR", raising=False)
    assert agent_env.outside() == agent_env.Outside("", {}, [])


def test_a_missing_folder_is_no_layer_and_no_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path / "none"))
    assert agent_env.outside().values == {} and agent_env.outside().unused == []


def test_a_relative_folder_is_named(monkeypatch):
    monkeypatch.setenv("LADO_ENV_DIR", "secrets")
    assert agent_env.outside().unused == [
        "variable folder secrets (LADO_ENV_DIR) not used: not an absolute path"
    ]


def test_folder_cannot_be_listed(outdir):
    outdir.chmod(0)
    try:
        [line] = agent_env.outside().unused
        assert line.startswith(f"variable folder {outdir} (LADO_ENV_DIR) not used: cannot be listed")
    finally:
        outdir.chmod(0o700)


def test_the_folder_wins_over_the_login_shell(outdir, monkeypatch):
    monkeypatch.setenv("LADO_AGENT_ENV", "inherit")
    monkeypatch.setenv("GH_TOKEN", "old")
    write(outdir, "GH_TOKEN", b"new\n")
    assert agent_env.resolve()["GH_TOKEN"] == "new"


def test_read_anew_at_each_call(outdir):
    assert "NEW_KEY" not in agent_env.outside().values
    write(outdir, "NEW_KEY", b"v")
    assert agent_env.outside().values["NEW_KEY"] == "v"


def test_no_value_in_a_line(outdir):
    write(outdir, "BIN", b"canary-7f3e\0")
    write(outdir, "bad-name", b"canary-7f3e")
    assert "canary-7f3e" not in "\n".join(agent_env.outside().unused)
```

(`test_folder_cannot_be_listed` is skipped when `os.geteuid() == 0`: root reads anyway.)

- [ ] **Step 2: Run** `uv run pytest tests/test_agent_env.py -n0 -k "outside or folder or newline or file or reserved or canary or value" -v`
  Expected: FAIL (`AttributeError: module 'lado.agent_env' has no attribute 'outside'`).

- [ ] **Step 3: Implement** in `src/lado/agent_env.py` (after `SHELL_OWN`):

```python
# A folder of files, one per variable (Docker's /run/secrets form), laid over the login
# shell's environment for each launch; LADO's image sets it (openspec agent-variables).
ENV_DIR_VAR = "LADO_ENV_DIR"
MAX_VALUE = 65536
VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
RESERVED = frozenset({*SHELL_OWN, "HOME", "USER", "LOGNAME", "SHELL", "PATH", "TERM",
                      "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "TMUX", "TMUX_PANE"})


class Outside(NamedTuple):
    """The variables of the outside folder, and the lines naming what was not used."""

    folder: str
    values: dict[str, str]
    unused: list[str]


def outside(environ: Mapping[str, str] | None = None) -> Outside:
    """The folder LADO_ENV_DIR names, read now. Never a value in a line."""
    folder = (os.environ if environ is None else environ).get(ENV_DIR_VAR, "")
    if not folder:
        return Outside("", {}, [])
    where = f"variable folder {folder} ({ENV_DIR_VAR}) not used"
    if not os.path.isabs(folder):
        return Outside(folder, {}, [f"{where}: not an absolute path"])
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name)
    except FileNotFoundError:
        return Outside(folder, {}, [])
    except NotADirectoryError:
        return Outside(folder, {}, [f"{where}: not a folder"])
    except OSError as exc:
        return Outside(folder, {}, [f"{where}: cannot be listed: {exc.strerror}"])
    values, unused = {}, []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        reason, value = _take(entry)
        if reason:
            name = f"{entry.name}/" if reason == "in a subfolder" else entry.name
            unused.append(f"variable file {name} in {folder} not used: {reason}")
        else:
            values[entry.name] = value
    return Outside(folder, values, unused)


def _take(entry: os.DirEntry) -> tuple[str, str]:
    """(reason, "") for a file not used, ("", value) for one used."""
    if entry.is_dir(follow_symlinks=True):
        return "in a subfolder", ""
    if not entry.is_file(follow_symlinks=True):
        return "not a regular file", ""
    if not VARIABLE_NAME.fullmatch(entry.name):
        return "not a variable name", ""
    if entry.name in RESERVED or entry.name.startswith("LADO_"):
        return "a reserved name", ""
    try:
        with open(entry.path, "rb") as file:
            data = file.read(MAX_VALUE + 1)
    except OSError as exc:
        return f"cannot be read: {exc.strerror}", ""
    if len(data) > MAX_VALUE:
        return "larger than 64 KiB", ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 text", ""
    if "\0" in text:
        return "not UTF-8 text", ""
    for end in ("\r\n", "\n"):
        if text.endswith(end):
            return "", text[: -len(end)]
    return "", text
```

(Symbolic links in the folder are followed: Docker's and Kubernetes' secrets are links.)
And in `resolve()`:

```python
def resolve() -> dict[str, str]:
    """The environment for an agent, before LADO's and its provider's variables: the
    login shell's (or the starting process's), then the outside folder's."""
    env = from_shell() if source() == SHELL else dict(os.environ)
    dropped = (*EXCLUDED, *SHELL_OWN)
    base = {k: v for k, v in tmux.without_agent_vars(env).items() if k not in dropped}
    return {**base, **outside().values}
```

Add `import re`. Update the module docstring with one paragraph on the folder.

- [ ] **Step 4: Run** the same command. Expected: PASS. Then `uv run pytest tests/test_agent_env.py -n auto` (all green) and `make lint`.

- [ ] **Step 5: Commit**

```bash
git add src/lado/agent_env.py tests/test_agent_env.py
git commit -m "Agents get the variables of the folder LADO_ENV_DIR names (LAD-76)"
```

### Task 2: Warnings of a start, resume and spawn

**Files:**
- Modify: `src/lado/runtime.py` (`start_session` around `started = Started(...)`,
  `spawn_worker` around `held = ...`, a helper `_outside_warnings`)
- Test: `tests/test_runtime.py`

**Interfaces:**
- Consumes: `agent_env.outside() -> Outside` (Task 1).
- Produces: `runtime._outside_warnings(agent: state.Agent, launch: providers.Launch,
  *, files: bool) -> list[str]`.

- [ ] **Step 1: Write the failing tests** (the module's existing fixtures for a recorded
  start: tmux replaced by the recorder, `LADO_AGENT_ENV=inherit`; follow the nearest test
  of `Started.warnings`):

```python
def test_a_start_names_the_files_not_used(started_session, tmp_path, monkeypatch):
    folder = tmp_path / "secrets"
    folder.mkdir()
    (folder / "PATH").write_text("/x")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    started = started_session()
    assert f"variable file PATH in {folder} not used: a reserved name" in started.warnings


def test_a_provider_set_name_keeps_lados_value(started_session, tmp_path, monkeypatch, fake_launch_env):
    # fake_launch_env: the fake provider's Launch.env holds {"FAKE_CONFIG": "lado's"}
    folder = tmp_path / "secrets"
    folder.mkdir()
    (folder / "FAKE_CONFIG").write_text("mine")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    started = started_session()
    assert (f"variable file FAKE_CONFIG in {folder} not used: LADO sets FAKE_CONFIG for fake"
            in started.warnings)


def test_a_spawn_names_only_provider_set_names(...):
    # a reserved file and a provider-set file; spawn_worker(warnings=w): only the latter
    ...
```

  Write the third test in full in the module's style: the folder holds `PATH` and
  `FAKE_CONFIG`; after `runtime.spawn_worker(..., warnings=w)` `w` holds the
  `LADO sets FAKE_CONFIG for fake` line and no `PATH` line. If the module has no fixture
  for a provider's `Launch.env`, add `fake_launch_env` in `tests/conftest.py` by
  monkeypatching the fake provider's `launch` to return `env={"FAKE_CONFIG": "lado's"}`.

- [ ] **Step 2: Run** `uv run pytest tests/test_runtime.py -n0 -k "files_not_used or provider_set or only_provider" -v`
  Expected: FAIL.

- [ ] **Step 3: Implement** in `runtime.py`:

```python
def _outside_warnings(
    agent: state.Agent, launch: providers.Launch, *, files: bool
) -> list[str]:
    """The outside folder's lines for one launch: its files not used (`files`: a
    session's start or resume only, as the folder is the container's), and each of its
    names LADO or the provider sets for this launch, which keep LADO's value."""
    found = agent_env.outside()
    lines = list(found.unused) if files else []
    ours = {**providers.agent_env(agent), **launch.env}
    lines += [
        f"variable file {name} in {found.folder} not used: LADO sets {name} for {agent.provider}"
        for name in sorted(found.values.keys() & ours.keys())
    ]
    return lines
```

  In `start_session`, after `started.warnings += launch.warnings`:
  `started.warnings += _outside_warnings(agent, launch, files=True)`.
  In `spawn_worker`, extend `held`: `held = launch.warnings +
  _outside_warnings(agent, launch, files=False) + _first_hook_blocker(...)`.

- [ ] **Step 4: Run** the command again (PASS), then `uv run pytest tests/test_runtime.py -n auto`.

- [ ] **Step 5: Commit**

```bash
git add src/lado/runtime.py tests/test_runtime.py tests/conftest.py
git commit -m "A start names the variable files it does not use (LAD-76)"
```

### Task 3: lado doctor's check and the bug report

**Files:**
- Modify: `src/lado/doctor.py` (`check_outside`, `run_checks`, `report`)
- Test: `tests/test_doctor.py`, `tests/test_bug_report.py` (whichever covers
  `doctor.report`)

**Interfaces:**
- Consumes: `agent_env.outside()`.
- Produces: `doctor.check_outside() -> Check | None` (None when `LADO_ENV_DIR` is unset
  or empty), placed after `check_repos_folder()` in `run_checks`.

- [ ] **Step 1: Failing tests**:

```python
def test_outside_lists_names_and_files_not_used(tmp_path, monkeypatch):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "YOUGILE_API_KEY").write_text("canary-1")
    (folder / "GH_TOKEN").write_text("canary-2")
    (folder / "a-b").write_text("x")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    check = doctor.check_outside()
    assert check.level == doctor.WARN
    assert check.detail == f"{folder}: GH_TOKEN, YOUGILE_API_KEY; a-b not used: not a variable name"
    assert "canary" not in check.detail + check.hint


def test_outside_ok_none_and_no_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path))
    assert (doctor.check_outside().level, doctor.check_outside().detail) == (doctor.OK, f"{tmp_path}: none")
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path / "x"))
    assert (doctor.check_outside().level, doctor.check_outside().detail) == (doctor.INFO, f"{tmp_path / 'x'}: no folder")
    monkeypatch.delenv("LADO_ENV_DIR")
    assert doctor.check_outside() is None


def test_the_report_has_no_variable_name(tmp_path, monkeypatch):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "SECRET_NAME_X").write_text("canary-3")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    text = doctor.report(doctor.system_info(), None)
    assert "SECRET_NAME_X" not in text and "canary-3" not in text
```

  (Use the signature of `doctor.report` and `system_info` as the module has them; if
  the report lists checks by name, it shows `Variables from outside: 1 variable`.)

- [ ] **Step 2: Run** `uv run pytest tests/test_doctor.py -n0 -k outside -v`; FAIL.

- [ ] **Step 3: Implement**:

```python
def check_outside() -> Check | None:
    """The outside folder (LADO_ENV_DIR): the names it gives agents, never a value."""
    if not os.environ.get(agent_env.ENV_DIR_VAR):
        return None
    name = "Variables from outside"
    found = agent_env.outside()
    if found.unused and not found.values and found.unused[0].startswith("variable folder"):
        return Check(name, WARN, found.unused[0])
    if not os.path.isdir(found.folder):
        return Check(name, INFO, f"{found.folder}: no folder")
    names = ", ".join(sorted(found.values)) or "none"
    detail = f"{found.folder}: {names}"
    if found.unused:
        prefix = f"variable file "
        short = [line[len(prefix):].replace(f" in {found.folder} ", " ") for line in found.unused]
        return Check(name, WARN, f"{detail}; " + "; ".join(short))
    return Check(name, OK, detail)
```

  and in `run_checks`, `outside = check_outside()` with `*([outside] if outside else [])`
  after the repositories folder. In `report`, if it prints checks, replace this check's
  detail by the count (`<n> variable(s)`); otherwise leave `report` as it is and keep the
  test as a guard.

- [ ] **Step 4: Run** (PASS), `uv run pytest tests/test_doctor.py tests/test_bug_report.py -n auto`, `make lint`.

- [ ] **Step 5: Commit** `git commit -m "lado doctor names the variables from outside (LAD-76)"` with the three files.

### Task 4: Integration: a worker and a kit's MCP server get the variable

**Files:**
- Create: `tests/integration/test_outside_variables.py`
- Test helpers: `tests/agent_helpers.py` (existing session start and polling; a folder kit
  as other integration tests make one — grep `kits add` or `mcp:` in
  `tests/integration/` and follow that kit's layout)

- [ ] **Step 1: Write the tests** (marker `integration`; the fake agent; `LADO_ENV_DIR`
  set in the test's environment, which `lado start` and the session loop inherit):
  - `test_a_worker_gets_the_folders_variable`: folder with `OUT_KEY` = `v-1`; start a
    fake session; the supervisor's fake agent runs `spawn_worker`; the worker's
    `seen.json` / process environment (as the module's other env tests read it) has
    `OUT_KEY=v-1`; then write `OUT_KEY2`, spawn a second worker: it has `OUT_KEY2`, the
    first does not.
  - `test_a_kit_needing_the_variable_starts`: a folder kit whose supervisor's MCP server
    has `env: {KEY: "${OUT_KIT_KEY}"}` (its command: the fake agent's harmless MCP server
    or `true` as the module's kit tests use); with the file the start succeeds; without
    it `lado start` exits 1 naming `OUT_KIT_KEY`.
  - `test_no_value_in_lados_logs`: after the first test's run, `hooks.log`, `loop.log`,
    `errors.jsonl` (when present) and `lado log` output do not contain `v-1`.

- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_outside_variables.py -v`.
  Expected: PASS (Tasks 1-2 make it pass; if it fails, the failure is a real gap: fix in
  the code of Tasks 1-2).

- [ ] **Step 3: Commit** `git commit -m "Integration tests of the variables from outside (LAD-76)"`.

### Task 5: The image: secrets folder, git identity, gh for https

**Files:**
- Modify: `docker/Dockerfile`, `docker/compose.yaml`, `docker/entrypoint.sh`,
  `.gitignore` (`docker/secrets/`)
- Test: `tests/test_docker.py`

- [ ] **Step 1: Failing unit tests** in `tests/test_docker.py`:

```python
def test_the_image_reads_the_secrets_folder():
    assert env()["LADO_ENV_DIR"] == "/run/secrets"
    assert "LADO_AGENT_ENV" not in env()


def test_compose_binds_the_secrets_folder_read_only(compose):
    [mount] = [v for v in compose["services"]["lado"]["volumes"]
               if isinstance(v, dict) and v.get("target") == "/run/secrets"]
    assert mount["source"] == "${LADO_SECRETS:-./secrets}"
    assert mount["read_only"] is True
    assert mount["bind"]["create_host_path"] is False


def test_compose_passes_the_git_identity_and_nothing_secret(compose):
    environment = compose["services"]["lado"]["environment"]
    assert environment["LADO_GIT_NAME"] == "${LADO_GIT_NAME:-}"
    assert environment["LADO_GIT_EMAIL"] == "${LADO_GIT_EMAIL:-}"
    assert set(environment) == {"LADO_PORT", "LADO_REPOS", "LADO_GIT_NAME", "LADO_GIT_EMAIL"}


def test_gh_is_gits_credential_helper_for_github():
    run = [line for line in lines() if "credential.https://github.com.helper" in line]
    assert run, "no gh credential helper"
    joined = " ".join(run)
    assert "--system" in joined and "!/usr/bin/gh auth git-credential" in joined


def test_the_entrypoint_writes_git_identity_every_start():
    text = (DOCKER / "entrypoint.sh").read_text()
    after_root = text[text.index('if [ -e "$MARK" ]'):]
    assert 'git config --global user.name "$LADO_GIT_NAME"' in after_root
    assert 'git config --global user.email "$LADO_GIT_EMAIL"' in after_root
    assert "lado: warning: git has no user.name or user.email: agents cannot commit; set LADO_GIT_NAME and LADO_GIT_EMAIL" in text
```

- [ ] **Step 2: Run** `uv run pytest tests/test_docker.py -n0 -v`; the new ones FAIL.

- [ ] **Step 3: Implement**:
  - Dockerfile, the `safe.directory` RUN becomes:
    ```dockerfile
    # git trusts every repository (git 2.39 has no `<path>/*` form, and the container has
    # one user), and gets github.com's https credentials from gh: GH_TOKEN or gh's own
    # login on the home volume (what `gh auth setup-git` writes).
    RUN git config --system --add safe.directory '*' \
     && git config --system credential.https://github.com.helper '' \
     && git config --system --add credential.https://github.com.helper '!/usr/bin/gh auth git-credential'
    ```
  - Dockerfile's final `ENV` gets `LADO_ENV_DIR=/run/secrets`.
  - compose.yaml `environment:` adds `LADO_GIT_NAME: ${LADO_GIT_NAME:-}` and
    `LADO_GIT_EMAIL: ${LADO_GIT_EMAIL:-}`; `volumes:` adds:
    ```yaml
      # The agents' variables: one file per variable (LADO_ENV_DIR), never in docker inspect.
      - type: bind
        source: ${LADO_SECRETS:-./secrets}
        target: /run/secrets
        read_only: true
        bind:
          create_host_path: false
    ```
  - entrypoint.sh, in phase 3 before the `LADO_REPOS` check:
    ```sh
    # git's identity for the agents' commits, from the container's settings, at every
    # start: a container made again with a new .env takes the new values.
    if [ -n "${LADO_GIT_NAME:-}" ]; then git config --global user.name "$LADO_GIT_NAME"; fi
    if [ -n "${LADO_GIT_EMAIL:-}" ]; then git config --global user.email "$LADO_GIT_EMAIL"; fi
    if [ -z "$(git config user.name)" ] || [ -z "$(git config user.email)" ]; then
        echo "lado: warning: git has no user.name or user.email: agents cannot commit; set LADO_GIT_NAME and LADO_GIT_EMAIL" >&2
    fi
    ```
    (Run from `/home/lado`, so no repository's config is read; a failing `git config`
    write is a warning under `set -eu`: wrap each in `|| echo "lado: warning: ..." >&2`.)
  - `.gitignore`: `docker/secrets/`.
  - `tests/container/conftest.py` and `tests/container/test_two_lados.py`: each compose
    project makes its own empty `secrets` folder in its temporary folder and sets
    `LADO_SECRETS` to it (compose resolves `./secrets` against `docker/` for `-f
    docker/compose.yaml`).

- [ ] **Step 4: Run** `uv run pytest tests/test_docker.py -n auto` and `make lint` (PASS).

- [ ] **Step 5: Commit** `git commit -m "The image reads the agents' variables from /run/secrets and sets git's identity (LAD-76)"`.

### Task 6: The ssh agent without root's group

**Files:**
- Create: `docker/ssh-agent-socket.sh`
- Modify: `docker/Dockerfile`, `docker/Dockerfile.dockerignore`, `docker/compose.yaml`,
  `docker/profile.sh`, `docker/entrypoint.sh`
- Test: `tests/test_docker.py`

- [ ] **Step 1: Failing unit tests**:

```python
def test_the_ssh_rule_names_one_program_without_setenv():
    rule = [l for l in lines() if "/etc/sudoers.d/lado-ssh-agent" in l]
    assert rule
    text = " ".join(rule)
    assert "lado ALL=(root) NOPASSWD: /usr/local/bin/lado-ssh-agent-socket" in text
    assert "SETENV" not in text


def test_the_ssh_program_takes_no_argument_and_checks_the_socket():
    text = (DOCKER / "ssh-agent-socket.sh").read_text()
    assert 'SOCKET=/run/lado/ssh-agent.sock' in text
    assert '[ "$#" -eq 0 ]' in text
    assert "PATH=/usr/bin:/bin" in text
    assert "-L \"$SOCKET\"" in text and "-S \"$SOCKET\"" in text
    assert "chown --no-dereference" in text


def test_compose_binds_the_ssh_agent_or_dev_null(compose):
    [mount] = [v for v in compose["services"]["lado"]["volumes"]
               if isinstance(v, dict) and v.get("target") == "/run/lado/ssh-agent.sock"]
    assert mount["source"] == "${LADO_SSH_AGENT:-/dev/null}"
    assert mount["bind"]["create_host_path"] is False
    assert "group_add" not in compose["services"]["lado"]


def test_the_profile_points_ssh_auth_sock_only_at_a_socket():
    profile = (DOCKER / "profile.sh").read_text()
    assert ('[ -S /run/lado/ssh-agent.sock ] && export SSH_AUTH_SOCK=/run/lado/ssh-agent.sock'
            in profile)
```

  and change `test_profile_sets_what_env_sets_for_the_agents` to leave that conditional
  line out of its parity check (it matches only `^export`, so the conditional line is
  outside it already; assert that the set stays the same five names).
  `test_compose_mounts_nothing_only_docker_desktop_has` stays: compose holds
  `/run/host-services` only in its header comment, which `yaml.safe_load` drops.

- [ ] **Step 2: Run** `uv run pytest tests/test_docker.py -n0 -k ssh -v`; FAIL.

- [ ] **Step 3: Implement**:
  - `docker/ssh-agent-socket.sh`:
    ```sh
    #!/bin/sh
    # LADO's image: gives Docker Desktop's ssh agent socket, root's in the container, to
    # lado. Run as root through its own sudo rule (no SETENV: sudo's env_reset), at every
    # start by the entrypoint; it takes no argument and changes nothing but that one
    # socket's owner, and only while it is root's, so an agent running it gains nothing
    # SSH_AUTH_SOCK does not give it already.
    set -eu
    PATH=/usr/bin:/bin
    SOCKET=/run/lado/ssh-agent.sock
    [ "$#" -eq 0 ] || { echo "lado-ssh-agent-socket: takes no argument" >&2; exit 2; }
    if [ -L "$SOCKET" ] || [ ! -S "$SOCKET" ]; then
        echo "lado-ssh-agent-socket: $SOCKET is not a socket" >&2
        exit 1
    fi
    [ "$(stat -c %u "$SOCKET")" = 0 ] || exit 0
    chown --no-dereference "$(id -u lado)" "$SOCKET"
    ```
  - Dockerfile: `COPY --chmod=755 docker/ssh-agent-socket.sh /usr/local/bin/lado-ssh-agent-socket`;
    in the sudo RUN add
    `printf '%s\n' 'lado ALL=(root) NOPASSWD: /usr/local/bin/lado-ssh-agent-socket' > /etc/sudoers.d/lado-ssh-agent && chmod 0440 /etc/sudoers.d/lado-ssh-agent && visudo -cf /etc/sudoers.d/lado-ssh-agent && mkdir -p /run/lado && chmod 755 /run/lado`.
    `Dockerfile.dockerignore` allows `docker/ssh-agent-socket.sh`.
  - compose.yaml `volumes:` adds:
    ```yaml
      # The host's ssh agent (LADO_SSH_AGENT; /dev/null: none), for the agents' git over ssh.
      - type: bind
        source: ${LADO_SSH_AGENT:-/dev/null}
        target: /run/lado/ssh-agent.sock
        bind:
          create_host_path: false
    ```
  - profile.sh: `[ -S /run/lado/ssh-agent.sock ] && export SSH_AUTH_SOCK=/run/lado/ssh-agent.sock`
    (with `|| true` so a login shell with `set -e` does not stop).
  - entrypoint.sh, phase 3 after the git lines:
    ```sh
    # The host's ssh agent: Docker Desktop's socket is root's in the container; its own
    # sudo rule gives it to lado at every start (Docker Desktop's restart makes it root's
    # again). A Linux host's socket of the projects' owner works as it is.
    SOCK=/run/lado/ssh-agent.sock
    if [ -S "$SOCK" ] && ! SSH_AUTH_SOCK=$SOCK ssh-add -l >/dev/null 2>&1; then
        status=$?
    fi
    ```
    then, written out: when `ssh-add -l` exits 2 (cannot connect) and the socket's owner
    is 0 and `may_become_root`, run `sudo -n /usr/local/bin/lado-ssh-agent-socket`; test
    `ssh-add -l` again; when it still exits 2, print the ssh warning with
    `ssh-add cannot connect`, or with `no root to give it to lado (no-new-privileges or
    dropped capabilities)` when `may_become_root` failed. Exit 0 or 1 of `ssh-add -l`
    (keys or none) is usable. Compute `status` without `set -e` stopping the script
    (`ssh-add -l >/dev/null 2>&1 && status=0 || status=$?`).

- [ ] **Step 4: Run** `uv run pytest tests/test_docker.py -n auto`, `make lint`; PASS.

- [ ] **Step 5: Commit** `git commit -m "The host's ssh agent reaches the agents without root's group (LAD-76)"`.

### Task 7: Container tests

**Files:**
- Create: `tests/container/test_access.py`
- Modify: `tests/container/container_helpers.py` (a `secrets(tmp_path, **files)` helper
  making a 700 folder with 600 files), `tests/container/conftest.py` if `start` needs a
  `secrets=` argument

Each test uses `start` (existing fixture) and only fake values; container and volume
names from `new_name()`.

- [ ] **Step 1: Write the tests**:
  - `test_a_kit_with_a_variable_starts_and_inspect_holds_no_value`:
    1. A secrets folder with `LADO_TEST_KEY=fake-6c1d…` mounted
       `-v <folder>:/run/secrets:ro`.
    2. In the container, a folder kit (written with `c.write` under `/home/lado/kit`; its
       supervisor's MCP server `env: {KEY: ${LADO_TEST_KEY}}`, command `true`) is added
       with `lado kits add /home/lado/kit --yes`.
    3. `claude_session(c, repo, "smoke", ...)` with `--kit` of it (extend `start_claude`
       with `*more_args`) gets to idle.
    4. `agent_environ(c, "smoke", "supervisor")` has `LADO_TEST_KEY=fake-6c1d…`.
    5. `docker inspect <name>` output does not contain `fake-6c1d`.
  - `test_git_identity_and_the_warning`: one container with `-e "LADO_GIT_NAME=Ann
    O'Lee" -e LADO_GIT_EMAIL=ann@example.com`; in a repo, `git commit --allow-empty -m x`
    with no `-c` as `lado` in a login shell: `git log -1 --format='%an <%ae>|%cn <%ce>'`
    is `Ann O'Lee <ann@example.com>|Ann O'Lee <ann@example.com>`; `docker logs` has no
    git warning. A second container without both on a fresh home: `docker logs` has the
    warning line, `/api/health` answers.
  - `test_gh_gives_github_its_token`: secrets folder with `GH_TOKEN=fake-gh-123`; an
    agent's login shell environment (`bash -lc` with `LADO_ENV_DIR` applied via
    `python -c "from lado import agent_env; ..."` or the supervisor's environment):
    run `printf 'protocol=https\nhost=github.com\n\n' | GH_TOKEN=fake-gh-123 git
    credential fill` as `lado`: output has `password=fake-gh-123`; `gh auth token` prints
    it.
  - `test_ssh_agent_through_a_root_owned_socket`:
    1. A volume `<name>-ssh`.
    2. A sidecar `docker run -d --name <name>-agent -u 0 -v <vol>:/run/lado --entrypoint
       sh <image> -c "ssh-agent -D -a /run/lado/ssh-agent.sock"`.
    3. `docker exec -u 0 <agent> sh -c 'ssh-keygen -q -t ed25519 -N "" -f /tmp/k && SSH_AUTH_SOCK=/run/lado/ssh-agent.sock ssh-add /tmp/k'`.
    4. LADO's container with `-v <vol>:/run/lado`.
    5. `c.sh("bash -lc 'ssh-add -l'")` lists one ED25519 key; `id -G` has no `0`.
    6. `docker restart`, after which the owner is set back to 0 by `docker exec -u 0
       <agent> chown 0 /run/lado/ssh-agent.sock` before the restart, and the key is
       listed again.

    The sidecar and volume are registered for removal as `start`'s containers are.
  - `test_ssh_agent_of_the_projects_owner`: as above with the sidecar run as `-u 2001`
    and the socket in a volume, projects owned by 2001 (`projects_volume(2001, 2001)`):
    the key is listed and `stat -c %u` of the socket stays 2001.
  - `test_no_ssh_agent_no_line`: a plain container: `docker logs` has no `ssh agent`
    line; an agent's login shell has no `SSH_AUTH_SOCK=/run/lado/ssh-agent.sock`.
  - `test_the_ssh_rule_gives_no_root`: `c.exec("sudo", "-n", "true", check=False)` fails;
    `sudo -n /usr/local/bin/lado-ssh-agent-socket x` exits 2; `sudo -n env FOO=1
    /usr/local/bin/lado-ssh-agent-socket` is refused by sudo.

- [ ] **Step 2: Build and run**: `make docker`, then
  `uv run pytest -m container -n0 tests/container/test_access.py -v`. Expected: PASS.
  Then the whole layer once, since compose and the entrypoint changed:
  `make test-container`.

- [ ] **Step 3: Commit** `git commit -m "Container tests of the agents' variables, git identity, gh and ssh (LAD-76)"`.

### Task 8: Headers, AGENTS.md, CHANGELOG

**Files:**
- Modify: `docker/compose.yaml` and `docker/Dockerfile` headers, `AGENTS.md`,
  `CHANGELOG.md`
- Test: `tests/test_docker.py`

- [ ] **Step 1: Failing test**:

```python
@pytest.mark.parametrize("path", ["compose.yaml", "Dockerfile"])
def test_the_headers_say_how_agents_log_in_and_get_access(path):
    head = header_of(DOCKER / path)  # the leading comment block
    for needle in ("secrets", "LADO_GIT_NAME", "LADO_GIT_EMAIL", "GH_TOKEN", "gh auth login",
                   "LADO_SSH_AGENT", "/run/host-services/ssh-auth.sock", "SSH_AUTH_SOCK",
                   "CLAUDE_CODE_OAUTH_TOKEN", "opencode auth login", "kilo auth login",
                   "mkdir -m 700 secrets"):
        assert needle in head, (path, needle)
```

  (`header_of`: the lines before the first non-comment line; reuse `header_text()` for
  compose if it already does that.)

- [ ] **Step 2: Implement** the headers. compose.yaml's `.env` example gains the three
  lines (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `LADO_SSH_AGENT` commented with the Mac and
  Linux values), then a block "The agents' variables and logins":
  - `mkdir -m 700 secrets`, one file per variable (`printf %s "$TOKEN" > secrets/GH_TOKEN`);
  - what they are for (`GH_TOKEN`: git over https and gh; `CLAUDE_CODE_OAUTH_TOKEN` from
    `claude setup-token`; a kit's key; a model provider's key);
  - new files reach agents started after them;
  - every agent of the container can read them, another LADO is another folder;
  - logins inside: `docker compose exec -it lado claude`, `gh auth login`, `opencode auth
    login`, `kilo auth login`, kept on the home volume;
  - Codex later.

  The Dockerfile's `docker run` example adds `-v "$PWD/secrets:/run/secrets:ro"`, `-e
  LADO_GIT_NAME=… -e LADO_GIT_EMAIL=…`, and for ssh `-v
  /run/host-services/ssh-auth.sock:/run/lado/ssh-agent.sock` (Mac) or `-v
  "$SSH_AUTH_SOCK:/run/lado/ssh-agent.sock"` (Linux), with the same notes.
  AGENTS.md:
  - Layout's `agent_env.py` line gets the outside folder;
  - How agents talk's environment bullet gets "then the variables of the `LADO_ENV_DIR`
    folder (`agent_env.outside`)";
  - the `docker/` paragraph gets the secrets folder, git identity, the gh helper, the ssh
    socket and its rule;
  - Commands' container paragraph gets `test_access.py`'s checks.

  CHANGELOG under `## 0.40.0 (unreleased)`: one line for the container (secrets folder,
  git identity, GitHub over https, ssh without root's group, logins in the headers) and
  one for `LADO_ENV_DIR` in general.

- [ ] **Step 3: Run** `uv run pytest tests/test_docker.py -n auto`, `make lint`,
  `openspec validate container-secrets-and-git --strict`; PASS.

- [ ] **Step 4: Commit** `git commit -m "The image's headers say how agents get variables, git and logins (LAD-76)"`.

### Task 9: Regression run

- [ ] `make lint`
- [ ] `make test` (unit, `-n auto`; report the numbers)
- [ ] `uv run pytest -m integration -n auto tests/integration/test_outside_variables.py`
- [ ] `make docker && make test-container` (the whole container layer: compose's new
  required folder touches `test_two_lados.py`, `test_sessions.py`, `test_migration.py`)
- [ ] `openspec validate --specs --strict` and `openspec validate container-secrets-and-git --strict`
- [ ] CI on the pull request (`ci-ok`: unit, integration shards, UI, smoke, container on
  amd64 and arm64)
- [ ] The PR body carries the manual check of the design doc, step by step.

## Tests per requirement

| Requirement | Tests (layer) |
|---|---|
| agent-variables: Agents get the variables of the outside folder | Task 1 unit; Task 4 integration (worker, kit); Task 7 container (kit, inspect) |
| agent-variables: A file the outside folder cannot give is named | Task 1 unit; Task 2 unit (start warnings); Task 3 unit (doctor) |
| agent-variables: A name LADO sets keeps LADO's value | Task 2 unit |
| agent-variables: lado doctor checks the outside folder | Task 3 unit |
| agent-variables: The values stay out of LADO's records | Task 1 unit (lines), Task 3 unit (doctor, report), Task 4 integration (logs), Task 7 container (inspect) |
| container: secrets folder | Task 5 unit (compose, ENV); Task 7 container |
| container: git identity | Task 5 unit; Task 7 container |
| container: gh for https | Task 5 unit; Task 7 container |
| container: ssh without root's group | Task 6 unit; Task 7 container (root-owned, owner's, none, rule) |
| container: headers | Task 8 unit |
| container: the user takes the projects folder's owner (modified wording) | existing `test_projects.py` (no way to root) and Task 7 (`test_the_ssh_rule_gives_no_root`) |
