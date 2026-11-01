"""The window of an agent whose CLI needs a login and has none: it waits, then runs the CLI.

lado.runtime starts such an agent's window with `command` instead of lado.agent_env's, and
marks the agent waiting with lado.logins.wait_reason. The window (`lado login-wait`, a
hidden command, so a test's fake providers are known to it as to the hooks) reads and
removes its file as lado.agent_env does, says what it waits for, and every
lado.logins.POLL seconds asks the provider's login_status again, with the file layers read
anew (the outside folder, LADO's secrets, the session's project) over the environment it
holds, never over LADO's and the provider's own variables, and the provider's login taken
whole from one layer (lado.agent_env.merge; the file keeps the login shell's own login
variables for that); a login shell's change needs a new agent. Once the CLI is logged in,
or LADO cannot tell (unknown never holds an agent), it settles what the CLI asks first
(Provider.first_hook_blocker: Claude Code's trust and first run, Codex's login file or the
key saved meanwhile), tells loop.log what it did, and replaces itself with the CLI.
"""

import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from lado import agent_env, logins, loop, project_secrets, providers, state
from lado.providers import base


def command(
    file: Path,
    provider: str,
    env: Mapping[str, str],
    ours: list[str],
    project: str | None,
    shell_login: Mapping[str, str],
    argv: list[str],
) -> list[str]:
    """The waiting window's command: `argv` of `provider` once logged in, with `env`, whose
    names `ours` (LADO's and the provider's) no layer replaces; `project` the session's;
    `shell_login` the login shell layer's values of the provider's login variables, which
    `env` may no longer hold (lado.agent_env.merge). Both go into `file`, readable by the
    user only, until the window reads it."""
    agent_env.check_program(argv[0], env)
    held = {"env": dict(env), "ours": ours, "project": project, "shell_login": dict(shell_login)}
    agent_env.write_private(file, held)
    return providers.lado_command("login-wait", provider, str(file), *argv)


def layers(
    env: dict[str, str],
    ours: list[str],
    project: str | None,
    login: tuple[str, ...],
    shell_login: Mapping[str, str],
) -> dict[str, str]:
    """`env` with the file layers read now over it, and its own `ours` over those; the
    login variables `login` taken whole from one layer, of which `shell_login` (the login
    shell's) is the lowest."""
    base = {name: value for name, value in env.items() if name not in login}
    found = agent_env.Layers(
        {**base, **shell_login},
        agent_env.outside(env).values,
        agent_env.lado_secrets().values,
        project_secrets.layer(project) if project else {},
    )
    kept = {name: env[name] for name in ours if name in env}
    return {**agent_env.merge(found, login), **kept}


def main(args: list[str]) -> None:
    name, file, *argv = args
    data = json.loads(Path(file).read_text())
    Path(file).unlink()  # it holds the user's keys
    env, ours, project = data["env"], data["ours"], data["project"]
    shell_login = data["shell_login"]
    # This process's own LADO (lado.db, loop.log, LADO's secrets) is the agent's.
    for key in ("LADO_HOME", "LADO_TMUX_SOCKET"):
        if key in env:
            os.environ[key] = env[key]
    provider = providers.get(name)
    session, agent = env.get("LADO_SESSION", ""), env.get("LADO_AGENT", "")
    print(logins.wait_reason(provider), flush=True)
    while provider.login_status(env).state == base.NO:
        time.sleep(logins.POLL)
        env = layers(env, ours, project, provider.login_variables, shell_login)
    said = f"{provider.title} is logged in: starting it"
    print(said, flush=True)
    loop.log(session, f"{agent}: {said}")
    blocker = provider.first_hook_blocker(os.getcwd(), env)
    for note in blocker.notes:  # LADO's own writes: loop.log only, no line in the terminal
        loop.log(session, f"{agent}: {note}")
    for line in (blocker.reason, blocker.warning):
        if line:
            print(line, flush=True)
            loop.log(session, f"{agent}: {line}")
    # The CLI's launch, from which the session loop counts its silence (runtime
    # .check_starts); before it is starting, so the wait for the login is never counted.
    state.window_opened(session, agent)
    if blocker.reason:
        state.block(session, agent, blocker.reason)
    else:
        state.set_status(session, agent, state.STARTING)  # no longer waiting for the login
    env.update({k: os.environ[k] for k in agent_env.PANE_VARS if k in os.environ})
    os.execvpe(argv[0], argv, env)


if __name__ == "__main__":
    main(sys.argv[1:])
