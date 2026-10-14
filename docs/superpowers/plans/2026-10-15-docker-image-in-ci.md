# LADO's Docker image in the repository, built and smoke-tested in CI: implementation plan

**Goal:** `docker/` holds LADO's image (LADO from the build's wheel, Claude Code at its pin),
which one `docker run` starts; a new Container test layer checks it with real Docker and no
model; CI builds and tests it on amd64 and arm64 in a job `ci-ok` needs; nothing is
published.

**Architecture:** `make docker` builds the web UI's bundle, one wheel, then
`docker/Dockerfile` with the repository as context through an allowlist
(`docker/Dockerfile.dockerignore`). `docker/profile.sh` gives login shells, so the agents,
what the image's `ENV` gives the server. `tests/container/` drives the `docker` CLI from the
host; the smoke's 401 endpoint moves to `tests/fake_endpoint.py` and also runs as a script
inside the container. `scripts/smoke_ci.py container` is a CI cell with the smoke's pass
rule.

**Tech Stack:** Dockerfile (BuildKit), Docker Compose v2, Python 3.10+ (pytest, standard
library), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-15-docker-image-in-ci-design.md`,
`openspec/changes/docker-image-in-ci/` (design.md D1-D13, deltas `container` and
`continuous-integration`).

## Global Constraints

- No file under `src/` changes.
- The image's tag built locally: `lado:local` (`LADO_IMAGE` in the Makefile and in
  compose, `LADO_TEST_IMAGE` in the tests).
- Ports: `LADO_PORT`, default `8765`; publication always `127.0.0.1:<p>:<p>`.
- The image's user: `lado`, uid 1000, home `/home/lado`; programs under `/opt/uv` and
  `/opt/agents`; LADO's Python `/opt/uv/tools/lado/bin/python`.
- Environment of the image (ENV and `docker/profile.sh`, the same values):
  `LADO_CONTAINER=1`, `LADO_REPOS=/projects`, `CLAUDE_CONFIG_DIR=/home/lado/.claude`
  (`$HOME/.claude` in profile.sh), `DISABLE_AUTOUPDATER=1`, `LANG=en_US.UTF-8`, `PATH` with
  `/opt/uv/bin:/opt/agents/bin` first; ENV only: `SHELL=/bin/bash`, `LADO_PORT=8765`.
- Claude Code's version: `ARG CLAUDE_VERSION=` `PINS["claude"][1]` of
  `scripts/smoke_ci.py` (today `2.1.295`); no other agent CLI.
- Every `FROM` and `COPY --from` pinned `<name>:<tag>@sha256:<digest>`; no `curl ... | sh`
  or `| bash`.
- Container tests: marker `container`, never in the default run; they skip when Docker or
  the image is missing; every container, volume and compose project they make is named
  `lado-test-<hex>` and removed after the test, also on a failure; containers run with
  `LADO_TELEMETRY=0` and `LADO_NO_UPDATE_CHECK=1`.
- CI: nothing logs in to a registry or pushes; every `uses:` pinned to a commit with
  `# vX.Y.Z` (copy the pins ci.yml already has).
- Commit messages: a plain sentence ending in `(LAD-64)`; the body says why.

## Review Focus

- A build context that drags the repository in (`.lado/worktrees`, `node_modules`, `.venv`):
  the allowlist must send exactly one wheel and `docker/profile.sh` (Task 3: the build's
  "transferring context" stays small; `test_the_build_context_is_an_allowlist`).
- Two wheels in `dist/` (an old one left): `COPY dist/lado-*.whl` would install both or
  fail; `make docker` empties `dist/` first (Task 3).
- `docker/compose.yaml` on a Linux host: no path that exists only under Docker Desktop (the
  prototype's ssh socket) (Task 3 test; Task 4 runs compose on the Linux runner).
- A container test that fails half way must leave no container, volume or compose project
  behind, or later runs pile them up (Task 4: removal in each fixture's `finally`, and the
  session fixture's teardown asserts `docker ps -a --filter name=lado-test-` is empty).
- The agent's environment check must read the CLI's own process, not the pane's shell
  (Task 4: `agent_pid`: the pane's process, whose `/proc/<pid>/exe` must be the file the
  `claude` command names; Claude Code 2.x is a native binary).

---

### Task 1: The fake endpoint as a module and a script

**Files:**
- Create: `tests/fake_endpoint.py`
- Modify: `tests/smoke/conftest.py` (import `Endpoint` and the 401 bodies from it)
- Test: `tests/test_fake_endpoint.py`

**Interfaces:**
- Produces: `fake_endpoint.Endpoint(host="127.0.0.1", port=0, log: Path | None = None)` with
  `.url`, `.requests: list[tuple[str, str]]`, `.close()`; as a script: `python
  fake_endpoint.py <port> <log file>` serves on `127.0.0.1:<port>` until killed and appends
  one JSON line `{"method": ..., "path": ...}` per request to the log.

- [ ] **Step 1: Write the failing test** (`tests/test_fake_endpoint.py`)

```python
"""tests/fake_endpoint.py: the 401 model API of the smoke and container tests, in process and
as a script (the container tests run it inside the image)."""

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import fake_endpoint

SCRIPT = Path(fake_endpoint.__file__)


def post(url: str) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=b"{}", method="POST")
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    raise AssertionError("the endpoint answered 2xx")


def test_in_process_it_answers_401_with_each_apis_body_and_keeps_requests():
    endpoint = fake_endpoint.Endpoint()
    try:
        assert post(f"{endpoint.url}/v1/messages") == (401, fake_endpoint.ANTHROPIC_401)
        assert post(f"{endpoint.url}/v1/responses") == (401, fake_endpoint.OPENAI_401)
        assert endpoint.requests == [("POST", "/v1/messages"), ("POST", "/v1/responses")]
    finally:
        endpoint.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_as_a_script_it_serves_on_its_port_and_logs_each_request(tmp_path):
    port, log = free_port(), tmp_path / "requests.jsonl"
    script = subprocess.Popen([sys.executable, "-I", str(SCRIPT), str(port), str(log)])
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                code, _ = post(f"http://127.0.0.1:{port}/v1/messages")
                break
            except urllib.error.URLError:
                assert time.monotonic() < deadline, "the script never listened"
                time.sleep(0.1)
        assert code == 401
        assert json.loads(log.read_text().splitlines()[0]) == {
            "method": "POST",
            "path": "/v1/messages",
        }
    finally:
        script.terminate()
        script.wait(timeout=10)
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_fake_endpoint.py -n0 -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fake_endpoint'`.

- [ ] **Step 3: Write `tests/fake_endpoint.py`**

Move `ANTHROPIC_401`, `OPENAI_401` and `Endpoint` out of `tests/smoke/conftest.py`
unchanged in behaviour, add the `host`, `port` and `log` arguments and the script entry.
Standard library only, no import of `lado` or of other test modules (it runs with the
image's Python under `-I`).

```python
"""A model API that answers every request at once with 401: the smoke tests' endpoint
(tests/smoke/) and the container tests' (tests/container/, which run it in the image as a
script). Standard library only.

    python fake_endpoint.py <port> <log file>   # 127.0.0.1:<port>, one JSON line per request
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The error each API gives a request with a wrong key; the CLIs end the turn on it and do not
# retry (a closed port would give them a transient error to retry with their own backoff).
ANTHROPIC_401 = {
    "type": "error",
    "error": {"type": "authentication_error", "message": "invalid x-api-key"},
}
OPENAI_401 = {
    "error": {
        "message": "Incorrect API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}


class Endpoint:
    """Answers every request at once with 401, and keeps the method and path of each (and,
    with `log`, appends them to that file as a JSON line)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, log: Path | None = None):
        self.requests: list[tuple[str, str]] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                endpoint.requests.append((self.command, self.path))
                if log is not None:
                    with log.open("a") as kept:
                        kept.write(json.dumps({"method": self.command, "path": self.path}) + "\n")
                body = ANTHROPIC_401 if "/messages" in self.path else OPENAI_401
                data = json.dumps(body).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.url = f"http://{host}:{self.server.server_address[1]}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    port, log = int(sys.argv[1]), Path(sys.argv[2])
    Endpoint(port=port, log=log)._thread.join()
```

In `tests/smoke/conftest.py` delete the moved code and import it:
`from fake_endpoint import ANTHROPIC_401, OPENAI_401, Endpoint  # noqa: F401` (keep the
`fake_endpoint` fixture there; `ANTHROPIC_401`/`OPENAI_401` only if still used there).
`tests/` is on `sys.path` already (the smoke conftest imports `real_clis` and
`agent_helpers` the same way).

Note: `Path | None` needs Python 3.10, the floor; the image runs 3.13.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_fake_endpoint.py -n0 -v` → 2 passed.
Run: `uv run pytest -m smoke -n0 -v -k claude --collect-only -q` → collects the smoke test
(no import error). When Claude Code is installed locally: `uv run pytest -m smoke -n0 -v -k
claude` → passed.

- [ ] **Step 5: Commit**

```bash
git add tests/fake_endpoint.py tests/test_fake_endpoint.py tests/smoke/conftest.py
git commit -m "The smoke tests' 401 endpoint is a module that also runs as a script (LAD-64)" \
  -m "The container tests run it inside LADO's image, where no pytest fixture reaches."
```

---

### Task 2: `smoke_ci.py container`, a CI cell with the smoke's pass rule

**Files:**
- Modify: `scripts/smoke_ci.py`
- Test: `tests/test_smoke_ci.py`

**Interfaces:**
- Produces: `smoke_ci.py container <out>`: runs `uv run pytest -m container -n0 -v`, its
  output to the terminal and `<out>/container.log`; exit 0 only by `passed(summary, code)`;
  on red copies `real_clis.EVIDENCE` (`<tmp>/lado-live-evidence`) into `<out>/evidence`.
  `cell(tests: list[str], log: Path, out: Path, name: str) -> int` is the shared body of
  `run` and `container`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_smoke_ci.py`; reuse its
  `UV` stub and `PASSED`)

```python
def run_container(tmp_path, **env):
    """Run `smoke_ci.py container <out>` with the uv stub: its process, out and what it ran."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "uv").write_text(UV)
    (stubs / "uv").chmod(0o755)
    temp = tmp_path / "tmp"
    temp.mkdir(exist_ok=True)
    out = tmp_path / "out"
    full = {
        "PATH": f"{stubs}{os.pathsep}/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TMPDIR": str(temp),
        "CELL_RAN": str(tmp_path / "ran"),
        "SUMMARY": PASSED,
        **env,
    }
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "container", str(out)],
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ran = tmp_path / "ran"
    return done, out, ran.read_text() if ran.exists() else ""


def test_the_container_cell_runs_the_container_tests_and_installs_nothing(tmp_path):
    done, out, ran = run_container(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "uv run pytest -m container -n0 -v\n" in ran
    assert "npm" not in ran
    assert PASSED in (out / "container.log").read_text()


@pytest.mark.parametrize(
    "summary, code", [("====== 3 passed, 2 skipped in 3.00s ======", "0"), (PASSED, "1")]
)
def test_the_container_cell_is_red_unless_the_pass_rule_holds(tmp_path, summary, code):
    done, _, _ = run_container(tmp_path, SUMMARY=summary, CODE=code)
    assert done.returncode != 0


def test_a_failing_container_cell_keeps_its_evidence(tmp_path):
    done, out, _ = run_container(
        tmp_path, SUMMARY="=== 1 failed in 3.00s ===", CODE="1", EVIDENCE_WRITES="1"
    )
    assert done.returncode != 0
    assert (out / "evidence" / "20261010-test_w" / "lado-log.txt").exists()


def test_container_with_wrong_arguments_is_a_usage_error(tmp_path):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "container"], capture_output=True, text=True
    )
    assert done.returncode == 2
```

(The `UV` stub runs `command -v opencode`; with no opencode on the stub PATH it prints
nothing and goes on.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_smoke_ci.py -n0 -v -k container` → 4 failed (usage error).

- [ ] **Step 3: Implement**

In `scripts/smoke_ci.py`: move the part of `run` from `evidence = ...` to its end into

```python
def cell(tests: list[str], log: Path, out: Path, name: str) -> int:
    """Run one cell's pytest command: its output to the terminal and to `log`; 0 only by the
    pass rule; on red, the tests' evidence copied into `<out>/evidence`."""
    # Where a failing test keeps its evidence (tests/real_clis.py, EVIDENCE).
    evidence = Path(tempfile.gettempdir(), "lado-live-evidence")
    shutil.rmtree(evidence, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    print("$", " ".join(tests), flush=True)
    with (
        log.open("w") as kept,
        subprocess.Popen(
            tests, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ) as pytest,
    ):
        for line in pytest.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            kept.write(line)
    code = pytest.returncode
    line = summary(log.read_text())
    if passed(line, code):
        return 0
    print(f"{name}: not passed (exit {code}): {line or 'no summary'}", file=sys.stderr)
    if evidence.is_dir():
        shutil.copytree(evidence, out / "evidence", dirs_exist_ok=True)
    return 1
```

`run` keeps its install and calls `cell(tests, out / f"smoke-{provider}.log", out,
f"smoke {provider}")`, passing its `env` (add an `env: dict | None = None` parameter to
`cell`, given to `Popen`). Add

```python
def container(out: Path) -> int:
    """The container tests against the image `make docker` built (ci.yml's job
    `container`): no CLI to install, the image has its own."""
    tests = ["uv", "run", "pytest", "-m", "container", "-n0", "-v"]
    return cell(tests, out / "container.log", out, "container")
```

and in `main`: `if len(argv) == 2 and argv[0] == "container": return container(Path(argv[1]))`;
`USAGE` gains `| container <out>`. Extend the module docstring with a paragraph on
`container`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_smoke_ci.py -n0 -v` → all passed (the old ones too).

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ci.py tests/test_smoke_ci.py
git commit -m "smoke_ci.py runs the container tests as a cell with the smoke's pass rule (LAD-64)" \
  -m "A container job whose tests skip, as without Docker, must be red as a smoke cell is."
```

---

### Task 3: The image and its compose file

**Files:**
- Create: `docker/Dockerfile`, `docker/Dockerfile.dockerignore`, `docker/profile.sh`,
  `docker/compose.yaml`
- Modify: `Makefile` (target `docker`, `LADO_IMAGE ?= lado:local`, `.PHONY`),
  `.github/dependabot.yml`
- Test: `tests/test_docker.py`

**Interfaces:**
- Produces: `make docker` → image `lado:local`; the files' texts the unit tests read.

- [ ] **Step 1: Write the failing tests** (`tests/test_docker.py`)

```python
"""docker/: LADO's image (openspec capability container): Claude Code at its pin and no other
CLI, bases pinned by digest, no piped install script, the environment the same for the
server (ENV) and the agents' login shells (profile.sh), the build context an allowlist, and
compose's one port number."""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
DOCKER = ROOT / "docker"
DOCKERFILE = (DOCKER / "Dockerfile").read_text()


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("smoke_ci", ROOT / "scripts" / "smoke_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PINS


def lines() -> list[str]:
    """The Dockerfile's instructions, continuation lines joined."""
    return [l.strip() for l in re.sub(r"\\\n", " ", DOCKERFILE).splitlines() if l.strip()]


def test_claude_codes_default_is_its_pin():
    [arg] = [l for l in lines() if l.startswith("ARG CLAUDE_VERSION=")]
    assert arg == f"ARG CLAUDE_VERSION={_pins()['claude'][1]}"


def test_node_22_comes_from_the_official_image():
    [stage] = [l for l in lines() if l.startswith("FROM node:")]
    assert stage.startswith("FROM node:22-bookworm-slim@sha256:") and stage.endswith(" AS node")


def test_no_other_agent_cli():
    for package, _, _ in _pins().values():
        if package != "@anthropic-ai/claude-code":
            assert package not in DOCKERFILE


def unpinned(text: str) -> list[str]:
    bad = []
    for line in text.splitlines():
        m = re.match(r"\s*(FROM|COPY\s+(?:--\S+\s+)*--from=)(\S+)", line)
        if m and m.group(2) not in ("uv", "node") and "@sha256:" not in m.group(2):
            bad.append(line.strip())
    return bad


def test_every_base_image_is_pinned_by_digest():
    assert unpinned(DOCKERFILE) == []


def test_an_unpinned_base_is_named():
    assert unpinned("FROM debian:bookworm-slim\n") == ["FROM debian:bookworm-slim"]
    assert unpinned("COPY --from=node:22-bookworm-slim /x /x\n") != []


def test_no_piped_install_script():
    assert not re.search(r"\|\s*(ba)?sh\b", DOCKERFILE)


def env() -> dict[str, str]:
    """The Dockerfile's ENV values (one ENV of `K=V` pairs per instruction)."""
    found = {}
    for line in lines():
        if line.startswith("ENV "):
            for key, value in re.findall(r'(\w+)=("[^"]*"|\S+)', line[4:]):
                found[key] = value.strip('"')
    return found


def test_profile_sets_what_env_sets_for_the_agents():
    exported = dict(
        re.findall(r'^export (\w+)="?([^"\n]*)"?$', (DOCKER / "profile.sh").read_text(), re.M)
    )
    image = env()
    assert set(exported) == {
        "PATH",
        "LADO_CONTAINER",
        "LADO_REPOS",
        "CLAUDE_CONFIG_DIR",
        "DISABLE_AUTOUPDATER",
        "LANG",
    }
    for key, value in exported.items():
        value = value.replace("$HOME", "/home/lado")
        if key == "PATH":
            assert value.startswith("/opt/uv/bin:/opt/agents/bin:")
            assert image["PATH"].startswith("/opt/uv/bin:/opt/agents/bin:")
        else:
            assert image[key] == value, key
    assert image["LADO_CONTAINER"] == "1" and image["LADO_PORT"] == "8765"


def test_the_server_listens_on_all_addresses_at_lado_port_under_tini():
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in lines()
    [cmd] = [l for l in lines() if l.startswith("CMD ")]
    assert "lado server --host 0.0.0.0 --port" in cmd and "$LADO_PORT" in cmd


def test_the_build_context_is_an_allowlist():
    ignore = (DOCKER / "Dockerfile.dockerignore").read_text().split()
    assert ignore == ["*", "!dist/lado-*.whl", "!docker/profile.sh"]


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load((DOCKER / "compose.yaml").read_text())


def test_compose_publishes_one_port_number_on_loopback(compose):
    lado = compose["services"]["lado"]
    assert lado["ports"] == ["127.0.0.1:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]
    assert lado["environment"]["LADO_PORT"] == "${LADO_PORT:-8765}"


def test_compose_names_no_container_and_needs_the_projects_folder(compose):
    lado = compose["services"]["lado"]
    assert "container_name" not in lado
    assert lado["image"] == "${LADO_IMAGE:-lado:local}"
    assert "home:/home/lado" in lado["volumes"]
    [projects] = [v for v in lado["volumes"] if v.endswith(":/projects")]
    assert projects.startswith("${LADO_PROJECTS:?")


def test_compose_mounts_nothing_only_docker_desktop_has(compose):
    assert "/run/host-services" not in str(compose)
    assert "group_add" not in compose["services"]["lado"]


def test_dependabot_updates_the_images_bases():
    updates = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())["updates"]
    [docker] = [u for u in updates if u["package-ecosystem"] == "docker"]
    assert docker["directory"] == "/docker"
    assert docker["cooldown"] == {"default-days": 7}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_docker.py -n0 -v` → errors: no `docker/Dockerfile`.

- [ ] **Step 3: Look up the digests**

```bash
docker buildx imagetools inspect debian:bookworm-slim --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect node:22-bookworm-slim --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.12.3 --format '{{json .Manifest.Digest}}'
```

Use each index digest (multi-arch), never one platform's.

- [ ] **Step 4: Write `docker/profile.sh`**

```sh
# LADO's image: what every login shell gets, so every agent (agent_env.resolve takes an
# agent's environment from `$SHELL -ilc`, not from the image's ENV). The Dockerfile's ENV
# sets the same for the server and `docker exec`; tests/test_docker.py keeps them the same.
export PATH="/opt/uv/bin:/opt/agents/bin:$PATH"
export LADO_CONTAINER=1
export LADO_REPOS=/projects
export CLAUDE_CONFIG_DIR="$HOME/.claude"
export DISABLE_AUTOUPDATER=1
export LANG=en_US.UTF-8
```

- [ ] **Step 5: Write `docker/Dockerfile.dockerignore`**

```
*
!dist/lado-*.whl
!docker/profile.sh
```

- [ ] **Step 6: Write `docker/Dockerfile`** (digests from Step 3)

```dockerfile
# LADO's image: LADO from the one wheel of its build, Claude Code at its pin, the UI server
# on 0.0.0.0:$LADO_PORT. Built from a checkout with `make docker` (lado:local); nothing
# publishes it yet. One command starts it:
#
#   docker run -d --name lado -p 127.0.0.1:8765:8765 \
#     -v lado-home:/home/lado -v ~/projects:/projects lado:local
#   docker exec lado lado ui --no-open            # the UI's link with its token
#
# Another port: -e LADO_PORT=8766 -p 127.0.0.1:8766:8766. compose.yaml runs the same image.

FROM ghcr.io/astral-sh/uv:0.12.3@sha256:<digest> AS uv
FROM node:22-bookworm-slim@sha256:<digest> AS node
FROM debian:bookworm-slim@sha256:<digest>

# tmux 3.3a and git 2.39 from Debian 12; tini reaps what tmux and the agents leave; gh and
# the ssh client for the agents' pushes; curl fetches gh's keyring (a binary .gpg).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git tmux tini procps less openssh-client locales \
 && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# Node 22 and npm from the official image, no NodeSource script: npm installs Claude Code,
# and the agents and kits' MCP servers run node and npx.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# The user lado (uid 1000, as the prototype). Programs live under /opt, outside the home
# volume, so a new image replaces them; the home volume keeps only state (LADO_HOME,
# Claude Code's login). /projects is LADO_REPOS, the human's projects.
COPY --from=uv /uv /usr/local/bin/uv
COPY docker/profile.sh /etc/profile.d/lado.sh
RUN useradd --create-home --uid 1000 --shell /bin/bash lado \
 && mkdir -p /opt/uv /opt/agents /projects \
 && chown lado:lado /opt/uv /opt/agents /projects

USER lado
WORKDIR /home/lado
ENV UV_TOOL_DIR=/opt/uv/tools \
    UV_TOOL_BIN_DIR=/opt/uv/bin \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    NPM_CONFIG_PREFIX=/opt/agents

# Installed as lado: a chown afterwards would copy the layer.
COPY --chown=lado:lado dist/lado-*.whl /tmp/wheel/
RUN uv tool install --python 3.13 /tmp/wheel/lado-*.whl \
 && rm -rf /tmp/wheel /home/lado/.cache

# Claude Code only, at the version LADO is tested with (scripts/smoke_ci.py's PINS;
# tests/test_docker.py keeps them the same): a native binary that the package's
# postinstall puts in place of its `claude` command. Its update check is off
# (DISABLE_AUTOUPDATER).
ARG CLAUDE_VERSION=2.1.295
RUN npm install -g --prefix /opt/agents "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
 && npm cache clean --force

ENV PATH=/opt/uv/bin:/opt/agents/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SHELL=/bin/bash \
    LANG=en_US.UTF-8 \
    LADO_CONTAINER=1 \
    LADO_REPOS=/projects \
    CLAUDE_CONFIG_DIR=/home/lado/.claude \
    DISABLE_AUTOUPDATER=1 \
    LADO_PORT=8765

EXPOSE 8765
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \"$LADO_PORT\""]
```

`useradd --create-home` copies `/etc/skel` (`.profile`, `.bashrc`): the container tests
append to `~/.profile`.

- [ ] **Step 7: Write `docker/compose.yaml`**

```yaml
# LADO's image (Dockerfile) with compose: the same as one `docker run`, kept in a file.
#
#   LADO_PROJECTS=~/projects docker compose up -d           # from this folder
#   docker compose exec lado lado ui --no-open               # the UI's link with its token
#
# LADO_PORT (8765) is the server's port in the container and the one published on this
# computer's loopback, always the same number. A second LADO beside the first, with its
# own container and home volume:
#
#   LADO_PROJECTS=~/projects LADO_PORT=8766 docker compose -p lado-2 up -d
#   docker compose -p lado-2 exec lado lado ui --no-open
#
# LADO_IMAGE names the image (lado:local, which `make docker` builds).
name: lado

services:
  lado:
    image: ${LADO_IMAGE:-lado:local}
    hostname: lado
    environment:
      LADO_PORT: ${LADO_PORT:-8765}
    ports:
      # This computer only: the UI's token is the one guard.
      - "127.0.0.1:${LADO_PORT:-8765}:${LADO_PORT:-8765}"
    volumes:
      # LADO_HOME (~/.lado) and Claude Code's login and config.
      - home:/home/lado
      # The human's projects (LADO_REPOS in the image).
      - ${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}:/projects
    extra_hosts:
      # A local model on the host: Docker Desktop has it already, a Linux host needs it.
      - "host.docker.internal:host-gateway"
    restart: unless-stopped

volumes:
  home:
```

- [ ] **Step 8: Makefile and Dependabot**

Makefile: add `docker` and (Task 4) `test-container` to `.PHONY`, and

```make
LADO_IMAGE ?= lado:local

docker: ## LADO's image $(LADO_IMAGE) from the working copy: the web UI's bundle, one wheel, the image
	cd web && npm ci --no-audit --no-fund && npm run build
	rm -rf dist && uv build --wheel
	docker build -f docker/Dockerfile -t $(LADO_IMAGE) .
```

`.github/dependabot.yml`, after `npm`:

```yaml
  - package-ecosystem: docker
    directory: /docker
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      docker:
        patterns: ["*"]
        update-types: [minor, patch]
```

- [ ] **Step 9: Run the tests and build**

Run: `uv run pytest tests/test_docker.py -n0 -v` → all passed.
Run (Docker installed): `make docker` → the build's context transfer is a few hundred KB
(one wheel, one script), the image is built. Then
`docker run --rm lado:local lado --version` prints the wheel's version,
`docker run --rm lado:local claude --version` prints `2.1.295`, and
`docker run --rm lado:local sh -c 'node --version && npx --version && file -L "$(command -v claude)"'`
prints `v22...`, npm's version and an ELF executable (`file` may be missing: then
`head -c4` gives `\x7fELF`).

- [ ] **Step 10: Commit**

```bash
git add docker/ Makefile .github/dependabot.yml tests/test_docker.py
git commit -m "LADO's Docker image lives in docker/, built from a wheel with Claude Code at its pin (LAD-64)" \
  -m "The research prototype was built by hand from PyPI; the image now holds exactly the LADO of the wheel it is given, so CI can test a pull request's code and a release can ship PyPI's wheel."
```

---

### Task 4: The Container test layer

**Files:**
- Create: `tests/container/__init__.py` (only if the other test folders have one; they
  import by `tests/` on `sys.path`), `tests/container/conftest.py`,
  `tests/container/test_image.py`
- Modify: `pyproject.toml` (marker `container`, `addopts` gains `and not container`),
  `Makefile` (`test-container`)

**Interfaces:**
- Consumes: `fake_endpoint.py` as a script (Task 1); the image `lado:local` (Task 3);
  `real_clis.EVIDENCE`.
- Produces: `make test-container` (`uv run pytest -m container -n0 -v`).

- [ ] **Step 1: Marker and target**

`pyproject.toml`: `addopts = "-m 'not integration and not live and not smoke and not ui
and not container'"`; markers gain `"container: LADO's image with real Docker (docker/,
make docker first); no model"`. Makefile:

```make
test-container: ## container tests: LADO's image with real Docker, serially (make docker first)
	uv run pytest -m container -n0 -v
```

- [ ] **Step 2: Write `tests/container/conftest.py`**

```python
"""Container tests: LADO's image (docker/Dockerfile) with real Docker and no model. They
drive the `docker` CLI from the host against an image built already (`make docker`,
`LADO_TEST_IMAGE` or lado:local) and skip when Docker does not run or the image is missing;
CI's cell (scripts/smoke_ci.py container) makes a skip red.

Each test's containers, volumes and compose projects are named lado-test-<hex> and removed
after it, also when it fails; a failed test keeps the containers' logs and LADO's logs in
real_clis.EVIDENCE, as a failed smoke test does."""

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest
import real_clis

ROOT = Path(__file__).parents[2]
IMAGE = os.environ.get("LADO_TEST_IMAGE", "lado:local")
PYTHON = "/opt/uv/tools/lado/bin/python"  # LADO's own Python in the image
QUIET = ["-e", "LADO_TELEMETRY=0", "-e", "LADO_NO_UPDATE_CHECK=1"]


def docker(*args: str, check: bool = True, timeout: float = 120, **kw):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=check, timeout=timeout, **kw
    )


@pytest.fixture(scope="session", autouse=True)
def image() -> str:
    if shutil.which("docker") is None or docker("info", check=False).returncode != 0:
        pytest.skip("docker does not run")
    if docker("image", "inspect", IMAGE, check=False).returncode != 0:
        pytest.skip(f"no image {IMAGE}: run make docker")
    yield IMAGE
    left = docker("ps", "-a", "-q", "--filter", "name=lado-test-").stdout.split()
    assert left == [], f"containers left behind: {left}"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def health(port: int, timeout: float = 90) -> dict:
    """/api/health on the host's loopback, once the server answers."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as r:
                return json.loads(r.read())
        except OSError:
            if time.monotonic() > deadline:
                raise AssertionError(f"no /api/health on 127.0.0.1:{port} in {timeout} s")
            time.sleep(0.5)


class Container:
    def __init__(self, name: str, port: int):
        self.name, self.port = name, port

    def exec(self, *cmd: str, check: bool = True, input: str | None = None, timeout=120):
        return docker("exec", "-i", self.name, *cmd, check=check, input=input, timeout=timeout)

    def sh(self, script: str, **kw):
        return self.exec("sh", "-c", script, **kw)

    def python(self, code: str) -> str:
        return self.exec(PYTHON, "-c", code).stdout.strip()

    def write(self, path: str, text: str):
        self.exec("sh", "-c", f'mkdir -p "$(dirname {path})" && cat > {path}', input=text)

    def logs(self) -> str:
        done = docker("logs", self.name, check=False)
        return done.stdout + done.stderr


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        item.failed_call = report.failed


def keep_evidence(item, container: Container) -> None:
    folder = real_clis.EVIDENCE / f"{datetime.now():%Y%m%d-%H%M%S}-{item.name}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "docker-logs.txt").write_text(container.logs())
    for name, script in [
        ("lado-log.txt", "lado log smoke 2>&1"),
        ("lado-ls.txt", "lado ls 2>&1"),
        ("hooks.log", "cat ~/.lado/hooks.log 2>&1"),
        ("loop.log", "cat ~/.lado/loop.log 2>&1"),
        ("server.log", "cat ~/.lado/server.log 2>&1"),
    ]:
        (folder / name).write_text(container.sh(script, check=False).stdout)
    print(f"evidence: {folder}")


def run_container(name: str, *args: str) -> None:
    docker("run", "-d", "--name", name, *QUIET, "-v", f"{name}-home:/home/lado", *args, IMAGE)


@pytest.fixture
def container(request):
    """The image as one `docker run` starts it, on a free port other than 8765."""
    name, port = f"lado-test-{secrets.token_hex(4)}", free_port()
    run_container(name, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}")
    started = Container(name, port)
    try:
        health(port)
        yield started
    finally:
        if getattr(request.node, "failed_call", False):
            keep_evidence(request.node, started)
        docker("rm", "-f", name, check=False)
        docker("volume", "rm", f"{name}-home", check=False)
```

- [ ] **Step 3: Write `tests/container/test_image.py`**

```python
"""LADO's image (openspec capability container): one `docker run` serves the UI on its
LADO_PORT, `lado doctor` is clean and says `in a container`, a Claude Code agent gets to
idle and knows it runs in a container, and the compose file publishes one port number."""

import json
import os
import secrets
import time
import urllib.request

import pytest
from conftest import IMAGE, PYTHON, ROOT, docker, free_port, health, run_container

pytestmark = pytest.mark.container

ENDPOINT_PORT = 8399  # the fake model API, on the container's own loopback
KEY = "container-fake-key-0123456789abcdef"


def wheel_version() -> str | None:
    wheels = list((ROOT / "dist").glob("lado-*.whl"))
    return wheels[0].name.split("-")[1] if len(wheels) == 1 else None


def test_docker_run_serves_the_ui_on_its_port(container):
    found = health(container.port)
    assert found["ok"] is True
    installed = container.exec("lado", "--version").stdout.split()[-1]
    assert found["version"] == installed
    if wheel_version():
        assert installed == wheel_version()
    with urllib.request.urlopen(f"http://127.0.0.1:{container.port}/", timeout=10) as page:
        assert b"<html" in page.read().lower()
    assert f"0.0.0.0:{container.port}" in container.logs()
    assert "runs in a container" in container.logs()
    link = container.exec("lado", "ui", "--no-open").stdout.strip()
    assert link.startswith(f"http://127.0.0.1:{container.port}/?token=")


def test_without_lado_port_the_server_is_on_8765():
    name, port = f"lado-test-{secrets.token_hex(4)}", free_port()
    run_container(name, "-p", f"127.0.0.1:{port}:8765")
    try:
        assert health(port)["ok"] is True
    finally:
        docker("rm", "-f", name, check=False)
        docker("volume", "rm", f"{name}-home", check=False)


def test_lado_doctor_is_clean_in_the_container(container):
    doctor = container.exec("lado", "doctor", check=False)
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "[FAIL]" not in doctor.stdout
    [lado] = [l for l in doctor.stdout.splitlines() if "] LADO:" in l]
    assert lado.endswith("in a container")
    printed = doctor.stdout.splitlines()
    # Claude Code at its pin (an untested version would be a warn), the other CLIs absent.
    assert any(l.startswith("[ok  ] Claude Code:") for l in printed), doctor.stdout
    for other in ("Codex CLI", "Kilo CLI", "OpenCode"):
        assert any(l.startswith(f"[info] {other}:") for l in printed), doctor.stdout


def test_node_and_npx_are_on_the_login_shells_path(container):
    shell = container.exec("bash", "-lc", "node --version && npx --version")
    node, npx = shell.stdout.split()
    assert node.startswith("v22.") and npx


def agent_pid(container, session: str, window: str) -> int:
    """The agent CLI's own process: the window's pane process, as lado.agent_env execs the
    CLI in place and Claude Code 2.x is a native binary. Checked, never guessed: its
    executable must be the file the `claude` command names."""
    pane = container.exec(
        "tmux",
        "-L",
        "lado",
        "display-message",
        "-p",
        "-t",
        f"{session}:{window}",
        "#{pane_pid}",
    ).stdout.strip()
    running = container.exec("readlink", f"/proc/{pane}/exe").stdout.strip()
    claude = container.sh('readlink -f "$(command -v claude)"').stdout.strip()
    assert running == claude, f"pane process {pane} runs {running}, not claude ({claude})"
    return int(pane)


def test_a_claude_session_gets_to_idle_and_knows_the_container(container):
    # The fake model API inside the container, on its own loopback.
    docker(
        "cp", str(ROOT / "tests" / "fake_endpoint.py"), f"{container.name}:/tmp/fake_endpoint.py"
    )
    docker(
        "exec",
        "-d",
        container.name,
        PYTHON,
        "-I",
        "/tmp/fake_endpoint.py",
        str(ENDPOINT_PORT),
        "/tmp/endpoint.jsonl",
    )
    # Claude Code pointed at it through the login shell, as a human gives a token; its
    # first-run screens, the bypass mode's disclaimer and the repository's trust done.
    container.sh(
        "cat >> ~/.profile <<'EOF'\n"
        f"export ANTHROPIC_BASE_URL=http://127.0.0.1:{ENDPOINT_PORT}\n"
        f"export ANTHROPIC_AUTH_TOKEN={KEY}\n"
        "export CLAUDE_CODE_MAX_RETRIES=0\n"
        "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1\n"
        "EOF"
    )
    container.write(
        "/home/lado/.claude/.claude.json",
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "bypassPermissionsModeAccepted": True,
                "projects": {"/home/lado/repo": {"hasTrustDialogAccepted": True}},
            }
        ),
    )
    container.sh(
        "git init -q -b main ~/repo && git -C ~/repo -c user.name=lado "
        "-c user.email=lado@example.com commit -q --allow-empty -m first"
    )
    started = container.exec(
        "lado",
        "start",
        "/home/lado/repo",
        "--name",
        "smoke",
        "--provider",
        "claude",
        "--permission-mode",
        "bypassPermissions",
        "--no-attach",
        check=False,
    )
    assert started.returncode == 0, started.stdout + started.stderr

    status = ""
    for _ in range(240):
        status = container.python(
            "from lado import state; a = state.get_agent('smoke', 'supervisor'); "
            "print(a.status if a else 'gone')"
        )
        if status == "idle":
            break
        time.sleep(0.5)
    assert status == "idle", f"the supervisor is {status}"

    # The agent's own environment, as its login shell made it (profile.d), not the image's ENV.
    pid = agent_pid(container, "smoke", "supervisor")
    environ = container.exec("cat", f"/proc/{pid}/environ").stdout.split("\0")
    assert "LADO_CONTAINER=1" in environ
    doctor = container.sh(
        f"xargs -0 sh -c 'exec env -i \"$@\" lado doctor' _ < /proc/{pid}/environ", check=False
    )
    [lado] = [l for l in doctor.stdout.splitlines() if "] LADO:" in l]
    assert lado.endswith("in a container"), doctor.stdout + doctor.stderr

    stopped = container.exec("lado", "stop", "--all", check=False)
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


QUIET_OVERRIDE = """services:
  lado:
    environment:
      LADO_TELEMETRY: "0"
      LADO_NO_UPDATE_CHECK: "1"
"""


def compose(project: str, override, env: dict, *args: str, check: bool = True):
    files = ["-f", str(ROOT / "docker" / "compose.yaml"), "-f", str(override)]
    return docker("compose", *files, "-p", project, *args, check=check, env=env, timeout=180)


def test_compose_serves_on_lado_port(tmp_path):
    override = tmp_path / "quiet.yaml"
    override.write_text(QUIET_OVERRIDE)
    project, port = f"lado-test-{secrets.token_hex(4)}", free_port()
    env = {
        **os.environ,
        "LADO_IMAGE": IMAGE,
        "LADO_PORT": str(port),
        "LADO_PROJECTS": str(tmp_path),
    }
    try:
        compose(project, override, env, "up", "-d")
        assert health(port)["ok"] is True
        link = compose(project, override, env, "exec", "-T", "lado", "lado", "ui", "--no-open")
        assert link.stdout.strip().startswith(f"http://127.0.0.1:{port}/?token=")
    finally:
        compose(project, override, env, "down", "-v", check=False)


def test_compose_refuses_without_the_projects_folder(tmp_path):
    override = tmp_path / "quiet.yaml"
    override.write_text(QUIET_OVERRIDE)
    env = {k: v for k, v in os.environ.items() if k != "LADO_PROJECTS"}
    done = compose("lado-test-config", override, env, "config", check=False)
    assert done.returncode != 0
    assert "LADO_PROJECTS" in done.stderr
```

The compose project's container name starts with the project, `lado-test-...`, so the
session fixture's leftover check covers it.

- [ ] **Step 4: Run them**

Run: `uv run pytest -m container -n0 -v --collect-only -q` → 7 tests collected; without
Docker they skip (`docker does not run`). With Docker: `make docker && make
test-container` → 7 passed. Run `make test` too: the default run collects none of them.

- [ ] **Step 5: Commit**

```bash
git add tests/container/ pyproject.toml Makefile
git commit -m "Container tests run LADO's image with real Docker and a fake model API (LAD-64)" \
  -m "They check what the image adds to LADO: one docker run serves the UI on LADO_PORT, lado doctor is clean, and a Claude Code agent started from its login shell knows it runs in a container."
```

---

### Task 5: The CI job `container`, in ci-ok's needs

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_ci_workflow.py`

**Interfaces:**
- Consumes: `make docker` (Task 3), `scripts/smoke_ci.py container` (Task 2).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_ci_workflow.py`; and add
  `"docker/"` to `SMOKE_RUNS`, plus `"docker/"` and `"docker/Dockerfile"` to the
  parametrize list of `test_the_guard_refuses_a_path_the_smoke_runs`)

```python
@pytest.fixture(scope="module")
def container(workflow) -> dict:
    return workflow["jobs"]["container"]


def test_the_image_is_built_and_tested_on_each_architectures_own_runner(container):
    assert container["name"] == "container (${{ matrix.arch }})"
    assert container["runs-on"] == "${{ matrix.runner }}"
    assert container["strategy"] == {
        "fail-fast": False,
        "matrix": {
            "include": [
                {"arch": "amd64", "runner": "ubuntu-24.04"},
                {"arch": "arm64", "runner": "ubuntu-24.04-arm"},
            ]
        },
    }
    assert container["timeout-minutes"] == 30


def test_the_container_job_runs_on_every_run(container):
    assert "if" not in container and "needs" not in container


def test_the_container_job_builds_then_tests_and_keeps_its_out(container):
    steps = container["steps"]
    assert step_named(steps, "Image")["run"] == "make docker"
    run = step_named(steps, "Container tests")["run"]
    assert run == 'uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container"'
    names = [s.get("name") or s["uses"].split("@")[0] for s in steps]
    assert names.index("Image") < names.index("Container tests")
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "container-${{ matrix.arch }}"
    assert upload["with"]["path"] == "${{ runner.temp }}/container"


def test_the_container_job_pushes_nothing(text):
    job = text.split("\n  container:\n", 1)[1].split("\n  ci-ok:\n", 1)[0]
    for word in ("docker login", "docker push", "--push", "login-action", "build-push-action"):
        assert word not in job
```

(`test_ci_ok_needs_every_other_job_and_runs_whatever_their_results` already fails while
`ci-ok` lacks `container`.) If the job is placed elsewhere than just before `ci-ok`, cut
its text by the next job's key instead.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_ci_workflow.py -n0 -v` → the new tests error (`KeyError:
'container'`), the guard's `docker/` cases fail.

- [ ] **Step 3: Add the job** (before `ci-ok`; copy the pinned `uses:` lines from the job
  `ui`)

```yaml
  # LADO's image (docker/Dockerfile) built from this run's wheel on each architecture's own
  # runner, then the container tests (tests/container/) against it, red unless they passed
  # with no skip (scripts/smoke_ci.py container). Every run, whatever it changes; nothing is
  # pushed anywhere.
  container:
    name: container (${{ matrix.arch }})
    runs-on: ${{ matrix.runner }}
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        include:
          - arch: amd64
            runner: ubuntu-24.04
          - arch: arm64
            runner: ubuntu-24.04-arm
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with:
          python-version: "3.13"
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: lts/*
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: uv sync --locked
      - name: Image
        run: make docker
      - name: Container tests
        run: uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container"
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: container-${{ matrix.arch }}
          path: ${{ runner.temp }}/container
          retention-days: 5
```

`ci-ok`: `needs: [unit, integration, ui, js, changes, smoke, container]`. Update the
module docstring of `tests/test_ci_workflow.py` to name the job `container`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_ci_workflow.py tests/test_workflow_security.py -n0 -v` → all
passed.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/test_ci_workflow.py
git commit -m "CI builds LADO's image on amd64 and arm64 and runs the container tests, which ci-ok needs (LAD-64)" \
  -m "Without it any change of LADO or of Claude Code's pin could break the image unseen."
```

---

### Task 6: Docs, the regression run and the pull request's CI

**Files:**
- Modify: `AGENTS.md`, `CHANGELOG.md`

- [ ] **Step 1: AGENTS.md**

- Commands: `make docker` (LADO's image `lado:local` from the working copy: the web UI's
  bundle, one wheel, `docker build`; needs Docker and Node) and `make test-container` (uv
  run pytest -m container -n0 -v: the image with real Docker, no model; `make docker`
  first); a paragraph on the container tests as the smoke's has (image `LADO_TEST_IMAGE`,
  skips, names `lado-test-<hex>`, evidence, the fake endpoint inside the container, the
  agent's environment from `/proc`).
- The CI paragraph: the job `container (<arch>)` on `ubuntu-24.04` and `ubuntu-24.04-arm`,
  `make docker` then `scripts/smoke_ci.py container`, every run, nothing pushed, in `ci-ok`'s
  needs; `docker/` may not be on the skip list.
- Layout: `docker/` (Dockerfile, its `.dockerignore` allowlist, `profile.sh`,
  `compose.yaml`; LADO from the build's wheel, Claude Code at `PINS`, the environment in
  `ENV` and `/etc/profile.d/lado.sh`); `tests/fake_endpoint.py`; `scripts/smoke_ci.py`'s
  `container`.
- Testing: a seventh layer, **Container** (`make test-container`, marker `container`): the
  image as one `docker run` starts it; needed for a change of `docker/` or of how LADO
  behaves in a container's environment; in CI on both architectures, not in `make check`.

- [ ] **Step 2: CHANGELOG.md**, under `## 0.39.0 (unreleased)`:

```markdown
- LADO's Docker image is in the repository (`docker/`): LADO from the build's wheel and
  Claude Code, started with one `docker run` (or `docker/compose.yaml`, whose `LADO_PORT`
  sets the port inside and on the host alike). `make docker` builds it from a checkout; CI
  builds and tests it on amd64 and arm64. It is not published yet.
```

- [ ] **Step 3: Regression run**

Run: `make lint` → clean. Run: `make test` → passed (report the count). Run: `openspec
validate --specs --strict` and `openspec validate docker-image-in-ci --strict` → valid.
When Docker runs locally: `make docker && make test-container` → 7 passed. When Claude
Code is installed: `uv run pytest -m smoke -n0 -v -k claude` → passed (the moved endpoint).

- [ ] **Step 4: Commit and push; CI**

```bash
git add AGENTS.md CHANGELOG.md
git commit -m "AGENTS.md and the changelog name LADO's image, its tests and its CI job (LAD-64)"
git push -u origin HEAD
```

Open the pull request and wait for CI: `container (amd64)`, `container (arm64)` and
`ci-ok` green; the smoke runs (the pull request changes `tests/` and `scripts/`). Name the
two container jobs' times in the build report.

- [ ] **Step 5: By hand on a Mac (AC-9), in the build report**

`make docker`; `docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado
-v ~/projects:/projects lado:local`; open `docker exec lado lado ui --no-open`'s link in the
host's browser; then from `docker/`: `LADO_PROJECTS=~/projects LADO_PORT=8766 docker
compose -p lado-2 up -d` and its link beside the first. Clean up: `docker rm -f lado`,
`docker volume rm lado-home`, `docker compose -p lado-2 down -v`. Screenshots of both
UIs as run artifacts.
