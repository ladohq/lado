"""tests/fake_model_server.py: the model servers of the probe's tests, in process and as a
script (the integration tests run it in its own process)."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import fake_model_server as fake
import pytest

SCRIPT = Path(fake.__file__)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def ask(url: str, method: str = "GET", headers: dict | None = None) -> tuple[int, object]:
    data = b"{}" if method == "POST" else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with OPENER.open(request, timeout=5) as answer:
            status, raw, kind = answer.status, answer.read(), answer.headers["Content-Type"]
    except urllib.error.HTTPError as e:
        status, raw, kind = e.code, e.read(), e.headers["Content-Type"]
    return status, json.loads(raw) if kind == "application/json" else raw.decode()


def statuses(server: fake.Server) -> dict[str, int]:
    """The status of each of the probe's requests."""
    checks = {
        "models": ("GET", fake.MODELS),
        "version": ("GET", fake.OLLAMA_VERSION),
        "lmstudio": ("GET", fake.LMSTUDIO_MODELS),
        "chat": ("POST", fake.CHAT),
        "responses": ("POST", fake.RESPONSES),
        "messages": ("POST", fake.MESSAGES),
        "control": ("POST", fake.CONTROL),
    }
    return {k: ask(server.url + path, method)[0] for k, (method, path) in checks.items()}


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("openai", (200, 404, 404, 400, 404, 404, 404)),
        ("ollama", (200, 200, 404, 400, 400, 404, 404)),
        ("list-500", (500, 200, 404, 400, 400, 404, 404)),
        ("lmstudio", (200, 404, 200, 400, 400, 404, 404)),
        ("anthropic", (200, 404, 404, 404, 404, 400, 404)),
        ("litellm", (200, 404, 404, 400, 400, 400, 404)),
        ("anthropic-versioned", (400, 404, 404, 404, 404, 400, 404)),
        ("responses-only", (404, 404, 404, 404, 400, 404, 404)),
        ("messages-only", (404, 404, 404, 404, 404, 400, 404)),
        ("all", (200, 404, 404, 400, 422, 400, 404)),
        ("models-only", (200, 404, 404, 405, 400, 404, 404)),
        ("empty-list", (200, 404, 404, 400, 404, 404, 404)),
        ("unknown", (404,) * 7),
        ("gateway-400", (400,) * 7),
        ("gateway-400-list", (200, 400, 400, 400, 400, 400, 400)),
        ("forbidden", (403,) * 7),
    ],
)
def test_each_profile_answers_the_probe_s_paths_as_named(profile, expected):
    server = fake.Server(profile)
    try:
        assert tuple(statuses(server).values()) == expected
    finally:
        server.close()


def test_bodies_tell_the_shapes_apart():
    ollama, anthropic, plain = (
        fake.Server("ollama"),
        fake.Server("anthropic"),
        fake.Server("models-only"),
    )
    try:
        assert ask(ollama.url + fake.MODELS)[1]["data"][0]["id"] == "llama3.1:8b"
        assert ask(ollama.url + fake.OLLAMA_VERSION)[1] == {"version": "0.12.3"}
        listed = ask(anthropic.url + fake.MODELS)[1]
        assert listed["has_more"] is False and listed["data"][0]["type"] == "model"
        assert ask(plain.url + fake.RESPONSES, "POST") == (400, "Bad Request")  # not JSON
        assert ask(plain.url + "/elsewhere") == (404, "404 page not found")
    finally:
        for server in (ollama, anthropic, plain):
            server.close()


VERSIONED = {"anthropic-version": "2023-06-01"}


def test_a_gateway_of_both_apis_lists_by_the_header():
    litellm, versioned = fake.Server("litellm"), fake.Server("anthropic-versioned")
    try:
        plain = ask(litellm.url + fake.MODELS)[1]
        assert "has_more" not in plain and plain["data"][0]["object"] == "model"
        headered = ask(litellm.url + fake.MODELS, headers=VERSIONED)[1]
        assert headered["has_more"] is False and headered["data"][0]["type"] == "model"
        assert [m["id"] for m in plain["data"]] == [m["id"] for m in headered["data"]]
        assert ask(versioned.url + fake.MODELS)[0] == 400
        status, listed = ask(versioned.url + fake.MODELS, headers=VERSIONED)
        assert (status, listed["data"][0]["id"]) == (200, "claude-x")
        # The header changes only the answers a profile gives for it.
        assert ask(litellm.url + fake.CHAT, "POST", VERSIONED)[0] == 400
    finally:
        litellm.close()
        versioned.close()


def test_lmstudio_types_its_models():
    server = fake.Server("lmstudio")
    try:
        listed = ask(server.url + fake.LMSTUDIO_MODELS)[1]["data"]
        assert [(m["id"], m["type"]) for m in listed] == [
            ("qwen3-8b", "llm"),
            (fake.EMBEDDINGS, "embeddings"),
        ]
        assert [m["id"] for m in ask(server.url + fake.MODELS)[1]["data"]] == [
            "qwen3-8b",
            fake.EMBEDDINGS,
        ]
    finally:
        server.close()


def test_it_keeps_each_request_with_its_headers_and_body():
    server = fake.Server("openai")
    try:
        ask(server.url + fake.CHAT, "POST", {"X-Mark": "1"})
        (request,) = server.requests
        assert (request.method, request.path, request.body) == ("POST", fake.CHAT, b"{}")
        assert request.headers["X-Mark"] == "1"
        assert server.paths() == [("POST", fake.CHAT)]
    finally:
        server.close()


def test_a_key_is_asked_before_anything_else():
    server = fake.Server("openai", key="k1")
    try:
        assert ask(server.url + fake.MODELS)[0] == 401
        assert ask(server.url + fake.MODELS, headers={"Authorization": "Bearer no"})[0] == 401
        assert ask(server.url + fake.MODELS, headers={"Authorization": "Bearer k1"})[0] == 200
    finally:
        server.close()


def test_a_prefix_is_the_gateway_s_path():
    server = fake.Server("openai", prefix="/llm")
    try:
        assert server.url.endswith("/llm")
        assert ask(server.url + fake.MODELS)[0] == 200
        assert ask(server.url.removesuffix("/llm") + fake.MODELS)[0] == 404
    finally:
        server.close()


def test_redirect_and_hang():
    redirect = fake.Server("redirect", location="http://elsewhere.invalid")
    hang = fake.Server("hang")
    try:
        status, _ = ask(redirect.url + fake.MODELS)
        assert status == 301
        assert redirect.requests[0].path == fake.MODELS
        request = urllib.request.Request(hang.url + fake.MODELS)
        with pytest.raises(TimeoutError):
            urllib.request.urlopen(request, timeout=0.3)
    finally:
        redirect.close()
        hang.close()


def test_as_a_script_it_writes_its_port_and_answers_with_its_key(tmp_path):
    port_file = tmp_path / "port"
    script = subprocess.Popen([sys.executable, "-I", str(SCRIPT), "ollama", str(port_file), "k1"])
    try:
        deadline = time.monotonic() + 10
        while not port_file.exists():
            assert time.monotonic() < deadline, "the script never wrote its port"
            time.sleep(0.05)
        url = f"http://127.0.0.1:{port_file.read_text()}"
        assert ask(url + fake.OLLAMA_VERSION)[0] == 401
        auth = {"Authorization": "Bearer k1"}
        assert ask(url + fake.OLLAMA_VERSION, headers=auth) == (200, {"version": "0.12.3"})
    finally:
        script.terminate()
        script.wait(timeout=10)
