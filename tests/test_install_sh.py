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


def on_tty(host: Host, answers: list[tuple[str, str]], *args: str, env=None, piped=False) -> Done:
    """install.sh with a pty as its terminal: each (prompt, answer) answered once the
    prompt is seen; the output is the terminal's, stdout and stderr together. `piped`: the
    script read from a pipe, as `curl | sh` runs it, so its stdin is no terminal."""
    dash = shutil.which("dash")
    flags = ["--version", VERSION, "--no-open", *args]
    argv = [dash, str(SCRIPT), *flags]
    if piped:
        argv = [dash, "-c", f'cat "$0" | {dash} -s -- "$@"', str(SCRIPT), *flags]
    given = {
        "argv": argv,
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


def fails(done: Done) -> Done:
    """A run that must stop: non-zero, its last word a line `lado install: <what failed and
    the next step>` (spec: Every stop of the installer says what and what to do)."""
    assert done.code != 0, done.text
    last = done.err.rstrip("\n").splitlines()[-1]
    assert last.startswith("lado install: ") and ": " in last[len("lado install: ") :], done.err
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


def test_a_stamped_copy_installs_its_own_version(host, tmp_path):
    """The release's file (scripts/stamp_installers.py) needs no --version."""
    out = tmp_path / "stamped"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "stamp_installers.py"), "0.44.0rc1", str(out)],
        check=True,
    )
    done = subprocess.run(
        [shutil.which("dash"), str(out / "install.sh"), "--yes", "--no-open"],
        env=host.env(), cwd=host.home, capture_output=True, text=True,
        start_new_session=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert env_file(host)["LADO_VERSION"] == "0.44.0rc1"
    (curl,) = host.calls("curl")
    assert "/releases/download/v0.44.0rc1/compose.yaml" in curl["args"][-1]


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


def test_a_piped_script_asks_through_the_terminal(host):
    """Under `curl | sh` stdin is the script: the answers come from /dev/tty."""
    done = on_tty(host, [("Workspace folder", "~/piped"), ("phone too?", "")], piped=True)
    assert done.code == 0, done.text
    assert env_file(host)["LADO_WORKSPACE"] == f"{host.home}/piped"


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


# Task 3: start, link, opener, phone.


def test_stray_variables_never_reach_compose_and_are_named(host):
    done = install(host, env={"LADO_VERSION": "0.30.0", "COMPOSE_PROJECT_NAME": "other"})
    assert done.code == 0, done.text
    assert env_file(host)["LADO_VERSION"] == VERSION
    for call in host.calls("docker"):
        assert call["env"] == {}, call
    assert "LADO_VERSION" in done.out and "COMPOSE_PROJECT_NAME" in done.out
    assert "unset" in done.out


def test_another_folders_container_stops_it(host):
    host.set(ps_dirs=["/Users/ann/lado"])
    done = fails(install(host))
    assert "/Users/ann/lado" in done.err
    assert host.compose_calls("up") == [] and host.compose_calls("down") == []
    assert not (host.home / "lado-docker" / ".env").exists()
    (ps,) = [c for c in host.calls("docker") if c["args"][:1] == ["ps"]]
    assert "label=com.docker.compose.project=lado" in ps["args"]


def test_its_own_folders_container_is_no_other(host):
    folder = host.home / "lado-docker"
    host.set(ps_dirs=[str(folder)])
    assert install(host).code == 0


def test_the_link_is_waited_for(host):
    host.set(health_fails=3, ui_fails=1)
    done = install(host)
    assert done.code == 0, done.text
    assert len(host.calls("sleep")) == 4
    assert f"LADO {VERSION} runs: {LINK}" in done.out
    (up,) = host.compose_calls("up")
    assert up["args"] == ["compose", "up", "-d"]
    ui = [c["args"] for c in host.compose_calls("exec") if "ui" in c["args"]]
    assert ui[-1] == ["compose", "exec", "-T", "lado", "lado", "ui", "--no-open"]


def test_a_server_that_never_answers_shows_the_log_tail(host):
    host.set(health_fails=999)
    done = fails(install(host))
    assert len(host.calls("sleep")) == 90  # every 2 s up to 180 s
    assert "LOG LINE TWO" in done.err
    assert host.compose_calls("logs")


def test_a_failed_up_names_the_port(host):
    host.set(up_code=1, up_error="Bind for 127.0.0.1:8765 failed: port is already allocated\n")
    done = fails(install(host))
    assert "port is already allocated" in done.err
    assert "LADO_PORT" in done.err


def opened(host: Host) -> list[list[str]]:
    """What the openers were given: not `open -a Docker` nor `cmd.exe /c hostname`."""
    calls = [c for name in ("open", "xdg-open", "wslview", "cmd.exe") for c in host.calls(name)]
    return [c["args"] for c in calls if c["args"][:1] != ["-a"] and "hostname" not in c["args"]]


def test_the_link_is_printed_and_opened_on_macos(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", git_name="Ann", git_email="a@b.c")
    done = run(host, "--version", VERSION, "--yes")
    assert done.code == 0, done.text
    assert LINK in done.out and "bookmark" in done.out
    assert opened(host) == [[LINK]]


def test_linux_with_a_display_opens_it(host):
    assert run(host, "--version", VERSION, "--yes", env={"DISPLAY": ":0"}).code == 0
    assert [c["args"] for c in host.calls("xdg-open")] == [[LINK]]


def test_linux_without_a_display_only_prints(host):
    done = run(host, "--version", VERSION, "--yes")
    assert LINK in done.out
    assert opened(host) == []


WSL = "5.15.153.1-microsoft-standard-WSL2"


def test_wsl_opens_windows_browser(tmp_path):
    host = Host(tmp_path / "host", kernel=WSL, git_name="Ann", git_email="a@b.c")
    assert run(host, "--version", VERSION, "--yes").code == 0
    assert opened(host) == [[LINK]]
    assert host.calls("wslview")


def test_wsl_without_wslview_opens_by_cmd(tmp_path):
    host = Host(tmp_path / "host", without=("wslview",), kernel=WSL, git_name="A", git_email="a@b")
    assert run(host, "--version", VERSION, "--yes").code == 0
    assert opened(host) == [["/c", "start", "", LINK]]


def test_no_open(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", git_name="Ann", git_email="a@b.c")
    done = install(host)
    assert LINK in done.out
    assert opened(host) == []


def test_enter_means_no_after_the_warning(host):
    done = on_tty(host, [("Workspace folder", ""), ("Open LADO on your phone too? [y/N]", "")])
    assert done.code == 0, done.text
    warning = done.out.index("anyone on the same network who gets it can run commands as you")
    assert warning < done.out.index("Open LADO on your phone too? [y/N]")
    assert "plain HTTP" in done.out and "café" in done.out
    assert "LADO_LISTEN" not in env_file(host)


def test_yes_alone_means_no(host):
    assert install(host).code == 0
    assert "LADO_LISTEN" not in env_file(host)


def test_macos_yes_uses_local_host_name(tmp_path):
    host = Host(tmp_path / "host", os="Darwin", git_name="Ann", git_email="a@b.c")
    host.set(ui_other="http://ann-mbp.local:8765/?token=abc")
    done = on_tty(host, [("Workspace folder", ""), ("phone too?", "y")])
    assert done.code == 0, done.text
    found = env_file(host)
    assert (found["LADO_LISTEN"], found["LADO_PUBLIC_HOST"]) == ("0.0.0.0", "ann-mbp.local")
    assert "On your phone: http://ann-mbp.local:8765/?token=abc" in done.out
    assert "live → the QR code" in done.out


def test_phone_flag_warns_without_asking(host):
    done = install(host, "--phone")
    assert done.code == 0, done.text
    assert "anyone on the same network" in done.out
    assert env_file(host)["LADO_LISTEN"] == "0.0.0.0"


def test_no_phone_is_not_asked(host):
    done = on_tty(host, [("Workspace folder", "")], "--no-phone")
    assert done.code == 0, done.text
    assert "phone too?" not in done.out
    assert "LADO_LISTEN" not in env_file(host)


def test_linux_with_avahi_uses_its_hostname(host):
    host.set(avahi=True, hostname="box")
    assert install(host, "--phone").code == 0
    assert env_file(host)["LADO_PUBLIC_HOST"] == "box.local"


def test_linux_without_avahi_takes_the_address_and_warns(host):
    done = install(host, "--phone")
    assert done.code == 0, done.text
    assert env_file(host)["LADO_PUBLIC_HOST"] == "192.168.1.23"
    assert "may change" in done.text


def test_wsl_takes_windows_name(tmp_path):
    host = Host(tmp_path / "host", kernel=WSL, git_name="Ann", git_email="a@b.c")
    host.set(windows_name="WINPC")
    assert install(host, "--phone").code == 0
    assert env_file(host)["LADO_PUBLIC_HOST"] == "winpc.local"


# Task 4: reruns.


def installed(host: Host, version: str, *more: str) -> Path:
    """~/lado-docker as an earlier install left it, `.env` at `version`."""
    folder = host.home / "lado-docker"
    folder.mkdir()
    (folder / "compose.yaml").write_text("name: lado # old\n")
    lines = [f"LADO_VERSION={version}", "LADO_WORKSPACE=/w", "LADO_PORT=8765", *more]
    (folder / ".env").write_text("".join(f"{line}\n" for line in lines))
    return folder


def test_an_update_keeps_the_bak_and_the_users_lines(host):
    folder = installed(host, "0.43.0", "LADO_SECRETS=./secrets", "# mine")
    host.set(compose_text="name: lado # new\n")
    done = install(host)
    assert done.code == 0, done.text
    assert (folder / "compose.yaml.bak").read_text() == "name: lado # old\n"
    assert (folder / "compose.yaml").read_text() == "name: lado # new\n"
    assert (folder / ".env").read_text() == (
        f"LADO_VERSION={VERSION}\nLADO_WORKSPACE=/w\nLADO_PORT=8765\n"
        "LADO_SECRETS=./secrets\n# mine\n"
    )
    assert host.compose_calls("up")
    assert "diff compose.yaml.bak compose.yaml" in done.out
    assert "secrets/" in done.out


def test_an_update_asks_nothing(host):
    installed(host, "0.43.0")
    done = on_tty(host, [])
    assert done.code == 0, done.text
    assert "?" not in done.out.replace("?token", "")


@pytest.mark.parametrize("older", ["0.44.0rc2", "0.43.9", "0.9.99"])
def test_an_older_version_updates(host, older):
    installed(host, older)
    assert install(host).code == 0
    assert env_file(host)["LADO_VERSION"] == VERSION


def test_a_release_candidate_of_the_next_updates_to_it(host):
    installed(host, "0.43.0")
    assert install(host).code == 0
    host.set()
    assert env_file(host)["LADO_VERSION"] == VERSION
    done = run(host, "--version", "0.45.0rc1", "--yes", "--no-open")
    assert done.code == 0, done.text
    assert env_file(host)["LADO_VERSION"] == "0.45.0rc1"


def test_a_quoted_version_is_read(host):
    installed(host, '"0.43.0"  # pinned')
    assert install(host).code == 0
    assert env_file(host)["LADO_VERSION"] == VERSION


def test_the_same_version_rewrites_nothing(host):
    folder = installed(host, VERSION, "# mine")
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    done = install(host)
    assert done.code == 0, done.text
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert host.calls("curl") == []
    assert host.compose_calls("up")
    assert LINK in done.out


@pytest.mark.parametrize("newer", ["0.45.0", "0.44.1", "0.44.0rc9.dev0"])
def test_a_newer_or_unknown_env_refuses(host, newer):
    folder = installed(host, newer)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    done = fails(install(host))
    assert newer in done.err
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert host.compose_calls("up") == []


def test_a_newer_env_names_the_way_back(host):
    installed(host, "0.45.0")
    assert "#go-back-to-the-version-before" in fails(install(host)).err


def test_a_dev_version_refuses(host):
    installed(host, "0.44.0.dev1")
    done = fails(install(host))
    assert "by hand" in done.err


def test_an_env_without_a_version_refuses(host):
    folder = host.home / "lado-docker"
    folder.mkdir()
    (folder / ".env").write_text("LADO_PORT=8765\n")
    fails(install(host))
    assert (folder / ".env").read_text() == "LADO_PORT=8765\n"


def test_phone_added_on_a_rerun(host):
    installed(host, VERSION, "# mine")
    assert install(host, "--phone").code == 0
    found = env_file(host)
    assert found["LADO_LISTEN"] == "0.0.0.0" and found["LADO_PUBLIC_HOST"] == "192.168.1.23"
    assert found["LADO_VERSION"] == VERSION
    assert "# mine" in (host.home / "lado-docker" / ".env").read_text()


def test_no_phone_removes_both_lines(host):
    installed(host, VERSION, "LADO_LISTEN=0.0.0.0", "LADO_PUBLIC_HOST=x.local")
    assert install(host, "--no-phone").code == 0
    found = env_file(host)
    assert "LADO_LISTEN" not in found and "LADO_PUBLIC_HOST" not in found
    assert found["LADO_PORT"] == "8765"


def test_a_rerun_keeps_the_phone_and_prints_its_link(host):
    installed(host, VERSION, "LADO_LISTEN=0.0.0.0", "LADO_PUBLIC_HOST=x.local")
    host.set(ui_other="http://x.local:8765/?token=abc")
    done = install(host)
    assert "On your phone: http://x.local:8765/?token=abc" in done.out
    assert env_file(host)["LADO_LISTEN"] == "0.0.0.0"


def test_a_failed_download_leaves_the_old_files(host):
    folder = installed(host, "0.43.0")
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    host.set(curl_fails=True)
    done = fails(install(host))
    assert "https://github.com/ladohq/lado/releases/download/v0.44.0/compose.yaml" in done.err
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_a_failed_fresh_download_writes_no_env(host):
    host.set(curl_fails=True)
    fails(install(host))
    assert [p.name for p in (host.home / "lado-docker").iterdir()] == []


def test_a_rerun_in_another_folder_keeps_its_project(host, tmp_path):
    folder = tmp_path / "second"
    assert install(host, "--dir", str(folder)).code == 0
    host.set(ps_dirs=[str(folder)])
    assert install(host, "--dir", str(folder)).code == 0
    ps = [c for c in host.calls("docker") if c["args"][:1] == ["ps"]]
    assert all("label=com.docker.compose.project=lado-second" in c["args"] for c in ps)
