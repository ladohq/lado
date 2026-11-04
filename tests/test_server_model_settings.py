"""The UI server's API of Settings → Models (openspec change model-settings-page): the
configured models and model servers through lado.server.model_entries over
lado.model_settings. In process, with FastAPI's test client and the fake model servers of
tests/fake_model_server.py."""

import json
import socket

import fake_model_server as fake
import pytest
from fastapi.testclient import TestClient

from lado import agent_env, model_servers, model_settings, providers, state, update
from lado.providers import base
from lado.server import app as server_app
from lado.server import auth, model_entries
from lado.server import launch as server_launch

PORT = 8127
OWN = "http://testserver"


@pytest.fixture
def client(lado_home, monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)
    monkeypatch.delenv("LADO_CONTAINER", raising=False)
    model_entries.forget_probes()
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    yield client
    model_entries.forget_probes()
    server_launch.forget_model_lists()  # kept by the process: no later test gets them


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


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ok(answer):
    assert answer.status_code == 200, answer.text
    return answer.json()


def refused(answer):
    assert answer.status_code == 400, answer.text
    return answer.json()["detail"]


def add_server(client, name, url, key=None, replace=False):
    return client.post(
        "/api/model-servers", json={"name": name, "address": url, "key": key, "replace": replace}
    )


def listing(monkeypatch, name, listed):
    seen = []
    monkeypatch.setattr(
        type(providers.get(name)), "model_list", lambda self, env: seen.append(env) or listed
    )
    return seen


# The listing.


def test_listing_empty_makes_no_db(client, lado_home):
    assert ok(client.get("/api/model-settings")) == {"models": [], "servers": []}
    assert not (lado_home / "lado.db").exists()


def test_listing_asks_no_server(client, serve):
    server = serve("lmstudio", key="k-1")
    ok(add_server(client, "LM Studio дома", server.url, key="k-1"))
    state.add_model("Q", "opencode", "qwen3-8b", state.model_server("LM Studio дома").id)
    state.add_model("Быстрая", "claude", "haiku", None)
    server.requests.clear()
    assert ok(client.get("/api/model-settings")) == {
        "models": [
            {
                "name": "Q",
                "cli": "opencode",
                "cli_title": "OpenCode",
                "model": "qwen3-8b",
                "server": "LM Studio дома",
            },
            {
                "name": "Быстрая",
                "cli": "claude",
                "cli_title": "Claude Code",
                "model": "haiku",
                "server": None,
            },
        ],
        "servers": [
            {
                "name": "LM Studio дома",
                "address": server.url,
                "kind": "LM Studio",
                "has_key": True,
            }
        ],
    }
    assert server.requests == []


# Adding and changing a server.


def test_add_server_lmstudio(client, serve):
    server = serve("lmstudio")
    added = ok(add_server(client, "LM Studio дома", server.url.removeprefix("http://")))
    assert added["server"]["name"] == "LM Studio дома"
    assert (added["server"]["kind"], added["notes"], added["warnings"]) == ("LM Studio", [], [])
    assert added["probe"] == {
        "kind": "LM Studio",
        "address": server.url,
        "models": ["qwen3-8b", fake.EMBEDDINGS],
        "models_why": "",
        "embeddings": [fake.EMBEDDINGS],
        "apis_why": "",
        "clis": [
            {"name": "kilo", "title": "Kilo CLI", "api": base.CHAT_COMPLETIONS},
            {"name": "opencode", "title": "OpenCode", "api": base.CHAT_COMPLETIONS},
            {"name": "codex", "title": "Codex CLI", "api": base.RESPONSES},
        ],
    }
    assert [s.name for s in state.model_servers()] == ["LM Studio дома"]


def test_a_server_whose_apis_cannot_be_told_says_why(client, serve):
    server = serve("gateway-400-list")
    added = ok(add_server(client, "gw", server.url))
    assert added["probe"]["clis"] == []
    assert added["probe"]["apis_why"] == f"{server.url} answers 400 to any POST"


def test_add_server_same_address_note(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "gateway", server.url))
    added = ok(add_server(client, "LiteLLM", server.url.removeprefix("http://") + "/v1/"))
    assert added["notes"] == ['same address as model server "gateway"']


def test_add_server_plain_http_warning(client):
    detail = refused(add_server(client, "ext", "http://llm.invalid", key="k-1"))
    assert detail["warnings"] == [
        "the key goes to llm.invalid over plain http://, unencrypted; use https:// if the "
        "server has it"
    ]
    assert detail["field"] == "address"
    assert state.model_servers() == []


def test_add_server_refusals_carry_fields(client, serve):
    port = closed_port()
    detail = refused(add_server(client, "lab", f"http://127.0.0.1:{port}"))
    assert detail == {
        "message": f"http://127.0.0.1:{port} does not answer (connection refused)",
        "hint": "",
        "field": "address",
        "warnings": [],
    }
    work = serve("openai", key="k-1")
    detail = refused(add_server(client, "work", work.url))
    assert detail["message"] == (f"{work.url} asks for a key (401): enter it in Key")
    assert detail["field"] == "key"
    assert refused(add_server(client, "x", "ftp://x"))["field"] == "address"
    assert refused(add_server(client, " x", work.url))["field"] == "name"
    lms = serve("lmstudio")
    ok(add_server(client, "lms", lms.url))
    lms.requests.clear()
    detail = refused(add_server(client, "LMS", lms.url))
    assert detail["field"] == "name"
    assert detail["message"].startswith('a model server "lms" is saved already')
    assert lms.requests == []


def test_empty_key_refused(client, serve):
    server = serve("openai")
    detail = refused(add_server(client, "work", server.url, key=""))
    assert (detail["message"], detail["field"]) == ("the key is empty", "key")
    assert server.requests == []


def test_change_keeps_key_on_null(client, serve):
    old = serve("openai", key="k-1")
    ok(add_server(client, "work", old.url, key="k-1"))
    new = serve("ollama", key="k-1")
    changed = ok(add_server(client, "WORK", new.url, replace=True))
    assert (changed["server"]["address"], changed["server"]["kind"]) == (new.url, "Ollama")
    assert {r.headers["Authorization"] for r in new.requests} == {"Bearer k-1"}
    assert model_settings.server_key(state.model_server("work")) == "k-1"


def test_change_writes_new_key(client, serve):
    old = serve("openai", key="k-1")
    ok(add_server(client, "work", old.url, key="k-1"))
    state.add_model("W", "opencode", "gpt-oss-20b", state.model_server("work").id)
    new = serve("openai", key="k-2")
    ok(add_server(client, "work", new.url, key="k-2", replace=True))
    assert model_settings.server_key(state.model_server("work")) == "k-2"
    assert state.model("W").server == state.model_server("work").id


def test_a_failed_change_changes_nothing(client, serve):
    old = serve("openai", key="k-1")
    ok(add_server(client, "work", old.url, key="k-1"))
    before = state.model_server("work")
    refused(add_server(client, "work", f"http://127.0.0.1:{closed_port()}", replace=True))
    assert state.model_server("work") == before


def test_unreadable_body_on_secret_route_repeats_nothing(client):
    canary = "canary-key-in-a-422"
    answer = client.post("/api/model-servers", json={"name": 1, "key": canary})
    assert answer.status_code == 422
    assert canary not in answer.text
    answer = client.post("/api/model-servers", json={"name": "x", "address": "y", "key": [canary]})
    assert answer.status_code == 422
    assert canary not in answer.text


# A server's list.


def test_probe_route_reads_now_and_keeps_the_probe(client, serve):
    server = serve("lmstudio", key="k-1")
    ok(add_server(client, "lms", server.url, key="k-1"))
    server.requests.clear()
    probe = ok(client.post("/api/model-servers/lms/probe"))
    assert probe["models"] == ["qwen3-8b", fake.EMBEDDINGS]
    assert server.requests and {r.headers["Authorization"] for r in server.requests} == {
        "Bearer k-1"
    }
    server.requests.clear()
    ok(client.post("/api/models/check", json={"cli": "opencode", "model": "qwen3-8b",
                                              "server": "lms"}))  # fmt: skip
    assert server.requests == []  # the probe kept
    ok(client.post("/api/model-servers/lms/probe"))
    assert server.requests  # read again


def test_probe_of_a_server_that_does_not_answer(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "lms", server.url))
    server.close()
    detail = refused(client.post("/api/model-servers/lms/probe"))
    assert detail["message"] == f"{server.url} does not answer (connection refused)"
    assert refused(client.post("/api/model-servers/nope/probe"))["message"] == (
        'no model server "nope" is saved'
    )


def test_a_list_given_only_with_the_version_header_has_no_why(client, serve):
    ok(add_server(client, "anth", serve("anthropic-versioned").url))
    probe = ok(client.post("/api/model-servers/anth/probe"))
    assert (probe["models"], probe["models_why"]) == (["claude-x"], "")


# Checking and adding a model.


def check(client, **given):
    return ok(client.post("/api/models/check", json=given))


def check_server(client, name="", address="", key=None, key_typed=False, replace=False):
    given = {"name": name, "address": address, "key": key, "key_typed": key_typed}
    if replace:
        given["replace"] = True
    return ok(client.post("/api/model-servers/check", json=given))


def test_check_server_of_a_change_takes_the_servers_own_name(client, serve):
    lms = serve("lmstudio")
    ok(add_server(client, "LM Studio дома", lms.url))
    moved = serve("lmstudio")
    change = check_server(client, "lm studio дома", moved.url, replace=True)
    assert (change["refusals"], change["probe"]["kind"]) == ([], "LM Studio")
    same = check_server(client, "LM Studio дома", lms.url, replace=True)
    assert same["notes"] == []  # its own address is no other server's
    add = check_server(client, "LM Studio дома", moved.url)
    assert [r["field"] for r in add["refusals"]] == ["name"]
    none = check_server(client, "nope", moved.url, replace=True)
    assert [r["field"] for r in none["refusals"]] == ["name"]


def test_check_server_of_a_change_sends_the_kept_key(client, serve):
    old = serve("openai", key="k-1")
    ok(add_server(client, "work", old.url, key="k-1"))
    moved = serve("ollama", key="k-1")
    change = check_server(client, "work", moved.url, replace=True)
    assert (change["refusals"], change["probe"]["kind"]) == ([], "Ollama")
    assert {r.headers["Authorization"] for r in moved.requests} == {"Bearer k-1"}
    assert "k-1" not in json.dumps(change)
    other = serve("ollama", key="k-1")
    add = check_server(client, "new", other.url)  # a new server has no kept key
    assert [r["field"] for r in add["refusals"]] == ["key"]
    typed = check_server(client, "work", other.url, key_typed=True, replace=True)
    assert [r["field"] for r in typed["refusals"]] == ["key"]  # a new key typed, not checked


def test_check_model_says_the_name_a_save_would_take(client, serve, monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("sonnet",), None, why="no list"))
    assert check(client, cli="claude", model="sonnet")["name"] == "Claude Sonnet"
    assert check(client, cli="claude", model="sonnet", name="Своя")["name"] == "Своя"
    lms = serve("lmstudio")
    ok(add_server(client, "LM Studio дома", lms.url))
    for cli, title in (("opencode", "OpenCode"), ("kilo", "Kilo CLI")):
        would = check(client, cli=cli, model="qwen3-8b", server="LM Studio дома")
        assert would["name"] == f"qwen3-8b · LM Studio дома · {title}"
    listing(monkeypatch, "codex", base.ModelList((), ("gpt-5-codex",), "codex models"))
    ok(client.post("/api/models", json={"name": "qwen3-8b · LM Studio дома · Kilo CLI",
                                        "cli": "codex", "model": "gpt-5-codex"}))  # fmt: skip
    taken = check(client, cli="kilo", model="qwen3-8b", server="LM Studio дома")
    assert taken["name"] == "qwen3-8b · LM Studio дома · Kilo CLI (2)"
    assert check(client, cli="gemini", model="x")["name"] == ""  # refused: no name


def test_check_server_probes_without_a_key_and_saves_nothing(client, serve):
    server = serve("lmstudio")
    found = check_server(client, "LM Studio дома", server.url.removeprefix("http://"))
    assert (found["refusals"], found["warnings"], found["notes"]) == ([], [], [])
    assert found["probe"]["kind"] == "LM Studio"
    assert found["probe"]["address"] == server.url  # what answered, its scheme filled in
    assert found["probe"]["models"] == ["qwen3-8b", fake.EMBEDDINGS]
    assert [c["name"] for c in found["probe"]["clis"]] == ["kilo", "opencode", "codex"]
    assert server.requests and all("Authorization" not in r.headers for r in server.requests)
    assert state.model_servers() == []


def test_check_server_with_nothing_typed_asks_nothing(client, lado_home):
    assert check_server(client) == {"probe": None, "refusals": [], "warnings": [], "notes": []}
    assert check_server(client, "lab")["refusals"] == []
    assert not (lado_home / "lado.db").exists()  # a check makes none


def test_check_server_refusals_carry_their_fields(client, serve):
    lms = serve("lmstudio")
    ok(add_server(client, "lms", lms.url))
    taken = check_server(client, "LMS", lms.url)
    assert [r["field"] for r in taken["refusals"]] == ["name"]
    assert taken["refusals"][0]["message"].startswith('a model server "lms" is saved already')
    assert taken["probe"]["kind"] == "LM Studio"  # the address is checked all the same
    assert taken["notes"] == ['same address as model server "lms"']
    port = closed_port()
    silent = check_server(client, "lab", f"http://127.0.0.1:{port}")
    assert silent["probe"] is None
    assert silent["refusals"] == [
        {
            "message": f"http://127.0.0.1:{port} does not answer (connection refused)",
            "hint": "",
            "field": "address",
            "warnings": [],
        }
    ]
    assert [r["field"] for r in check_server(client, "x", "ftp://x")["refusals"]] == ["address"]
    assert [r["field"] for r in check_server(client, " x")["refusals"]] == ["name"]


def test_check_server_says_a_key_is_asked_for_and_sends_one_only_given(client, serve):
    work = serve("openai", key="k-1")
    asks = check_server(client, "work", work.url, key_typed=True)
    assert [(r["field"], r["message"]) for r in asks["refusals"]] == [
        ("key", f"{work.url} asks for a key (401): enter it in Key")
    ]
    assert all("Authorization" not in r.headers for r in work.requests)
    work.requests.clear()
    keyed = check_server(client, "work", work.url, key="k-1", key_typed=True)
    assert (keyed["refusals"], keyed["probe"]["kind"]) == ([], "OpenAI-compatible")
    assert work.requests and {r.headers["Authorization"] for r in work.requests} == {"Bearer k-1"}
    wrong = check_server(client, "work", work.url, key="k-2", key_typed=True)
    assert [r["field"] for r in wrong["refusals"]] == ["key"]
    empty = check_server(client, "work", work.url, key="", key_typed=True)
    assert [(r["field"], r["message"]) for r in empty["refusals"]] == [("key", "the key is empty")]
    assert state.model_servers() == []


def test_check_server_says_the_plain_http_warning_with_no_key_sent(client):
    found = check_server(client, "ext", "http://llm.invalid", key_typed=True)
    assert found["warnings"] == [model_servers.PLAIN_HTTP.format(host="llm.invalid")]
    assert [r["field"] for r in found["refusals"]] == ["address"]
    assert check_server(client, "ext", "http://llm.invalid")["warnings"] == []
    assert check_server(client, "ext", "https://llm.invalid", key_typed=True)["warnings"] == []
    assert check_server(client, "ext", "10.0.0.5:4000x", key_typed=True)["warnings"] == []


def test_check_model_ok_warn_refused(client, serve, monkeypatch):
    listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    assert check(client, cli="kilo", model="kilo/a") == {
        "kind": "ok",
        "text": "in Kilo CLI's list of models",
        "field": "",
        "name": "kilo/a",
    }
    assert check(client, cli="kilo", model="kilo/z") == {
        "kind": "refused",
        "text": "kilo/z is not in Kilo CLI's list of models; ↻ Refresh reads the list again",
        "field": "model",
        "name": "",
    }
    listing(monkeypatch, "claude", base.ModelList(("opus",), None, why="no list"))
    warned = check(client, cli="claude", model="claude-opus-5-5")
    assert (warned["kind"], warned["field"]) == ("warn", "")
    assert check(client, cli="gemini", model="x")["field"] == "cli"
    assert check(client, cli="kilo", model="kilo/a", server="nope")["field"] == "server"
    assert state.schema_version() is None or state.models() == []


def test_the_pages_refusals_name_no_command(client, serve, monkeypatch):
    """The page's lines say what to do on the page, never a command to run; the CLI prints
    its own (tests/test_cli_model_settings.py)."""
    said = []

    def page(answer):
        detail = refused(answer)
        said.append(detail)
        return detail["message"], detail["hint"]

    gateway = serve("openai", key="k-1")
    assert page(add_server(client, "gw", gateway.url)) == (
        f"{gateway.url} asks for a key (401): enter it in Key",
        "",
    )
    ok(add_server(client, "gw", gateway.url, key="k-1"))
    assert page(add_server(client, "GW", gateway.url))[0] == (
        'a model server "gw" is saved already; its Change sets another address or key'
    )
    model_settings._write_key(state.model_server("gw").id, "k-2")  # the server takes no more
    assert page(client.post("/api/model-servers/gw/probe")) == (
        f"{gateway.url} refused the key (401)",
        "",
    )
    open_one = serve("openai")
    ok(add_server(client, "open", open_one.url))
    open_one.close()
    asking = serve("openai", key="k-3", port=open_one.port)
    assert page(client.post("/api/model-servers/open/probe")) == (
        f"{open_one.url} asks for a key (401): Change sets its key",
        "",
    )
    asking.close()
    lms = serve("lmstudio")
    ok(add_server(client, "lms", lms.url))
    assert page(
        client.post(
            "/api/models", json={"cli": "opencode", "model": fake.EMBEDDINGS, "server": "lms"}
        )
    )[0] == (  # fmt: skip
        f"{fake.EMBEDDINGS} is an embeddings model on lms; an agent needs a chat model"
    )
    assert page(
        client.post("/api/models", json={"cli": "opencode", "model": "gone", "server": "lms"})
    )[0] == (  # fmt: skip
        "gone is not in lms's list of models; ↻ Refresh reads the list again"
    )
    assert page(
        client.post("/api/models", json={"cli": "opencode", "model": "qwen3-8b", "server": "nope"})
    )[0] == (  # fmt: skip
        'no model server "nope" is saved'
    )
    monkeypatch.setattr(update, "in_container", lambda: True)
    port = closed_port()
    assert page(add_server(client, "lab", f"http://localhost:{port}"))[1] == (
        "LADO runs in a container, where localhost is the container itself; a server on your "
        f"machine: http://host.docker.internal:{port} (not tried)"
    )
    assert [d for d in said if "lado " in d["message"] + d["hint"]] == []


def test_check_model_of_a_cli_reads_its_list_once_a_minute(client, monkeypatch):
    """The live check of Other model… at each settled keystroke takes the CLI's list the
    launch window keeps, read when the source opened (`fresh`); a save reads it now."""
    asked = listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    server_launch.forget_model_lists()
    client.get("/api/providers/kilo/models", params={"fresh": True})  # the source opened
    assert check(client, cli="kilo", model="kilo/a")["kind"] == "ok"
    assert check(client, cli="kilo", model="kilo/b")["kind"] == "refused"
    assert len(asked) == 1
    ok(client.post("/api/models", json={"cli": "kilo", "model": "kilo/a"}))
    assert len(asked) == 2


def test_check_model_keeps_the_probe_a_minute(client, serve, monkeypatch):
    server = serve("lmstudio")
    ok(add_server(client, "lms", server.url))
    clock = [1000.0]
    monkeypatch.setattr(model_entries.time, "monotonic", lambda: clock[0])
    model_entries.forget_probes()
    server.requests.clear()
    check(client, cli="opencode", model="qwen3-8b", server="lms")
    asked = len(server.requests)
    assert asked
    check(client, cli="opencode", model="qwen3-14b", server="lms")
    assert len(server.requests) == asked
    clock[0] += model_entries.KEPT + 1
    check(client, cli="opencode", model="qwen3-8b", server="lms")
    assert len(server.requests) == 2 * asked
    ok(client.post("/api/models", json={"cli": "opencode", "model": "qwen3-8b", "server": "lms"}))
    assert len(server.requests) == 3 * asked  # a save probes now


def test_a_failed_probe_is_not_kept(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "lms", server.url))
    port = server.port
    server.close()
    model_entries.forget_probes()  # the add's probe
    assert check(client, cli="opencode", model="qwen3-8b", server="lms")["field"] == "server"
    again = serve("lmstudio", port=port)
    assert check(client, cli="opencode", model="qwen3-8b", server="lms")["kind"] == "ok"
    assert again.requests


def test_add_model_default_name(client, serve, monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("sonnet",), None, why="no list"))
    added = ok(client.post("/api/models", json={"name": None, "cli": "claude", "model": "sonnet"}))
    assert added == {
        "model": {
            "name": "Claude Sonnet",
            "cli": "claude",
            "cli_title": "Claude Code",
            "model": "sonnet",
            "server": None,
        },
        "check": {"kind": "ok", "text": "an alias of Claude Code", "field": "", "name": ""},
    }
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    added = ok(client.post("/api/models", json={"cli": "opencode", "model": "qwen3-8b",
                                                "server": "LiteLLM"}))  # fmt: skip
    assert added["model"]["name"] == "qwen3-8b · LiteLLM · OpenCode"  # several CLIs suit it
    detail = refused(client.post("/api/models", json={"cli": "opencode",
                                                      "model": fake.EMBEDDINGS,
                                                      "server": "LiteLLM"}))  # fmt: skip
    assert detail["field"] == "model"
    assert detail["message"].startswith(f"{fake.EMBEDDINGS} is an embeddings model")


def test_add_model_with_a_name(client, monkeypatch):
    listing(monkeypatch, "claude", base.ModelList(("sonnet",), None, why="no list"))
    added = ok(client.post("/api/models", json={"name": "Сильная", "cli": "claude",
                                                "model": "sonnet"}))  # fmt: skip
    assert added["model"]["name"] == "Сильная"
    detail = refused(client.post("/api/models", json={"name": "сильная", "cli": "claude",
                                                      "model": "sonnet"}))  # fmt: skip
    assert detail["field"] == "name"


# Renaming and removing.


def test_rename_model_route(client):
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    state.add_model("Other", "claude", "haiku", None)
    settings = ok(client.patch("/api/models/claude%20sonnet", json={"name": "Сильная"}))
    assert [m["name"] for m in settings["models"]] == ["Other", "Сильная"]
    detail = refused(client.patch("/api/models/Сильная", json={"name": "OTHER"}))
    assert (detail["field"], detail["message"]) == (
        "name",
        'the name is taken by the model "Other"',
    )
    assert refused(client.patch("/api/models/nope", json={"name": "x"}))["field"] == ""


def test_a_name_with_a_slash_in_the_path(client):
    state.add_model("a/b", "claude", "sonnet", None)
    settings = ok(client.patch("/api/models/a%2Fb", json={"name": "c/d"}))
    assert [m["name"] for m in settings["models"]] == ["c/d"]
    assert ok(client.delete("/api/models/c%2Fd"))["models"] == []


def test_remove_model_route(client):
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    assert ok(client.delete("/api/models/claude%20SONNET"))["models"] == []
    detail = refused(client.delete("/api/models/claude%20sonnet"))
    assert detail["message"] == 'no model "claude sonnet" is saved'


def test_remove_server_route(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    id = state.model_server("LiteLLM").id
    for name in ("a", "b"):
        state.add_model(name, "opencode", "qwen3-8b", id)
    state.add_model("own", "claude", "haiku", None)
    detail = refused(client.delete("/api/model-servers/LiteLLM"))
    assert (detail["message"], detail["hint"]) == (
        'model server "LiteLLM" is used by the models a, b',
        "",
    )
    detail = refused(
        client.delete(
            "/api/model-servers/litellm", params={"with_models": True, "confirmed": ["a"]}
        )
    )
    assert detail["message"] == (
        'model server "LiteLLM" has other models now: a, b; nothing was removed'
    )
    assert len(state.models()) == 3
    settings = ok(
        client.delete(
            "/api/model-servers/litellm", params={"with_models": True, "confirmed": ["a", "B"]}
        )
    )
    assert settings == {
        "models": [
            {
                "name": "own",
                "cli": "claude",
                "cli_title": "Claude Code",
                "model": "haiku",
                "server": None,
            }
        ],
        "servers": [],
    }
    assert not model_settings.key_folder(id).exists()


def test_changes_need_the_token(client):
    client.cookies.clear()
    assert client.get("/api/model-settings").status_code == 401
    assert client.post("/api/models", json={"cli": "claude", "model": "x"}).status_code == 401


# The launch window's list, read now.


def test_provider_models_fresh_skips_the_kept_list(client, monkeypatch):
    asked = listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    server_launch.forget_model_lists()
    client.get("/api/providers/kilo/models")
    client.get("/api/providers/kilo/models")
    assert len(asked) == 1
    client.get("/api/providers/kilo/models", params={"fresh": True})
    assert len(asked) == 2
    client.get("/api/providers/kilo/models")
    assert len(asked) == 2  # the fresh list is kept
