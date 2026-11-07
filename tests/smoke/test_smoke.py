"""The smoke scenario, the same for each provider: real CLI, real tmux, hooks, `lado mcp` and
SQLite, no model (tests/smoke/conftest.py). It shows that a session starts, the CLI's hooks
run, LADO's messages reach it, a worker starts, and `lado stop` leaves no process."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import agent_helpers
import fake_endpoint as endpoints
import fake_model_server
import pytest
from real_clis import CLASSES, SANDBOX_ERROR, agent_processes, answer_dialogs, check_gone, status

from lado import logins, loop, model_settings, projects, providers, runtime, state, tmux
from lado.providers import codex, opencode_family

pytestmark = pytest.mark.smoke

SESSION = "smoke"
RECEIVED = (state.DELIVERED, state.READ)
HUMAN_SAYS = "Smoke test: a line from the human\nwith a body to read"
TASK = "Smoke test: no model answers; this task only has to reach you."
# Codex CLI 0.162 runs no hook for a turn that ends on an API error: on a built-in model the
# agent stays busy, so nothing more is handed over to it, and no turn_error is recorded.
CODEX_GAP = "A Codex agent on a built-in model whose turn ends on an API error stays busy"


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def answering(provider: str, agent: str, check, session: str = SESSION):
    """`check` for wait_for, failing first if the agent shows a trust dialog (LADO settles
    each CLI's before the agent starts)."""

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
        note = f"LADO recorded Claude Code's trust in {repo} in {config}"
        assert note not in started.warnings  # LADO's own write: loop.log only
        assert note in (state.home() / "loop.log").read_text()

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


# The session's model per CLI: one the endpoint serves (smoke/conftest.py). Claude Code's is
# a full name, which it gives no list for; Codex's model provider is the endpoint's, with no
# list either; OpenCode's and Kilo's is in their own `models` list.
SESSION_MODELS = {
    "claude": "claude-smoke-2",
    "codex": "smoke-model-2",
    "kilo": "smoke/smoke-model-2",
    "opencode": "smoke/smoke-model-2",
}


def test_the_session_s_model_reaches_the_cli(
    smoke_repo, smoke_provider, fake_endpoint, monkeypatch
):
    """`lado start --model`: the model is checked against the CLI, passed its own way (argv,
    config.toml, config content), and the CLI asks the endpoint for it."""
    provider = smoke_provider
    if provider in ("kilo", "opencode"):
        # The CLI itself, without the test's own --model (real_clis.with_model).
        monkeypatch.setitem(providers._PROVIDERS, provider, CLASSES[provider]())
    model = SESSION_MODELS[provider]
    started = runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", provider, model=model
    )
    print(f"{provider}: started, warnings {started.warnings}")
    checked = [w for w in started.warnings if "LADO cannot check" in w]
    assert bool(checked) == (provider in ("claude", "codex")), started.warnings
    agent = state.get_agent(SESSION, "supervisor")
    assert (agent.model, agent.model_source) == (model, state.SESSION)
    asked = model.removeprefix("smoke/")
    if provider == "codex":
        home = providers.base.config_path(agent)
        assert f'model = "{model}"' in (home / "config.toml").read_text().splitlines()
        first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
        wait_for(answering(provider, "supervisor", first), "codex's first input delivered", 120)
    else:
        idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
        wait_for(idle, "the supervisor to be idle after its session start", 120)
        runtime.write_as_human(SESSION, HUMAN_SAYS)
    wait_for(lambda: asked in fake_endpoint.models, f"a request for {asked}", 120)
    print(f"{provider}: models asked {fake_endpoint.models}")
    runtime.stop_session(SESSION)


SERVER_KEY = "smoke-claude-server-key"
SERVER_MODEL = "smoke-qwen"
CANARY = "smoke-canary-of-the-human"  # in each secret of the human's a test sets


@pytest.fixture
def claude_server(smoke_repo, tmp_path, monkeypatch):
    """A saved model server of Anthropic's API with the model `Шлюз Qwen` and a key, and every
    other way out of the machine refused: no request of the real CLI can reach a real host."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
        monkeypatch.setenv(name.lower(), "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = endpoints.Anthropic(SERVER_MODEL, tmp_path / "shell-ran", SERVER_KEY)
    model_settings.add_server("Шлюз", server.url, SERVER_KEY, warn=print, note=print)
    state.add_model("Шлюз Qwen", "claude", SERVER_MODEL, state.model_server("Шлюз").id)
    yield server
    server.close()


def turn_with_tools(server: endpoints.Anthropic) -> None:
    """The supervisor idle, then a turn in which the server has it run a shell and an MCP tool."""
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    runtime.write_as_human(SESSION, endpoints.RUN_TOOLS)
    wait_for(server.marker.exists, "the shell tool to run", 120)
    called = lambda: endpoints.MCP_CALL in server.tool_results()  # noqa: E731
    wait_for(called, "the MCP tool to run", 120)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the turn's end", 120)


def claude_output() -> int:
    """What a Claude agent on the fake's model may ask for: the context is known."""
    return providers.base.Limit(endpoints.CONTEXT).output_room()


def only_the_server_s_key_and_model(server: endpoints.Anthropic) -> None:
    turns = [r for r in server.requests if r[0] == "/v1/messages" and b'"model"' in r[2]]
    assert turns, "no turn reached the server"  # LADO's probe sends an empty object
    for path, headers, body in server.requests:
        print(f"claude: {path} {sorted(headers)}")
        assert CANARY not in json.dumps(headers) and CANARY.encode() not in body
        assert headers.get("x-api-key", SERVER_KEY) == SERVER_KEY
        assert headers.get("authorization", f"Bearer {SERVER_KEY}") == f"Bearer {SERVER_KEY}"
    assert {json.loads(body)["model"] for _, _, body in turns} == {SERVER_MODEL}
    assert [h for _, h, _ in turns if "x-api-key" not in h and "authorization" not in h] == []


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_claude_code_runs_on_a_server_with_no_login_and_no_first_run(
    smoke_repo, smoke_provider, claude_server, fake_endpoint, monkeypatch
):
    """Not logged in, and its first run not recorded: nothing holds the agent, and a turn with
    a shell and an MCP tool runs on the server alone."""
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN")
    config = Path(os.environ["CLAUDE_CONFIG_DIR"], ".claude.json")
    config.write_text("{}")
    started = runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    print(f"claude: started, warnings {started.warnings}")
    turn_with_tools(claude_server)
    agent = state.get_agent(SESSION, "supervisor")
    assert agent.model == SERVER_MODEL
    assert runtime.status_reasons(SESSION) == {}
    asked = {json.loads(b)["max_tokens"] for p, _, b in claude_server.requests if b'"model"' in b}
    assert asked == {claude_output()}
    assert delivered(state.HUMAN, "supervisor", endpoints.RUN_TOOLS)()
    only_the_server_s_key_and_model(claude_server)
    assert fake_endpoint.requests == []
    settings = (providers.base.config_path(agent) / "settings.json").read_text()
    assert SERVER_KEY not in settings
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_nothing_of_the_human_s_claude_reaches_a_server(
    smoke_repo, smoke_provider, claude_server, fake_endpoint, tmp_path, monkeypatch
):
    """A login file, a key in the environment, and user settings with a key's helper, a token
    and another address: the server gets its own key alone, and the other address nothing."""
    other = endpoints.Anthropic(SERVER_MODEL, tmp_path / "other-ran")
    home = Path(os.environ["CLAUDE_CONFIG_DIR"])
    login = {"accessToken": f"sk-ant-oat01-{CANARY}", "refreshToken": f"r-{CANARY}"}
    login |= {"expiresAt": 4102444800000, "scopes": ["user:inference"]}
    (home / ".credentials.json").write_text(json.dumps({"claudeAiOauth": login}))
    env = {"ANTHROPIC_AUTH_TOKEN": f"token-{CANARY}", "ANTHROPIC_BASE_URL": other.url}
    settings = {"apiKeyHelper": f"echo helper-{CANARY}", "env": env}
    (home / "settings.json").write_text(json.dumps(settings))
    monkeypatch.setenv("ANTHROPIC_API_KEY", f"sk-ant-api03-{CANARY}")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", f"shell-{CANARY}")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", f"oauth-{CANARY}")
    try:
        started = runtime.start_session(
            str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
        )
        print(f"claude: started, warnings {started.warnings}")
        turn_with_tools(claude_server)
        only_the_server_s_key_and_model(claude_server)
        assert other.requests == [] and fake_endpoint.requests == []
    finally:
        other.close()
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CLAUDE_CODE_USE_BEDROCK", "1"),
        ("CLAUDE_CODE_USE_MANTLE", "1"),
        ("ANTHROPIC_UNIX_SOCKET", "/nonexistent/smoke.sock"),
    ],
)
def test_another_way_out_in_the_environment_does_not_take_a_claude_agent_off_its_server(
    smoke_repo, smoke_provider, claude_server, monkeypatch, variable, value
):
    monkeypatch.setenv(variable, value)
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    turn_with_tools(claude_server)
    only_the_server_s_key_and_model(claude_server)
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_auto_mode_of_the_human_leaves_a_claude_agent_on_a_server_lado_s_tools(
    smoke_repo, smoke_provider, claude_server
):
    """Inherited from the user's settings. Its classifier asks the server's model, which gives it
    no usable answer here: LADO's tools do not go there, or the agent could not answer anyone."""
    settings = {"permissions": {"defaultMode": "auto"}}
    Path(os.environ["CLAUDE_CONFIG_DIR"], "settings.json").write_text(json.dumps(settings))
    runtime.start_session(str(smoke_repo), SESSION, None, "claude", model="Шлюз Qwen")
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    assert "auto mode on" in tmux.capture(SESSION, "supervisor")
    runtime.write_as_human(SESSION, endpoints.RUN_MCP)
    called = lambda: endpoints.MCP_CALL in claude_server.tool_results()  # noqa: E731
    wait_for(called, "the MCP tool's result", 120)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the turn's end", 120)
    assert "by auto mode" not in tmux.capture(SESSION, "supervisor")
    last = [r for r in claude_server.requests if b"tool_result" in r[2]][-1]
    assert b"auto mode" not in last[2].split(b"tool_result", 1)[1]
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_a_claude_agent_on_a_large_context_compacts_before_it_passes_it(
    smoke_repo, smoke_provider, claude_server, tmp_path
):
    """On a server that counts a request's input and max_tokens, as cloud.ru does, reads of 50 KB
    up to a compaction: the output of 32000 Claude Code would ask for passed 131072 there."""
    claude_server.context = 131072
    error = {"type": "invalid_request_error", "message": "Invalid request"}
    claude_server.over_context = (400, {"type": "error", "error": error})
    for n in range(12):
        file = tmp_path / f"part{n:02}.txt"
        file.write_text(f"line of notes {n}\n" * 3000)
        claude_server.reads.append(file)
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    runtime.write_as_human(SESSION, HUMAN_SAYS)
    done = lambda: claude_server.compactions == endpoints.COMPACTIONS  # noqa: E731
    wait_for(done, "its compactions", 240)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the turn's end", 120)
    asked = [
        (len(b) // endpoints.TOKEN_BYTES, json.loads(b))
        for _, _, b in claude_server.requests
        if b'"max_tokens"' in b
    ]
    peak = max(tokens + request["max_tokens"] for tokens, request in asked)
    print(f"claude: {claude_server.compactions} compactions, the peak of a request {peak}")
    assert peak <= claude_server.context
    assert events("supervisor", state.TURN_ERROR) == []
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_the_human_s_effort_does_not_reach_a_server(smoke_repo, smoke_provider, claude_server):
    """A server may refuse an effort: gpt-oss on cloud.ru answers 400 to the human's `xhigh`."""
    settings = Path(os.environ["CLAUDE_CONFIG_DIR"], "settings.json")
    settings.write_text(json.dumps({"effortLevel": "xhigh"}))
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    turn_with_tools(claude_server)
    turns = [json.loads(b) for p, _, b in claude_server.requests if b'"max_tokens"' in b]
    assert turns and [t for t in turns if "output_config" in t] == []
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_a_turn_of_a_large_prompt_ends_on_a_context_that_fits_it(
    smoke_repo, smoke_provider, claude_server
):
    """A human's own CLAUDE.md and rules brought a prompt to 45K tokens: with the 32000 tokens of
    output Claude Code asks for by itself that is over 64K, and the server ends the stream."""
    size = 22000 * endpoints.TOKEN_BYTES
    Path(os.environ["CLAUDE_CONFIG_DIR"], "CLAUDE.md").write_text("Be brief. " * (size // 10))
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    turn_with_tools(claude_server)
    turns = [r for r in claude_server.requests if r[0] == "/v1/messages" and b'"tools"' in r[2]]
    largest = max(len(body) for _, _, body in turns) // endpoints.TOKEN_BYTES
    print(f"claude: the largest prompt is about {largest} tokens")
    assert largest + 32000 > endpoints.CONTEXT
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_model_of_a_claude_agent_on_a_server_shows_its_model_alone(
    smoke_repo, smoke_provider, claude_server
):
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    tmux.send_text(SESSION, "supervisor", "/model")
    shown = lambda: "Default" in tmux.capture(SESSION, "supervisor")  # noqa: E731
    wait_for(shown, "/model's list", 30)
    screen = tmux.capture(SESSION, "supervisor")
    print(f"claude: /model shows\n{screen}")
    assert SERVER_MODEL in screen
    for name in ("Opus", "Sonnet", "Haiku", "Fable"):
        assert name not in screen
    runtime.stop_session(SESSION)


@pytest.fixture
def two_servers():
    """Two model servers of OpenAI's kind, each taking a key of its own, and saved."""
    found = []
    for name, key in (("first", "smoke-server-key-one"), ("second", "smoke-server-key-two")):
        server = fake_model_server.Server("all", key=key)
        found.append(server)
        model_settings.add_server(name, server.url, key, warn=print, note=print)
    yield found
    for server in found:
        server.close()


def chats(server: fake_model_server.Server) -> list[fake_model_server.Request]:
    return [
        r for r in server.requests if r.path == fake_model_server.CHAT and b"messages" in r.body
    ]


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
def test_an_agent_starts_from_the_user_s_memory_and_leaves_it_as_it_is(
    smoke_repo, smoke_provider, fake_endpoint, monkeypatch
):
    """The CLI's own settings: the agent asks for the model the user last picked, in the user's
    state folder, not for one of LADO's servers, and that file stays as it was."""
    provider = smoke_provider
    monkeypatch.setitem(providers._PROVIDERS, provider, CLASSES[provider]())
    pick = {"providerID": "smoke", "modelID": "smoke-model-2"}
    ours = {"providerID": "lado-gone", "modelID": "m1"}
    memory = Path(os.environ["XDG_STATE_HOME"], provider, "model.json")
    memory.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"recent": [ours, pick], "model": {"code": pick}, "favorite": []})
    memory.write_text(text)
    runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", provider, model="")
    agent = state.get_agent(SESSION, "supervisor")
    idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    runtime.write_as_human(SESSION, HUMAN_SAYS)
    wait_for(lambda: "smoke-model-2" in fake_endpoint.models, "a request for the user's pick", 120)
    own = providers.base.state_path(agent) / provider / "model.json"
    print(f"{provider}: the agent's state: {sorted(p.name for p in own.parent.iterdir())}")
    assert "lado-gone" not in own.read_text()
    runtime.stop_session(SESSION)
    assert memory.read_text() == text


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
@pytest.mark.parametrize("mode", ["bypassPermissions", "plan"])
def test_a_session_on_a_server_s_model_asks_it_with_its_key(
    smoke_repo, smoke_provider, two_servers, monkeypatch, mode
):
    """Both servers are in the agent's config beside the CLI's own models, under `--model` the
    CLI runs the session's, in each mode, and its server gets the key of its own."""
    provider = smoke_provider
    monkeypatch.setitem(providers._PROVIDERS, provider, CLASSES[provider]())
    for name in ("first", "second"):
        state.add_model(f"Модель {name}", provider, "m1", state.model_server(name).id)
    started = runtime.start_session(str(smoke_repo), SESSION, mode, provider, model="Модель first")
    print(f"{provider}: started, warnings {started.warnings}")
    agent = state.get_agent(SESSION, "supervisor")
    first = state.model_server("first")
    assert (agent.model, agent.model_source) == (f"lado-{first.id}/m1", state.SESSION)

    # Its servers alone: the whole config would run LADO's plugin, whose hooks are the agent's.
    config = providers.base.config_path(agent) / f"{provider}.json"
    servers = json.dumps({"provider": json.loads(config.read_text())["provider"]})
    env = {**os.environ, **CLASSES[provider]().env(config, servers)}
    listed = subprocess.run(
        [provider, "models"], env=env, capture_output=True, text=True, timeout=60
    ).stdout.split()
    for name in ("first", "second"):
        assert f"lado-{state.model_server(name).id}/m1" in listed
    assert "smoke/smoke-model" in listed  # the CLI's own stay

    idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)
    runtime.write_as_human(SESSION, HUMAN_SAYS)
    one, other = two_servers
    wait_for(lambda: chats(one), "a request to the session's server", 120)
    print(f"{provider}: asked {[r.path for r in one.requests]}")
    assert chats(one)[0].headers.get("Authorization") == "Bearer smoke-server-key-one"
    assert json.loads(chats(one)[0].body)["model"] == "m1"
    assert chats(other) == []
    runtime.stop_session(SESSION)


REFUSALS = {
    400: ("the model provider refused the key (400)", "invalid_request_error"),
    401: ("the model provider refused the key (401)", "authentication_error"),
    404: ("the model provider refused the request (404)", "not_found_error"),
    413: ("the model provider refused the request (413)", "request_too_large"),
    429: ("the model provider limits requests, or the quota is spent (429)", "rate_limit_error"),
}


def cloud_ru_400(key: str) -> dict:
    """What cloud.ru answers to a wrong key, the human's report; with the key echoed."""
    return {"message": f"invalid api key secret {key}", "code": "InvalidArgument"}


def check_refusal(status_code: int, key: str, requests) -> None:
    """The turn ended on the server's `status_code` in LADO's words with no key in them, the
    agent is idle and the server's count of `requests()` stopped growing."""

    def told():
        said = [m for m in state.list_messages(SESSION) if m.recipient == state.HUMAN]
        return [m for m in said if "ended on an error" in m.summary]

    wait_for(told, "the turn's end on a refusal", 300)  # a 401 of Claude Code takes about 150 s
    [line] = told()
    print(f"refusal: {line.summary!r} body {line.body!r}, {requests()} requests")
    assert REFUSALS[status_code][0] in line.summary
    assert line.summary.endswith("; it is idle")
    assert key not in line.summary + line.body
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the agent to be idle", 30)
    assert state.get_agent(SESSION, "supervisor").resume_at is None

    def quiet() -> bool:
        count = requests()
        time.sleep(5)
        return requests() == count

    wait_for(quiet, "the server's count of requests to stop growing", 90)
    print(f"refusal: turn errors {[e.detail for e in events('supervisor', state.TURN_ERROR)]}")
    assert len(told()) == 1
    assert len(events("supervisor", state.TURN_ERROR)) == 1
    for file in state.home().glob("lado.db*"):
        assert key.encode() not in file.read_bytes()
    hooks_log = state.home() / "hooks.log"
    assert not hooks_log.exists() or key not in hooks_log.read_text()


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
@pytest.mark.parametrize("status_code", [s for s in REFUSALS if s != 413])  # their own overflow
def test_a_provider_s_refusal_ends_the_turn_within_the_cli_s_repeats(
    smoke_repo, smoke_provider, monkeypatch, status_code
):
    """The key the server repeats stays out of LADO's words, and the CLI's repeats end. No CLI's
    name in the test's: `-k <provider>` of a CI cell would take the other's case, which skips."""
    provider = smoke_provider
    monkeypatch.setitem(providers._PROVIDERS, provider, CLASSES[provider]())
    key = "smoke-refused-key-0123456789"
    server = fake_model_server.Server("all", key=key)
    try:
        model_settings.add_server("Облако", server.url, key, warn=print, note=print)
        state.add_model("Облачная", provider, "m1", state.model_server("Облако").id)
        runtime.start_session(str(smoke_repo), SESSION, None, provider, model="Облачная")
        idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
        wait_for(idle, "the supervisor to be idle after its session start", 120)
        error = {"error": {"message": f"Refused for {key}", "type": "refused"}}
        if status_code == 400:
            error = cloud_ru_400(key)
        server.refusal = fake_model_server.Answer(status_code, error, endpoints.RETRY_SOON)
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        check_refusal(status_code, key, lambda: len(chats(server)))
    finally:
        runtime.stop_session(SESSION)
        server.close()


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
@pytest.mark.parametrize("status_code", list(REFUSALS))
def test_a_provider_s_refusal_ends_a_claude_agent_s_turn_within_its_repeats(
    smoke_repo, smoke_provider, claude_server, status_code
):
    """In its TUI, past the CLAUDE_CODE_MAX_RETRIES of 0 the smoke's own environment sets: the
    agent's settings win. At most 7 repeats, so 8 requests of the turn on a 429 and, as measured,
    10 on a 401; beside them the TUI asks for the session's title, a request with no tools, and
    repeats it as much (2.1.295)."""
    runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "claude", model="Шлюз Qwen"
    )
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor to be idle after its session start", 120)

    def asked() -> list[dict]:
        bodies = [r[2] for r in list(claude_server.requests) if r[0] == "/v1/messages"]
        return [json.loads(body) for body in bodies if b'"messages"' in body]

    before = len(asked())
    error = {"type": REFUSALS[status_code][1], "message": f"Refused for {SERVER_KEY}"}
    answer = {"type": "error", "error": error}
    claude_server.refusal = (
        status_code,
        cloud_ru_400(SERVER_KEY) if status_code == 400 else answer,
    )
    runtime.write_as_human(SESSION, HUMAN_SAYS)
    check_refusal(status_code, SERVER_KEY, lambda: len(asked()))
    turn = [request for request in asked()[before:] if request.get("tools")]
    print(f"claude: {len(turn)} requests of the turn, {len(asked()) - before} in all")
    least, most = {400: (1, 1), 401: (2, 10), 404: (1, 2), 413: (1, 1), 429: (2, 8)}[status_code]
    assert least <= len(turn) <= most
    assert len(asked()) - before <= 2 * most
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
def test_a_cli_takes_a_config_with_a_model_s_limit(smoke_repo, smoke_provider, monkeypatch):
    """The real CLI starts on a model whose config holds `limit`, and asks the server with the
    output it was told; OpenCode refuses a config it does not understand."""
    provider = smoke_provider
    monkeypatch.setitem(providers._PROVIDERS, provider, CLASSES[provider]())
    server = fake_model_server.Server("gateway-limits")
    try:
        model_settings.add_server("малый", server.url, None, warn=print, note=print)
        saved = state.add_model("Малая", provider, "small", state.model_server("малый").id)
        started = runtime.start_session(str(smoke_repo), SESSION, None, provider, model=saved.name)
        assert any("has a context of 16,000 tokens" in line for line in started.warnings)
        agent = state.get_agent(SESSION, "supervisor")
        config = json.loads((providers.base.config_path(agent) / f"{provider}.json").read_text())
        entry = config["provider"][f"lado-{saved.server}"]["models"]["small"]
        assert entry["limit"] == {"context": 16000, "output": 2048}
        idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
        wait_for(idle, "the supervisor to be idle after its session start", 120)
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        told = lambda: [json.loads(r.body).get("max_tokens") for r in chats(server)]  # noqa: E731
        wait_for(lambda: 2048 in told(), "a request with the output it was told", 120)
    finally:
        runtime.stop_session(SESSION)
        server.close()


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
def test_a_message_right_after_the_start_goes_in_at_the_first_attempt(smoke_repo, smoke_provider):
    """Nothing is typed before the TUI's prompt has focus: the real CLI takes the first paste."""
    provider = smoke_provider
    try:
        runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", provider)
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        summary = HUMAN_SAYS.splitlines()[0]
        check = answering(provider, "supervisor", delivered(state.HUMAN, "supervisor", summary))
        wait_for(check, "the human's message", 120)
        assert message(state.HUMAN, "supervisor", summary).attempts == 1
    finally:
        runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["kilo", "opencode"], indirect=True)
def test_a_tui_plugin_that_does_not_load_leaves_no_agent_starting(
    smoke_repo, smoke_provider, monkeypatch, tmp_path
):
    """A CLI that no longer loads the TUI plugin: the server plugin says so, the message goes."""
    provider = smoke_provider
    monkeypatch.setattr(opencode_family, "TUI_PLUGIN", tmp_path / "no-such-plugin.js")
    try:
        runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", provider)
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        summary = HUMAN_SAYS.splitlines()[0]
        check = answering(provider, "supervisor", delivered(state.HUMAN, "supervisor", summary))
        wait_for(check, "the human's message", 120)
        line = f"supervisor: {opencode_family.TUI_SILENT_NOTE}"
        assert line in [m.summary for m in state.list_messages(SESSION)]
    finally:
        runtime.stop_session(SESSION)


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
    "claude": (("yes", "Token", "ANTHROPIC_AUTH_TOKEN"), "no"),
    # The smoke's Codex home is logged in with a key (conftest.codex_login).
    "codex": (("yes", "Pay per use (API key)", ""), "no"),
    "kilo": (None, "no"),
    "opencode": (None, "no"),
}


def test_each_clis_login_is_read_from_its_own_command(
    smoke_provider, tmp_path, monkeypatch, codex_home
):
    provider = providers.get(smoke_provider)
    given, none = LOGINS[smoke_provider]
    if given:
        found = provider.login_status(logins.environment(provider))
        print(f"{smoke_provider}: {found}")
        assert (found.state, found.method, found.variable) == given
        if smoke_provider == "claude":
            monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN")
        else:
            (codex_home / "auth.json").unlink()
    found = provider.login_status(logins.environment(provider))
    print(f"{smoke_provider}: without a login {found}")
    assert found.state == none, found.problem
    if smoke_provider in ("kilo", "opencode"):
        # A credential in the CLI's own file, and a key in the environment.
        data = Path(os.environ["XDG_DATA_HOME"]) / smoke_provider
        data.mkdir(parents=True, exist_ok=True)
        (data / "auth.json").write_text(json.dumps({"anthropic": {"type": "api", "key": "k"}}))
        monkeypatch.setenv("OPENAI_API_KEY", "smoke-key")
        found = provider.login_status(logins.environment(provider))
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
    config.write_text(json.dumps({}))
    started = runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", "claude")
    print(f"claude: started, warnings {started.warnings}")
    note = f"LADO recorded Claude Code's first run in {config}"
    assert note not in started.warnings  # LADO's own write: loop.log only
    assert note in (state.home() / "loop.log").read_text()
    assert json.loads(config.read_text())["hasCompletedOnboarding"] is True
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor idle with no human", 120)
    # Bypass mode's warning was skipped by the agent's own settings, not the shared file.
    assert "bypassPermissionsModeAccepted" not in json.loads(config.read_text())
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["claude"], indirect=True)
def test_a_claude_session_with_a_repo_mcp_json_starts_with_no_screen(
    smoke_provider, smoke_repo, fake_endpoint
):
    """A repository's .mcp.json makes Claude Code ask "New MCP server found in this
    project" before any hook; the agent's own settings take its servers (LAD-163)."""
    servers = {"mcpServers": {"repo-tool": {"command": "true", "args": []}}}
    (smoke_repo / ".mcp.json").write_text(json.dumps(servers))
    git = ["git", "-C", str(smoke_repo)]
    subprocess.run([*git, "add", ".mcp.json"], check=True)
    subprocess.run([*git, "commit", "-qm", "A repository MCP server"], check=True)
    # Not bypass mode, whose own warning the other test covers.
    runtime.start_session(str(smoke_repo), SESSION, "default", "claude")
    idle = answering("claude", "supervisor", lambda: status(SESSION, "supervisor") == "idle")
    wait_for(idle, "the supervisor idle with no human", 120)
    changed = subprocess.run([*git, "status", "--porcelain"], capture_output=True, text=True)
    assert changed.stdout == ""  # nothing written into the repository
    runtime.stop_session(SESSION)


# Codex's shared login (openspec change codex-shared-login): each agent's auth.json is a link
# to the user's, which Codex writes in place, so a refresh in one reaches all.
FILE_STORE = ["-c", 'cli_auth_credentials_store="file"']
PLUGINS_WATCH = 40  # seconds a new agent's home is watched for Codex's plugins catalogue


def _codex(home: Path, *args: str, key: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["codex", *args, *FILE_STORE],
        input=key,
        env={**os.environ, "CODEX_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )


CODEX_KEY = "smoke-codex-server-key"
CODEX_SERVER_MODEL = "smoke/gpt"
CODEX_MODEL = "Шлюз GPT"


@pytest.fixture
def codex_server(smoke_repo, tmp_path, monkeypatch, codex_home):
    """A saved model server of the Responses API with the model `Шлюз GPT` and a key, every other
    way out of the machine refused, and Codex not logged in."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
        monkeypatch.setenv(name.lower(), "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    (codex_home / "auth.json").unlink(missing_ok=True)
    server = endpoints.Responses(CODEX_SERVER_MODEL, tmp_path / "shell-ran", CODEX_KEY)
    model_settings.add_server("Шлюз", server.url, CODEX_KEY, warn=print, note=print)
    state.add_model(CODEX_MODEL, "codex", CODEX_SERVER_MODEL, state.model_server("Шлюз").id)
    yield server
    server.close()


def codex_session(smoke_repo, server: endpoints.Responses) -> state.Agent:
    """A Codex session on the server, past its first turn."""
    started = runtime.start_session(
        str(smoke_repo), SESSION, "bypassPermissions", "codex", model=CODEX_MODEL
    )
    print(f"codex: started, warnings {started.warnings}")
    assert not [w for w in started.warnings if "/model" in w], started.warnings
    first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
    wait_for(answering("codex", "supervisor", first), "codex's first input delivered", 120)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the first turn's end", 120)
    return state.get_agent(SESSION, "supervisor")


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_codex_runs_on_a_server_with_its_tools_and_no_login(
    smoke_repo, smoke_provider, codex_server, fake_endpoint
):
    """Not logged in: a turn with a shell and LADO's MCP tool runs on the server alone, with the
    agent's own list of models, and asks for nothing a server may refuse."""
    agent = codex_session(smoke_repo, codex_server)
    runtime.write_as_human(SESSION, endpoints.RUN_TOOLS)
    wait_for(codex_server.marker.exists, "the shell tool to run", 120)
    called = lambda: endpoints.MCP_CALL in codex_server.tool_results()  # noqa: E731
    wait_for(called, "the MCP tool to run", 120)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "the turn's end", 120)
    assert state.get_agent(SESSION, "supervisor").model == CODEX_SERVER_MODEL
    assert fake_endpoint.requests == []
    home = providers.base.config_path(agent)
    assert not (home / "auth.json").exists()
    assert CODEX_KEY not in (home / "config.toml").read_text()
    assert CODEX_KEY not in (home / "models.json").read_text()
    asked = codex_server.asked()
    assert {request["model"] for request in asked} == {CODEX_SERVER_MODEL}
    for _, headers, body in codex_server.requests:
        if b'"model"' in body:
            assert headers["authorization"] == f"Bearer {CODEX_KEY}"
    tools = asked[-1]["tools"]
    print(f"codex: tools {[(t.get('type'), t.get('name')) for t in tools]}")
    assert not [t for t in tools if t.get("type") in ("web_search", "custom")]
    assert "reasoning" not in asked[-1] or not (asked[-1]["reasoning"] or {}).get("effort")
    assert endpoints.LADO_TOOL in [
        inner["name"]
        for tool in tools
        if tool.get("type") == "namespace"
        for inner in tool["tools"]
    ]
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_model_of_a_codex_agent_on_a_server_shows_its_model_alone(
    smoke_repo, smoke_provider, codex_server
):
    """Real Codex takes the agent's list, in the format of the installed binary: with a field it
    does not read the list, it would show OpenAI's models here."""
    codex_session(smoke_repo, codex_server)
    tmux.send_text(SESSION, "supervisor", "/model")
    shown = lambda: CODEX_MODEL in tmux.capture(SESSION, "supervisor")  # noqa: E731
    wait_for(shown, "/model's list", 30)
    screen = tmux.capture(SESSION, "supervisor")
    print(f"codex: /model shows\n{screen}")
    assert "On Шлюз" in screen
    assert "gpt-5" not in screen.lower() and "gpt-6" not in screen.lower()
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_codex_on_a_server_compacts_past_its_limit(smoke_repo, smoke_provider, codex_server):
    agent = codex_session(smoke_repo, codex_server)
    written = (providers.base.config_path(agent) / "config.toml").read_text()
    assert f"model_context_window = {endpoints.CONTEXT}" in written
    # Past LADO's limit, which leaves the output room, and short of Codex's own 90%.
    room = providers.base.Limit(endpoints.CONTEXT).output_room()
    codex_server.tokens = endpoints.CONTEXT - room + 100
    runtime.write_as_human(SESSION, "a turn that reports the tokens")
    wait_for(lambda: len(codex_server.asked()) >= 2, "that turn", 120)
    wait_for(lambda: status(SESSION, "supervisor") == "idle", "that turn's end", 120)
    assert codex_server.compactions == 0
    codex_server.tokens = 1
    runtime.write_as_human(SESSION, "the next turn")
    wait_for(lambda: codex_server.compactions == 1, "the compaction", 120)
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
@pytest.mark.parametrize("status_code", [401, 429])
def test_a_refusal_ends_a_codex_agent_s_turn_in_lado_s_words(
    smoke_repo, smoke_provider, codex_server, status_code
):
    """The journal's format of the installed Codex: only this layer catches a change of it. The
    server echoes the key, which stays out of LADO's words."""
    agent = codex_session(smoke_repo, codex_server)
    error = {"error": {"message": f"Refused for {CODEX_KEY}", "type": "refused"}}
    codex_server.refusal = (status_code, error)
    before = len(codex_server.asked())
    runtime.write_as_human(SESSION, HUMAN_SAYS)
    check_refusal(status_code, CODEX_KEY, lambda: len(codex_server.asked()))
    repeats = len(codex_server.asked()) - before
    print(f"codex: {repeats} requests of the turn")
    assert 1 <= repeats <= 12
    assert (providers.base.config_path(agent) / "journal-offset").exists()
    runtime.stop_session(SESSION)


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_a_codex_agent_shares_the_users_login_file(
    smoke_provider, smoke_repo, fake_endpoint, codex_home
):
    user = codex_home / "auth.json"
    runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", "codex")
    first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
    wait_for(answering("codex", "supervisor", first), "codex's first input delivered", 120)
    wait_for(lambda: fake_endpoint.requests, "the supervisor's turn at the endpoint", 120)
    home = providers.base.config_path(state.get_agent(SESSION, "supervisor"))
    auth = home / "auth.json"
    assert auth.is_symlink() and os.readlink(auth) == str(user)
    status = _codex(home, "login", "status")
    assert "Logged in using an API key" in status.stderr + status.stdout, status
    # Codex writes the login through the agent's link into the user's file (its refresh
    # saves the same way): the link stays a link. A Codex that wrote a new file and renamed
    # it would break the shared login here.
    before = user.stat().st_ino
    written = _codex(home, "login", "--with-api-key", key="smoke-second-key-0123456789")
    assert written.returncode == 0, written
    assert auth.is_symlink() and os.readlink(auth) == str(user)
    assert user.stat().st_ino == before
    assert "smoke-second-key" in user.read_text()
    runtime.stop_session(SESSION)


def sandbox_probes(monkeypatch) -> list[str | None]:
    """What each probe of Codex's sandbox answered, the real one asked (real_clis.isolated)."""
    assert codex._sandbox_error is SANDBOX_ERROR, "the smoke must ask the real Codex"
    probes = []

    def probe(*args):
        probes.append(SANDBOX_ERROR(*args))
        return probes[-1]

    monkeypatch.setattr(codex, "_sandbox_error", probe)
    return probes


def check_sandbox_warning(started, probes: list[str | None], mode: str | None) -> None:
    """The launch warned of Codex's sandbox exactly as the real probe answered (LAD-151), as
    on a host: tests/conftest.py clears LADO_CONTAINER."""
    warned = [w for w in started.warnings if w.startswith("Codex's sandbox cannot start")]
    if sys.platform != "linux" or mode == "bypassPermissions":
        assert (probes, warned) == ([], [])
        return
    [error] = probes
    assert warned == (
        []
        if error is None
        else [
            f"Codex's sandbox cannot start here ({error}): Codex agent supervisor asks before "
            "each shell command; docs/install.md says how to allow it, or use bypassPermissions"
        ]
    )


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
@pytest.mark.parametrize("mode", [None, "default", "bypassPermissions"])
def test_a_codex_session_starts_with_no_screen_in_each_mode(
    smoke_provider, smoke_repo, fake_endpoint, codex_home, mode, monkeypatch
):
    """A repository the user's Codex never trusted, with its own hooks never reviewed: the
    agent's first input, submitted once no dialog holds Codex, is delivered with no human,
    and Codex fetched no plugins into its home. On Linux, out of bypass mode, the launch
    asked the real Codex whether its sandbox starts, and warned only when it did not."""
    probes = sandbox_probes(monkeypatch)
    hooks = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}}
    (smoke_repo / ".codex").mkdir()
    (smoke_repo / ".codex" / "hooks.json").write_text(json.dumps(hooks))
    git = ["git", "-C", str(smoke_repo)]
    subprocess.run([*git, "add", ".codex"], check=True)
    subprocess.run([*git, "commit", "-qm", "The repository's own Codex hooks"], check=True)
    assert "projects" not in (codex_home / "config.toml").read_text()
    started = runtime.start_session(str(smoke_repo), SESSION, mode, "codex")
    check_sandbox_warning(started, probes, mode)
    first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
    wait_for(answering("codex", "supervisor", first), "codex's first input delivered", 120)
    home = providers.base.config_path(state.get_agent(SESSION, "supervisor"))
    # Codex 0.162 clones its plugins catalogue some seconds after its start (16 s in the
    # container): watched for a while, in one mode, as it does not depend on the mode.
    deadline = time.monotonic() + (PLUGINS_WATCH if mode is None else 0)
    while not (home / ".tmp" / "plugins").exists() and time.monotonic() < deadline:
        time.sleep(1)
    assert not (home / ".tmp" / "plugins").exists()
    assert "projects" not in (codex_home / "config.toml").read_text()  # the user's untouched
    runtime.stop_session(SESSION)


# A model whose metadata turns Codex's second version of its own subagents on (Codex 0.162):
# the tools of the namespace `collaboration`, `wait_agent` among them (LAD-167).
# Not gpt-5.6-sol, whose TUI asks first whether to move to gpt-6-sol.
SUBAGENT_MODEL = "gpt-6-sol"
# The first version's tools, which a namespace may hold too.
SUBAGENT_TOOLS = {"spawn_agent", "wait_agent", "send_input", "resume_agent", "close_agent"}


def _subagent_tools(names: list[str]) -> list[str]:
    return [
        n for n in names if n.startswith("collaboration.") or n.rsplit(".", 1)[-1] in SUBAGENT_TOOLS
    ]


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_a_codex_agent_gets_none_of_codex_s_own_subagents(
    smoke_provider, smoke_repo, fake_endpoint, codex_home
):
    """With a model whose metadata gives Codex's subagents, a plain `codex exec` (its plugins
    off) offers it `collaboration.wait_agent`; a LADO agent's first request offers no
    subagent tool."""
    config = codex_home / "config.toml"
    config.write_text(
        re.sub(r'(?m)^model = ".*"$', f'model = "{SUBAGENT_MODEL}"', config.read_text())
    )
    # Plugins off: Codex 0.162 syncs OpenAI's curated plugins catalogue at its start in the
    # background (`git ls-remote https://github.com/openai/plugins.git`, then a clone);
    # `codex exec` ends before it, and the orphaned git outlived the test (LAD-175).
    control = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "-c", "features.plugins=false", "hi"],
        cwd=smoke_repo,
        env={**os.environ, "CODEX_HOME": str(codex_home)},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )
    plain = [n for names in fake_endpoint.tools for n in names]
    assert "collaboration.wait_agent" in plain, (
        f"{SUBAGENT_MODEL} no longer brings Codex's own subagents to a plain `codex exec`: "
        f"re-check the cause (openspec change codex-subagents-off, D4); tools {plain}, "
        f"codex {control.stderr[-2000:]}"
    )
    asked = len(fake_endpoint.requests)

    runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", "codex")
    first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
    wait_for(answering("codex", "supervisor", first), "codex's first input delivered", 120)
    wait_for(
        lambda: len(fake_endpoint.requests) > asked, "the supervisor's turn at the endpoint", 120
    )
    agent = fake_endpoint.tools[asked]
    assert {"exec_command", "functions.exec"} & set(agent), agent  # the names were read
    assert _subagent_tools(agent) == [], agent
    runtime.stop_session(SESSION)
