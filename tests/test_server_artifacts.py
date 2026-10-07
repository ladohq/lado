"""Artifacts in the UI server's API: a session's artifacts, one artifact, a record and its
content under the contract's security rules, and the attachments of messages, notes and
gates (docs/design/artifacts.md, The human's side). In process, with FastAPI's test client."""

import pytest
from fastapi.testclient import TestClient

from lado import artifacts, artifacts_local, runs, runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8123
OWN = "http://testserver"  # the test client's Host
ARTIFACTS = "/api/sessions/s/artifacts"

SHIP = """\
name: ship
description: build and ship
start: build
states:
  build: {agent: supervisor, do: Build it., outcomes: {done: check, polish: polish}}
  polish: {agent: supervisor, do: Polish it., produces: [polish], outcomes: {done: check}}
  check:
    gate: approval
    ask: Ship it?
    reads: [polish]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def session(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    return "s"


@pytest.fixture
def other(repo, fake_tmux):
    """Session "t" with an artifact of its own."""
    state.add_session(state.Session("t", str(repo), None, provider="claude"))
    state.add_agent(state.Agent("t", "supervisor", "x", str(repo), None, None, "idle", "claude"))
    return artifacts.write("t", "supervisor", "theirs", content="not yours")


def test_the_sessions_artifacts_each_with_its_latest_record(client, session):
    artifacts.write("s", "supervisor", "plan", content="v1", title="The plan")
    artifacts.write("s", "supervisor", "plan", content="v22", summary="step two")
    runs.start("s", "ship", "Add x", name="x")
    artifacts.write("s", "supervisor", "ship/x/mockup.html", content="<p>hi</p>")
    answer = client.get(ARTIFACTS)
    assert answer.status_code == 200
    plan, mockup = sorted(answer.json(), key=lambda a: a["full_name"])
    assert plan["latest"]["created_at"].endswith("Z")
    del plan["latest"]["created_at"], plan["id"], plan["latest"]["id"], plan["latest"]["hash"]
    assert plan == {
        "session": "s",
        "scope": "",
        "name": "plan",
        "full_name": "plan",
        "title": "The plan",
        "latest": {
            "media_type": "text/markdown",
            "size": 3,
            "author": "supervisor",
            "run": None,
            "state": None,
            "summary": "step two",
        },
    }
    assert (mockup["full_name"], mockup["scope"], mockup["latest"]["media_type"]) == (
        "ship/x/mockup.html",
        "ship/x",
        "text/html",
    )
    assert (mockup["latest"]["run"], mockup["latest"]["state"]) == ("ship/x", "build")


def test_one_artifact_and_one_record_of_the_session(client, session):
    first = artifacts.write("s", "supervisor", "plan", content="v1")
    latest = artifacts.write("s", "supervisor", "plan", content="v2")
    one = client.get(f"{ARTIFACTS}/{first.artifact.id}").json()
    assert (one["full_name"], one["latest"]["id"]) == ("plan", latest.record.id)
    found = client.get(f"/api/sessions/s/records/{first.record.id}").json()
    assert (found["artifact"]["id"], found["artifact"]["latest"]["id"]) == (
        first.artifact.id,
        latest.record.id,
    )
    assert (found["record"]["id"], found["record"]["hash"]) == (first.record.id, first.record.hash)
    content = client.get(f"/api/sessions/s/records/{first.record.id}/content")
    assert (content.status_code, content.content) == (200, b"v1")


def test_another_sessions_or_an_unknown_artifact_is_404(client, session, other):
    for path in (
        f"{ARTIFACTS}/{other.artifact.id}",
        f"{ARTIFACTS}/no-such-id",
        f"/api/sessions/s/records/{other.record.id}",
        f"/api/sessions/s/records/{other.record.id}/content",
        "/api/sessions/s/records/no-such-id/content",
        "/api/sessions/nobody/artifacts",
    ):
        assert client.get(path).status_code == 404, path


def test_artifacts_need_the_token(session):
    written = artifacts.write("s", "supervisor", "plan", content="v1")
    anonymous = TestClient(server_app.create_app(auth.token(), PORT))
    for path in (
        ARTIFACTS,
        f"{ARTIFACTS}/{written.artifact.id}",
        f"/api/sessions/s/records/{written.record.id}",
        f"/api/sessions/s/records/{written.record.id}/content",
    ):
        assert anonymous.get(path).status_code == 401, path


@pytest.mark.parametrize(
    "media_type, name, download, disposition, csp",
    [
        ("text/markdown", "design", False, 'inline; filename="design.md"', "sandbox"),
        ("text/plain", "notes.txt", False, 'inline; filename="notes.txt"', "sandbox"),
        ("text/html", "mockup.html", False, 'inline; filename="mockup.html"', None),
        ("image/png", "shot.png", False, 'inline; filename="shot.png"', "sandbox"),
        ("image/svg+xml", "logo", False, 'inline; filename="logo.svg"', "sandbox"),
        ("text/x-python", "tool.py", False, 'attachment; filename="tool.py"', "sandbox"),
        ("application/json", "data", False, 'attachment; filename="data.json"', "sandbox"),
        ("application/pdf", "spec.md", False, 'attachment; filename="spec.md.pdf"', "sandbox"),
        ("application/x-thing", "blob", False, 'attachment; filename="blob"', "sandbox"),
        ("text/html", "mockup.html", True, 'attachment; filename="mockup.html"', None),
        ("image/png", "shot.png", True, 'attachment; filename="shot.png"', "sandbox"),
    ],
)
def test_content_headers_by_the_kind_of_media_type(media_type, name, download, disposition, csp):
    headers = server_app._content_headers(media_type, name, download)
    assert headers["Content-Disposition"] == disposition
    assert headers["Content-Security-Policy"] == (csp or "sandbox allow-scripts")
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_only_html_may_run_scripts_in_its_sandbox():
    assert server_app._content_headers("text/html", "a.html", False)["Content-Security-Policy"] == (
        "sandbox allow-scripts"
    )
    for media_type in ("image/svg+xml", "text/markdown", "text/plain", "application/json"):
        headers = server_app._content_headers(media_type, "a", False)
        assert headers["Content-Security-Policy"] == "sandbox", media_type


def test_a_file_name_keeps_no_slash_quote_or_line_break():
    headers = server_app._content_headers("text/plain", 'a/b"c\r\nd\\e.txt', True)
    assert headers["Content-Disposition"] == 'attachment; filename="a_b_c__d_e.txt"'


def test_every_media_type_of_the_extension_table_has_one_extension_that_maps_back():
    for media_type in set(artifacts.EXTENSIONS.values()):
        extension = artifacts.PREFERRED_EXTENSION[media_type]
        assert artifacts.EXTENSIONS[extension] == media_type


def test_content_is_served_with_its_type_and_cached_for_good(client, session):
    written = artifacts.write("s", "supervisor", "mockup.html", content="<p>hi</p>")
    path = f"/api/sessions/s/records/{written.record.id}/content"
    answer = client.get(path)
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "text/html; charset=utf-8"
    assert answer.headers["content-security-policy"] == "sandbox allow-scripts"
    assert answer.headers["x-content-type-options"] == "nosniff"
    assert answer.headers["content-disposition"] == 'inline; filename="mockup.html"'
    assert answer.headers["cache-control"] == "private, max-age=31536000, immutable"
    downloaded = client.get(path, params={"download": 1})
    assert downloaded.headers["content-disposition"] == 'attachment; filename="mockup.html"'


def test_content_missing_from_the_store_is_a_500_never_cached(client, session):
    written = artifacts.write("s", "supervisor", "plan", content="gone")
    store = artifacts_local.LocalStore(state.home())
    store._path(written.record.hash).unlink()
    answer = client.get(f"/api/sessions/s/records/{written.record.id}/content")
    assert answer.status_code == 500
    assert "content of plan is missing from the store" in answer.json()["detail"]
    assert answer.headers["cache-control"] == "no-store"
    assert answer.headers["x-content-type-options"] == "nosniff"


def _attachment(written: artifacts.Written) -> dict:
    return {
        "artifact": written.artifact.id,
        "record": written.record.id,
        "full_name": written.full_name,
        "name": written.artifact.name,
        "scope": written.artifact.scope,
        "title": written.artifact.title,
        "media_type": written.media_type,
        "size": written.size,
        "hash": written.record.hash,
    }


def test_a_message_carries_its_attachments_with_the_attached_records_hash(client, session):
    written = artifacts.write("s", "supervisor", "plan", content="v1", title="Plan")
    runtime.send_message("s", "supervisor", "human", "the plan", attached=["plan"])
    runtime.send_message("s", "supervisor", "human", "no artifacts")
    artifacts.write("s", "supervisor", "plan", content="v2")
    attached, plain = client.get("/api/sessions/s/messages", params={"with": "human"}).json()[
        "items"
    ]
    assert attached["attachments"] == [_attachment(written)]
    assert plain["attachments"] == []


def test_attachments_are_looked_up_only_for_the_rows_that_have_them(client, session, monkeypatch):
    artifacts.write("s", "supervisor", "plan", content="v1")
    runtime.send_message("s", "supervisor", "human", "the plan", attached=["plan"])
    for n in range(5):
        runtime.send_message("s", "supervisor", "human", f"plain {n}")
    looked = []
    real = state._attachments

    def counted(column, row_id):
        looked.append((column, row_id))
        return real(column, row_id)

    monkeypatch.setattr(state, "_attachments", counted)
    client.get("/api/sessions/s/messages", params={"with": "human"})
    client.get("/api/sessions/s/notes")
    client.get("/api/sessions/s/gates")
    assert len(looked) == 1


def _at_gate_from_polish():
    """Run ship/x at gate check, led there from polish with an artifact attached to its note
    besides the polish it produces."""
    runs.start("s", "ship", "Add x", name="x")
    runs.advance("s", "supervisor", "ship/x", "polish", "to polish")
    polish = artifacts.write("s", "supervisor", "ship/x/polish", content="p1")
    written = artifacts.write("s", "supervisor", "ship/x/design", content="d1")
    runs.advance("s", "supervisor", "ship/x", "done", "polished", attached=["ship/x/design"])
    return polish, written


def test_a_note_and_its_gate_carry_the_notes_attachments_and_the_gate_reads_no_one_twice(
    client, session
):
    polish, written = _at_gate_from_polish()
    attached = [_attachment(polish), _attachment(written)]
    notes = client.get("/api/sessions/s/notes").json()
    assert [n["attachments"] for n in notes] == [[], attached]
    [gate] = client.get("/api/sessions/s/gates").json()
    assert gate["attachments"] == attached
    assert gate["reads"] == []  # polish is attached to the note before it


def test_a_closed_gate_keeps_its_notes_attachments_after_the_run_moved_on(client, session):
    polish, written = _at_gate_from_polish()
    runs.answer("s", "1", "reject", "again")
    artifacts.write("s", "supervisor", "ship/x/plan", content="p")
    runs.advance("s", "supervisor", "ship/x", "done", "built", attached=["ship/x/plan"])
    first, second = client.get("/api/sessions/s/gates").json()
    assert first["attachments"] == [_attachment(polish), _attachment(written)]
    assert [a["full_name"] for a in second["attachments"]] == ["ship/x/plan"]
    assert second["reads"] == ["ship/x/polish"]
