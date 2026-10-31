"""docker/install.sh, LADO's one-line Docker installer (openspec capability docker-installer),
run under dash and bash on a faked host (tests/install_fakes.py): fake docker, curl, git and
friends on a PATH of their own, a temporary HOME, questions through a pty. The real Docker
run is tests/container/test_install.py."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from install_fakes import Host

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "docker" / "install.sh"
HEADER = (ROOT / "docker" / "compose.yaml").read_text().split("\nname: lado")[0]
VERSION = "0.44.0"
LINK = "http://127.0.0.1:8765/?token=abc"

SHELLS = [s for s in ("dash", "bash") if shutil.which(s)]


@pytest.fixture(params=SHELLS)
def shell(request) -> str:
    return request.param


@pytest.fixture
def host(tmp_path) -> Host:
    return Host(tmp_path / "host", git_name="Ann Lee", git_email="ann@example.com")


class Done:
    def __init__(self, code: int, out: str, err: str = ""):
        self.code, self.out, self.err = code, out, err

    @property
    def text(self) -> str:
        return self.out + self.err


def run(host: Host, *args: str, shell: str = "dash", env: dict | None = None) -> Done:
    """install.sh as a file, with no terminal (a session of its own), `args` as given."""
    done = subprocess.run(
        [shutil.which(shell), str(SCRIPT), *args],
        env=host.env(**(env or {})), cwd=host.home, capture_output=True, text=True,
        stdin=subprocess.DEVNULL, start_new_session=True, timeout=60,
    )  # fmt: skip
    return Done(done.returncode, done.stdout, done.stderr)


def install(host: Host, *args: str, **kw) -> Done:
    """A run with the version given, defaults taken and no browser opened."""
    return run(host, "--version", VERSION, "--yes", "--no-open", *args, **kw)


def on_tty(host: Host, answers: list[tuple[str, str]], *args: str, env=None) -> Done:
    """install.sh with a pty as its terminal: each (prompt, answer) answered once the
    prompt is seen; the output is the terminal's, stdout and stderr together."""
    given = {
        "argv": [shutil.which("dash"), str(SCRIPT), "--version", VERSION, "--no-open", *args],
        "env": host.env(**(env or {})),
        "cwd": str(host.home),
        "answers": answers,
    }
    done = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "install_fakes.py")],
        input=json.dumps(given), capture_output=True, text=True, timeout=90, check=True,
    )  # fmt: skip
    found = json.loads(done.stdout)
    assert not found["pending"], f"never asked {found['pending'][0][0]!r}:\n{found['text']}"
    return Done(found["code"], found["text"])


def env_file(host: Host, folder: str = "lado-docker") -> dict[str, str]:
    path = host.home / folder / ".env"
    found = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            found[key] = value
    return found


def failures() -> list[str]:
    return FAILED


FAILED: list[str] = []


def fails(done: Done) -> Done:
    """A run that must stop: non-zero, its stderr kept for the `lado install:` check."""
    assert done.code != 0, done.text
    FAILED.append(done.err)
    return done


# Task 1: the script, its version, Docker.


def test_it_runs_from_a_pipe(host, shell):
    done = subprocess.run(
        [shutil.which(shell), "-s", "--", "--version", VERSION, "--yes", "--no-open"],
        input=SCRIPT.read_text(), env=host.env(), cwd=host.home,
        capture_output=True, text=True, start_new_session=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert env_file(host)["LADO_VERSION"] == VERSION
    assert LINK in done.stdout


def test_it_runs_as_a_file(host, shell):
    done = install(host, shell=shell)
    assert done.code == 0, done.text
    assert env_file(host)["LADO_VERSION"] == VERSION


def test_main_is_called_on_the_last_line():
    """A download cut in the middle runs nothing: every step is in main."""
    assert SCRIPT.read_text().rstrip().splitlines()[-1] == 'main "$@"'


def test_the_placeholder_is_one_line_of_its_own():
    assert re.findall(r"(?m)^LADO_INSTALL_VERSION=.*$", SCRIPT.read_text()) == [
        "LADO_INSTALL_VERSION="
    ]


def test_an_unstamped_copy_refuses_and_makes_nothing(host):
    done = fails(run(host, "--yes", "--no-open"))
    assert (
        "lado install: this install.sh carries no version: take the release's "
        "(https://github.com/ladohq/lado/releases/latest/download/install.sh) "
        "or pass --version X.Y.Z"
    ) in done.err
    assert not (host.home / "lado-docker").exists()
    assert host.calls("docker") == []


def test_an_unknown_flag_stops(host):
    done = fails(install(host, "--frobnicate"))
    assert "--frobnicate" in done.err
    assert not (host.home / "lado-docker").exists()


def test_help_names_every_flag(host):
    done = run(host, "--help")
    assert done.code == 0
    for flag in ("--yes", "--phone", "--no-phone", "--version", "--dir", "--image",
                 "--source", "--no-open", "--help"):  # fmt: skip
        assert flag in done.out


def test_a_version_of_another_form_stops(host):
    done = fails(run(host, "--version", "latest", "--yes"))
    assert "latest" in done.err


def nothing_made(host: Host) -> None:
    assert not (host.home / "lado-docker").exists()
    assert host.calls("sudo") == []


def test_no_docker_on_linux_names_docker_engine(tmp_path):
    host = Host(tmp_path / "host", without=("docker",))
    done = fails(install(host))
    assert "https://docs.docker.com/engine/install/" in done.err
    assert "curl -fsSL https://get.docker.com | sh" in done.err
    nothing_made(host)


def test_no_docker_on_macos_names_docker_desktop(tmp_path):
    host = Host(tmp_path / "host", without=("docker",), os="Darwin")
    done = fails(install(host))
    assert "https://www.docker.com/products/docker-desktop/" in done.err
    nothing_made(host)


def test_no_docker_in_wsl_names_docker_desktop(tmp_path):
    host = Host(tmp_path / "host", without=("docker",), kernel="5.15.1-microsoft-standard-WSL2")
    done = fails(install(host))
    assert "https://www.docker.com/products/docker-desktop/" in done.err
    nothing_made(host)


def test_no_compose_names_the_plugin(host):
    host.set(no_compose=True)
    done = fails(install(host))
    assert "https://docs.docker.com/compose/install/" in done.err
    nothing_made(host)


def test_permission_denied_names_the_docker_group(host):
    host.set(
        info_fails=99,
        info_error="permission denied while trying to connect to the Docker daemon socket\n",
    )
    done = fails(install(host))
    assert "sudo usermod -aG docker $USER" in done.err
    assert "log in again" in done.err
    nothing_made(host)


def test_a_stopped_daemon_on_linux_names_systemctl(host):
    host.set(info_fails=99)
    done = fails(install(host))
    assert "sudo systemctl start docker" in done.err
    nothing_made(host)


def test_docker_desktop_is_started_and_waited_for(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", info_fails=3)
    done = install(host)
    assert done.code == 0, done.text
    assert "Waiting for Docker Desktop" in done.out
    assert ["-a", "Docker"] in [c["args"] for c in host.calls("open")]


def test_docker_desktop_that_never_answers_stops(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", info_fails=999)
    done = fails(install(host))
    assert "Docker Desktop" in done.err
    assert len(host.calls("sleep")) == 60  # every 2 s up to 120 s
    nothing_made(host)


def test_no_docker_desktop_app_names_its_download(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", info_fails=999, docker_desktop=False)
    done = fails(install(host))
    assert "https://www.docker.com/products/docker-desktop/" in done.err
    nothing_made(host)


# Task 2: a fresh install's .env.


def test_enter_takes_the_home_workspace_and_makes_it(host):
    done = on_tty(host, [("Workspace folder", ""), ("Open LADO on your phone too? [y/N]", "")])
    assert done.code == 0, done.text
    assert env_file(host)["LADO_WORKSPACE"] == f"{host.home}/workspace"
    assert (host.home / "workspace").is_dir()
    assert f"Made {host.home}/workspace" in done.out


def test_a_tilde_is_expanded(host):
    done = on_tty(host, [("Workspace folder", "~/code"), ("phone too?", "")])
    assert done.code == 0, done.text
    assert env_file(host)["LADO_WORKSPACE"] == f"{host.home}/code"


def test_a_relative_workspace_is_asked_again(host):
    done = on_tty(
        host,
        [("Workspace folder", "projects"), ("Workspace folder", "/tmp"), ("phone too?", "")],
    )
    assert done.code == 0, done.text
    assert "full path" in done.out
    assert env_file(host)["LADO_WORKSPACE"] == "/tmp"


def test_the_computers_git_identity_is_taken_unasked(host):
    done = on_tty(host, [("Workspace folder", ""), ("phone too?", "")])
    assert done.code == 0, done.text
    assert "name for" not in done.out.lower()
    found = env_file(host)
    assert found["LADO_GIT_NAME"] == '"Ann Lee"'
    assert found["LADO_GIT_EMAIL"] == "ann@example.com"


def test_a_missing_identity_is_asked(tmp_path):
    host = Host(tmp_path / "host")
    done = on_tty(
        host,
        [
            ("Workspace folder", ""),
            ("Your name for the agents' git commits", "Ann Lee"),
            ("Your email for the agents' git commits", "ann@example.com"),
            ("phone too?", ""),
        ],
    )
    assert done.code == 0, done.text
    found = env_file(host)
    assert (found["LADO_GIT_NAME"], found["LADO_GIT_EMAIL"]) == ('"Ann Lee"', "ann@example.com")


def test_a_name_with_a_dollar_is_asked_again(tmp_path):
    host = Host(tmp_path / "host", git_email="ann@example.com")
    done = on_tty(
        host,
        [
            ("Workspace folder", ""),
            ("Your name for the agents' git commits", "Ann $HOME"),
            ("Your name for the agents' git commits", "Ann"),
            ("phone too?", ""),
        ],
    )
    assert done.code == 0, done.text
    assert env_file(host)["LADO_GIT_NAME"] == "Ann"


def test_without_a_terminal_the_defaults_are_taken_and_the_identity_warned(tmp_path):
    host = Host(tmp_path / "host")
    done = run(host, "--version", VERSION, "--no-open")
    assert done.code == 0, done.text
    assert "No terminal: taking the defaults." in done.text
    found = env_file(host)
    assert "LADO_GIT_NAME" not in found and "LADO_GIT_EMAIL" not in found
    assert "cannot commit" in done.text
    assert "LADO_LISTEN" not in found
    assert found["LADO_WORKSPACE"] == f"{host.home}/workspace"


def test_a_taken_port_moves_to_the_next(host):
    host.set(busy_ports=[8765], ui_link="http://127.0.0.1:8766/?token=abc")
    done = install(host)
    assert done.code == 0, done.text
    assert env_file(host)["LADO_PORT"] == "8766"
    assert ":8766" in done.out


def test_no_free_port_stops(host):
    host.set(busy_ports=list(range(8765, 8800)))
    done = fails(install(host))
    assert "8765" in done.err and "8799" in done.err
    assert not (host.home / "lado-docker" / ".env").exists()


def test_macos_gets_docker_desktops_agent(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", git_name="Ann", git_email="a@b.c")
    assert install(host).code == 0
    assert env_file(host)["LADO_SSH_AGENT"] == "/run/host-services/ssh-auth.sock"


def test_linux_without_an_agent_says_ssh_is_off(host):
    done = install(host)
    assert "LADO_SSH_AGENT" not in env_file(host)
    assert "git over ssh is off" in done.text


def test_linux_socket_is_taken_with_its_note(host):
    folder = tempfile.mkdtemp(prefix="lado-ssh-", dir="/tmp")
    path = os.path.join(folder, "agent.sock")
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(path)
        done = install(host, env={"SSH_AUTH_SOCK": path})
    shutil.rmtree(folder)
    assert env_file(host)["LADO_SSH_AGENT"] == path
    assert "new login" in done.text


def test_another_folder_gets_its_project_name(host, tmp_path):
    folder = tmp_path / "lado-check"
    done = install(host, "--dir", str(folder))
    assert done.code == 0, done.text
    assert "COMPOSE_PROJECT_NAME=lado-lado-check\n" in (folder / ".env").read_text()
    assert not (host.home / "lado-docker").exists()
    (up,) = host.compose_calls("up")
    assert up["cwd"] == str(folder)


def test_a_folder_name_is_made_a_compose_name(host, tmp_path):
    folder = tmp_path / "My LADO.2"
    assert install(host, "--dir", str(folder)).code == 0
    assert "COMPOSE_PROJECT_NAME=lado-my-lado-2\n" in (folder / ".env").read_text()


def test_the_default_folder_keeps_composes_name(host):
    assert install(host).code == 0
    assert "COMPOSE_PROJECT_NAME" not in env_file(host)


def test_image_is_written(host):
    assert install(host, "--image", "lado:local").code == 0
    found = env_file(host)
    assert found["LADO_IMAGE"] == "lado:local"
    assert found["LADO_VERSION"] == VERSION


def test_the_env_says_who_wrote_it(host):
    assert install(host).code == 0
    first = (host.home / "lado-docker" / ".env").read_text().splitlines()[0]
    assert first.startswith("# Written by LADO's installer on ")


def test_every_written_name_is_in_the_compose_header():
    names = set(re.findall(r"\b((?:LADO|COMPOSE)_[A-Z_]+)=", SCRIPT.read_text()))
    names -= {"LADO_INSTALL_VERSION"}
    assert names >= {"LADO_VERSION", "LADO_WORKSPACE", "LADO_PORT", "LADO_LISTEN"}
    assert [n for n in sorted(names) if n not in HEADER] == []


def test_the_versions_compose_file_is_downloaded(host):
    host.set(compose_text="name: lado # 0.44.0\n")
    assert install(host).code == 0
    (curl,) = host.calls("curl")
    assert curl["args"][-1] == (
        "https://github.com/ladohq/lado/releases/download/v0.44.0/compose.yaml"
    )
    assert (host.home / "lado-docker" / "compose.yaml").read_text() == "name: lado # 0.44.0\n"
    assert not (host.home / "lado-docker" / "compose.yaml.new").exists()


def test_source_copies_and_downloads_nothing(host, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "compose.yaml").write_text("name: lado # local\n")
    assert install(host, "--source", str(source)).code == 0
    assert host.calls("curl") == []
    assert (host.home / "lado-docker" / "compose.yaml").read_text() == "name: lado # local\n"


def test_a_compose_file_without_env_is_refused(host):
    folder = host.home / "lado-docker"
    folder.mkdir()
    (folder / "compose.yaml").write_text("name: lado\n")
    done = fails(install(host))
    assert "docs/install.md" in done.err
    assert not (folder / ".env").exists()
