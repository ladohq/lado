"""The human's model servers and configured models (lado.model_settings): names, the key
file, the checks on adding, removal; against the fake servers of tests/fake_model_server.py
in process."""

import os
import socket
import stat

import fake_model_server as fake
import pytest

from lado import model_servers, model_settings, state
from lado.providers import base

CHAT, RESPONSES = base.CHAT_COMPLETIONS, base.RESPONSES


@pytest.fixture
def serve():
    servers = []

    def start(profile, **kwargs):
        server = fake.Server(profile, **kwargs)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


@pytest.fixture(autouse=True)
def outside_container(monkeypatch):
    monkeypatch.delenv("LADO_CONTAINER", raising=False)


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def add(name, address, key=None, replace=False):
    warned = []
    found = model_settings.add_server(name, address, key, replace=replace, warn=warned.append)
    return found, warned


def key_file(name):
    return model_settings.key_folder(state.model_server(name).id) / model_settings.KEY


# Names.


@pytest.mark.parametrize(
    ("name", "says"),
    [
        ("", "a model server's name is empty"),
        ("x" * 65, "a model server's name is at most 64 characters (this one has 65)"),
        (
            "a\nb",
            "a model server's name is one line of visible text: U+000A is not allowed",
        ),
        (
            "a​b",
            "a model server's name is one line of visible text: U+200B ZERO WIDTH SPACE is not "
            "allowed",
        ),
        (" lab", "a model server's name has no spaces at its ends"),
        ("lab ", "a model server's name has no spaces at its ends"),
    ],
)
def test_a_name_refused(name, says):
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_name(name, model_settings.SERVER)
    assert str(refused.value) == says


@pytest.mark.parametrize("name", ["LM Studio дома", "x" * 64, "Быстрая", "-x"])
def test_a_name_kept(name):
    model_settings.check_name(name, model_settings.MODEL)


# Servers.


def test_add_saves_the_address_type_and_apis_not_the_models(serve):
    server = serve("lmstudio")
    found, warned = add("LM Studio дома", server.url.removeprefix("http://"))
    assert (found.kind, found.models, warned) == ("LM Studio", ("qwen3-8b",), [])
    [saved] = state.model_servers()
    assert (saved.name, saved.address, saved.kind, saved.apis) == (
        "LM Studio дома",
        server.url,
        "LM Studio",
        (CHAT, RESPONSES),
    )
    assert not model_settings.key_folder(saved.id).exists()
    assert model_settings.server_key(saved) is None


@pytest.mark.parametrize("profile", ["unknown", "openai-key", "closed"])
def test_a_server_that_fails_the_probe_is_not_saved(serve, profile, lado_home):
    if profile == "closed":
        url = f"http://127.0.0.1:{closed_port()}"
    elif profile == "openai-key":
        url = serve("openai", key="k-1").url
    else:
        url = serve(profile).url
    with pytest.raises(model_servers.ProbeError):
        add("lab", url, key="wrong" if profile == "openai-key" else None)
    assert state.model_servers() == []
    assert not (lado_home / model_settings.KEYS).exists()


def test_a_bad_address_is_a_value_error():
    with pytest.raises(ValueError):
        add("lab", "ftp://x")


def test_a_taken_name_is_refused_before_any_request(serve):
    first = serve("lmstudio")
    add("LM Studio дома", first.url)
    second = serve("lmstudio")
    with pytest.raises(model_settings.Refused) as refused:
        add("lm studio ДОМА", second.url)
    assert str(refused.value) == (
        'a model server "LM Studio дома" is saved already; to change its address or key: '
        'lado model-server add "LM Studio дома" <address> [--key] --replace'
    )
    assert second.requests == []


def test_the_probe_names_the_add_command(serve):
    server = serve("openai", key="k-1")
    with pytest.raises(model_servers.ProbeError) as raised:
        add("work", server.url)
    assert str(raised.value).endswith(f'run lado model-server add "work" {server.url} --key')


@pytest.fixture(params=[0o077, 0o000])
def umask(request):
    old = os.umask(request.param)
    yield
    os.umask(old)


def test_the_key_file_is_private_whatever_the_umask(serve, umask, lado_home):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    path = key_file("work")
    assert path.read_text() == "k-1"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE((lado_home / model_settings.KEYS).stat().st_mode) == 0o700
    assert model_settings.server_key(state.model_server("work")) == "k-1"
    assert sorted(os.listdir(path.parent)) == ["key"]


def test_a_link_on_the_way_to_the_key_is_refused(serve, lado_home, tmp_path):
    server = serve("openai", key="k-1")
    lado_home.mkdir(exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (lado_home / model_settings.KEYS).symlink_to(elsewhere)
    with pytest.raises(model_settings.Refused, match="symbolic link"):
        add("work", server.url, key="k-1")
    assert list(elsewhere.iterdir()) == []
    assert state.model_servers() == []


def test_replace_with_a_new_key_rewrites_the_file(serve):
    old = serve("openai", key="k-1")
    add("work", old.url, key="k-1")
    new = serve("openai", key="k-2")
    found, _ = add("WORK", new.url, key="k-2", replace=True)
    assert found.kind == "OpenAI-compatible"
    assert key_file("work").read_text() == "k-2"
    assert state.model_server("work").address == new.url


def test_replace_without_a_key_keeps_and_sends_the_kept_one(serve):
    old = serve("openai", key="k-1")
    add("work", old.url, key="k-1")
    state.add_model("Q", "opencode", "gpt-oss-20b", state.model_server("work").id)
    new = serve("ollama", key="k-1")
    add("work", new.url, replace=True)
    saved = state.model_server("work")
    assert (saved.address, saved.kind, saved.apis) == (new.url, "Ollama", (CHAT, RESPONSES))
    assert {r.headers["Authorization"] for r in new.requests} == {"Bearer k-1"}
    assert key_file("work").read_text() == "k-1"
    assert state.model("Q").server == saved.id


def test_a_failed_replace_changes_nothing(serve):
    old = serve("openai", key="k-1")
    add("work", old.url, key="k-1")
    before = state.model_server("work")
    with pytest.raises(model_servers.ProbeError):
        add("work", f"http://127.0.0.1:{closed_port()}", key="k-2", replace=True)
    assert state.model_server("work") == before
    assert key_file("work").read_text() == "k-1"


def test_replace_of_a_name_no_server_has_is_refused(serve):
    server = serve("openai")
    with pytest.raises(model_settings.Refused) as refused:
        add("work", server.url, replace=True)
    assert str(refused.value) == (
        'no model server "work" is saved; lado model-server list names them'
    )
    assert server.requests == []


def test_the_plain_http_warning_comes_before_the_probe(serve, monkeypatch):
    server = serve("openai", key="k-1")
    events = []
    real = model_servers.probe

    def probe(text, key, command):  # the public address answers on the fake server
        events.append("probe")
        return real(server.url, key, command)

    monkeypatch.setattr(model_servers, "probe", probe)
    model_settings.add_server("ext", "http://llm.example.com", "k-1", warn=events.append)
    assert events == [
        "the key goes to llm.example.com over plain http://, unencrypted; use https:// if the "
        "server has it",
        "probe",
    ]


def test_remove_removes_the_server_and_its_key_folder(serve, lado_home):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    folder = key_file("work").parent
    assert model_settings.remove_server("WORK") == "work"
    assert state.model_servers() == []
    assert not folder.exists()
    assert list((lado_home / model_settings.KEYS).iterdir()) == []


def test_remove_of_a_server_models_use_is_refused_naming_them(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    id = state.model_server("LM Studio дома").id
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", id)
    state.add_model("Another", "kilo", "qwen3-8b", id)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.remove_server("LM Studio дома")
    assert str(refused.value) == (
        'model server "LM Studio дома" is used by the models Another, Локальная Qwen; remove '
        'them first: lado model remove "Another"'
    )
    assert state.model_server("LM Studio дома") is not None


def test_remove_of_a_name_no_server_has_is_refused():
    with pytest.raises(model_settings.Refused, match='no model server "work" is saved'):
        model_settings.remove_server("work")


def test_a_failed_insert_removes_the_key_it_wrote(serve, monkeypatch, lado_home):
    """Another add saved the name between the check and the insert."""
    server = serve("openai", key="k-1")

    def taken(*args):
        raise state.NameTaken("Work")

    monkeypatch.setattr(state, "add_model_server", taken)
    with pytest.raises(model_settings.Refused, match='a model server "Work" is saved already'):
        add("work", server.url, key="k-1")
    assert list((lado_home / model_settings.KEYS).iterdir()) == []


def test_the_clis_a_saved_server_suits():
    saved = state.add_model_server(
        "s1", "work", "https://gw", "OpenAI-compatible", (CHAT, RESPONSES)
    )
    assert model_settings.clis(saved) == ["Kilo CLI", "OpenCode", "Codex CLI"]
    bare = state.add_model_server("s2", "bare", "https://x", "OpenAI-compatible", ())
    assert model_settings.clis(bare) == []
