"""Read-only roles for real: a read-only agent's hooks check its repository at each turn
and its `lado mcp` has no command tools (fake agent, real tmux, git, hooks and MCP)."""

import json

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "itest"
# What a turn does that changes the repository: a commit and a file left behind.
CHANGES = "sh echo x > done.txt && git add done.txt && git commit -qm done && echo y > junk.txt"


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def from_lado(to: str) -> list[str]:
    return [
        m.summary for m in state.list_messages(SESSION) if m.sender == "lado" and m.recipient == to
    ]


def events(kind: str) -> list[tuple[str, str]]:
    return [(e.agent, e.detail) for e in state.list_events(SESSION) if e.kind == kind]


def kit(repo, supervisor: str | None = None):
    folder = repo.parent / "kits" / "quiet"
    (folder / "agents").mkdir(parents=True)
    lead = f"supervisor: {supervisor}\n" if supervisor else ""
    (folder / "kit.yaml").write_text(f"name: quiet\nversion: 1.0.0\n{lead}")
    for name, extra in (("reviewer", "read_only: true\n"), ("dev", "")):
        (folder / "agents" / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {name}\n{extra}---\nWork.\n"
        )
    agent_helpers.install_kit(folder)


def test_a_read_only_worker_s_commit_and_file_reach_the_supervisor_a_normal_one_s_do_not(repo):
    kit(repo)
    runtime.start_session(str(repo), SESSION, None, "fake", kit_names=["quiet"])
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "supervisor")
    runtime.spawn_worker(SESSION, CHANGES, name="d1", role="dev")
    runtime.spawn_worker(SESSION, CHANGES, name="r1", role="reviewer")
    for agent in ("d1", "r1"):
        wait_for(lambda a=agent: seen(a).get("sh", {}).get("code") == 0, f"{agent}'s commit")
    wait_for(lambda: events(state.REPO_CHANGED), "the repo_changed event")
    [(agent, detail)] = events(state.REPO_CHANGED)
    assert agent == "r1"
    head, *rest = detail.splitlines()
    assert head.startswith("HEAD ") and rest == ["new: junk.txt"]
    wait_for(lambda: from_lado("supervisor"), "the line to the supervisor")
    assert from_lado("supervisor") == [
        f"while r1's turn the repository changed: {head}, new: junk.txt"
    ]
    wait_for(lambda: state.get_agent(SESSION, "r1").status == state.IDLE, "r1 idle")
    wait_for(lambda: state.get_agent(SESSION, "d1").status == state.IDLE, "d1 idle")
    assert events(state.REPO_CHECK_FAILED) == []
    assert len(from_lado("supervisor")) == 1


def test_a_read_only_supervisor_cannot_spawn_a_worker(repo):
    kit(repo, supervisor="reviewer")
    runtime.start_session(str(repo), SESSION, None, "fake", kit_names=["quiet"])
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "supervisor")
    runtime.send_message(SESSION, "human", "supervisor", "tools")
    wait_for(lambda: "tools" in seen("supervisor"), "its tool list")
    assert "spawn_worker" not in seen("supervisor")["tools"]
    assert "send_message" in seen("supervisor")["tools"]
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    wait_for(
        lambda: (
            "role reviewer is read-only: spawn_worker is not available"
            in tmux.run("capture-pane", "-p", "-J", "-t", f"={SESSION}:=supervisor")
        ),
        "spawn_worker's refusal",
    )
    assert [a.name for a in state.list_agents(SESSION)] == ["supervisor"]
