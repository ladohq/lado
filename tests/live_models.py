"""The models of the live tests (docs/testing.md): every provider reaches its model at one
remote endpoint, LADO_LIVE_ENDPOINT, by its entry in SETUPS. No endpoint, key or model: its
tests skip, saying what to set.

OpenCode and Kilo take the endpoint as an OpenAI-compatible chat API through a config file of
the test (`opencode_config`), Codex as a Responses API through its own config (`codex_config`),
Claude Code as an Anthropic API through its variables.
"""

import json
import os
from pathlib import Path

from lado.providers.codex import toml_text

# The context the config declares: a Codex agent's first prompt is 10-13k tokens.
MIN_CONTEXT = 65536
# OpenCode's and Kilo's config file of the test, by the variable each reads it from.
CONFIG_VARIABLES = {"opencode": "OPENCODE_CONFIG", "kilo": "KILO_CONFIG"}
# Each CLI's own test model, which wins over the endpoint's.
MODEL_VARIABLES = {
    p: f"LADO_LIVE_{p.upper()}_MODEL" for p in ("claude", "codex", "kilo", "opencode")
}
# The endpoint: its base URL (ending in /v1), its key (only ever in the environment: the
# configs name the variable, never the value) and the model of all four.
ENDPOINT = "LADO_LIVE_ENDPOINT"
API_KEY = "LADO_LIVE_API_KEY"
ENDPOINT_MODEL = "LADO_LIVE_MODEL"
ENDPOINT_PROVIDER = "endpoint"  # the provider's name in each CLI's config
# What a person's login would give; each provider's entry alone says what a test uses.
LOGIN_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)


def opencode_config(model: str, base_url: str, key_variable: str) -> dict:
    """OpenCode's and Kilo's config of the test (OPENCODE_CONFIG, KILO_CONFIG): the model,
    and for `endpoint/<id>` the OpenAI-compatible provider it names at `base_url`, with the
    key as a reference to `key_variable` ({env:...}, which both expand). LADO's own config of
    each agent goes on top and keeps both."""
    config: dict = {"model": model}
    provider, _, name = model.partition("/")
    if provider == ENDPOINT_PROVIDER:
        config["provider"] = {
            provider: {
                "npm": "@ai-sdk/openai-compatible",
                "name": "the live endpoint",
                "options": {"baseURL": base_url, "apiKey": f"{{env:{key_variable}}}"},
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


def codex_config(model: str, base_url: str, env_key: str) -> str:
    """The user's Codex config of the test, which LADO carries into each agent's own
    (providers/codex.py, CARRIED): the model at a Responses endpoint, its key read from the
    variable `env_key`."""
    provider = {"name": ENDPOINT_PROVIDER, "base_url": base_url, "wire_api": "responses"}
    provider["env_key"] = env_key
    return toml_text(
        {
            "model": model,
            "model_provider": ENDPOINT_PROVIDER,
            "model_providers": {ENDPOINT_PROVIDER: provider},
        }
    )


def endpoint() -> str | None:
    """The endpoint's base URL, or None: the live tests skip."""
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
    if not endpoint():
        return f"no model to run on: set {ENDPOINT}, {API_KEY} and {ENDPOINT_MODEL}"
    if not endpoint_model(provider):
        own = MODEL_VARIABLES[provider]
        return f"{ENDPOINT} has no default model: set {ENDPOINT_MODEL} (or {own})"
    if not os.environ.get(API_KEY):
        return f"{ENDPOINT} is set without its key: set {API_KEY}"
    return None


def _claude(model: str, folder: Path) -> dict[str, str]:
    """Claude Code at the endpoint without its /v1, the key as a value: it has no reference
    to a variable. A token, not ANTHROPIC_API_KEY: it takes that for Anthropic's own, and one
    it has not seen is a question."""
    return {
        "ANTHROPIC_BASE_URL": endpoint().removesuffix("/v1"),
        "ANTHROPIC_AUTH_TOKEN": os.environ[API_KEY],
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,  # its background calls name a haiku of their own
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def _codex(model: str, folder: Path) -> dict[str, str]:
    """`folder` is the test's CODEX_HOME."""
    (folder / "config.toml").write_text(codex_config(model, endpoint(), API_KEY))
    return {}


def _opencode_family(provider: str):
    def setup(model: str, folder: Path) -> dict[str, str]:
        path = folder / f"{provider}-config.json"
        path.write_text(json.dumps(opencode_config(model, endpoint(), API_KEY)))
        return {CONFIG_VARIABLES[provider]: str(path)}

    return setup


# One entry per provider, its whole setup on the endpoint: (model, folder) -> the variables to
# set. A new CLI is an entry here, a pin in scripts/smoke_ci.py and a line in live.yml's matrix.
SETUPS = {
    "claude": _claude,
    "codex": _codex,
    "kilo": _opencode_family("kilo"),
    "opencode": _opencode_family("opencode"),
}
