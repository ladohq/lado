"""`lado model-server probe`: the output, the exit codes and the server's key (lado.cli,
lado.model_servers), against the fake servers of tests/fake_model_server.py."""

import io
import socket

import fake_model_server as fake
import pytest

from lado import state
from lado.cli import main


class Stdin(io.StringIO):
    """stdin as a pipe holding `text`, or a terminal; whether it was read."""

    def __init__(self, text: str = "", tty: bool = False):
        super().__init__()
        self.buffer = io.BytesIO(text.encode())
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty

    @property
    def touched(self) -> bool:
        return self.buffer.tell() > 0


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
    monkeypatch.setattr("sys.stdin", Stdin())  # no terminal, nothing piped


def test_probe_prints_the_server(serve, capsys):
    server = serve("ollama")
    assert main(["model-server", "probe", server.url.removeprefix("http://")]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        f"{server.url} (added http://)",
        "type: Ollama",
        "models: llama3.1:8b, qwen2.5-coder:7b",
        "CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)",
        "not: Claude Code (no Anthropic Messages API)",
    ]
    assert err == ""
    assert not state.home().joinpath("lado.db").exists()  # the probe keeps nothing


def test_no_not_line_when_all_suit(serve, capsys):
    assert main(["model-server", "probe", serve("all").url]) == 0
    assert not [line for line in capsys.readouterr().out.splitlines() if line.startswith("not:")]


def test_failure_exit_1_on_stderr(capsys, monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setenv("LADO_CONTAINER", "1")
    assert main(["model-server", "probe", f"127.0.0.1:{port}"]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.splitlines() == [
        f"lado: http://127.0.0.1:{port} does not answer (connection refused)",
        "lado: LADO runs in a container, where localhost is the container itself; a server on "
        f"your machine: lado model-server probe http://host.docker.internal:{port} (not tried)",
    ]


def test_unknown_server_exit_1(serve, capsys):
    server = serve("gateway-400")
    assert main(["model-server", "probe", server.url]) == 1
    assert capsys.readouterr().err.startswith(f"lado: unknown server: {server.url} answered")


def test_bad_address_exit_2(capsys):
    assert main(["model-server", "probe", "http://me:pw@h:4000"]) == 2
    out, err = capsys.readouterr()
    assert err.startswith("lado: a server's address holds no user or password")
    assert "pw" not in out + err


def test_key_from_stdin(serve, capsys, monkeypatch):
    server = serve("openai", key="k-123")
    monkeypatch.setattr("sys.stdin", Stdin("k-123\n"))
    monkeypatch.setattr("getpass.getpass", lambda prompt: pytest.fail("asked"))
    assert main(["model-server", "probe", server.url, "--key"]) == 0
    out, err = capsys.readouterr()
    assert {r.headers["Authorization"] for r in server.requests} == {"Bearer k-123"}
    assert "k-123" not in out + err


def test_key_on_a_terminal_asks_without_echo(serve, capsys, monkeypatch):
    server = serve("openai", key="k-123")
    monkeypatch.setattr("sys.stdin", Stdin(tty=True))
    asked = []
    monkeypatch.setattr("getpass.getpass", lambda prompt: asked.append(prompt) or "k-123")
    assert main(["model-server", "probe", server.url, "--key"]) == 0
    assert asked == ["Key of the server (not shown): "]
    assert "k-123" not in "".join(capsys.readouterr())


def test_refused_key(serve, capsys, monkeypatch):
    server = serve("openai", key="k-123")
    monkeypatch.setattr("sys.stdin", Stdin("wrong-777"))
    assert main(["model-server", "probe", server.url, "--key"]) == 1
    out, err = capsys.readouterr()
    assert err == f"lado: {server.url} refused the key (401)\n"
    assert "wrong-777" not in out + err


def test_empty_key_is_refused(serve, capsys, monkeypatch):
    server = serve("openai")
    monkeypatch.setattr("sys.stdin", Stdin("\n"))
    assert main(["model-server", "probe", server.url, "--key"]) == 1
    assert capsys.readouterr().err == "lado: the key is empty\n"
    assert server.requests == []


@pytest.mark.parametrize("given", [["--key", "s3cr3t"], ["--key=s3cr3t"]])
def test_key_on_the_command_line_is_refused_unechoed(serve, capsys, monkeypatch, given):
    server = serve("openai")
    stdin = Stdin("k\n")
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["model-server", "probe", server.url, *given]) == 1
    out, err = capsys.readouterr()
    assert err == (
        "lado: a server's key is never given on the command line (ps and the shell's history "
        f"keep it); run lado model-server probe {server.url} --key and type it, or pipe it in\n"
    )
    assert "s3cr3t" not in out + err
    assert server.requests == []
    assert not stdin.touched


def test_model_server_alone_prints_help(capsys):
    assert main(["model-server"]) == 0
    assert "probe" in capsys.readouterr().out
