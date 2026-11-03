"""The human's model servers and configured models (lado.model_settings): names, the key
file, the checks on adding, removal; against the fake servers of tests/fake_model_server.py
in process."""

import os
import socket
import sqlite3
import stat

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
    state.add_model("own", "claude", "haiku", None)
    folder = key_file("lms").parent
    removed = []
    assert model_settings.remove_server("LMS", with_models=True, removed=removed.append) == "lms"
    assert removed == ["coder-oc", "sp"]
    assert state.model_servers() == []
    assert [m.name for m in state.models()] == ["own"]
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
        add_model("W", "opencode", "gpt-oss-20b", "work", no_env)
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
    assert model_settings.clis(saved) == ["Kilo CLI", "OpenCode", "Codex CLI"]
    bare = state.add_model_server("s2", "bare", "https://x", "OpenAI-compatible", ())
    assert model_settings.clis(bare) == []


# Models.


def no_env(provider):
    raise AssertionError("a model on a server reads no CLI's list")


def listing(monkeypatch, name, listed):
    """The CLI `name` gives `listed`, read with the environment the command passes. Its
    class is patched, never the shared instance: undoing an instance's patch would leave
    the old bound method on it, over any later test's patch of the class."""
    seen = []
    provider = type(providers.get(name))
    monkeypatch.setattr(provider, "model_list", lambda self, env: seen.append(env) or listed)
    return seen


def add_model(name, cli, model, server=None, env=lambda provider: {"PATH": "/agents"}):
    return model_settings.add_model(name, cli, model, server, env)


def test_an_alias_of_the_cli_is_saved(monkeypatch):
    seen = listing(monkeypatch, "claude", base.ModelList(("haiku",), None, why="no list"))
    saved, verdict = add_model("Быстрая", "claude", " haiku ")
    assert (saved.name, saved.cli, saved.model, saved.server) == (
        "Быстрая",
        "claude",
        "haiku",
        None,
    )
    assert (verdict.kind, verdict.text) == (model_check.OK, "an alias of Claude Code")
    assert seen == [{"PATH": "/agents"}]


def test_a_name_the_cli_does_not_list_is_refused(monkeypatch):
    listing(
        monkeypatch,
        "opencode",
        base.ModelList((), ("anthropic/claude-sonnet-4",), "opencode models"),
    )
    with pytest.raises(model_settings.Refused) as refused:
        add_model("S", "opencode", "anthropic/claude-sonet-4")
    assert str(refused.value) == (
        "anthropic/claude-sonet-4 is not in OpenCode's list of models; opencode models prints "
        "the list"
    )
    assert state.models() == []


def test_a_cli_without_a_list_saves_with_a_warning(monkeypatch):
    listing(monkeypatch, "kilo", base.ModelList(why="kilo is not installed"))
    saved, verdict = add_model("K", "kilo", "x/y")
    assert verdict.kind == model_check.WARN
    assert verdict.text.startswith("kilo is not installed: LADO cannot check x/y")
    assert state.model("K") == saved


def test_a_cli_lado_does_not_know_is_refused():
    with pytest.raises(model_settings.Refused) as refused:
        add_model("G", "gemini", "x")
    assert str(refused.value) == (
        'LADO knows no agent CLI "gemini"; --cli takes one of claude, codex, kilo, opencode'
    )


def test_an_empty_model_is_refused():
    with pytest.raises(model_settings.Refused, match="the model is empty"):
        add_model("E", "claude", "  ")


def test_a_taken_name_is_refused_before_any_check(monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("haiku", "sonnet")))
    add_model("Быстрая", "claude", "haiku")
    seen = listing(monkeypatch, "claude", base.ModelList(("haiku", "sonnet")))
    with pytest.raises(model_settings.Refused) as refused:
        add_model("быстрая", "claude", "sonnet")
    assert str(refused.value) == (
        'a model "Быстрая" is saved already; remove it first: lado model remove "Быстрая"'
    )
    assert seen == []
    assert state.model("Быстрая").model == "haiku"


def test_a_server_no_one_saved_is_refused_without_a_request():
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "q", "nowhere", no_env)
    assert str(refused.value) == (
        'no model server "nowhere" is saved; lado model-server list names them'
    )


def test_a_model_on_a_server_in_its_list_is_saved(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    saved, verdict = add_model("Локальная Qwen", "opencode", "qwen3-8b", "lm studio дома", no_env)
    assert saved.server == state.model_server("LM Studio дома").id
    assert (verdict.kind, verdict.text) == (model_check.OK, "in LM Studio дома's list of models")


def test_a_model_the_server_does_not_list_is_refused(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "qwen3-14b", "LM Studio дома", no_env)
    assert str(refused.value) == (
        f"qwen3-14b is not in LM Studio дома's list of models; lado model-server probe "
        f"{server.url} prints the list"
    )
    assert state.models() == []


def test_an_embeddings_model_is_refused(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("emb", "opencode", fake.EMBEDDINGS, "lms", no_env)
    assert str(refused.value) == (
        f"{fake.EMBEDDINGS} is an embeddings model on lms; an agent needs a chat model: "
        f"lado model-server probe {server.url} lists the models"
    )
    assert state.models() == []
    saved, _ = add_model("chat", "opencode", "qwen3-8b", "lms", no_env)
    assert saved.model == "qwen3-8b"


def test_the_api_is_checked_before_the_embeddings(serve):
    server = serve("lmstudio")
    add("lms", server.url)
    with pytest.raises(model_settings.Refused, match="lms does not suit Claude Code"):
        add_model("emb", "claude", fake.EMBEDDINGS, "lms", no_env)


def test_a_server_without_types_is_checked_by_its_list(serve):
    server = serve("ollama")
    add("ol", server.url)
    _, verdict = add_model("O", "opencode", "llama3.1:8b", "ol", no_env)
    assert verdict.kind == model_check.OK


def test_a_server_with_no_list_saves_with_a_warning(serve):
    server = serve("responses-only")
    add("resp", server.url)
    _, verdict = add_model("C", "codex", "gpt-x", "resp", no_env)
    assert verdict.kind == model_check.WARN
    assert verdict.text.startswith("GET /v1/models: 404: LADO cannot check gpt-x")


def test_a_server_that_does_not_answer_refuses_the_model(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    server.close()
    with pytest.raises(model_settings.Refused) as refused:
        add_model("Q", "opencode", "qwen3-8b", "LM Studio дома", no_env)
    assert str(refused.value) == (
        f"{server.url} does not answer (connection refused); LADO cannot check qwen3-8b"
    )
    assert state.models() == []


def test_the_server_is_asked_with_its_kept_key(serve):
    server = serve("openai", key="k-1")
    add("work", server.url, key="k-1")
    server.requests.clear()
    add_model("W", "opencode", "gpt-oss-20b", "work", no_env)
    assert {r.headers["Authorization"] for r in server.requests} == {"Bearer k-1"}


def test_a_server_that_does_not_suit_the_cli_is_refused(serve):
    server = serve("openai")  # chat completions only
    add("LM Studio дома", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("C", "codex", "gpt-oss-20b", "LM Studio дома", no_env)
    assert str(refused.value) == (
        "LM Studio дома does not suit Codex CLI: it has no Responses API; it suits Kilo CLI, "
        "OpenCode"
    )


def test_a_server_that_suits_no_cli_says_so(serve):
    server = serve("models-only")
    add("bare", server.url)
    with pytest.raises(model_settings.Refused) as refused:
        add_model("C", "opencode", "m1", "bare", no_env)
    assert str(refused.value) == (
        "bare does not suit OpenCode: it has no chat completions; it suits no CLI"
    )


def test_a_cli_that_speaks_no_server_api_is_refused(serve, monkeypatch):
    server = serve("all")
    add("all", server.url)
    server.requests.clear()
    monkeypatch.setattr(type(providers.get("kilo")), "server_api", "")
    with pytest.raises(model_settings.Refused) as refused:
        add_model("K", "kilo", "m1", "all", no_env)
    assert str(refused.value) == "all does not suit Kilo CLI: Kilo CLI speaks no model server's API"
    assert server.requests == []


def test_claude_on_an_anthropic_compatible_server_is_saved(serve):
    server = serve("anthropic")
    add("gw", server.url)
    saved, verdict = add_model("Gw Claude", "claude", "claude-x", "gw", no_env)
    assert (saved.cli, verdict.kind) == ("claude", model_check.OK)


def test_remove_a_model_keeps_its_server(serve):
    server = serve("lmstudio")
    add("LM Studio дома", server.url)
    add_model("Локальная Qwen", "opencode", "qwen3-8b", "LM Studio дома", no_env)
    assert remove_models("локальная QWEN") == ["Локальная Qwen"]
    assert state.models() == []
    assert model_settings.remove_server("LM Studio дома") == "LM Studio дома"


def remove_models(*names):
    removed = []
    model_settings.remove_models(list(names), removed.append)
    return removed


def saved_models(*names):
    for name in names:
        state.add_model(name, "claude", "haiku", None)


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
            return False  # another process was first
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


def test_model_refusals_name_their_field(serve, monkeypatch):
    server = serve("lmstudio")
    add("lms", server.url)
    add("chat", serve("openai").url)
    listing(monkeypatch, "claude", base.ModelList(("haiku",), ("claude-x",), "claude models"))
    add_model("Taken", "claude", "haiku")
    cases = [
        (("", "claude", "haiku", None), "name"),
        (("taken", "claude", "haiku", None), "name"),
        (("N", "gemini", "x", None), "cli"),
        (("N", "claude", " ", None), "model"),
        (("N", "claude", "claude-y", None), "model"),
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
        add_model("N", "opencode", "qwen3-8b", "lms", no_env)
    assert refused.value.field == "server"


# A model's check without the save.


def check_model(name, cli, model, server=None, probe=None):
    return model_settings.check_model(
        name, cli, model, server, lambda provider: {"PATH": "/agents"}, probe=probe
    )


def test_check_model_refuses_as_add_model_does_and_saves_nothing(serve, monkeypatch):
    server = serve("lmstudio")
    add("lms", server.url)
    listing(monkeypatch, "claude", base.ModelList(("haiku",), ("claude-x",), "claude models"))
    add_model("Taken", "claude", "haiku")
    cases = [
        ("taken", "claude", "haiku", None),
        ("N", "gemini", "x", None),
        ("N", "claude", "claude-y", None),
        ("N", "opencode", fake.EMBEDDINGS, "lms"),
        ("N", "opencode", "q", "nowhere"),
    ]
    for case in cases:
        with pytest.raises(model_settings.Refused) as checked:
            check_model(*case)
        with pytest.raises(model_settings.Refused) as added:
            add_model(*case, env=lambda provider: {})
        assert (str(checked.value), checked.value.field) == (str(added.value), added.value.field)
    checked = check_model("N", "opencode", "qwen3-8b", "lms")
    assert (checked.verdict.kind, checked.model, checked.server.name) == (
        model_check.OK,
        "qwen3-8b",
        "lms",
    )
    assert checked.provider is providers.get("opencode")
    assert [m.name for m in state.models()] == ["Taken"]


def test_check_model_without_a_name_checks_no_name(monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("haiku",), None, why="no list"))
    add_model("haiku", "claude", "haiku")
    checked = check_model(None, "claude", "haiku")
    assert (checked.verdict.kind, checked.name) == (model_check.OK, "Claude Haiku")


def test_check_model_uses_the_list_given(monkeypatch):
    seen = listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    given = []
    checked = model_settings.check_model(
        None,
        "kilo",
        "kilo/b",
        None,
        lambda provider: {},
        listing=lambda provider: (
            given.append(provider.name) or base.ModelList((), ("kilo/b",), "kilo models")
        ),
    )
    assert (checked.verdict.kind, given, seen) == (model_check.OK, ["kilo"], [])


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


def litellm_server():
    return state.add_model_server("s1", "LiteLLM", "http://gw", "OpenAI-compatible", (CHAT,))


def default_name(cli, model, server=None, aliases=()):
    return model_settings.default_name(providers.get(cli), model, server, aliases)


def test_the_default_name_of_an_alias():
    aliases = ("sonnet", "sonnet[1m]")
    assert default_name("claude", "sonnet", aliases=aliases) == "Claude Sonnet"
    assert default_name("claude", "sonnet[1m]", aliases=aliases) == "Claude Sonnet[1m]"


def test_the_default_name_of_a_model_of_the_clis_list():
    assert default_name("codex", "gpt-5-codex") == "gpt-5-codex"


def test_the_default_name_of_a_model_on_a_server():
    assert default_name("opencode", "qwen3-8b", litellm_server()) == "qwen3-8b · LiteLLM"


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


def test_add_model_without_a_name_names_it(monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("sonnet",), None, why="no list"))
    saved, _ = add_model(None, "claude", "sonnet")
    assert saved.name == "Claude Sonnet"
    saved, _ = add_model(None, "claude", "sonnet")
    assert saved.name == "Claude Sonnet · Claude Code"


def test_a_model_whose_default_name_is_no_name_is_refused_under_the_model(monkeypatch):
    """A model of no list (a warning) with a hidden character would be named by it: the
    name's rule refuses it, under the model's field, in the check and the save alike."""
    listing(monkeypatch, "claude", base.ModelList(("sonnet",), None, why="no list"))
    hidden = "claude-opus​-5-5"  # U+200B
    says = "a model's name is one line of visible text: U+200B ZERO WIDTH SPACE is not allowed"
    with pytest.raises(model_settings.Refused) as checked:
        check_model(None, "claude", hidden)
    with pytest.raises(model_settings.Refused) as added:
        add_model(None, "claude", hidden)
    for refused in (checked.value, added.value):
        assert (str(refused), refused.field) == (says, "model")
    assert state.models() == []
    assert check_model(None, "claude", "sonnet").name == "Claude Sonnet"


# Renaming a model.


def rename(name, new):
    return model_settings.rename_model(name, new)


def test_rename_a_model():
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    renamed = rename("claude sonnet", "Сильная")
    assert (renamed.name, renamed.cli, renamed.model) == ("Сильная", "claude", "sonnet")
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
