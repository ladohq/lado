"""The live tests' setup on their endpoint (tests/live_models.py): no model, no network."""

import json
import sys

import live_models
import pytest

from lado import providers

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ENDPOINT = "http://gateway.test:4000/v1"
SECRET = "sk-the-human-s-secret-value"
MODEL = "qwen/qwen3.6-35b-a3b"


@pytest.fixture
def endpoint_env(monkeypatch):
    for name in [*live_models.MODEL_VARIABLES.values(), live_models.ENDPOINT_MODEL]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(live_models.ENDPOINT, f"{ENDPOINT}/")
    monkeypatch.setenv(live_models.API_KEY, SECRET)
    monkeypatch.setenv(live_models.ENDPOINT_MODEL, MODEL)


def written(folder):
    return {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_every_provider_has_an_entry():
    assert sorted(live_models.SETUPS) == sorted(providers.names())
    assert sorted(live_models.MODEL_VARIABLES) == sorted(providers.names())


@pytest.mark.parametrize("provider", sorted(live_models.SETUPS))
def test_without_an_endpoint_the_tests_name_what_to_set(monkeypatch, provider):
    monkeypatch.delenv(live_models.ENDPOINT, raising=False)
    assert live_models.endpoint() is None
    problem = live_models.endpoint_problem(provider)
    for variable in (live_models.ENDPOINT, live_models.API_KEY, live_models.ENDPOINT_MODEL):
        assert variable in problem


def test_the_opencode_config_of_another_provider_has_only_the_model():
    config = live_models.opencode_config("opencode/big-pickle", ENDPOINT, live_models.API_KEY)
    assert config == {"model": "opencode/big-pickle"}


@pytest.mark.parametrize("provider", ["opencode", "kilo"])
def test_opencode_and_kilo_reach_the_endpoint_with_the_key_by_reference(
    endpoint_env, tmp_path, provider
):
    assert live_models.endpoint() == ENDPOINT
    assert live_models.endpoint_problem(provider) is None
    model = live_models.endpoint_model(provider)
    assert model == f"endpoint/{MODEL}"
    variables = live_models.SETUPS[provider](model, tmp_path)
    [(name, path)] = variables.items()
    assert name == live_models.CONFIG_VARIABLES[provider]
    config = json.loads(open(path).read())
    assert config["model"] == model
    endpoint = config["provider"]["endpoint"]
    assert endpoint["npm"] == "@ai-sdk/openai-compatible"
    assert endpoint["options"] == {"baseURL": ENDPOINT, "apiKey": "{env:LADO_LIVE_API_KEY}"}
    entry = endpoint["models"][MODEL]
    assert entry["tool_call"] is True
    assert entry["modalities"]["input"] == ["text", "image"]
    assert entry["limit"]["context"] == 65536
    assert not [p for p, data in written(tmp_path).items() if SECRET.encode() in data]


def test_codex_reaches_the_endpoint_with_the_key_by_reference(endpoint_env, tmp_path):
    model = live_models.endpoint_model("codex")
    assert model == MODEL
    assert live_models.SETUPS["codex"](model, tmp_path) == {}
    config = tomllib.loads((tmp_path / "config.toml").read_text())
    assert config["model"] == model
    assert config["model_provider"] == "endpoint"
    assert config["model_providers"]["endpoint"] == {
        "name": "endpoint",
        "base_url": ENDPOINT,
        "wire_api": "responses",
        "env_key": "LADO_LIVE_API_KEY",
    }
    assert not [p for p, data in written(tmp_path).items() if SECRET.encode() in data]


def test_claude_code_s_entry_gives_only_variables(endpoint_env, tmp_path):
    model = "anthropic/claude-haiku-5.5"
    assert live_models.SETUPS["claude"](model, tmp_path) == {
        "ANTHROPIC_BASE_URL": ENDPOINT.removesuffix("/v1"),
        "ANTHROPIC_AUTH_TOKEN": SECRET,
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    assert written(tmp_path) == {}


def test_a_cli_s_own_model_wins_over_the_endpoint_s(endpoint_env, monkeypatch):
    monkeypatch.setenv("LADO_LIVE_KILO_MODEL", "endpoint/google/gemma-4-26b-a4b")
    assert live_models.endpoint_model("kilo") == "endpoint/google/gemma-4-26b-a4b"
    assert live_models.endpoint_model("opencode") == f"endpoint/{MODEL}"


def test_an_endpoint_without_a_model_or_a_key_is_a_skip_reason(endpoint_env, monkeypatch):
    monkeypatch.delenv(live_models.ENDPOINT_MODEL)
    assert "LADO_LIVE_MODEL" in live_models.endpoint_problem("codex")
    monkeypatch.setenv("LADO_LIVE_CODEX_MODEL", MODEL)
    assert live_models.endpoint_problem("codex") is None
    monkeypatch.delenv(live_models.API_KEY)
    problem = live_models.endpoint_problem("codex")
    assert "LADO_LIVE_API_KEY" in problem and SECRET not in problem
