"""The agents' access in LADO's image (openspec capability container, change
container-secrets-and-git): variables from the secrets folder at /run/secrets (a kit that
needs one starts, and docker inspect holds no value), git's identity from LADO_GIT_NAME and
LADO_GIT_EMAIL, github.com's https credentials from gh, and the host's ssh agent without
root's group, through a socket of root's (Docker Desktop's) or of the workspace's owner.
Only fake values."""

import time

import pytest
from container_helpers import (
    IMAGE,
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
    "lado: warning: git has no user.name or user.email: agents cannot commit; set "
    "LADO_GIT_NAME and LADO_GIT_EMAIL"
)
SOCKET = "/run/lado/ssh-agent.sock"
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


def test_a_new_git_email_on_the_same_home_volume(start):
    home = f"{new_name()}-home"
    first = served(start, "-e", "LADO_GIT_NAME=Ann", "-e", "LADO_GIT_EMAIL=a@example.com",
                   home=home)  # fmt: skip
    docker("rm", "-f", first.name)
    second = served(start, "-e", "LADO_GIT_EMAIL=b@example.com", home=home)
    got = second.sh("cd / && git config user.name && git config user.email").stdout
    assert got.split() == ["Ann", "b@example.com"]


def test_gh_gives_github_its_token(start, tmp_path):
    c = served(start, *with_secrets(tmp_path, GH_TOKEN=FAKE_GH))
    # The environment an agent starts from (agent_env.resolve), with the folder's GH_TOKEN.
    script = (
        "import subprocess; from lado import agent_env; env = agent_env.resolve(); "
        "print(subprocess.run(['git', 'credential', 'fill'], env=env, text=True, "
        "capture_output=True, check=True, input='protocol=https\\nhost=github.com\\n\\n').stdout); "
        "print(subprocess.run(['gh', 'auth', 'token'], env=env, text=True, "
        "capture_output=True).stdout)"
    )
    out = c.python(script)
    assert f"password={FAKE_GH}" in out.splitlines(), out
    assert out.splitlines()[-1] == FAKE_GH, out
    assert FAKE_GH not in docker("inspect", c.name).stdout


AGENT_SOCKET = "/agent/ssh-agent.sock"  # the sidecar's path of the same socket


def remove_volume(volume: str) -> None:
    """The volume, after every container that mounts it (LADO's, the sidecar)."""
    users = docker("ps", "-aq", "--filter", f"volume={volume}").stdout.split()
    if users:
        docker("rm", "-f", *users, check=False)
    docker("volume", "rm", "-f", volume, check=False)


@pytest.fixture
def ssh_agent(request):
    """`ssh_agent(uid, owner)`: an ssh agent holding one test key, run as `uid` by a
    container of its own, its socket in a new volume that LADO's container mounts at
    /run/lado, the socket then given to `owner`: 0 as Docker Desktop's looks in a
    container, or the agent's own uid as a Linux host's. OpenSSH's agent serves only its
    own uid (Docker Desktop's forwarder serves any), so `uid` is the one lado gets.
    Returns the volume and the sidecar's name; both removed after the test."""

    def make(uid: int, owner: int) -> tuple[str, str]:
        volume = f"{new_name()}-ssh"
        request.addfinalizer(lambda: remove_volume(volume))
        # Mounted where the image has no folder, so Docker copies no owner onto it.
        docker(
            "run", "--rm", "-u", "0", "--entrypoint", "sh", "-v", f"{volume}:/agent", IMAGE,
            "-c", f"chown {uid}:{uid} /agent",
        )  # fmt: skip
        name = new_name()
        docker(
            "run", "-d", "--name", name, "-u", str(uid), "--entrypoint", "sh",
            "-v", f"{volume}:/agent", IMAGE, "-c", f"exec ssh-agent -D -a {AGENT_SOCKET}",
        )  # fmt: skip
        deadline = time.monotonic() + 30
        while docker("exec", name, "test", "-S", AGENT_SOCKET, check=False).returncode != 0:
            assert time.monotonic() < deadline, docker("logs", name, check=False).stderr
            time.sleep(0.2)
        # ssh-keygen needs a user of that uid, which only 1000 has: made as root.
        docker(
            "exec", "-u", "0", name, "sh", "-c",
            f"ssh-keygen -q -t ed25519 -N '' -C lado-test -f /tmp/k && chown {uid} /tmp/k",
        )  # fmt: skip
        docker("exec", name, "sh", "-c", f"SSH_AUTH_SOCK={AGENT_SOCKET} ssh-add -q /tmp/k")
        docker("exec", "-u", "0", name, "chown", str(owner), AGENT_SOCKET)
        return volume, name

    return make


def keys(c) -> str:
    """`ssh-add -l` in an agent's login shell."""
    return c.exec("bash", "-lc", "ssh-add -l", check=False).stdout


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


def test_the_first_ssh_to_github_knows_its_host_key(container):
    """A new home volume and no ssh agent: ssh to github.com fails on the missing key of
    the user, never on the host's key, and writes no known_hosts. A real ssh to GitHub: when
    GitHub rotates its keys this turns red, and the image needs the new ones
    (docker/ssh_known_hosts)."""
    done = container.exec(
        "bash", "-lc", "ssh -T -o BatchMode=yes -o ConnectTimeout=20 git@github.com",
        check=False,
    )  # fmt: skip
    assert "Permission denied (publickey)" in done.stderr, done.stderr
    assert "Host key verification failed" not in done.stderr
    assert container.sh("test -e ~/.ssh/known_hosts && echo made || echo none").stdout.strip() == (
        "none"
    )


def test_ssh_agent_through_a_root_owned_socket(start, ssh_agent):
    volume, agent = ssh_agent(1000, 0)
    c = served(start, "-v", f"{volume}:/run/lado")
    assert "lado-test (ED25519)" in keys(c), c.logs()
    assert server_ssh_sock(c.sh) == SOCKET
    assert "0" not in c.exec("id", "-G").stdout.split()
    assert "ssh agent" not in c.logs()
    # Docker Desktop's restart makes the socket root's again; the next start gives it back.
    docker("exec", "-u", "0", agent, "chown", "0", AGENT_SOCKET)
    docker("restart", c.name)
    health(c.port)
    assert "lado-test (ED25519)" in keys(c), c.logs()
    assert server_ssh_sock(c.sh) == SOCKET


def test_ssh_agent_of_the_projects_owner_stays_its(start, ssh_agent, projects_volume):
    volume, agent = ssh_agent(2001, 2001)
    projects = projects_volume(2001, 2001)
    c = served(start, "-v", f"{volume}:/run/lado", "-v", f"{projects}:/srv/projects",
               "-e", "LADO_REPOS=/srv/projects")  # fmt: skip
    assert c.exec("id", "-u").stdout.strip() == "2001"
    assert "lado-test (ED25519)" in keys(c), c.logs()
    assert docker("exec", agent, "stat", "-c", "%u", AGENT_SOCKET).stdout.strip() == "2001"


def test_a_root_owned_socket_where_lado_may_not_become_root_is_named(start, ssh_agent):
    volume, _ = ssh_agent(1000, 0)
    c = served(start, "--security-opt", "no-new-privileges", "-v", f"{volume}:/run/lado")
    line = (
        "lado: warning: lado (uid 1000) cannot use the ssh agent socket of uid 0: no root to "
        "give it to lado (no-new-privileges or dropped capabilities)"
    )
    assert line in c.logs().splitlines(), c.logs()


def test_no_ssh_agent_no_line(compose):
    """compose's default, /dev/null: no socket, no SSH_AUTH_SOCK from the image, no line."""
    compose.run("up", "-d")
    health(compose.port)
    shell = compose.run("exec", "-T", "lado", "bash", "-lc", "echo ${SSH_AUTH_SOCK:-none}")
    assert shell.stdout.strip() == "none"

    def in_lado(script: str):
        return compose.run("exec", "-T", "lado", "sh", "-c", script)

    assert server_ssh_sock(in_lado) == "none"
    assert "ssh agent" not in compose.run("logs", "lado").stdout


def test_the_ssh_rule_gives_no_root(start, ssh_agent):
    volume, _ = ssh_agent(1000, 0)
    c = served(start, "-v", f"{volume}:/run/lado")
    assert c.exec("sudo", "-n", "true", check=False).returncode != 0
    with_arg = c.exec("sudo", "-n", "/usr/local/bin/lado-ssh-agent-socket", "x", check=False)
    assert with_arg.returncode == 2, with_arg.stderr
    # No SETENV: sudo refuses a variable for it.
    with_env = c.exec(
        "sudo", "-n", "PATH=/tmp", "/usr/local/bin/lado-ssh-agent-socket", check=False
    )
    assert with_env.returncode != 0 and "lado-ssh-agent-socket" not in with_env.stdout
    # Run again on lado's socket, it changes nothing.
    again = c.exec("sudo", "-n", "/usr/local/bin/lado-ssh-agent-socket", check=False)
    assert again.returncode == 0, again.stderr
    assert c.exec("stat", "-c", "%u", SOCKET).stdout.strip() == c.exec("id", "-u").stdout.strip()
