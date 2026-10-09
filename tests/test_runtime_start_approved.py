"""The supervisor starts a session the human approved (runtime.start_approved_session)."""

import pytest

from lado import artifacts, providers, runtime, state, tmux

CHOICE_B = runtime.START_CHOICE.format(name="b")


@pytest.fixture
def team_kit(repo):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "skills" / "style").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "skills" / "style" / "SKILL.md").write_text("---\nname: style\ndescription: d\n---\n")
    return kit


@pytest.fixture
def a(repo, fake_tmux, team_kit):
    """Session "a" with its own settings, a worker w1 and a brief by the supervisor."""
    runtime.start_session(
        str(repo),
        "a",
        "plan",
        provider="claude",
        kit_names=["default", "team"],
        without=["skill:style"],
    )
    runtime.spawn_worker("a", "do x", name="w1")
    artifacts.write("a", "supervisor", "brief-b", content="# Fix the bug\n", title="Brief")
    return "a"


def _ask(session="a", sender="supervisor", choices=(CHOICE_B, "No"), attached=("brief-b",)):
    text = runtime.ask_human(
        session, sender, "Start a session for the bug?", choices=list(choices), attached=attached
    )
    return int(text.split("#")[1].split()[0])


def _approved(choice=CHOICE_B, comment=None, **ask):
    question = _ask(**ask)
    runtime.answer_question("a", question, choice, comment)
    return question


def test_an_approved_question_starts_the_session_with_the_callers_settings(a, repo, fake_tmux):
    question = _approved()
    started = runtime.start_approved_session("a", "supervisor", "b", question)
    assert (started.session.name, started.resumed, started.lead) == (
        "b",
        False,
        "lead: supervisor of kit default",
    )
    b = state.get_session("b")
    assert (b.repo, b.provider, b.permission_mode, b.kits, b.without) == (
        str(repo),
        "claude",
        "plan",
        ["default", "team"],
        ["skill:style"],
    )
    assert [c[1] for c in fake_tmux if c[0] == "new_session"] == ["a", "b"]
    assert state.get_agent("b", "supervisor").status == state.STARTING


def test_the_brief_is_copied_and_attached_to_the_new_supervisors_first_message(a, tmp_path):
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 30)
    artifacts.write("a", "w1", "shot.png", file=str(shot))
    question = _approved(comment="look at the log too", attached=("brief-b", "shot.png"))
    runtime.start_approved_session("a", "supervisor", "b", question)
    [first] = state.list_messages("b")
    assert (first.sender, first.recipient, first.state) == ("lado", "supervisor", state.PENDING)
    assert first.summary == f"session started from a/supervisor's proposal #{question}"
    assert "Start a session for the bug?" in first.body
    assert "brief-b (by a/supervisor)" in first.body
    assert "shot.png (by a/w1)" in first.body
    assert "look at the log too" in first.body
    assert "read it with read_artifact" in first.body
    copies = artifacts.attached(state.message_attachments(first.id))
    assert [(c.artifact.session, c.artifact.name, c.record.author) for c in copies] == [
        ("b", "brief-b", "lado"),
        ("b", "shot.png", "lado"),
    ]
    assert artifacts.content(copies[0].record) == b"# Fix the bug\n"


def test_the_brief_never_reaches_the_command_line_or_the_role(a, fake_tmux):
    artifacts.write("a", "supervisor", "brief-b", content="SECRET-BRIEF-TEXT\n")
    runtime.start_approved_session("a", "supervisor", "b", _approved())
    [call] = [c for c in fake_tmux if c[0] == "new_session" and c[1] == "b"]
    assert "SECRET-BRIEF-TEXT" not in repr(call)
    config = providers.base.config_path(state.get_agent("b", "supervisor"))
    assert all("SECRET-BRIEF-TEXT" not in p.read_text(errors="replace") for p in _files(config))


def _files(folder):
    return [p for p in folder.rglob("*") if p.is_file()]


def test_the_supervisor_is_told_how_to_propose_a_session(a, fake_tmux):
    config = providers.base.config_path(state.get_agent("a", "supervisor"))
    prompt = (config / "prompt.md").read_text()
    assert runtime.START_CHOICE.format(name="<name>") in prompt
    assert "start_session(name, question)" in prompt


@pytest.mark.parametrize(
    "agent, name, refusal",
    [
        ("w1", "b", "only the supervisor"),
        ("supervisor", "B b", 'no valid session name: "B b"'),
    ],
)
def test_a_caller_or_name_that_is_not_allowed_is_refused(a, agent, name, refusal):
    question = _approved()
    with pytest.raises(runtime.LadoError, match=refusal):
        runtime.start_approved_session("a", agent, name, question)
    assert state.get_session("b") is None


def test_an_unknown_message_or_one_that_is_no_question_is_refused(a):
    with pytest.raises(runtime.LadoError, match="no question #999 of supervisor in session a"):
        runtime.start_approved_session("a", "supervisor", "b", 999)
    state.queue_message("a", "w1", "supervisor", "hi")
    [message] = [m for m in state.list_messages("a") if m.summary == "hi"]
    with pytest.raises(runtime.LadoError, match=f"no question #{message.id} of supervisor"):
        runtime.start_approved_session("a", "supervisor", "b", message.id)


def test_another_agents_question_is_refused(a):
    artifacts.write("a", "w1", "brief-w", content="x")
    question = _approved(sender="w1", attached=("brief-w",))
    with pytest.raises(runtime.LadoError, match=f"no question #{question} of supervisor"):
        runtime.start_approved_session("a", "supervisor", "b", question)


def test_another_sessions_question_is_refused(a, repo):
    runtime.start_session(str(repo), "c", None, provider="claude")
    artifacts.write("c", "supervisor", "brief-b", content="x")
    question = _ask(session="c")
    runtime.answer_question("c", question, CHOICE_B)
    with pytest.raises(runtime.LadoError, match=f"no question #{question} of supervisor"):
        runtime.start_approved_session("a", "supervisor", "b", question)


def test_a_question_not_approved_for_that_name_is_refused(a):
    open_question = _ask()
    dismissed = _ask()
    runtime.dismiss_question("a", dismissed)
    declined = _approved(choice="No")
    other_name = _approved(
        choice=runtime.START_CHOICE.format(name="c"),
        choices=(runtime.START_CHOICE.format(name="c"),),
    )
    for question in (open_question, dismissed, declined, other_name):
        with pytest.raises(
            runtime.LadoError,
            match=f"the human has not approved starting session b with question #{question}",
        ):
            runtime.start_approved_session("a", "supervisor", "b", question)
    assert state.get_session("b") is None


def test_a_free_answer_is_no_approval(a):
    question = _ask()
    runtime.answer_question("a", question, None, CHOICE_B)  # typed, not the choice
    with pytest.raises(runtime.LadoError, match="has not approved"):
        runtime.start_approved_session("a", "supervisor", "b", question)


def test_a_question_without_an_attachment_is_refused(a):
    question = _approved(attached=())
    with pytest.raises(runtime.LadoError, match="no brief attached"):
        runtime.start_approved_session("a", "supervisor", "b", question)
    assert state.get_session("b") is None


def test_two_attachments_of_one_name_are_refused(a):
    state.add_run(
        state.Run(
            session="a",
            name="feature/x",
            flow="feature",
            snapshot='{"name": "feature"}',
            kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
            task="t",
            state="design",
            worktree="/w",
            branch="lado/a/x",
            visits={"design": 1},
        ),
        [],
    )
    artifacts.write("a", "supervisor", "feature/x/brief-b", content="run's")
    question = _approved(attached=("brief-b", "feature/x/brief-b"))
    with pytest.raises(runtime.LadoError, match='two attached artifacts are named "brief-b"'):
        runtime.start_approved_session("a", "supervisor", "b", question)
    assert state.get_session("b") is None


def test_one_approval_starts_one_session(a):
    question = _approved()
    runtime.start_approved_session("a", "supervisor", "b", question)
    with pytest.raises(runtime.SessionExists):
        runtime.start_approved_session("a", "supervisor", "b", question)
    assert len(state.list_messages("b")) == 1  # nothing copied or queued again


def test_a_stopped_session_of_that_name_is_not_resumed(a, repo):
    runtime.start_session(str(repo), "b", None, provider="claude")
    runtime.stop_session("b")
    with pytest.raises(runtime.SessionExists):
        runtime.start_approved_session("a", "supervisor", "b", _approved())
    assert state.get_session("b").stopped_at


def test_a_failed_start_leaves_no_session_and_no_copy(a, monkeypatch):
    question = _approved()

    def fail(*args, **kwargs):
        raise tmux.TmuxError("no tmux today")

    monkeypatch.setattr(tmux, "new_session", fail)
    with pytest.raises(tmux.TmuxError):
        runtime.start_approved_session("a", "supervisor", "b", question)
    assert state.get_session("b") is None
    assert artifacts.store().list("b") == []
    assert state.list_messages("b") == []


def test_first_is_only_for_a_new_session(repo, fake_tmux):
    first = runtime.FirstInput("hello", "body", [])
    for resume in (None, True):
        with pytest.raises(runtime.LadoError, match="only for a new session"):
            runtime.start_session(
                str(repo), "b", None, provider="claude", resume=resume, first=first
            )
