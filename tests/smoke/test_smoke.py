"""The smoke scenario, the same for each provider: real CLI, real tmux, hooks, `lado mcp` and
SQLite, no model (tests/smoke/conftest.py). It shows that a session starts, the CLI's hooks
run, LADO's messages reach it, a worker starts, and `lado stop` leaves no process."""

import json
import os
import sys
from pathlib import Path

import agent_helpers
import pytest
from real_clis import agent_processes, answer_dialogs, check_gone, status

from lado import logins, loop, projects, providers, runtime, state, tmux

pytestmark = pytest.mark.smoke

SESSION = "smoke"
RECEIVED = (state.DELIVERED, state.READ)
HUMAN_SAYS = "Smoke test: a line from the human\nwith a body to read"
TASK = "Smoke test: no model answers; this task only has to reach you."
# Codex CLI 0.162 runs no hook for a turn that ends on an API error: the agent stays busy,
# so nothing more is handed over to it, and no turn_error is recorded.
CODEX_GAP = "A Codex agent whose turn ends on a model or API error stays busy"


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def answering(provider: str, agent: str, check, session: str = SESSION):
    """`check` for wait_for, answering the agent's trust dialog first (each Codex agent has a
    home of its own, so it asks about its folder)."""

    def answered():
        answer_dialogs(provider, session, agent)
        return check()

    return answered


def message(sender: str, recipient: str, summary: str) -> state.Message:
    [found] = [
        m
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient, m.summary) == (sender, recipient, summary)
    ]
    return found


def delivered(sender: str, recipient: str, summary: str):
    """A check that the message is delivered: the agent's own prompt-submit hook or plugin
    saw its line."""
    return lambda: message(sender, recipient, summary).state in RECEIVED


def events(agent: str, kind: str) -> list[state.Event]:
    return [e for e in state.list_events(SESSION) if (e.agent, e.kind) == (agent, kind)]


def test_a_session_starts_takes_messages_and_stops(smoke_repo, smoke_provider, fake_endpoint):
    provider = smoke_provider

    # 1. The session starts: its window, the agents' environment and PATH, the CLI.
    started = runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", provider)
    print(f"{provider}: started, warnings {started.warnings}")
    if provider == "claude":
        # The smoke's config trusted no folder: LADO recorded the repo's trust, so the CLI
        # starts without the question (answer_dialogs fails if it asks).
        config = Path(os.environ["CLAUDE_CONFIG_DIR"], ".claude.json")
        repo = str(smoke_repo.resolve())
        assert json.loads(config.read_text())["projects"][repo] == {"hasTrustDialogAccepted": True}
        assert f"LADO recorded Claude Code's trust in {repo} in {config}" in started.warnings

    # 2. The supervisor's session-start hook ran: it is idle. Codex starts its session only
    # on its first input, LADO's FIRST_INPUT, which its prompt-submit hook confirms.
    if provider == "codex":
        print(f"codex: the session starts on its first input; then: {CODEX_GAP} (BACKLOG)")
        first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
        wait_for(answering(provider, "supervisor", first), "codex's first input delivered", 120)
    else:
        idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
        wait_for(idle, "the supervisor to be idle after its session start", 120)
    assert loop.running(SESSION)

    # 3. The CLI listed LADO's MCP tools.
    wait_for(lambda: events("supervisor", state.MCP_READY), "the supervisor's mcp_ready", 60)

    # 4. A message with a body reaches the supervisor through its own hook, and its turn
    # fails at the endpoint: a turn's end with an error. Not Codex (above).
    if provider != "codex":
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        summary = HUMAN_SAYS.splitlines()[0]
        wait_for(delivered(state.HUMAN, "supervisor", summary), "the human's message", 120)
        wait_for(lambda: events("supervisor", state.TURN_ERROR), "the supervisor's turn_error", 120)
        print(f"{provider}: turn_error {events('supervisor', state.TURN_ERROR)[0].detail!r}")
    # Codex posts its first request after its prompt-submit hook confirmed the input, so the
    # confirmation can come first; for the others the turn_error above came after it.
    wait_for(lambda: fake_endpoint.requests, "the supervisor's turn at the endpoint", 120)
    asked = len(fake_endpoint.requests)

    # 5. A worker: its worktree, a second agent, its hooks; its task reaches it.
    worker = runtime.spawn_worker(SESSION, TASK, name="w1")
    task = delivered(state.LADO, "w1", "your task")
    wait_for(answering(provider, "w1", task), "w1's task delivered", 120)
    wait_for(lambda: len(fake_endpoint.requests) > asked, "w1's turn at the endpoint", 120)
    assert worker.cwd and worker.branch
    print(f"{provider}: requests at the endpoint {fake_endpoint.requests}")

    # 6. lado stop: the windows, the loop and every process go.
    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "stop")
    wait_for(lambda: not loop.running(SESSION), "the session loop to end", 5 * loop.INTERVAL)
    agent_helpers.check_loop_ended_by_stop(SESSION)


PROBE = Path(__file__).with_name("probe_mcp.py")
PROBE_VALUE = "smoke-project-value=1 ü"
PROBE_SECRET = "smoke-project-secret=2 ü"


def test_a_kits_mcp_server_sees_the_project_s_variable(
    smoke_provider, tmp_path, monkeypatch, git_config
):
    """The project's variable and secret, set nowhere else, reach a kit's MCP server that
    the real CLI starts for a worker of a session in the project: through the kit's ${NAME}
    (lado.mcp_exec) and, the variable, in the server's own environment."""
    provider = smoke_provider
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("SMOKE_PROBE_VALUE", raising=False)
    monkeypatch.delenv("SMOKE_PROBE_TOKEN", raising=False)
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    projects.set_variable("shop", "SMOKE_PROBE_VALUE", PROBE_VALUE)
    projects.set_secret("shop", "SMOKE_PROBE_TOKEN", PROBE_SECRET)
    out = tmp_path / "probe.json"
    kit = tmp_path / "kits" / "probe"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: probe\nversion: 1.0.0\n")
    server = {
        "command": [sys.executable, str(PROBE)],
        "env": {
            "PROBE_VALUE": "${SMOKE_PROBE_VALUE}",
            "PROBE_SECRET": "${SMOKE_PROBE_TOKEN}",
            "PROBE_OUT": str(out),
        },
    }
    front = {"name": "prober", "description": "probes", "mcp": {"probe": server}}
    (kit / "agents" / "prober.md").write_text(
        f"---\n{json.dumps(front)}\n---\nYou probe.\n"  # JSON is YAML
    )
    agent_helpers.install_kit(kit)

    session = "shop-frontend"
    runtime.start_session(
        None,
        None,
        "bypassPermissions",
        provider,
        ["default", "probe"],
        project="shop",
        repo_name="frontend",
    )
    if provider != "codex":  # Codex starts its session on its first input (above)
        idle = answering(
            provider, "supervisor", lambda: status(session, "supervisor") == "idle", session
        )
        agent_helpers.wait_for(idle, "the supervisor idle", session, 120, interval=0.5)
    runtime.spawn_worker(session, TASK, name="p1", role="prober")
    probed = answering(provider, "p1", out.exists, session)
    agent_helpers.wait_for(probed, "the probe's file", session, 120, interval=0.5)
    print(f"{provider}: the probe saw {out.read_text()}")
    assert json.loads(out.read_text()) == {
        "template": PROBE_VALUE,
        "inherited": PROBE_VALUE,
        "secret": PROBE_SECRET,
    }
    runtime.stop_session(session)


# Each CLI's own status command in a fresh home (openspec change provider-logins): what
# LADO's parser reads of the real CLI's output, at the tested version.
LOGINS = {
    # A token LADO's tests give it (ANTHROPIC_AUTH_TOKEN, "oauth_token" too); none: no login.
    "claude": (("yes", "token", "ANTHROPIC_AUTH_TOKEN"), "no"),
    "codex": (None, "no"),
    "kilo": (None, "no"),
    "opencode": (None, "no"),
}


def test_each_clis_login_is_read_from_its_own_command(smoke_provider, tmp_path, monkeypatch):
    provider = providers.get(smoke_provider)
    given, none = LOGINS[smoke_provider]
    if given:
        found = provider.login_status(logins.environment())
        print(f"{smoke_provider}: {found}")
        assert (found.state, found.method, found.variable) == given
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN")
    found = provider.login_status(logins.environment())
    print(f"{smoke_provider}: without a login {found}")
    assert found.state == none, found.problem
    if smoke_provider in ("kilo", "opencode"):
        # A credential in the CLI's own file, and a key in the environment.
        data = Path(os.environ["XDG_DATA_HOME"]) / smoke_provider
        data.mkdir(parents=True, exist_ok=True)
        (data / "auth.json").write_text(json.dumps({"anthropic": {"type": "api", "key": "k"}}))
        monkeypatch.setenv("OPENAI_API_KEY", "smoke-key")
        found = provider.login_status(logins.environment())
        print(f"{smoke_provider}: with logins {found}")
        assert found.state == "yes"
        assert [(i.name, i.kind, i.variable) for i in found.items] == [
            ("Anthropic", "api", ""),
            ("OpenAI", "variable", "OPENAI_API_KEY"),
        ]


# Claude Code's only: a parameter, not a skip, since CI's smoke cell counts a skip as a
# failure (scripts/smoke_ci.py) and picks a provider's tests by `-k <provider>`.
@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_a_logged_in_agent_passes_the_clis_first_run_with_no_human(
    smoke_provider, smoke_repo, fake_endpoint
):
    """A fresh Claude Code config (no hasCompletedOnboarding: the theme screen would hold
    the agent before any hook): LADO records the first run, and the agent is idle."""
    config = Path(os.environ["CLAUDE_CONFIG_DIR"], ".claude.json")
    config.write_text(json.dumps({"bypassPermissionsModeAccepted": True}))
    started = runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", "claude")
    print(f"claude: started, warnings {started.warnings}")
    assert f"LADO recorded Claude Code's first run in {config}" in started.warnings
    assert json.loads(config.read_text())["hasCompletedOnboarding"] is True
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor idle with no human", 120)
    runtime.stop_session(SESSION)
