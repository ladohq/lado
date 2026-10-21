"""The repositories' toolchains in LADO's image (openspec capability container): mise at its pin,
its tools on the home volume kept over a new container, the workspace trusted, the
image's Node 22 first; make, gcc and g++; the agents' `npm i -g` and `uv tool install` under
~/.local at another uid and on an older home volume; the agents' base tools, openspec at its
pin with its statistics off, python3 the image's 3.13 unless a project names its own, and
that Python closed to the agents. Each command runs in a login shell started from a clean
environment, as LADO starts an agent's (agent_env.resolve)."""

import base64
import hashlib
import io
import re
import shlex
import zipfile

import pytest
from container_helpers import ROOT, Container, docker, free_port, health, new_name
from test_docker import BASE_TOOLS as PACKAGES

pytestmark = pytest.mark.container

PROJECTS = "/srv/projects"
GO = "1.23.4"  # one download (~70 MB) per run
# What agent_env.resolve hands the login shell: no ENV of the image.
CLEAN = [
    "env", "-i", "HOME=/home/lado", "USER=lado", "LOGNAME=lado", "SHELL=/bin/bash",
    "LANG=en_US.UTF-8", "TERM=dumb", "PATH=/usr/local/bin:/usr/bin:/bin",
]  # fmt: skip


def login(container: Container, script: str, cwd: str = "/home/lado", check: bool = True):
    """`script` in an agent's login shell in `cwd`; with `check`, a failure raises with its
    output."""
    done = container.exec(
        *CLEAN, "bash", "-lc", f"cd {shlex.quote(cwd)} && {script}", check=False, timeout=600
    )
    if check:
        assert done.returncode == 0, f"{script}: exit {done.returncode}\n{done.stdout}{done.stderr}"
    return done


def served(start, projects: str, home: str | None = None) -> Container:
    """The image with `projects` at PROJECTS, once the entrypoint is done (the server
    answers)."""
    port = free_port()
    started = start(
        port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}",
        "-v", f"{projects}:{PROJECTS}", "-e", f"LADO_REPOS={PROJECTS}", home=home,
    )  # fmt: skip
    health(port)
    return started


def test_mise_is_the_pins_and_roots(start, projects_volume):
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text()
    pinned = re.search(r"^FROM jdxcode/mise:([\d.]+)@sha256:", dockerfile, re.M).group(1)
    c = served(start, projects_volume(1000, 1000))
    assert login(c, "mise --version").stdout.split()[0] == pinned
    assert c.exec("stat", "-c", "%U %a", "/usr/local/bin/mise").stdout.split() == ["root", "755"]
    assert login(c, "mise self-update -y", check=False).returncode != 0


MAKEFILE = """\
all: hello-c hello-cpp
hello-c: hello.c
\tgcc -o $@ $<
hello-cpp: hello.cpp
\tg++ -o $@ $<
"""


def test_make_builds_c_and_cpp(start, projects_volume):
    c = served(start, projects_volume(1000, 1000))
    app = f"{PROJECTS}/native"
    c.write(f"{app}/Makefile", MAKEFILE)
    c.write(f"{app}/hello.c", '#include <stdio.h>\nint main(void) { puts("c ok"); }\n')
    c.write(f"{app}/hello.cpp", '#include <iostream>\nint main() { std::cout << "cpp ok\\n"; }\n')
    assert login(c, "make -s && ./hello-c && ./hello-cpp", cwd=app).stdout == "c ok\ncpp ok\n"


# Each installed Go's folder, with its inode first.
INSTALLED = (
    "find ~/.local/share/mise/installs/go -mindepth 1 -maxdepth 1 -type d -printf '%i %f\\n'"
)


def test_a_projects_go_is_installed_once_and_kept_in_a_new_container(start, projects_volume):
    """Two agents at once (mise's lock): both succeed, one install; then the container is
    made again on the same volumes and the Go is still there."""
    projects, home = projects_volume(1000, 1000), f"{new_name()}-home"
    first = served(start, projects, home=home)
    app = f"{PROJECTS}/hello-go"
    first.write(f"{app}/.tool-versions", f"go {GO}\n")
    first.write(f"{app}/go.mod", "module example.com/hello\n\ngo 1.23\n")
    first.write(
        f"{app}/main.go", 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("go ok") }\n'
    )
    both = login(
        first,
        "(mise install > /tmp/one.log 2>&1; echo $? > /tmp/one) & "
        "(mise install > /tmp/two.log 2>&1; echo $? > /tmp/two) & wait; "
        "cat /tmp/one /tmp/two /tmp/one.log /tmp/two.log",
        cwd=app,
    ).stdout
    assert both.splitlines()[:2] == ["0", "0"], both
    # Its folder alone: mise adds links beside it (1, 1.23, latest).
    installed = login(first, INSTALLED).stdout
    assert installed.split()[1:] == [GO], installed
    built = login(first, "go build -o hello . && ./hello", cwd=app)
    assert built.stdout == "go ok\n" and "WARN" not in built.stderr, built.stderr
    assert login(first, "command -v go", cwd=app).stdout.strip() == (
        "/home/lado/.local/share/mise/shims/go"
    )
    # A project that names its Go by .go-version: the same Go, nothing to install. Its
    # go.mod's `go` line, a minimum, is not read: no newer 1.23 and no mise warning.
    other = f"{PROJECTS}/other-go"
    first.write(f"{other}/.go-version", f"{GO}\n")
    first.write(f"{other}/go.mod", "module example.com/other\n\ngo 1.23\n")
    assert login(first, "mise current go", cwd=other).stdout.strip() == GO
    version = login(first, "go version", cwd=other)
    assert version.stdout.startswith(f"go version go{GO} ")
    assert "WARN" not in version.stderr, version.stderr
    docker("rm", "-f", first.name)

    second = served(start, projects, home=home)
    assert login(second, "go version", cwd=app).stdout.startswith(f"go version go{GO} ")
    # The same folder, not one a shim's auto-install made anew.
    assert login(second, INSTALLED).stdout == installed


TRUSTED = """\
[env]
TOOLCHAIN_CHECK = "from mise.toml"

[tools]
node = "20"
"""


def test_the_projects_mise_toml_is_trusted_and_node_22_stays_first(start, projects_volume):
    """A mise.toml with an [env], which mise refuses where it is not trusted (the control
    outside the workspace). Its Node 20, and then a container-wide one, never shadows
    the image's Node 22."""
    c = served(start, projects_volume(1000, 1000))
    app, outside = f"{PROJECTS}/web", "/tmp/elsewhere"
    for folder in (app, outside):
        c.write(f"{folder}/mise.toml", TRUSTED)
    refused = login(c, "mise env", cwd=outside, check=False)
    assert refused.returncode != 0 and "not trusted" in refused.stderr, refused.stderr
    login(c, "mise install", cwd=app)
    assert "TOOLCHAIN_CHECK=" in login(c, "mise env", cwd=app).stdout
    assert login(c, "node --version", cwd=app).stdout.startswith("v22.")
    login(c, "mise use -g node@20")
    for folder in (app, "/home/lado"):
        assert login(c, "node --version", cwd=folder).stdout.startswith("v22.")
        assert login(c, "mise exec node@20 -- node --version", cwd=folder).stdout.startswith("v20.")


def wheel() -> bytes:
    """A wheel of one module and its console script `hello-uv`, made here: `uv tool install`
    of it needs no index."""
    files = {
        "hello_uv.py": "def main():\n    print('uv ok')\n",
        "hello_uv-1.0.dist-info/METADATA": "Metadata-Version: 2.1\nName: hello-uv\nVersion: 1.0\n",
        "hello_uv-1.0.dist-info/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        "hello_uv-1.0.dist-info/entry_points.txt": "[console_scripts]\nhello-uv = hello_uv:main\n",
    }
    record = []
    for name, text in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(text.encode()).digest()).rstrip(b"=")
        record.append(f"{name},sha256={digest.decode()},{len(text.encode())}")
    record.append("hello_uv-1.0.dist-info/RECORD,,")
    files["hello_uv-1.0.dist-info/RECORD"] = "\n".join(record) + "\n"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return out.getvalue()


PACKAGE = '{"name": "hello-npm", "version": "1.0.0", "bin": {"hello-npm": "bin.js"}}\n'


def installs_go_home(c: Container) -> None:
    """An agent's `npm i -g` of a local package and `uv tool install` of a local wheel: both
    under ~/.local, both commands found by a new login shell."""
    c.write("/tmp/pkg/package.json", PACKAGE)
    c.write("/tmp/pkg/bin.js", "#!/usr/bin/env node\nconsole.log('npm ok')\n")
    login(c, "npm pack --silent --pack-destination /tmp /tmp/pkg")
    login(c, "npm install -g --offline --no-audit --no-fund /tmp/hello-npm-1.0.0.tgz")
    whl = base64.b64encode(wheel()).decode()
    c.sh(f"echo {whl} | base64 -d > /tmp/hello_uv-1.0-py3-none-any.whl")
    login(
        c,
        "uv tool install --offline --python /opt/uv/python/cpython-3.13-*/bin/python3.13 "
        "/tmp/hello_uv-1.0-py3-none-any.whl",
    )
    where = login(c, "command -v hello-npm hello-uv").stdout.split()
    assert where == ["/home/lado/.local/bin/hello-npm", "/home/lado/.local/bin/hello-uv"]
    assert login(c, "hello-npm && hello-uv").stdout == "npm ok\nuv ok\n"
    assert login(c, "ls -d ~/.local/lib/node_modules/hello-npm ~/.local/share/uv/tools/hello-uv")
    assert c.sh("ls /opt/agents/lib/node_modules /opt/uv/tools").stdout.count("hello") == 0


def test_the_agents_installs_go_home_at_another_uid(start, projects_volume):
    c = served(start, projects_volume(1001, 1001))
    assert c.exec("id", "-u").stdout.strip() == "1001"
    installs_go_home(c)


def test_the_agents_installs_go_home_on_an_older_volume(start, projects_volume, old_home):
    home, _ = old_home()
    c = served(start, projects_volume(1001, 1001), home=home)
    installs_go_home(c)
    listed = c.exec("lado", "ls", check=False)
    assert listed.returncode == 0 and "old" in listed.stdout, listed.stdout + listed.stderr


# The agents' base tools (Debian package: a call that answers with exit 0).
BASE_TOOLS = {
    "jq": "jq --version",
    "ripgrep": "rg --version",
    "unzip": "unzip -v",
    "zip": "zip -v",
    "xz-utils": "xz --version",
    "bzip2": "bzip2 --help",
    "patch": "patch --version",
    "file": "file --version",
    "rsync": "rsync --version",
    "sqlite3": "sqlite3 --version",
    "tree": "tree --version",
    "lsof": "lsof -p $$",
    # OpenBSD's nc has no version flag, and its help's exit status is no promise.
    "netcat-openbsd": "nc -h 2>&1 | grep -q 'OpenBSD netcat'",
}
OPENSPEC_OFF = {"OPENSPEC_TELEMETRY": "0", "OPENSPEC_NO_UPDATE_CHECK": "1"}


def openspec_pin() -> str:
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text()
    return re.search(r"^ARG OPENSPEC_VERSION=(\S+)$", dockerfile, re.M).group(1)


def environment(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def test_the_base_tools_and_openspec_answer_on_a_clean_home(start, projects_volume):
    """The test's packages are the unit test's (tests/test_docker.py), each by its command."""
    assert PACKAGES.keys() == BASE_TOOLS.keys()
    c = served(start, projects_volume(1000, 1000))
    for package, call in BASE_TOOLS.items():
        done = login(c, f"{call} > /dev/null 2>&1", cwd=PROJECTS, check=False)
        assert done.returncode == 0, f"{package}: {call}: exit {done.returncode}"
    assert login(c, "openspec --version", cwd=PROJECTS).stdout.strip() == openspec_pin()
    assert login(c, "command -v openspec").stdout.strip() == "/opt/tools/bin/openspec"
    for env in (environment(login(c, "env").stdout), environment(c.exec("env").stdout)):
        assert {key: env.get(key) for key in OPENSPEC_OFF} == OPENSPEC_OFF


def test_an_older_openspec_through_mise_does_not_shadow_the_images(start, projects_volume):
    c = served(start, projects_volume(1000, 1000))
    login(c, "mise use -g npm:@fission-ai/openspec@1.14.0")
    assert login(c, "mise exec -- openspec --version").stdout.strip() == "1.14.0"
    for folder in (PROJECTS, "/home/lado"):
        assert login(c, "openspec --version", cwd=folder).stdout.strip() == openspec_pin()


def test_python3_is_the_images_313_unless_a_project_names_its_own(start, projects_volume):
    c = served(start, projects_volume(1000, 1000))
    for name in ("python3", "python"):
        assert login(c, f"{name} --version").stdout.startswith("Python 3.13."), name
    app = f"{PROJECTS}/py312"
    c.write(f"{app}/.python-version", "3.12\n")
    login(c, "mise install", cwd=app)
    for name in ("python3", "python"):
        assert login(c, f"{name} --version", cwd=app).stdout.startswith("Python 3.12."), name
        assert login(c, f"{name} --version", cwd=PROJECTS).stdout.startswith("Python 3.13.")


def test_the_agents_cannot_change_lados_python_and_make_environments(start, projects_volume):
    c = served(start, projects_volume(1000, 1000))
    whl = base64.b64encode(wheel()).decode()
    c.sh(f"echo {whl} | base64 -d > /tmp/hello_uv-1.0-py3-none-any.whl")
    refused = login(
        c, "python3 -m pip install --no-index /tmp/hello_uv-1.0-py3-none-any.whl", check=False
    )
    assert refused.returncode != 0
    assert "externally-managed-environment" in refused.stdout + refused.stderr, refused.stderr
    # Every file of the image's Python, and /opt/uv that holds it, root's and closed to lado.
    assert c.sh("find /opt/uv/python ! -user root | head -1").stdout == ""
    assert c.exec("stat", "-c", "%U", "/opt/uv").stdout.strip() == "root"
    python = login(c, "readlink -f /opt/fallback/bin/python3").stdout.strip()
    assert python.startswith("/opt/uv/python/cpython-3.13."), python
    # /opt/uv/tools and /opt/uv/bin stay lado's: LADO's own install. uv makes its lock file
    # writable for all (mode 666), so that a reading uv may take it; it holds no Python.
    writable = login(
        c,
        "{ find /opt/uv -maxdepth 0 -writable; "
        "find /opt/uv/python /opt/fallback -writable ! -path /opt/uv/python/.lock; }",
    )
    assert writable.stdout == "", writable.stdout
    login(c, f"python3 -m venv {PROJECTS}/app/.venv")
    login(
        c,
        f"{PROJECTS}/app/.venv/bin/pip install --no-index -q /tmp/hello_uv-1.0-py3-none-any.whl",
    )
    assert login(c, f"{PROJECTS}/app/.venv/bin/hello-uv").stdout == "uv ok\n"
    assert login(c, "python3 -c 'import hello_uv'", check=False).returncode != 0
    assert login(c, "lado --version").stdout.startswith("lado ")
