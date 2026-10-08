"""The human's files: uploads to the session's scope, read by every agent as `/<name>`
(docs/design/artifacts.md, The human's side; Names and scopes)."""

import pytest

from lado import artifacts, state

# sha256(b"abc") begins with ba7816bf
ABC = "ba7816bf"


def _agent(name, run=None, cwd="/r"):
    return state.Agent("s", name, "worker", cwd, None, None, state.IDLE, "claude", run=run)


@pytest.fixture
def session(lado_home, tmp_path):
    """Session "s": the supervisor, w1 a worker of run feature/x, w2 a worker of no run."""
    state.add_session(state.Session("s", str(tmp_path), None, provider="claude"))
    state.add_agent(_agent("supervisor", cwd=str(tmp_path)))
    state.add_agent(_agent("w1", run="feature/x", cwd=str(tmp_path / "w1")))
    state.add_agent(_agent("w2", cwd=str(tmp_path / "w2")))
    run = state.Run(
        session="s",
        name="feature/x",
        flow="feature",
        snapshot='{"name": "feature"}',
        kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
        task="add x",
        state="design",
        worktree="/w",
        branch="lado/s/x",
        visits={"design": 1},
    )
    state.add_run(run, [])
    return "s"


def test_an_upload_is_the_sessions_by_the_human_named_by_its_stem_hash_and_extension(session):
    written = artifacts.upload(session, "Screenshot 2026-10-08.PNG", b"abc")
    artifact, record = written.artifact, written.record
    assert artifact.full_name == f"screenshot-2026-10-08-{ABC}.png"
    assert (artifact.scope, artifact.title) == ("", "Screenshot 2026-10-08.PNG")
    assert (record.author, record.media_type, record.size) == ("human", "image/png", 3)
    assert (record.run, record.state, record.visit) == (None, None, None)
    assert record.summary == "attached by the human"
    assert artifacts.content(record) == b"abc"


@pytest.mark.parametrize(
    "given, name",
    [
        ("notes.txt", f"notes-{ABC}.txt"),
        ("build.LOG", f"build-{ABC}.log"),
        ("archive.tar.gz", f"archive.tar-{ABC}"),  # gz is no known extension: none
        ("Bug report (v2)!.md", f"bug-report-v2-{ABC}.md"),
        ("Отчёт.md", f"file-{ABC}.md"),
        ("---.md", f"file-{ABC}.md"),
        (".env", f"env-{ABC}"),
        ("__init__.py", f"init__-{ABC}.py"),
        ("a  __ b.json", f"a-__-b-{ABC}.json"),
        ("x" * 60 + ".txt", "x" * 40 + f"-{ABC}.txt"),
        ("noext", f"noext-{ABC}"),
    ],
)
def test_an_uploads_name_is_made_valid(session, given, name):
    assert artifacts.upload(session, given, b"abc").full_name == name
    assert artifacts.NAME.fullmatch(name)


def test_the_same_file_again_returns_its_record_and_writes_nothing(session):
    first = artifacts.upload(session, "log.txt", b"abc")
    again = artifacts.upload(session, "log.txt", b"abc")
    assert again.record == first.record
    [(_, latest)] = artifacts.of_session(session)
    assert latest == first.record
    with state.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM artifact_records").fetchone()[0] == 1


def test_an_upload_to_a_stopped_session_is_refused(session):
    state.stop_session(session)
    with pytest.raises(artifacts.ArtifactError, match='session "s" is stopped'):
        artifacts.upload(session, "log.txt", b"abc")
    assert artifacts.of_session(session) == []


def test_an_upload_over_the_limit_or_without_a_name_is_refused(session, monkeypatch):
    monkeypatch.setattr(artifacts, "MAX_SIZE", 2)
    with pytest.raises(artifacts.ArtifactError, match="the limit is 2 bytes"):
        artifacts.upload(session, "log.txt", b"abc")
    with pytest.raises(artifacts.ArtifactError, match="the file has no name"):
        artifacts.upload(session, "  ", b"ab")
    assert artifacts.of_session(session) == []


def test_every_agent_reads_a_session_artifact_by_slash_name(session):
    name = artifacts.upload(session, "notes.txt", b"abc").full_name
    for agent in ("w1", "w2", "supervisor"):
        assert artifacts.read(session, agent, f"/{name}")["content"] == "abc"
    # a run's worker is told the name it reads it by
    assert artifacts.read(session, "w1", f"/{name}")["name"] == f"/{name}"
    assert artifacts.read(session, "w2", f"/{name}")["name"] == name
    assert artifacts.read(session, "w2", name)["name"] == name


def test_a_runs_worker_may_not_write_to_the_sessions_scope_by_slash_name(session):
    with pytest.raises(artifacts.ArtifactError, match="may write only to run feature/x's scope"):
        artifacts.write(session, "w1", "/plan", content="x")
    assert artifacts.of_session(session) == []


def test_session_names_are_slash_names_for_a_runs_worker_only(session):
    upload = artifacts.upload(session, "notes.txt", b"abc")
    design = artifacts.write(session, "w1", "design", content="d")
    attachments = [(upload.artifact.id, upload.record.id), (design.artifact.id, design.record.id)]
    session_name = upload.full_name

    def names(read):
        return [a["name"] for a in read]

    assert names(artifacts.read_attachments(attachments, "feature/x")) == [
        f"/{session_name}",
        "feature/x/design",
    ]
    assert names(artifacts.read_attachments(attachments)) == [session_name, "feature/x/design"]
    assert artifacts.attached_line(attachments, "feature/x") == (
        f"Artifacts: /{session_name}, feature/x/design"
    )
    assert artifacts.attached_line(attachments) == f"Artifacts: {session_name}, feature/x/design"
