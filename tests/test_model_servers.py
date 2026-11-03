"""lado.model_servers: what a model server is, from its address, against the fake servers of
tests/fake_model_server.py (real HTTP on 127.0.0.1)."""

import socket
import time
from types import SimpleNamespace

import fake_model_server as fake
import pytest

from lado import model_servers as ms
from lado.providers import base

PROBED = [
    ("GET", fake.MODELS),
    ("GET", fake.MODELS),  # once more with anthropic-version
    ("GET", fake.OLLAMA_VERSION),
    ("GET", fake.LMSTUDIO_MODELS),
    ("POST", fake.CHAT),
    ("POST", fake.RESPONSES),
    ("POST", fake.MESSAGES),
    ("POST", fake.CONTROL),
]


@pytest.fixture
def serve():
    servers = []

    def start(profile, **kwargs):
        server = fake.Server(profile, **kwargs)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


@pytest.fixture(autouse=True)
def outside_container(monkeypatch):
    monkeypatch.delenv("LADO_CONTAINER", raising=False)


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# The CLIs follow from the APIs a server proves.


def test_ollama_two_apis(serve):
    server = serve("ollama")
    probe = ms.probe(server.url)
    assert probe.kind == "Ollama"
    assert probe.models == fake.OLLAMA_MODELS
    suits, not_suits = probe.clis()
    assert suits == [
        ("Kilo CLI", base.CHAT_COMPLETIONS),
        ("OpenCode", base.CHAT_COMPLETIONS),
        ("Codex CLI", base.RESPONSES),
    ]
    assert not_suits == [("Claude Code", base.ANTHROPIC_MESSAGES)]
    assert ms.lines(probe) == [
        server.url,
        "type: Ollama",
        "models: llama3.1:8b, qwen2.5-coder:7b",
        "CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)",
        "not: Claude Code (no Anthropic Messages API)",
    ]


def test_openai_chat_only(serve):
    probe = ms.probe(serve("openai").url)
    assert probe.kind == "OpenAI-compatible"
    assert probe.apis == {base.CHAT_COMPLETIONS}
    suits, not_suits = probe.clis()
    assert [t for t, _ in suits] == ["Kilo CLI", "OpenCode"]
    assert not_suits == [("Codex CLI", base.RESPONSES), ("Claude Code", base.ANTHROPIC_MESSAGES)]
    assert ms.lines(probe)[-1] == (
        "not: Codex CLI (no Responses API), Claude Code (no Anthropic Messages API)"
    )


def test_responses_only(serve):
    probe = ms.probe(serve("responses-only").url)
    assert probe.kind == "OpenAI-compatible"  # by the API it proved: no list
    assert probe.models is None
    assert probe.clis()[0] == [("Codex CLI", base.RESPONSES)]


def test_anthropic_messages_only(serve):
    probe = ms.probe(serve("anthropic").url)
    assert probe.kind == "Anthropic-compatible"
    assert probe.models == ("claude-x",)
    assert probe.clis()[0] == [("Claude Code", base.ANTHROPIC_MESSAGES)]
    assert [t for t, _ in probe.clis()[1]] == ["Kilo CLI", "OpenCode", "Codex CLI"]


def test_models_only_proves_no_api(serve):
    probe = ms.probe(serve("models-only").url)
    assert probe.kind == "OpenAI-compatible"
    assert probe.apis == frozenset()
    lines = ms.lines(probe)
    assert "CLIs: none" in lines
    assert lines[-1] == (
        "not: Kilo CLI (no chat completions), OpenCode (no chat completions), "
        "Codex CLI (no Responses API), Claude Code (no Anthropic Messages API)"
    )


def test_all_three_apis(serve):
    probe = ms.probe(serve("all").url)
    assert probe.apis == set(base.SERVER_APIS)
    assert probe.clis()[1] == []
    lines = ms.lines(probe)
    assert lines[-1] == (
        "CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API); "
        "Claude Code (Anthropic Messages API)"
    )
    assert not any(line.startswith("not:") for line in lines)


def test_a_provider_without_an_api_is_left_out(serve, monkeypatch):
    registry = {"stand-in": SimpleNamespace(name="stand-in", title="Stand-in", server_api="")}
    monkeypatch.setattr(ms.providers, "_PROVIDERS", {**ms.providers._PROVIDERS, **registry})
    suits, not_suits = ms.probe(serve("all").url).clis()
    assert "Stand-in" not in [t for t, _ in suits + not_suits]


# The server's type.


def test_lmstudio_type(serve):
    assert ms.probe(serve("lmstudio").url).kind == "LM Studio"


# Embeddings models are marked.


def test_lmstudio_s_embeddings_models_are_marked(serve):
    probe = ms.probe(serve("lmstudio").url)
    assert probe.embeddings == {fake.EMBEDDINGS}
    assert ms.lines(probe)[2] == f"models: qwen3-8b, {fake.EMBEDDINGS} (embeddings)"


def test_no_mark_without_lm_studio_s_types(serve, monkeypatch):
    probe = ms.probe(serve("ollama").url)
    assert probe.embeddings == frozenset()
    assert ms.lines(probe)[2] == "models: llama3.1:8b, qwen2.5-coder:7b"
    # An answer of /api/v0/models without types, or with odd ones, marks nothing.
    monkeypatch.setitem(
        fake.PROFILES,
        "lmstudio-untyped",
        {
            ("GET", fake.MODELS): fake.openai_list("a", "b"),
            ("GET", fake.LMSTUDIO_MODELS): fake.Answer(
                200, {"data": [{"id": "a"}, {"id": "b", "type": ["embeddings"]}, "c"]}
            ),
            ("POST", fake.CHAT): fake.OPENAI_400,
        },
    )
    probe = ms.probe(serve("lmstudio-untyped").url)
    assert (probe.kind, probe.embeddings) == ("LM Studio", frozenset())
    assert ms.lines(probe)[2] == "models: a, b"


def test_an_embeddings_id_is_one_line_of_visible_text(serve, monkeypatch):
    monkeypatch.setitem(
        fake.PROFILES,
        "lmstudio-odd",
        {
            ("GET", fake.MODELS): fake.openai_list("e\nx"),
            ("GET", fake.LMSTUDIO_MODELS): fake.Answer(
                200, {"data": [{"id": "e\nx", "type": "embeddings"}]}
            ),
            ("POST", fake.CHAT): fake.OPENAI_400,
        },
    )
    probe = ms.probe(serve("lmstudio-odd").url)
    assert ms.lines(probe)[2] == "models: e x (embeddings)"


def test_anthropic_shape_type(serve):
    assert ms.probe(serve("anthropic").url).kind == "Anthropic-compatible"


def test_type_by_api_without_models(serve):
    assert ms.probe(serve("messages-only").url).kind == "Anthropic-compatible"
    assert ms.probe(serve("responses-only").url).kind == "OpenAI-compatible"


def test_a_gateway_of_both_apis_is_openai_compatible(serve):
    """LiteLLM lists in Anthropic's shape only when asked with anthropic-version."""
    probe = ms.probe(serve("litellm").url)
    assert probe.kind == "OpenAI-compatible"
    assert probe.models == fake.LITELLM_MODELS  # once each
    assert probe.apis == set(base.SERVER_APIS)
    assert not any(line.startswith("not:") for line in ms.lines(probe))


def test_an_anthropic_api_listing_only_with_its_header(serve):
    probe = ms.probe(serve("anthropic-versioned").url)
    assert (probe.kind, probe.models) == ("Anthropic-compatible", ("claude-x",))
    assert ms.lines(probe)[2] == "models: claude-x"
    assert probe.models_why == ""  # a list: no why left over from the plain request


def test_a_list_that_fails_both_ways_keeps_its_why(serve, monkeypatch):
    monkeypatch.setitem(
        fake.PROFILES,
        "list-500-both",
        {
            ("GET", fake.MODELS): fake.Answer(500, {"error": "internal error"}),
            ("GET", fake.MODELS, fake.VERSIONED): fake.Answer(500, {"error": "internal error"}),
            ("POST", fake.MESSAGES): fake.ANTHROPIC_400,
        },
    )
    probe = ms.probe(serve("list-500-both").url)
    assert (probe.models, probe.models_why) == (None, "GET /v1/models: 500")


@pytest.mark.parametrize(
    ("profile", "field"),
    [("closed", "address"), ("forbidden", "key"), ("unknown", "address")],
)
def test_a_probe_error_names_its_field(serve, profile, field):
    if profile == "closed":
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            url = f"http://127.0.0.1:{s.getsockname()[1]}"
    else:
        url = serve(profile).url
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(url)
    assert raised.value.field == field


def test_a_refused_key_and_an_uncarriable_one_name_the_key(serve):
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(serve("openai", key="k-1").url, "wrong")
    assert raised.value.field == "key"
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(serve("openai").url, "a\nb")
    assert raised.value.field == "key"


def test_the_list_without_the_header_wins(serve, monkeypatch):
    monkeypatch.setitem(
        fake.PROFILES,
        "mixed",
        {
            ("GET", fake.MODELS): fake.openai_list("gpt-oss-20b"),
            ("GET", fake.MODELS, fake.VERSIONED): fake.anthropic_list("other"),
            ("POST", fake.CHAT): fake.OPENAI_400,
        },
    )
    probe = ms.probe(serve("mixed").url)
    assert (probe.kind, probe.models) == ("OpenAI-compatible", ("gpt-oss-20b",))


def test_a_headered_list_in_openai_s_shape_fills_no_gap(serve, monkeypatch):
    monkeypatch.setitem(
        fake.PROFILES,
        "headered-openai",
        {
            ("GET", fake.MODELS, fake.VERSIONED): fake.openai_list("m1"),
            ("POST", fake.RESPONSES): fake.OPENAI_400,
        },
    )
    probe = ms.probe(serve("headered-openai").url)
    assert (probe.kind, probe.models) == ("OpenAI-compatible", None)  # by the API
    assert probe.models_why == "GET /v1/models: 404"


# An API is proven without generating.


def test_api_proven_by_400_or_422_json(serve):
    # "all": chat completions 400, Responses 422, Messages 400, each with JSON.
    assert ms.probe(serve("all").url).apis == set(base.SERVER_APIS)


def test_404_405_and_non_json_are_no(serve):
    # "models-only": chat completions 405, Responses 400 with text, Messages 404.
    assert ms.probe(serve("models-only").url).apis == frozenset()


def test_one_request_per_check_with_empty_bodies(serve):
    server = serve("ollama")
    ms.probe(server.url)
    assert sorted(server.paths()) == sorted(PROBED)
    assert {r.body for r in server.requests if r.method == "POST"} == {b"{}"}
    assert {r.body for r in server.requests if r.method == "GET"} == {b""}


def test_anthropic_version_goes_with_the_posts_and_one_list(serve):
    server = serve("ollama")
    ms.probe(server.url)
    first = server.requests[0]
    assert (first.method, first.path, first.headers["anthropic-version"]) == (
        "GET",
        fake.MODELS,
        None,
    )
    versioned = sorted(
        (r.method, r.path) for r in server.requests if r.headers["anthropic-version"]
    )
    assert versioned == sorted([("GET", fake.MODELS)] + [(m, p) for m, p in PROBED if m == "POST"])
    assert {r.headers["anthropic-version"] for r in server.requests} == {None, "2023-06-01"}


def test_headers_of_each_request(serve):
    server = serve("ollama")
    ms.probe(server.url)
    for request in server.requests:
        assert request.headers["User-Agent"].startswith("lado/")
        assert "Authorization" not in request.headers and "x-api-key" not in request.headers
        if request.method == "POST":
            assert request.headers["Content-Type"] == "application/json"


# A server that answers every POST alike proves no API.


def test_gateway_400_everywhere_is_unknown(serve):
    server = serve("gateway-400")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert str(raised.value) == (
        f"unknown server: {server.url} answered, but not as an OpenAI-compatible, "
        "Anthropic-compatible, Ollama or LM Studio server (GET /v1/models: 400; it answers 400 "
        "to any POST, so its APIs cannot be told)"
    )


def test_gateway_400_with_list_tells_no_api(serve):
    server = serve("gateway-400-list")
    probe = ms.probe(server.url)
    assert probe.kind == "OpenAI-compatible"
    assert probe.apis == frozenset()
    assert ms.lines(probe)[2:] == [
        "models: m1",
        f"APIs: cannot be told: {server.url} answers 400 to any POST",
        "CLIs: none",
        "not: Kilo CLI (no chat completions), OpenCode (no chat completions), "
        "Codex CLI (no Responses API), Claude Code (no Anthropic Messages API)",
    ]


def test_control_404_keeps_the_apis(serve):
    server = serve("all")
    probe = ms.probe(server.url)
    assert ("POST", fake.CONTROL) in server.paths()  # asked, answered 404
    assert probe.apis == set(base.SERVER_APIS)
    assert not any(line.startswith("APIs:") for line in ms.lines(probe))


# A server's models or no list.


def test_list_500_is_no_list(serve):
    probe = ms.probe(serve("list-500").url)
    assert (probe.kind, probe.models) == ("Ollama", None)
    assert ms.lines(probe)[2] == "models: no list (GET /v1/models: 500)"
    assert probe.clis()[0]  # the type and CLIs still


def test_empty_list_is_none(serve):
    assert ms.lines(ms.probe(serve("empty-list").url))[2] == "models: none"


def test_a_server_s_words_are_one_line_of_visible_text(serve):
    """A model id or a redirect's location forges no line of the output, drives no
    terminal."""
    lines = ms.lines(ms.probe(serve("odd-ids").url))
    assert lines[2] == "models: a CLIs: Claude Code (Anthropic Messages API), [31mb"
    assert len(lines) == 5
    server = serve("redirect", location="http://other.invalid/\x1b[2Jx")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert "\x1b" not in str(raised.value)
    assert "301 to http://other.invalid/ [2Jx/v1/models)" in str(raised.value)


def test_a_list_too_large_is_no_list(serve, monkeypatch):
    monkeypatch.setattr(ms, "MAX_ANSWER", 100)  # the list is longer, the rest shorter
    probe = ms.probe(serve("ollama").url)
    assert ms.lines(probe)[2] == "models: no list (the answer is larger than 4 MiB)"


# The address as given, its scheme added visibly.


@pytest.mark.parametrize(
    ("given", "root", "added"),
    [
        ("localhost:11434", "http://localhost:11434", True),
        ("  localhost:11434/v1/  ", "http://localhost:11434", True),
        ("http://h/v1/", "http://h", False),
        ("https://gw/llm/v1", "https://gw/llm", False),
        ("HTTPS://gw/llm/", "https://gw/llm", False),
        ("http://[::1]:8080", "http://[::1]:8080", False),
    ],
)
def test_address_forms(given, root, added):
    assert ms.address(given) == (root, added)


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ("ftp://h", "http:// or https://"),
        ("http://u:pw@h", "user or password"),
        ("http://u@h", "user or password"),
        ("http://h?x=1", "query"),
        ("http://h#f", "fragment"),
        ("http://", "no host"),
        ("", "no address"),
        ("http://h:99999", "port"),
        # urllib's own refusals name the address: a fixed text instead.
        ("http://u:pw@h＃x", "not an address"),
        ("http://u:pw@[::1", "not an address"),
        ("http://u:pw@[zz]", "not an address"),
    ],
)
def test_address_refused(given, says):
    with pytest.raises(ValueError, match=says) as raised:
        ms.address(given)
    assert "pw" not in str(raised.value)


def test_the_root_keeps_a_gateway_s_path(serve):
    server = serve("openai", prefix="/llm")
    probe = ms.probe(server.url + "/v1/")
    assert probe.address == server.url
    assert ("GET", "/llm/v1/models") in server.paths()


def test_added_scheme_is_on_the_first_line(serve):
    server = serve("openai")
    probe = ms.probe(server.url.removeprefix("http://"))
    assert ms.lines(probe)[0] == f"{server.url} (added http://)"


# An address that does not answer.


def test_closed_port_does_not_answer_after_one_request(monkeypatch):
    asked = []
    real = ms._ask
    monkeypatch.setattr(ms, "_ask", lambda *a: asked.append(a) or real(*a))
    port = closed_port()
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(f"http://127.0.0.1:{port}")
    assert str(raised.value) == f"http://127.0.0.1:{port} does not answer (connection refused)"
    assert raised.value.hint == ""
    assert len(asked) == 1


def test_hanging_server_does_not_answer(serve, monkeypatch):
    monkeypatch.setattr(ms, "TIMEOUT", 0.5)
    server = serve("hang")
    started = time.monotonic()
    with pytest.raises(ms.ProbeError, match=r"does not answer \(no answer in 0.5 s\)"):
        ms.probe(server.url)
    assert time.monotonic() - started < 2
    assert server.paths() == [("GET", fake.MODELS)]


def test_the_limit_is_five_seconds():
    assert ms.TIMEOUT == 5


def test_unknown_host_does_not_answer():
    with pytest.raises(ms.ProbeError, match=r"does not answer \(unknown host\)"):
        ms.probe("http://lado-probe-test.invalid:4000")


def test_a_slow_resolver_is_cut_at_the_limit(monkeypatch):
    monkeypatch.setattr(ms, "TIMEOUT", 0.3)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: time.sleep(3))
    started = time.monotonic()
    with pytest.raises(ms.ProbeError, match=r"no answer in 0.3 s"):
        ms.probe("http://slow.example:4000")
    assert time.monotonic() - started < 1.5


def test_tls_failure(serve):
    server = serve("openai")
    url = server.url.replace("http://", "https://")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(url)
    text = str(raised.value)
    assert text.startswith(f"{url}: TLS failed (")
    assert text.endswith("); a company's CA goes in the file SSL_CERT_FILE names")


# localhost in LADO's container.


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.1.2.3", "[::1]"])
def test_container_hint(host, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    port = closed_port()
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(f"{host}:{port}/llm")
    assert raised.value.hint == (
        "LADO runs in a container, where localhost is the container itself; a server on your "
        f"machine: lado model-server probe http://host.docker.internal:{port}/llm (not tried)"
    )


def test_container_hint_names_the_command_run(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    port = closed_port()
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(f"localhost:{port}", command='lado model-server add "LM Studio дома" --replace')
    assert raised.value.hint.endswith(
        f'machine: lado model-server add "LM Studio дома" --replace '
        f"http://host.docker.internal:{port} (not tried)"
    )


def test_container_hint_takes_the_scheme_s_port(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setattr(ms, "_ask", lambda *a: ms.Answer(why="connection refused"))
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe("https://localhost")
    assert "probe https://host.docker.internal:443 (not tried)" in raised.value.hint


def test_no_hint_outside_container():
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(f"localhost:{closed_port()}")
    assert raised.value.hint == ""


def test_no_hint_for_a_lan_address(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setattr(ms, "_ask", lambda *a: ms.Answer(why="connection refused"))
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe("192.168.1.10:11434")
    assert raised.value.hint == ""


def test_container_hint_sends_nothing_there(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    asked = []
    real = ms._ask
    monkeypatch.setattr(ms, "_ask", lambda *a: asked.append(a[1]) or real(*a))
    port = closed_port()
    with pytest.raises(ms.ProbeError):
        ms.probe(f"localhost:{port}")
    assert asked == [f"http://localhost:{port}/v1/models"]


# The server's key.


def test_key_headers(serve):
    server = serve("ollama", key="k-123")
    assert ms.probe(server.url, key="k-123").kind == "Ollama"
    assert sorted(server.paths()) == sorted(PROBED)
    for request in server.requests:
        assert request.headers["Authorization"] == "Bearer k-123"
        assert request.headers["x-api-key"] == "k-123"


def test_asks_for_a_key(serve):
    server = serve("openai", key="k-123")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert str(raised.value) == (
        f"{server.url} asks for a key (401): run lado model-server probe {server.url} --key"
    )


def test_asks_for_a_key_names_the_command_run(serve):
    server = serve("openai", key="k-123")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url, command='lado model-server add "work"')
    assert str(raised.value) == (
        f'{server.url} asks for a key (401): run lado model-server add "work" {server.url} --key'
    )


@pytest.mark.parametrize(
    ("root", "host"),
    [
        ("http://llm.example.com", "llm.example.com"),
        ("http://llm.example.com:8080/llm", "llm.example.com"),
        ("http://8.8.8.8:4000", "8.8.8.8"),
        ("http://[2001:4860::8888]:4000", "2001:4860::8888"),
        ("http://localhost.example.com", "localhost.example.com"),
    ],
)
def test_a_key_over_plain_http_to_a_public_host_is_warned(root, host):
    assert ms.plain_http_warning(root, "k") == (
        f"the key goes to {host} over plain http://, unencrypted; use https:// if the server has it"
    )


@pytest.mark.parametrize(
    "root",
    [
        "http://localhost:1234",
        "http://LOCALHOST:1234",
        "http://127.0.0.1:1234",
        "http://[::1]:1234",
        "http://10.0.0.5:4000",
        "http://192.168.1.10:11434",
        "http://172.16.0.1",
        "http://169.254.1.1",
        "http://[fd00::1]:4000",
        "http://[fe80::1]:4000",
        "http://host.docker.internal:1234",
    ],
)
def test_no_warning_for_a_local_host(root):
    assert ms.plain_http_warning(root, "k") is None


def test_no_warning_without_a_key_or_over_https():
    assert ms.plain_http_warning("http://llm.example.com", None) is None
    assert ms.plain_http_warning("https://llm.example.com", "k") is None


def test_asks_for_a_key_on_403(serve):
    server = serve("forbidden")
    with pytest.raises(ms.ProbeError, match=r"asks for a key \(403\)"):
        ms.probe(server.url)


def test_refuses_the_key_never_in_error_text(serve):
    server = serve("openai", key="k-123")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url, key="wrong-key-777")
    assert str(raised.value) == f"{server.url} refused the key (401)"
    assert "wrong-key-777" not in repr(raised.value) + str(raised.value.args)


def test_a_key_a_header_cannot_carry_is_refused_unechoed():
    with pytest.raises(ms.ProbeError, match="a character no HTTP header can carry") as raised:
        ms.probe("http://h:1", key="bad\nkey-777")
    assert "key-777" not in str(raised.value)


# An unknown server.


def test_unknown_server(serve):
    server = serve("unknown")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert str(raised.value) == (
        f"unknown server: {server.url} answered, but not as an OpenAI-compatible, "
        "Anthropic-compatible, Ollama or LM Studio server (GET /v1/models: 404)"
    )


def test_redirect_is_not_followed(serve):
    elsewhere = serve("openai")
    server = serve("redirect", location=elsewhere.url)
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url, key="k-123")
    assert f"(GET /v1/models: 301 to {elsewhere.url}/v1/models)" in str(raised.value)
    assert elsewhere.requests == []


def test_redirect_location_loses_its_query(serve):
    server = serve("redirect", location="http://other.invalid/x?token=t0k")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert "(GET /v1/models: 301 to http://other.invalid/x)" in str(raised.value)


def test_redirect_to_no_url_is_named_so(serve):
    server = serve("redirect", location="http://[zz]")
    with pytest.raises(ms.ProbeError) as raised:
        ms.probe(server.url)
    assert "(GET /v1/models: 301 to a location that is not a URL)" in str(raised.value)
