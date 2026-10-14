"""docker/: LADO's image (openspec capability container): Claude Code at its pin and no other
CLI, Node 22 from the official image, bases pinned by digest, no piped install script, the
environment the same for the server (ENV) and the agents' login shells (profile.sh), the
build context an allowlist, and compose's one port number."""

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


def lines(text: str = DOCKERFILE) -> list[str]:
    """The Dockerfile's instructions, continuation lines joined, comments left out."""
    joined = re.sub(r"\\\n", " ", text)
    return [
        line.strip()
        for line in joined.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_claude_codes_default_is_its_pin():
    [arg] = [line for line in lines() if line.startswith("ARG CLAUDE_VERSION=")]
    pinned = _pins()["claude"][1]
    assert arg == f"ARG CLAUDE_VERSION={pinned}", f"Dockerfile {arg}, PINS {pinned}"


def test_claude_code_is_installed_at_that_version():
    [install] = [line for line in lines() if "npm install -g" in line]
    assert '"@anthropic-ai/claude-code@${CLAUDE_VERSION}"' in install


def test_node_22_comes_from_the_official_image():
    [stage] = [line for line in lines() if line.startswith("FROM node:")]
    assert stage.startswith("FROM node:22-bookworm-slim@sha256:")
    assert stage.endswith(" AS node")


def test_no_other_agent_cli():
    for package, _, command in _pins().values():
        if package != "@anthropic-ai/claude-code":
            assert package not in DOCKERFILE
            assert not re.search(rf"\b{command}\b", DOCKERFILE), command


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
        "LADO_REPOS",
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
    assert image["LADO_PORT"] == "8765"
    assert image["SHELL"] == "/bin/bash"


def test_the_server_listens_on_all_addresses_at_lado_port_under_tini():
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in lines()
    [cmd] = [line for line in lines() if line.startswith("CMD ")]
    assert cmd == 'CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \\"$LADO_PORT\\""]'
    assert "USER lado" in lines()


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
    assert "build" not in lado
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
