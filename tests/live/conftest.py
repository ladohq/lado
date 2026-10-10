"""Live end-to-end tests: real agent CLIs and real models, one short scenario per provider.

Run them with `uv run pytest -m live` (or `make test-live`, `make test-live PROVIDER=kilo`).
They cost tokens (Claude Code) or depend on free models (Kilo, OpenCode), so they never run by
default.

Environment:
- LADO_LIVE_CLAUDE_MODEL: model for Claude Code agents, default "haiku" (cheap and quick).
- LADO_LIVE_KILO_MODEL: model for Kilo agents, default "kilo/kilo-auto/free" (no login).
- LADO_LIVE_OPENCODE_MODEL: model for OpenCode agents, default "opencode/nemotron-3-ultra-free"
  (no login; "opencode/big-pickle" is often rate-limited).
- LADO_LIVE_CODEX_MODEL: a local Ollama model for Codex CLI agents, default "qwen3-coder:30b"
  (no login; the test skips without `ollama` or the model). It goes in the user's Codex
  config of the test (CODEX_HOME), which LADO carries into each agent's own.

Claude Code asks whether to trust a new workspace and records the answer in its own config;
no option skips that. So the Claude test always uses the same repo path, and the test answers
the dialog like the human would (see real_clis.answer_dialogs): Claude Code keeps one entry for it.

A failed test keeps its evidence in a folder under EVIDENCE, named in the failure report.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import real_clis
from agent_helpers import init_repo
from real_clis import CLASSES, EVIDENCE, isolated, with_model  # noqa: F401 (fixture, names)

from lado import providers

MODELS = {
    "claude": os.environ.get("LADO_LIVE_CLAUDE_MODEL") or "haiku",
    "kilo": os.environ.get("LADO_LIVE_KILO_MODEL") or "kilo/kilo-auto/free",
    "opencode": os.environ.get("LADO_LIVE_OPENCODE_MODEL") or "opencode/nemotron-3-ultra-free",
    "codex": os.environ.get("LADO_LIVE_CODEX_MODEL") or "qwen3-coder:30b",
}


def _claude_unusable() -> str | None:
    result = subprocess.run(
        ["claude", "auth", "status"], capture_output=True, text=True, check=False
    )
    try:
        logged_in = json.loads(result.stdout).get("loggedIn")
    except ValueError:
        logged_in = False
    return None if logged_in else "Claude Code is not logged in (`claude auth status`)"


def _codex_unusable() -> str | None:
    if shutil.which("ollama") is None:
        return "ollama not installed (Codex CLI runs on a local model)"
    listed = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=False)
    names = [line.split()[0] for line in listed.stdout.splitlines()[1:] if line.split()]
    if MODELS["codex"] not in names:
        return f"ollama has no {MODELS['codex']} (`ollama pull {MODELS['codex']}`)"
    return None


# Kilo's and OpenCode's free models need no login, nor does Codex on a local model.
UNUSABLE = {
    "claude": _claude_unusable,
    "codex": _codex_unusable,
    "kilo": lambda: None,
    "opencode": lambda: None,
}


@pytest.fixture(params=["claude", "codex", "kilo", "opencode"])
def live_provider(request, monkeypatch, codex_home) -> str:
    """The name of a provider whose CLI is installed and usable, set up with its test model."""
    name = request.param
    if shutil.which(CLASSES[name].command) is None:
        pytest.skip(f"{CLASSES[name].command} not installed")
    if reason := UNUSABLE[name]():
        pytest.skip(reason)
    monkeypatch.setitem(providers._PROVIDERS, name, with_model(CLASSES[name], MODELS[name]))
    if name == "codex":
        # The user's Codex config of the test, which LADO carries into each agent's own: the
        # model's provider, as a user of a local model has it. It trusts no folder, so each
        # agent asks (real_clis.answer_dialogs). Not `--oss`: in a new home that shows
        # Codex's login screen (0.162.0).
        codex_home.mkdir(parents=True, exist_ok=True)
        (codex_home / "config.toml").write_text('model_provider = "ollama"\n')
    return name


CLAUDE_REPO = Path(tempfile.gettempdir(), "lado-live-claude", "My Repo")


@pytest.fixture
def live_repo(live_provider, tmp_path):
    if live_provider != "claude":
        yield init_repo(tmp_path / "My Repo")
        return
    shutil.rmtree(CLAUDE_REPO.parent, ignore_errors=True)
    yield init_repo(CLAUDE_REPO)
    shutil.rmtree(CLAUDE_REPO.parent, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    real_clis.keep_evidence(item, outcome.get_result())
