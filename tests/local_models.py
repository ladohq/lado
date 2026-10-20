"""The local models of the live tests (docs/testing.md): LM Studio's check, the config
that gives each CLI its model, and the bridge Codex reaches LM Studio through.

Codex, OpenCode and Kilo run on one model LM Studio serves, MODEL. OpenCode and Kilo reach
it as LM Studio's OpenAI-compatible chat API, through a config file of the test
(`opencode_config`). Codex speaks only the Responses API, and LM Studio's own drops the MCP
tools Codex sends (their `namespace` type), so Codex goes through a LiteLLM proxy that turns
Responses into Chat (`Bridge`), started by the test.
"""

import json
import os
import secrets
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from lado.providers.codex import toml_text

MODEL = "qwen/qwen3.5-35b-a3b"  # vision and tools; 22 GB
MIN_CONTEXT = 65536  # a Codex agent's first prompt is 10-13k tokens; LM Studio's default 4096
LITELLM = ["uvx", "--from", "litellm[proxy]==1.104.2", "litellm"]
INSTALL_TIMEOUT = 300  # uvx's first run installs LiteLLM
START_TIMEOUT = 120
# OpenCode's and Kilo's config file of the test, by the variable each reads it from.
CONFIG_VARIABLES = {"opencode": "OPENCODE_CONFIG", "kilo": "KILO_CONFIG"}
# Each CLI's own test model, which wins over the endpoint's.
MODEL_VARIABLES = {
    p: f"LADO_LIVE_{p.upper()}_MODEL" for p in ("claude", "codex", "kilo", "opencode")
}
# A remote OpenAI-compatible endpoint instead of LM Studio, for Codex, OpenCode and Kilo: its
# base URL (ending in /v1), its key (only ever in the environment: the configs name the
# variable, never the value) and the model of all three.
ENDPOINT = "LADO_LIVE_ENDPOINT"
API_KEY = "LADO_LIVE_API_KEY"
ENDPOINT_MODEL = "LADO_LIVE_MODEL"
ENDPOINT_PROVIDER = "endpoint"  # the provider's name in each CLI's config


def lmstudio_url() -> str:
    return (os.environ.get("LADO_LIVE_LMSTUDIO_URL") or "http://127.0.0.1:1234").rstrip("/")


def lmstudio_models(url: str) -> list[dict] | None:
    """The models LM Studio lists (/api/v0/models), None when it does not answer."""
    try:
        with urllib.request.urlopen(f"{url}/api/v0/models", timeout=5) as response:
            return json.load(response)["data"]
    except (OSError, ValueError, KeyError):
        return None


def _instances(models: list[dict], model: str) -> list[dict]:
    """The model's entries: LM Studio lists a second instance as `<id>:2`."""
    return [m for m in models if m.get("id") == model or m.get("id", "").startswith(f"{model}:")]


def lmstudio_problem(model: str, url: str) -> str | None:
    """Why `model` cannot run the live tests on LM Studio at `url`, with what to run; None
    when an instance is loaded with a context of at least MIN_CONTEXT."""
    models = lmstudio_models(url)
    if models is None:
        return f"LM Studio is not reachable at {url}: start LM Studio's server (`lms server start`)"
    instances = _instances(models, model)
    if not instances:
        return f"LM Studio has no model {model} (`lms get {model}`)"
    if not any(
        m.get("state") == "loaded" and (m.get("loaded_context_length") or 0) >= MIN_CONTEXT
        for m in instances
    ):
        return (
            f"LM Studio has not loaded {model} with a context of at least {MIN_CONTEXT} tokens "
            f"(`lms load {model} --context-length {MIN_CONTEXT} -y`)"
        )
    return None


def lmstudio_sees_images(model: str, url: str) -> bool:
    """Whether LM Studio declares the model a vision model (`type: vlm`)."""
    return any(m.get("type") == "vlm" for m in _instances(lmstudio_models(url) or [], model))


def opencode_config(model: str, base_url: str, key_variable: str | None = None) -> dict:
    """OpenCode's and Kilo's config of the test (OPENCODE_CONFIG, KILO_CONFIG): the model,
    and for `lmstudio/<id>` or `endpoint/<id>` the OpenAI-compatible provider it names at
    `base_url`, with the key as a reference to `key_variable` ({env:...}, which both expand).
    LADO's own config of each agent goes on top and keeps both."""
    config: dict = {"model": model}
    provider, _, name = model.partition("/")
    if provider in ("lmstudio", ENDPOINT_PROVIDER):
        options = {"baseURL": base_url}
        if key_variable:
            options["apiKey"] = f"{{env:{key_variable}}}"
        config["provider"] = {
            provider: {
                "npm": "@ai-sdk/openai-compatible",
                "name": "LM Studio (local)" if provider == "lmstudio" else "the live endpoint",
                "options": options,
                "models": {
                    name: {
                        "name": name,
                        "tool_call": True,
                        "attachment": True,
                        "modalities": {"input": ["text", "image"], "output": ["text"]},
                        "limit": {"context": MIN_CONTEXT, "output": 16384},
                    }
                },
            }
        }
    return config


def codex_config(model: str, base_url: str, env_key: str | None, name: str = "bridge") -> str:
    """The user's Codex config of the test, which LADO carries into each agent's own
    (providers/codex.py, CARRIED): the model at a Responses endpoint, its key read from the
    variable `env_key`."""
    provider = {"name": name, "base_url": base_url, "wire_api": "responses"}
    if env_key:
        provider["env_key"] = env_key
    return toml_text({"model": model, "model_provider": name, "model_providers": {name: provider}})


def endpoint() -> str | None:
    """The remote endpoint's base URL, or None: LM Studio."""
    return (os.environ.get(ENDPOINT) or "").rstrip("/") or None


def endpoint_model(provider: str) -> str:
    """The provider's test model on the endpoint: its own variable, else LADO_LIVE_MODEL
    (OpenCode and Kilo name it `endpoint/<id>`); "" when neither is set."""
    if own := os.environ.get(MODEL_VARIABLES[provider]):
        return own
    model = os.environ.get(ENDPOINT_MODEL, "")
    return f"{ENDPOINT_PROVIDER}/{model}" if model and provider in CONFIG_VARIABLES else model


def endpoint_problem(provider: str) -> str | None:
    """Why the provider's tests cannot run on the endpoint, or None. Never the key."""
    if not endpoint_model(provider):
        own = MODEL_VARIABLES[provider]
        return f"{ENDPOINT} has no default model: set {ENDPOINT_MODEL} (or {own})"
    if not os.environ.get(API_KEY):
        return f"{ENDPOINT} is set without its key: set {API_KEY}"
    return None


def write_endpoint_config(provider: str, model: str, folder: Path) -> dict[str, str]:
    """Write the provider's config for the endpoint in `folder` (Codex: the test's own user
    config, `folder` its CODEX_HOME), the key only by reference. The variables to set."""
    url = endpoint()
    if provider == "codex":
        text = codex_config(model, url, API_KEY, ENDPOINT_PROVIDER)
        (folder / "config.toml").write_text(text)
        return {}
    path = folder / f"{provider}-config.json"
    path.write_text(json.dumps(opencode_config(model, url, API_KEY)))
    return {CONFIG_VARIABLES[provider]: str(path)}


def write_lmstudio_config(provider: str, model: str, folder: Path) -> dict[str, str]:
    """Write OpenCode's or Kilo's config for LM Studio in `folder`, at its OpenAI-compatible
    API under /v1. The variables to set."""
    path = folder / f"{provider}-config.json"
    path.write_text(json.dumps(opencode_config(model, f"{lmstudio_url()}/v1")))
    return {CONFIG_VARIABLES[provider]: str(path)}


class BridgeError(Exception):
    pass


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Bridge:
    """A LiteLLM proxy on 127.0.0.1 that serves `model` at a Responses API (`base_url`)
    from LM Studio's chat API, behind a random key (`key`, its master key). Its process
    group is ended by `stop`."""

    def __init__(self, folder: Path, port: int, key: str, process: subprocess.Popen):
        self.folder, self.port, self.key, self.process = folder, port, key, process
        self.base_url = f"http://127.0.0.1:{port}/v1"
        self.log = folder / "litellm.log"

    @classmethod
    def start(cls, folder: Path, upstream: str, model: str, command=LITELLM) -> "Bridge":
        folder.mkdir(parents=True, exist_ok=True)
        log = folder / "litellm.log"
        version = subprocess.run(
            [*command, "--version"],
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT,
            check=False,
        )
        if version.returncode != 0:
            raise BridgeError(
                f"{' '.join(command)} --version failed ({version.returncode}): "
                f"{(version.stdout + version.stderr)[-2000:]}"
            )
        config = folder / "litellm.yaml"
        config.write_text(
            "model_list:\n"
            f"  - model_name: {model}\n"
            "    litellm_params:\n"
            f"      model: openai/{model}\n"
            f"      api_base: {upstream}/v1\n"
            "      api_key: none\n"
            "      use_chat_completions_api: true\n"
        )
        port, key = _free_port(), f"sk-{secrets.token_hex(24)}"
        argv = [*command, "--config", str(config), "--host", "127.0.0.1", "--port", str(port)]
        # It serves the whole test run: without the LADO_HOME of the test that starts it,
        # the mark by which that test's leftovers are killed (tests/leftovers.py).
        env = {name: value for name, value in os.environ.items() if name != "LADO_HOME"}
        with log.open("w") as out:
            process = subprocess.Popen(
                argv,
                stdout=out,
                stderr=subprocess.STDOUT,
                env={**env, "LITELLM_MASTER_KEY": key},
                start_new_session=True,  # its own process group, ended by stop()
            )
        bridge = cls(folder, port, key, process)
        try:
            bridge._wait()
        except BaseException:
            bridge.stop()
            raise
        return bridge

    def _wait(self) -> None:
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                health = f"http://127.0.0.1:{self.port}/health/liveliness"
                with urllib.request.urlopen(health, timeout=2):
                    return
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        raise BridgeError(
            f"the bridge did not come up on port {self.port} (exit {self.process.poll()}); "
            f"its log {self.log}:\n{self.log.read_text()[-3000:]}"
        )

    def stop(self) -> None:
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            self.process.wait()  # it ended by itself
            return
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
