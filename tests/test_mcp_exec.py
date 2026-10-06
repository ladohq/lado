import os

import pytest

from lado import interpreter, mcp_exec

PREFIX = interpreter.run_module("lado.mcp_exec")


def wrapper_args(argv: list[str]) -> list[str]:
    """The wrapper's arguments in the command `wrap` made."""
    assert argv[: len(PREFIX)] == PREFIX
    return argv[len(PREFIX) :]


def test_a_wrapped_server_gets_its_values_from_the_environment(monkeypatch):
    argv = mcp_exec.wrap("db", ["srv", "--x"], {"T": "${A}-${B}", "U": "${A}"})
    calls = []
    monkeypatch.setattr(os, "execvpe", lambda *call: calls.append(call))
    monkeypatch.setenv("A", "s3cr3t")
    monkeypatch.setenv("B", "two")
    mcp_exec.main(wrapper_args(argv))
    [(program, args, env)] = calls
    assert (program, args) == ("srv", ["srv", "--x"])
    assert (env["T"], env["U"], env["A"]) == ("s3cr3t-two", "s3cr3t", "s3cr3t")


def test_the_templates_look_like_no_cli_substitution():
    argv = mcp_exec.wrap("db", ["srv"], {"T": "${TOKEN}", "V": "{env:X}{file:y}"})
    for arg in argv:
        assert "${" not in arg and "{env:" not in arg and "{file:" not in arg


def test_an_unset_variable_is_one_line_and_exit_1(monkeypatch, capsys):
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.setattr(os, "execvpe", lambda *call: pytest.fail("exec'd"))
    argv = mcp_exec.wrap("db", ["srv"], {"T": "x-${TOKEN}"})
    with pytest.raises(SystemExit) as exc:
        mcp_exec.main(wrapper_args(argv))
    assert exc.value.code == 1
    assert capsys.readouterr().err == (
        "LADO: environment variable TOKEN is not set for MCP server db\n"
    )


def test_references_and_expand():
    assert mcp_exec.references("${A}-${B}-x-$C") == ["A", "B"]
    assert mcp_exec.references("plain") == []
    assert mcp_exec.expand({"T": "${A}/${A}"}, {"A": "1"}) == {"T": "1/1"}
    with pytest.raises(mcp_exec.Unset) as exc:
        mcp_exec.expand({"T": "${A}${B}"}, {"A": "1"})
    assert exc.value.name == "B"
