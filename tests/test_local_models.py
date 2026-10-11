"""The live tests' local models (tests/local_models.py), against a fake LM Studio and a fake
bridge command: no model, no network."""

import http.server
import json
import os
import sys
import threading
import time

import local_models
import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

MODEL = local_models.MODEL


def entry(id=MODEL, state="loaded", context=65536, type="vlm"):
    """A model as LM Studio's /api/v0/models lists it: only the fields the check reads."""
    loaded = context if state == "loaded" else None
    return {
        "id": id,
        "type": type,
        "state": state,
        "max_context_length": 262144,
        "loaded_context_length": loaded,
    }


@pytest.fixture
def lmstudio():
    """A fake LM Studio server; set `.models` to what it lists. Its URL is `.url`."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/api/v0/models":
                self.send_error(404)
                return
            body = json.dumps({"object": "list", "data": server.models}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.models = []
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


def test_a_loaded_model_with_enough_context_is_usable(lmstudio):
    lmstudio.models = [entry("other"), entry()]
    assert local_models.lmstudio_problem(MODEL, lmstudio.url) is None


def test_a_second_instance_counts_as_the_model(lmstudio):
    lmstudio.models = [entry(state="not-loaded"), entry(f"{MODEL}:2")]
    assert local_models.lmstudio_problem(MODEL, lmstudio.url) is None


def test_lmstudio_not_reachable_says_to_start_its_server(lmstudio):
    url = lmstudio.url
    lmstudio.shutdown()
    lmstudio.server_close()
    problem = local_models.lmstudio_problem(MODEL, url)
    assert problem.startswith(f"LM Studio is not reachable at {url}")
    assert "lms server start" in problem


def test_a_model_lmstudio_does_not_have_is_named(lmstudio):
    lmstudio.models = [entry("other")]
    problem = local_models.lmstudio_problem(MODEL, lmstudio.url)
    assert problem == f"LM Studio has no model {MODEL} (`lms get {MODEL}`)"


@pytest.mark.parametrize(
    "listed",
    [
        [entry(state="not-loaded")],
        [entry(context=4096)],
        [entry(context=4096), entry(f"{MODEL}:2", state="not-loaded")],
    ],
)
def test_a_model_not_loaded_with_enough_context_gives_the_load_command(lmstudio, listed):
    lmstudio.models = listed
    problem = local_models.lmstudio_problem(MODEL, lmstudio.url)
    assert problem == (
        f"LM Studio has not loaded {MODEL} with a context of at least 65536 tokens "
        f"(`lms load {MODEL} --context-length 65536 -y`)"
    )


def test_images_are_seen_by_a_model_lmstudio_lists_as_vlm(lmstudio):
    lmstudio.models = [entry(), entry("text-only", type="llm")]
    assert local_models.lmstudio_sees_images(MODEL, lmstudio.url) is True
    assert local_models.lmstudio_sees_images("text-only", lmstudio.url) is False
    assert local_models.lmstudio_sees_images("absent", lmstudio.url) is False


def test_the_url_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("LADO_LIVE_LMSTUDIO_URL", raising=False)
    assert local_models.lmstudio_url() == "http://127.0.0.1:1234"
    monkeypatch.setenv("LADO_LIVE_LMSTUDIO_URL", "http://127.0.0.1:9/")
    assert local_models.lmstudio_url() == "http://127.0.0.1:9"


def test_the_opencode_config_has_lmstudio_and_the_model():
    config = local_models.opencode_config(f"lmstudio/{MODEL}", "http://127.0.0.1:1234")
    assert config["model"] == f"lmstudio/{MODEL}"
    lmstudio = config["provider"]["lmstudio"]
    assert lmstudio["npm"] == "@ai-sdk/openai-compatible"
    assert lmstudio["options"]["baseURL"] == "http://127.0.0.1:1234/v1"
    model = lmstudio["models"][MODEL]
    assert model["tool_call"] is True
    assert model["modalities"]["input"] == ["text", "image"]
    assert model["limit"]["context"] == 65536


def test_the_opencode_config_of_another_provider_has_only_the_model():
    config = local_models.opencode_config("opencode/big-pickle", "http://127.0.0.1:1234")
    assert config == {"model": "opencode/big-pickle"}


def test_the_codex_config_points_at_the_endpoint():
    text = local_models.codex_config(MODEL, "http://127.0.0.1:4011/v1", "BRIDGE_KEY")
    config = tomllib.loads(text)
    assert config["model"] == MODEL
    assert config["model_provider"] == "bridge"
    assert config["model_providers"]["bridge"] == {
        "name": "bridge",
        "base_url": "http://127.0.0.1:4011/v1",
        "wire_api": "responses",
        "env_key": "BRIDGE_KEY",
    }
    no_key = tomllib.loads(local_models.codex_config(MODEL, "http://h/v1", None))
    assert "env_key" not in no_key["model_providers"]["bridge"]


# A stand-in for LiteLLM: `--version`, or a server that answers /health/liveliness and
# records its argv, its key and its config.
FAKE_LITELLM = """\
import http.server, json, os, pathlib, sys
here = pathlib.Path(sys.argv[0]).parent
if "--version" in sys.argv:
    print("fake litellm 1.0")
    sys.exit(int(os.environ.get("FAKE_VERSION_EXIT", "0")))
if os.environ.get("FAKE_NEVER_UP"):
    print("cannot start: no luck", flush=True)
    sys.exit(3)
args = sys.argv[1:]
config = args[args.index("--config") + 1]
(here / "seen.json").write_text(json.dumps({
    "argv": args,
    "key": os.environ.get("LITELLM_MASTER_KEY"),
    "config": pathlib.Path(config).read_text(),
    "pid": os.getpid(),
}))

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/health/liveliness" else 404)
        self.end_headers()
        self.wfile.write(b'"alive"')

    def log_message(self, *a):
        pass

port = int(args[args.index("--port") + 1])
http.server.HTTPServer((args[args.index("--host") + 1], port), Handler).serve_forever()
"""


@pytest.fixture
def fake_litellm(tmp_path):
    script = tmp_path / "litellm.py"
    script.write_text(FAKE_LITELLM)
    return [sys.executable, str(script)], tmp_path / "seen.json"


def gone(pid: int) -> bool:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_the_bridge_starts_with_a_random_key_and_stops(tmp_path, fake_litellm):
    command, seen = fake_litellm
    bridge = local_models.Bridge.start(tmp_path / "b1", "http://127.0.0.1:1234", MODEL, command)
    try:
        recorded = json.loads(seen.read_text())
        assert bridge.base_url == f"http://127.0.0.1:{bridge.port}/v1"
        assert recorded["argv"][-4:] == ["--host", "127.0.0.1", "--port", str(bridge.port)]
        assert recorded["key"] == bridge.key and len(bridge.key) >= 32
        config = recorded["config"]
        assert f"model_name: {MODEL}" in config
        assert f"model: openai/{MODEL}" in config
        assert "api_base: http://127.0.0.1:1234/v1" in config
        assert "use_chat_completions_api: true" in config
        assert "DANGEROUSLY" not in json.dumps(dict(os.environ)) + config
    finally:
        bridge.stop()
    assert gone(recorded["pid"])
    other = local_models.Bridge.start(tmp_path / "b2", "http://127.0.0.1:1234", MODEL, command)
    other.stop()
    assert other.key != bridge.key


def test_a_bridge_that_does_not_come_up_fails_with_its_log(tmp_path, fake_litellm, monkeypatch):
    command, _ = fake_litellm
    monkeypatch.setenv("FAKE_NEVER_UP", "1")
    with pytest.raises(local_models.BridgeError) as error:
        local_models.Bridge.start(tmp_path / "b", "http://127.0.0.1:1234", MODEL, command)
    assert "cannot start: no luck" in str(error.value)
    assert str(tmp_path / "b" / "litellm.log") in str(error.value)


def test_a_bridge_whose_install_fails_says_so(tmp_path, fake_litellm, monkeypatch):
    command, seen = fake_litellm
    monkeypatch.setenv("FAKE_VERSION_EXIT", "2")
    with pytest.raises(local_models.BridgeError, match="--version failed"):
        local_models.Bridge.start(tmp_path / "b", "http://127.0.0.1:1234", MODEL, command)
    assert not seen.exists()


def test_the_bridge_command_is_litellm_pinned_through_uvx():
    assert local_models.LITELLM == ["uvx", "--from", "litellm[proxy]==1.104.2", "litellm"]
