"""read_artifact shows an image to the model as MCP image content, within the limits of
the providers' APIs; any other binary gives its facts and why (docs/design/artifacts.md,
Images)."""

import asyncio
import base64
import json

import pytest
from test_images import gif, jpeg, png, vp8x

from lado import artifacts, mcp_server, runtime


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    return "s"


def _read(name, agent="supervisor"):
    return asyncio.run(mcp_server.build("s", agent).call_tool("read_artifact", {"name": name}))


def test_a_text_artifacts_result_is_one_json_text_as_before(session):
    artifacts.write(session, "supervisor", "plan", content="# Plan\n")
    result = _read("plan")
    assert result.structured_content is None
    [text] = result.content
    assert text.type == "text"
    assert text.text == (
        "{\n"
        '  "name": "plan",\n'
        '  "media_type": "text/markdown",\n'
        '  "size": 7,\n'
        '  "lines": 1,\n'
        '  "from_line": 1,\n'
        '  "to_line": 1,\n'
        '  "content": "# Plan\\n",\n'
        '  "cut": false\n'
        "}"
    )


@pytest.mark.parametrize(
    "file_name, data, media_type, size",
    [
        ("shot.png", png(3, 2), "image/png", (3, 2)),
        ("photo.jpg", jpeg(1024, 768), "image/jpeg", (1024, 768)),
        ("anim.gif", gif(640, 480), "image/gif", (640, 480)),
        ("pic.webp", vp8x(8000, 20), "image/webp", (8000, 20)),
    ],
)
def test_an_image_comes_back_as_an_image_with_its_facts(session, file_name, data, media_type, size):
    name = artifacts.upload(session, file_name, data).full_name
    result = _read(name)
    facts, image = result.content
    assert json.loads(facts.text) == {
        "name": name,
        "media_type": media_type,
        "size": len(data),
        "width": size[0],
        "height": size[1],
    }
    assert (image.type, image.mime_type) == ("image", media_type)
    assert base64.b64decode(image.data) == data


def test_a_run_workers_image_facts_name_it_as_it_reads_it(session):
    runtime.spawn_worker(session, "task", name="w1")
    name = artifacts.upload(session, "shot.png", png(3, 2)).full_name
    facts, _ = _read(name, "w1").content
    assert json.loads(facts.text)["name"] == name  # w1 is no run's worker


@pytest.mark.parametrize(
    "data, media_type, note",
    [
        (vp8x(8001, 20), "image/webp", "not shown: it is 8001×20 px, the limit is 8000 px a side"),
        (png(3, 2)[:20], "image/png", "not shown: its header cannot be read as image/png"),
        (b"%PDF-1.7", "application/pdf", artifacts.UNREADABLE),
        (b"\x00\x01", "application/octet-stream", artifacts.UNREADABLE),
    ],
)
def test_an_image_it_cannot_show_or_another_binary_gives_its_facts_and_why(
    session, data, media_type, note
):
    extension = {"image/webp": "webp", "image/png": "png", "application/pdf": "pdf"}
    name = artifacts.upload(session, f"x.{extension.get(media_type, 'bin')}", data).full_name
    [facts] = _read(name).content
    read = json.loads(facts.text)
    assert (read["media_type"], read["size"], read["binary"], read["note"]) == (
        media_type,
        len(data),
        True,
        note,
    )
    assert artifacts.UNREADABLE == (
        "cannot be read by an agent: only text and PNG, JPEG, GIF, WebP images"
    )


def test_an_image_over_the_size_limit_is_not_shown(session, monkeypatch):
    data = png(3, 2)
    monkeypatch.setattr(artifacts, "IMAGE_LIMIT", len(data) - 1)
    name = artifacts.upload(session, "shot.png", data).full_name
    [facts] = _read(name).content
    assert json.loads(facts.text)["note"] == (
        f"not shown: it is {len(data)} bytes, the limit is {len(data) - 1} bytes"
    )


def test_the_limits_are_the_smallest_of_the_providers_apis():
    assert (artifacts.IMAGE_LIMIT, artifacts.IMAGE_MAX_SIDE) == (3_932_160, 8000)
    assert artifacts.AGENT_IMAGES == ("image/png", "image/jpeg", "image/gif", "image/webp")
