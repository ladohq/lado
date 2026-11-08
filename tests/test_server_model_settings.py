"""The UI server's API of Settings → Model servers (openspec change model-settings-page): the
configured models and model servers through lado.server.model_entries over
lado.model_settings. In process, with FastAPI's test client and the fake model servers of
tests/fake_model_server.py."""

import json
import socket

import fake_model_server as fake
import pytest
from fastapi.testclient import TestClient

from lado import agent_env, model_servers, model_settings, providers, runtime, state, update
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
    assert ok(client.get("/api/model-settings")) == {"models": [], "servers": [], "defaults": []}
    assert not (lado_home / "lado.db").exists()


def test_listing_asks_no_server(client, serve):
    server = serve("lmstudio", key="k-1")
    ok(add_server(client, "LM Studio дома", server.url, key="k-1"))
    saved = state.add_model("Q", "opencode", "qwen3-8b", state.model_server("LM Studio дома").id)
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    state.set_cli_default(state.ModelRef("claude", None, "opus"))
    server.requests.clear()
    assert ok(client.get("/api/model-settings")) == {
        "models": [
            {
                "id": saved.id,
                "name": "Q",
                "cli": "opencode",
                "cli_title": "OpenCode",
                "model": "qwen3-8b",
                "server": "LM Studio дома",
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
        "defaults": [
            {
                "cli": "claude",
                "external": None,
                "builtin": "opus",
                "name": "opus",
                "model": "opus",
                "server": None,
                "whole_process": True,
            },
            {
                "cli": "opencode",
                "external": saved.id,
                "builtin": None,
                "name": "Q",
                "model": "qwen3-8b",
                "server": "LM Studio дома",
                "whole_process": False,
            },
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
        ],
        "cli_notes": [
            "Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not "
            "talk to LADO"
        ],
    }
    assert [s.name for s in state.model_servers()] == ["LM Studio дома"]


def test_a_server_of_a_type_every_cli_takes_has_no_note(client, serve):
    added = ok(add_server(client, "gw", serve("all").url))
    assert added["probe"]["cli_notes"] == []
    assert "codex" in [cli["name"] for cli in added["probe"]["clis"]]


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
    assert detail["message"].startswith('A model server "lms" is saved already')
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


@pytest.fixture
def short_ceilings(monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 0.3)
    monkeypatch.setattr(model_servers, "LATE_TIMEOUT", 0.6)


def late_words(url):
    return f"the Anthropic Messages API of {url} did not answer in time: try again"


def test_a_late_api_is_said_once_in_the_probe_of_a_check_and_of_an_add(
    client, serve, short_ceilings
):
    late = serve("late-always")
    found = check_server(client, "Шлюз", late.url)
    assert found["probe"]["apis_why"] == late_words(late.url)
    assert found["warnings"] == []
    added = ok(add_server(client, "Шлюз", late.url))
    assert added["probe"]["apis_why"] == late_words(late.url)
    assert added["warnings"] == []


def test_a_saved_server_s_probe_says_its_api_is_late_not_missing(client, serve, short_ceilings):
    late = serve("late-always")
    ok(add_server(client, "Шлюз", late.url))
    assert ok(client.post("/api/model-servers/Шлюз/probe"))["apis_why"] == late_words(late.url)


def test_a_probe_s_own_reason_stays_before_a_late_api(client, serve, short_ceilings):
    server = serve("late-control-always")
    found = check_server(client, "Шлюз", server.url)
    assert found["probe"]["apis_why"] == f"{server.url} answers 400 to any POST"


def test_a_late_check_asks_the_server_again_at_the_next_try(client, serve, short_ceilings):
    server = serve("late-two-probes")
    ok(add_server(client, "Шлюз", server.url))
    first = check(client, cli="claude", model="m1", server="Шлюз")
    assert first["text"] == "the Anthropic Messages API of Шлюз did not answer in time: try again"
    assert check(client, cli="claude", model="m1", server="Шлюз")["kind"] != "refused"


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


def test_check_model_says_the_name_a_save_would_take(client, serve):
    lms = serve("lmstudio")
    ok(add_server(client, "LM Studio дома", lms.url))
    on = {"model": "qwen3-8b", "server": "LM Studio дома"}
    assert check(client, cli="opencode", name="Своя", **on)["name"] == "Своя"
    for cli in ("opencode", "kilo"):
        assert check(client, cli=cli, **on)["name"] == "qwen3-8b"
    ok(client.post("/api/models", json={"name": "qwen3-8b", "cli": "opencode", **on}))
    assert check(client, cli="kilo", **on)["name"] == "qwen3-8b · Kilo CLI"
    assert check(client, cli="gemini", **on)["name"] == ""  # refused: no name


def test_check_server_probes_without_a_key_and_saves_nothing(client, serve):
    server = serve("lmstudio")
    found = check_server(client, "LM Studio дома", server.url.removeprefix("http://"))
    assert (found["refusals"], found["warnings"], found["notes"]) == ([], [], [])
    assert found["probe"]["kind"] == "LM Studio"
    assert found["probe"]["address"] == server.url  # what answered, its scheme filled in
    assert found["probe"]["models"] == ["qwen3-8b", fake.EMBEDDINGS]
    assert [c["name"] for c in found["probe"]["clis"]] == ["kilo", "opencode"]
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
    assert taken["refusals"][0]["message"].startswith('A model server "lms" is saved already')
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


def test_check_model_ok_warn_refused(client, serve):
    ok(add_server(client, "lms", serve("lmstudio").url))
    assert check(client, cli="kilo", model="qwen3-8b", server="lms") == {
        "kind": "ok",
        "text": "in lms's list of models",
        "field": "",
        "name": "qwen3-8b",
    }
    assert check(client, cli="kilo", model="kilo/z", server="lms") == {
        "kind": "refused",
        "text": "kilo/z is not in lms's list of models; ↻ Refresh reads the list again",
        "field": "model",
        "name": "",
    }
    ok(add_server(client, "resp", serve("responses-only").url))
    warned = check(client, cli="codex", model="gpt-x", server="resp")
    assert (warned["kind"], warned["field"]) == ("warn", "")
    assert check(client, cli="gemini", model="x", server="lms")["field"] == "cli"
    assert check(client, cli="kilo", model="kilo/a", server="nope")["field"] == "server"
    assert state.models() == []


def test_a_model_without_a_server_is_no_request(client):
    answer = client.post("/api/models", json={"cli": "claude", "model": "haiku"})
    assert answer.status_code == 422
    assert client.post("/api/models/check", json={"cli": "x", "model": "y"}).status_code == 422


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
        'A model server "gw" is saved already; its Change sets another address or key'
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


def test_add_model_default_name(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    added = ok(client.post("/api/models", json={"cli": "opencode", "model": "qwen3-8b",
                                                "server": "LiteLLM"}))  # fmt: skip
    assert added == {
        "model": {
            "id": state.model("qwen3-8b").id,
            "name": "qwen3-8b",  # its server and CLI show beside it
            "cli": "opencode",
            "cli_title": "OpenCode",
            "model": "qwen3-8b",
            "server": "LiteLLM",
        },
        "check": {"kind": "ok", "text": "in LiteLLM's list of models", "field": "", "name": ""},
    }
    detail = refused(client.post("/api/models", json={"cli": "opencode",
                                                      "model": fake.EMBEDDINGS,
                                                      "server": "LiteLLM"}))  # fmt: skip
    assert detail["field"] == "model"
    assert detail["message"].startswith(f"{fake.EMBEDDINGS} is an embeddings model")


def test_add_model_with_a_name(client, serve):
    ok(add_server(client, "lms", serve("lmstudio").url))
    given = {"cli": "opencode", "model": "qwen3-8b", "server": "lms"}
    added = ok(client.post("/api/models", json={"name": "Сильная", **given}))
    assert added["model"]["name"] == "Сильная"
    detail = refused(client.post("/api/models", json={"name": "сильная", **given}))
    assert detail["field"] == "name"


# Renaming and removing.


def saved_server():
    return state.add_model_server("s1", "lms", "http://lms", "LM Studio", (base.CHAT_COMPLETIONS,))


def test_rename_model_route(client):
    saved_server()
    state.add_model("Claude Sonnet", "opencode", "qwen3-8b", "s1")
    state.add_model("Other", "opencode", "qwen3-8b", "s1")
    settings = ok(client.patch("/api/models/claude%20sonnet", json={"name": "Сильная"}))
    assert [m["name"] for m in settings["models"]] == ["Other", "Сильная"]
    detail = refused(client.patch("/api/models/Сильная", json={"name": "OTHER"}))
    assert (detail["field"], detail["message"]) == (
        "name",
        'The name is taken by the model "Other"',
    )
    assert refused(client.patch("/api/models/nope", json={"name": "x"}))["field"] == ""


def test_a_name_with_a_slash_in_the_path(client):
    saved_server()
    state.add_model("a/b", "opencode", "qwen3-8b", "s1")
    settings = ok(client.patch("/api/models/a%2Fb", json={"name": "c/d"}))
    assert [m["name"] for m in settings["models"]] == ["c/d"]
    assert ok(client.delete("/api/models/c%2Fd"))["models"] == []


def test_remove_model_route(client):
    saved_server()
    state.add_model("Claude Sonnet", "opencode", "qwen3-8b", "s1")
    assert ok(client.delete("/api/models/claude%20SONNET"))["models"] == []
    detail = refused(client.delete("/api/models/claude%20sonnet"))
    assert detail["message"] == 'no model "claude sonnet" is saved'


def test_remove_server_route(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    id = state.model_server("LiteLLM").id
    for name in ("a", "b"):
        state.add_model(name, "opencode", "qwen3-8b", id)
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
    assert len(state.models()) == 2
    settings = ok(
        client.delete(
            "/api/model-servers/litellm", params={"with_models": True, "confirmed": ["a", "B"]}
        )
    )
    assert settings == {"models": [], "servers": [], "defaults": []}
    assert not model_settings.key_folder(id).exists()


def test_removing_a_model_names_the_default_it_cleared(client):
    """A page gone stale knows of no default: the answer says one went."""
    saved_server()
    a = state.add_model("a", "opencode", "qwen3-8b", "s1")
    state.add_model("b", "opencode", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", a.id, None))
    assert ok(client.delete("/api/models/b"))["cleared"] == []
    answer = ok(client.delete("/api/models/a"))
    assert answer["cleared"] == ["opencode"]
    assert (answer["models"], answer["defaults"]) == ([], [])


def test_removing_a_default_s_model_or_server_clears_it(client):
    saved_server()
    a = state.add_model("a", "opencode", "qwen3-8b", "s1")
    state.add_model("b", "kilo", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", a.id, None))
    assert ok(client.delete("/api/models/a"))["defaults"] == []
    b = state.model("b")
    state.set_cli_default(state.ModelRef("kilo", b.id, None))
    settings = ok(
        client.delete("/api/model-servers/lms", params={"with_models": True, "confirmed": ["b"]})
    )
    assert settings["defaults"] == []


def test_changes_need_the_token(client):
    client.cookies.clear()
    assert client.get("/api/model-settings").status_code == 401
    body = {"cli": "claude", "model": "x", "server": "s"}
    assert client.post("/api/models", json=body).status_code == 401
    assert client.put("/api/model-defaults/claude", json={"builtin": "x"}).status_code == 401
    assert client.delete("/api/model-defaults/claude").status_code == 401
    assert client.get("/api/providers/claude/model-choices").status_code == 401


# A CLI's full list and its default model.


def test_choices_of_a_cli_with_a_list(client, monkeypatch):
    listing(monkeypatch, "opencode", base.ModelList((), ("a/b",), "opencode models"))
    saved_server()
    saved = state.add_model("Q", "opencode", "qwen3-8b", "s1")
    state.add_model("K", "kilo", "qwen3-8b", "s1")
    assert ok(client.get("/api/providers/opencode/model-choices")) == {
        "aliases": [],
        "models": ["a/b"],
        "why": "",
        "external": [
            {
                "id": saved.id,
                "name": "Q",
                "cli": "opencode",
                "cli_title": "OpenCode",
                "model": "qwen3-8b",
                "server": "lms",
            }
        ],
        "other_name": False,
        "whole_process": False,
        "read_again": True,
        "check": {
            "kind": "default",
            "text": "empty: OpenCode's default model; type or pick one of its models",
            "field": "",
            "name": "",
        },
    }


def test_choices_of_claude_code_are_aliases_not_read_again(client):
    choices = ok(client.get("/api/providers/claude/model-choices"))
    assert "opus" in choices["aliases"]
    assert (choices["models"], choices["other_name"]) == (None, True)
    assert (choices["whole_process"], choices["read_again"]) == (True, False)


def test_choices_of_a_list_that_cannot_be_read_say_why(client, monkeypatch):
    listing(monkeypatch, "kilo", base.ModelList(why="`kilo models` timed out after 15 s"))
    saved_server()
    state.add_model("K", "kilo", "qwen3-8b", "s1")
    choices = ok(client.get("/api/providers/kilo/model-choices"))
    assert choices["why"] == "`kilo models` timed out after 15 s"
    assert [m["name"] for m in choices["external"]] == ["K"]
    assert (choices["other_name"], choices["read_again"]) == (True, True)


def test_choices_check_the_model_given_by_the_core_s_rule(client, monkeypatch):
    listing(monkeypatch, "kilo", base.ModelList((), ("a/b",), "kilo models"))
    server_launch.forget_model_lists()

    def check_of(model):
        return ok(client.get("/api/providers/kilo/model-choices", params={"model": model}))["check"]

    assert check_of("a/b")["kind"] == "ok"
    assert check_of("old/model")["kind"] == "refused"
    assert check_of("")["kind"] == "default"
    listing(monkeypatch, "kilo", base.ModelList(why="`kilo models` timed out after 15 s"))
    server_launch.forget_model_lists()
    assert check_of("a/b") == {
        "kind": "warn",
        "text": "`kilo models` timed out after 15 s: LADO cannot check a/b; a wrong name stops "
        "its agents at their first turn",
        "field": "",
        "name": "",
    }


def test_a_default_says_whether_it_takes_the_whole_process(client):
    saved_server()
    on_claude = state.add_model("Шлюз Opus", "claude", "opus", "s1")
    on_kilo = state.add_model("Q", "kilo", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("claude", on_claude.id, None))
    state.set_cli_default(state.ModelRef("kilo", on_kilo.id, None))
    defaults = ok(client.get("/api/model-settings"))["defaults"]
    assert {d["cli"]: d["whole_process"] for d in defaults} == {"claude": True, "kilo": False}


def test_choices_when_the_environment_cannot_be_read_say_why(client, monkeypatch):
    def broken(*args):
        raise runtime.LadoError("the login shell failed")

    monkeypatch.setattr(runtime, "agents_env", broken)
    server_launch.forget_model_lists()
    choices = ok(client.get("/api/providers/kilo/model-choices"))
    assert (choices["models"], choices["why"]) == (None, "the login shell failed")


def test_choices_make_no_db_and_take_the_kept_list_unless_fresh(client, monkeypatch, lado_home):
    asked = listing(monkeypatch, "kilo", base.ModelList((), ("a/b",), "kilo models"))
    server_launch.forget_model_lists()
    assert ok(client.get("/api/providers/kilo/model-choices"))["external"] == []
    client.get("/api/providers/kilo/model-choices")
    assert len(asked) == 1
    client.get("/api/providers/kilo/model-choices", params={"fresh": True})
    assert len(asked) == 2
    assert not (lado_home / "lado.db").exists()
    assert client.get("/api/providers/gemini/model-choices").status_code == 404


@pytest.fixture
def on_path(tmp_path, monkeypatch):
    """`on_path(cli, …)`: the agents' PATH holds those CLIs and no other."""

    def put(*clis):
        for cli in clis:
            command = tmp_path / providers.get(cli).command
            command.write_text("#!/bin/sh\n")
            command.chmod(0o755)

    monkeypatch.setattr(model_entries, "_agents_env", lambda provider: {"PATH": str(tmp_path)})
    return put


def test_set_an_external_default(client, on_path, serve):
    on_path("opencode")
    server = serve("lmstudio")
    ok(add_server(client, "lms", server.url))
    saved = state.add_model("Q", "opencode", "qwen3-8b", state.model_server("lms").id)
    server.requests.clear()
    answer = ok(client.put("/api/model-defaults/opencode", json={"external": saved.id}))
    assert answer["check"] is None
    assert [d["name"] for d in answer["settings"]["defaults"]] == ["Q"]
    assert server.requests == []


def test_set_a_built_in_default_with_its_check(client, on_path, monkeypatch):
    on_path("claude")
    answer = ok(client.put("/api/model-defaults/claude", json={"builtin": "opus"}))
    assert answer["check"]["kind"] == "ok"
    assert answer["settings"]["defaults"][0]["builtin"] == "opus"
    answer = ok(client.put("/api/model-defaults/claude", json={"builtin": "claude-x"}))
    assert answer["check"]["kind"] == "warn"
    assert state.cli_defaults() == [state.ModelRef("claude", None, "claude-x")]


def test_a_refused_default_is_an_entry_refused_and_names_no_command(client, on_path, monkeypatch):
    on_path("kilo")
    listing(monkeypatch, "kilo", base.ModelList((), ("a/b",), "kilo models"))
    server_launch.forget_model_lists()
    state.set_cli_default(state.ModelRef("kilo", None, "a/b"))
    detail = refused(client.put("/api/model-defaults/kilo", json={"builtin": "a/c"}))
    assert (detail["message"], detail["field"]) == (
        "a/c is not in Kilo CLI's list of models",
        "model",
    )
    detail = refused(client.put("/api/model-defaults/codex", json={"builtin": "x"}))
    assert (detail["message"], detail["field"]) == ("Codex CLI is not installed", "cli")
    assert state.cli_defaults() == [state.ModelRef("kilo", None, "a/b")]


def test_a_typed_name_is_taken_as_lado_model_default_takes_it(client, on_path):
    """Other name: another CLI's model is refused, the CLI's own saved model is a reference."""
    on_path("claude")
    saved_server()
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    own = state.add_model("Шлюз", "claude", "opus", "s1")
    detail = refused(client.put("/api/model-defaults/claude", json={"typed": "локальная qwen"}))
    assert (detail["message"], detail["field"]) == (
        '"Локальная Qwen" is a model of OpenCode, not of Claude Code',
        "model",
    )
    assert state.cli_defaults() == []
    answer = ok(client.put("/api/model-defaults/claude", json={"typed": "шлюз"}))
    assert answer["check"] is None
    assert state.cli_defaults() == [state.ModelRef("claude", own.id, None)]
    answer = ok(client.put("/api/model-defaults/claude", json={"typed": "claude-x"}))
    assert answer["check"]["kind"] == "warn"
    assert state.cli_defaults() == [state.ModelRef("claude", None, "claude-x")]


def test_a_picked_built_in_name_stays_built_in_whatever_a_saved_model_is_called(client, on_path):
    """A row of the list is a reference: a saved model of that name cannot take its place."""
    on_path("claude")
    saved_server()
    state.add_model("opus", "claude", "claude-opus-x", "s1")
    ok(client.put("/api/model-defaults/claude", json={"builtin": "opus"}))
    assert state.cli_defaults() == [state.ModelRef("claude", None, "opus")]


def test_the_check_of_a_typed_name_is_the_one_a_save_makes_and_saves_nothing(client, on_path):
    on_path("claude")
    saved_server()
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    state.add_model("Шлюз", "claude", "opus-x", "s1")

    def check_of(name):
        return ok(client.post("/api/model-defaults/claude/check", json={"name": name}))

    assert check_of("Локальная Qwen") == {
        "kind": "refused",
        "text": '"Локальная Qwen" is a model of OpenCode, not of Claude Code',
        "field": "model",
        "name": "",
    }
    own = check_of("шлюз")
    assert (own["kind"], own["text"]) == ("ok", "your model Шлюз: opus-x on lms")
    assert check_of("opus")["text"] == "an alias of Claude Code"
    assert check_of("claude-x")["kind"] == "warn"
    assert check_of("")["kind"] == "refused"
    assert state.cli_defaults() == []
    assert (
        client.post("/api/model-defaults/gemini/check", json={"name": "x"}).json()["field"] == "cli"
    )


def test_a_default_set_takes_exactly_one_way_to_name_the_model(client, on_path):
    on_path("claude")
    for body in ({}, {"external": "x", "builtin": "y"}, {"builtin": "y", "typed": "z"}):
        assert client.put("/api/model-defaults/claude", json=body).status_code == 422
    assert state.schema_version() is None or state.cli_defaults() == []


def test_clear_a_default(client):
    state.set_cli_default(state.ModelRef("kilo", None, "x/y"))
    assert ok(client.delete("/api/model-defaults/kilo"))["defaults"] == []
    assert ok(client.delete("/api/model-defaults/kilo"))["defaults"] == []
    assert refused(client.delete("/api/model-defaults/gemini"))["field"] == "cli"


# The launch window's list, read now.


def test_model_choices_fresh_skips_the_kept_list(client, monkeypatch):
    asked = listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    server_launch.forget_model_lists()
    choices = "/api/providers/kilo/model-choices"
    client.get(choices)
    client.get(choices)
    assert len(asked) == 1
    client.get(choices, params={"fresh": True})
    assert len(asked) == 2
    client.get(choices)
    assert len(asked) == 2  # the fresh list is kept
