import dataclasses
import re

import pytest

from lado import artifacts, state


def _agent(name, run=None, cwd="/r"):
    return state.Agent("s", name, "worker", cwd, None, None, state.IDLE, "claude", run=run)


def _run(name, status=state.ACTIVE, at="design", visits=None):
    run = state.Run(
        session="s",
        name=name,
        flow="feature",
        snapshot='{"name": "feature"}',
        kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
        task="add x",
        state=at,
        worktree="/w",
        branch="lado/s/x",
        visits=visits or {at: 1},
    )
    return dataclasses.replace(run, status=status)


@pytest.fixture
def session(lado_home, tmp_path):
    """Session "s": the supervisor in the repo, w1 a worker of run feature/x (in design, its
    second visit), w2 a worker of no run; feature/y is open too, feature/z ended."""
    state.add_session(state.Session("s", str(tmp_path), None, provider="claude"))
    state.add_agent(_agent("supervisor", cwd=str(tmp_path)))
    state.add_agent(_agent("w1", run="feature/x", cwd=str(tmp_path / "w1")))
    state.add_agent(_agent("w2", cwd=str(tmp_path / "w2")))
    state.add_run(_run("feature/x", visits={"plan": 1, "design": 2}), [])
    state.add_run(_run("feature/y", at="review"), [])
    state.add_run(_run("feature/z", status=state.ENDED), [])
    return "s"


def test_an_artifact_is_written_and_read_back_in_the_session_scope(session):
    written = artifacts.write(session, "supervisor", "plan", content="# Plan\nstep one\n")
    assert (written.full_name, written.status, written.size, written.media_type) == (
        "plan",
        "created",
        16,
        "text/markdown",
    )
    read = artifacts.read(session, "w2", "plan")
    assert read["content"] == "# Plan\nstep one\n"
    assert (read["name"], read["lines"], read["cut"]) == ("plan", 2, False)


def test_a_bare_name_is_in_a_run_workers_run_and_in_the_session_for_the_others(session):
    artifacts.write(session, "w1", "design", content="run's")
    artifacts.write(session, "supervisor", "design", content="session's")
    assert artifacts.read(session, "w1", "design")["content"] == "run's"
    assert artifacts.read(session, "w1", "feature/x/design")["name"] == "feature/x/design"
    assert artifacts.read(session, "w2", "design")["content"] == "session's"
    assert artifacts.read(session, "supervisor", "design")["content"] == "session's"
    assert artifacts.read(session, "supervisor", "feature/x/design")["content"] == "run's"


def test_a_name_not_found_says_which_full_name_was_looked_up(session):
    artifacts.write(session, "supervisor", "plan", content="x")
    with pytest.raises(artifacts.ArtifactError, match='no artifact "feature/x/plan"'):
        artifacts.read(session, "w1", "plan")  # no fallback to the session's scope
    with pytest.raises(artifacts.ArtifactError, match='no artifact "feature/y/plan"'):
        artifacts.read(session, "supervisor", "feature/y/plan")


@pytest.mark.parametrize(
    "agent, name, allowed",
    [
        ("w1", "feature/y/design", 'only to run feature/x\'s scope: "design" or "feature/x/'),
        ("w2", "feature/x/design", "only to the session's scope"),
        ("supervisor", "feature/z/design", "run feature/z is ended"),
        ("supervisor", "feature/q/design", 'no run "feature/q"'),
    ],
)
def test_who_may_write_where_and_the_refusal_names_the_allowed_scope(session, agent, name, allowed):
    with pytest.raises(artifacts.ArtifactError, match=re.escape(allowed)):
        artifacts.write(session, agent, name, content="x")
    assert artifacts.store().list(session) == []


def test_the_supervisor_writes_to_the_session_and_any_open_run(session):
    for name in ("plan", "feature/x/plan", "feature/y/plan"):
        assert artifacts.write(session, "supervisor", name, content="x").full_name == name
    assert artifacts.write(session, "w1", "feature/x/notes", content="x").full_name == (
        "feature/x/notes"
    )


def test_a_write_in_a_runs_scope_keeps_the_run_its_state_and_the_states_visit(session):
    record = artifacts.write(session, "w1", "design", content="x").record
    assert (record.run, record.state, record.visit, record.author) == (
        "feature/x",
        "design",
        2,
        "w1",
    )
    record = artifacts.write(session, "supervisor", "feature/y/review", content="x").record
    assert (record.run, record.state, record.visit) == ("feature/y", "review", 1)
    record = artifacts.write(session, "w2", "notes", content="x").record
    assert (record.run, record.state, record.visit) == (None, None, None)


def test_a_worker_of_a_closed_run_writes_nothing(session):
    state.add_agent(_agent("w3", run="feature/z"))
    with pytest.raises(artifacts.ArtifactError, match="run feature/z is ended"):
        artifacts.write(session, "w3", "design", content="x")


def test_a_relative_file_is_read_from_the_folder_the_agent_was_started_in(
    session, tmp_path, monkeypatch
):
    (tmp_path / "w2").mkdir()
    (tmp_path / "w2" / "report.md").write_text("from w2's folder")
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "report.md").write_text("from the process's cwd")
    monkeypatch.chdir(tmp_path / "elsewhere")
    written = artifacts.write(session, "w2", "report", file="report.md")
    assert artifacts.read(session, "w2", "report")["content"] == "from w2's folder"
    assert (written.status, written.media_type) == ("created", "text/markdown")
    absolute = artifacts.write(session, "w2", "other", file=str(tmp_path / "elsewhere/report.md"))
    assert absolute.size == len("from the process's cwd")


@pytest.mark.parametrize(
    "arguments, refusal",
    [
        ({}, "exactly one of content and file"),
        ({"content": "x", "file": "x.md"}, "exactly one of content and file"),
        ({"file": "missing.md"}, "no file"),
        ({"file": "."}, "not a regular file"),
    ],
)
def test_a_write_takes_content_or_an_existing_file(session, arguments, refusal):
    with pytest.raises(artifacts.ArtifactError, match=refusal):
        artifacts.write(session, "supervisor", "plan", **arguments)


@pytest.mark.parametrize(
    "name", ["", "Plan", "-plan", "my plan", "a" * 65, "plan/", "feature/x/.plan"]
)
def test_a_name_is_lower_case_letters_digits_dash_underscore_and_dot(session, name):
    with pytest.raises(artifacts.ArtifactError, match="a name is 1-64 characters"):
        artifacts.write(session, "supervisor", name, content="x")


def test_names_at_the_limits_are_taken(session):
    for name in ("a", "9" + "a" * 63, "mockup.v2_final-1.html"):
        assert artifacts.write(session, "supervisor", name, content="x").full_name == name


@pytest.mark.parametrize("field", ["title", "summary"])
def test_a_title_and_a_summary_are_one_line_of_at_most_200_characters(session, field):
    artifacts.write(session, "supervisor", "plan", content="x", **{field: "t" * 200})
    for bad in ("t" * 201, "two\nlines"):
        with pytest.raises(artifacts.ArtifactError, match=f"{field} must be one line of at most"):
            artifacts.write(session, "supervisor", "plan", content="x", **{field: bad})


def test_a_record_over_the_limit_is_refused_with_the_limit(session, tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "MAX_SIZE", 10)
    (tmp_path / "big.bin").write_bytes(b"x" * 11)
    for arguments in ({"content": "x" * 11}, {"file": str(tmp_path / "big.bin")}):
        with pytest.raises(artifacts.ArtifactError, match="11 bytes, the limit is 10 bytes"):
            artifacts.write(session, "supervisor", "big", **arguments)
    assert artifacts.write(session, "supervisor", "big", content="x" * 10).size == 10


@pytest.mark.parametrize(
    "arguments, media_type",
    [
        ({"name": "plan", "content": "x"}, "text/markdown"),
        ({"name": "data.json", "content": "{}"}, "application/json"),
        ({"name": "data", "content": "{}", "media_type": "application/json"}, "application/json"),
        ({"name": "page", "file": "page.html"}, "text/html"),
        ({"name": "page.txt", "file": "page.html"}, "text/html"),  # the file's first
        ({"name": "logo.png", "file": "logo"}, "image/png"),  # else the name's
        ({"name": "blob", "file": "logo"}, "application/octet-stream"),
        ({"name": "mock", "file": "page.html", "media_type": "text/plain"}, "text/plain"),
    ],
)
def test_the_media_type_is_given_else_by_the_files_or_the_names_extension(
    session, tmp_path, arguments, media_type
):
    (tmp_path / "page.html").write_text("<p>hi</p>")
    (tmp_path / "logo").write_bytes(b"\x89PNG")
    assert artifacts.write(session, "supervisor", **arguments).media_type == media_type


def test_every_code_and_text_extension_reads_as_text_and_ts_is_no_video():
    for extension in ("md", "markdown", "txt", "log", "json", "yaml", "yml", "csv", "html"):
        assert artifacts.is_text(artifacts.EXTENSIONS[extension]), extension
    for extension in ("htm", "svg", "py", "ts", "tsx", "js", "sh", "toml", "xml"):
        assert artifacts.is_text(artifacts.EXTENSIONS[extension]), extension
    for extension in ("png", "jpg", "jpeg", "gif", "webp", "pdf"):
        assert not artifacts.is_text(artifacts.EXTENSIONS[extension]), extension
    assert artifacts.EXTENSIONS["ts"] == "text/typescript"
    assert not artifacts.is_text("application/octet-stream")


def test_a_media_type_given_must_be_one(session):
    with pytest.raises(artifacts.ArtifactError, match='media_type "markdown" is no media type'):
        artifacts.write(session, "supervisor", "plan", content="x", media_type="markdown")


def test_the_same_content_again_is_an_unchanged_record_and_a_title_given_stays(session):
    first = artifacts.write(session, "supervisor", "plan", content="v1", title="The plan")
    again = artifacts.write(session, "supervisor", "plan", content="v1", summary="no change")
    other = artifacts.write(session, "supervisor", "plan", content="v2")
    assert [first.status, again.status, other.status] == ["created", "unchanged", "created"]
    assert first.record.id != again.record.id and again.record.hash == first.record.hash
    assert again.artifact.title == other.artifact.title == "The plan"
    renamed = artifacts.write(session, "supervisor", "plan", content="v2", title="Plan B")
    assert renamed.status == "unchanged" and renamed.artifact.title == "Plan B"
    artifact, latest = artifacts.store().latest(session, "", "plan")
    assert latest.id == renamed.record.id and artifact.id == first.artifact.id


def test_a_long_text_is_read_cut_with_its_lines_and_by_a_line_range(session, monkeypatch):
    artifacts.write(
        session, "supervisor", "log", content="".join(f"line {n}\n" for n in range(1, 11))
    )
    monkeypatch.setattr(artifacts, "READ_LIMIT", 21)  # three lines of 7 characters
    read = artifacts.read(session, "supervisor", "log")
    assert (read["content"], read["lines"], read["from_line"], read["to_line"], read["cut"]) == (
        "line 1\nline 2\nline 3\n",
        10,
        1,
        3,
        True,
    )
    read = artifacts.read(session, "supervisor", "log", from_line=9)
    assert (read["content"], read["to_line"], read["cut"]) == ("line 9\nline 10\n", 10, False)
    read = artifacts.read(session, "supervisor", "log", from_line=2, to_line=3)
    assert (read["content"], read["cut"]) == ("line 2\nline 3\n", False)
    with pytest.raises(artifacts.ArtifactError, match="has 10 lines"):
        artifacts.read(session, "supervisor", "log", from_line=11)
    with pytest.raises(artifacts.ArtifactError, match="from_line and to_line"):
        artifacts.read(session, "supervisor", "log", from_line=3, to_line=2)


def test_a_single_line_over_the_limit_is_cut_by_characters(session, monkeypatch):
    artifacts.write(session, "supervisor", "blob.txt", content="x" * 50)
    monkeypatch.setattr(artifacts, "READ_LIMIT", 20)
    read = artifacts.read(session, "supervisor", "blob.txt")
    assert (read["content"], read["to_line"], read["cut"]) == ("x" * 20, 1, True)


def test_a_binary_artifact_gives_its_metadata_only(session, tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    artifacts.write(session, "supervisor", "logo", file="logo.png")
    assert artifacts.read(session, "w2", "logo") == {
        "name": "logo",
        "media_type": "image/png",
        "size": 6,
        "binary": True,
        "note": "cannot be read as text",
    }


def test_text_that_is_not_utf8_is_read_with_replacement_characters(session, tmp_path):
    (tmp_path / "latin.txt").write_bytes(b"caf\xe9\n")
    artifacts.write(session, "supervisor", "latin", file="latin.txt")
    assert artifacts.read(session, "w2", "latin")["content"] == "caf�\n"
