"""Codex agents share a real ChatGPT login (openspec change codex-shared-login): a Codex
session with a worker on OpenAI's model, each agent's auth.json a link to the login file of
a Codex home the human logged in to; each agent started on that file made stale, so it
refreshes it through its link; the other goes on working, the links stay, and the home is
still logged in. And a Codex supervisor on that login, OpenAI's newer models whose metadata
brings Codex's own subagents, ends its start turn and answers the human's first message
without them (openspec change codex-subagents-off).

Only at a release, with the human: it needs a ChatGPT account, which CI has none of, and it
spends a few of its requests. Log a throwaway Codex home in once, then name it:

    CODEX_HOME=/tmp/lado-codex-live codex login --device-auth
    LADO_LIVE_CODEX_HOME=/tmp/lado-codex-live make test-live PROVIDER=codex

Skipped without it. Afterwards `CODEX_HOME=/tmp/lado-codex-live codex logout` revokes it."""

import datetime
import json
import os
import subprocess
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo
from real_clis import answer_dialogs

from lado import providers, runtime, state

pytestmark = pytest.mark.live

SESSION = "live-codex-login"
HOME_VARIABLE = "LADO_LIVE_CODEX_HOME"
FILE_STORE = ["-c", 'cli_auth_credentials_store="file"']


def _status(home: Path) -> str:
    done = subprocess.run(
        ["codex", "login", "status", *FILE_STORE],
        env={**os.environ, "CODEX_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.stdout + done.stderr


@pytest.fixture
def chatgpt_home(monkeypatch) -> Path:
    """The Codex home the human logged in to with ChatGPT: the user's own Codex here."""
    named = os.environ.get(HOME_VARIABLE)
    if not named:
        pytest.skip(f"{HOME_VARIABLE} names no Codex home logged in with ChatGPT")
    home = Path(named)
    if "Logged in using ChatGPT" not in _status(home):
        pytest.skip(f"the Codex home {home} is not logged in with ChatGPT")
    monkeypatch.setenv("CODEX_HOME", str(home))
    for name in ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)  # the shared file is the login
    return home


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def idle(agent: str):
    def check() -> bool:
        answer_dialogs("codex", SESSION, agent)
        found = state.get_agent(SESSION, agent)
        return found is not None and found.status == state.IDLE

    return check


def linked(agent: str, target: Path) -> None:
    auth = providers.base.config_path(state.get_agent(SESSION, agent)) / "auth.json"
    assert auth.is_symlink() and os.readlink(auth) == str(target), auth


STALE_TOKEN = "stale-access-token"  # no token Codex can use: it must refresh


def make_stale(target: Path) -> dict:
    """The login file as one due for a refresh, written in place as Codex writes it: an
    access token Codex cannot use and `last_refresh` a month old. A running Codex keeps its
    login in memory and reads the file again only when its own tokens need a refresh (live
    run of 2026-11-01: a file made stale under two running agents was never refreshed), so
    an agent is started on it."""
    data = json.loads(target.read_text())
    month_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    data["last_refresh"] = month_ago.isoformat().replace("+00:00", "Z")
    data["tokens"]["access_token"] = STALE_TOKEN
    with target.open("w") as file:
        json.dump(data, file)
    return data


def refreshed(target: Path, stale: dict) -> bool:
    data = json.loads(target.read_text())
    return (
        data["last_refresh"] != stale["last_refresh"]
        and data["tokens"]["access_token"] != STALE_TOKEN
    )


def test_codex_agents_share_a_chatgpt_login_and_its_refresh(chatgpt_home, tmp_path):
    target = chatgpt_home / "auth.json"
    inode = target.stat().st_ino
    repo = init_repo(tmp_path / "repo")

    # The supervisor starts on a stale login: it refreshes it through its link.
    stale = make_stale(target)
    runtime.start_session(str(repo), SESSION, "bypassPermissions", "codex")
    wait_for(idle("supervisor"), "the supervisor's first turn on its ChatGPT login", 300)
    linked("supervisor", target)
    assert refreshed(target, stale), "the supervisor's refresh did not reach the shared file"

    # So does a worker, on the login made stale again; the supervisor, with the tokens of its
    # own refresh, goes on working beside it.
    stale = make_stale(target)
    runtime.spawn_worker(SESSION, "Reply with the word ready, nothing else.", name="w1")
    wait_for(idle("w1"), "the worker's first turn", 300)
    linked("w1", target)
    assert refreshed(target, stale), "the worker's refresh did not reach the shared file"
    runtime.send_message(SESSION, "human", "supervisor", "Reply with the word again, nothing else.")
    wait_for(
        lambda: (
            [m for m in state.list_messages(SESSION) if m.sender == "human"][-1].state
            in (state.DELIVERED, state.READ)
        ),
        "the supervisor's message delivered",
        300,
    )
    wait_for(idle("supervisor"), "the supervisor's turn after the worker's refresh", 300)

    assert target.stat().st_ino == inode  # written in place: the links still reach it
    for agent in ("supervisor", "w1"):
        linked(agent, target)
    assert "Logged in using ChatGPT" in _status(chatgpt_home)
    runtime.stop_session(SESSION)


# Codex's own subagents, of both versions: newer OpenAI models turn the second on through
# their metadata (openspec change codex-subagents-off).
SUBAGENT_TOOLS = {"spawn_agent", "wait_agent", "send_input", "resume_agent", "close_agent"}


def tool_calls(agent: str) -> list[str]:
    """The names of the tools the agent's Codex called, from the rollouts in its home's
    sessions/, a namespace's as `<namespace>.<name>`."""
    home = providers.base.config_path(state.get_agent(SESSION, agent))
    names = []
    for rollout in sorted((home / "sessions").rglob("rollout-*.jsonl")):
        for line in rollout.read_text().splitlines():
            payload = json.loads(line).get("payload") or {}
            if payload.get("type") in ("function_call", "custom_tool_call"):
                namespace = payload.get("namespace")
                names.append(f"{namespace}.{payload['name']}" if namespace else payload["name"])
    return names


def test_a_codex_supervisor_answers_the_human_s_first_message(chatgpt_home, tmp_path):
    """A session without a first message: LADO's start line ends the supervisor's turn, the
    human's "hi" is delivered and answered, and no turn called Codex's own subagents."""
    repo = init_repo(tmp_path / "repo")
    runtime.start_session(str(repo), SESSION, "bypassPermissions", "codex")
    first = [m for m in state.list_messages(SESSION) if m.summary == runtime.FIRST_INPUT]
    assert first, "the supervisor got no first input from LADO"
    wait_for(idle("supervisor"), "the supervisor's start turn to end", 300)

    runtime.write_as_human(SESSION, "hi")
    wait_for(
        lambda: (
            [m for m in state.list_messages(SESSION) if m.sender == "human"][-1].state
            in (state.DELIVERED, state.READ)
        ),
        "the human's hi delivered",
        300,
    )

    def answered():
        messages = state.list_messages(SESSION)
        return [m for m in messages if (m.sender, m.recipient) == ("supervisor", "human")]

    wait_for(answered, "the supervisor's answer to the human", 300)
    wait_for(idle("supervisor"), "the supervisor idle after its answer", 300)

    called = tool_calls("supervisor")
    print(f"codex: the supervisor's tool calls {called}")
    assert called, "no tool call in the supervisor's rollouts: were they read?"
    assert [n for n in called if n.rsplit(".", 1)[-1] in SUBAGENT_TOOLS] == [], called
    runtime.stop_session(SESSION)
