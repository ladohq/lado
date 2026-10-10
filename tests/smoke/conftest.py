"""Smoke tests: real agent CLIs, no model. One short scenario per provider shows that LADO and
the CLI work together on this platform: a session starts, the CLI's hooks run, LADO's
messages reach it, a worker starts, and a stop leaves no process.

Run them with `uv run pytest -m smoke` (or `make test-smoke`, `make test-smoke
PROVIDER=kilo`). They need the CLIs installed, never a login or an account: each CLI gets a
home of its own (HOME, XDG_*, CLAUDE_CONFIG_DIR, CODEX_HOME in the test's folder, never the
user's) whose config points it at `fake_endpoint`, a local server that answers every request
with 401. So no model is ever reached, and the turn a message starts ends on that error.

A failed test keeps its evidence as a failed live test does (real_clis.EVIDENCE).
"""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import real_clis
from agent_helpers import init_repo
from real_clis import CLASSES, isolated, with_model  # noqa: F401 (a fixture)

from lado import providers

KEY = "smoke-fake-key-0123456789abcdefghij"  # no account's key: the endpoint takes none
MODEL = "smoke-model"  # the model the endpoint "serves" to OpenCode, Kilo and Codex

# The error each API gives a request with a wrong key; the CLIs end the turn on it and do not
# retry (a closed port would give them a transient error to retry with their own backoff).
ANTHROPIC_401 = {
    "type": "error",
    "error": {"type": "authentication_error", "message": "invalid x-api-key"},
}
OPENAI_401 = {
    "error": {
        "message": "Incorrect API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}


class Endpoint:
    """A model API on 127.0.0.1 that answers every request at once with 401, and keeps the
    method and path of each."""

    def __init__(self):
        self.requests: list[tuple[str, str]] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                endpoint.requests.append((self.command, self.path))
                body = ANTHROPIC_401 if "/messages" in self.path else OPENAI_401
                data = json.dumps(body).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_endpoint():
    endpoint = Endpoint()
    yield endpoint
    endpoint.close()


def _openai_compatible(endpoint: Endpoint) -> dict:
    """An OpenCode or Kilo global config with one provider, `smoke`, at the endpoint."""
    return {
        "provider": {
            "smoke": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "smoke",
                "options": {"baseURL": f"{endpoint.url}/v1", "apiKey": KEY},
                "models": {MODEL: {"name": MODEL}},
            }
        }
    }


@pytest.fixture(params=["claude", "codex", "kilo", "opencode"])
def smoke_provider(request, monkeypatch, tmp_path, fake_endpoint, codex_home) -> str:
    """The name of a provider whose CLI is installed, pointed at the fake endpoint in a home
    of its own. A CLI that is missing skips, which CI's pass rule makes red."""
    name = request.param
    if shutil.which(CLASSES[name].command) is None:
        pytest.skip(f"{CLASSES[name].command} not installed")
    home = tmp_path / "home"
    home.mkdir()
    # The agents get the test's environment (LADO_AGENT_ENV=inherit): none of the user's
    # config, skills or keys reaches them.
    monkeypatch.setenv("HOME", str(home))
    for xdg, folder in [
        ("XDG_CONFIG_HOME", ".config"),
        ("XDG_DATA_HOME", ".local/share"),
        ("XDG_CACHE_HOME", ".cache"),
        ("XDG_STATE_HOME", ".local/state"),
    ]:
        (home / folder).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(xdg, str(home / folder))
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    if name == "claude":
        config = tmp_path / "claude-config"
        config.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
        # What a human answers once, ahead: the first-run screens, the bypass permissions
        # mode's disclaimer (a fresh home shows it before any hook; 2.1.296), and the trust of
        # the smoke's repo.
        (config / ".claude.json").write_text(
            json.dumps(
                {
                    "hasCompletedOnboarding": True,
                    "bypassPermissionsModeAccepted": True,
                    "projects": {str(tmp_path / "My Repo"): {"hasTrustDialogAccepted": True}},
                }
            )
        )
        monkeypatch.setenv("ANTHROPIC_BASE_URL", fake_endpoint.url)
        # A token, which Claude Code takes without asking (an ANTHROPIC_API_KEY it has not
        # seen is a question). It retries every 401 ten times with backoff (2.1.296), so no
        # retries: the turn ends on the first.
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", KEY)
        monkeypatch.setenv("CLAUDE_CODE_MAX_RETRIES", "0")
        monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    elif name == "codex":
        codex_home.mkdir(parents=True, exist_ok=True)
        (codex_home / "config.toml").write_text(
            f'model = "{MODEL}"\n'
            'model_provider = "smoke"\n'
            "[model_providers.smoke]\n"
            'name = "smoke"\n'
            f'base_url = "{fake_endpoint.url}/v1"\n'
            'wire_api = "responses"\n'
            'env_key = "SMOKE_API_KEY"\n'
        )
        monkeypatch.setenv("SMOKE_API_KEY", KEY)
    else:
        folder = home / ".config" / name
        folder.mkdir()
        (folder / f"{name}.json").write_text(json.dumps(_openai_compatible(fake_endpoint)))
        provider = with_model(CLASSES[name], f"smoke/{MODEL}")
        monkeypatch.setitem(providers._PROVIDERS, name, provider)
    return name


@pytest.fixture
def smoke_repo(smoke_provider, tmp_path):
    return init_repo(tmp_path / "My Repo")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    real_clis.keep_evidence(item, outcome.get_result())
