"""The UI server's API of Settings → Models (openspec change model-settings-page): the
configured models and model servers through lado.server.model_entries over
lado.model_settings. In process, with FastAPI's test client and the fake model servers of
tests/fake_model_server.py."""

import socket

import fake_model_server as fake
import pytest
from fastapi.testclient import TestClient

from lado import agent_env, model_settings, providers, state
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
    assert detail["message"] == (
        f'{work.url} asks for a key (401): run lado model-server add "work" {work.url} --key'
    )
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
        'no model server "nope" is saved; lado model-server list names them'
    )


def test_a_list_given_only_with_the_version_header_has_no_why(client, serve):
    ok(add_server(client, "anth", serve("anthropic-versioned").url))
    probe = ok(client.post("/api/model-servers/anth/probe"))
    assert (probe["models"], probe["models_why"]) == (["claude-x"], "")


# Checking and adding a model.


def check(client, **given):
    return ok(client.post("/api/models/check", json=given))


def test_check_model_ok_warn_refused(client, serve, monkeypatch):
    listing(monkeypatch, "kilo", base.ModelList((), ("kilo/a",), "kilo models"))
    assert check(client, cli="kilo", model="kilo/a") == {
        "kind": "ok",
        "text": "in Kilo CLI's list of models",
        "field": "",
    }
    assert check(client, cli="kilo", model="kilo/z") == {
        "kind": "refused",
        "text": "kilo/z is not in Kilo CLI's list of models; kilo models prints the list",
        "field": "model",
    }
    listing(monkeypatch, "claude", base.ModelList(("opus",), None, why="no list"))
    warned = check(client, cli="claude", model="claude-opus-5-5")
    assert (warned["kind"], warned["field"]) == ("warn", "")
    assert check(client, cli="gemini", model="x")["field"] == "cli"
    assert check(client, cli="kilo", model="kilo/a", server="nope")["field"] == "server"
    assert state.schema_version() is None or state.models() == []


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
        "check": {"kind": "ok", "text": "an alias of Claude Code", "field": ""},
    }
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    added = ok(client.post("/api/models", json={"cli": "opencode", "model": "qwen3-8b",
                                                "server": "LiteLLM"}))  # fmt: skip
    assert added["model"]["name"] == "qwen3-8b · LiteLLM"
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
        'a model "Other" is saved already; remove it first: lado model remove "Other"',
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
    assert detail["message"] == 'no model "claude sonnet" is saved; lado model list names them'


def test_remove_server_route(client, serve):
    server = serve("lmstudio")
    ok(add_server(client, "LiteLLM", server.url))
    id = state.model_server("LiteLLM").id
    for name in ("a", "b"):
        state.add_model(name, "opencode", "qwen3-8b", id)
    state.add_model("own", "claude", "haiku", None)
    detail = refused(client.delete("/api/model-servers/LiteLLM"))
    assert detail["hint"] == (
        'or remove them with it: lado model-server remove "LiteLLM" --with-models'
    )
    settings = ok(client.delete("/api/model-servers/litellm", params={"with_models": True}))
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
