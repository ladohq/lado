"""The agent CLIs' logins: what Settings → Providers and environment and `lado doctor` show,
the agents that wait for one, and the login windows.

Each provider reads its own CLI's login (Provider.login_status) and names its login and
logout commands and the variables that log it in; nothing here knows any CLI's output. The
state is read in the environment LADO's agents get without a project (`environment`):
the login shell's, the outside folder's and LADO's secrets (lado.agent_env.resolve). Where
the variable that logs a CLI in comes from is the core's to say (`layer`).

An agent whose CLI needs a login (Capabilities.needs_login) and has none waits from its
start with `wait_reason` (lado.runtime, lado.login_wait); the server finds the agents that
wait by that reason, so the text lives here alone.

A login window is a tmux session of its own on LADO's server, one per provider, named
`lado-login-<provider>` and labelled with user options (LOGIN, HOME): it runs the CLI's
login or logout command with the agents' environment (lado.agent_env.command) and ends
with it. `lado stop --all` and the UI server's start and stop end the windows by their
labels, never by name; they are no LADO session, so `lado ls` and the runtime never see
them. The UI streams one through lado.terminal (`open_login`).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from lado import agent_env, gui_session, project_secrets, providers, state, tmux
from lado.providers import base

SETTINGS = "Settings → Providers and environment"
POLL = 3.0  # seconds between two looks of an agent that waits for a login (lado.login_wait)

# The layers a login variable comes from, as the page and `lado doctor` name them.
SECRET = "LADO's secret"
OUTSIDE = f"the outside folder ({agent_env.ENV_DIR_VAR})"
SHELL = "the login shell"
INHERITED = "the process that starts LADO"

LOGIN, HOME = "@lado-login", "@lado-home"  # a login window's labels
PREFIX = "lado-login-"
TERMINAL = {"prefix": "None", "prefix2": "None", "status": "off", "mouse": "on"}


def wait_reason(provider: base.Provider) -> str:
    """Why an agent of `provider` waits from its start: its CLI is not logged in."""
    names = provider.login_variables
    how = f"log in in {SETTINGS}" + (f", or set {names[0]}" if names else "")
    return f"{provider.title} is not logged in: {how}; the agent starts by itself once you do"


def waits_for(agent: state.Agent, reason: str | None) -> str | None:
    """The provider whose login `agent` waits for, by its block `reason`; None for another
    reason or none."""
    if not reason:
        return None
    try:
        provider = providers.get(agent.provider)
    except ValueError:
        return None
    return provider.name if reason == wait_reason(provider) else None


def environment(project: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment the agents of a session without a project get, before LADO's and
    their provider's own variables (AgentEnvError when the login shell fails)."""
    return agent_env.resolve(project)


def layer(name: str, env: Mapping[str, str]) -> str:
    """Which layer gives `name` in `env` (built by `environment`): LADO's secrets, the
    outside folder, or the login shell (or the starting process); "" when unset."""
    if not env.get(name):
        return ""
    if name in agent_env.lado_secrets().values:
        return SECRET
    if name in agent_env.outside().values:
        return OUTSIDE
    return INHERITED if agent_env.source() == agent_env.INHERIT else SHELL


@dataclass(frozen=True)
class AgentRef:
    session: str
    agent: str


@dataclass(frozen=True)
class Variable:
    """A login variable: whether LADO's secrets hold it, and which layer gives it now."""

    name: str
    secret: bool
    layer: str


@dataclass
class Login:
    """One provider's login as Settings shows it; no value of any variable."""

    provider: base.Provider
    status: base.LoginStatus
    layer: str  # of status.variable; "" for none
    variables: list[Variable] = field(default_factory=list)
    waiting: list[AgentRef] = field(default_factory=list)
    running: list[AgentRef] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    window: bool = False  # a login window of it is open


def read(
    provider: base.Provider,
    env: Mapping[str, str],
    full: bool = True,
    status: base.LoginStatus | None = None,
) -> Login:
    """`provider`'s login read now in `env` (`environment`), unless `status` is given
    (e.g. why it cannot be read), with the agents and projects that concern it (lado.db
    read as it is) unless not `full`."""
    status = status or provider.login_status(dict(env))
    found = Login(provider, status, layer(status.variable, env) if status.variable else "")
    held = set(project_secrets.lado_names())
    found.variables = [Variable(n, n in held, layer(n, env)) for n in provider.login_variables]
    if not full:
        return found
    if state.schema_version() is not None:
        try:
            found.waiting, found.running = agents(provider)
            found.projects = projects_with_login(provider)
        except state.SchemaError:
            pass  # lado.db of another schema: no agents to name
    found.window = provider.name in open_windows()
    return found


def source(found: Login) -> str:
    """Where a login comes from, for humans: the variable and its layer, else the CLI's
    file; "" when the CLI names neither."""
    if found.status.variable:
        return (
            f"{found.status.variable} from {found.layer}" if found.layer else found.status.variable
        )
    return found.status.file


def logout(provider: base.Provider) -> None:
    """Run `provider`'s logout that asks nothing (Provider.logout_argv) with the agents'
    environment: ValueError when it has none, RuntimeError with why when it fails."""
    argv = provider.logout_argv()
    if argv is None:
        raise ValueError(f"{provider.title} logs out in its login window")
    found = base.run_status(argv, environment())
    if isinstance(found, str):
        raise RuntimeError(found)
    if found.returncode != 0:
        command = " ".join(argv)
        why = base.error_line(f"exit status {found.returncode}", found.stderr or found.stdout)
        raise RuntimeError(f"`{command}` failed with {why}")


def agents(provider: base.Provider) -> tuple[list[AgentRef], list[AgentRef]]:
    """The live agents of `provider` that wait for its login, and all its live agents."""
    reason = wait_reason(provider)
    waiting, running = [], []
    for sess in state.list_sessions():
        if sess.stopped_at:
            continue
        blocked = state.block_reasons(sess.name)
        for agent in state.list_agents(sess.name):
            if agent.provider != provider.name or agent.status == state.STOPPED:
                continue
            ref = AgentRef(sess.name, agent.name)
            running.append(ref)
            if agent.status == state.WAITING and blocked.get(agent.name) == reason:
                waiting.append(ref)
    return waiting, running


def projects_with_login(provider: base.Provider) -> list[str]:
    """The projects whose variables or secrets set one of `provider`'s login variables, by
    id: their sessions' agents get that one instead."""
    names = set(provider.login_variables)
    if not names:
        return []
    return [
        p.id
        for p in state.list_projects()
        if names & (state.project_variables(p.id).keys() | set(project_secrets.names(p.id)))
    ]


def check_variable(provider: base.Provider, name: str) -> None:
    """ValueError unless `name` is one of `provider`'s login variables: LADO's secrets hold
    only those."""
    if name not in provider.login_variables:
        allowed = ", ".join(provider.login_variables) or "none"
        raise ValueError(
            f"{name} is not a login variable of {provider.title} (LADO's secrets take: {allowed})"
        )


# The login windows.


def tmux_name(provider: base.Provider) -> str:
    return PREFIX + provider.name


def _home() -> str:
    return str(state.home().resolve())


def action(provider: base.Provider, id: str) -> base.LoginAction:
    for found in provider.login_actions():
        if found.id == id:
            return found
    known = ", ".join(a.id for a in provider.login_actions()) or "none"
    raise ValueError(f'{provider.title} has no login action "{id}" (known: {known})')


def open_windows() -> dict[str, str]:
    """This LADO_HOME's login windows: tmux session by provider name."""
    home = _home()
    try:
        rows = tmux.sessions_with(LOGIN, HOME)
    except tmux.TmuxError:
        return {}
    return {login: name for name, login, of_home in rows if login and of_home == home}


def open_window(provider: base.Provider, id: str) -> str:
    """Open `provider`'s login window running its action `id` (ValueError for none such)
    with the agents' environment; the one open already is returned as it is. Its tmux
    session's name."""
    chosen = action(provider, id)
    if running := open_windows().get(provider.name):
        return running
    name = tmux_name(provider)
    env = environment()
    folder = state.home() / "logins"
    folder.mkdir(mode=0o700, exist_ok=True)
    command = agent_env.command(folder / f"{provider.name}.json", env, list(chosen.argv))
    cwd = env.get("HOME") or str(Path.home())
    labels = {LOGIN: provider.name, HOME: _home(), **TERMINAL}
    tmux.new_labelled_session(
        name,
        cwd if os.path.isdir(cwd) else "/",
        command,
        labels,
        before_attempt=lambda: gui_session.ensure_server(tmux.socket()),
    )
    return name


def close_window(provider: base.Provider) -> bool:
    """End `provider`'s login window and its command; False when none is open."""
    name = open_windows().get(provider.name)
    if name is None:
        return False
    try:
        tmux.kill_session(name)
    except tmux.TmuxError:
        return False  # it ended meanwhile
    return True


def end_windows() -> list[str]:
    """End every login window of this LADO_HOME, found by its labels; their names."""
    ended = []
    for name in open_windows().values():
        try:
            tmux.kill_session(name)
        except tmux.TmuxError:
            continue
        ended.append(name)
    return ended
