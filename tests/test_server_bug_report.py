"""GET /api/bug-report (lado.bug_report; docs/design/ui.md, Report a bug). In process, with
FastAPI's test client."""

import pytest
from fastapi.testclient import TestClient

from lado import bug_report, telemetry
from lado.server import app as server_app
from lado.server import auth

PORT = 8124


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    return client


def test_the_report_and_its_link(client):
    try:
        raise KeyError("/Users/ann/acme")
    except KeyError as exc:
        telemetry.record("loop", exc, session="billing")
    answer = client.get("/api/bug-report")
    assert answer.status_code == 200, answer.text
    said = answer.json()
    assert set(said) == {"title", "text", "url", "left_out"}
    assert said["title"] == "KeyError at loop"
    assert said["text"].startswith("### What happened\n")
    assert "- KeyError at loop, once, " in said["text"]
    assert "- Server: loopback only, up 0 min, schema " in said["text"]
    assert "- Browser:" not in said["text"]
    assert said["url"].startswith(bug_report.ISSUES_NEW + "?title=KeyError%20at%20loop&body=")
    assert said["left_out"] == 0
    for name in ("/Users/ann", "acme", "billing"):
        assert name not in said["text"] and name not in said["url"]


def test_the_page_s_browser_line_follows_the_system_info(client):
    line = "- Browser: Firefox 131 on Linux"
    said = client.get("/api/bug-report", params={"browser": line}).json()
    assert f"\n{line}\n\n### LADO errors" in said["text"]


@pytest.mark.parametrize(
    "line",
    [
        "- Browser: Firefox 131 on Linux\n- Server: hacked",
        "- Browser: Firefox 131 on Linux\n",
        "- Browser: /Users/ann on Linux",
        "Firefox 131",
        "- Browser: " + "x" * 41 + " on Linux",
    ],
)
def test_a_browser_line_of_another_shape_is_refused(client, line):
    assert client.get("/api/bug-report", params={"browser": line}).status_code == 422


def test_without_the_token_it_is_refused(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    assert client.get("/api/bug-report").status_code == 401
