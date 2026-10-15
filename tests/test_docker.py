"""docker/: LADO's image (openspec capability container): the four agent CLIs at their pins
and no other npm package, Node 22 from the official image, bases pinned by digest, no piped
install script, the environment the same for the server (ENV) and the agents' login shells
(profile.sh), the build context an allowlist, compose's one port number and its image by
LADO_VERSION, and the headers' update by version."""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from lado import update

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
    packages = {pin[0] for pin in _pins().values()}
    installs = [line for line in lines() if "npm install" in line]
    assert len(installs) == len(packages), installs
    for line in installs:
        named = re.findall(r'"(@?[^"@]+)@[^"]*"', line)
        assert named and set(named) <= packages, line


def unpinned(text: str) -> list[str]:
    """Each FROM or COPY --from of `text` that names an image without a digest (a stage of
    the same file, `uv` or `node`, is no image)."""
    bad = []
    for line in lines(text):
        m = re.match(r"(?:FROM\s+|COPY\s+(?:--\S+\s+)*--from=)(\S+)", line)
        if m and m.group(1) not in ("uv", "node") and "@sha256:" not in m.group(1):
            bad.append(line)
    return bad


def test_every_base_image_is_pinned_by_digest():
    assert unpinned(DOCKERFILE) == []


def test_an_unpinned_base_is_named():
    assert unpinned("FROM debian:bookworm-slim\n") == ["FROM debian:bookworm-slim"]
    assert unpinned("COPY --from=node:22-bookworm-slim /x /x\n") != []
    assert unpinned("COPY --chown=a:a --from=ghcr.io/x/y:1 /x /x\n") != []


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
    }
    for key, value in exported.items():
        value = value.replace("$HOME", "/home/lado")
        if key == "PATH":
            assert value == "/opt/uv/bin:/opt/agents/bin:$PATH"
            assert image["PATH"].startswith("/opt/uv/bin:/opt/agents/bin:")
        else:
            assert image[key] == value, key
    assert image["LADO_CONTAINER"] == "1"
    # The container's own LADO_REPOS (-e) reaches the agents through the entrypoint's
    # lado-repos.sh, so profile.sh does not set the image's default.
    assert image["LADO_REPOS"] == "/projects"
    assert image["LADO_PORT"] == "8765"
    assert image["SHELL"] == "/bin/bash"


def test_the_server_listens_on_all_addresses_at_lado_port_under_tini():
    assert 'ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/lado-entrypoint"]' in lines()
    [cmd] = [line for line in lines() if line.startswith("CMD ")]
    assert cmd == 'CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \\"$LADO_PORT\\""]'
    assert "USER lado" in lines()


def test_the_build_context_is_an_allowlist():
    ignore = (DOCKER / "Dockerfile.dockerignore").read_text().split()
    assert ignore == ["*", "!dist/lado-*.whl", "!docker/profile.sh", "!docker/entrypoint.sh"]


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
    [install] = [line for line in lines() if "apt-get install" in line]
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


COMPOSE_TEXT = (DOCKER / "compose.yaml").read_text()


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_TEXT)


def test_compose_publishes_one_port_number_on_loopback(compose):
    lado = compose["services"]["lado"]
    assert lado["ports"] == ["127.0.0.1:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]
    assert lado["environment"]["LADO_PORT"] == "${LADO_PORT:-8765}"


def test_compose_names_no_container_and_needs_the_projects_folder(compose):
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


def test_compose_mounts_the_projects_at_the_hosts_own_path(compose):
    """The same path inside as on the host, named by LADO_REPOS: git's worktree links and
    LADO's stored paths are then right on both sides."""
    lado = compose["services"]["lado"]
    projects = "${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}"
    assert lado["volumes"] == ["home:/home/lado", f"{projects}:{projects}"]
    assert lado["environment"]["LADO_REPOS"] == projects


def test_the_compose_headers_commands_all_have_the_projects_folder_and_the_version():
    """Compose reads `${LADO_PROJECTS:?}` and `${LADO_VERSION:?}` for every command (exec,
    logs, down too), so the header sets both in .env, which compose reads, before its
    first `docker compose` line."""
    header = [line.lstrip("# ").strip() for line in COMPOSE_TEXT.splitlines()]
    first = next(i for i, line in enumerate(header) if line.startswith("docker compose"))
    env = [line.split("=")[0] for line in header[:first] if re.match(r"[A-Z_]+=\S", line)]
    assert {"LADO_PROJECTS", "LADO_VERSION"} <= set(env), env
    assert "in .env next to this file" in " ".join(header[:first])


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


def test_an_update_is_a_new_version_in_env_and_up():
    """Compose pulls an image it does not have: the version's tag never moves, so the image
    before keeps its name and nothing needs keeping by hand."""
    assert header_steps("To update, set the new LADO_VERSION in .env") == ["docker compose up -d"]


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
    for name in ("COMPOSE_PROJECT_NAME", "LADO_PORT", "LADO_VERSION", "LADO_PROJECTS"):
        assert name in second, name
    assert " -p " not in header_text()


def test_the_dockerfiles_header_names_the_published_image_and_its_update():
    header = " ".join(
        line.lstrip("#").strip() for line in DOCKERFILE.splitlines() if line.startswith("#")
    )
    assert f"{update.IMAGE}:<version>" in header
    for words in ("Update:", "Back:", "A second LADO:"):
        assert words in header, words


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
