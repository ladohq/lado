"""docker/: LADO's image (openspec capability container): the four agent CLIs at their pins
and no other npm package, Node 22 from the official image, bases pinned by digest, no piped
install script, the environment the same for the server (ENV) and the agents' login shells
(profile.sh), the build context an allowlist, compose's one port number and its image by
LADO_VERSION, and the headers' update by version."""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lado import update
from lado.providers.claude import ClaudeProvider

ROOT = Path(__file__).parents[1]
DOCKER = ROOT / "docker"
DOCKERFILE = (DOCKER / "Dockerfile").read_text()


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("smoke_ci", ROOT / "scripts" / "smoke_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PINS


def lines(text: str = DOCKERFILE) -> list[str]:
    """The Dockerfile's instructions, continuation lines joined, comments left out."""
    joined = re.sub(r"\\\n", " ", text)
    return [
        line.strip()
        for line in joined.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# Each provider's build argument: its version in the image, its default the pin.
ARGS = {
    "claude": "CLAUDE_VERSION",
    "codex": "CODEX_VERSION",
    "opencode": "OPENCODE_VERSION",
    "kilo": "KILO_VERSION",
}


def test_every_provider_of_pins_has_its_build_argument():
    assert set(ARGS) == set(_pins()), f"PINS {sorted(_pins())}, Dockerfile {sorted(ARGS)}"


@pytest.mark.parametrize("provider", sorted(ARGS))
def test_each_clis_default_is_its_pin(provider):
    name = ARGS[provider]
    [arg] = [line for line in lines() if line.startswith(f"ARG {name}=")]
    pinned = _pins()[provider][1]
    assert arg == f"ARG {name}={pinned}", f"Dockerfile {arg}, PINS {pinned}"


@pytest.mark.parametrize("provider", sorted(ARGS))
def test_each_cli_is_installed_at_that_version_in_a_layer_of_its_own(provider):
    package = _pins()[provider][0]
    [install] = [line for line in lines() if f'"{package}@${{{ARGS[provider]}}}"' in line]
    assert install.startswith("RUN npm install -g --prefix /opt/agents ")
    assert install.count("@${") == 1, install


def test_node_22_comes_from_the_official_image():
    [stage] = [line for line in lines() if line.startswith("FROM node:")]
    assert stage.startswith("FROM node:22-bookworm-slim@sha256:")
    assert stage.endswith(" AS node")


def test_no_other_npm_package_is_installed():
    """The four CLIs of PINS and openspec, the kits' tool."""
    packages = {pin[0] for pin in _pins().values()} | {OPENSPEC}
    installs = [line for line in lines() if "npm install" in line]
    assert len(installs) == len(packages), installs
    for line in installs:
        named = re.findall(r'"(@?[^"@]+)@[^"]*"', line)
        assert named and set(named) <= packages, line


def flat() -> list[str]:
    """The Dockerfile's instructions with their runs of spaces made one."""
    return [" ".join(line.split()) for line in lines()]


OPENSPEC = "@fission-ai/openspec"
OPENSPEC_INSTALL = (
    f'RUN npm install -g --prefix /opt/tools "{OPENSPEC}@${{OPENSPEC_VERSION}}" '
    "&& npm cache clean --force"
)


def loose_pin(text: str) -> list[str]:
    """The lines of `text` that leave openspec's pin loose: its ARG's default not an exact
    version, its install sharing a layer with another package (or missing)."""
    bad = [
        line
        for line in lines(text)
        if line.startswith("ARG OPENSPEC_VERSION")
        and not re.fullmatch(r"ARG OPENSPEC_VERSION=\d+\.\d+\.\d+", line)
    ]
    installs = [line for line in lines(text) if f'"{OPENSPEC}@' in line]
    bad += [line for line in installs if " ".join(line.split()) != OPENSPEC_INSTALL]
    if not installs:
        bad.append(f"no install of {OPENSPEC}")
    return bad


def test_openspec_is_pinned_in_a_layer_of_its_own_after_the_clis():
    assert loose_pin(DOCKERFILE) == []
    [arg] = [line for line in lines() if line.startswith("ARG OPENSPEC_VERSION=")]
    install = flat().index(OPENSPEC_INSTALL)
    assert lines().index(arg) < install
    clis = [i for i, line in enumerate(lines()) if "--prefix /opt/agents" in line]
    assert len(clis) == len(ARGS) and max(clis) < install


def test_a_loose_openspec_pin_is_named():
    arg = "ARG OPENSPEC_VERSION=1.14.1\n"
    assert loose_pin(arg + OPENSPEC_INSTALL + "\n") == []
    assert loose_pin("ARG OPENSPEC_VERSION=latest\n" + OPENSPEC_INSTALL + "\n") == [
        "ARG OPENSPEC_VERSION=latest"
    ]
    assert loose_pin("ARG OPENSPEC_VERSION=^1.14\n" + OPENSPEC_INSTALL + "\n") != []
    shared = 'RUN npm install -g --prefix /opt/tools "@fission-ai/openspec@${OPENSPEC_VERSION}" jq'
    assert loose_pin(arg + shared + "\n") == [shared]
    assert loose_pin(arg) == [f"no install of {OPENSPEC}"]


def test_opt_tools_is_named_only_where_it_is_made_installed_and_on_path():
    """openspec is no agent CLI: /opt/agents stays the four of PINS."""
    named = [line for line in flat() if "/opt/tools" in line]
    [made] = [line for line in named if line.startswith("RUN useradd")]
    assert re.search(r"mkdir -p [^&]*/opt/tools", made)
    assert re.search(r"chown lado:lado [^&]*/opt/tools", made)
    [path] = [line for line in named if line.startswith("ENV ")]
    assert named == [made, OPENSPEC_INSTALL, path]


# The agents' base tools from Debian (package: command): the kits' scripts and the agent
# CLIs call them in a new container on a clean home volume.
BASE_TOOLS = {
    "jq": "jq",
    "ripgrep": "rg",
    "unzip": "unzip",
    "zip": "zip",
    "xz-utils": "xz",
    "bzip2": "bzip2",
    "patch": "patch",
    "file": "file",
    "rsync": "rsync",
    "sqlite3": "sqlite3",
    "tree": "tree",
    "lsof": "lsof",
    "netcat-openbsd": "nc",
}


def missing_tools(text: str) -> list[str]:
    """The base tools' packages missing from the first `apt-get install` of `text`."""
    installs = [line for line in lines(text) if "apt-get install" in line]
    first = installs[0].split("apt-get install", 1)[1].split("&&", 1)[0].split()
    return sorted(set(BASE_TOOLS) - set(first))


def test_the_image_carries_the_agents_base_tools():
    assert missing_tools(DOCKERFILE) == []


def test_a_base_tool_left_out_of_the_first_apt_layer_is_named():
    first = "RUN apt-get update && apt-get install -y " + " ".join(sorted(set(BASE_TOOLS) - {"jq"}))
    assert missing_tools(first + " && rm -rf /var/lib/apt/lists/*\n") == ["jq"]
    # A later apt-get install does not count: the first layer carries them.
    later = "RUN apt-get update && apt-get install -y jq\n"
    assert missing_tools(first + "\n" + later) == ["jq"]


def missing_uv_binaries(text: str) -> list[str]:
    """Which of uv and uvx the `COPY --from=uv` lines of `text` leave out of /usr/local/bin."""
    copied = set()
    for line in lines(text):
        words = line.split()
        if words[:2] != ["COPY", "--from=uv"]:
            continue
        sources, target = words[2:-1], words[-1]
        if target.rstrip("/") == "/usr/local/bin":
            copied.update(Path(source).name for source in sources)
        elif str(Path(target).parent) == "/usr/local/bin" and len(sources) == 1:
            copied.add(Path(target).name)
    return sorted({"uv", "uvx"} - copied)


def test_the_image_carries_uvx_beside_uv():
    """uvx runs `uv tool run` through the uv beside it; kits' MCP servers call it."""
    assert missing_uv_binaries(DOCKERFILE) == []


def test_a_uv_copy_without_uvx_is_named():
    assert missing_uv_binaries("COPY --from=uv /uv /usr/local/bin/uv\n") == ["uvx"]
    assert missing_uv_binaries("COPY --from=uv /uv /usr/local/bin/\n") == ["uvx"]
    assert missing_uv_binaries("COPY --from=mise /uvx /usr/local/bin/\n") == ["uv", "uvx"]
    assert missing_uv_binaries("COPY --from=uv /uv /uvx /usr/local/bin/\n") == []


PYTHON_FALLBACK = "/opt/fallback/bin"


def test_the_images_python_is_roots_and_the_fallback_of_python3():
    """Installed as root before `USER lado`, so no agent changes the Python LADO runs on;
    /opt/uv itself is root's too, or lado could rename the folder away. Without uv's bin
    links, which would land in root's ~/.local/bin."""
    [install] = [line for line in lines() if "uv python install" in line]
    assert " ".join(install.split()).startswith(
        "RUN UV_PYTHON_INSTALL_DIR=/opt/uv/python uv python install 3.13 --no-bin "
    )
    assert lines().index(install) < lines().index("USER lado")
    for name in ("python3", "python"):
        assert f'ln -s "$python" {PYTHON_FALLBACK}/{name}' in install, name
    assert f"{PYTHON_FALLBACK}/python3 --version" in install
    [made] = [line for line in lines() if line.startswith("RUN useradd")]
    [chown] = re.findall(r"chown lado:lado ([^&]*)", made)
    assert "/opt/uv/tools" in chown.split() and "/opt/uv/bin" in chown.split()
    assert "/opt/uv" not in chown.split() and "/opt/uv/python" not in chown.split()


def unpinned(text: str) -> list[str]:
    """Each FROM or COPY --from of `text` that names an image without a digest (a stage of
    the same file, `uv`, `node` or `mise`, is no image)."""
    bad = []
    for line in lines(text):
        m = re.match(r"(?:FROM\s+|COPY\s+(?:--\S+\s+)*--from=)(\S+)", line)
        if m and m.group(1) not in ("uv", "node", "mise") and "@sha256:" not in m.group(1):
            bad.append(line)
    return bad


def test_every_base_image_is_pinned_by_digest():
    assert unpinned(DOCKERFILE) == []


def test_an_unpinned_base_is_named():
    assert unpinned("FROM debian:bookworm-slim\n") == ["FROM debian:bookworm-slim"]
    assert unpinned("COPY --from=node:22-bookworm-slim /x /x\n") != []
    assert unpinned("COPY --chown=a:a --from=ghcr.io/x/y:1 /x /x\n") != []
    assert unpinned("FROM jdxcode/mise:2026.10.7 AS mise\n") == [
        "FROM jdxcode/mise:2026.10.7 AS mise"
    ]
    assert unpinned("COPY --from=mise /usr/local/bin/mise /usr/local/bin/mise\n") == []


def test_mise_comes_from_its_official_image_root_owned():
    """Copied before `USER lado`, so the binary is root's and `mise self-update` cannot
    replace it: the version is the pin's, which Dependabot moves with the other bases."""
    [stage] = [line for line in lines() if line.startswith("FROM jdxcode/mise:")]
    assert re.fullmatch(r"FROM jdxcode/mise:\d{4}\.\d+\.\d+@sha256:[0-9a-f]{64} AS mise", stage)
    copy = "COPY --from=mise /usr/local/bin/mise /usr/local/bin/mise"
    assert copy in lines()
    assert lines().index(copy) < lines().index("USER lado")


def test_the_image_carries_the_build_tools():
    [install] = [line for line in lines() if "apt-get install" in line and " tmux " in line]
    assert {"make", "gcc", "g++", "libc6-dev"} <= set(install.split())


MISE_TOML = DOCKER / "mise.toml"


def test_mise_reads_the_version_files_of_go_java_python_and_ruby_alone():
    """Not Node's (.nvmrc, .node-version): the image's Node 22 runs the agents and kits'
    MCP servers; a project's other Node goes through `mise exec`."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    settings = tomllib.loads(MISE_TOML.read_text())["settings"]
    assert settings["idiomatic_version_file_enable_tools"] == ["go", "java", "python", "ruby"]
    # go.mod's `go` line is a minimum, deprecated in mise and read with a warning on every call.
    assert settings["idiomatic_version_file_ignore_minimum_versions"] is True
    # The binary is the pin's: a newer release is the image's update, not the agents'.
    assert settings["disable_update_warning"] is True
    assert "COPY docker/mise.toml /etc/mise/config.toml" in lines()


def test_no_piped_install_script():
    assert not re.search(r"\|\s*(ba)?sh\b", DOCKERFILE)


def env() -> dict[str, str]:
    """The Dockerfile's ENV values (`K=V` pairs; a later ENV wins)."""
    found = {}
    for line in lines():
        if line.startswith("ENV "):
            for key, value in re.findall(r'(\w+)=("[^"]*"|\S+)', line[4:]):
                found[key] = value.strip('"')
    return found


def test_profile_sets_what_env_sets_for_the_agents():
    profile = (DOCKER / "profile.sh").read_text()
    exported = dict(re.findall(r'^export (\w+)="?([^"\n]*)"?$', profile, re.M))
    image = env()
    assert set(exported) == {
        "PATH",
        "LADO_CONTAINER",
        "CLAUDE_CONFIG_DIR",
        "DISABLE_AUTOUPDATER",
        "LANG",
        "LADO_ENV_DIR",
        "NPM_CONFIG_PREFIX",
        "MISE_TRUSTED_CONFIG_PATHS",
        "OPENSPEC_TELEMETRY",
        "OPENSPEC_NO_UPDATE_CHECK",
    }
    for key, value in exported.items():
        value = value.replace("$HOME", "/home/lado")
        if key == "PATH":
            # The image's programs first, so no shim shadows its Node or openspec; then the
            # agents' installs and mise's shims; last the image's python3, so a project's
            # Python through mise answers first.
            mine = "/opt/uv/bin:/opt/agents/bin:/opt/tools/bin:"
            after = ":" + ":".join([*AGENTS_PATH, PYTHON_FALLBACK])
            assert value == f"{mine}$PATH{after}"
            assert image["PATH"].startswith(mine) and image["PATH"].endswith(after)
            assert "/home/lado" not in image["PATH"][len(mine) : -len(after)]
            assert "/opt" not in image["PATH"][len(mine) : -len(after)]
        elif key == "MISE_TRUSTED_CONFIG_PATHS":
            # The container's own LADO_REPOS, which the ENV cannot follow.
            assert value == "$LADO_REPOS"
            assert key not in image
        else:
            assert image[key] == value, key
    assert image["LADO_CONTAINER"] == "1"
    # openspec's usage statistics and update check off: the human's choice.
    assert (image["OPENSPEC_TELEMETRY"], image["OPENSPEC_NO_UPDATE_CHECK"]) == ("0", "1")
    # The container's own LADO_REPOS (-e) reaches the agents through the entrypoint's
    # lado-repos.sh, so profile.sh does not set the image's default.
    assert image["LADO_REPOS"] == "/projects"
    assert image["LADO_PORT"] == "8765"
    assert image["SHELL"] == "/bin/bash"


AGENTS_PATH = ["/home/lado/.local/bin", "/home/lado/.local/share/mise/shims"]
INSTALL_DIRS = ["NPM_CONFIG_PREFIX", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR", "UV_PYTHON_INSTALL_DIR"]


def opt_installs(found: dict[str, str]) -> list[str]:
    """The variables of `found` that point an install at a folder under /opt."""
    return [key for key in INSTALL_DIRS if found.get(key, "").startswith("/opt")]


def test_no_install_goes_to_opt_at_run_time():
    """/opt stays uid 1000's after the entrypoint's uid change and a new image replaces it:
    the agents' and `docker exec`'s installs go to the home volume, ~/.local."""
    assert opt_installs(env()) == []
    assert env()["NPM_CONFIG_PREFIX"] == "/home/lado/.local"
    assert opt_installs({"UV_TOOL_DIR": "/opt/uv/tools"}) == ["UV_TOOL_DIR"]


def test_the_build_installs_lado_and_the_clis_under_opt():
    [lado] = [" ".join(line.split()) for line in lines() if "uv tool install" in line]
    assert lado.startswith(
        "RUN UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/opt/uv/bin "
        "UV_PYTHON_INSTALL_DIR=/opt/uv/python uv tool install "
    )


def test_the_image_reads_the_agents_variables_from_the_secrets_folder():
    """Set for the server and `docker exec` (ENV) and for every login shell (profile.sh),
    whose `lado mcp` spawns workers too; never `inherit`, which would give the agents the
    container's whole environment."""
    assert env()["LADO_ENV_DIR"] == "/run/secrets"
    assert "LADO_AGENT_ENV" not in DOCKERFILE + (DOCKER / "profile.sh").read_text()


def test_gh_is_gits_credential_helper_for_github():
    """What `gh auth setup-git` writes: an empty helper first drops any inherited one."""
    [run] = [line for line in lines() if "credential.https://github.com.helper" in line]
    assert "git config --system credential.https://github.com.helper ''" in run
    assert (
        "git config --system --add credential.https://github.com.helper "
        "'!/usr/bin/gh auth git-credential'"
    ) in run
    assert run.index("helper ''") < run.index("gh auth git-credential")


def test_the_server_listens_on_all_addresses_at_lado_port_under_tini():
    assert 'ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/lado-entrypoint"]' in lines()
    [cmd] = [line for line in lines() if line.startswith("CMD ")]
    assert cmd == 'CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \\"$LADO_PORT\\""]'
    assert "USER lado" in lines()


def test_the_build_context_is_an_allowlist():
    ignore = (DOCKER / "Dockerfile.dockerignore").read_text().split()
    assert ignore == [
        "*",
        "!dist/lado-*.whl",
        "!docker/profile.sh",
        "!docker/entrypoint.sh",
        "!docker/ssh-agent-socket.sh",
        "!docker/ssh_known_hosts",
        "!docker/ssh-agent-env.sh",
        "!docker/mise.toml",
    ]


def test_the_host_keys_are_githubs_public_keys_alone():
    """GitHub's published keys (api.github.com/meta, `ssh_keys`), one per type; no other
    host, no private key: the image holds no one's secrets."""
    text = (DOCKER / "ssh_known_hosts").read_text()
    entries = [line.split() for line in text.splitlines() if line and not line.startswith("#")]
    assert [host for host, *_ in entries] == ["github.com"] * 3
    assert sorted(kind for _, kind, *_ in entries) == [
        "ecdsa-sha2-nistp256",
        "ssh-ed25519",
        "ssh-rsa",
    ]
    assert all(len(entry) == 3 for entry in entries), entries
    assert "PRIVATE KEY" not in text


def test_the_image_knows_the_host_keys_system_wide():
    """root's, mode 644: no agent changes them, every user's ssh reads them."""
    assert "COPY --chmod=644 docker/ssh_known_hosts /etc/ssh/ssh_known_hosts" in lines()


SSH_RULE = "lado ALL=(root) NOPASSWD: /usr/local/bin/lado-ssh-agent-socket"
SSH_PROGRAM = DOCKER / "ssh-agent-socket.sh"
SOCKET = "/run/lado/ssh-agent.sock"


def test_the_ssh_rule_names_one_program_and_keeps_no_variable():
    """Its own file, which the first start's root phase leaves; no SETENV, so sudo's
    env_reset gives the program a clean environment."""
    [run] = [line for line in lines() if "/etc/sudoers.d/lado-ssh-agent" in line]
    assert f"printf '%s\\n' '{SSH_RULE}' > /etc/sudoers.d/lado-ssh-agent" in run
    assert "chmod 0440 /etc/sudoers.d/lado-ssh-agent" in run
    assert "visudo -cf /etc/sudoers.d/lado-ssh-agent" in run
    assert "SETENV" not in run
    assert "COPY --chmod=755 docker/ssh-agent-socket.sh /usr/local/bin/lado-ssh-agent-socket" in (
        lines()
    )
    # /run/lado is root's, so no agent can plant a file at the socket's path.
    assert "mkdir -p /run/lado" in run and "chmod 755 /run/lado" in run


def test_the_ssh_program_checks_its_one_socket():
    text = SSH_PROGRAM.read_text()
    assert text.startswith("#!/bin/sh\n") and "\nset -eu\n" in text
    assert "\nPATH=/usr/bin:/bin\n" in text
    assert f"\nSOCKET={SOCKET}\n" in text
    assert '[ -L "$SOCKET" ] || [ ! -S "$SOCKET" ]' in text
    assert '[ "$(stat -c %u "$SOCKET")" = 0 ] || exit 0' in text
    assert 'chown --no-dereference "$(id -u lado)" "$SOCKET"' in text
    assert text.index("stat -c %u") < text.index("chown")


def test_the_ssh_program_takes_no_argument():
    done = subprocess.run(["sh", str(SSH_PROGRAM), SOCKET], capture_output=True, text=True)
    assert (done.returncode, done.stderr) == (2, "lado-ssh-agent-socket: takes no argument\n")


@pytest.mark.skipif(Path(SOCKET).exists(), reason="the image's own socket")
def test_the_ssh_program_refuses_what_is_no_socket():
    done = subprocess.run(["sh", str(SSH_PROGRAM)], capture_output=True, text=True)
    assert (done.returncode, done.stderr) == (
        1,
        f"lado-ssh-agent-socket: {SOCKET} is not a socket\n",
    )


def test_compose_binds_the_ssh_agent_or_dev_null(compose):
    """/dev/null: no ssh agent, and a path every host has."""
    [mount] = [
        v
        for v in compose["services"]["lado"]["volumes"]
        if isinstance(v, dict) and v.get("target") == SOCKET
    ]
    assert mount == {
        "type": "bind",
        "source": "${LADO_SSH_AGENT:-/dev/null}",
        "target": SOCKET,
        "bind": {"create_host_path": False},
    }
    assert "group_add" not in compose["services"]["lado"]


SSH_ENV = DOCKER / "ssh-agent-env.sh"
SSH_PROFILE = "/etc/profile.d/lado-ssh-agent.sh"


def test_ssh_auth_sock_points_only_at_a_socket_in_one_file():
    """One rule: ssh-agent-env.sh, which every login shell reads (the agents) and the
    entrypoint sources (the server, whose clone and branch listing use git over ssh). Not
    in the ENV: an image cannot say whether compose bound a socket."""
    rule = f"[ -S {SOCKET} ] && export SSH_AUTH_SOCK={SOCKET} || true"
    assert rule in SSH_ENV.read_text().splitlines()
    assert "SSH_AUTH_SOCK" not in (DOCKER / "profile.sh").read_text()
    assert "SSH_AUTH_SOCK" not in env()
    assert f"COPY docker/ssh-agent-env.sh {SSH_PROFILE}" in lines()


def test_the_server_gets_ssh_auth_sock_after_the_socket_is_lados():
    """Sourced after the socket's owner is fixed, right before the command."""
    body = ENTRYPOINT.splitlines()
    # Read only when there: the unit tests run the entrypoint outside the image.
    sourced = body.index(f"if [ -r {SSH_PROFILE} ]; then . {SSH_PROFILE}; fi")
    assert sourced > max(i for i, line in enumerate(body) if "lado-ssh-agent-socket" in line)
    assert body[sourced + 1 :].count('exec "$@"') == 1


SSH_WARNING = "lado: warning: lado (uid $(id -u)) cannot use the ssh agent socket of uid $owner:"


def test_the_entrypoint_gives_a_root_owned_socket_to_lado_at_every_start():
    every = ENTRYPOINT.split('if [ -e "$MARK" ]', 1)[1].split("\nfi\n", 1)[1]
    assert f"SOCK={SOCKET}" in every
    assert "sudo -n /usr/local/bin/lado-ssh-agent-socket" in every
    assert every.index("may_become_root") < every.index("sudo -n /usr/local/bin/lado-ssh-agent")
    assert SSH_WARNING in every
    assert "ssh-add cannot connect" in every
    assert "no root to give it to lado (no-new-privileges or dropped capabilities)" in every


RULE = "lado ALL=(root) NOPASSWD:SETENV: /usr/local/bin/lado-entrypoint"
ENTRYPOINT = (DOCKER / "entrypoint.sh").read_text()


def test_the_entrypoint_is_copied_in_place():
    assert "COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/lado-entrypoint" in lines()
    assert ENTRYPOINT.startswith("#!/bin/sh\n")
    assert "\nset -eu\n" in ENTRYPOINT


def test_the_sudo_rule_names_the_entrypoint_alone():
    [run] = [line for line in lines() if "/etc/sudoers.d/lado-entrypoint" in line]
    assert f"printf '%s\\n' '{RULE}' > /etc/sudoers.d/lado-entrypoint" in run
    assert "chmod 0440 /etc/sudoers.d/lado-entrypoint" in run
    assert "visudo -cf /etc/sudoers.d/lado-entrypoint" in run
    assert "touch /etc/lado/first-start" in run
    [install] = [line for line in lines() if "apt-get install" in line and " tmux " in line]
    assert " sudo " in install


def test_git_trusts_every_repository():
    assert any("git config --system --add safe.directory '*'" in line for line in lines())


def test_the_entrypoint_removes_its_way_to_root_first():
    """The root branch deletes the sudo rule and the marker before any step that can fail,
    so no later process, an agent included, can become root through them."""
    body = ENTRYPOINT.split('if [ "$(id -u)" = 0 ]; then\n', 1)[1]
    first, second = (line.strip() for line in body.splitlines()[:2])
    assert first == f"PATH={ROOT_PATH}"
    assert second == 'if ! rm -f "$RULE" "$MARK"; then'
    assert "RULE=/etc/sudoers.d/lado-entrypoint" in ENTRYPOINT
    assert "MARK=/etc/lado/first-start" in ENTRYPOINT


ROOT_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def test_the_root_phase_takes_no_command_from_the_callers_path():
    """The sudo rule stays where the entrypoint was skipped, and SETENV lets its caller set
    any variable: the root phase runs on a fixed PATH and gives the caller's back only
    after the drop to lado."""
    root = ENTRYPOINT.split('if [ "$(id -u)" = 0 ]; then\n', 1)[1].split("\nfi\n", 1)[0]
    assert re.findall(r"^\s*(?:export\s+)?PATH\b.*$", root, re.M) == [f"    PATH={ROOT_PATH}"]
    [drop] = [line.strip() for line in root.splitlines() if "setpriv" in line]
    assert drop.startswith("exec /usr/bin/setpriv --reuid=lado --regid=lado --init-groups --")
    assert '/usr/bin/env PATH="$saved" "$SELF" "$@"' in drop


def test_the_entrypoint_writes_lado_repos_for_the_agents():
    assert "/etc/profile.d/lado-repos.sh" in ENTRYPOINT
    assert "export LADO_REPOS=" in ENTRYPOINT
    # The image's own, for a container that may not become root.
    assert any(
        """printf "export LADO_REPOS='/projects'\\n" > /etc/profile.d/lado-repos.sh""" in line
        for line in lines()
    )


def test_the_entrypoint_goes_on_without_root():
    """A container that may not become root (no-new-privileges, `--cap-drop`) does not try
    sudo: the first start checks first, so the server starts as uid 1000."""
    phase1 = ENTRYPOINT.split('if [ -e "$MARK" ]', 1)[1].split("\nfi\n", 1)[0]
    assert phase1.index("if ! may_become_root; then") < phase1.index("exec sudo -E -n")
    assert phase1.index("elif read_only_root; then") < phase1.index("exec sudo -E -n")
    assert "NoNewPrivs:\t1" in ENTRYPOINT


GIT_WARNING = (
    "lado: warning: git has no user.name or user.email: agents cannot commit; set "
    "LADO_GIT_NAME and LADO_GIT_EMAIL"
)


def every_start(tmp_path, **given: str) -> subprocess.CompletedProcess:
    """The entrypoint's every-start phase run here (no marker, not root), with a home of
    its own and `given` in a clean environment; its command prints git's identity."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    environ = {"PATH": os.environ["PATH"], "HOME": str(home), "LADO_REPOS": str(tmp_path)}
    return subprocess.run(
        [
            "sh",
            str(DOCKER / "entrypoint.sh"),
            "sh",
            "-c",
            "git config user.name; git config user.email; true",
        ],
        env={**environ, **given},
        cwd=home,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.skipif(
    os.geteuid() == 0 or Path("/etc/lado/first-start").exists(), reason="the image's own phases"
)
def test_the_entrypoint_writes_gits_identity_at_every_start(tmp_path):
    """As one argument each, never split or evaluated; a later start takes a new value."""
    done = every_start(tmp_path, LADO_GIT_NAME="Ann O'Lee $(x)", LADO_GIT_EMAIL="ann@example.com")
    assert done.stdout == "Ann O'Lee $(x)\nann@example.com\n"
    assert GIT_WARNING not in done.stderr
    done = every_start(tmp_path, LADO_GIT_EMAIL="ann@other.example")
    assert done.stdout == "Ann O'Lee $(x)\nann@other.example\n"
    assert done.stderr == ""


@pytest.mark.skipif(
    os.geteuid() == 0 or Path("/etc/lado/first-start").exists(), reason="the image's own phases"
)
def test_without_gits_identity_the_entrypoint_warns_and_goes_on(tmp_path):
    done = every_start(tmp_path)
    assert GIT_WARNING in done.stderr.splitlines()
    done = every_start(tmp_path, LADO_GIT_NAME="Ann", LADO_GIT_EMAIL="")
    assert GIT_WARNING in done.stderr.splitlines()
    assert done.stdout == "Ann\n"


COMPOSE_TEXT = (DOCKER / "compose.yaml").read_text()


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_TEXT)


def test_compose_binds_the_secrets_folder_read_only_and_never_makes_it(compose):
    """No secrets by default, as no ssh agent (/dev/null, which LADO takes as none). A
    folder LADO_SECRETS names but that is missing: Docker on Linux would make it as root,
    where the human could not add a file without sudo, so compose refuses instead."""
    [mount] = [
        v
        for v in compose["services"]["lado"]["volumes"]
        if isinstance(v, dict) and v.get("target") == "/run/secrets"
    ]
    assert mount == {
        "type": "bind",
        "source": "${LADO_SECRETS:-/dev/null}",
        "target": "/run/secrets",
        "read_only": True,
        "bind": {"create_host_path": False},
    }


def test_compose_passes_the_git_identity_and_no_secret(compose):
    """No value for the agents goes through `environment:`, which docker inspect shows."""
    environment = compose["services"]["lado"]["environment"]
    assert environment["LADO_GIT_NAME"] == "${LADO_GIT_NAME:-}"
    assert environment["LADO_GIT_EMAIL"] == "${LADO_GIT_EMAIL:-}"
    assert set(environment) == {
        "LADO_PORT",
        "LADO_REPOS",
        "LADO_GIT_NAME",
        "LADO_GIT_EMAIL",
        "LADO_LISTEN",
        "LADO_PUBLIC_HOST",
    }
    assert "env_file" not in compose["services"]["lado"]


def test_compose_publishes_one_port_number_on_lado_listen(compose):
    """On loopback unless .env says otherwise; the container learns where from LADO_LISTEN,
    and the name for the link from LADO_PUBLIC_HOST (share-access)."""
    lado = compose["services"]["lado"]
    assert lado["ports"] == ["${LADO_LISTEN:-127.0.0.1}:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]
    assert lado["environment"]["LADO_PORT"] == "${LADO_PORT:-8765}"
    assert lado["environment"]["LADO_LISTEN"] == "${LADO_LISTEN:-127.0.0.1}"
    assert lado["environment"]["LADO_PUBLIC_HOST"] == "${LADO_PUBLIC_HOST:-}"


def test_the_compose_header_names_the_settings_for_other_devices():
    text = " ".join(header_text().split())
    assert "LADO_LISTEN=0.0.0.0" in text and "LADO_PUBLIC_HOST=" in text
    assert "every device of your network" in text and "unencrypted" in text


def test_compose_names_no_container_and_keeps_home_on_its_volume(compose):
    lado = compose["services"]["lado"]
    assert "container_name" not in lado
    assert "build" not in lado
    assert lado["volumes"][0] == "home:/home/lado"


def test_compose_runs_the_published_image_of_lado_version(compose):
    """No default version: a compose file that took `latest` would leave the image before
    an update without a name. LADO_IMAGE wins (lado:local, the tests)."""
    assert compose["services"]["lado"]["image"] == (
        f"${{LADO_IMAGE:-{update.IMAGE}:${{LADO_VERSION:?set LADO_VERSION to the LADO "
        "version to run, e.g. in .env next to this file}}"
    )


WORKSPACE = "${LADO_WORKSPACE:-${LADO_PROJECTS:-/set-LADO_WORKSPACE-to-your-workspace-folder}}"


def test_compose_mounts_the_workspace_at_the_hosts_own_path(compose):
    """The same path inside as on the host, named by LADO_REPOS: git's worktree links and
    LADO's stored paths are then right on both sides. LADO_PROJECTS, the name before
    0.43.0, still counts; no nested `:?`, which Compose v2 on GitHub's runners evaluates
    even when LADO_WORKSPACE is set (LAD-73). A missing workspace is never made on the
    host: Docker refuses the bind, and its error names the placeholder's LADO_WORKSPACE."""
    lado = compose["services"]["lado"]
    assert lado["volumes"][0] == "home:/home/lado"
    assert lado["volumes"][1] == {
        "type": "bind",
        "source": WORKSPACE,
        "target": WORKSPACE,
        "bind": {"create_host_path": False},
    }
    assert all(isinstance(v, dict) for v in lado["volumes"][1:])  # the binds below
    assert lado["environment"]["LADO_REPOS"] == WORKSPACE


def test_the_compose_headers_commands_all_have_the_workspace_and_the_version():
    """Compose reads `${LADO_VERSION:?}` for every command (exec, logs, down too), and `up`
    needs the workspace, so the header sets both in .env, which compose reads, before its
    first `docker compose` line."""
    header = [line.lstrip("# ").strip() for line in COMPOSE_TEXT.splitlines()]
    first = next(i for i, line in enumerate(header) if line.startswith("docker compose"))
    env = [line.split("=")[0] for line in header[:first] if re.match(r"[A-Z_]+=\S", line)]
    assert {"LADO_WORKSPACE", "LADO_VERSION"} <= set(env), env
    assert "LADO_PROJECTS" not in env, env
    assert "in .env next to this file" in " ".join(header[:first])


def test_the_compose_header_still_accepts_lado_projects():
    """An installed .env with the name before 0.43.0 keeps working, and says so."""
    text = header_text()
    assert "LADO_PROJECTS" in text
    said = text.split("LADO_PROJECTS")[1][:200]
    assert "still accepted" in said and "LADO_WORKSPACE wins" in said, said


def header_steps(heading: str) -> list[str]:
    """The commands of compose.yaml's header after the paragraph that says `heading`, in
    order: the lines after that paragraph's end up to the next empty one."""
    lines = [line.lstrip("#").strip() for line in COMPOSE_TEXT.splitlines()]
    start = next(i for i, line in enumerate(lines) if heading in line)
    end = next(i for i in range(start, len(lines)) if not lines[i])
    first = next(i for i in range(end + 1, len(lines)) if lines[i])
    return lines[first : lines.index("", first)]


def way_back() -> list[str]:
    """The commands of compose.yaml's header that go back to the version before, once it
    is in .env again."""
    return header_steps("Back to the version you had before")


def header_text() -> str:
    return " ".join(line.lstrip("#").strip() for line in COMPOSE_TEXT.splitlines())


UPDATE = "To update, in this folder"
VERSION_COMPOSE = "https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml"
# A change made to compose.yaml by hand is kept beside it, never lost silently.
UPDATE_STEPS = [
    "cp compose.yaml compose.yaml.bak",
    f"curl -fLO {VERSION_COMPOSE}",
    "docker compose up -d",
]


def test_an_update_is_the_versions_compose_file_a_new_version_in_env_and_up():
    """A release may change compose.yaml (0.40.0 added git's identity, the ssh agent and
    the secrets folder): every update takes that version's. Compose pulls an image it does
    not have: the version's tag never moves, so the image before keeps its name and nothing
    needs keeping by hand."""
    assert header_steps(UPDATE) == UPDATE_STEPS
    update_text = header_text().split(UPDATE)[1].split("Back to the version")[0]
    assert "new LADO_VERSION in .env" in update_text
    assert ".env, secrets/ and the home volume stay" in update_text
    assert "carry it over" in update_text
    assert "diff compose.yaml.bak compose.yaml" in update_text
    assert "each LADO in its own folder" in update_text


def test_the_updates_address_is_the_release_asset_of_the_versions_tag():
    """The release workflow runs for the tag v<version> (it checks the tag against
    pyproject's version) and uploads docker/compose.yaml under its base name."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert '"v$version" != "$GITHUB_REF_NAME"' in workflow
    assert re.search(
        r'gh release create "\$GITHUB_REF_NAME" [^\n]*\bdocker/compose\.yaml\b', workflow
    )
    tag, asset = VERSION_COMPOSE.split("/releases/download/")[1].split("/")
    assert (tag, asset) == ("v<version>", "compose.yaml")


def test_the_way_back_keeps_the_newer_compose_file():
    """An older LADO ignores the mounts and variables it does not know."""
    assert "keep this compose.yaml" in header_text().split("Back to the version")[1]


def test_the_compose_header_says_how_to_go_back_to_the_backup():
    assert "put it back in .env" in header_text()
    down, restore, up = way_back()
    assert down == "docker compose down"
    assert restore.startswith("docker compose run --rm lado sh -c '")
    assert "rm -f lado.db-wal lado.db-shm" in restore
    assert "cp backups/lado.db.schema-<N> lado.db" in restore
    assert up == "docker compose up -d"


def test_a_second_lado_is_a_folder_with_its_own_env():
    """`-p` on each command is easy to forget; a folder's .env names the project once."""
    second = header_text().split("A second LADO beside the first")[1]
    for name in ("COMPOSE_PROJECT_NAME", "LADO_PORT", "LADO_VERSION", "LADO_WORKSPACE"):
        assert name in second, name
    assert " -p " not in header_text()


def test_the_dockerfiles_header_names_the_published_image_and_its_update():
    header = " ".join(
        line.lstrip("#").strip() for line in DOCKERFILE.splitlines() if line.startswith("#")
    )
    assert f"{update.IMAGE}:<version>" in header
    for words in ("Update:", "Back:", "A second LADO:"):
        assert words in header, words


def test_the_compose_header_says_the_sessions_follow_the_container():
    text = header_text()
    for words in (
        "docker compose down",
        "stops its sessions",
        "docker compose up -d",
        "resumes them",
        "stopped by hand",
        "one model turn",
    ):
        assert words in text.split("The container's sessions")[1], words


def test_the_dockerfiles_header_says_the_sessions_follow_the_container():
    header = " ".join(
        line.lstrip("#").strip() for line in DOCKERFILE.splitlines() if line.startswith("#")
    )
    sessions = header.split("Sessions:")[1]
    for words in ("docker stop", "docker start", "stopped by hand", "one model turn"):
        assert words in sessions, words


def leading_comment(path: Path) -> str:
    """A file's header: its comment lines before the first other line."""
    head = []
    for line in path.read_text().splitlines():
        if not line.startswith("#"):
            break
        head.append(line.lstrip("#").strip())
    return " ".join(head)


@pytest.mark.parametrize("name", ["compose.yaml", "Dockerfile"])
def test_the_headers_say_how_agents_get_variables_access_and_logins(name):
    head = leading_comment(DOCKER / name)
    for needle in (
        "mkdir -m 700 secrets",
        "LADO_GIT_NAME",
        "LADO_GIT_EMAIL",
        "GH_TOKEN",
        "gh auth login",
        "LADO_SSH_AGENT" if name == "compose.yaml" else "/run/lado/ssh-agent.sock",
        "/run/host-services/ssh-auth.sock",
        "$SSH_AUTH_SOCK",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "claude setup-token",
        "opencode auth login",
        "kilo auth login",
        "Every agent of the container can read every variable given to it",
        "LADO_SECRETS=./secrets" if name == "compose.yaml" else '-v "$PWD/secrets:/run/secrets:ro"',
    ):
        assert needle in head, (name, needle)


def dockerfile_run() -> list[str]:
    """The commands of the Dockerfile header's `docker run`."""
    header = [line[1:].strip() for line in DOCKERFILE.splitlines() if line.startswith("#")]
    start = next(i for i, line in enumerate(header) if line.endswith("One command starts it:")) + 2
    return commands("\n".join(header[start : header.index("", start)]))


def test_the_minimal_start_makes_no_folder():
    """The secrets folder is optional: neither header's first start has a mkdir."""
    first = [without_comment(line) for line in header_steps("Then, from this folder")]
    run = dockerfile_run()
    assert first and run
    assert not [step for step in [*first, *run] if step.startswith("mkdir")]
    assert "/run/secrets" not in " ".join(run)


def test_the_compose_header_sets_the_new_settings_in_env():
    header = [line.lstrip("# ").strip() for line in COMPOSE_TEXT.splitlines()]
    first = next(i for i, line in enumerate(header) if line.startswith("docker compose"))
    settings = " ".join(header[:first])
    for key in ("LADO_GIT_NAME=", "LADO_GIT_EMAIL=", "LADO_SSH_AGENT="):
        assert key in settings, key


def test_nothing_in_docker_names_lado_previous():
    """One name per machine, which a second LADO overwrote (LAD-71's G2): a version's tag
    names the image before an update instead."""
    for path in DOCKER.iterdir():
        if path.is_file():
            assert "lado:previous" not in path.read_text(), path


def test_compose_mounts_nothing_only_docker_desktop_has(compose):
    assert "/run/host-services" not in str(compose)
    assert "group_add" not in compose["services"]["lado"]


def test_dependabot_updates_the_images_bases():
    updates = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())["updates"]
    [docker] = [u for u in updates if u["package-ecosystem"] == "docker"]
    assert docker["directory"] == "/docker"
    assert docker["cooldown"] == {"default-days": 7}


# The install guide's Docker section (openspec change docker-install-guide): it repeats only
# the steps a user runs, and these tests keep them the headers' (which the container tests
# run).

INSTALL = ROOT / "docs" / "install.md"


def guide() -> str:
    """docs/install.md's `## Docker` section, up to the next `## `."""
    text = INSTALL.read_text()
    start = text.index("\n## Docker\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def blocks(text: str, lang: str = "bash") -> list[str]:
    return re.findall(rf"^ *```{lang}\n(.*?)^ *```", text, flags=re.S | re.M)


def commands(block: str) -> list[str]:
    """A block's commands: continuation lines joined, a trailing `# comment` left out."""
    joined = re.sub(r"\\\n\s*", "", block)
    lines = (re.sub(r"\s+#\s.*$", "", line).strip() for line in joined.splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def guide_part(heading: str) -> str:
    """The guide's text under `### <heading>`, up to the next heading of that level."""
    text = guide()
    start = text.index(f"\n### {heading}\n")
    end = text.find("\n### ", start + 1)
    return text[start : end if end != -1 else len(text)]


def guide_steps(heading: str) -> list[str]:
    """The commands of the bash blocks under `### <heading>`, in order."""
    return [line for block in blocks(guide_part(heading)) for line in commands(block)]


def without_comment(line: str) -> str:
    return re.sub(r"\s+#\s.*$", "", line).strip()


def test_the_guides_first_start_is_the_headers():
    first = [without_comment(line) for line in header_steps("Then, from this folder")]
    assert first == [
        "docker compose up -d",
        "docker compose exec lado lado ui --no-open",
    ]
    assert guide_steps("Start") == first


def test_the_guides_update_and_way_back_are_the_headers():
    assert guide_steps("Update the container") == header_steps(UPDATE)
    assert guide_steps("Go back to the version before") == way_back()


def test_the_guide_enables_secrets_as_a_step_of_its_own():
    variables = guide_part("The agents' variables")
    assert "LADO_SECRETS=./secrets" in variables
    assert "mkdir -m 700 secrets" in guide_steps("The agents' variables")
    assert "mkdir" not in " ".join(guide_steps("Start"))


def test_the_guides_update_says_what_stays_and_what_to_carry_over():
    text = " ".join(guide_part("Update the container").split())
    assert guide_steps("Update the container") == UPDATE_STEPS
    assert "`.env`, `secrets/` and the home volume stay" in text
    assert "carry it over" in text
    assert "diff compose.yaml.bak compose.yaml" in text
    assert "in its own folder, with its own `.env`" in text
    assert "keeps the `compose.yaml` you have" in " ".join(
        guide_part("Go back to the version before").split()
    )


def readme_part(heading: str, sub: str) -> str:
    """README's `### <sub>` under `## <heading>`."""
    text = (ROOT / "README.md").read_text()
    part = text[text.index(f"\n## {heading}\n") :]
    part = part[: part.index("\n## ", 3)]
    part = part[part.index(f"\n### {sub}\n") :]
    end = part.find("\n### ", 3)
    return part if end == -1 else part[:end]


def test_readmes_docker_install_starts_without_mkdir():
    steps = [line for block in blocks(readme_part("Install", "Docker")) for line in commands(block)]
    assert "docker compose up -d" in steps
    assert [s for s in steps if s.startswith("mkdir")] == [
        "mkdir ~/lado-docker && cd ~/lado-docker"
    ]


def test_readmes_docker_install_checks_the_shell_first():
    """A shell's LADO_VERSION beats .env's and ran a manual check on the wrong version
    twice (LAD-69, LAD-73): README's start looks first, as the guide's does."""
    steps = [line for block in blocks(readme_part("Install", "Docker")) for line in commands(block)]
    look = steps.index("env | grep -E '^(LADO|COMPOSE)_'")
    [unset] = [i for i, step in enumerate(steps) if step.startswith("unset ")]
    assert {"LADO_VERSION", "COMPOSE_PROJECT_NAME"} <= set(steps[unset].split())
    assert max(look, unset) < steps.index("docker compose up -d")


def test_readmes_update_downloads_the_versions_compose_file_first():
    steps = [line for block in blocks(readme_part("Update", "Docker")) for line in commands(block)]
    assert steps == UPDATE_STEPS


def test_the_guide_downloads_the_release_asset():
    assert (
        "curl -fLO https://github.com/ladohq/lado/releases/latest/download/compose.yaml"
        in guide_steps("Get compose.yaml and write .env")
    )


def test_the_guides_env_names_every_variable_compose_reads():
    # LADO_PROJECTS: the name before LADO_WORKSPACE, still read, not one to write.
    read = set(re.findall(r"\$\{([A-Z_]+)", COMPOSE_TEXT)) - {
        "LADO_IMAGE",
        "LADO_SECRETS",
        "LADO_PROJECTS",
    }
    assert {"LADO_VERSION", "LADO_WORKSPACE", "LADO_SSH_AGENT"} <= read
    envs = blocks(guide_part("Get compose.yaml and write .env"), "ini")
    assert len(envs) == 2  # a Mac's and Linux's
    for env_file in envs:
        # An optional setting may be there commented out: `# LADO_LISTEN=0.0.0.0`.
        lines = (line.removeprefix("# ") for line in env_file.splitlines())
        named = {line.split("=")[0] for line in lines if re.match(r"[A-Z_]+=", line)}
        assert named == read, env_file


def test_the_guide_makes_the_workspace_before_compose_needs_it():
    """Compose never makes a missing workspace (`create_host_path: false`), so the guide
    makes it, and its troubleshooting reads Docker's refusal for any path, not only the
    placeholder's."""
    envs = blocks(guide_part("Get compose.yaml and write .env"), "ini")
    for env_file in envs:
        [workspace] = re.findall(r"^LADO_WORKSPACE=(\S+)", env_file, flags=re.M)
        assert workspace.endswith("/workspace"), env_file
    assert "mkdir -p ~/workspace" in guide_steps("Get compose.yaml and write .env")
    said = " ".join(guide_part("Get compose.yaml and write .env").split())
    assert "compose never makes it" in said, said
    trouble = " ".join(guide_part("If something goes wrong in Docker").split())
    assert "**`bind source path does not exist: <path>`**" in trouble, trouble
    line = trouble.split("bind source path does not exist: <path>")[1][:500]
    assert "/set-LADO_WORKSPACE-to-your-workspace-folder" in line, line
    assert "mkdir -p" in line, line


def test_the_guide_says_how_to_open_lado_on_a_phone():
    phone = " ".join(guide_part("Open LADO on your phone").split())
    for said in (
        "LADO_LISTEN=0.0.0.0",
        "LADO_PUBLIC_HOST=",
        "LADO_LISTEN=192.168.1.23",
        "docker compose up -d",
        "Open on another device",
        "unencrypted",
        "every network",
        "New link",
    ):
        assert said in phone, said


def test_the_guide_removes_only_its_own_container_and_volume():
    steps = guide_steps("Remove it")
    assert steps[0] == "docker compose down"
    assert any(re.fullmatch(r"docker volume rm [\w.-]+_home", step) for step in steps), steps
    # Docker's name filter matches a part of the name unless anchored.
    assert any(re.fullmatch(r"docker volume ls --filter name='\^[\w.-]+_home\$'", s) for s in steps)
    assert not [s for s in steps if "--volumes" in s or re.search(r"down .*-v\b", s)]


def test_nothing_written_for_users_prunes():
    """Docker's prune takes other containers' and volumes' too: a second LADO's, anyone's.
    What users read: README.md, the guides in docs/ and docker/ (docs/research/ and
    docs/superpowers/ are records, whose plans only forbid it)."""
    paths = [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *DOCKER.iterdir()]
    found = [p for p in paths if p.is_file() and "prune" in p.read_text()]
    assert found == []


def test_the_guide_says_to_check_the_shells_variables_first():
    steps = guide_steps("Check the shell")
    assert "env | grep -E '^(LADO|COMPOSE)_'" in steps
    [unset] = [step for step in steps if step.startswith("unset ")]
    # The same kinds the grep finds: a COMPOSE_ variable beats .env as a LADO_ one does.
    assert "COMPOSE_PROJECT_NAME" in unset.split() and "LADO_VERSION" in unset.split()


def test_the_first_session_names_claude_codes_trust_question(tmp_path):
    """The container's Claude Code has trusted no folder yet: LADO records the trust, and
    the guide says so and what that runs. When it cannot (here a home it cannot write), the
    guide quotes the answers as LADO's own reason for the wait words them, so Needs you and
    the guide agree."""
    repo, home = tmp_path / "repo", tmp_path / "home"
    home.mkdir(mode=0o500)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    try:
        reason = ClaudeProvider().first_hook_blocker(str(repo), {"HOME": str(home)}).reason
    finally:
        home.chmod(0o700)
    assert "LADO could not record the trust" in reason
    text = " ".join(guide_part("Your first session").split())
    assert "LADO records Claude Code's trust" in text
    assert "`.claude/`" in text and "`.mcp.json`" in text
    assert "Needs you" in text
    for answer in ('"Yes, I trust this folder"', '"No, exit"'):
        assert answer in text and answer in reason, answer


def test_the_guides_docker_run_is_the_dockerfiles():
    assert guide_steps("With docker run") == dockerfile_run()


def test_readme_and_the_headers_point_to_the_guide():
    readme = (ROOT / "README.md").read_text()
    install = readme[readme.index("## Install") :]
    assert "docs/install.md#docker" in install[: install.index("\n## ", 3)]
    assert "- [Docker](#docker)" in INSTALL.read_text()
    for name in ("compose.yaml", "Dockerfile"):
        assert "docs/install.md#docker" in leading_comment(DOCKER / name), name


def test_docker_is_the_first_and_recommended_way_to_install():
    """The human's choice (2026-10-16): Docker first, PyPI the other way."""
    readme = (ROOT / "README.md").read_text()
    install = readme[readme.index("## Install") :]
    install = install[: install.index("\n## ", 3)]
    assert "**Docker** (recommended)" in install
    assert install.index("### Docker") < install.index("### PyPI")
    text = INSTALL.read_text()
    opening = text[: text.index("\n## ")]
    assert "**Docker**, the recommended one, and **PyPI**" in opening
    assert text.index("\n## Docker\n") < text.index("\n## macOS\n")


def test_update_says_both_ways_docker_first():
    """The human's comment (2026-10-16): how to update is clear for Docker and for PyPI."""
    readme = (ROOT / "README.md").read_text()
    update_part = readme[readme.index("\n## Update\n") :]
    update_part = update_part[: update_part.index("\n## ", 3)]
    assert update_part.index("### Docker") < update_part.index("### PyPI")
    assert "docker compose up -d" in update_part and "lado update" in update_part
    text = INSTALL.read_text()
    update_part = text[text.index("\n## Update\n") :]
    update_part = update_part[: update_part.index("\n## ", 3)]
    assert "[Update the container](#update-the-container)" in update_part
    assert "- **PyPI**: `lado update`" in update_part


def test_no_example_names_a_version_that_goes_stale():
    """A version written in an example is out of date at the next release: the examples
    say <version>, and the text where to find it."""
    paths = [ROOT / "README.md", INSTALL, DOCKER / "compose.yaml", DOCKER / "Dockerfile"]
    for path in paths:
        assert not re.search(r"LADO_VERSION=\d", path.read_text()), path
        assert not re.search(r"ghcr\.io/ladohq/lado:\d", path.read_text()), path
