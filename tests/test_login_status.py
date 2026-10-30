"""Each provider's login (Provider.login_status, login_actions, login_choices, login_variables,
needs_login, login_note), on outputs recorded from the real CLIs in throwaway homes: Claude
Code 2.1.295, Codex CLI 0.162.0, OpenCode 1.18.35, Kilo 7.8.8 (2026-10-28)."""

import json
import subprocess
import sys

import pytest

from lado import providers
from lado.providers import base
from lado.providers.base import NO, UNKNOWN, YES, LoginItem, LoginStatus

# The real one: tests/conftest.py's cli_logins stands in for it in every test.
RUN_STATUS = base.run_status


@pytest.fixture
def answers(monkeypatch):
    """base.run_status answered from a table: argv[0] -> (exit code, stdout, stderr) or a
    problem string; the calls are kept."""
    table: dict[str, object] = {}
    calls: list[tuple[list[str], dict]] = []

    def run(argv, env):
        calls.append((argv, env))
        answer = table[argv[0]]
        if isinstance(answer, str):
            return answer
        code, out, err = answer
        return subprocess.CompletedProcess(argv, code, out, err)

    monkeypatch.setattr(base, "run_status", run)
    table["calls"] = calls
    return table


def _claude(answers, data, code=0, env=None):
    answers["claude"] = (code, json.dumps(data, indent=2), "")
    return providers.get("claude").login_status(env or {"HOME": "/h"})


CONFIG = {"configDirectory": "/h/.claude", "projectsDirectory": "/h/.claude/projects"}


def test_claude_reads_its_own_status_command(answers):
    _claude(answers, {"loggedIn": False, "authMethod": "none", **CONFIG}, code=1)
    [(argv, env)] = answers["calls"]
    assert argv == ["claude", "auth", "status", "--json"]
    assert env == {"HOME": "/h"}


def test_claude_not_logged_in(answers):
    data = {"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty", **CONFIG}
    assert _claude(answers, data, code=1) == LoginStatus(NO)


def test_claude_subscription(answers, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    data = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "max", **CONFIG}
    assert _claude(answers, data) == LoginStatus(
        YES,
        "Subscription (Max)",
        file="/h/.claude/.credentials.json",
        file_words="Claude Code's login file",
        choice="subscription",
    )


def test_claude_subscription_on_macos_is_in_the_keychain(answers, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    data = {"loggedIn": True, "authMethod": "claude.ai", **CONFIG}
    assert _claude(answers, data) == LoginStatus(
        YES,
        "Subscription",
        file="the login keychain",
        file_words="the login keychain",
        choice="subscription",
    )


def test_claude_token(answers):
    data = {"loggedIn": True, "authMethod": "oauth_token", **CONFIG}
    env = {"CLAUDE_CODE_OAUTH_TOKEN": "t"}
    assert _claude(answers, data, env=env) == LoginStatus(
        YES, "Subscription (token)", variable="CLAUDE_CODE_OAUTH_TOKEN", choice="subscription"
    )


def test_claude_token_names_the_variable_that_gives_it(answers):
    # ANTHROPIC_AUTH_TOKEN is an "oauth_token" too (2.1.295, checked by hand).
    data = {"loggedIn": True, "authMethod": "oauth_token", **CONFIG}
    # A gateway's token: no way to pay the sheet offers.
    assert _claude(answers, data, env={"ANTHROPIC_AUTH_TOKEN": "t"}) == LoginStatus(
        YES, "Token", variable="ANTHROPIC_AUTH_TOKEN"
    )
    both = {"ANTHROPIC_AUTH_TOKEN": "t", "CLAUDE_CODE_OAUTH_TOKEN": "c"}
    assert _claude(answers, data, env=both).variable == "CLAUDE_CODE_OAUTH_TOKEN"


def test_claude_through_another_api_provider(answers):
    data = {"loggedIn": True, "authMethod": "third_party", "apiProvider": "bedrock", **CONFIG}
    assert _claude(answers, data) == LoginStatus(YES, "Bedrock")


def test_claude_api_key_from_a_variable(answers):
    data = {"loggedIn": True, "authMethod": "api_key", "apiKeySource": "ANTHROPIC_API_KEY"}
    assert _claude(answers, {**data, **CONFIG}) == LoginStatus(
        YES, "Pay per use (API key)", variable="ANTHROPIC_API_KEY", choice="usage"
    )


def test_claude_api_key_of_its_own_login(answers):
    data = {"loggedIn": True, "authMethod": "api_key", "apiKeySource": "/login managed key"}
    assert _claude(answers, {**data, **CONFIG}) == LoginStatus(
        YES,
        "Pay per use (Console)",
        file="/h/.claude/.credentials.json",
        file_words="Claude Code's login file",
        choice="usage",
    )


def test_claude_method_it_does_not_know_is_named_as_it_is(answers):
    data = {"loggedIn": True, "authMethod": "bedrock", **CONFIG}
    assert _claude(answers, data) == LoginStatus(YES, "bedrock")


@pytest.mark.parametrize(
    ("answer", "problem"),
    [
        ("`claude auth status --json` timed out after 10 s", "timed out"),
        ((0, "not json", ""), "cannot read `claude auth status --json`"),
        ((0, "[1]", ""), "cannot read `claude auth status --json`"),
        ((2, "", "boom\n"), "`claude auth status --json` failed with exit status 2: boom"),
        ((0, json.dumps({"authMethod": "none"}), ""), "cannot read"),
    ],
)
def test_claude_status_it_cannot_read_is_unknown_never_no(answers, answer, problem):
    answers["claude"] = answer
    found = providers.get("claude").login_status({})
    assert found.state == UNKNOWN
    assert problem in found.problem


def test_claude_asks_how_the_human_pays_and_runs_no_login_command():
    claude = providers.get("claude")
    assert claude.login_actions() == ()
    assert claude.login_question == "How do you pay for Claude?"
    assert [(c.id, c.title, c.detail, c.variable) for c in claude.login_choices] == [
        (
            "subscription",
            "Subscription — Claude Pro or Max",
            "Run `claude setup-token` on any computer where Claude Code is installed and "
            "paste the token it prints.",
            "CLAUDE_CODE_OAUTH_TOKEN",
        ),
        (
            "usage",
            "Pay per use — API billing",
            "Paste an API key from console.anthropic.com.",
            "ANTHROPIC_API_KEY",
        ),
    ]
    assert claude.login_variables == ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
    assert claude.capabilities.needs_login
    assert claude.login_note == ""


def test_only_claude_needs_a_login():
    needs = {n: providers.get(n).capabilities.needs_login for n in providers.names()}
    assert needs == {"claude": True, "codex": False, "kilo": False, "opencode": False}


# Codex prints its status on stderr, after a warning of its own.
CODEX_WARNING = (
    "WARNING: proceeding, even though we could not create PATH aliases: Refusing to create "
    'helper binaries under temporary dir "/tmp" (codex_home: AbsolutePathBuf("/tmp/c"))\n'
)


def test_codex_not_logged_in(answers):
    answers["codex"] = (1, "", CODEX_WARNING + "Not logged in\n")
    assert providers.get("codex").login_status({"HOME": "/h"}) == LoginStatus(NO)
    [(argv, _)] = answers["calls"]
    assert argv == ["codex", "login", "status"]


def test_codex_logged_in_keeps_nothing_after_the_dash(answers):
    answers["codex"] = (0, "", CODEX_WARNING + "Logged in using an API key - sk-proj-***lmnop\n")
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": "/c"})
    assert found == LoginStatus(YES, "API key", file="/c/auth.json")
    assert "lmnop" not in repr(found)


def test_codex_chatgpt_in_its_default_home(answers):
    answers["codex"] = (0, "Logged in using ChatGPT\n", "")
    found = providers.get("codex").login_status({"HOME": "/h"})
    assert found == LoginStatus(YES, "ChatGPT", file="/h/.codex/auth.json")


def test_codex_error_is_unknown(answers):
    error = 'Error loading configuration: CODEX_HOME points to "/c", but that path does not exist\n'
    answers["codex"] = (1, "", error)
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": "/c"})
    assert found.state == UNKNOWN
    assert "Error loading configuration" in found.problem


def test_codex_offers_no_login_and_says_why():
    codex = providers.get("codex")
    assert codex.login_actions() == ()
    assert codex.login_choices == ()
    assert codex.login_variables == ()
    assert "#113" in codex.login_note and "do not get" in codex.login_note


# `opencode auth list` and `kilo auth list`, ANSI colours and all (stdout; stderr has one
# reset code).
FAMILY_FULL = (
    "┌  Credentials \x1b[90m~/d/{cli}/auth.json\n│\n●  Anthropic \x1b[90mapi\n│\n"
    "●  OpenRouter \x1b[90moauth\n│\n└  2 credentials\n\n┌  Environment\n│\n"
    "●  OpenAI \x1b[90mOPENAI_API_KEY\n│\n└  1 environment variable\n\n"
)
FAMILY_NONE = "┌  Credentials \x1b[90m~/d/{cli}/auth.json\n│\n└  0 credentials\n\n"


@pytest.mark.parametrize("cli", ["opencode", "kilo"])
def test_family_lists_credentials_and_variables(answers, cli):
    answers[cli] = (0, FAMILY_FULL.format(cli=cli), "\x1b[0m\n")
    found = providers.get(cli).login_status({"HOME": "/h"})
    assert found == LoginStatus(
        YES,
        "2 credentials, 1 variable",
        file=f"~/d/{cli}/auth.json",
        items=(
            LoginItem("Anthropic", "api"),
            LoginItem("OpenRouter", "oauth"),
            LoginItem("OpenAI", "variable", "OPENAI_API_KEY"),
        ),
    )
    [(argv, _)] = answers["calls"]
    assert argv == [cli, "auth", "list"]


@pytest.mark.parametrize("cli", ["opencode", "kilo"])
def test_family_without_logins(answers, cli):
    answers[cli] = (0, FAMILY_NONE.format(cli=cli), "\x1b[0m\n")
    found = providers.get(cli).login_status({})
    assert found == LoginStatus(NO, file=f"~/d/{cli}/auth.json")


@pytest.mark.parametrize("cli", ["opencode", "kilo"])
def test_family_output_it_cannot_read_is_unknown(answers, cli):
    answers[cli] = (0, "something else\n", "")
    assert providers.get(cli).login_status({}).state == UNKNOWN
    answers[cli] = (1, "", "Error: boom\n")
    found = providers.get(cli).login_status({})
    assert found.state == UNKNOWN and "boom" in found.problem


@pytest.mark.parametrize("cli", ["opencode", "kilo"])
def test_family_login_and_logout_go_in_the_window(cli):
    provider = providers.get(cli)
    assert [(a.id, a.label, a.argv) for a in provider.login_actions()] == [
        ("login", "Add a login…", (cli, "auth", "login")),
        ("logout", "Log out of one…", (cli, "auth", "logout")),
    ]
    assert provider.login_choices == ()
    assert provider.login_variables == ()


def test_run_status_kills_a_command_that_runs_too_long(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "LOGIN_TIMEOUT", 0.5)
    script = tmp_path / "slow"
    script.write_text("#!/bin/sh\nsleep 30\n")
    script.chmod(0o755)
    found = RUN_STATUS(["slow", "status"], {"PATH": f"{tmp_path}:/usr/bin:/bin"})
    assert found == "`slow status` timed out after 0.5 s"


def test_run_status_of_a_command_not_on_path(tmp_path):
    assert RUN_STATUS(["nope"], {"PATH": str(tmp_path)}) == ("`nope` is not on the agents' PATH")


def test_run_status_gives_the_output(tmp_path):
    script = tmp_path / "say"
    script.write_text("#!/bin/sh\necho out; echo err >&2; exit 3\n")
    script.chmod(0o755)
    found = RUN_STATUS(["say"], {"PATH": str(tmp_path), "HOME": str(tmp_path)})
    assert (found.returncode, found.stdout, found.stderr) == (3, "out\n", "err\n")


@pytest.mark.parametrize("name", ["claude", "codex", "kilo", "opencode"])
def test_each_choice_logs_in_by_one_of_the_providers_login_variables(name):
    provider = providers.get(name)
    assert {c.variable for c in provider.login_choices} <= set(provider.login_variables)
    assert bool(provider.login_choices) == bool(provider.login_question)
