"""Live end-to-end tests: real agent CLIs and real models, short scenarios per provider.

Run them with `make test-live` (`PROVIDER=codex|opencode|kilo|claude`), or in CI by live.yml.
They never run by default. The endpoint, its key and the models come from the environment
every LADO process of the test inherits, each provider set up by its entry in
`live_models.SETUPS`; without them the tests skip and name what to set (docs/testing.md,
"Live tests").

Claude Code asks whether to trust a new workspace and keeps the answer in its config, here the
test's own (tests/conftest.py's claude_config); no option skips that, so LADO records the
trust of the session's repo there before it starts a Claude agent. If Claude Code asks all
the same, the test fails (see real_clis.answer_dialogs).

A failed test keeps its evidence in a folder under EVIDENCE, named in the failure report.
"""

import os
import shutil

import live_models
import pytest
import real_clis
from agent_helpers import init_repo
from real_clis import CLASSES, EVIDENCE, isolated  # noqa: F401 (fixture, names)

# The test model of each provider.
MODELS = {p: live_models.endpoint_model(p) for p in live_models.SETUPS}


@pytest.fixture(params=sorted(live_models.SETUPS))
def live_provider(request, monkeypatch, codex_home, tmp_path) -> str:
    """The name of a provider whose CLI is installed, set up on the endpoint with its test
    model and with nobody's login."""
    name = request.param
    if shutil.which(CLASSES[name].command) is None:
        pytest.skip(f"{CLASSES[name].command} not installed")
    if reason := live_models.endpoint_problem(name):
        pytest.skip(reason)
    for variable in real_clis.LOGIN_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    folder = codex_home if name == "codex" else tmp_path
    folder.mkdir(parents=True, exist_ok=True)
    for variable, value in live_models.SETUPS[name](MODELS[name], folder).items():
        monkeypatch.setenv(variable, value)
    # Kilo's and OpenCode's TUI takes the model an agent used last (<state>/<cli>/model.json)
    # over the config's (Kilo 7.8.8: the user's kilo-auto/free won): a state of the test's own,
    # where they record the model they use (test_live.check_models).
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return name


@pytest.fixture
def live_model(live_provider) -> str:
    """The test model of the provider, as its CLI gets it."""
    return MODELS[live_provider]


@pytest.fixture
def declared_vision(live_provider) -> None:
    """Skip, before any image is sent, a model that does not declare image input: whether it
    does is LADO_LIVE_IMAGE's to say."""
    declared = os.environ.get("LADO_LIVE_IMAGE")
    if declared is None:
        pytest.skip(
            f"whether {MODELS[live_provider]} takes images is unknown: set LADO_LIVE_IMAGE=1 or 0"
        )
    if declared != "1":
        pytest.skip(f"{MODELS[live_provider]} takes no images (LADO_LIVE_IMAGE={declared})")


@pytest.fixture
def live_repo(live_provider, tmp_path):
    return init_repo(tmp_path / "My Repo")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    real_clis.keep_evidence(item, outcome.get_result(), (os.environ.get(live_models.API_KEY, ""),))
