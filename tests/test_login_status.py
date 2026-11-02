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
    """base.run_status answered from a table: argv[0] -> (exit code, stdout, stderr), a
    problem string, or a function of argv giving one; the calls are kept."""
    table: dict[str, object] = {}
    calls: list[tuple[list[str], dict]] = []

    def run(argv, env):
        calls.append((argv, env))
        answer = table[argv[0]]
        if callable(answer):
            answer = answer(argv)
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


def test_claude_always_needs_a_login_and_codex_by_its_model(tmp_path):
    env = {"HOME": "/h", "CODEX_HOME": str(tmp_path)}  # Codex on OpenAI's model
    needs = {n: providers.get(n).needs_login(env) for n in providers.names()}
    assert needs == {"claude": True, "codex": True, "kilo": False, "opencode": False}
    (tmp_path / "config.toml").write_text('model_provider = "ollama"\n')
    assert not providers.get("codex").needs_login(env)


# Codex prints its status on stderr, after a warning of its own.
CODEX_WARNING = (
    "WARNING: proceeding, even though we could not create PATH aliases: Refusing to create "
    'helper binaries under temporary dir "/tmp" (codex_home: AbsolutePathBuf("/tmp/c"))\n'
)


# `codex login status` reads the store Codex's agents use, the login file (they keep their
# login there, cli_auth_credentials_store = "file"): a login only in the keyring is none.
CODEX_STATUS = ["codex", "login", "status", "-c", 'cli_auth_credentials_store="file"']
CODEX_FILE = "Codex's login file"


def test_codex_not_logged_in(answers):
    answers["codex"] = (1, "", CODEX_WARNING + "Not logged in\n")
    assert providers.get("codex").login_status({"HOME": "/h"}) == LoginStatus(NO)
    [(argv, _)] = answers["calls"]
    assert argv == CODEX_STATUS


def test_codex_logged_in_keeps_nothing_after_the_dash(answers):
    answers["codex"] = (0, "", CODEX_WARNING + "Logged in using an API key - sk-proj-***lmnop\n")
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": "/c"})
    assert found == LoginStatus(
        YES, "Pay per use (API key)", file="/c/auth.json", file_words=CODEX_FILE, choice="usage"
    )
    assert "lmnop" not in repr(found)


def test_codex_chatgpt_in_its_default_home(answers):
    answers["codex"] = (0, "Logged in using ChatGPT\n", "")
    found = providers.get("codex").login_status({"HOME": "/h"})
    assert found == LoginStatus(
        YES, "ChatGPT plan", file="/h/.codex/auth.json", file_words=CODEX_FILE, choice="chatgpt"
    )


def test_codex_an_api_key_variable_is_a_login_without_the_command(answers):
    """Codex's TUI does not read OPENAI_API_KEY: LADO hands it to its agents
    (lado.providers.codex), so Codex's status would not say."""
    found = providers.get("codex").login_status({"HOME": "/h", "OPENAI_API_KEY": "sk-canary"})
    assert found == LoginStatus(
        YES, "Pay per use (API key)", variable="OPENAI_API_KEY", choice="usage"
    )
    assert answers["calls"] == []
    assert "canary" not in repr(found)


@pytest.mark.parametrize("line", ["personal access token", "access token"])
def test_codex_an_access_token(answers, line):
    """Codex reads CODEX_ACCESS_TOKEN itself, before its file, and wins over a key."""
    answers["codex"] = (0, "", f"Logged in using {line}\n")
    env = {"HOME": "/h", "CODEX_ACCESS_TOKEN": "at-canary", "OPENAI_API_KEY": "sk-x"}
    found = providers.get("codex").login_status(env)
    assert found == LoginStatus(
        YES, "ChatGPT access token", variable="CODEX_ACCESS_TOKEN", choice="token"
    )
    # One stored by `codex login --with-access-token` is the file's.
    found = providers.get("codex").login_status({"HOME": "/h"})
    assert (found.variable, found.file, found.choice) == ("", "/h/.codex/auth.json", "token")


@pytest.mark.parametrize("store", ["keyring", "auto"])
def test_codex_a_login_in_the_keyring_is_none_the_agents_can_read(answers, tmp_path, store):
    (tmp_path / "config.toml").write_text(f'cli_auth_credentials_store = "{store}"\n')
    answers["codex"] = lambda argv: (
        (1, "", "Not logged in\n") if "-c" in argv else (0, "", "Logged in using ChatGPT\n")
    )
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": str(tmp_path)})
    assert found == LoginStatus(NO, keyring=True)
    assert [argv for argv, _ in answers["calls"]] == [CODEX_STATUS, CODEX_STATUS[:3]]
    # Not logged in there either: plainly none.
    answers["codex"] = (1, "", "Not logged in\n")
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": str(tmp_path)})
    assert found == LoginStatus(NO)


def test_codex_without_a_keyring_store_asks_once(answers, tmp_path):
    answers["codex"] = (1, "", "Not logged in\n")
    providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": str(tmp_path)})
    assert len(answers["calls"]) == 1


def test_codex_error_is_unknown(answers):
    error = 'Error loading configuration: CODEX_HOME points to "/c", but that path does not exist\n'
    answers["codex"] = (1, "", error)
    found = providers.get("codex").login_status({"HOME": "/h", "CODEX_HOME": "/c"})
    assert found.state == UNKNOWN
    assert "Error loading configuration" in found.problem


def test_codex_logs_in_by_its_variables_and_says_where_the_keyring_cannot_be_read():
    codex = providers.get("codex")
    assert codex.login_variables == ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN")
    assert codex.login_note == ""
    assert codex.keyring_note == (
        "Your Codex keeps its login in the system keyring, which Codex agents cannot read. "
        "Log in here: the login goes to Codex's login file, and your own Codex keeps using "
        "the keyring."
    )
    assert all(providers.get(n).keyring_note == "" for n in providers.names() if n != "codex")


def _codex_needs(tmp_path, text=None):
    if text is not None:
        (tmp_path / "config.toml").write_text(text)
    return providers.get("codex").needs_login({"HOME": "/h", "CODEX_HOME": str(tmp_path)})


@pytest.mark.parametrize(
    "text, needs",
    [
        (None, True),  # OpenAI's model by default
        ('model_provider = "openai"\n', True),
        ('model_provider = "ollama"\n', False),
        ('model_provider = "lmstudio"\n', False),
        ('model_provider = "x"\n[model_providers.x]\nrequires_openai_auth = true\n', True),
        ('model_provider = "x"\n[model_providers.x]\nenv_key = "X_KEY"\n', False),
        ('profile = "p"\n[profiles.p]\nmodel_provider = "ollama"\n', False),
        ('model_provider = "ollama"\nprofile = "p"\n[profiles.p]\nmodel = "m"\n', False),
        (
            'model_provider = "ollama"\nprofile = "p"\n[profiles.p]\nmodel_provider = "openai"\n',
            True,
        ),
        ("= broken", True),  # the status decides; an unknown one never refuses
    ],
)
def test_codex_needs_a_login_by_its_model_provider(tmp_path, text, needs):
    assert _codex_needs(tmp_path, text) is needs


def test_codex_a_profile_without_a_provider_falls_back_to_the_top_level(tmp_path):
    assert not _codex_needs(tmp_path, 'model_provider = "ollama"\nprofile = "p"\n[profiles.p]\n')


@pytest.mark.parametrize(
    "text, needs",
    [
        ('model_providers = "x"\n', True),
        ('model_provider = "x"\nmodel_providers = "x"\n', False),
        ('model_provider = "x"\n[model_providers]\nx = "y"\n', False),
        ('profile = ["a"]\n[profiles.p]\nmodel_provider = "ollama"\n', True),
        ('profile = "p"\nprofiles = "p"\n', True),
        ('profile = "p"\n[profiles]\np = 1\n', True),
    ],
)
def test_codex_a_config_of_odd_types_is_read_as_codex_would_not_crash(tmp_path, text, needs):
    """A value of another type than Codex's is no table: never a crash of `lado doctor`,
    Settings or a start."""
    assert _codex_needs(tmp_path, text) is needs


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
def test_each_choice_logs_in_by_a_login_variable_or_a_login_action(name):
    provider = providers.get(name)
    actions = {a.id for a in provider.login_actions()}
    for choice in provider.login_choices:
        assert bool(choice.variable) != bool(choice.action), choice
        assert choice.variable in provider.login_variables or choice.action in actions
    assert bool(provider.login_choices) == bool(provider.login_question)


def test_codex_asks_how_the_human_pays():
    codex = providers.get("codex")
    assert codex.login_question == "How do you pay for Codex?"
    assert [(c.id, c.title, c.variable, c.action) for c in codex.login_choices] == [
        ("chatgpt", "ChatGPT plan — Plus, Pro, Business or Enterprise", "", "login"),
        ("token", "ChatGPT Business or Enterprise — access token", "CODEX_ACCESS_TOKEN", ""),
        ("usage", "Pay per use — OpenAI API key", "OPENAI_API_KEY", ""),
    ]
    assert [c.detail for c in codex.login_choices] == [
        "Sign in with your ChatGPT account by a one-time code: LADO shows a link and a code, "
        "you open the link on any device and enter the code.",
        "Paste an access token your workspace admin made in ChatGPT's admin console (Codex "
        "access tokens).",
        "Paste an API key from platform.openai.com.",
    ]
    file = ("-c", 'cli_auth_credentials_store="file"')
    assert [(a.id, a.label, a.argv, a.help) for a in codex.login_actions()] == [
        (
            "login",
            "Get a sign-in code",
            ("codex", "login", "--device-auth", *file),
            "This window closes by itself once you are signed in.",
        ),
        ("logout", "Log out…", ("codex", "logout", *file), ""),
    ]


# Codex 0.162.0's `codex login --device-auth` as tmux's capture-pane -J gives it (recorded
# 2026-11-01 in LADO's image), and the same with its colours and wrapped at 60 columns.
CODEX_CODE = """\
Welcome to Codex [v0.162.0]
OpenAI's command-line coding agent

Follow these steps to sign in with ChatGPT using device code authorization:

1. Open this link in your browser and sign in to your account
   https://auth.openai.com/codex/device

2. Enter this one-time code (expires in 15 minutes)
   UD75-FNMVY

Continue only if you started this login in Codex. If a website or another person gave you \
this code, cancel.



"""
CODE_WARNING = (
    "Continue only if you started this login in Codex. If a website or another person gave "
    "you this code, cancel."
)
CODEX_COLOURED = (
    "Welcome to Codex [v\x1b[90m0.162.0\x1b[39m]\n"
    "\x1b[90mOpenAI's command-line coding agent\n\n"
    "\x1b[39mFollow these steps to sign in with ChatGPT using device code authorization:\n\n"
    "1. Open this link in your browser and sign in to your account\n"
    "   \x1b[94mhttps://auth.openai.com/codex/device\n\n"
    "\x1b[39m2. Enter this one-time code \x1b[90m(expires in 15 minutes)\n"
    "\x1b[39m   \x1b[94mUD75-FNMVY\n\n"
    "\x1b[90mContinue only if you started this login in Codex. If a website or another\n"
    "person gave you this code, cancel.\x1b[39m\n"
)
CODEX_PROMPT = base.LoginPrompt(
    "https://auth.openai.com/codex/device", "UD75-FNMVY", "expires in 15 minutes", (CODE_WARNING,)
)


def test_codex_s_login_window_shows_its_link_and_code():
    codex = providers.get("codex")
    assert codex.login_prompt(CODEX_CODE) == CODEX_PROMPT
    assert codex.login_prompt(CODEX_COLOURED) == CODEX_PROMPT  # wrapped, coloured
    assert [a.shows_code for a in codex.login_actions()] == [True, False]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Welcome to Codex [v0.162.0]\n",
        CODEX_CODE.split("2. Enter")[0],  # the link, no code yet
        CODEX_CODE.replace("https://auth", "http://auth"),  # only https is shown
        CODEX_CODE.replace("UD75-FNMVY", "a code"),
    ],
    ids=["empty", "welcome", "no-code", "http", "no-code-token"],
)
def test_codex_s_partial_or_other_output_shows_no_code(text):
    assert providers.get("codex").login_prompt(text) is None


def test_the_code_before_its_warning_is_shown_without_it():
    partial = CODEX_CODE.split("Continue only")[0]
    assert providers.get("codex").login_prompt(partial) == base.LoginPrompt(
        CODEX_PROMPT.link, CODEX_PROMPT.code, CODEX_PROMPT.expires, ()
    )
    # Its end, with no warning: Codex's error is no line of the prompt.
    ended = partial + "Error: device auth timed out after 15 minutes\n"
    assert providers.get("codex").login_prompt(ended).lines == ()


def test_other_providers_show_no_code():
    for name in ("claude", "opencode", "kilo"):
        provider = providers.get(name)
        assert provider.login_prompt(CODEX_CODE) is None
        assert not any(a.shows_code for a in provider.login_actions())
