"""The agent CLIs' logins: what Settings → Providers and environment and `lado doctor` show,
the agents that wait for one, and the login windows.

Each provider reads its own CLI's login (Provider.login_status) and names its login
commands, the choices Settings offers and the variables that log it in; nothing here knows
any CLI's output. The state is read in the environment LADO's agents of that CLI get
without a project (`environment`): the login shell's, the outside folder's and LADO's
secrets, with the CLI's login taken whole from one layer (lado.agent_env.merge). Which
layer gives the login is the core's to say (`layer`); a login of the CLI's own file, the
provider's (LoginStatus.file_words).

A new session or worker whose CLI needs a login (Provider.needs_login) and has none is
refused before anything of it is made (`refusal`, lado.runtime.check_login); a resumed agent
of such a CLI waits from its start with `wait_reason` instead (lado.runtime,
lado.login_wait), as does one whose login went between the check and its launch. The
server finds the agents that wait by that reason, so the texts live here alone.

A login window is a tmux session of its own on LADO's server, one per provider, named
`lado-login-<provider>` and labelled with user options (LOGIN, HOME): it runs the CLI's
login or logout command (OpenCode's, Kilo's, Codex's sign-in code) with the agents'
environment (lado.agent_env.command), under `main`, which writes its exit status. When the
command ends its pane stays, dead, with its text, and the window counts as ended; `look`
reads them and ends it.
`lado stop --all` and the UI server's start and stop end the windows by their labels,
never by name; they are no LADO session, so `lado ls` and the runtime never see them. The
UI streams one through lado.terminal (`open_login`), and lado.server.terminals watches it
with `look`: the link and the code of an action that shows one, and how it ended.
"""

import contextlib
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from lado import agent_env, gui_session, interpreter, project_secrets, providers, state, tmux
from lado.providers import base

SETTINGS = "Settings → Providers and environment"
POLL = 3.0  # seconds between two looks of an agent that waits for a login (lado.login_wait)

# The layers a login variable comes from, as the page and `lado doctor` name them.
SECRET = "LADO's secret"
OUTSIDE = "outside folder"
SHELL = "login shell"
INHERITED = "the process that starts LADO"

LOGIN, HOME, ACTION = "@lado-login", "@lado-home", "@lado-login-action"  # a window's labels
PREFIX = "lado-login-"
# Its pane stays, dead, with its text and exit status once its command ended (`look`).
TERMINAL = {
    "prefix": "None",
    "prefix2": "None",
    "status": "off",
    "mouse": "on",
    "remain-on-exit": "on",
}
DEAD, STATUS = "pane_dead", "pane_dead_status"  # tmux's formats of a dead pane


def wait_reason(provider: base.Provider) -> str:
    """Why an agent of `provider` waits from its start: its CLI is not logged in."""
    names = provider.login_variables
    how = f"log in in {SETTINGS}" + (f", or set {names[0]}" if names else "")
    return f"{provider.title} is not logged in: {how}; the agent starts by itself once you do"


SESSION, WORKER = "session", "worker"  # what a refusal does not start
RESUME = "resume"  # a stopped session resumed by hand (lado start, the UI's Resume)


def refusal(provider: base.Provider, env: Mapping[str, str], what: str) -> str | None:
    """Why a new `what` (SESSION or WORKER) of `provider`, or a RESUME of a session whose
    supervisor it starts, is not started: its agents need a login in `env`, the
    environment they would start from (Provider.needs_login), and its status there says
    none. None otherwise, also when the status cannot be read: that never refuses (the
    launch warns)."""
    if not provider.needs_login(env):
        return None
    if provider.login_status(dict(env)).state != base.NO:
        return None
    done = "the session was not resumed" if what == RESUME else f"the {what} was not started"
    head = f"{provider.title} is not logged in, so {done}"
    if what == WORKER:
        return (
            f"{head}: ask the human to log in in {SETTINGS}, or start the worker with "
            "another provider"
        )
    how = f"log in in LADO's UI ({SETTINGS}, `lado ui`)"
    if names := provider.login_variables:
        how += f", or set {names[0]} as LADO's secret or a project secret"
    return f"{head}: {how}"


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


def environment(provider: base.Provider, found: agent_env.Layers | None = None) -> dict[str, str]:
    """The environment the agents of `provider` in a session without a project get, before
    LADO's and their provider's own variables: `found` (the layers, read now when None;
    AgentEnvError when the login shell fails) merged with its login taken whole from one
    layer."""
    return agent_env.merge(agent_env.layers() if found is None else found, provider.login_variables)


def layer(name: str, found: agent_env.Layers, login: Iterable[str] = ()) -> str:
    """Which of `found`'s layers (a session's without a project) gives `name` to an agent
    whose CLI's login variables are `login`: LADO's secrets, the outside folder, or the
    login shell (or the starting process); "" when it gets none."""
    login = tuple(login)
    if not agent_env.merge(found, login).get(name):
        return ""
    names = login if name in login else (name,)
    shell = INHERITED if agent_env.source() == agent_env.INHERIT else SHELL
    for words, values in ((SECRET, found.secrets), (OUTSIDE, found.outside), (shell, found.shell)):
        if any(values.get(n) for n in names):
            return words
    return ""


@dataclass(frozen=True)
class AgentRef:
    session: str
    agent: str


@dataclass
class Login:
    """One provider's login as Settings shows it; no value of any variable."""

    provider: base.Provider
    status: base.LoginStatus
    layer: str  # of status.variable; "" for none
    # Where the login comes from, for the state line: `layer`, else the CLI's own file in
    # the provider's words (LoginStatus.file_words); "" when neither says.
    where: str = ""
    waiting: list[AgentRef] = field(default_factory=list)
    running: list[AgentRef] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    window: bool = False  # a login window of it is open
    # Its agents need a login (Provider.needs_login), asked in the environment `status` is
    # read in.
    needs_login: bool = False


def read(
    provider: base.Provider,
    layers: agent_env.Layers,
    full: bool = True,
    status: base.LoginStatus | None = None,
) -> Login:
    """`provider`'s login read now in the environment its agents get of `layers`
    (`environment`), unless `status` is given (e.g. why it cannot be read), with the agents
    and projects that concern it (lado.db read as it is) unless not `full`."""
    env = environment(provider, layers)
    status = status or provider.login_status(env)
    given = layer(status.variable, layers, provider.login_variables) if status.variable else ""
    found = Login(provider, status, given, given or status.file_words)
    found.needs_login = provider.needs_login(env)
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


def check_secret(provider: base.Provider, name: str, value: str) -> None:
    """ValueError unless `value` may be kept as LADO's secret `name`: one of `provider`'s
    login variables, not empty, and a value the agents get (agent_env.value_problem), so
    Settings never shows as set what no agent gets."""
    check_variable(provider, name)
    if not value:
        raise ValueError(f"{name} needs a value")
    if problem := agent_env.value_problem(name, value):
        raise ValueError(problem)


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


@dataclass(frozen=True)
class Window:
    name: str  # its tmux session
    action: str  # the id of the login action it runs
    dead: bool  # its command ended; its pane is kept until LADO reads it
    status: int | None  # tmux's exit status once dead; None for a signal or none given


def windows() -> dict[str, Window]:
    """This LADO_HOME's login windows, those whose command ended too, by provider name."""
    home = _home()
    try:
        rows = tmux.sessions_with(LOGIN, HOME, ACTION, DEAD, STATUS)
    except tmux.TmuxError:
        return {}
    found = {}
    for name, login, of_home, chosen, dead, status in rows:
        if login and of_home == home:
            code = int(status) if dead == "1" and status.lstrip("-").isdigit() else None
            found[login] = Window(name, chosen, dead == "1", code)
    return found


def open_windows() -> dict[str, str]:
    """This LADO_HOME's login windows whose command runs: tmux session by provider name. One
    whose command ended counts as ended."""
    return {login: w.name for login, w in windows().items() if not w.dead}


@dataclass(frozen=True)
class Ended:
    status: int | None  # the command's exit status; None when a signal ended it
    said: str  # the last line it printed that is not blank, as it wrote it


@dataclass(frozen=True)
class Look:
    """A login window as `look` found it: what its command asks the human (an action that
    shows_code), and how it ended."""

    prompt: base.LoginPrompt | None = None
    ended: Ended | None = None


def look(provider: base.Provider, prompt: bool = True) -> Look | None:
    """`provider`'s login window now; None when none is open. With `prompt`, and when its
    action shows_code, its text is read for the link and the code (Provider.login_prompt).
    Once its command ended, its text and status are read and the window ends: its command's
    last line is never lost, also one printed just before its exit."""
    window = windows().get(provider.name)
    if window is None:
        return None
    try:
        shows = prompt and action(provider, window.action).shows_code
    except ValueError:
        shows = False  # a window of another LADO version's action
    if not window.dead and not shows:
        return Look()
    try:
        text = tmux.pane_text(window.name)
    except tmux.TmuxError:
        return None  # it ended meanwhile (Close)
    found = provider.login_prompt(text) if shows else None
    if not window.dead:
        return Look(found)
    with contextlib.suppress(tmux.TmuxError):
        tmux.kill_session(window.name)
    said = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")
    return Look(found, Ended(_status(provider, window), said))


def status_file(provider: base.Provider) -> Path:
    """Where the login window's wrapper (`main`) keeps its command's exit status."""
    return state.home() / "logins" / f"{provider.name}.status"


def _status(provider: base.Provider, window: Window) -> int | None:
    """The exit status of the dead `window`'s command, as its wrapper wrote it, read once;
    else tmux's. Under load tmux may list a pane dead and never give its status."""
    file = status_file(provider)
    try:
        written = file.read_text().strip()
        file.unlink()
    except OSError:
        return window.status
    return int(written) if written.lstrip("-").isdigit() else window.status


def open_window(provider: base.Provider, id: str) -> str:
    """Open `provider`'s login window running its action `id` (ValueError for none such)
    with the agents' environment; the one running already is returned as it is, one whose
    command ended is replaced. Its tmux session's name."""
    chosen = action(provider, id)
    if found := windows().get(provider.name):
        if not found.dead:
            return found.name
        with contextlib.suppress(tmux.TmuxError):
            tmux.kill_session(found.name)
    name = tmux_name(provider)
    env = environment(provider)
    folder = state.home() / "logins"
    folder.mkdir(mode=0o700, exist_ok=True)
    agent_env.check_program(chosen.argv[0], env)  # the CLI, not the wrapper's Python
    status = status_file(provider)
    status.unlink(missing_ok=True)  # an earlier window's
    wrapped = [*interpreter.run_module("lado.logins", str(status)), *chosen.argv]
    command = agent_env.command(folder / f"{provider.name}.json", env, wrapped)
    cwd = env.get("HOME") or str(Path.home())
    labels = {LOGIN: provider.name, HOME: _home(), ACTION: chosen.id, **TERMINAL}
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
    found = windows().get(provider.name)
    if found is None:
        return False
    try:
        tmux.kill_session(found.name)
    except tmux.TmuxError:
        return False  # it ended meanwhile
    return True


def end_windows() -> list[str]:
    """End every login window of this LADO_HOME, found by its labels; their names."""
    ended = []
    for found in windows().values():
        try:
            tmux.kill_session(found.name)
        except tmux.TmuxError:
            continue
        ended.append(found.name)
    return ended


def main(args: list[str]) -> None:
    """A login window's command (`python -m lado.logins <status file> <argv>...`): run the
    CLI's login command on the window's terminal, write its exit status (a signal's as
    -N), atomically, and end with it. Ctrl+C reaches the command, which decides."""
    file, *argv = args
    process = subprocess.Popen(argv)
    while True:
        try:
            code = process.wait()
            break
        except KeyboardInterrupt:
            continue
    written = Path(f"{file}.part")
    written.write_text(f"{code}\n")
    os.replace(written, file)
    sys.exit(code if code >= 0 else 128 - code)


if __name__ == "__main__":
    main(sys.argv[1:])
