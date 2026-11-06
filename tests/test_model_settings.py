"""The human's model servers and configured models (lado.model_settings): names, the key
file, the checks on adding, removal; against the fake servers of tests/fake_model_server.py
in process."""

import json
import os
import socket
import sqlite3
import stat
import time

import fake_model_server as fake
import pytest

from lado import agent_env, model_check, model_servers, model_settings, providers, state
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


def add(name, address, key=None, replace=False, notes=None):
    warned = []
    found = model_settings.add_server(
        name,
        address,
        key,
        replace=replace,
        warn=warned.append,
        note=(notes if notes is not None else []).append,
    )
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
    assert (found.kind, found.models, warned) == ("LM Studio", ("qwen3-8b", fake.EMBEDDINGS), [])
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


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("http://h:1234", "http://h:1234", True),
        ("http://h:1234", "http://H:1234", True),
        ("http://h", "http://h:80", True),
        ("https://h", "https://h:443", True),
        ("http://h:1234/llm", "http://h:1234/llm", True),
        ("http://h:1234", "http://h:1235", False),
        ("http://h:1234", "http://h:1234/llm", False),
        ("http://h:443", "https://h:443", False),
        ("http://h", "https://h", False),
        ("http://[::1]:1234", "http://[::1]:1234", True),
        ("http://h:1234/LLM", "http://h:1234/llm", False),
    ],
)
def test_same_address(a, b, same):
    assert model_settings.same_address(a, b) is same
    assert model_settings.same_address(b, a) is same


@pytest.mark.parametrize("given", ["{host}", "{host}/v1/", "http://{host}/"])
def test_a_server_at_the_address_of_another_is_saved_and_named(serve, given):
    server = serve("lmstudio")
    host = server.url.removeprefix("http://")
    add("macpro", server.url)
    add("other", serve("openai").url)
    notes = []
    add("lms", given.format(host=host), notes=notes)
    assert notes == ['same address as model server "macpro"']
    assert [s.name for s in state.model_servers()] == ["lms", "macpro", "other"]


def test_each_server_at_the_address_is_named(serve):
    server = serve("lmstudio")
    add("a", server.url)
    add("b", server.url)
    notes = []
    add("c", server.url, notes=notes)
    assert notes == ['same address as model server "a"', 'same address as model server "b"']


def test_another_port_is_not_named(serve):
    # Another path: test_same_address (a fake answers under one path only).
    add("gw", serve("openai", prefix="/llm").url)
    notes = []
    add("root", serve("openai").url, notes=notes)
    assert notes == []


def test_replace_does_not_count_the_server_replaced(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    notes = []
    add("lms", server.url + "/", replace=True, notes=notes)
    assert notes == []
    add("macpro", server.url)
    add("lms", server.url, replace=True, notes=notes)
    assert notes == ['same address as model server "macpro"']


def test_a_failed_probe_names_no_server(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    server.close()
    notes = []
    with pytest.raises(model_servers.ProbeError):
        add("macpro", server.url, notes=notes)
    assert notes == []


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
    model_settings.add_server(
        "ext", "http://llm.example.com", "k-1", warn=events.append, note=events.append
    )
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
        'them first: lado model remove "Another" "Локальная Qwen"'
    )
    assert refused.value.hint == (
        'or remove them with it: lado model-server remove "LM Studio дома" --with-models'
    )
    assert state.model_server("LM Studio дома") is not None


def test_remove_with_models_removes_them_then_the_server(serve, lado_home):
    server = serve("lmstudio", key="k-1")
    add("lms", server.url, key="k-1")
    id = state.model_server("lms").id
    state.add_model("sp", "kilo", "qwen3-8b", id)
    state.add_model("coder-oc", "opencode", "qwen3-8b", id)
    folder = key_file("lms").parent
    removed = []
    assert model_settings.remove_server("LMS", with_models=True, removed=removed.append) == "lms"
    assert removed == ["coder-oc", "sp"]
    assert state.model_servers() == []
    assert state.models() == []
    assert not folder.exists()


def test_remove_with_models_takes_a_model_added_after_the_listing(serve, monkeypatch):
    """The models are found in the transaction that removes the server: one added after the
    page listed them goes too, never a foreign-key refusal."""
    add("lms", serve("lmstudio").url)
    id = state.model_server("lms").id
    state.add_model("listed", "opencode", "qwen3-8b", id)
    real = state.remove_model_server_with_models

    def late(server_id, confirmed):
        state.add_model("late", "kilo", "qwen3-8b", server_id)
        return real(server_id, confirmed)

    monkeypatch.setattr(state, "remove_model_server_with_models", late)
    removed = []
    model_settings.remove_server("lms", with_models=True, removed=removed.append)
    assert removed == ["late", "listed"]
    assert state.models() == []


def test_remove_with_the_models_confirmed_refuses_one_added_after_the_confirmation(serve):
    """The page names the models it removes: one added after it asked keeps the server and
    every model, and the refusal names them all."""
    add("lms", serve("lmstudio").url)
    id = state.model_server("lms").id
    state.add_model("listed", "opencode", "qwen3-8b", id)
    state.add_model("late", "kilo", "qwen3-8b", id)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.remove_server("lms", with_models=True, confirmed=["listed"])
    assert str(refused.value) == (
        'model server "lms" has other models now: late, listed; nothing was removed'
    )
    assert (refused.value.hint, refused.value.field) == ("", "")
    assert [m.name for m in state.models()] == ["late", "listed"]
    removed = []
    model_settings.remove_server(
        "lms", with_models=True, confirmed=["late", "LISTED"], removed=removed.append
    )
    assert (removed, state.model_servers()) == (["late", "listed"], [])


def test_remove_with_models_of_a_server_no_model_uses(serve):
    add("lms", serve("lmstudio").url)
    removed = []
    assert model_settings.remove_server("lms", with_models=True, removed=removed.append) == "lms"
    assert (removed, state.model_servers()) == ([], [])


def test_remove_of_a_name_no_server_has_is_refused():
    with pytest.raises(model_settings.Refused, match='no model server "work" is saved'):
        model_settings.remove_server("work")


def test_remove_refused_by_a_model_gone_again_meanwhile(serve, monkeypatch):
    """The foreign key refused the removal for a model added meanwhile, removed again before
    it could be named: a refusal, never an IndexError."""
    add("lab", serve("openai").url)

    def refused(id):
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    monkeypatch.setattr(state, "remove_model_server", refused)
    with pytest.raises(model_settings.Refused) as raised:
        model_settings.remove_server("lab")
    assert str(raised.value) == (
        'model server "lab" was used by a model meanwhile; run the command again'
    )


@pytest.fixture
def unreadable(lado_home):
    """Make a server's key folder unreadable (mode 000); restored after the test."""
    made = []

    def make(name):
        folder = model_settings.key_folder(state.model_server(name).id)
        folder.chmod(0)
        made.append(folder)
        return folder

    yield make
    for folder in made:
        folder.chmod(0o700)


def test_a_key_that_cannot_be_read_refuses_in_one_line(serve, unreadable):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    folder = unreadable("work")
    with pytest.raises(model_settings.Refused) as raised:
        model_settings.server_key(state.model_server("work"))
    assert str(raised.value) == f"{folder / 'key'} cannot be read (Permission denied)"
    with pytest.raises(model_settings.Refused, match="cannot be read"):
        add_model("W", "opencode", "gpt-oss-20b", "work")
    with pytest.raises(model_settings.Refused, match="cannot be read"):
        add("work", server.url, replace=True)
    with pytest.raises(model_settings.Refused, match="cannot be written"):
        add("work", server.url, key="k-1", replace=True)
    assert state.models() == []


def test_a_key_over_64_kib_is_refused_before_any_request(serve, lado_home):
    server = serve("openai")
    with pytest.raises(model_settings.Refused) as raised:
        add("work", server.url, key="k" * (agent_env.MAX_VALUE + 1))
    assert str(raised.value) == "the key is larger than 64 KiB"
    assert server.requests == []
    assert state.model_servers() == []
    assert not (lado_home / model_settings.KEYS).exists()


@pytest.mark.parametrize("key", ["\udcff\udcfe", "a\nb", "ключ"])
def test_a_key_no_header_can_carry_is_refused(serve, key):
    server = serve("openai")
    with pytest.raises(model_settings.Refused) as raised:
        add("work", server.url, key=key)
    assert str(raised.value) == "the key holds a character no HTTP header can carry"
    assert server.requests == []


def test_a_cleanup_that_fails_keeps_the_first_error(serve, monkeypatch):
    server = serve("openai", key="k-1")
    monkeypatch.setattr(
        state, "add_model_server", lambda *a: (_ for _ in ()).throw(state.NameTaken("Work"))
    )

    def refused(id):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(model_settings, "_remove_key", refused)
    with pytest.raises(model_settings.Refused, match='a model server "Work" is saved already'):
        add("work", server.url, key="k-1")


def test_a_key_file_over_64_kib_is_not_read_cut(serve):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    path = model_settings.key_folder(state.model_server("work").id) / model_settings.KEY
    path.write_text("k" * (agent_env.MAX_VALUE + 1))
    with pytest.raises(model_settings.Refused) as raised:
        model_settings.server_key(state.model_server("work"))
    assert str(raised.value) == f"{path} is larger than 64 KiB"


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
    assert model_settings.clis(saved) == ["Codex CLI", "Kilo CLI", "OpenCode"]
    bare = state.add_model_server("s2", "bare", "https://x", "OpenAI-compatible", ())
    assert model_settings.clis(bare) == []


# Models.


def listing(monkeypatch, name, listed):
    """The CLI `name` gives `listed`, read with the environment the command passes. Its
    class is patched, never the shared instance: undoing an instance's patch would leave
    the old bound method on it, over any later test's patch of the class."""
    seen = []
    provider = type(providers.get(name))
    monkeypatch.setattr(provider, "model_list", lambda self, env: seen.append(env) or listed)
    return seen


def add_model(name, cli, model, server=None):
    return model_settings.add_model(name, cli, model, server)


def test_a_model_without_a_server_is_refused_and_reads_no_list(monkeypatch):
    seen = listing(monkeypatch, "claude", base.ModelList(("haiku",), None, why="no list"))
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Быстрая", "claude", "haiku")
    assert str(refused.value) == (
        "a CLI's own models need no saving; only a model on a server is added: --server <server>"
    )
    assert refused.value.hint == "to make one its default: lado model default <cli> <model>"
    assert refused.value.field == "server"
    assert seen == []
    assert state.models() == []


def test_a_cli_lado_does_not_know_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        add_model("G", "gemini", "x")
    assert str(refused.value) == (
        'LADO knows no agent CLI "gemini"; --cli takes one of claude, codex, kilo, opencode'
    )


def test_an_empty_model_is_refused():
    with pytest.raises(model_settings.Refused, match="the model is empty"):
        add_model("E", "claude", "  ")


def test_a_taken_name_is_refused_before_any_check(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    add_model("Быстрая", "opencode", "qwen3-8b", "lms")
    server.requests.clear()
    with pytest.raises(model_settings.Refused) as refused:
        add_model("быстрая", "kilo", "qwen3-8b", "lms")
    assert str(refused.value) == (
        'a model "Быстрая" is saved already; remove it first: lado model remove "Быстрая"'
    )
    assert server.requests == []
    assert state.model("Быстрая").cli == "opencode"


def test_a_server_no_one_saved_is_refused_without_a_request():
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "q", "nowhere")
    assert str(refused.value) == (
        'no model server "nowhere" is saved; lado model-server list names them'
    )


def test_a_model_on_a_server_in_its_list_is_saved(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    saved, verdict = add_model("Локальная Qwen", "opencode", "qwen3-8b", "lm studio дома")
    assert saved.server == state.model_server("LM Studio дома").id
    assert (verdict.kind, verdict.text) == (model_check.OK, "in LM Studio дома's list of models")


def test_a_model_the_server_does_not_list_is_refused(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "qwen3-14b", "LM Studio дома")
    assert str(refused.value) == (
        f"qwen3-14b is not in LM Studio дома's list of models; lado model-server probe "
        f"{server.url} prints the list"
    )
    assert state.models() == []


def test_an_embeddings_model_is_refused(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("emb", "opencode", fake.EMBEDDINGS, "lms")
    assert str(refused.value) == (
        f"{fake.EMBEDDINGS} is an embeddings model on lms; an agent needs a chat model: "
        f"lado model-server probe {server.url} lists the models"
    )
    assert state.models() == []
    saved, _ = add_model("chat", "opencode", "qwen3-8b", "lms")
    assert saved.model == "qwen3-8b"


def test_the_api_is_checked_before_the_embeddings(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    with pytest.raises(model_settings.Refused, match="lms does not suit Claude Code"):
        add_model("emb", "claude", fake.EMBEDDINGS, "lms")


def test_a_server_without_types_is_checked_by_its_list(serve):
    server = serve("ollama")
    add("ol", server.url)
    _, verdict = add_model("O", "opencode", "llama3.1:8b", "ol")
    assert verdict.kind == model_check.OK


def test_a_server_with_no_list_saves_with_a_warning(serve):
    server = serve("responses-only")
    add("resp", server.url)
    _, verdict = add_model("C", "codex", "gpt-x", "resp")
    assert verdict.kind == model_check.WARN
    assert verdict.text.startswith("GET /v1/models: 404: LADO cannot check gpt-x")


def test_a_server_that_does_not_answer_refuses_the_model(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    server.close()
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "qwen3-8b", "LM Studio дома")
    assert str(refused.value) == (
        f"{server.url} does not answer (connection refused); LADO cannot check qwen3-8b"
    )
    assert state.models() == []


def test_the_server_is_asked_with_its_kept_key(serve):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    server.requests.clear()
    add_model("W", "opencode", "gpt-oss-20b", "work")
    assert {r.headers["Authorization"] for r in server.requests} == {"Bearer k-1"}


def test_a_server_that_does_not_suit_the_cli_is_refused(serve):
    server = serve("openai")  # chat completions only
    add("LM Studio дома", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("C", "codex", "gpt-oss-20b", "LM Studio дома")
    assert str(refused.value) == (
        "LM Studio дома does not suit Codex CLI: it has no Responses API; it suits Kilo CLI, "
        "OpenCode"
    )


def test_a_server_that_suits_no_cli_says_so(serve):
    server = serve("models-only")
    add("bare", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("C", "opencode", "m1", "bare")
    assert str(refused.value) == (
        "bare does not suit OpenCode: it has no chat completions; it suits no CLI"
    )


def test_a_cli_that_speaks_no_server_api_is_refused(serve, monkeypatch):
    server = serve("all")
    add("all", server.url)
    server.requests.clear()
    monkeypatch.setattr(type(providers.get("kilo")), "server_api", "")
    with pytest.raises(model_settings.Refused) as refused:
        add_model("K", "kilo", "m1", "all")
    assert str(refused.value) == "all does not suit Kilo CLI: Kilo CLI speaks no model server's API"
    assert server.requests == []


def test_claude_on_an_anthropic_compatible_server_is_saved(serve):
    server = serve("anthropic")
    add("gw", server.url)
    saved, verdict = add_model("Gw Claude", "claude", "claude-x", "gw")
    assert (saved.cli, verdict.kind) == ("claude", model_check.OK)


@pytest.mark.parametrize(
    "model", ["sonnet", "Sonnet", "opus", "best", "opusplan", "default", "qwen3[1m]", "qwen[1M]"]
)
def test_a_name_claude_code_reads_as_its_own_is_not_saved_for_it(serve, model):
    server = serve("all")
    add("all", server.url)
    asked = len(server.requests)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Своя", "claude", model, "all")
    assert str(refused.value) == (
        f"Claude Code reads {model} as its own model, so it would not ask all for it; give the "
        "model another name on the server"
    )
    assert refused.value.field == model_settings.MODEL_FIELD
    assert len(server.requests) == asked and state.models() == []


def test_a_name_claude_code_reads_as_its_own_starts_on_opencode():
    default_on(entry("Своя", model="sonnet"))
    start = model_settings.start_model(None, OPENCODE)
    probe = counting_probe(found_on_server("sonnet"))
    assert model_settings.check_start(start, OPENCODE, {}, probe).kind == model_check.OK


def test_a_saved_name_claude_code_reads_as_its_own_is_refused_at_a_start():
    saved = entry("Своя", cli="claude", model="sonnet", server="Шлюз")
    default_on(saved)
    probe = counting_probe()
    start = model_settings.start_model(None, CLAUDE)
    with pytest.raises(model_settings.Refused, match="reads sonnet as its own model"):
        model_settings.check_start(start, CLAUDE, {}, probe)
    assert probe.asked == []


def test_claude_code_on_a_server_without_its_api_is_refused(serve):
    server = serve("openai")
    add("oai", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("O", "claude", "gpt-oss-20b", "oai")
    assert str(refused.value).startswith(
        "oai does not suit Claude Code: it has no Anthropic Messages API; it suits "
    )


def test_remove_a_model_keeps_its_server(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    add_model("Локальная Qwen", "opencode", "qwen3-8b", "LM Studio дома")
    assert remove_models("локальная QWEN") == ["Локальная Qwen"]
    assert state.models() == []
    assert model_settings.remove_server("LM Studio дома") == "LM Studio дома"


def remove_models(*names):
    removed = []
    model_settings.remove_models(list(names), removed.append)
    return removed


def saved_models(*names):
    server = state.add_model_server("s1", "lms", "http://lms", "LM Studio", (CHAT,))
    for name in names:
        state.add_model(name, "opencode", "qwen3-8b", server.id)


def test_remove_several_models_in_the_order_given():
    saved_models("coder-codex", "coder-oc", "sp", "kept")
    assert remove_models("sp", "CODER-codex", "coder-oc", "Sp") == ["sp", "coder-codex", "coder-oc"]
    assert [m.name for m in state.models()] == ["kept"]


def test_remove_of_a_name_no_model_has_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        remove_models("nope")
    assert str(refused.value) == 'no model "nope" is saved; lado model list names them'


def test_one_name_not_saved_removes_none():
    saved_models("coder-codex", "sp")
    removed = []
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.remove_models(
            ["coder-codex", "nowhere", "sp", "x", "NOWHERE"], removed.append
        )
    assert str(refused.value) == ('no models "nowhere", "x" are saved; lado model list names them')
    assert removed == []
    assert [m.name for m in state.models()] == ["coder-codex", "sp"]


def test_a_model_removed_meanwhile_is_named_after_the_others(monkeypatch):
    saved_models("a", "b", "c")
    real = state.remove_model

    def remove(name):
        if name == "b":
            real(name)
            return None  # another process was first
        return real(name)

    monkeypatch.setattr(state, "remove_model", remove)
    removed = []
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.remove_models(["a", "b", "c"], removed.append)
    assert removed == ["a", "c"]
    assert str(refused.value) == 'no model "b" is saved; lado model list names them'
    assert state.models() == []


# The field a refusal concerns (the page shows it under that field).


def test_name_refusals_name_the_name():
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_name("", model_settings.MODEL)
    assert refused.value.field == "name"


def test_server_refusals_name_their_field(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    for call, field in [
        (lambda: add("LMS", server.url), "name"),
        (lambda: add("nope", server.url, replace=True), "name"),
        (lambda: add("work", server.url, key="a\nb"), "key"),
        (lambda: add("work", server.url, key=""), "key"),
        (lambda: model_settings.remove_server("nope"), ""),
    ]:
        with pytest.raises(model_settings.Refused) as refused:
            call()
        assert refused.value.field == field, refused.value
    state.add_model("Q", "opencode", "qwen3-8b", state.model_server("lms").id)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.remove_server("lms")
    assert refused.value.field == ""


def test_the_empty_key_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_key("")
    assert (str(refused.value), refused.value.field) == ("the key is empty", "key")


def test_model_refusals_name_their_field(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    add("chat", serve("openai").url)
    add_model("Taken", "opencode", "qwen3-8b", "lms")
    cases = [
        (("", "opencode", "qwen3-8b", "lms"), "name"),
        (("taken", "opencode", "qwen3-8b", "lms"), "name"),
        (("N", "gemini", "x", "lms"), "cli"),
        (("N", "opencode", " ", "lms"), "model"),
        (("N", "opencode", "qwen3-8b", None), "server"),
        (("N", "opencode", fake.EMBEDDINGS, "lms"), "model"),
        (("N", "opencode", "qwen3-14b", "lms"), "model"),
        (("N", "opencode", "q", "nowhere"), "server"),
        (("N", "codex", "gpt-oss-20b", "chat"), "server"),
    ]
    for (name, cli, model, on), field in cases:
        with pytest.raises(model_settings.Refused) as refused:
            add_model(name, cli, model, on)
        assert refused.value.field == field, refused.value
    server.close()
    with pytest.raises(model_settings.Refused) as refused:
        add_model("N", "opencode", "qwen3-8b", "lms")
    assert refused.value.field == "server"


# A model's check without the save.


def check_model(name, cli, model, server=None, probe=None):
    return model_settings.check_model(name, cli, model, server, probe=probe)


def test_check_model_refuses_as_add_model_does_and_saves_nothing(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    add_model("Taken", "opencode", "qwen3-8b", "lms")
    cases = [
        ("taken", "opencode", "qwen3-8b", "lms"),
        ("N", "gemini", "x", "lms"),
        ("N", "opencode", "qwen3-8b", None),
        ("N", "opencode", fake.EMBEDDINGS, "lms"),
        ("N", "opencode", "q", "nowhere"),
    ]
    for case in cases:
        with pytest.raises(model_settings.Refused) as checked:
            check_model(*case)
        with pytest.raises(model_settings.Refused) as added:
            add_model(*case)
        assert (str(checked.value), checked.value.field) == (str(added.value), added.value.field)
    checked = check_model("N", "opencode", "qwen3-8b", "lms")
    assert (checked.verdict.kind, checked.model, checked.server.name) == (
        model_check.OK,
        "qwen3-8b",
        "lms",
    )
    assert checked.provider is providers.get("opencode")
    assert [m.name for m in state.models()] == ["Taken"]


def test_check_model_without_a_name_checks_no_name(serve):
    add("lms", serve("lmstudio").url)
    add_model("qwen3-8b · lms · OpenCode", "opencode", "qwen3-8b", "lms")
    checked = check_model(None, "opencode", "qwen3-8b", "lms")
    assert (checked.verdict.kind, checked.name) == (
        model_check.OK,
        "qwen3-8b · lms · OpenCode (2)",
    )


def test_check_model_uses_the_probe_given(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    kept = model_servers.probe(server.url)
    server.requests.clear()
    seen = []
    checked = check_model(
        "N", "opencode", "qwen3-8b", "lms", probe=lambda s: seen.append(s) or kept
    )
    assert checked.verdict.kind == model_check.OK
    assert [s.name for s in seen] == ["lms"]
    assert server.requests == []


# A model's default name.


def litellm_server(apis=(RESPONSES,)):
    """A server one CLI suits (Codex CLI, by the Responses API), unless `apis` say more."""
    return state.add_model_server("s1", "LiteLLM", "http://gw", "OpenAI-compatible", apis)


def default_name(cli, model, server):
    return model_settings.default_name(providers.get(cli), model, server)


def test_the_default_name_of_a_model_on_a_server():
    assert default_name("codex", "qwen3-8b", litellm_server()) == "qwen3-8b · LiteLLM"


def test_the_default_name_on_a_server_several_clis_suit_names_its_cli():
    """Ticked for OpenCode and then Kilo CLI, each name says its CLI, the first too."""
    server = litellm_server((CHAT, RESPONSES))
    assert default_name("opencode", "qwen3-8b", server) == "qwen3-8b · LiteLLM · OpenCode"
    state.add_model("qwen3-8b · LiteLLM · OpenCode", "opencode", "qwen3-8b", server.id)
    assert default_name("kilo", "qwen3-8b", server) == "qwen3-8b · LiteLLM · Kilo CLI"
    state.add_model("qwen3-8b · LiteLLM · kilo cli", "kilo", "qwen3-8b", server.id)
    assert default_name("kilo", "qwen3-8b", server) == "qwen3-8b · LiteLLM · Kilo CLI (2)"


def test_a_taken_default_name_gets_the_cli_then_a_number():
    server = litellm_server()
    state.add_model("QWEN3-8B · litellm", "opencode", "qwen3-8b", server.id)
    assert default_name("codex", "qwen3-8b", server) == "qwen3-8b · LiteLLM · Codex CLI"
    state.add_model("qwen3-8b · LiteLLM · Codex CLI", "codex", "qwen3-8b", server.id)
    assert default_name("codex", "qwen3-8b", server) == "qwen3-8b · LiteLLM · Codex CLI (2)"
    state.add_model("qwen3-8b · LiteLLM · Codex CLI (2)", "codex", "qwen3-8b", server.id)
    assert default_name("codex", "qwen3-8b", server) == "qwen3-8b · LiteLLM · Codex CLI (3)"


def test_a_long_default_name_is_cut_before_its_suffix():
    server = litellm_server()
    model = "m" * 70
    first = default_name("opencode", model, server)
    assert (len(first), first) == (64, "m" * 64)  # cut: no room for " · LiteLLM"
    state.add_model(first, "opencode", model, server.id)
    second = default_name("codex", model, server)
    assert len(second) == 64
    assert second.endswith(" · Codex CLI")
    state.add_model(second, "codex", model, server.id)
    third = default_name("codex", model, server)
    assert (len(third), third.endswith(" · Codex CLI (2)")) == (64, True)
    model_settings.check_name(third, model_settings.MODEL)


def test_add_model_without_a_name_names_it(serve):
    add("resp", serve("responses-only").url)
    saved, _ = add_model(None, "codex", "gpt-x", "resp")
    assert saved.name == "gpt-x · resp"
    saved, _ = add_model(None, "codex", "gpt-x", "resp")
    assert saved.name == "gpt-x · resp · Codex CLI"


def test_a_model_whose_default_name_is_no_name_is_refused_under_the_model(serve):
    """A model of no list (a warning) with a hidden character would be named by it: the
    name's rule refuses it, under the model's field, in the check and the save alike."""
    add("resp", serve("responses-only").url)
    hidden = "claude-opus​-5-5"  # U+200B
    says = "a model's name is one line of visible text: U+200B ZERO WIDTH SPACE is not allowed"
    with pytest.raises(model_settings.Refused) as checked:
        check_model(None, "codex", hidden, "resp")
    with pytest.raises(model_settings.Refused) as added:
        add_model(None, "codex", hidden, "resp")
    for refused in (checked.value, added.value):
        assert (str(refused), refused.field) == (says, "model")
    assert state.models() == []
    assert check_model(None, "codex", "gpt-x", "resp").name == "gpt-x · resp"


# Renaming a model.


def rename(name, new):
    return model_settings.rename_model(name, new)


def test_rename_a_model():
    saved_models("Claude Sonnet")
    renamed = rename("claude sonnet", "Сильная")
    assert (renamed.name, renamed.cli, renamed.model) == ("Сильная", "opencode", "qwen3-8b")
    assert [m.name for m in state.models()] == ["Сильная"]
    assert rename("сильная", "СИЛЬНАЯ").name == "СИЛЬНАЯ"


def test_rename_to_a_taken_name_is_refused():
    saved_models("a", "Other")
    with pytest.raises(model_settings.Refused) as refused:
        rename("a", "OTHER")
    assert (str(refused.value), refused.value.field) == (
        'a model "Other" is saved already; remove it first: lado model remove "Other"',
        "name",
    )
    assert [m.name for m in state.models()] == ["a", "Other"]


@pytest.mark.parametrize("new", ["", "x" * 65, " a"])
def test_rename_to_no_name_is_refused(new):
    saved_models("a")
    with pytest.raises(model_settings.Refused) as refused:
        rename("a", new)
    assert refused.value.field == "name"
    assert [m.name for m in state.models()] == ["a"]


def test_rename_of_a_model_not_saved_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        rename("nope", "x")
    assert (str(refused.value), refused.value.field) == (
        'no model "nope" is saved; lado model list names them',
        "",
    )


# An agent CLI's full list.


def external(name="Локальная Qwen", cli="opencode", model="qwen3-8b"):
    if state.model_server("lms") is None:
        state.add_model_server("s1", "lms", "http://lms", "LM Studio", (CHAT,))
    return state.add_model(name, cli, model, "s1")


def test_the_full_list_of_a_cli_with_a_list_offers_no_other_name():
    external("Second")
    external("first")
    external("Kilo's", "kilo")
    listed = base.ModelList((), ("a/b", "c/d"), "opencode models")
    choices = model_settings.choices(providers.get("opencode"), lambda provider: listed)
    assert (choices.aliases, choices.models, choices.why) == ((), ("a/b", "c/d"), "")
    assert [m.name for m in choices.external] == ["first", "Second"]
    assert choices.other_name is False


def test_the_full_list_of_claude_code_is_its_aliases_and_an_other_name():
    listed = base.ModelList(("opus",), None, why="Claude Code gives no list beyond its aliases")
    choices = model_settings.choices(providers.get("claude"), lambda provider: listed)
    assert (choices.aliases, choices.models) == (("opus",), None)
    assert choices.why == "Claude Code gives no list beyond its aliases"
    assert choices.other_name is True


def test_a_list_that_cannot_be_read_keeps_the_external_models():
    external("K", "kilo")
    listed = base.ModelList(why="`kilo models` timed out after 15 s")
    choices = model_settings.choices(providers.get("kilo"), lambda provider: listed)
    assert [m.name for m in choices.external] == ["K"]
    assert (choices.why, choices.other_name) == ("`kilo models` timed out after 15 s", True)


def test_which_clis_take_a_whole_process_for_an_external_model():
    whole = {name: providers.get(name).external_whole_process for name in providers.names()}
    assert whole == {"claude": True, "codex": True, "kilo": False, "opencode": False}


# An agent CLI's default model.


@pytest.fixture
def installed(tmp_path):
    """`installed(cli, …)`: an environment whose PATH holds those CLIs and no other."""

    def env_of(*clis):
        for cli in clis:
            command = tmp_path / providers.get(cli).command
            command.write_text("#!/bin/sh\n")
            command.chmod(0o755)
        return lambda provider: {"PATH": str(tmp_path)}

    return env_of


OPENCODE_LIST = base.ModelList((), ("anthropic/claude-sonnet-4",), "opencode models")
CLAUDE_LIST = base.ModelList(("opus",), None, why="Claude Code gives no list beyond its aliases")


def test_an_external_default_is_found_ignoring_case_and_asks_no_server(installed, monkeypatch):
    saved = external()
    listing(monkeypatch, "opencode", OPENCODE_LIST)
    ref, verdict = model_settings.set_default("opencode", "локальная qwen", installed("opencode"))
    assert ref == state.ModelRef("opencode", saved.id, None)
    assert verdict is None
    assert state.cli_defaults() == [ref]


def test_an_external_default_is_set_when_the_list_cannot_be_read(installed, monkeypatch):
    saved = external()
    listing(monkeypatch, "opencode", base.ModelList(why="no list"))
    ref, _ = model_settings.set_default("opencode", "Локальная Qwen", installed("opencode"))
    assert ref.model_id == saved.id


def test_a_built_in_default_of_an_alias(installed, monkeypatch):
    seen = listing(monkeypatch, "claude", CLAUDE_LIST)
    env = installed("claude")
    ref, verdict = model_settings.set_default("claude", " opus ", env)
    assert ref == state.ModelRef("claude", None, "opus")
    assert (verdict.kind, verdict.text) == (model_check.OK, "an alias of Claude Code")
    assert seen == [env(None)]


def test_a_built_in_default_the_list_lacks_is_refused(installed, monkeypatch):
    listing(monkeypatch, "opencode", OPENCODE_LIST)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("opencode", "anthropic/claude-sonet-4", installed("opencode"))
    assert str(refused.value) == (
        "anthropic/claude-sonet-4 is not in OpenCode's list of models; opencode models prints "
        "the list"
    )
    assert refused.value.page == "anthropic/claude-sonet-4 is not in OpenCode's list of models"
    assert state.cli_defaults() == []


def test_a_built_in_default_with_no_list_is_set_with_a_warning(installed, monkeypatch):
    listing(monkeypatch, "claude", CLAUDE_LIST)
    ref, verdict = model_settings.set_default(
        "claude", "claude-opus-4-1-20250805", installed("claude")
    )
    assert ref.builtin == "claude-opus-4-1-20250805"
    assert verdict.kind == model_check.WARN
    assert verdict.text == (
        "Claude Code gives no list beyond its aliases: LADO cannot check "
        "claude-opus-4-1-20250805; a wrong name stops its agents at their first turn"
    )


def test_one_name_of_two_models_is_refused(installed, monkeypatch):
    external("qwen3-8b")
    listing(monkeypatch, "opencode", base.ModelList((), ("qwen3-8b",), "opencode models"))
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("opencode", "QWEN3-8B", installed("opencode"))
    assert str(refused.value) == (
        '"qwen3-8b" is both a saved model of OpenCode and one of its own; rename the saved one: '
        "Settings → Models"
    )
    assert state.cli_defaults() == []


def test_another_cli_s_model_is_refused_on_a_cli_with_no_list(installed, monkeypatch):
    external()
    seen = listing(monkeypatch, "claude", CLAUDE_LIST)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("claude", "локальная qwen", installed("claude"))
    assert str(refused.value) == '"Локальная Qwen" is a model of OpenCode, not of Claude Code'
    assert len(seen) == 1
    assert state.cli_defaults() == []


def test_a_built_in_name_another_cli_s_model_also_has_is_set(installed, monkeypatch):
    external("opus")
    listing(monkeypatch, "claude", CLAUDE_LIST)
    ref, _ = model_settings.set_default("claude", "opus", installed("claude"))
    assert ref == state.ModelRef("claude", None, "opus")


def test_a_cli_not_installed_or_not_known_is_refused(installed, monkeypatch):
    saved = external("K", "kilo")
    seen = listing(monkeypatch, "kilo", base.ModelList(why="no list"))
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("kilo", "K", installed())
    assert str(refused.value) == "Kilo CLI is not installed"
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("gemini", "K", installed())
    assert str(refused.value) == (
        'LADO knows no agent CLI "gemini"; it knows claude, codex, kilo, opencode'
    )
    assert refused.value.field == "cli"
    assert seen == []
    assert state.model_by_id(saved.id) is not None
    assert state.cli_defaults() == []


@pytest.mark.parametrize(
    ("model", "says"),
    [
        ("  ", "the model is empty"),
        ("a​b", "a model is one line of visible text: U+200B ZERO WIDTH SPACE is not allowed"),
    ],
)
def test_a_default_that_is_no_name_is_refused(installed, monkeypatch, model, says):
    listing(monkeypatch, "claude", CLAUDE_LIST)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default("claude", model, installed("claude"))
    assert (str(refused.value), refused.value.field) == (says, "model")


def test_a_default_set_by_reference_takes_the_model_of_the_id(installed, monkeypatch):
    saved = external("qwen3-8b")
    listing(monkeypatch, "opencode", base.ModelList((), ("qwen3-8b",), "opencode models"))
    env = installed("opencode")
    ref = state.ModelRef("opencode", saved.id, None)
    assert model_settings.set_default_ref(ref, env) == (ref, None)
    built_in = state.ModelRef("opencode", None, "qwen3-8b")
    set_ref, verdict = model_settings.set_default_ref(built_in, env)
    assert (set_ref, verdict.kind) == (built_in, model_check.OK)
    assert state.cli_defaults() == [built_in]


def test_a_default_set_by_reference_refuses_another_cli_s_or_a_gone_model(installed):
    saved = external()
    env = installed("claude")
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default_ref(state.ModelRef("claude", saved.id, None), env)
    assert str(refused.value) == '"Локальная Qwen" is a model of OpenCode, not of Claude Code'
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default_ref(state.ModelRef("claude", "nope", None), env)
    assert str(refused.value) == "that model is no longer saved"
    assert state.cli_defaults() == []


def test_a_default_set_by_reference_uses_the_list_given(installed, monkeypatch):
    seen = listing(monkeypatch, "claude", CLAUDE_LIST)
    given = []

    def kept(provider):
        given.append(provider.name)
        return CLAUDE_LIST

    ref = state.ModelRef("claude", None, "opus")
    model_settings.set_default_ref(ref, installed("claude"), kept)
    assert (given, seen) == (["claude"], [])


def test_a_model_removed_between_the_check_and_the_save_is_refused(installed, monkeypatch):
    saved = external()
    listing(monkeypatch, "opencode", OPENCODE_LIST)
    env = installed("opencode")
    real = state.set_cli_default

    def late(ref):
        state.remove_model(saved.name)
        real(ref)

    monkeypatch.setattr(state, "set_cli_default", late)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.set_default_ref(state.ModelRef("opencode", saved.id, None), env)
    assert str(refused.value) == "that model is no longer saved"


def test_clearing_a_default_of_a_cli_not_installed(installed):
    state.set_cli_default(state.ModelRef("kilo", None, "x/y"))
    assert model_settings.clear_default("kilo") is True
    assert model_settings.clear_default("kilo") is False
    assert state.cli_defaults() == []
    with pytest.raises(model_settings.Refused, match='LADO knows no agent CLI "gemini"'):
        model_settings.clear_default("gemini")


def test_the_defaults_name_their_model_and_server():
    saved = external()
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    state.set_cli_default(state.ModelRef("claude", None, "opus"))
    state.rename_model(saved.name, "Alpha")
    claude, opencode = model_settings.defaults()
    assert (claude.ref.cli, claude.name, claude.model, claude.server) == (
        "claude",
        "opus",
        "opus",
        None,
    )
    assert (opencode.ref.model_id, opencode.name, opencode.model, opencode.server) == (
        saved.id,
        "Alpha",
        "qwen3-8b",
        "lms",
    )


def test_removing_a_default_s_model_says_the_cli_cleared():
    saved = external()
    other = external("Other")
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    events = []
    model_settings.remove_models(
        [other.name, saved.name],
        lambda name: events.append(("removed", name)),
        lambda cli: events.append(("cleared", cli)),
    )
    assert events == [
        ("removed", "Other"),
        ("removed", "Локальная Qwen"),
        ("cleared", "opencode"),
    ]


def test_removing_a_server_says_the_defaults_cleared(serve):
    add("lms", serve("lmstudio").url)
    id = state.model_server("lms").id
    saved = state.add_model("coder-oc", "opencode", "qwen3-8b", id)
    state.add_model("sp", "kilo", "qwen3-8b", id)
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    removed, cleared = [], []
    model_settings.remove_server(
        "lms", with_models=True, removed=removed.append, cleared=cleared.append
    )
    assert (removed, cleared) == (["coder-oc", "sp"], ["opencode"])
    assert state.cli_defaults() == []


# What an agent starts on.


OPENCODE, KILO, CLAUDE, CODEX = (
    providers.get(name) for name in ("opencode", "kilo", "claude", "codex")
)
EMPTY = base.ModelList(models=("opencode/big-pickle",), command="opencode models")


def entry(name="Локальная Qwen", cli="opencode", model="qwen3-8b", server="LM Studio дома"):
    """A saved model on a server of that name, saved first when new."""
    saved = state.model_server(server) or state.add_model_server(
        server.encode().hex()[:12], server, "http://localhost:1234", "LM Studio", [CHAT]
    )
    return state.add_model(name, cli, model, saved.id)


def default_on(saved):
    state.set_cli_default(state.ModelRef(saved.cli, saved.id, None))


def external_table(saved):
    return state.PowerTable.of(state.PowerRow(saved.cli, saved.model, saved.id, saved.name))


def test_the_row_of_the_session_goes_first():
    default_on(entry())
    start = model_settings.start_model(state.PowerTable.single("opencode", "x/y"), OPENCODE)
    assert (start.name, start.model, start.server, start.source) == ("x/y", "x/y", None, "session")


def test_an_external_row_is_read_by_its_id():
    saved = entry()
    table = external_table(saved)
    state.rename_model(saved.name, "Qwen дома")
    start = model_settings.start_model(table, OPENCODE)
    assert (start.name, start.model, start.source) == ("Qwen дома", "qwen3-8b", "session")
    assert start.server.name == "LM Studio дома" and not start.gone
    server_id = start.server.id
    assert start.launch_name(OPENCODE) == f"lado-{server_id}/qwen3-8b"


def test_the_settings_row_goes_past_a_default():
    default_on(entry())
    start = model_settings.start_model(state.PowerTable.single("opencode", ""), OPENCODE)
    assert (start.name, start.model, start.source) == (None, None, "cli")


def test_no_table_takes_the_default():
    default_on(entry())
    start = model_settings.start_model(None, OPENCODE)
    assert (start.name, start.model, start.source) == ("Локальная Qwen", "qwen3-8b", "default")


def test_a_built_in_default():
    state.set_cli_default(state.ModelRef("opencode", None, "opencode/big-pickle"))
    start = model_settings.start_model(None, OPENCODE)
    assert (start.model, start.server, start.source) == ("opencode/big-pickle", None, "default")


def test_nothing_set_is_the_cli_s_choice():
    start = model_settings.start_model(None, OPENCODE)
    assert (start.name, start.model, start.source, start.note) == (None, None, "cli", None)


def test_a_table_of_another_cli_takes_the_agent_s_default():
    default_on(entry("Qwen в Kilo", "kilo"))
    start = model_settings.start_model(state.PowerTable.single("opencode", "x/y"), KILO)
    assert (start.name, start.source, start.note) == ("Qwen в Kilo", "default", None)


def test_a_table_of_another_cli_with_no_default_says_so():
    start = model_settings.start_model(state.PowerTable.single("codex", "gpt-5.6-sol"), CLAUDE)
    assert start.model is None and start.source == "cli"
    assert start.note == "the session's model gpt-5.6-sol is for Codex CLI"


def test_a_settings_row_of_another_cli_has_no_note():
    start = model_settings.start_model(state.PowerTable.single("codex", ""), CLAUDE)
    assert start.note is None


def test_an_entry_removed_is_gone():
    saved = entry()
    table = external_table(saved)
    state.remove_model(saved.name)
    start = model_settings.start_model(table, OPENCODE)
    assert start.gone and start.name == "Локальная Qwen" and start.server is None
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, OPENCODE, {})
    assert str(refused.value) == (
        "the session ran on the model Локальная Qwen, which is no longer saved; resume it with "
        "--model '' for OpenCode's settings or --model <model> for another"
    )


def test_an_unreadable_table_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.start_model(state.PowerTable.unreadable(), OPENCODE)
    assert str(refused.value) == (
        "the session's model cannot be read; resume it with --model '' for OpenCode's settings "
        "or --model <model> for another"
    )


# A name given for a session.


@pytest.fixture
def on_path(monkeypatch):
    monkeypatch.setattr(model_settings.shutil, "which", lambda *a, **k: "/bin/x")


def test_an_empty_name_is_the_settings(on_path):
    assert model_settings.session_row("", OPENCODE, {}) == state.PowerRow("opencode", "")
    assert model_settings.session_row("  ", OPENCODE, {}) == state.PowerRow("opencode", "")


def test_a_built_in_name_is_a_built_in_row(on_path):
    row = model_settings.session_row("opencode/big-pickle", OPENCODE, {}, lambda _: EMPTY)
    assert row == state.PowerRow("opencode", "opencode/big-pickle")


def test_an_external_name_is_an_external_row_ignoring_case(on_path):
    saved = entry()
    row = model_settings.session_row("локальная qwen", OPENCODE, {}, lambda _: EMPTY)
    assert row == state.PowerRow("opencode", "qwen3-8b", saved.id, "Локальная Qwen")


def test_another_cli_s_external_name_is_refused(on_path):
    entry()
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.session_row("Локальная Qwen", CLAUDE, {}, lambda _: base.ModelList())
    assert str(refused.value) == '"Локальная Qwen" is a model of OpenCode, not of Claude Code'


# The check before a start.


def counting_probe(found=None, error=None):
    asked = []

    def probe(server):
        asked.append(server.name)
        if error:
            raise error
        return found

    probe.asked = asked
    return probe


def found_on_server(*models, apis=(CHAT,), why=""):
    return model_servers.Probe(
        "http://localhost:1234",
        False,
        "LM Studio",
        frozenset(apis),
        models or None,
        why,
        "",
        frozenset(),
    )


def test_nothing_to_check_asks_nothing():
    probe = counting_probe()
    verdict = model_settings.check_start(
        model_settings.start_model(None, OPENCODE), OPENCODE, {}, probe
    )
    assert verdict.kind == model_check.DEFAULT and probe.asked == []


def test_a_built_in_model_is_checked_against_the_list():
    start = model_settings.start_model(state.PowerTable.single("opencode", "x/y"), OPENCODE)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, OPENCODE, {}, listing=lambda _: EMPTY)
    assert str(refused.value) == (
        "x/y is not in OpenCode's list of models; opencode models prints the list"
    )


def test_an_external_model_is_on_its_server():
    default_on(entry())
    probe = counting_probe(found_on_server("qwen3-8b"))
    start = model_settings.start_model(None, OPENCODE)
    assert model_settings.check_start(start, OPENCODE, {}, probe).kind == model_check.OK
    assert probe.asked == ["LM Studio дома"]


def test_a_server_with_no_list_warns():
    default_on(entry())
    probe = counting_probe(found_on_server(why="its answer lists no models"))
    start = model_settings.start_model(None, OPENCODE)
    verdict = model_settings.check_start(start, OPENCODE, {}, probe)
    assert verdict.kind == model_check.WARN and "LADO cannot check qwen3-8b" in verdict.text


def test_a_model_gone_from_its_server_is_refused():
    default_on(entry())
    start = model_settings.start_model(None, OPENCODE)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, OPENCODE, {}, counting_probe(found_on_server("other")))
    assert str(refused.value) == (
        "qwen3-8b is not in LM Studio дома's list of models; lado model-server probe "
        "http://localhost:1234 prints the list"
    )
    assert refused.value.page == "qwen3-8b is not in LM Studio дома's list of models"
    assert refused.value.retry


def test_a_silent_server_is_refused_in_the_words_of_each_place():
    default_on(entry())
    start = model_settings.start_model(None, OPENCODE)
    error = model_servers.ProbeError(
        "http://localhost:1234 does not answer (connection refused)", silent="connection refused"
    )
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, OPENCODE, {}, counting_probe(error=error))
    assert str(refused.value) == (
        "http://localhost:1234 does not answer (connection refused); LADO cannot check qwen3-8b"
    )
    assert refused.value.window == (
        "LM Studio дома does not answer (connection refused); qwen3-8b is on it. Start the "
        "server or pick another model."
    )
    assert refused.value.short == "LM Studio дома does not answer"
    assert refused.value.peek == "not answering"
    assert refused.value.retry


@pytest.mark.parametrize("apis", [(CHAT,), ()], ids=["OpenCode suits", "nothing suits"])
def test_a_cli_on_no_server_is_refused_with_no_request(apis):
    server = state.add_model_server("gw", "Шлюз", "http://gw", "OpenAI-compatible", apis)
    saved = state.add_model("Шлюз GPT", "codex", "gw-gpt", server.id)
    default_on(saved)
    probe = counting_probe()
    start = model_settings.start_model(None, CODEX)
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, CODEX, {}, probe)
    who = "Kilo CLI and OpenCode do" if apis else "no agent CLI runs on it yet"
    assert str(refused.value) == (
        f"Шлюз GPT is on the model server Шлюз; Codex CLI does not run on a model server yet, {who}"
    )
    assert probe.asked == [] and not refused.value.retry


@pytest.mark.parametrize(
    ("name", "model"),
    [("Со {env:HOME}", "qwen3-8b"), ("Qwen", "{file:/etc/passwd}")],
    ids=["name", "model"],
)
def test_text_a_cli_would_expand_cannot_be_a_start_model(name, model):
    default_on(entry(name, model=model))
    probe = counting_probe()
    start = model_settings.start_model(None, OPENCODE)
    with pytest.raises(model_settings.Refused, match="the agent CLI would expand"):
        model_settings.check_start(start, OPENCODE, {}, probe)
    assert probe.asked == []


def test_the_way_out_says_where_the_model_came_from():
    default_on(entry())
    default = model_settings.start_model(None, OPENCODE)
    assert model_settings.way_out(default, OPENCODE, given=False) == (
        "; it is OpenCode's default model: start with --model '' for its settings, or change it "
        "with lado model default opencode"
    )
    kept = model_settings.start_model(state.PowerTable.single("opencode", "x/y"), OPENCODE)
    assert model_settings.way_out(kept, OPENCODE, given=False) == (
        "; the session ran on it before: resume it with --model '' for OpenCode's settings or "
        "--model <model> for another"
    )
    assert model_settings.way_out(kept, OPENCODE, given=True) == ""


# The servers of an agent's config.


def write_key(saved, key):
    model_settings._write_key(saved.server, key)


def test_the_ticked_models_are_grouped_by_server():
    one = entry()
    other = entry("Рабочая Qwen", model="qwen3-coder-30b")
    gateway = entry("Шлюз Qwen", model="qwen/qwen3", server="Шлюз")
    entry("Qwen в Kilo", cli="kilo")
    write_key(gateway, "secret-key")
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert warnings == []
    assert [server.name for server in found] == ["LM Studio дома", "Шлюз"]
    home, gate = found
    assert home.models == (("qwen3-8b", one.name), ("qwen3-coder-30b", other.name))
    assert home.base_url == "http://localhost:1234/v1"
    assert (home.key, home.key_variable) == (None, "")
    assert gate.key == "secret-key"
    assert gate.key_variable == f"LADO_MODEL_KEY_{gateway.server.upper()}"
    assert "secret-key" not in repr(gate)


def on_fake(fake_server, name="Малая", model="small", cli="opencode"):
    """A saved model on the fake server, by a server of its own name."""
    saved = state.model_server(fake_server.url) or state.add_model_server(
        f"{fake_server.port:012x}", fake_server.url, fake_server.url, "LiteLLM", [CHAT]
    )
    return state.add_model(name, cli, model, saved.id)


def test_a_server_s_limits_go_with_its_entry(serve):
    on_fake(serve("gateway-limits"))
    (found,), warnings = model_settings.agent_servers(OPENCODE)
    assert found.limits["small"] == base.Limit(16000, 2048)
    assert warnings == []


def test_a_server_that_reports_nothing_has_no_limits_and_no_warning():
    default_on(entry())
    start = model_settings.start_model(None, OPENCODE)
    (found,), warnings = model_settings.agent_servers(OPENCODE, start)
    assert found.limits == {}
    assert warnings == []


def test_silent_servers_cost_one_ceiling_together(serve, monkeypatch):
    monkeypatch.setattr(model_servers, "LIMIT_TIMEOUT", 0.5)
    on_fake(serve("hang"), "Первая")
    on_fake(serve("hang"), "Вторая")
    on_fake(serve("hang"), "Третья")
    began = time.monotonic()
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert time.monotonic() - began < 1.2
    assert len(found) == 3 and warnings == []


def warned(server, cli, model="small"):
    saved = on_fake(server, model=model, cli=cli.name)
    default_on(saved)
    return model_settings.agent_servers(cli, model_settings.start_model(None, cli))[1]


@pytest.mark.parametrize(("cli", "need"), [(OPENCODE, "32,768"), (providers.get("kilo"), "49,152")])
def test_a_start_below_the_cli_s_need_warns(serve, cli, need):
    server = serve("gateway-limits")
    assert warned(server, cli) == [
        f"Малая on {server.url} has a context of 16,000 tokens; {cli.title} needs about "
        f"{need} for its instructions and tools: load the model with a larger context; see "
        '"What to expect of a small model" in docs/install.md'
    ]


@pytest.mark.parametrize(
    ("kind", "how"),
    [
        (
            model_servers.LMSTUDIO,
            "load the model with a larger context (lms load --context-length)",
        ),
        (model_servers.OLLAMA, "raise OLLAMA_CONTEXT_LENGTH, or the context in the Ollama app"),
        (model_servers.OPENAI, "load the model with a larger context"),
    ],
)
def test_the_warning_says_where_a_server_of_a_known_kind_sets_the_context(kind, how):
    server = state.ModelServer("id", "Дома", "http://localhost:1", kind, (CHAT,), "")
    start = model_settings.StartModel(name="m", model="m", server=server)
    warning = model_settings.context_warning(start, OPENCODE, base.Limit(4000))
    assert f"tools: {how}; see " in warning


def test_a_context_at_the_need_does_not_warn():
    start = model_settings.StartModel(name="m", model="m", server=None)
    assert model_settings.context_warning(start, OPENCODE, base.Limit(32768)) is None
    assert model_settings.context_warning(start, OPENCODE, base.Limit(32767)) is not None


def test_an_unknown_context_off_a_server_does_not_warn():
    start = model_settings.StartModel(name="m", model="m", server=None)
    assert model_settings.context_warning(start, OPENCODE, None) is None


@pytest.mark.parametrize("address", ["http://localhost:1", "http://192.168.1.10:1234"])
def test_an_unknown_context_on_a_local_server_does_not_warn(address):
    server = state.ModelServer("id", "Дома", address, model_servers.OPENAI, (CHAT,), "")
    start = model_settings.StartModel(name="m", model="m", server=server)
    assert model_settings.context_warning(start, OPENCODE, None) is None


def test_an_unknown_context_on_a_public_server_warns_and_a_known_one_does_not():
    server = state.ModelServer(
        "id", "Облако", "https://llm.example.com", model_servers.OPENAI, (CHAT,), ""
    )
    start = model_settings.StartModel(name="Большая", model="m", server=server)
    assert model_settings.context_warning(start, OPENCODE, None) == (
        "Большая on Облако: the server reports no context for it, so the agent compacts late and "
        'its answers have no limit; see "A cloud provider" in docs/install.md'
    )
    assert model_settings.context_warning(start, OPENCODE, base.Limit(131072)) is None


def test_a_cli_with_no_need_never_warns():
    start = model_settings.StartModel(name="m", model="m", server=None)
    assert model_settings.context_warning(start, CODEX, base.Limit(1)) is None


def test_a_small_model_the_agent_does_not_start_on_does_not_warn(serve):
    on_fake(serve("gateway-limits"))
    assert model_settings.agent_servers(OPENCODE)[1] == []


def test_a_cli_on_no_server_gets_no_servers():
    default_on(entry("Шлюз GPT", cli="codex", model="gw-gpt"))
    start = model_settings.start_model(None, CODEX)
    assert model_settings.agent_servers(CODEX, start) == ((), [])


def test_a_cli_of_one_model_per_process_gets_the_server_of_its_start_alone():
    saved = entry("Шлюз Opus", cli="claude", model="gw-opus", server="Шлюз")
    entry("Шлюз Sonnet", cli="claude", model="gw-sonnet", server="Шлюз")
    entry("Другая", cli="claude", model="other", server="Другой")
    write_key(saved, "k")
    default_on(saved)
    start = model_settings.start_model(None, CLAUDE)
    (found,), warnings = model_settings.agent_servers(CLAUDE, start)
    assert (found.id, found.name, found.models) == (
        saved.server,
        "Шлюз",
        (("gw-opus", "Шлюз Opus"),),
    )
    assert (found.key_variable, found.key) == (f"LADO_MODEL_KEY_{saved.server.upper()}", "k")
    assert (found.root, found.base_url) == ("http://localhost:1234", "http://localhost:1234/v1")
    assert warnings == []


def test_a_cli_of_one_model_per_process_on_a_built_in_model_gets_no_server():
    entry("Шлюз Opus", cli="claude", model="gw-opus", server="Шлюз")
    table = state.PowerTable.single("claude", "opus")
    start = model_settings.start_model(table, CLAUDE)
    assert model_settings.agent_servers(CLAUDE, start) == ((), [])
    assert model_settings.agent_servers(CLAUDE) == ((), [])


def test_a_cli_of_one_model_per_process_has_the_limits_of_its_model(serve):
    saved = on_fake(serve("gateway-limits"), model="small", cli="claude")
    default_on(saved)
    start = model_settings.start_model(None, CLAUDE)
    (found,), warnings = model_settings.agent_servers(CLAUDE, start)
    assert found.limits["small"] == base.Limit(16000, 2048)
    assert len(warnings) == 1 and "needs about 65,536" in warnings[0]


def test_a_key_that_cannot_be_read_refuses_the_one_server_of_a_start():
    saved = entry("Шлюз Opus", cli="claude", model="gw-opus", server="Шлюз")
    default_on(saved)
    write_key(saved, "k")
    key = model_settings.key_folder(saved.server) / model_settings.KEY
    key.unlink()
    key.symlink_to("/etc/hostname")
    start = model_settings.start_model(None, CLAUDE)
    with pytest.raises(model_settings.Refused, match="symbolic link"):
        model_settings.agent_servers(CLAUDE, start)


def test_a_key_that_cannot_be_read_leaves_its_server_out():
    saved = entry()
    other = entry("Шлюз Qwen", model="gw-qwen", server="Шлюз")
    write_key(saved, "k")
    key = model_settings.key_folder(saved.server) / model_settings.KEY
    key.unlink()
    key.symlink_to("/etc/hostname")
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert [server.id for server in found] == [other.server]
    assert len(warnings) == 1 and "LM Studio дома" in warnings[0] and "left out" in warnings[0]


def test_a_key_that_cannot_be_read_refuses_the_server_of_the_start():
    saved = entry()
    default_on(saved)
    write_key(saved, "k")
    key = model_settings.key_folder(saved.server) / model_settings.KEY
    key.unlink()
    key.symlink_to("/etc/hostname")
    start = model_settings.start_model(None, OPENCODE)
    with pytest.raises(model_settings.Refused, match="symbolic link"):
        model_settings.agent_servers(OPENCODE, start)


@pytest.mark.parametrize("key", ['ab"cd', "ab\\cd", "ab\tcd"], ids=["quote", "backslash", "tab"])
def test_a_key_that_would_break_the_config_leaves_its_server_out(key):
    saved = entry()
    other = entry("Шлюз Qwen", model="gw-qwen", server="Шлюз")
    write_key(saved, key)
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert [server.id for server in found] == [other.server]
    assert len(warnings) == 1 and "LM Studio дома" in warnings[0] and "left out" in warnings[0]
    assert key not in warnings[0]


@pytest.mark.parametrize("key", ['ab"cd', "ab\\cd", "ab\tcd"], ids=["quote", "backslash", "tab"])
def test_a_key_that_would_break_the_config_refuses_the_start_on_its_server(key):
    saved = entry()
    default_on(saved)
    write_key(saved, key)
    start = model_settings.start_model(None, OPENCODE)
    probe = counting_probe(found_on_server("m1"))
    with pytest.raises(model_settings.Refused) as refused:
        model_settings.check_start(start, OPENCODE, {}, probe)
    assert 'the key of model server "LM Studio дома"' in str(refused.value)
    assert key not in str(refused.value)
    assert probe.asked == []
    with pytest.raises(model_settings.Refused):
        model_settings.agent_servers(OPENCODE, start)


@pytest.mark.parametrize(
    ("model", "name", "server"),
    [
        ("{env:HOME}", "Qwen", "LM Studio дома"),
        ("qwen3-8b", "Со {file:x}", "LM Studio дома"),
    ],
    ids=["id", "name"],
)
def test_a_model_a_cli_would_expand_is_left_out(model, name, server):
    entry(name, model=model, server=server)
    good = entry("Рабочая Qwen", model="qwen3-coder-30b", server=server)
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert found[0].models == ((good.model, good.name),)
    assert len(warnings) == 1 and name in warnings[0] and "left out" in warnings[0]


def test_a_server_a_cli_would_expand_is_left_out():
    entry(server="Со {env:HOME}")
    found, warnings = model_settings.agent_servers(OPENCODE)
    assert found == () and "left out" in warnings[0]


def test_a_key_over_plain_http_to_a_public_address_is_warned_about():
    server = state.add_model_server("gw", "Шлюз", "http://llm.example.com", "OpenAI", [CHAT])
    saved = state.add_model("Qwen", "opencode", "q", server.id)
    write_key(saved, "k")
    _, warnings = model_settings.agent_servers(OPENCODE)
    assert warnings == [model_servers.PLAIN_HTTP.format(host="llm.example.com")]


# LADO's models by the name the CLI gives them.


def _agent_on(saved, source, session_power=None):
    state.add_session(state.Session("s", "/r", None, provider=saved.cli, power=session_power))
    agent = state.Agent("s", "w1", "worker", "/r", None, None, "starting", saved.cli)
    state.add_agent(agent)
    named = f"lado-{saved.server}/{saved.model}"
    state.set_model("s", "w1", state.Choice(named, source), None)
    return state.get_agent("s", "w1")


def test_an_agent_keeps_the_name_it_started_on_beside_a_twin():
    """Two entries of one CLI, model and server are allowed: a twin saved first by name must not
    take the agent's name."""
    chosen = entry("Абрикос")
    entry("Яблоко")  # the same model and server, read after it
    agent = _agent_on(chosen, state.SESSION, external_table(chosen))
    assert model_settings.model_name(agent) == "Абрикос"
    assert model_settings.agent_shown(agent).name == "Абрикос"


def test_an_agent_on_a_default_keeps_its_name_beside_a_twin():
    chosen = entry("Абрикос")
    entry("Яблоко")
    default_on(chosen)
    agent = _agent_on(chosen, state.DEFAULT_MODEL)
    assert model_settings.model_name(agent) == "Абрикос"


def test_a_model_renamed_while_the_agent_runs_shows_the_new_name():
    chosen = entry("Абрикос")
    entry("Яблоко")  # a twin must not take it either
    agent = _agent_on(chosen, state.SESSION, external_table(chosen))
    state.rename_model("Абрикос", "Персик")
    assert model_settings.model_name(agent) == "Персик"


def test_a_default_renamed_while_the_agent_runs_shows_the_new_name():
    chosen = entry("Абрикос")
    default_on(chosen)
    agent = _agent_on(chosen, state.DEFAULT_MODEL)
    state.rename_model("Абрикос", "Персик")
    assert model_settings.model_name(agent) == "Персик"


def test_the_config_names_a_model_of_two_entries_as_the_agent_started_on_it():
    chosen = entry("Абрикос")
    entry("Яблоко")  # the same model and server
    default_on(chosen)
    start = model_settings.start_model(None, OPENCODE)
    found, _ = model_settings.agent_servers(OPENCODE, start)
    assert found[0].models == (("qwen3-8b", "Абрикос"),)


def test_a_model_of_two_entries_stands_once_in_the_config():
    entry("Абрикос")
    entry("Яблоко")
    found, _ = model_settings.agent_servers(OPENCODE)
    assert found[0].models == (("qwen3-8b", "Абрикос"),)


def test_a_model_changed_in_the_cli_is_found_by_its_id():
    chosen = entry("Яблоко")
    other = entry("Абрикос", model="m2")
    agent = _agent_on(other, state.CLI_CHANGED, external_table(chosen))
    assert model_settings.model_name(agent) == "Абрикос"


def test_a_table_that_cannot_be_read_leaves_the_lookup_by_id():
    saved = entry("Яблоко")
    agent = _agent_on(saved, state.SESSION, state.PowerTable.unreadable())
    assert model_settings.model_name(agent) == "Яблоко"


def test_a_model_of_a_server_is_shown_by_its_entry():
    saved = entry("Рабочая Qwen", model="qwen/qwen3-coder")
    found = model_settings.shown(OPENCODE, f"lado-{saved.server}/qwen/qwen3-coder")
    assert found == model_settings.Shown(
        "Рабочая Qwen", "qwen/qwen3-coder", "LM Studio дома", "http://localhost:1234"
    )


def test_a_model_of_a_server_with_no_entry_is_shown_by_its_id():
    saved = entry()
    found = model_settings.shown(OPENCODE, f"lado-{saved.server}/other")
    assert found == model_settings.Shown(
        "other", "other", "LM Studio дома", "http://localhost:1234"
    )


def test_another_cli_s_entry_gives_no_name():
    saved = entry("Qwen в Kilo", cli="kilo")
    assert model_settings.shown(OPENCODE, f"lado-{saved.server}/qwen3-8b").name == "qwen3-8b"


def test_a_removed_server_and_a_built_in_model_are_shown_as_they_are():
    assert model_settings.shown(OPENCODE, "lado-gone/qwen3-8b") is None
    assert model_settings.shown(OPENCODE, "opencode/big-pickle") is None
    assert model_settings.shown(CLAUDE, "lado-gone/qwen3-8b") is None


# A name given for a worker.


CLAUDE = providers.get("claude")
KILO = providers.get("kilo")
SHARED = "vendor/shared"
OPENCODE_MODELS = base.ModelList((), ("opencode/big-pickle", SHARED), "opencode models")
KILO_MODELS = base.ModelList((), ("kilo/auto", SHARED), "kilo models")


class Lists:
    """Each CLI's list by name, recording which were read; a CLI with none has no full list."""

    def __init__(self, **lists):
        self.lists = lists
        self.reads = []

    def __call__(self, provider):
        self.reads.append(provider.name)
        return self.lists.get(provider.name, base.ModelList(why="no list"))


def worker_start(name, given, session_cli, env, lists):
    return model_settings.worker_start(name, given, session_cli, env, lists)


def test_a_name_of_the_session_s_cli_reads_no_other_list(installed):
    lists = Lists(opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    env = installed("opencode", "kilo")
    cli, start = worker_start(SHARED, None, OPENCODE, env, lists)
    assert cli is OPENCODE
    assert (start.name, start.model, start.source) == (SHARED, SHARED, "supervisor")
    assert set(lists.reads) == {"opencode"}


def test_a_name_only_another_cli_has_picks_that_cli(installed):
    env = installed("claude", "kilo", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    cli, start = worker_start("kilo/auto", None, CLAUDE, env, lists)
    assert cli is KILO
    assert (start.name, start.source) == ("kilo/auto", "supervisor")


def test_a_saved_model_of_another_cli_picks_that_cli_ignoring_case(installed):
    saved = entry()
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    cli, start = worker_start("локальная qwen", None, CLAUDE, env, lists)
    assert cli is OPENCODE
    assert (start.name, start.model, start.entry, start.source) == (
        "Локальная Qwen",
        "qwen3-8b",
        saved,
        "supervisor",
    )


def test_a_name_of_two_other_clis_is_refused_naming_them(installed):
    env = installed("claude", "kilo", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start(SHARED, None, CLAUDE, env, lists)
    assert str(refused.value) == f"{SHARED} is a model of Kilo CLI and OpenCode; give provider"


def test_a_name_of_no_cli_is_refused_pointing_to_list_models(installed):
    env = installed("kilo", "opencode")
    lists = Lists(opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("gpt-9", None, OPENCODE, env, lists)
    assert str(refused.value) == "gpt-9 is in no agent CLI's list of models; list_models shows them"


def test_a_free_name_with_no_provider_says_how_to_give_it(installed):
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("sonet", None, CLAUDE, env, lists)
    assert str(refused.value) == (
        "sonet is in no agent CLI's list of models; list_models shows them; Claude Code gives no "
        'full list: provider="claude" starts it with a warning'
    )


def test_a_provider_that_has_the_name_takes_it(installed):
    env = installed("claude", "kilo", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    cli, start = worker_start(SHARED, KILO, CLAUDE, env, lists)
    assert (cli, start.name) == (KILO, SHARED)
    assert "opencode" not in lists.reads


def test_a_free_name_with_its_provider_starts(installed):
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    cli, start = worker_start("claude-opus-5-5", CLAUDE, OPENCODE, env, lists)
    assert (cli, start.name, start.source) == (CLAUDE, "claude-opus-5-5", "supervisor")


def test_a_saved_model_of_another_cli_is_refused_for_a_provider(installed):
    entry()
    env = installed("kilo", "opencode")
    lists = Lists(opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("Локальная Qwen", KILO, OPENCODE, env, lists)
    assert str(refused.value) == '"Локальная Qwen" is a model of OpenCode, not of Kilo CLI'


def test_a_built_in_model_of_another_cli_is_refused_for_a_provider(installed):
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("opus", OPENCODE, CLAUDE, env, lists)
    assert str(refused.value) == "opus is a model of Claude Code, not of OpenCode"


def test_a_free_name_another_cli_has_is_refused_for_a_provider_of_no_full_list(installed):
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("opencode/big-pickle", CLAUDE, OPENCODE, env, lists)
    assert str(refused.value) == "opencode/big-pickle is a model of OpenCode, not of Claude Code"


def test_a_name_no_list_has_is_refused_by_the_list_of_its_provider(installed):
    env = installed("kilo", "opencode")
    lists = Lists(opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("gpt-9", OPENCODE, KILO, env, lists)
    assert str(refused.value) == (
        "gpt-9 is not in OpenCode's list of models; opencode models prints the list"
    )


def test_a_list_that_failed_or_a_cli_not_installed_has_no_name(installed):
    env = installed("kilo", "opencode")  # Claude Code would have the name, but is not installed
    lists = Lists(claude=base.ModelList(("opus",)), opencode=OPENCODE_MODELS)  # Kilo's failed
    with pytest.raises(model_settings.Refused) as refused:
        worker_start("opus", None, OPENCODE, env, lists)
    assert str(refused.value) == "opus is in no agent CLI's list of models; list_models shows them"
    assert "claude" not in lists.reads


def test_a_saved_model_of_a_cli_not_installed_says_so(installed):
    entry()
    env = installed("claude")
    with pytest.raises(model_settings.Refused, match="^OpenCode is not installed$"):
        worker_start("Локальная Qwen", None, CLAUDE, env, Lists(claude=CLAUDE_LIST))


def test_a_saved_name_of_one_cli_and_built_in_of_the_session_s_stays_with_the_session(installed):
    entry(SHARED)
    env = installed("kilo", "opencode")
    lists = Lists(kilo=KILO_MODELS)
    cli, start = worker_start(SHARED, None, KILO, env, lists)
    assert (cli, start.entry) == (KILO, None)  # the built-in one, not OpenCode's saved one


def test_a_saved_name_that_is_also_built_in_of_its_cli_keeps_the_start_s_refusal(installed):
    entry(SHARED)
    env = installed("opencode")
    with pytest.raises(model_settings.Refused, match="both a saved model of OpenCode"):
        worker_start(SHARED, None, OPENCODE, env, Lists(opencode=OPENCODE_MODELS))


def test_a_name_with_a_hidden_character_is_no_name(installed):
    env = installed("opencode")
    with pytest.raises(model_settings.Refused, match="a model is one line"):
        worker_start("gpt\x1b[2J", None, OPENCODE, env, Lists(opencode=OPENCODE_MODELS))


def test_an_empty_name_is_the_cli_s_own_settings_past_a_default(installed):
    default_on(entry())
    lists = Lists()
    cli, start = worker_start(" ", None, OPENCODE, installed("opencode"), lists)
    assert (cli, start) == (OPENCODE, model_settings.StartModel())
    assert lists.reads == []


def test_an_empty_name_with_a_provider_is_that_cli(installed):
    cli, start = worker_start("", KILO, OPENCODE, installed("opencode"), Lists())
    assert (cli, start) == (KILO, model_settings.StartModel())


# What list_models gives.


def session_of(provider, power=None):
    return state.Session("s", "/repo", None, provider, power=power)


def test_each_installed_cli_is_listed_with_the_session_s_first(installed):
    saved = entry()
    env = installed("claude", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS)
    clis = model_settings.cli_models(session_of("opencode"), None, env, lists)
    assert clis == [
        {
            "cli": "opencode",
            "title": "OpenCode",
            "session": True,
            "starts_on": None,
            "note": None,
            "builtin": ["opencode/big-pickle", SHARED],
            "external": [{"name": saved.name, "server": "LM Studio дома", "blocked": None}],
        },
        {
            "cli": "claude",
            "title": "Claude Code",
            "session": False,
            "starts_on": None,
            "note": "Claude Code gives no list beyond its aliases",
            "builtin": ["opus"],
            "external": [],
        },
    ]


def test_a_provider_narrows_the_list_to_its_cli(installed):
    env = installed("claude", "kilo", "opencode")
    lists = Lists(claude=CLAUDE_LIST, opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    clis = model_settings.cli_models(session_of("claude"), KILO, env, lists)
    assert [cli["cli"] for cli in clis] == ["kilo"]
    assert lists.reads == ["kilo"]


def test_a_provider_not_installed_is_refused(installed):
    env = installed("claude")
    with pytest.raises(model_settings.Refused, match="^Kilo CLI is not installed$"):
        model_settings.cli_models(session_of("claude"), KILO, env, Lists())


def test_an_external_model_of_a_cli_on_no_server_says_why_it_cannot_start(installed):
    entry("Шлюз GPT", cli="codex", server="Шлюз")
    env = installed("codex")
    [codex] = model_settings.cli_models(session_of("codex"), None, env, Lists())
    [external] = codex["external"]
    assert external["blocked"] == (
        "Шлюз GPT is on the model server Шлюз; Codex CLI does not run on a model server yet, "
        "Kilo CLI and OpenCode do"
    )


def test_a_saved_name_of_claude_code_s_own_says_why_it_cannot_start(installed):
    entry("Своя", cli="claude", model="sonnet", server="Шлюз")
    env = installed("claude")
    [claude] = model_settings.cli_models(session_of("claude"), None, env, Lists(claude=CLAUDE_LIST))
    [external] = claude["external"]
    assert external["blocked"].startswith("Claude Code reads sonnet as its own model")


def test_an_external_model_of_claude_code_is_not_blocked(installed):
    entry("Шлюз Opus", cli="claude", server="Шлюз")
    env = installed("claude")
    [claude] = model_settings.cli_models(session_of("claude"), None, env, Lists(claude=CLAUDE_LIST))
    assert [one["blocked"] for one in claude["external"]] == [None]


def test_starts_on_is_what_a_worker_of_each_cli_starts_on_with_no_model(installed):
    saved = entry()
    env = installed("kilo", "opencode")
    lists = Lists(opencode=OPENCODE_MODELS, kilo=KILO_MODELS)
    session = session_of("opencode", external_table(saved))
    clis = model_settings.cli_models(session, None, env, lists)
    assert {cli["cli"]: cli["starts_on"] for cli in clis} == {
        "opencode": "Локальная Qwen",
        "kilo": None,
    }


def test_a_table_that_cannot_be_read_starts_on_nothing_named(installed):
    session = session_of("opencode", state.PowerTable.unreadable())
    env = installed("opencode")
    [cli] = model_settings.cli_models(session, None, env, Lists(opencode=OPENCODE_MODELS))
    assert cli["starts_on"] is None


def test_the_list_asks_no_server_and_holds_no_address_or_key(serve, installed):
    key = "secret-key-of-the-canary"
    listening = serve("all", key=key)
    model_settings.add_server("Шлюз", listening.url, key, warn=print, note=print)
    server = state.model_server("Шлюз")
    state.add_model("Шлюз Qwen", "opencode", "m1", server.id)
    listening.requests.clear()
    clis = model_settings.cli_models(
        session_of("opencode"), None, installed("opencode"), Lists(opencode=OPENCODE_MODELS)
    )
    assert listening.requests == []
    assert clis[0]["external"][0]["server"] == "Шлюз"
    assert key not in str(clis) and listening.url not in str(clis)


# An agent of a CLI whose model names no server: its launch says which.


def _claude_agent_on(saved, source, table=None):
    state.add_session(state.Session("s", "/r", None, provider="claude", power=table))
    agent = state.Agent("s", "w1", "worker", "/r", None, None, state.STARTING, "claude")
    state.add_agent(agent)
    state.set_model("s", "w1", state.Choice(saved.model, source), None)
    config = base.config_dir(agent) / "settings.json"
    config.write_text(json.dumps({"env": {base.MODEL_SERVER: saved.server}}))
    return state.get_agent("s", "w1")


@pytest.mark.parametrize("source", [state.SESSION, state.DEFAULT_MODEL, state.SUPERVISOR_CHOICE])
def test_an_agent_on_a_server_is_shown_by_its_name_and_server(source):
    saved = entry("Шлюз Opus", cli="claude", model="gw-opus", server="Шлюз")
    agent = _claude_agent_on(saved, source)
    assert model_settings.model_name(agent) == "Шлюз Opus"
    assert model_settings.agent_shown(agent) == model_settings.Shown(
        "Шлюз Opus", "gw-opus", "Шлюз", "http://localhost:1234"
    )


def test_a_built_in_model_of_the_id_of_a_saved_one_is_shown_as_it_is():
    entry("Шлюз Opus", cli="claude", model="claude-opus-5-5", server="Шлюз")
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent = state.Agent("s", "w1", "worker", "/r", None, None, state.STARTING, "claude")
    state.add_agent(agent)
    state.set_model("s", "w1", state.Choice("claude-opus-5-5", state.SUPERVISOR_CHOICE), None)
    assert model_settings.agent_shown(state.get_agent("s", "w1")) is None
