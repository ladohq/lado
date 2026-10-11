"""Live end-to-end tests: real agent CLIs and real models, short scenarios per provider.

Run them with `make test-live` (`PROVIDER=codex|opencode|kilo|claude`). They never run by
default. The models, the local setup (LM Studio, the bridge the Codex tests start), the
variables that override them and why a test skips are in AGENTS.md (Commands, "Live tests").
In short: Codex, OpenCode and Kilo run on LM Studio's `local_models.MODEL`, one source of
the model per provider in the environment every LADO process of the test inherits; Claude
Code on haiku (`--model`), paid: only with the human's yes.

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

import local_models
import pytest
import real_clis
from agent_helpers import init_repo
from real_clis import CLASSES, EVIDENCE, isolated, with_model  # noqa: F401 (fixture, names)

from lado import providers

# A remote endpoint (LADO_LIVE_ENDPOINT) for Codex, OpenCode and Kilo instead of LM Studio:
# no LM Studio check and no bridge; its key only in the environment (local_models).
ENDPOINT = local_models.endpoint()
LOCAL = f"lmstudio/{local_models.MODEL}"  # OpenCode and Kilo name LM Studio's so
# The test model of each provider.
MODELS = {
    "claude": os.environ.get("LADO_LIVE_CLAUDE_MODEL") or "haiku",
    **{
        p: local_models.endpoint_model(p)
        if ENDPOINT
        else os.environ.get(local_models.MODEL_VARIABLES[p]) or default
        for p, default in (("codex", local_models.MODEL), ("kilo", LOCAL), ("opencode", LOCAL))
    },
}
# Another Responses endpoint for Codex alone: no bridge, no LM Studio check.
CODEX_BASE_URL = os.environ.get("LADO_LIVE_CODEX_BASE_URL")
BRIDGE_KEY = "LADO_LIVE_BRIDGE_KEY"  # the variable Codex reads the bridge's key from
CONFIG_VARIABLES = local_models.CONFIG_VARIABLES


def lmstudio_model(provider: str) -> str | None:
    """The LM Studio model id the provider's test model is, or None for another endpoint."""
    model = MODELS[provider]
    if ENDPOINT:
        return None
    if provider == "codex":
        return None if CODEX_BASE_URL else model
    if provider in CONFIG_VARIABLES and model.startswith("lmstudio/"):
        return model.split("/", 1)[1]
    return None


def _claude_unusable() -> str | None:
    result = subprocess.run(
        ["claude", "auth", "status"], capture_output=True, text=True, check=False
    )
    try:
        logged_in = json.loads(result.stdout).get("loggedIn")
    except ValueError:
        logged_in = False
    return None if logged_in else "Claude Code is not logged in (`claude auth status`)"


def _local_unusable(provider: str) -> str | None:
    if ENDPOINT:
        return local_models.endpoint_problem(provider)
    model = lmstudio_model(provider)
    return local_models.lmstudio_problem(model, local_models.lmstudio_url()) if model else None


UNUSABLE = {
    "claude": _claude_unusable,
    "codex": lambda: _local_unusable("codex"),
    "kilo": lambda: _local_unusable("kilo"),
    "opencode": lambda: _local_unusable("opencode"),
}


@pytest.fixture(scope="session")
def codex_bridge(tmp_path_factory):
    """The LiteLLM bridge Codex reaches LM Studio through, once per test run."""
    if shutil.which("uvx") is None:
        pytest.skip("uvx not installed: Codex reaches LM Studio through a LiteLLM bridge it runs")
    folder = tmp_path_factory.mktemp("bridge")
    try:
        bridge = local_models.Bridge.start(folder, local_models.lmstudio_url(), MODELS["codex"])
    except local_models.BridgeError as error:
        pytest.fail(str(error))
    BRIDGES.append(bridge)
    yield bridge
    bridge.stop()


BRIDGES: list[local_models.Bridge] = []  # its log goes with a failed test's evidence


@pytest.fixture(params=["claude", "codex", "kilo", "opencode"])
def live_provider(request, monkeypatch, codex_home, tmp_path) -> str:
    """The name of a provider whose CLI is installed and usable, set up with its test model."""
    name = request.param
    if shutil.which(CLASSES[name].command) is None:
        pytest.skip(f"{CLASSES[name].command} not installed")
    if reason := UNUSABLE[name]():
        pytest.skip(reason)
    if name == "claude":
        monkeypatch.setitem(providers._PROVIDERS, name, with_model(CLASSES[name], MODELS[name]))
    elif ENDPOINT:
        folder = codex_home if name == "codex" else tmp_path
        folder.mkdir(parents=True, exist_ok=True)
        for variable, value in local_models.write_endpoint_config(
            name, MODELS[name], folder
        ).items():
            monkeypatch.setenv(variable, value)
    elif name == "codex":
        # The user's Codex config of the test, which LADO carries into each agent's own. It
        # trusts no folder, so each agent asks (real_clis.answer_dialogs).
        base_url, key = CODEX_BASE_URL, None
        if not base_url:
            bridge = request.getfixturevalue("codex_bridge")
            base_url, key = bridge.base_url, BRIDGE_KEY
            monkeypatch.setenv(BRIDGE_KEY, bridge.key)
        codex_home.mkdir(parents=True, exist_ok=True)
        config = local_models.codex_config(MODELS[name], base_url, key)
        (codex_home / "config.toml").write_text(config)
    else:
        config = tmp_path / f"{name}-config.json"
        config.write_text(
            json.dumps(local_models.opencode_config(MODELS[name], local_models.lmstudio_url()))
        )
        monkeypatch.setenv(CONFIG_VARIABLES[name], str(config))
    if name in CONFIG_VARIABLES:
        # Their TUI takes the model an agent used last (<state>/<cli>/model.json) over the
        # config's (Kilo 7.8.8: the user's kilo-auto/free won): a state of the test's own,
        # where they record the model they use (test_live.check_models).
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return name


@pytest.fixture
def live_model(live_provider) -> str:
    """The test model of the provider, as its CLI gets it."""
    return MODELS[live_provider]


@pytest.fixture
def declared_vision(live_provider) -> None:
    """Skip, before any image is sent, a model that does not declare image input: Claude's
    models do, an LM Studio model when LM Studio lists it as `vlm`, another endpoint's when
    LADO_LIVE_IMAGE=1."""
    if live_provider == "claude":
        return
    if model := lmstudio_model(live_provider):
        if not local_models.lmstudio_sees_images(model, local_models.lmstudio_url()):
            pytest.skip(f"LM Studio does not list {model} as a vision model (type vlm)")
        return
    declared = os.environ.get("LADO_LIVE_IMAGE")
    if declared is None:
        pytest.skip(
            f"whether {MODELS[live_provider]} takes images is unknown: set LADO_LIVE_IMAGE=1 or 0"
        )
    if declared != "1":
        pytest.skip(f"{MODELS[live_provider]} takes no images (LADO_LIVE_IMAGE={declared})")


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
    real_clis.keep_evidence(
        item,
        outcome.get_result(),
        tuple(b.log for b in BRIDGES),
        (os.environ.get(local_models.API_KEY, ""),),
    )
