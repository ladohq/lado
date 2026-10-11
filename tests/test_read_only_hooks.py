"""A read-only agent's hooks compare its repository at each turn's start and end
(lado.fingerprint): a change is told to its lead, nothing is blocked. Other agents' hooks
take no fingerprint."""

import json
import os
import sys
import time

import pytest

from lado import fingerprint, hooks, providers, runtime, state
from lado.providers import base


@pytest.fixture
def quiet(repo, fake_tmux):
    """Session "s" with a read-only reviewer "r1" and a developer "d1", both idle."""
    kit = repo / ".lado" / "kits" / "quiet"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: quiet\nversion: 1.0.0\n")
    (kit / "agents" / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: reviews\nread_only: true\n---\nReview.\n"
    )
    (kit / "agents" / "dev.md").write_text("---\nname: dev\ndescription: d\n---\nDevelop.\n")
    runtime.start_session(str(repo), "s", None, provider="claude", kit_names=["quiet"])
    runtime.spawn_worker("s", "review", name="r1", role="reviewer")
    runtime.spawn_worker("s", "build", name="d1", role="dev")
    for agent in ("r1", "d1"):
        _hook("SessionStart", agent)
        _hook(
            "UserPromptSubmit",
            agent,
            {"prompt": f"[from lado] {'review' if agent == 'r1' else 'build'}"},
        )
        _hook("Stop", agent)
    with state.connect() as db:
        db.execute("DELETE FROM messages")
        db.execute("DELETE FROM events WHERE kind LIKE 'repo_%'")
    return repo


def _hook(event, agent, payload=None, deadline=None):
    if event == "SessionStart":
        state.add_event("s", agent, state.MCP_READY, state.get_agent("s", agent).instance)
    claude = providers.get("claude")
    neutral = claude.parse_event(event, json.dumps(payload or {}))
    return hooks.handle(claude, neutral, "s", agent, deadline=deadline)


def _tree(agent):
    return state.get_agent("s", agent).cwd


def _baseline(agent):
    path = base.config_path(state.get_agent("s", agent)) / hooks.BASELINE
    return json.loads(path.read_text()) if path.exists() else None


def _from_lado(to):
    return [m for m in state.list_messages("s") if m.sender == state.LADO and m.recipient == to]


def _events(kind):
    return [e.detail for e in state.list_events("s") if e.kind == kind]


def test_a_change_in_a_read_only_turn_is_told_to_the_lead_with_an_event(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    assert _baseline("r1")["state"] == "open"
    open(f"{_tree('r1')}/notes.md", "w").write("x\n")
    _hook("Stop", "r1")
    [line] = _from_lado("supervisor")
    assert line.summary == "while r1's turn the repository changed: new: notes.md"
    assert _events(state.REPO_CHANGED) == ["new: notes.md"]
    assert _baseline("r1")["state"] == "closed"


def test_changes_between_its_turns_and_in_a_normal_agent_s_turn_are_not_told(quiet, monkeypatch):
    open(f"{_tree('r1')}/between.md", "w").write("x\n")  # e.g. another agent of its run
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    _hook("Stop", "r1")

    def no_git(*args):
        raise AssertionError("a normal agent's hooks take no fingerprint")

    monkeypatch.setattr(fingerprint, "take", no_git)
    _hook("UserPromptSubmit", "d1", {"prompt": "go"})
    open(f"{_tree('d1')}/code.py", "w").write("x\n")
    _hook("Stop", "d1")
    assert _from_lado("supervisor") == [] and _events(state.REPO_CHANGED) == []
    assert _baseline("d1") is None


def test_a_temporary_file_gone_by_the_turn_s_end_is_no_change(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    path = f"{_tree('r1')}/tmp.txt"
    open(path, "w").write("x\n")
    os.unlink(path)
    _hook("Stop", "r1")
    assert _from_lado("supervisor") == []


def test_the_turn_s_end_is_written_before_the_agent_is_idle(quiet, monkeypatch):
    seen = []
    set_status = state.set_status

    def recording(session, agent, status, *args, **kwargs):
        if agent == "r1" and status == state.IDLE:
            seen.append(_baseline("r1")["state"])
        return set_status(session, agent, status, *args, **kwargs)

    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    monkeypatch.setattr(state, "set_status", recording)
    _hook("Stop", "r1")
    assert seen == ["closed"]


def test_a_late_hook_leaves_the_next_turn_s_start_alone(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    _hook("Stop", "r1")
    _hook("UserPromptSubmit", "r1", {"prompt": "again"})
    opened = _baseline("r1")
    assert opened["state"] == "open"
    _hook("PostToolUse", "r1", {"tool_name": "Read", "tool_input": {}})  # async, late
    assert _baseline("r1") == opened


def test_a_turn_that_goes_on_from_the_hook_s_output_is_compared_with_the_last_end(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    runtime.send_message("s", "supervisor", "r1", "one more")  # waits: r1 is busy
    output = _hook("Stop", "r1")
    assert json.loads(output)["decision"] == "block"  # the queue goes in the hook's output
    # Claude Code runs no prompt-submit hook for that turn: the end is its start.
    assert _baseline("r1")["state"] == "continued"
    open(f"{_tree('r1')}/later.md", "w").write("x\n")
    _hook("Stop", "r1", {"stop_hook_active": True})
    assert [m.summary for m in _from_lado("supervisor")] == [
        "while r1's turn the repository changed: new: later.md"
    ]


def test_a_prompt_submit_for_the_hook_s_output_starts_the_turn_with_no_report(quiet):
    """OpenCode and Kilo run chat.message for the turn-end hook's output (promptAsync): its
    turn's start follows the end that was seen, nothing to tell between them."""
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    runtime.send_message("s", "supervisor", "r1", "one more")
    output = _hook("Stop", "r1")
    assert _baseline("r1")["state"] == "continued"
    open(f"{_tree('r1')}/other-agent.md", "w").write("x\n")  # e.g. another agent of its run
    _hook("UserPromptSubmit", "r1", {"prompt": json.loads(output)["reason"]})
    assert _from_lado("supervisor") == [] and _events(state.REPO_CHANGED) == []
    assert _baseline("r1")["state"] == "open"
    open(f"{_tree('r1')}/mine.md", "w").write("x\n")
    _hook("Stop", "r1")
    assert [m.summary for m in _from_lado("supervisor")] == [
        "while r1's turn the repository changed: new: mine.md"
    ]


def test_a_turn_whose_end_was_not_seen_is_compared_at_the_next_start(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    open(f"{_tree('r1')}/esc.md", "w").write("x\n")
    # The human pressed Esc: Claude Code runs no Stop; the next prompt comes.
    _hook("UserPromptSubmit", "r1", {"prompt": "go on"})
    [line] = _from_lado("supervisor")
    assert line.summary == (
        "since r1's turn started (its end was not seen) the repository changed: new: esc.md"
    )
    assert _baseline("r1")["state"] == "open"
    _hook("Stop", "r1")
    assert len(_from_lado("supervisor")) == 1


def test_a_turn_s_end_with_nothing_to_compare_writes_its_fingerprint(quiet, lado_home):
    path = base.config_path(state.get_agent("s", "r1")) / hooks.BASELINE
    path.unlink()
    _hook("UserPromptSubmit", "d1", {"prompt": "x"})  # nothing for r1
    state.set_status("s", "r1", state.BUSY)
    _hook("Stop", "r1")
    assert _baseline("r1")["state"] == "closed"
    assert "r1: no fingerprint of its turn's start" in (lado_home / "hooks.log").read_text()
    assert _from_lado("supervisor") == []


def test_a_read_only_supervisor_s_change_is_told_to_the_human(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "watch"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: watch\nversion: 1.0.0\nsupervisor: boss\n")
    (kit / "agents" / "boss.md").write_text(
        "---\nname: boss\ndescription: w\nread_only: true\n---\nWatch.\n"
    )
    runtime.start_session(str(repo), "s", None, provider="claude", kit_names=["watch"])
    _hook("SessionStart", "supervisor")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
    (repo / "a.txt").write_text("x\n")
    _hook("Stop", "supervisor")
    assert [m.summary for m in _from_lado("human")] == [
        "while supervisor's turn the repository changed: new: a.txt"
    ]


def test_a_long_list_is_cut_in_the_line_and_whole_in_the_body_and_the_event(quiet):
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    names = [f"file-with-a-rather-long-name-{n:02}.txt" for n in range(12)]
    for name in names:
        open(f"{_tree('r1')}/{name}", "w").write("x\n")
    _hook("Stop", "r1")
    [line] = _from_lado("supervisor")
    assert len(line.summary) <= state.SUMMARY_LIMIT
    assert line.summary.startswith("while r1's turn the repository changed: new: file-with")
    assert line.summary.endswith("more)")
    assert line.body == "\n".join(f"new: {n}" for n in names)
    assert _events(state.REPO_CHANGED) == [line.body]


def test_a_check_that_fails_is_told_once_and_the_queue_still_goes(quiet, monkeypatch, lado_home):
    def failing(*args):
        raise fingerprint.FingerprintError("git took longer than 2 s")

    monkeypatch.setattr(fingerprint, "take", failing)
    _hook("UserPromptSubmit", "r1", {"prompt": "go"})
    runtime.send_message("s", "supervisor", "r1", "one more")
    output = _hook("Stop", "r1")
    assert json.loads(output)["reason"].startswith("[from supervisor] one more")
    _hook("Stop", "r1", {"stop_hook_active": True})
    assert [m.summary for m in _from_lado("supervisor")] == [
        "could not check r1's repository: git took longer than 2 s"
    ]
    assert _events(state.REPO_CHECK_FAILED) == ["git took longer than 2 s"] * 3
    assert "could not check r1's repository" in (lado_home / "hooks.log").read_text()


def test_with_no_time_left_in_the_hook_no_git_runs(quiet, monkeypatch):
    def no_git(*args):
        raise AssertionError("no git with no time left")

    monkeypatch.setattr(fingerprint, "take", no_git)
    soon = time.monotonic() + fingerprint.MIN_BUDGET / 2
    _hook("UserPromptSubmit", "r1", {"prompt": "go"}, deadline=soon)
    assert _events(state.REPO_CHECK_FAILED) == ["no time left in the hook"]


def test_the_budget_is_what_is_left_before_the_hook_s_deadline(monkeypatch):
    claude = providers.get("claude")
    started = 100.0
    deadline = hooks.deadline(claude, "Stop", started)
    assert deadline == started + 60 - hooks.STARTUP_RESERVE - hooks.QUEUE_RESERVE
    assert hooks.deadline(providers.get("kilo"), "session.idle", started) is None
    monkeypatch.setattr(hooks.time, "monotonic", lambda: deadline - 0.5)
    assert hooks.budget(deadline) == 0.5
    assert hooks.budget(None) == fingerprint.BUDGET
    monkeypatch.setattr(hooks.time, "monotonic", lambda: started)
    assert hooks.budget(deadline) == fingerprint.BUDGET


def test_each_read_only_cli_leaves_the_fingerprint_its_least_time_in_the_turn_s_hooks():
    reserved = hooks.STARTUP_RESERVE + hooks.QUEUE_RESERVE + fingerprint.MIN_BUDGET
    for name in providers.names():
        cli = providers.get(name)
        if not cli.capabilities.deny_edit_tools:
            continue
        # A provider's EVENTS are in its module, or its base's (the OpenCode family).
        module = next(
            sys.modules[c.__module__]
            for c in type(cli).__mro__
            if hasattr(sys.modules[c.__module__], "EVENTS")
        )
        events = module.EVENTS
        turn = [n for n, e in events.items() if e in (base.PROMPT_SUBMIT, base.TURN_END)]
        assert turn, name
        for native in turn:
            limit = cli.hook_limit(native)
            assert limit is None or reserved < limit, (name, native)
