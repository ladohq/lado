"""`lado model-server add|list|remove` and `lado model add|list|remove` across processes
(openspec change model-settings): the real commands against the fake model server in a
process of its own (tests/fake_model_server.py). A canary key piped in reaches the server
and its own key file, and nothing else: no output, no other file under LADO_HOME, lado.db
and the error journal included; it goes with its server."""

import os
import stat
import uuid
from pathlib import Path

import pytest
from test_model_server_probe import closed_port, lado, serve  # noqa: F401 - a fixture

pytestmark = pytest.mark.integration


def _files(home: Path) -> list[Path]:
    return [Path(folder) / name for folder, _, names in os.walk(home) for name in names]


def test_add_list_remove_a_server_and_a_model(serve):  # noqa: F811
    url = serve("lmstudio", key="k-lab")
    added = lado("model-server", "add", "LM Studio дома", url, "--key", stdin="k-lab\n")
    assert added.returncode == 0, added.stderr
    assert added.stdout.splitlines()[-1] == 'Saved model server "LM Studio дома".'
    model = lado(
        "model", "add", "Локальная Qwen", "--cli", "opencode", "--model", "qwen3-8b",
        "--server", "lm studio ДОМА",
    )  # fmt: skip
    assert (model.returncode, model.stderr) == (0, "")
    assert model.stdout == (
        'Saved model "Локальная Qwen": OpenCode, qwen3-8b on LM Studio дома (in LM Studio '
        "дома's list of models)\n"
    )
    servers = lado("model-server", "list")
    assert servers.stdout.splitlines()[1].split("  ")[0] == "LM Studio дома"
    assert " yes  " in servers.stdout.splitlines()[1]
    models = lado("model", "list")
    assert models.stdout.splitlines()[1].split() == [
        "Локальная", "Qwen", "OpenCode", "qwen3-8b", "LM", "Studio", "дома",
    ]  # fmt: skip
    used = lado("model-server", "remove", "LM Studio дома")
    assert used.returncode == 1
    assert "is used by the models Локальная Qwen" in used.stderr
    assert lado("model", "remove", "Локальная Qwen").returncode == 0
    removed = lado("model-server", "remove", "LM Studio дома")
    assert (removed.returncode, removed.stdout) == (0, 'Removed model server "LM Studio дома".\n')
    assert lado("model-server", "list").stdout.startswith("No model servers.")


def test_the_key_canary(serve, lado_home):  # noqa: F811
    canary = f"canary-key-{uuid.uuid4().hex}"
    url = serve("openai", key=canary)
    runs = [lado("model-server", "add", "work", url, "--key", stdin=canary)]
    assert runs[0].returncode == 0, runs[0].stderr
    [key_file] = [p for p in _files(lado_home) if canary.encode() in p.read_bytes()]
    assert key_file.parent.parent == lado_home / "model-servers"
    assert key_file.name == "key"
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700
    runs.append(lado("model-server", "add", "work", url, "--replace"))  # the kept key
    assert runs[-1].returncode == 0, runs[-1].stderr
    runs.append(
        lado("model", "add", "W", "--cli", "kilo", "--model", "gpt-oss-20b", "--server", "work")
    )
    assert runs[-1].returncode == 0, runs[-1].stderr
    runs.append(lado("model-server", "list"))
    runs.append(lado("model", "list"))
    runs.append(lado("doctor"))
    assert "work answers (OpenAI-compatible)" in runs[-1].stdout
    refused = lado(
        "model-server", "add", "work", url, "--key", "--replace", stdin="wrong-" + canary
    )
    assert refused.returncode == 1
    runs.append(refused)
    for done in runs:
        assert canary not in done.stdout + done.stderr
    for path in _files(lado_home):
        if path != key_file:
            assert canary.encode() not in path.read_bytes(), path
    # A new key the server (moved) takes replaces the old one in the same file, private.
    second = f"canary-key-{uuid.uuid4().hex}"
    moved = serve("openai", key=second)
    replaced = lado("model-server", "add", "work", moved, "--key", "--replace", stdin=second)
    assert replaced.returncode == 0, replaced.stderr
    assert replaced.stdout.splitlines()[-1] == 'Replaced model server "work".'
    assert key_file.read_text() == second
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700
    checked = lado("doctor")
    assert "work answers (OpenAI-compatible)" in checked.stdout
    for done in (replaced, checked):
        assert second not in done.stdout + done.stderr
        assert canary not in done.stdout + done.stderr
    for path in _files(lado_home):
        assert canary.encode() not in path.read_bytes(), path  # the old key is gone
        if path != key_file:
            assert second.encode() not in path.read_bytes(), path
    assert lado("model", "remove", "W").returncode == 0
    assert lado("model-server", "remove", "work").returncode == 0
    assert not key_file.parent.exists()
    for path in _files(lado_home):
        assert canary.encode() not in path.read_bytes(), path
        assert second.encode() not in path.read_bytes(), path


def test_a_key_on_the_command_line_is_refused_unechoed(serve, lado_home):  # noqa: F811
    url = serve("openai")
    for given in (["--key", "s3cr3t"], ["--key", "-s3cr3t"], ["--help=s3cr3t"]):
        done = lado("model-server", "add", "work", url, *given)
        assert done.returncode in (0, 1)  # 0: --help=... printed the help (Python 3.11+)
        assert "s3cr3t" not in done.stdout + done.stderr
    assert lado("model-server", "list").stdout.startswith("No model servers.")


def test_an_address_that_does_not_answer_is_not_saved(lado_home):
    port = closed_port()
    done = lado("model-server", "add", "lab", f"127.0.0.1:{port}")
    assert done.returncode == 1
    assert done.stderr == f"lado: http://127.0.0.1:{port} does not answer (connection refused)\n"
    assert lado("model-server", "list").stdout.startswith("No model servers.")


def test_the_container_hint_names_add(lado_home):
    port = closed_port()
    env = {**os.environ, "LADO_CONTAINER": "1"}
    done = lado("model-server", "add", "LM Studio дома", f"localhost:{port}", env=env)
    assert done.returncode == 1
    assert done.stderr.splitlines()[-1] == (
        "lado: LADO runs in a container, where localhost is the container itself; a server on "
        f'your machine: lado model-server add "LM Studio дома" http://host.docker.internal:{port} '
        "(not tried)"
    )
