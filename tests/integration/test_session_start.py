"""The supervisor starts a session the human approved: from its own `lado mcp`, the fake
agent's MCP server, through real tmux, the session loop and the new supervisor's hooks."""

import json

import pytest
from agent_helpers import fake_logs, wait_for

from lado import loop, runtime, state, tmux

pytestmark = pytest.mark.integration


def seen(session: str) -> dict:
    path = fake_logs(session, "supervisor") / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def idle(session: str) -> bool:
    agent = state.get_agent(session, "supervisor")
    return agent is not None and agent.status == state.IDLE


def test_an_approved_proposal_starts_an_independent_session_with_the_brief(repo):
    (repo / "brief.md").write_text("# Fix the login bug\n")
    kit = repo / ".lado" / "kits" / "team"
    (kit / "skills" / "style").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "skills" / "style" / "SKILL.md").write_text("---\nname: style\ndescription: d\n---\n")
    runtime.start_session(
        str(repo), "a", None, "fake", kit_names=["default", "team"], without=["skill:style"]
    )
    try:
        wait_for(lambda: idle("a"), "a's supervisor idle", "a")
        choice = runtime.START_CHOICE.format(name="b")
        runtime.send_message(
            "a",
            "human",
            "supervisor",
            "artifact_write brief-b brief.md",
            None,
        )
        wait_for(lambda: "artifact_write" in seen("a"), "the brief written", "a")
        runtime.send_message(
            "a", "human", "supervisor", f"askhuman Start b? | {choice}, No --artifacts brief-b"
        )
        question = wait_for(
            lambda: next((m for m in state.list_messages("a") if m.kind == state.QUESTION), None),
            "the question",
            "a",
        )
        runtime.answer_question("a", question.id, choice, "the log is attached too")
        runtime.send_message("a", "human", "supervisor", f"start_session b {question.id}")
        wait_for(lambda: "start_session" in seen("a"), "start_session's result", "a")
        assert seen("a")["start_session"]["session"] == "b", seen("a")["start_session_text"]

        # B: its own session, the caller's repo and settings, its supervisor reads the brief.
        b = state.get_session("b")
        assert (b.repo, b.provider, b.permission_mode, b.kits, b.without) == (
            str(repo),
            "fake",
            None,
            ["default", "team"],
            ["skill:style"],
        )
        wait_for(lambda: "first_read" in seen("b"), "b's supervisor reads its first input", "b")
        [first] = seen("b")["first_read"]
        assert first["from"] == "lado"
        assert f"a/supervisor's proposal #{question.id}" in first["summary"]
        assert "the log is attached too" in first["body"]
        assert [a["name"] for a in first["artifacts"]] == ["brief-b"]
        environ = seen("b")["environ"]
        assert (environ["LADO_SESSION"], environ["LADO_AGENT"]) == ("b", "supervisor")
        assert "LADO_INSTANCE" not in environ  # not a's, from a's `lado mcp`
        lado_mcp = seen("b")["mcp"]["lado"]["env"]
        assert (lado_mcp["LADO_SESSION"], lado_mcp["LADO_INSTANCE"]) == (
            "b",
            state.get_agent("b", "supervisor").instance,
        )
        wait_for(lambda: idle("b"), "b's supervisor idle", "b")
        runtime.send_message("b", "human", "supervisor", "artifact_read brief-b")
        wait_for(lambda: "artifact_read" in seen("b"), "b reads the brief", "b")
        assert seen("b")["artifact_read"]["content"] == "# Fix the login bug\n"

        # One approval starts one session.
        wait_for(lambda: idle("a"), "a's supervisor idle", "a")
        runtime.send_message("a", "human", "supervisor", f"start_session b {question.id}")
        wait_for(
            lambda: "exists already" in " ".join(seen("a")["start_session_text"]),
            "the second start refused",
            "a",
        )

        # B outlives A.
        runtime.stop_session("a")
        assert tmux.has_session("b")
        assert loop.running("b")
        assert idle("b")
    finally:
        for session in ("a", "b"):
            sess = state.get_session(session)
            if sess and not sess.stopped_at:
                runtime.stop_session(session)
