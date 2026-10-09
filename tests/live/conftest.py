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
the dialog like the human would (see test_live.answer_dialogs): Claude Code keeps one entry for it.

A failed test keeps its evidence in a folder under EVIDENCE, named in the failure report.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo, refuse_unless_isolated

from lado import providers
from lado.providers import base
from lado.providers.claude import ClaudeProvider
from lado.providers.codex import CodexProvider
from lado.providers.kilo import KiloProvider
from lado.providers.opencode import OpenCodeProvider

MODELS = {
    "claude": os.environ.get("LADO_LIVE_CLAUDE_MODEL") or "haiku",
    "kilo": os.environ.get("LADO_LIVE_KILO_MODEL") or "kilo/kilo-auto/free",
    "opencode": os.environ.get("LADO_LIVE_OPENCODE_MODEL") or "opencode/nemotron-3-ultra-free",
    "codex": os.environ.get("LADO_LIVE_CODEX_MODEL") or "qwen3-coder:30b",
}


def with_model(provider_class: type[base.Provider], model: str) -> base.Provider:
    """The provider, with `--model` added to its agents' argv.

    LADO has no model option yet; this is test-only. Hooks run in their own processes and
    look up the real provider by name, which parses events the same way.
    """

    class WithModel(provider_class):
        def launch_command(self, *args, **kwargs) -> base.Launch:
            launch = super().launch_command(*args, **kwargs)
            argv = [launch.argv[0], "--model", self.model, *launch.argv[1:]]
            return base.Launch(argv, launch.env, launch.warnings)

    provider = WithModel()
    provider.model = model  # also for checks that run the CLI themselves
    return provider


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


CLASSES = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "kilo": KiloProvider,
    "opencode": OpenCodeProvider,
}
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
        # agent asks (test_live.answer_dialogs). Not `--oss`: in a new home that shows
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


EVIDENCE = Path(tempfile.gettempdir(), "lado-live-evidence")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """When a live test fails, keep what shows why (agent_helpers.keep_evidence) in a folder
    of its own under EVIDENCE, before teardown kills its tmux server and removes its LADO
    home, and name the folder in the failure report. A passing test keeps nothing."""
    outcome = yield
    report = outcome.get_result()
    if not report.failed or report.when == "teardown":
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = EVIDENCE / f"{stamp}-{re.sub(r'[^A-Za-z0-9_.-]', '_', item.name)}"
    try:
        agent_helpers.keep_evidence(item.module.SESSION, folder)
        kept = f"kept in {folder}"
    except Exception as exc:  # the test's own failure must still be reported
        kept = f"could not keep it in {folder}: {exc!r}"
    report.sections.append(("LADO evidence", kept))


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"  # a tmux server of its own for each test
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    refuse_unless_isolated()
    yield
    kill_tmux_server(socket)
