"""docker/install.sh with real Docker (openspec capability docker-installer): a fresh
install whose printed link answers, a rerun of the same version that changes no file, an
update from an older version that keeps the user's lines, and the phone's link. The
script takes compose.yaml from the working copy (--source) and runs the image under test
(--image); its folder and compose project carry this run's prefix (the `installed`
fixture). Every other requirement is tests/test_install_sh.py's, with fakes."""

import re
import urllib.request

import pytest
from container_helpers import IMAGE, ROOT

import lado

pytestmark = pytest.mark.container

LINK = re.compile(r"LADO \S+ runs: (http://127\.0\.0\.1:\d+/\?token=\S+)")


def install(installed, *args: str) -> str:
    """install.sh run for the folder; its link, once it answers 200 (its output kept as
    `installed.output`)."""
    done = installed.run(
        "--version", lado.__version__, "--source", str(ROOT / "docker"),
        "--image", IMAGE, "--dir", str(installed.folder), *args,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    found = LINK.search(done.stdout)
    assert found, done.stdout
    with urllib.request.urlopen(found[1], timeout=10) as answer:
        assert answer.status == 200
    installed.output = done.stdout
    return found[1]


def test_a_fresh_install_answers_its_link(installed):
    link = install(installed)
    env = installed.env()
    assert env["COMPOSE_PROJECT_NAME"] == f"lado-{installed.folder.name}"
    assert env["LADO_VERSION"] == lado.__version__
    assert env["LADO_WORKSPACE"] == str(installed.home / "workspace")
    assert (installed.home / "workspace").is_dir()
    assert f":{env['LADO_PORT']}/" in link
    assert "cannot commit" in installed.output  # the home has no git identity


def test_a_rerun_of_the_same_version_changes_nothing(installed):
    first = install(installed)
    files = ("compose.yaml", ".env")
    before = {name: (installed.folder / name).read_bytes() for name in files}
    assert install(installed) == first  # the token stays on the home volume
    assert {name: (installed.folder / name).read_bytes() for name in files} == before
    assert not (installed.folder / "compose.yaml.bak").exists()


def test_an_older_env_is_updated_and_keeps_its_lines(installed):
    install(installed)
    path = installed.folder / ".env"
    old = path.read_text().replace(f"LADO_VERSION={lado.__version__}", "LADO_VERSION=0.0.1")
    path.write_text(old + "# mine\n")
    compose = (installed.folder / "compose.yaml").read_text()
    install(installed)
    assert (installed.folder / "compose.yaml.bak").read_text() == compose
    text = path.read_text()
    assert f"LADO_VERSION={lado.__version__}\n" in text and text.endswith("# mine\n")
    assert "Updated LADO 0.0.1" in installed.output


def test_phone_prints_the_other_devices_link(installed):
    install(installed)
    install(installed, "--phone")
    env = installed.env()
    assert env["LADO_LISTEN"] == "0.0.0.0" and env["LADO_PUBLIC_HOST"]
    host = env["LADO_PUBLIC_HOST"]
    assert f"On your phone: http://{host}:{env['LADO_PORT']}/?token=" in installed.output
