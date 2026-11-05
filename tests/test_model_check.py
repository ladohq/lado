"""The check of a session's model against its CLI's aliases and own list (lado.model_check),
and each provider's list (Provider.model_list) from recorded outputs of its CLI."""

import json
import os
import sys

import pytest

from lado import model_check, providers
from lado.providers import base

# `codex debug models --bundled` of Codex CLI 0.162.0, cut to what LADO reads.
CODEX_BUNDLED = {
    "models": [
        {"slug": "gpt-6-sol", "display_name": "GPT-6-Sol"},
        {"slug": "gpt-5.6-sol", "display_name": "GPT-5.6-Sol"},
    ]
}
# The account's catalogue Codex caches in its home, cut the same way.
CODEX_CACHE = {"fetched_at": "2026-11-01T10:00:00Z", "models": [{"slug": "gpt-6-luna"}]}


@pytest.fixture
def clis(tmp_path):
    """A folder for stand-ins of the CLIs, and the agents' environment that has it on PATH
    (and nothing else of the user's)."""
    folder = tmp_path / "bin"
    folder.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = {"PATH": f"{folder}{os.pathsep}/usr/bin:/bin", "HOME": str(home)}
    return folder, env


def _cli(folder, name, out="", code=0, sleep=0):
    """A stand-in CLI that prints `out` and exits with `code`, after `sleep` seconds."""
    script = folder / name
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys, time\n"
        f"time.sleep({sleep})\n"
        f"sys.stdout.write({out!r})\n"
        f"sys.stderr.write('no network\\n' if {code} else '')\n"
        f"sys.exit({code})\n"
    )
    script.chmod(0o755)
    return script


def test_claude_has_its_aliases_and_no_list(clis):
    listed = providers.get("claude").model_list(clis[1])
    assert "opus" in listed.aliases and "sonnet[1m]" in listed.aliases
    assert listed.models is None
    assert listed.why == "Claude Code gives no list of models beyond its aliases"


def test_codex_lists_its_bundled_catalogue_and_the_account_s(clis):
    folder, env = clis
    _cli(folder, "codex", json.dumps(CODEX_BUNDLED))
    cache = folder.parent / "home" / ".codex" / "models_cache.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps(CODEX_CACHE))
    listed = providers.get("codex").model_list(env)
    assert listed.aliases == ()
    assert listed.models == ("gpt-6-sol", "gpt-5.6-sol", "gpt-6-luna")
    assert listed.command == "codex debug models"


def test_codex_without_the_account_s_cache_lists_the_bundled_one(clis):
    folder, env = clis
    _cli(folder, "codex", json.dumps(CODEX_BUNDLED))
    (folder.parent / "home" / ".codex").mkdir()
    (folder.parent / "home" / ".codex" / "models_cache.json").write_text("not json")
    assert providers.get("codex").model_list(env).models == ("gpt-6-sol", "gpt-5.6-sol")


def test_codex_on_another_model_provider_has_no_list(clis):
    folder, env = clis
    _cli(folder, "codex", json.dumps(CODEX_BUNDLED))
    config = folder.parent / "home" / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text('model_provider = "ollama"\n')
    listed = providers.get("codex").model_list(env)
    assert listed.models is None
    assert listed.why == "Codex CLI gives no list of models for the model provider `ollama`"
    assert listed.fixed is True


@pytest.mark.parametrize(
    ("out", "code", "why"),
    [
        ("", 1, "`codex debug models --bundled` failed: no network"),
        ("[1, 2]", 0, "`codex debug models --bundled` printed no list LADO can read"),
        ("{", 0, "`codex debug models --bundled` printed no list LADO can read"),
    ],
)
def test_codex_s_failing_command_gives_no_list(clis, out, code, why):
    folder, env = clis
    _cli(folder, "codex", out, code)
    listed = providers.get("codex").model_list(env)
    assert (listed.models, listed.why) == (None, why)


@pytest.mark.parametrize("name", ["opencode", "kilo"])
def test_the_opencode_family_lists_its_models_command(clis, name):
    folder, env = clis
    _cli(folder, name, "opencode/big-pickle\n\nanthropic/claude-sonnet-5-5\n")
    listed = providers.get(name).model_list(env)
    assert listed.models == ("opencode/big-pickle", "anthropic/claude-sonnet-5-5")
    assert listed.command == f"{name} models"


def test_a_list_command_over_its_time_gives_no_list(clis, monkeypatch):
    folder, env = clis
    monkeypatch.setattr(base, "MODEL_LIST_TIMEOUT", 0.3)
    _cli(folder, "kilo", "kilo/x\n", sleep=5)
    listed = providers.get("kilo").model_list(env)
    assert listed.models is None
    assert listed.why == "`kilo models` timed out after 0.3 s"


def test_a_cli_not_on_the_path_gives_no_list(clis):
    listed = providers.get("opencode").model_list(clis[1])
    assert (listed.models, listed.why) == (None, "`opencode` is not on the agents' PATH")


class _Listed(base.Provider):
    """A provider whose list is given: model_check alone."""

    name, title, command, install_hint = "listed", "Listed CLI", "listed", ""
    permission_modes = ()

    def __init__(self, listed):
        self.listed = listed

    def launch_command(self, agent, session, spec, notice=None):
        raise NotImplementedError

    def parse_event(self, native, payload):
        return None

    def model_list(self, env):
        return self.listed


LISTED = base.ModelList(("fast",), ("big-1", "small-1"), "listed models")


@pytest.mark.parametrize(
    ("listed", "model", "kind", "text"),
    [
        (
            LISTED,
            "",
            "default",
            "empty: Listed CLI's default model; type or pick one of its models",
        ),
        (LISTED, "fast", "ok", "an alias of Listed CLI"),
        (LISTED, "big-1", "ok", "in Listed CLI's list of models"),
        (
            LISTED,
            "big-9",
            "refused",
            "big-9 is not in Listed CLI's list of models; listed models prints the list",
        ),
        (
            base.ModelList(("fast",), None, why="Listed CLI gives no list"),
            "big-9",
            "warn",
            "Listed CLI gives no list: LADO cannot check big-9; a wrong name stops its agents "
            "at their first turn",
        ),
    ],
)
def test_the_check_s_verdicts(listed, model, kind, text):
    verdict = model_check.check(_Listed(listed), model, {})
    assert (verdict.kind, verdict.text) == (kind, text)


def test_a_verdict_names_whose_list_it_is():
    """A server's list: the texts name the server, not the CLI."""
    provider = _Listed(LISTED)
    found = model_check.verdict(provider, "big-1", LISTED, whose="LM Studio дома")
    assert found.text == "in LM Studio дома's list of models"
    refused = model_check.verdict(provider, "big-9", LISTED, whose="LM Studio дома")
    assert refused.text == (
        "big-9 is not in LM Studio дома's list of models; listed models prints the list"
    )
    assert model_check.verdict(provider, "fast", LISTED, whose="x").text == "an alias of Listed CLI"


def test_the_check_lists_nothing_for_an_empty_model():
    class _Unlisted(_Listed):
        def model_list(self, env):
            raise AssertionError("no list for an empty model")

    assert model_check.check(_Unlisted(LISTED), "", {}).kind == model_check.DEFAULT


def test_a_provider_without_a_list_warns():
    class _Plain(_Listed):
        model_list = base.Provider.model_list

    verdict = model_check.check(_Plain(LISTED), "x", {})
    assert verdict.kind == model_check.WARN
    assert verdict.text.startswith("LADO knows no list of this CLI's models: LADO cannot check x")
