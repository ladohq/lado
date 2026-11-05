"""The canary of a model server's key through Settings → Models' API (openspec change
model-settings-page, "A server's key enters the API and never leaves it"): unique keys sent
through a real `lado server` to check a server, to add one, to change it and check a change
with its kept key, in requests it cannot read and in one whose probe is refused, reach the
fake model server (in a process of its own) and the server's key file, and nothing else: no
answer, no change feed, no file under LADO_HOME (server.log, the error journal and lado.db
included) but `model-servers/<id>/key`."""

import json
import uuid

import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture
from test_project_secrets_canary import Api, files_holding

from lado import model_settings, state
from lado.server import run as server_run

pytestmark = pytest.mark.integration


@pytest.fixture
def api(lado_home):
    yield Api(server_run.wait_ready(server_run.start_background(None, 0)))
    if server_run.running():
        server_run.stop()


def test_a_model_server_s_key_is_found_nowhere_else(api, serve, lado_home):  # noqa: F811
    first, second, unread, refused_key, checked = (
        f"canary-{n}-{uuid.uuid4().hex}" for n in range(5)
    )
    canaries = (first, second, unread, refused_key, checked)
    said: list[str] = []

    def call(method, path, body=None, expected=200):
        status, answer = api.call(method, path, body)
        assert status == expected, answer
        said.append(answer)
        return json.loads(answer) if answer else None

    gate = serve("all", key=checked)
    found = call("POST", "/api/model-servers/check",
                 {"name": "gate", "address": gate, "key": checked, "key_typed": True})  # fmt: skip
    assert (found["refusals"], found["probe"]["models"]) == ([], ["m1"])
    found = call("POST", "/api/model-servers/check",
                 {"name": "gate", "address": gate, "key_typed": True})  # fmt: skip
    assert [r["field"] for r in found["refusals"]] == ["key"]
    call("POST", "/api/model-servers/check", {"name": "gate", "key": [checked]}, expected=422)
    old = serve("all", key=first)
    new = serve("all", key=second)
    added = call("POST", "/api/model-servers", {"name": "work", "address": old, "key": first})
    assert added["server"]["has_key"] is True
    call("POST", "/api/model-servers", {"name": "work", "address": new, "key": second,
                                        "replace": True})  # fmt: skip
    folder = model_settings.key_folder(state.model_server("work").id)
    assert (folder / model_settings.KEY).read_text() == second
    kept = call("POST", "/api/model-servers/check",
                {"name": "work", "address": new, "replace": True})  # fmt: skip
    assert (kept["refusals"], kept["probe"]["models"]) == ([], ["m1"])  # with its kept key
    for body in (
        {"name": 1, "address": new, "key": unread},
        {"name": "x", "address": new, "key": [unread]},
        {"key": unread},
    ):
        call("POST", "/api/model-servers", body, expected=422)
    forbidden = serve("forbidden")
    detail = call("POST", "/api/model-servers",
                  {"name": "gw", "address": forbidden, "key": refused_key},
                  expected=400)["detail"]  # fmt: skip
    assert detail["field"] == "key"

    call("GET", "/api/model-settings")
    call("POST", "/api/model-servers/work/probe")
    check = call("POST", "/api/models/check", {"cli": "opencode", "model": "m1", "server": "work"})
    assert check["kind"] == "ok"
    model = call("POST", "/api/models", {"cli": "opencode", "model": "m1", "server": "work"})
    assert model["model"]["name"] == "m1 · work · OpenCode"
    call("PATCH", "/api/models/m1%20%C2%B7%20work%20%C2%B7%20OpenCode", {"name": "Local"})
    home = state.home_path()
    for value in canaries:
        assert files_holding(home, value.encode(), [folder]) == []
    said.append(api.feed(2.0))  # the entries send no event: whatever the feed sends

    settings = call("DELETE", "/api/model-servers/work?with_models=true&confirmed=Local")
    assert settings == {"models": [], "servers": [], "defaults": []}
    assert not folder.exists()
    server_run.stop()
    assert [text for text in said if any(c in text for c in canaries)] == []
    for value in canaries:
        assert files_holding(home, value.encode(), []) == []
