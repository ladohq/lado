"""The agents' access in LADO's image (openspec capability container, change
container-secrets-and-git): variables from the secrets folder at /run/secrets (a kit that
needs one starts, and docker inspect holds no value), git's identity from LADO_GIT_NAME and
LADO_GIT_EMAIL, github.com's token from its git server, and no ssh: an old .env's
LADO_SSH_AGENT changes nothing. Only fake values."""

import json
import os
import shutil
import socket
import tempfile
import urllib.error
import urllib.request

import pytest
from container_helpers import (
    agent_environ,
    claude_session,
    docker,
    free_port,
    git_repo,
    health,
    new_name,
)

pytestmark = pytest.mark.container

GIT_WARNING = (
    "lado: warning: git has no user.name or user.email; set LADO_GIT_NAME and LADO_GIT_EMAIL, "
    "or the commit author in Settings → Git servers"
)
FAKE_KEY = "fake-6c1d-not-a-key"
FAKE_GH = "fake-gh-123-not-a-token"


def served(start, *args: str, home: str | None = None):
    """The image on a free port, its server answering."""
    port = free_port()
    started = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}", *args,
                    home=home)  # fmt: skip
    health(port)
    return started


def with_secrets(tmp_path, **files: str) -> list[str]:
    """`docker run` arguments for a secrets folder of the host (700, its files 600) at
    /run/secrets, read-only, and the host's workspace as LADO_REPOS, so lado takes
    the host user's uid and can read the files, as with compose."""
    secrets = tmp_path / "secrets"
    secrets.mkdir(mode=0o700)
    for name, value in files.items():
        (secrets / name).write_text(value + "\n")
        (secrets / name).chmod(0o600)
    projects = tmp_path / "projects"
    projects.mkdir()
    return [
        "-v", f"{secrets}:/run/secrets:ro",
        "-v", f"{projects}:{projects}", "-e", f"LADO_REPOS={projects}",
    ]  # fmt: skip


def test_a_kit_with_a_variable_starts_and_inspect_holds_no_value(start, tmp_path):
    c = served(start, *with_secrets(tmp_path, TEST_KIT_KEY=FAKE_KEY))
    c.write("/home/lado/kit/kit.yaml", "name: needs-key\nversion: 1.0.0\n")
    c.write(
        "/home/lado/kit/agents/reviewer.md",
        "---\nname: reviewer\ndescription: reviews\n"
        "mcp:\n  keyed:\n    command: ['true']\n    env: {KEY: '${TEST_KIT_KEY}'}\n"
        "---\nYou review.\n",
    )
    c.exec("lado", "kits", "add", "/home/lado/kit", "--yes")
    git_repo(c, "/home/lado/repo")
    claude_session(c, "/home/lado/repo", start_args=("--kit", "default", "--kit", "needs-key"))
    assert f"TEST_KIT_KEY={FAKE_KEY}" in agent_environ(c, "smoke", "supervisor")
    # The kit's check of its MCP server's ${TEST_KIT_KEY} sees the file.
    c.python(
        "from lado import runtime; runtime.spawn_worker('smoke', 'wait', role='reviewer', "
        "name='r1')"
    )
    inspected = docker("inspect", c.name).stdout
    assert "/run/secrets" in inspected
    assert FAKE_KEY not in inspected
    assert FAKE_KEY not in c.logs()
    doctor = c.exec("lado", "doctor", check=False).stdout
    assert "Variables from outside: /run/secrets: TEST_KIT_KEY" in doctor, doctor
    assert FAKE_KEY not in doctor
    stopped = c.exec("lado", "stop", "--all", check=False)
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


def test_git_identity_and_the_warning_without_it(start):
    c = served(start, "-e", "LADO_GIT_NAME=Ann O'Lee", "-e", "LADO_GIT_EMAIL=ann@example.com")
    git_repo(c, "/home/lado/repo")
    done = c.exec(
        "bash", "-lc",
        "cd /home/lado/repo && git commit -q --allow-empty -m x && "
        "git log -1 --format='%an <%ae>|%cn <%ce>'",
    )  # fmt: skip
    assert done.stdout.strip() == "Ann O'Lee <ann@example.com>|Ann O'Lee <ann@example.com>"
    assert GIT_WARNING not in c.logs()

    bare = served(start)
    assert GIT_WARNING in bare.logs().splitlines(), bare.logs()


def api(port: int, token: str, method: str, path: str, body: dict | None = None) -> dict:
    """The served server's answer to `method path` with `body` as JSON."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=60) as answer:
        return json.load(answer)


def test_a_clean_container_starts_a_project_with_ladOs_author_alone(start):
    """No LADO_GIT_NAME, no terminal: LADO's author set through the API signs a repository
    made from scratch, and git's global config stays without user.name."""
    c = served(start)
    token = c.exec("lado", "ui", "--no-open").stdout.strip().partition("?token=")[2]
    api(c.port, token, "PUT", "/api/git-author", {"name": "Ann Lee", "email": "ann@example.com"})
    api(c.port, token, "POST", "/api/projects", {"id": "shop", "title": None})
    made = api(c.port, token, "POST", "/api/projects/shop/repos", {"name": "site"})
    log = c.sh(f"git -C {made['path']} log -1 --format='%an <%ae>|%cn <%ce>'").stdout.strip()
    assert log == "Ann Lee <ann@example.com>|Ann Lee <ann@example.com>"
    assert c.sh("git config --global user.name", check=False).stdout.strip() == ""
    assert "agents cannot commit" not in c.exec("lado", "doctor", check=False).stdout


def test_a_new_git_email_on_the_same_home_volume(start):
    home = f"{new_name()}-home"
    first = served(start, "-e", "LADO_GIT_NAME=Ann", "-e", "LADO_GIT_EMAIL=a@example.com",
                   home=home)  # fmt: skip
    docker("rm", "-f", first.name)
    second = served(start, "-e", "LADO_GIT_EMAIL=b@example.com", home=home)
    got = second.sh("cd / && git config user.name && git config user.email").stdout
    assert got.split() == ["Ann", "b@example.com"]


FAKE_ENTRY = "fake-entry-456-not-a-token"
GITHUB_ACCESS = """
import pathlib, subprocess, tempfile
from lado import agent_env, git_kinds, git_servers, state

def fill(env):
    asked = "protocol=https\\nhost=github.com\\n\\n"
    done = subprocess.run(["git", "credential", "fill"], env={**env, "GIT_TERMINAL_PROMPT": "0"},
                          text=True, capture_output=True, input=asked)
    return done.stdout.replace("\\n", " ")

def gh(env):
    done = subprocess.run(["gh", "auth", "token"], env=env, text=True, capture_output=True)
    return done.stdout.strip() or "none"

def launched():
    env, servers = agent_env.resolve(), state.git_servers()
    folder = pathlib.Path(tempfile.mkdtemp()) / "gh"
    return {**env, **git_servers.variables(env, servers),
            **git_servers.gh_variables(servers, folder, lambda: None)}

import time
for _ in range(100):  # the server's start takes the GitHub login over first: let it end
    if state.github_takeover() is not None:
        break
    time.sleep(0.2)
if state.git_server_by_host("github.com"):  # whatever GitHub said of the fake GH_TOKEN
    git_servers.remove(git_servers.address("github.com"))
print("before", fill(launched()), "|", gh(launched()))
checked = git_servers.Checked(git_kinds.by_name("github"), "octo")
git_servers.save(git_servers.address("github.com"), checked, "%s")
print("after", fill(launched()), "|", gh(launched()))
"""


def test_github_com_takes_the_token_of_its_git_server_alone(start, tmp_path):
    """No credential helper of the image's and no login outside LADO: a GH_TOKEN in the
    secrets folder and gh's own login on the home volume give github.com nothing; once
    github.com is saved, the agents' git and the real gh take its token."""
    c = served(start, *with_secrets(tmp_path, GH_TOKEN=FAKE_GH))
    c.sh(
        "mkdir -p ~/.config/gh && printf 'github.com:\\n    oauth_token: gho-home-volume\\n"
        "    user: someone\\n' > ~/.config/gh/hosts.yml"
    )
    out = c.python(GITHUB_ACCESS % FAKE_ENTRY).splitlines()
    before, after = out[-2], out[-1]
    assert "password=" not in before and before.endswith("| none"), out
    assert f"password={FAKE_ENTRY}" in after and after.endswith(f"| {FAKE_ENTRY}"), out
    assert FAKE_GH not in "\n".join(out)
    assert FAKE_GH not in docker("inspect", c.name).stdout


PRIVATE = "https://example.invalid/acme/kit.git"  # resolves nowhere
REMOTE = "/home/lado/remote/kit.git"  # where the secrets folder's insteadOf sends PRIVATE


def remote_branches(port: int, token: str, url: str) -> dict:
    """The served server's listing of `url` (`POST /api/remote-branches`)."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/remote-branches",
        data=json.dumps({"url": url}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return json.load(answer)
    except urllib.error.HTTPError as refused:
        return {"refused": refused.code, "detail": json.load(refused)}


def test_lados_own_git_takes_the_secrets_folders_access(start, tmp_path):
    """The access a token in /run/secrets gives, stood for by git config entries there that
    send PRIVATE to a repository in the container: the server's listing and `lado kits add`
    reach PRIVATE only through LADO's own git getting the folder's variables (AC-5)."""
    c = served(start, *with_secrets(tmp_path, GIT_CONFIG_COUNT="1",
                                    GIT_CONFIG_KEY_0=f"url.file://{REMOTE}.insteadOf",
                                    GIT_CONFIG_VALUE_0=PRIVATE))  # fmt: skip
    c.write("/home/lado/kit/kit.yaml", "name: private-kit\nversion: 1.0.0\n")
    c.write(
        "/home/lado/kit/agents/reviewer.md",
        "---\nname: reviewer\ndescription: reviews\n---\nYou review.\n",
    )
    c.sh(
        "cd /home/lado/kit && git init -q -b main && git add -A && "
        "git -c user.name=lado -c user.email=lado@example.com commit -q -m kit && "
        f"git tag v1.0.0 && git clone -q --bare . {REMOTE}"
    )
    token = c.exec("lado", "ui", "--no-open").stdout.strip().partition("?token=")[2]
    listed = remote_branches(c.port, token, PRIVATE)
    assert listed.get("branches") == ["main"], listed
    added = c.exec("lado", "kits", "add", PRIVATE, "--yes", check=False)
    assert added.returncode == 0, added.stdout + added.stderr
    assert f"from {PRIVATE}" in c.exec("lado", "kits").stdout


def server_ssh_sock(run) -> str:
    """The UI server's own SSH_AUTH_SOCK (its clone and branch listing run git with the
    server's environment), or "none"; `run(script)` runs a shell script in the container,
    failing when no server runs, so "none" is never an absent process."""
    script = (
        # [l]: the pattern never matches this shell's own command line.
        "pid=$(pgrep -n -f '[l]ado server --host') || exit 3; "
        "tr '\\0' '\\n' < /proc/$pid/environ | sed -n 's/^SSH_AUTH_SOCK=//p'"
    )
    return run(script).stdout.strip() or "none"


def test_an_old_ssh_agent_line_changes_nothing(compose):
    """An .env of a version before still names the host's ssh agent: the container has no
    ssh and says nothing about it, neither in its logs nor in `lado doctor`."""
    # AF_UNIX paths are short: a socket of the host's in a folder of its own under /tmp.
    folder = tempfile.mkdtemp(prefix="lado-agent-", dir="/tmp")
    path = os.path.join(folder, "agent.sock")
    try:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(path)
            compose.env["LADO_SSH_AGENT"] = path
            compose.run("up", "-d")
            health(compose.port)

            def in_lado(script: str, check: bool = True):
                return compose.run("exec", "-T", "lado", "sh", "-c", script, check=check)

            gone = in_lado(
                "for p in /run/lado /etc/ssh/ssh_known_hosts /etc/sudoers.d/lado-ssh-agent "
                "/usr/local/bin/lado-ssh-agent-socket /etc/profile.d/lado-ssh-agent.sh; do "
                'test -e "$p" && echo "$p"; done; true'
            )
            assert gone.stdout.strip() == ""
            shell = compose.run("exec", "-T", "lado", "bash", "-lc", "echo ${SSH_AUTH_SOCK:-none}")
            assert shell.stdout.strip() == "none"
            assert server_ssh_sock(in_lado) == "none"
            # The workspace's path is the test's folder, whose name says ssh.
            workspace = compose.env["LADO_WORKSPACE"]
            logs = compose.run("logs", "lado")
            assert "ssh" not in (logs.stdout + logs.stderr).replace(workspace, "").lower()
            doctor = in_lado("lado doctor", check=False)
            assert "ssh" not in (doctor.stdout + doctor.stderr).replace(workspace, "").lower()
            # The root step's way to root is gone, and no other rule is left.
            listed = in_lado("sudo -n -l", check=False)
            assert listed.returncode != 0 and "NOPASSWD" not in listed.stdout, listed
    finally:
        shutil.rmtree(folder)
