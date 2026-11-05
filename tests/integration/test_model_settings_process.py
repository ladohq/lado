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
from fake_model_server import EMBEDDINGS
from test_model_server_probe import closed_port, lado, serve  # noqa: F401 - a fixture

from lado import agent_env

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


def test_a_default_model_set_read_and_cleared_with_its_server(serve, tmp_path):  # noqa: F811
    """Across processes: a default set by one command, read by the next, and gone with its
    server in the same transaction; a stand-in of OpenCode on PATH gives the CLI's list."""
    folder = tmp_path / "clis"
    folder.mkdir()
    opencode = folder / "opencode"
    opencode.write_text('#!/bin/sh\nif [ "$1" = models ]; then echo a/one; fi\n')
    opencode.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{folder}{os.pathsep}{os.environ['PATH']}",
        agent_env.SOURCE_VAR: agent_env.INHERIT,
    }
    url = serve("lmstudio")
    assert lado("model-server", "add", "lms", url).returncode == 0
    added = lado(
        "model", "add", "Локальная Qwen", "--cli", "opencode", "--model", "qwen3-8b",
        "--server", "lms",
    )  # fmt: skip
    assert added.returncode == 0, added.stderr
    no_server = lado("model", "add", "Быстрая", "--cli", "claude", "--model", "haiku")
    assert no_server.returncode == 1
    assert "lado model default <cli> <model>" in no_server.stderr

    built_in = lado("model", "default", "opencode", "a/one", env=env)
    assert (built_in.returncode, built_in.stderr) == (0, "")
    assert built_in.stdout == "OpenCode's default model: a/one (in OpenCode's list of models)\n"
    refused = lado("model", "default", "opencode", "a/two", env=env)
    assert refused.returncode == 1
    assert "a/two is not in OpenCode's list of models" in refused.stderr
    external = lado("model", "default", "opencode", "локальная qwen", env=env)
    assert external.stdout == ("OpenCode's default model: Локальная Qwen (qwen3-8b on lms)\n")
    rows = lado("model", "default").stdout.splitlines()
    assert rows[0].split() == ["CLI", "DEFAULT", "MODEL", "SERVER"]
    [row] = [line for line in rows if line.startswith("OpenCode")]
    assert row.split() == ["OpenCode", "Локальная", "Qwen", "lms"]

    removed = lado("model-server", "remove", "lms", "--with-models")
    assert removed.stdout.splitlines() == [
        'Removed model "Локальная Qwen".',
        "OpenCode's default model is cleared.",
        'Removed model server "lms".',
    ]
    [row] = [line for line in lado("model", "default").stdout.splitlines() if "OpenCode" in line]
    assert row.split() == ["OpenCode", "—", "—"]
    assert lado("model", "default", "opencode", "x", "--clear").returncode == 2


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


def test_embeddings_same_address_and_several_removed(serve, lado_home):  # noqa: F811
    """LM Studio under two names, its embeddings model refused, then several models removed
    and their server; a canary key in none of these lines, nor any file but its own."""
    canary = f"canary-key-{uuid.uuid4().hex}"
    url = serve("lmstudio", key=canary)
    runs = [lado("model-server", "add", "macpro", url, "--key", stdin=canary)]
    assert runs[-1].returncode == 0, runs[-1].stderr
    assert f"models: qwen3-8b, {EMBEDDINGS} (embeddings)" in runs[-1].stdout
    runs.append(
        lado("model-server", "add", "lms", url.removeprefix("http://") + "/v1/", "--key",
             stdin=canary)
    )  # fmt: skip
    assert runs[-1].returncode == 0, runs[-1].stderr
    assert runs[-1].stdout.splitlines()[-2:] == [
        'same address as model server "macpro"',
        'Saved model server "lms".',
    ]
    runs.append(lado("model", "add", "emb", "--cli", "opencode", "--model", EMBEDDINGS,
                     "--server", "lms"))  # fmt: skip
    assert runs[-1].returncode == 1
    assert runs[-1].stderr == (
        f"lado: {EMBEDDINGS} is an embeddings model on lms; an agent needs a chat model: "
        f"lado model-server probe {url} lists the models\n"
    )
    assert lado("model", "list").stdout.startswith("No models")
    for name, cli in (("coder-codex", "codex"), ("coder-oc", "opencode"), ("sp", "kilo")):
        runs.append(lado("model", "add", name, "--cli", cli, "--model", "qwen3-8b",
                         "--server", "lms"))  # fmt: skip
        assert runs[-1].returncode == 0, runs[-1].stderr
    runs.append(lado("model-server", "remove", "lms"))
    assert runs[-1].returncode == 1
    assert (
        runs[-1]
        .stderr.splitlines()[0]
        .endswith('remove them first: lado model remove "coder-codex" "coder-oc" "sp"')
    )
    runs.append(lado("model", "remove", "coder-codex", "coder-oc", "sp"))
    assert (runs[-1].returncode, runs[-1].stdout) == (
        0,
        'Removed model "coder-codex".\nRemoved model "coder-oc".\nRemoved model "sp".\n',
    )
    runs.append(lado("model-server", "remove", "lms"))
    assert runs[-1].returncode == 0, runs[-1].stderr
    for done in runs:
        assert canary not in done.stdout + done.stderr
    held = [p for p in _files(lado_home) if canary.encode() in p.read_bytes()]
    assert [p.parent.parent for p in held] == [lado_home / "model-servers"]  # macpro's key


def test_remove_a_server_with_its_models(serve, lado_home):  # noqa: F811
    url = serve("lmstudio")
    assert lado("model-server", "add", "lms", url).returncode == 0
    for name, cli in (("sp", "kilo"), ("coder-oc", "opencode")):
        added = lado("model", "add", name, "--cli", cli, "--model", "qwen3-8b", "--server", "lms")
        assert added.returncode == 0, added.stderr
    refused = lado("model-server", "remove", "lms")
    assert refused.returncode == 1
    assert refused.stderr.splitlines()[-1] == (
        'lado: or remove them with it: lado model-server remove "lms" --with-models'
    )
    removed = lado("model-server", "remove", "lms", "--with-models")
    assert (removed.returncode, removed.stdout) == (
        0,
        'Removed model "coder-oc".\nRemoved model "sp".\nRemoved model server "lms".\n',
    )
    assert lado("model", "list").stdout.startswith("No models")
    assert lado("model-server", "list").stdout.startswith("No model servers.")
    assert not any((lado_home / "model-servers").glob("*"))


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
