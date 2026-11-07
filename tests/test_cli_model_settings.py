"""`lado model-server add|list|remove` and `lado model add|list|remove` (lado.cli,
lado.model_settings): the output, the exit codes and the server's key, against the fake
servers of tests/fake_model_server.py."""

import io
import shlex
import socket
import sqlite3

import agent_helpers
import fake_model_server as fake
import pytest
from test_cli_model_server import Stdin

from lado import model_settings, providers, runtime, state, telemetry
from lado.cli import main
from lado.providers import base


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


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def piped(monkeypatch, text):
    stdin = Stdin(text)
    monkeypatch.setattr("sys.stdin", stdin)
    return stdin


# lado model-server add.


def test_add_prints_the_probe_and_saves(serve, capsys):
    server = serve("lmstudio")
    assert main(["model-server", "add", "LM Studio дома", server.url.removeprefix("http://")]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        f"{server.url} (added http://)",
        "type: LM Studio",
        "models: qwen3-8b, text-embedding-nomic-embed-text-v1.5 (embeddings)",
        "CLIs: Kilo CLI, OpenCode (chat completions)",
        "not: Claude Code (no Anthropic Messages API), Codex CLI (its Responses API loses Codex "
        "CLI's MCP tools, so the agent could not talk to LADO)",
        'Saved model server "LM Studio дома".',
    ]
    assert err == ""
    assert state.model_server("LM Studio дома").address == server.url


def test_add_names_a_server_at_the_same_address_before_saved(serve, capsys):
    server = serve("openai")
    main(["model-server", "add", "macpro", server.url])
    capsys.readouterr()
    assert main(["model-server", "add", "lms", server.url.removeprefix("http://") + "/v1/"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-2:] == [
        'same address as model server "macpro"',
        'Saved model server "lms".',
    ]
    assert out.splitlines()[-3].startswith("not: ")  # after the probe's lines
    assert err == ""
    assert main(["model-server", "add", "lms", server.url, "--replace"]) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        'same address as model server "macpro"',
        'Replaced model server "lms".',
    ]


def test_add_with_a_piped_key(serve, capsys, monkeypatch):
    server = serve("openai", key="k-123")
    piped(monkeypatch, "k-123\n")
    assert main(["model-server", "add", "work", server.url, "--key"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == 'Saved model server "work".'
    assert "k-123" not in out + err
    assert model_settings.server_key(state.model_server("work")) == "k-123"


def test_replace_says_so(serve, capsys):
    main(["model-server", "add", "lab", serve("openai").url])
    new = serve("ollama")
    assert main(["model-server", "add", "LAB", new.url, "--replace"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == 'Replaced model server "lab".'
    assert state.model_server("lab").kind == "Ollama"


def test_add_of_a_taken_name_exit_1(serve, capsys):
    main(["model-server", "add", "lab", serve("openai").url])
    other = serve("openai")
    capsys.readouterr()
    assert main(["model-server", "add", "Lab", other.url]) == 1
    assert capsys.readouterr().err == (
        'lado: a model server "lab" is saved already; to change its address or key: lado '
        'model-server add "lab" <address> [--key] --replace\n'
    )
    assert other.requests == []


def test_add_of_an_address_that_does_not_answer_exit_1(capsys, monkeypatch):
    port = closed_port()
    monkeypatch.setenv("LADO_CONTAINER", "1")
    assert main(["model-server", "add", "LM Studio дома", f"localhost:{port}"]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.splitlines() == [
        f"lado: http://localhost:{port} does not answer (connection refused)",
        "lado: LADO runs in a container, where localhost is the container itself; a server on "
        f'your machine: lado model-server add "LM Studio дома" http://host.docker.internal:{port} '
        "(not tried)",
    ]
    assert state.model_servers() == []


def test_add_of_a_server_asking_for_a_key_names_add(serve, capsys):
    server = serve("openai", key="k")
    assert main(["model-server", "add", "work", server.url]) == 1
    assert capsys.readouterr().err == (
        f'lado: {server.url} asks for a key (401): run lado model-server add "work" {server.url} '
        "--key\n"
    )


def test_add_of_a_bad_address_exit_2(capsys):
    assert main(["model-server", "add", "lab", "http://me:pw@h:4000"]) == 2
    out, err = capsys.readouterr()
    assert err.startswith("lado: a server's address holds no user or password")
    assert "pw" not in out + err


def test_add_of_a_bad_name_exit_1(capsys, serve):
    server = serve("openai")
    assert main(["model-server", "add", "", server.url]) == 1
    assert capsys.readouterr().err == "lado: a model server's name is empty\n"
    assert server.requests == []


def test_add_warns_of_a_key_over_plain_http(serve, capsys, monkeypatch):
    server = serve("openai", key="k")
    piped(monkeypatch, "k")
    real = model_settings.model_servers.probe
    monkeypatch.setattr(
        model_settings.model_servers,
        "probe",
        lambda text, key, command: real(server.url, key, command),
    )
    assert main(["model-server", "add", "ext", "http://llm.example.com", "--key"]) == 0
    assert capsys.readouterr().err == (
        "lado: warning: the key goes to llm.example.com over plain http://, unencrypted; use "
        "https:// if the server has it\n"
    )


def test_probe_warns_of_a_key_over_plain_http(capsys, monkeypatch):
    piped(monkeypatch, "k")
    monkeypatch.setattr(
        "lado.model_servers.probe", lambda *a, **k: pytest.fail("the warning comes first")
    )
    monkeypatch.setattr(
        "lado.model_servers.plain_http_warning",
        lambda root, key: f"warned {root}",
    )
    with pytest.raises(pytest.fail.Exception):
        main(["model-server", "probe", "http://llm.example.com", "--key"])
    assert capsys.readouterr().err == "lado: warning: warned http://llm.example.com\n"


def test_add_refuses_an_empty_key(serve, capsys, monkeypatch):
    server = serve("openai")
    piped(monkeypatch, "\n")
    assert main(["model-server", "add", "work", server.url, "--key"]) == 1
    assert capsys.readouterr().err == "lado: the key is empty\n"
    assert server.requests == []
    assert state.model_servers() == []


@pytest.mark.parametrize("command", ["probe", "add"])
def test_a_key_that_is_no_utf_8_is_refused_in_one_line(serve, capsys, monkeypatch, command):
    """Bytes that are no UTF-8 come as surrogates: refused by the header rule, never a crash
    (nor a journal line, which an unexpected exception writes)."""
    server = serve("openai")
    stdin = Stdin()
    stdin.buffer = io.BytesIO(b"\xff\xfe")
    monkeypatch.setattr("sys.stdin", stdin)
    name = ["work"] if command == "add" else []
    assert main(["model-server", command, *name, server.url, "--key"]) == 1
    assert capsys.readouterr().err == ("lado: the key holds a character no HTTP header can carry\n")
    assert server.requests == []
    assert not telemetry.journal_path().exists()


def test_add_refuses_a_piped_key_over_64_kib_not_cut(serve, capsys, monkeypatch):
    """stdin is read a little over the limit, so a longer key is refused, never cut to it."""
    server = serve("openai")
    piped(monkeypatch, "k" * (10 * 65536))
    assert main(["model-server", "add", "work", server.url, "--key"]) == 1
    assert capsys.readouterr().err == "lado: the key is larger than 64 KiB\n"
    assert server.requests == []
    assert state.model_servers() == []


ADD_TAKES_NO_MORE = (
    "lado: lado model-server add takes a name, an address, --key and --replace, nothing more; "
    "a server's key is never given on the command line (ps and the shell's history keep it): "
    "run lado model-server add <name> <address> --key and type it, or pipe it in"
)


@pytest.mark.parametrize(
    "given",
    [
        ["--key", "s3cr3t"],
        ["--key=s3cr3t"],
        ["--key", "-s3cr3t"],
        ["--k", "-s3cr3t"],
        ["--key", "a", "s3cr3t"],
        ["s3cr3t"],
        ["--help=s3cr3t"],
        ["--he=s3cr3t"],
        ["--key", "-hs3cr3t"],
    ],
)
def test_a_key_on_the_command_line_is_refused_unechoed(
    serve, capsys, monkeypatch, given, lado_home
):
    server = serve("openai")
    stdin = piped(monkeypatch, "k\n")
    try:
        code = main(["model-server", "add", "work", server.url, *given])
    except SystemExit as exited:
        code = exited.code
    out, err = capsys.readouterr()
    assert "s3cr3t" not in out + err
    assert code in (0, 1)  # 0: -h... printed the help (Python 3.11+)
    in_argv = (
        "lado: a server's key is never given on the command line (ps and the shell's history "
        f'keep it); run lado model-server add "work" {server.url} --key and type it, or pipe '
        "it in"
    )
    if code == 1:
        assert err.splitlines()[-1] in (ADD_TAKES_NO_MORE, in_argv)
    assert server.requests == []
    assert not stdin.touched
    assert not (lado_home / "lado.db").exists() or state.model_servers() == []


def test_a_missing_address_shows_the_add_usage(capsys):
    with pytest.raises(SystemExit) as exited:
        main(["model-server", "add", "work"])
    assert exited.value.code == 1
    assert capsys.readouterr().err.splitlines()[-1] == ADD_TAKES_NO_MORE


# lado model-server list and remove.


def test_list_shows_the_servers_without_asking_them(serve, capsys, monkeypatch):
    lm = serve("openai")
    work = serve("all", key="k")
    main(["model-server", "add", "LM Studio дома", lm.url])
    piped(monkeypatch, "k")
    main(["model-server", "add", "work", work.url, "--key"])
    lm.requests.clear()
    work.requests.clear()
    capsys.readouterr()
    assert main(["model-server", "list"]) == 0
    width = max(len(lm.url), len(work.url))
    assert capsys.readouterr().out.splitlines() == [
        f"NAME            {'ADDRESS'.ljust(width)}  TYPE               KEY  CLIs",
        f"LM Studio дома  {lm.url.ljust(width)}  OpenAI-compatible  no   Kilo CLI, OpenCode",
        f"work            {work.url.ljust(width)}  OpenAI-compatible  yes  "
        "Claude Code, Codex CLI, Kilo CLI, OpenCode",
    ]
    assert lm.requests == work.requests == []


def test_list_of_no_server(capsys):
    assert main(["model-server", "list"]) == 0
    assert capsys.readouterr().out == (
        "No model servers. Add one: lado model-server add <name> <address> [--key]\n"
    )


def test_list_of_a_server_suiting_no_cli(capsys):
    state.add_model_server("s1", "bare", "https://x", "OpenAI-compatible", ())
    main(["model-server", "list"])
    assert capsys.readouterr().out.splitlines()[1].endswith("no   none")


def test_a_model_of_codex_on_lm_studio_exits_1_and_is_not_saved(serve, capsys):
    main(["model-server", "add", "lms", serve("lmstudio").url])
    capsys.readouterr()
    args = ["model", "add", "C", "--cli", "codex", "--model", "qwen3-8b", "--server", "lms"]
    assert main(args) == 1
    assert capsys.readouterr().err == (
        "lado: lms does not suit Codex CLI: its Responses API loses Codex CLI's MCP tools, so the "
        "agent could not talk to LADO; Kilo CLI and OpenCode do\n"
    )
    assert state.models() == []


def test_remove_a_server(serve, capsys):
    main(["model-server", "add", "lab", serve("openai").url])
    capsys.readouterr()
    assert main(["model-server", "remove", "LAB"]) == 0
    assert capsys.readouterr().out == 'Removed model server "lab".\n'
    assert state.model_servers() == []


def test_remove_a_server_a_model_uses_exit_1(serve, capsys):
    main(["model-server", "add", "LM Studio дома", serve("lmstudio").url])
    main(["model", "add", "Локальная Qwen", "--cli", "opencode", "--model", "qwen3-8b",
          "--server", "LM Studio дома"])  # fmt: skip
    capsys.readouterr()
    assert main(["model-server", "remove", "LM Studio дома"]) == 1
    assert capsys.readouterr().err == (
        'lado: model server "LM Studio дома" is used by the models Локальная Qwen; remove them '
        'first: lado model remove "Локальная Qwen"\n'
        'lado: or remove them with it: lado model-server remove "LM Studio дома" --with-models\n'
    )
    assert state.model_server("LM Studio дома") is not None


def test_remove_a_server_with_its_models(serve, capsys):
    main(["model-server", "add", "lms", serve("lmstudio").url])
    for name, cli in (("sp", "kilo"), ("coder-oc", "opencode")):
        main(["model", "add", name, "--cli", cli, "--model", "qwen3-8b", "--server", "lms"])
    capsys.readouterr()
    assert main(["model-server", "remove", "LMS", "--with-models"]) == 0
    assert capsys.readouterr() == (
        'Removed model "coder-oc".\nRemoved model "sp".\nRemoved model server "lms".\n',
        "",
    )
    assert (state.model_servers(), state.models()) == ([], [])


def test_remove_an_unknown_server_exit_1(capsys):
    assert main(["model-server", "remove", "nope"]) == 1
    assert capsys.readouterr().err == (
        'lado: no model server "nope" is saved; lado model-server list names them\n'
    )


# lado model.


def listing(monkeypatch, name, listed):
    # The class, never the shared instance (tests/test_model_settings.py, listing).
    monkeypatch.setattr(type(providers.get(name)), "model_list", lambda self, env: listed)


def test_model_add_without_a_server_is_refused_naming_the_default(capsys, monkeypatch):
    monkeypatch.setattr(
        type(providers.get("claude")), "model_list", lambda self, env: pytest.fail("read a list")
    )
    assert main(["model", "add", "Быстрая", "--cli", "claude", "--model", "haiku"]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.splitlines() == [
        "lado: a CLI's own models need no saving; only a model on a server is added: "
        "--server <server>",
        "lado: to make one its default: lado model default <cli> <model>",
    ]
    assert state.models() == []


def test_model_add_on_a_server(serve, capsys):
    server = serve("lmstudio")
    main(["model-server", "add", "LM Studio дома", server.url])
    capsys.readouterr()
    assert (
        main(
            [
                "model",
                "add",
                "Локальная Qwen",
                "--cli",
                "opencode",
                "--model",
                "qwen3-8b",
                "--server",
                "LM Studio дома",
            ]
        )  # fmt: skip
        == 0
    )
    assert capsys.readouterr().out == (
        'Saved model "Локальная Qwen": OpenCode, qwen3-8b on LM Studio дома (in LM Studio '
        "дома's list of models)\n"
    )


def test_model_add_on_a_server_without_a_list_warns(serve, capsys):
    main(["model-server", "add", "resp", serve("responses-only").url])
    capsys.readouterr()
    assert main(["model", "add", "C", "--cli", "codex", "--model", "x", "--server", "resp"]) == 0
    out, err = capsys.readouterr()
    text = "GET /v1/models: 404: LADO cannot check x; a wrong name stops its agents at their "
    assert err == f"lado: warning: {text}first turn\n"
    assert out == f'Saved model "C": Codex CLI, x on resp ({text}first turn)\n'


def test_model_add_refused_exit_1(capsys):
    assert main(["model", "add", "G", "--cli", "gemini", "--model", "x"]) == 1
    assert capsys.readouterr().err.startswith('lado: LADO knows no agent CLI "gemini"')


def test_model_add_on_a_server_that_does_not_answer_gives_its_hint(serve, capsys, monkeypatch):
    port = closed_port()
    state.add_model_server("s1", "LM Studio дома", f"http://localhost:{port}", "LM Studio", ())
    monkeypatch.setenv("LADO_CONTAINER", "1")
    assert (
        main(
            ["model", "add", "Q", "--cli", "opencode", "--model", "q", "--server", "LM Studio дома"]
        )  # fmt: skip
        == 1
    )
    assert capsys.readouterr().err.splitlines() == [
        f"lado: http://localhost:{port} does not answer (connection refused); LADO cannot check q",
        "lado: LADO runs in a container, where localhost is the container itself; a server on "
        f'your machine: lado model-server add "LM Studio дома" --replace '
        f"http://host.docker.internal:{port} (not tried)",
    ]


def saved_server():
    return state.add_model_server("s1", "LM Studio дома", "http://localhost:1234", "LM Studio", ())


def test_model_list(capsys, monkeypatch):
    saved_server()
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    state.add_model("Быстрая", "kilo", "qwen3-8b", "s1")
    monkeypatch.setattr(
        type(providers.get("opencode")), "model_list", lambda self, env: pytest.fail("ran")
    )
    assert main(["model", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "NAME            CLI       MODEL     SERVER",
        "Быстрая         Kilo CLI  qwen3-8b  LM Studio дома",
        "Локальная Qwen  OpenCode  qwen3-8b  LM Studio дома",
    ]


def test_model_list_of_none(capsys):
    assert main(["model", "list"]) == 0
    assert capsys.readouterr().out == (
        "No models. Add one: lado model add <name> --cli <cli> --model <model> --server <server>\n"
    )


def test_model_remove(capsys):
    saved_server()
    state.add_model("Быстрая", "kilo", "qwen3-8b", "s1")
    assert main(["model", "remove", "быстрая"]) == 0
    assert capsys.readouterr().out == 'Removed model "Быстрая".\n'
    assert main(["model", "remove", "быстрая"]) == 1
    assert (
        capsys.readouterr().err == 'lado: no model "быстрая" is saved; lado model list names them\n'
    )


def test_model_remove_several(capsys):
    saved_server()
    for name in ("coder-codex", "coder-oc", "sp"):
        state.add_model(name, "kilo", "qwen3-8b", "s1")
    assert main(["model", "remove", "coder-codex", "nowhere"]) == 1
    out, err = capsys.readouterr()
    assert (out, err) == ("", 'lado: no model "nowhere" is saved; lado model list names them\n')
    assert main(["model", "remove", "coder-codex", "coder-oc", "sp"]) == 0
    assert capsys.readouterr().out == (
        'Removed model "coder-codex".\nRemoved model "coder-oc".\nRemoved model "sp".\n'
    )
    assert state.models() == []


def test_model_remove_of_a_default_says_it_is_cleared(capsys):
    saved_server()
    saved = state.add_model("Локальная Qwen", "kilo", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("kilo", saved.id, None))
    assert main(["model", "remove", "Локальная Qwen"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        'Removed model "Локальная Qwen".',
        "Kilo CLI's default model is cleared.",
    ]
    assert state.cli_defaults() == []


def test_a_server_removed_with_a_default_says_it_is_cleared(capsys):
    saved_server()
    state.add_model("coder-oc", "opencode", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", state.model("coder-oc").id, None))
    assert main(["model-server", "remove", "LM Studio дома", "--with-models"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        'Removed model "coder-oc".',
        "OpenCode's default model is cleared.",
        'Removed model server "LM Studio дома".',
    ]


# lado model default.


@pytest.fixture
def on_path(tmp_path, monkeypatch):
    """`on_path(cli, …)`: the agents' PATH holds those CLIs and no other."""

    def put(*clis):
        for cli in clis:
            command = tmp_path / providers.get(cli).command
            command.write_text("#!/bin/sh\n")
            command.chmod(0o755)

    monkeypatch.setattr(runtime, "agent_layers", lambda project: None)
    monkeypatch.setattr(runtime, "agents_env", lambda layers, cli: {"PATH": str(tmp_path)})
    return put


CLAUDE = base.ModelList(
    ("opus",), None, why="Claude Code gives no list of models beyond its aliases"
)


def test_default_prints_every_cli_running_none(capsys, monkeypatch):
    saved_server()
    saved = state.add_model("Локальная Qwen", "kilo", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("kilo", saved.id, None))
    state.set_cli_default(state.ModelRef("claude", None, "opus"))
    for name in providers.names():
        monkeypatch.setattr(
            type(providers.get(name)), "model_list", lambda self, env: pytest.fail("ran")
        )
    assert main(["model", "default"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "CLI          DEFAULT MODEL   SERVER",
        "Claude Code  opus            —",
        "Codex CLI    —               —",
        "Kilo CLI     Локальная Qwen  LM Studio дома",
        "OpenCode     —               —",
    ]


def test_default_of_one_cli_prints_its_row(capsys):
    state.set_cli_default(state.ModelRef("claude", None, "opus"))
    assert main(["model", "default", "claude"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "CLI          DEFAULT MODEL  SERVER",
        "Claude Code  opus           —",
    ]
    assert main(["model", "default", "gemini"]) == 1
    assert capsys.readouterr().err.startswith('lado: LADO knows no agent CLI "gemini"')


def test_default_sets_an_external_model(capsys, on_path, monkeypatch):
    on_path("kilo")
    listing(monkeypatch, "kilo", base.ModelList(why="no list"))
    saved_server()
    saved = state.add_model("Локальная Qwen", "kilo", "qwen3-8b", "s1")
    assert main(["model", "default", "kilo", "локальная qwen"]) == 0
    assert capsys.readouterr() == (
        "Kilo CLI's default model: Локальная Qwen (qwen3-8b on LM Studio дома)\n",
        "",
    )
    assert state.cli_defaults() == [state.ModelRef("kilo", saved.id, None)]


def test_default_sets_an_alias(capsys, on_path, monkeypatch):
    on_path("claude")
    listing(monkeypatch, "claude", CLAUDE)
    assert main(["model", "default", "claude", "opus"]) == 0
    assert capsys.readouterr() == (
        "Claude Code's default model: opus (an alias of Claude Code)\n",
        "",
    )


def test_default_of_a_name_no_list_can_check_warns(capsys, on_path, monkeypatch):
    on_path("claude")
    listing(monkeypatch, "claude", CLAUDE)
    assert main(["model", "default", "claude", "claude-opus-4-1-20250805"]) == 0
    out, err = capsys.readouterr()
    text = (
        "Claude Code gives no list of models beyond its aliases: LADO cannot check "
        "claude-opus-4-1-20250805; a wrong name stops its agents at their first turn"
    )
    assert err == f"lado: warning: {text}\n"
    assert out == f"Claude Code's default model: claude-opus-4-1-20250805 ({text})\n"
    assert state.cli_defaults() == [state.ModelRef("claude", None, "claude-opus-4-1-20250805")]


def test_default_refused_changes_nothing(capsys, on_path, monkeypatch):
    on_path("opencode")
    listing(monkeypatch, "opencode", base.ModelList((), ("a/b",), "opencode models"))
    state.set_cli_default(state.ModelRef("opencode", None, "a/b"))
    assert main(["model", "default", "opencode", "a/c"]) == 1
    assert capsys.readouterr().err == (
        "lado: a/c is not in OpenCode's list of models; opencode models prints the list\n"
    )
    assert main(["model", "default", "kilo", "x"]) == 1
    assert capsys.readouterr().err == "lado: Kilo CLI is not installed\n"
    assert state.cli_defaults() == [state.ModelRef("opencode", None, "a/b")]


def test_default_clear(capsys):
    state.set_cli_default(state.ModelRef("kilo", None, "x/y"))
    assert main(["model", "default", "kilo", "--clear"]) == 0
    assert capsys.readouterr().out == "Kilo CLI's default model is cleared.\n"
    assert main(["model", "default", "kilo", "--clear"]) == 0
    assert capsys.readouterr().out == "Kilo CLI has no default model.\n"
    assert main(["model", "default", "gemini", "--clear"]) == 1


@pytest.mark.parametrize("argv", [["default", "kilo", "x/y", "--clear"], ["default", "--clear"]])
def test_default_clear_takes_a_cli_and_no_model(capsys, argv):
    state.set_cli_default(state.ModelRef("kilo", None, "x/y"))
    with pytest.raises(SystemExit) as exited:
        main(["model", *argv])
    assert exited.value.code == 2
    assert len(state.cli_defaults()) == 1


def test_model_remove_needs_a_name(capsys):
    with pytest.raises(SystemExit) as exited:
        main(["model", "remove"])
    assert exited.value.code == 2


def test_a_removal_s_hint_is_one_command_for_all(serve, capsys):
    main(["model-server", "add", "lms", serve("lmstudio").url])
    for name, cli in (("coder-kilo", "kilo"), ("coder-oc", "opencode"), ("sp", "kilo")):
        main(["model", "add", name, "--cli", cli, "--model", "qwen3-8b", "--server", "lms"])
    capsys.readouterr()
    assert main(["model-server", "remove", "lms"]) == 1
    hint = capsys.readouterr().err.splitlines()[0]
    assert hint == (
        'lado: model server "lms" is used by the models coder-kilo, coder-oc, sp; remove them '
        'first: lado model remove "coder-kilo" "coder-oc" "sp"'
    )
    command = hint.split("remove them first: lado ", 1)[1]
    assert main(shlex.split(command)) == 0
    assert main(["model-server", "remove", "lms"]) == 0


def test_model_alone_prints_help(capsys):
    assert main(["model"]) == 0
    out = capsys.readouterr().out
    assert "add" in out and "list" in out and "remove" in out


def test_model_server_alone_names_its_commands(capsys):
    assert main(["model-server"]) == 0
    out = capsys.readouterr().out
    assert all(word in out for word in ("probe", "add", "list", "remove"))


# lado.db.


def _schema(lado_home):
    with sqlite3.connect(lado_home / "lado.db") as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def test_probe_does_not_migrate_and_add_does(serve, lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.stop_session("s")
    agent_helpers.previous_schema()
    server = serve("openai")
    assert main(["model-server", "probe", server.url]) == 0
    assert _schema(lado_home) == state.SCHEMA_VERSION - 1
    assert main(["model-server", "list"]) == 0
    assert _schema(lado_home) == state.SCHEMA_VERSION


def test_a_session_with_models_saved_and_no_default_asks_no_server(repo, fake_tmux, monkeypatch):
    saved_server()
    state.add_model("Быстрая", "claude", "haiku", "s1")
    monkeypatch.setattr(
        model_settings, "probe_saved", lambda server: pytest.fail("a server was asked")
    )
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    assert state.get_session("s").power is None
